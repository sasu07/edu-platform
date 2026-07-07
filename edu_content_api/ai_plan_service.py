"""
Serviciu AI pentru generarea planului de studiu personalizat
și a opțiunilor MCQ pentru testul diagnostic.
Folosește Claude (Anthropic) dacă ANTHROPIC_API_KEY e setat.
"""

import json
import math
import os
import random
import re
from datetime import date
from typing import Optional


# ─── MCQ Batch Generation via Claude ─────────────────────────────────────────

def generate_mcq_batch(exercises: list) -> list | None:
    """
    Generează opțiuni MCQ pentru o listă de exerciții via Claude.
    Fiecare element din exercises: {id, statement_latex, solution_latex, scoring_guide_latex}
    Returnează o listă de dicts: {exercise_id, options: [str,str,str,str], correct_index: int}
    sau None dacă API-ul nu e disponibil.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic  # noqa: PLC0415

        # Construim prompt-ul cu toate exercițiile
        ex_lines = []
        for i, ex in enumerate(exercises):
            stmt = (ex.get("statement_latex") or "").strip()[:400]
            sol  = (ex.get("solution_latex") or ex.get("scoring_guide_latex") or "").strip()[:300]
            ex_lines.append(
                f"[{i}] ID:{ex['id']}\n"
                f"Enunț: {stmt}\n"
                f"Soluție/Barem: {sol if sol else 'nedisponibilă'}"
            )

        exercises_text = "\n\n".join(ex_lines)

        prompt = f"""Ești profesor de matematică pentru Bacalaureat România (mate-info).

Pentru fiecare exercițiu de mai jos, generează 4 variante de răspuns (A, B, C, D):
- Una este CORECTĂ
- Trei sunt INCORECTE dar plauzibile (greșeli tipice ale elevilor)

Reguli:
- Pentru exerciții de calcul: opțiunile să fie expresii/numere concrete
- Pentru demonstrații: opțiunile să fie afirmații despre concluzia demonstrației
- Opțiunile să fie scurte (max 30 caractere fiecare)
- Nu folosi LaTeX complex — preferă forma text sau LaTeX simplu ($x$, $\\sqrt{{2}}$)

Exerciții:
{exercises_text}

