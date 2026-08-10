# EtoX Academy — Evaluare tehnică & plan de atac pentru brief-ul de simplificare

**Referință:** `platform-usability-implementation-brief.md`
**Data:** 10 august 2026
**Scop:** fezabilitate per epic, conflicte cu ramura EN, ordine de merge, plan pe sprinturi.

---

## 0. Verdict pe scurt

Brief-ul e **corect direcțional și realist** — consolidare, nu funcționalități noi. API-urile pe care se sprijină **există deja** (verificat). Cel mai mare risc **nu e tehnic, ci de coordonare**: brief-ul rescrie exact fișierele modificate de ramura `feature/evaluare-nationala`. Fără o ordine de merge clară, ies conflicte mari.

Grounding verificat în cod (`main`):
- Data BAC hardcodată confirmată: `frontend/src/App.tsx:75` → `new Date('2026-07-01')`.
- Nav elev are acum **~8 destinații** (`exercises`, `subiecte`, `my-requests`, `learning-path`, `study-session`, `study-plan`, `league`, `variants`) → brief vrea **4**.
- API-uri din §13.2: `study-sessions/start|complete|abandon`, `student/study-stats`, `study-plan`, `student/review-items`, `teacher/submissions/stats` — **toate există**. Doar `GET /student/today` (agregatul opțional) lipsește (și brief-ul îl marchează opțional).

---

## 1. Fezabilitate per epic

| Epic | Efort | Ce se reutilizează | Muncă nouă | Risc |
|---|---|---|---|---|
| **1. Dashboard pe-o-acțiune** | **M** | `AppHub` are deja logica `activeSession/todayPlan/recommendation`; datele se încarcă deja | Reordonare vizuală, 1 CTA dominant, scoatere dată hardcodată, stări loading/empty/error | Mic. Cel mai bun raport valoare/efort |
| **2. Flux unificat de exersare** | **L (cel mai mare)** | `StudySession.tsx`, `StudentExercises.tsx`, autosave localStorage există deja (`getWorkspaceStorageKey`), verificare numerică backend există | Unificarea a două ecrane mari într-unul; workspace + răspuns + indicii + escaladare pe un singur ecran; autosave server-side (opțional) | **Ridicat** — fișiere mari, multe stări, mobil cu tastatură virtuală |
| **3. Progres consolidat** | **M** | `StudyPlan`, `StudyPrepCalendar`, `LearningPath`, istoricul din `StudySession`, `ReviewTab` — toate există | O pagină-container cu tab-uri care le găzduiește; rutare `/app/progress` | Mic-mediu (mai mult reorganizare) |
| **4. Inbox profesor unificat** | **M-L** | `TeacherDashboard` are deja submissions + help live; sistemele submissions & help_requests le cunosc bine | Unificare submissions + help_requests + live într-un singur inbox cu filtre/prioritizare; contoare reactive | Mediu — două surse de date de reconciliat |
| **5. Dashboard părinte** | **S-M** | `ParentDashboard` există; datele de calendar/review există | Reordonare, tendințe (nu doar totaluri), copywriting explicativ | Mic |
| **Onboarding (3 întrebări + tur)** | **M** | Registration cere deja rol/program; diagnostic există | 3-întrebări la prima logare + tur contextual 3 pași, dismissabil | Mic-mediu |
| **`GET /student/today` (agregat)** | **S** | Toate sub-datele există | Un endpoint care le compune | Mic — recomandat pentru Epic 1 dacă apar prea multe cereri |

---

## 2. ⚠️ Conflictul cu ramura `feature/evaluare-nationala` (punctul critic)

Brief-ul și EN modifică **aceleași fișiere-cheie**:

| Fișier | Ce face EN acolo | Ce face brief-ul acolo | Conflict |
|---|---|---|---|
| `App.tsx` | ProgramSwitcher, LevelTestGate, link „Evaluare Națională", rutare Manager | **rescrie tot nav-ul** pe 4 destinații + logica dashboard | **MARE** |
| `App.css` | strat responsive, shell, hub | dashboard + nav + stări comune | **MARE** |
| `StudySession.tsx` | doar CSS mobil (minor) | **rescriere** flux exersare | Mediu |
| `StudentExercises.tsx` | figuri, ProgressiveHints, barem | **rescriere** în flux unificat | **MARE** |
| `TeacherDashboard.tsx` | secțiunea ManagerEvaluations + focus notificare | **rescriere** în inbox unificat | **MARE** |
| `NotificationBell.tsx` | rute noi (`new_submission`, `evaluation_report`) | — | Mic |

**Concluzie:** una dintre ramuri trebuie să aterizeze prima, iar cealaltă se rebazează peste. Nu se pot dezvolta „în paralel" fără durere la merge.

---

## 3. Ordine de merge recomandată

```
1. LANDING (main, acum)      → deploy imediat (doar frontend, independent, zero backend)
2. Decizie EN vs. Simplificare (ambele ating App.tsx/nav):
   • Dacă EN merge curând în prod  → merge EN în main ÎNTÂI, apoi simplificarea peste (absoarbe
     natural destinația „Evaluare Națională" în noul „Exersează"/nav).
   • Dacă EN mai stă în dev (așteaptă conținut) → simplificarea pe ramură din main ACUM,
     merge în main, iar ramura EN se rebazează peste noua structură (efort pe partea EN).
```