Returnează EXCLUSIV un JSON valid (fără text suplimentar):
[
  {{
    "exercise_index": 0,
    "options": ["opț A", "opț B", "opț C", "opț D"],
    "correct_index": 0
  }},
  ...
]
Numărul de obiecte trebuie să fie exact {len(exercises)}."""

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if match:
            raw = match.group(1)

        data = json.loads(raw)

        # Validăm și indexăm după exercise_index
        result = []
        for item in data:
            idx = item.get("exercise_index", 0)
            opts = item.get("options", [])
            cidx = item.get("correct_index", 0)
            if len(opts) == 4 and 0 <= cidx <= 3 and idx < len(exercises):
                result.append({
                    "exercise_id": exercises[idx]["id"],
                    "options": opts,
                    "correct_index": cidx,
                })

        return result if result else None

    except ImportError:
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f"[ai_plan_service] MCQ batch error: {e}")
        return None


# ─── Fallback MCQ fără AI ─────────────────────────────────────────────────────

def _extract_numeric(text: str) -> Optional[float]:
    """Extrage primul număr rezonabil dintr-un text de soluție/barem."""
    if not text:
        return None
    # Curăță comenzi LaTeX frecvente
    clean = re.sub(r'\\(?:frac|sqrt|left|right|cdot|times|div|pm|mp)\b', ' ', text)
    clean = re.sub(r'\\[a-zA-Z]+', ' ', clean)
    clean = re.sub(r'[{}$]', ' ', clean)

    # Caută ultima egalitate: "= X" sau "este X"
    for pattern in [
        r'=\s*([+\-]?\d+(?:[.,]\d+)?)',
        r'este\s+([+\-]?\d+(?:[.,]\d+)?)',
        r'egal\s+cu\s+([+\-]?\d+(?:[.,]\d+)?)',
        r'rezultatul\s+(?:este|e)\s+([+\-]?\d+(?:[.,]\d+)?)',
    ]:
        matches = re.findall(pattern, clean, re.IGNORECASE)
        if matches:
            try:
                v = float(matches[-1].replace(',', '.'))
                if math.isfinite(v) and abs(v) < 1e6:
                    return v
            except ValueError:
                pass

    # Ultimul număr întreg din text (max 4 cifre)
    all_ints = re.findall(r'\b([+\-]?\d{1,4})\b', clean)
    if all_ints:
        try:
            v = float(all_ints[-1])
            if math.isfinite(v):
                return v
        except ValueError:
            pass

    return None


def generate_mcq_no_ai(exercise: dict) -> tuple[list[str], int] | None:
    """
    Generează MCQ fără AI:
    1. Încearcă să extragă un număr din solution_latex sau scoring_guide_latex
    2. Dacă găsește → generează 3 distractor-e numerice
    3. Dacă nu → returnează None (exercițiu rămâne deschis)
    """
    sol = exercise.get("solution_latex") or ""
    barem = exercise.get("scoring_guide_latex") or ""
    ans_latex = exercise.get("answer_latex") or ""

    # 1. Răspuns numeric explicit
    if exercise.get("answer_numeric_value") is not None:
        try:
            return generate_mcq_options(float(exercise["answer_numeric_value"]), ans_latex)
        except Exception:
            pass

    # 2. Extrage din answer_latex
    if ans_latex:
        v = _extract_numeric(ans_latex)
        if v is not None:
            return generate_mcq_options(v, ans_latex)

    # 3. Extrage din barem (mai fiabil)
    v = _extract_numeric(barem)
    if v is not None:
        return generate_mcq_options(v, str(v))

    # 4. Extrage din soluție
    v = _extract_numeric(sol)
    if v is not None:
        return generate_mcq_options(v, str(v))

    return None


def generate_mcq_batch_no_ai(exercises: list) -> list:
    """
    Generează MCQ pentru toate exercițiile fără AI.
    Returnează lista de dicts cu exercise_id, options, correct_index.
    Exercițiile fără răspuns identificabil sunt omise (vor fi open-answer).
    """
    results = []
    for ex in exercises:
        result = generate_mcq_no_ai(ex)
        if result:
            opts, cidx = result
            results.append({
                "exercise_id": ex["id"],
                "options": opts,
                "correct_index": cidx,
            })
    return results


# ─── MCQ Distractor Generation (no AI needed) ────────────────────────────────

def _fmt_number(n: float) -> str:
    """Formatează un număr ca string lizibil."""
    if not math.isfinite(n):
        return str(n)
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    # Încearcă fracție simplă
    for d in range(2, 13):
        num = n * d
        if abs(num - round(num)) < 1e-9:
            return f"{int(round(num))}/{d}"
    return f"{n:.4g}"


def generate_mcq_options(answer_numeric: float, answer_latex: str) -> tuple[list[str], int]:
    """
    Generează 4 opțiuni MCQ pentru un exercițiu cu răspuns numeric.
    Returnează (options_shuffled, correct_index).

    Distractor-ele simulează greșeli tipice:
    - eroare de semn, ±1, ×2, ÷2, radical omis, etc.
    """
    n = answer_numeric
    correct_str = _fmt_number(n)

    candidates: list[float] = []

    # Erori tipice pentru întregi
    if abs(n - round(n)) < 1e-9:
        iv = int(round(n))
        for delta in [-2, -1, 1, 2, 3, -3]:
            candidates.append(float(iv + delta))
        candidates.append(float(-iv))
        candidates.append(float(abs(iv) * 2))
        if iv != 0 and iv % 2 == 0:
            candidates.append(float(iv // 2))
    else:
        # Număr fracționar / zecimal
        candidates.append(float(round(n + 1)))
        candidates.append(float(round(n - 1)))
        candidates.append(-n)
        candidates.append(float(round(n * 2, 4)))
        candidates.append(float(round(n / 2, 4)) if n != 0 else 1.0)
        # Încearcă să extragă numărătorul / numitorul ca distractor
        for d in range(2, 10):
            num = n * d
            if abs(num - round(num)) < 1e-9:
                candidates.append(float(int(round(num))))  # numărătorul
                candidates.append(float(d))               # numitorul
                break

    # Filtrare: nu egal cu corectul, finit, rezonabil
    def valid(c: float) -> bool:
        if abs(c - n) < 1e-6:
            return False
        if not math.isfinite(c):
            return False
        if abs(c) > max(500, abs(n) * 10 + 100):
            return False
        return True

    valid_candidates = [c for c in candidates if valid(c)]
    # Elimină duplicatele
    seen: set[str] = {correct_str}
    unique: list[float] = []
    for c in valid_candidates:
        s = _fmt_number(c)
        if s not in seen:
            seen.add(s)
            unique.append(c)

    random.shuffle(unique)
    distractors = unique[:3]

    # Dacă nu avem destui distractor-e, generăm padding simplu
    extra = 1
    while len(distractors) < 3:
        candidate = n + extra
        s = _fmt_number(candidate)
        if s not in seen:
            distractors.append(candidate)
            seen.add(s)
        extra += 1

    # Construim lista finală și o amestecăm
    all_opts = [_fmt_number(d) for d in distractors] + [correct_str]
    random.shuffle(all_opts)
    correct_idx = all_opts.index(correct_str)

    return all_opts, correct_idx


# ─── AI Plan Generation (Claude) ─────────────────────────────────────────────

def _build_prompt(diagnostic: dict, days_to_bac: int) -> str:
    topics = diagnostic.get("weak_topics", [])

    topic_lines = []
    for t in topics:
        label = t.get("topic_label") or t.get("topic_key", "—")
        score = t.get("score_pct", 0)
        correct = t.get("correct", 0)
        seen = t.get("seen", 0)
        subiect = t.get("subiect") or "?"
        emoji = "🔴" if score < 40 else "🟡" if score < 70 else "🟢"
        topic_lines.append(f"  {emoji} {label} (Subiectul {subiect}): {score}% — {correct}/{seen} corecte")

    topics_text = "\n".join(topic_lines) if topic_lines else "  — niciun topic evaluat —"

    score_pct = diagnostic.get("score_pct", 0)
    correct_count = diagnostic.get("correct_count", 0)
    total = diagnostic.get("total", 0)

    bac_date_str = "1 iulie 2026"

    return f"""Ești un profesor de matematică expert în pregătirea elevilor pentru Bacalaureatul din România (profil mate-info).

Un elev a completat testul diagnostic BAC. Rezultate:

📊 Scor general: {score_pct}% ({correct_count}/{total} corecte)
📅 Zile rămase până la BAC ({bac_date_str}): {days_to_bac}

📌 Rezultate pe topicuri:
{topics_text}

Pe baza acestor rezultate, creează un plan de studiu PERSONALIZAT și REALIST.
Planul trebuie să fie adaptat exact la lacunele acestui elev, nu generic.

Returnează EXCLUSIV un obiect JSON valid (fără markdown, fără explicații în afara JSON-ului):

{{
  "rezumat": "2-3 propoziții care descriu profilul elevului și prioritățile sale, menționate direct și onest",
  "nivel_general": "incepator|mediu|avansat",
  "saptamani": [
    {{
      "numar": 1,
      "titlu": "titlu scurt și motivant al săptămânii",
      "focus_principal": "ce topic/subiect e prioritar această săptămână",
      "obiective": [
        "obiectiv concret și măsurabil 1",
        "obiectiv concret și măsurabil 2"
      ],
      "topicuri_recomandate": ["topic_key_1", "topic_key_2"],
      "timp_zilnic_minute": 45,
      "strategie": "1-2 propoziții despre cum să abordeze această săptămână"
    }}
  ],
  "prioritati_urgente": ["topic slab 1 (justificare)", "topic slab 2 (justificare)"],
  "sfaturi_practice": [
    "sfat practic și specific 1",
    "sfat practic și specific 2",
    "sfat practic și specific 3"
  ],
  "motivatie": "mesaj motivațional scurt, sincer și adaptat nivelului acestui elev"
}}