Recomandarea mea concretă: **landing → simplificare (P0, rapidă) → EN se rebazează peste.**
Motiv: usability-ul e P0 și self-contained; EN oricum are nevoie de conținut înainte de prod. Costul: cineva trebuie să reintegreze nav-ul/rutele EN în structura nouă (o fac eu, controlat, când vine rândul EN).

Regula de aur: **NU** dezvolta simplificarea și EN simultan pe `main`.

---

## 4. Câștiguri rapide (low-risk, se pot face oricând)

1. **Data BAC din config** (nu hardcodată). Recomandat: un mic setting backend (`GET /config/public` → `{ exam_date }`) sau, minimal, `VITE_EXAM_DATE`. Elimină `App.tsx:75`. — **S**
2. **Componente comune** `LoadingState / EmptyState / ErrorState / PrimaryCTA** (§10) — fundație pentru toate epicele. — **S-M**
3. **Vocabular consecvent** (§2.4) — un fișier de constante cu etichetele standard, aplicat treptat. — **S**
4. **Instrumentare analytics** (§12) — un wrapper subțire `track(event, props)` + evenimentele minime. — **S**

Astea 4 = practic **Sprint A** (fundația), fără să atingă fluxurile mari.

---

## 5. Plan de atac pe sprinturi (aliniat cu §14)

| Sprint | Conținut | Efort | Ramură |
|---|---|---|---|
| **A — Fundația** | nav pe 4 destinații, dashboard pe-o-acțiune, dată BAC din config, componente comune loading/empty/error/CTA, analytics baseline | M | `feature/simplificare-ux` din main |
| **B — Sesiunea unificată** | durate 10/20/40, workspace unic, răspuns+verificare, ajutor gradual, autosave+reluare | **L** | idem |
| **C — Progres & continuitate** | rută `/app/progress` cu tab-uri (calendar/istoric/review/traseu), CTA spre următoarea sesiune, aliniere dashboard părinte | M | idem |
| **D — Profesor** | inbox unificat, prioritizare/filtre, contoare reactive, șabloane, preluare concurentă | M-L | idem |

Fiecare sprint = lansabil independent (cerință §14). Sprint A + B sunt P0; C + D sunt P1.

---

## 6. Riscuri tehnice specifice (peste ce zice brief-ul)

- **Epic 2 e „the big one".** `StudySession` + `StudentExercises` sunt fișiere mari cu stări multe. Recomand să le tratăm ca refactor incremental (întâi containerul cu zone, apoi mut logica), nu rescriere de la zero — altfel regresii.
- **Autosave server-side vs. local.** Există deja draft în localStorage. Trecerea pe server (decizie §18.3) adaugă un endpoint + sincronizare. Pentru prima iterație, local + „răspuns final" pe server e suficient.
- **Verificarea răspunsului la BAC.** EN are `/en/check-answer`; pentru fluxul general BAC există `answer_numeric_value`. Trebuie un endpoint de verificare unificat pentru non-EN, sau reutilizat cel numeric — de clarificat.
- **Inbox profesor:** submissions și help_requests au modele diferite (contoare, stări). Unificarea vizuală e ok, dar „preluare concurentă" (§7.5) cere un lock/verificare pe backend (submissions au deja `assigned_teacher_id`; help_requests au `/assign`).
- **`prefers-reduced-motion` + sticky pe mobil cu tastatură** (§11) — deja avem practici bune din landing; de dus în app.

---

## 7. Decizii tehnice de confirmat (completează §18)

1. **Sursa datei BAC** — recomand endpoint backend `GET /config/public`. (blochează Sprint A)
2. **Ordinea EN vs. simplificare** la merge (vezi §3) — decizie de prioritate produs.
3. **Verificarea răspunsului non-EN** — endpoint nou unificat sau reutilizare numerică?
4. **Autosave** — server sau local în prima iterație? (recomand local + răspuns final pe server)
5. **Rutele consolidate** — lansare graduală (feature flag) sau pentru toți? (recomand flag, ca să putem reveni controlat)
6. **Analytics** — ce instrument (Plausible/PostHog/self-hosted)? Impact CSP: dacă e extern, trebuie relaxat CSP-ul (ca la fonturi) sau self-hosted.

---

## 8. Recomandarea finală

- **Acum:** finalizăm + urcăm **landing-ul** (independent, gata).
- **Apoi:** pornesc **Sprint A** pe `feature/simplificare-ux` (cel mai mare ROI, low-risk): nav 4 destinații + dashboard pe-o-acțiune + dată BAC din config + componente comune.
- **Coordonare EN:** stabilim că EN se rebazează peste `main` după ce simplificarea aterizează (sau invers, dacă EN merge în prod mai repede).

Sprint A îl pot începe imediat ce zici, fără să ating landing-ul de pe `main`.