Numărul de săptămâni: adaptează la zilele rămase până la BAC (max 6 săptămâni, min 2).
Dacă mai sunt sub 14 zile: focus INTENSIV pe topicurile cu cel mai mare impact la BAC (Subiectul I garantează 30 de puncte).
Dacă scorul e sub 40%: prioritizează fundamentele Subiectului I înainte de II și III.
Fii direct, nu sugarcoat lacunele — elevul are nevoie de un plan realist."""


def generate_ai_plan(diagnostic: dict) -> Optional[dict]:
    """
    Apelează Claude pentru a genera un plan personalizat.
    Returnează dict-ul JSON sau None dacă API-ul nu e disponibil.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic  # noqa: PLC0415

        bac_date = date(2026, 7, 1)
        days_to_bac = max(1, (bac_date - date.today()).days)
        prompt = _build_prompt(diagnostic, days_to_bac)

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # Extrage JSON dacă e înconjurat de markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if match:
            raw = match.group(1)

        return json.loads(raw)

    except ImportError:
        print("[ai_plan_service] anthropic SDK not installed. Install with: pip install anthropic")
        return None
    except json.JSONDecodeError as e:
        print(f"[ai_plan_service] JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"[ai_plan_service] Error calling Claude: {e}")
        return None


def generate_fallback_plan(diagnostic: dict) -> dict:
    """
    Plan minimal rule-based când AI nu e disponibil.
    """
    topics = diagnostic.get("weak_topics", [])
    score = diagnostic.get("score_pct", 0)
    days = max(1, (date(2026, 7, 1) - date.today()).days)
    weeks = min(6, max(2, days // 7))

    weak = [t for t in topics if t.get("score_pct", 100) < 60]
    weak.sort(key=lambda t: t.get("score_pct", 100))

    if score < 40:
        nivel = "incepator"
    elif score < 70:
        nivel = "mediu"
    else:
        nivel = "avansat"

    saptamani = []
    for i in range(weeks):
        focus_topics = weak[i * 2: i * 2 + 2] if weak else topics[:2]
        saptamani.append({
            "numar": i + 1,
            "titlu": f"Săptămâna {i + 1} — Consolidare",
            "focus_principal": focus_topics[0]["topic_label"] if focus_topics else "Recapitulare generală",
            "obiective": [
                f"Rezolvă 10 exerciții din {t['topic_label']}" for t in focus_topics[:2]
            ] or ["Rezolvă 10 exerciții de recapitulare"],
            "topicuri_recomandate": [t["topic_key"] for t in focus_topics],
            "timp_zilnic_minute": 45,
            "strategie": "Lucrează zilnic, preferabil la aceeași oră.",
        })

    return {
        "rezumat": f"Scor diagnostic: {score}%. {'Ai lacune semnificative care necesită atenție' if score < 50 else 'Bază solidă, dar există topicuri de consolidat'}.",
        "nivel_general": nivel,
        "saptamani": saptamani,
        "prioritati_urgente": [f"{t['topic_label']} ({t['score_pct']}%)" for t in weak[:3]],
        "sfaturi_practice": [
            "Rezolvă exerciții zilnic, chiar și 30 de minute.",
            "Verifică fiecare răspuns și înțelege greșeala.",
            "Concentrează-te pe Subiectul I (30 de puncte garantate).",
        ],
        "motivatie": "Fiecare exercițiu rezolvat te apropie de nota dorită. Continui!",
    }
