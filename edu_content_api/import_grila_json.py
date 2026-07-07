"""
Importă exerciții grilă BAC din JSON cu format standard:
{
  "source": { "external_id": "...", "name": "...", ... },
  "exercises": [
    {
      "external_id": "GRILA-S1-01",
      "subiect": 1,
      "options": [
        {"label": "a", "value_latex": "$x=1$", "is_correct": false},
        {"label": "b", "value_latex": "$x=2$", "is_correct": true},
        ...
      ],
      "answer_latex": "$x=2$",
      "solution_latex": "...",
      "scoring_guide_latex": "...",
      "difficulty": 3,
      "points": 5,
      "status": "READY",
      "tags": [{"namespace": "topic", "key": "analiza", "label": "Analiză matematică"}]
    }
  ]
}

Rulare: python import_grila_json.py <fisier.json>
Dacă nu e specificat fișier, caută grila_100.json în același director.
"""
import json
import os
import sys
import uuid
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
DB = os.getenv("DATABASE_URL")


def convert_options(options: list) -> tuple[list[str], int]:
    """
    Convertește options din formatul JSON la (mcq_options, correct_index).
    options: [{"label": "a", "value_latex": "...", "is_correct": bool}]
    """
    labels = [opt["value_latex"] for opt in options]
    correct_idx = next(
        (i for i, opt in enumerate(options) if opt.get("is_correct")),
        0,
    )
    return labels, correct_idx


def main(json_path: str):
    if not os.path.exists(json_path):
        print(f"Eroare: fișierul '{json_path}' nu există.")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    source_info = data.get("source", {})
    exercises_raw = data.get("exercises", [])

    if not exercises_raw:
        print("Niciun exercițiu găsit în JSON.")
        sys.exit(1)

    source_prefix = source_info.get("external_id", "GRILA")
    print(f"Sursă: {source_info.get('name', source_prefix)}")
    print(f"Exerciții găsite: {len(exercises_raw)}")

    with psycopg.connect(DB) as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # Șterge exercițiile vechi cu același prefix
            prefixes = set()
            for ex in exercises_raw:
                eid = ex.get("external_id", "")
                # Ex: "GRILA-S1-01" → prefix "GRILA"
                prefix = eid.split("-")[0] if "-" in eid else eid[:5]
                prefixes.add(prefix)

            deleted_total = 0
            for prefix in prefixes:
                cur.execute(
                    "DELETE FROM exercises WHERE metadata::jsonb->>'external_id' LIKE %s",
                    (f"{prefix}-%",),
                )
                deleted_total += cur.rowcount

            if deleted_total:
                print(f"Șterse {deleted_total} exerciții vechi cu prefix {prefixes}")

            # Admin user
            cur.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
            admin_row = cur.fetchone()
            admin_id = str(admin_row["id"]) if admin_row else None

            tag_cache: dict[str, str] = {}

            def get_or_create_tag(namespace: str, key: str, label: str) -> str:
                ck = f"{namespace}:{key}"
                if ck in tag_cache:
                    return tag_cache[ck]
                cur.execute(
                    "SELECT id FROM tags WHERE namespace=%s AND key=%s",
                    (namespace, key),
                )
                row = cur.fetchone()
                if row:
                    tid = str(row["id"])
                else:
                    cur.execute(
                        "INSERT INTO tags (namespace, key, label) VALUES (%s,%s,%s) RETURNING id",
                        (namespace, key, label),
                    )
                    tid = str(cur.fetchone()["id"])
                tag_cache[ck] = tid
                return tid

            def insert_tag(ex_id: str, tid: str):
                cur.execute(
                    """
                    INSERT INTO exercise_tags
                      (exercise_id, tag_id, weight, created_by, created_by_user_id)
                    VALUES (%s,%s,1.0,'import',%s)
                    ON CONFLICT DO NOTHING
                    """,
                    (ex_id, tid, admin_id),
                )

            inserted = 0
            skipped = 0
            by_subiect: dict[int, int] = {}

            for ex in exercises_raw:
                external_id = ex.get("external_id", "")
                subiect = ex.get("subiect", 1)
                exercise_num = ex.get("exercise_num", 1)
                options_raw = ex.get("options", [])

                if not options_raw:
                    print(f"  SKIP {external_id}: fără opțiuni")
                    skipped += 1
                    continue

                mcq_options, correct_idx = convert_options(options_raw)

                ex_id = str(uuid.uuid4())
                metadata = {
                    "external_id": external_id,
                    "subiect": subiect,
                    "exercise_num": exercise_num,
                    "path": f"S{subiect}/{exercise_num}",
                    "is_container": False,
                    "diagnostic_grila": True,
                    "mcq_options": mcq_options,
                    "correct_option_index": correct_idx,
                    "source": source_info.get("external_id", ""),
                }

                cur.execute(
                    """
                    INSERT INTO exercises (
                        id, exam_type, profile, item_type,
                        statement_latex, answer_latex,
                        solution_latex, scoring_guide_latex,
                        difficulty, points, status, metadata,
                        created_at, updated_at
                    ) VALUES (
                        %s,
                        %s, %s, 'exercitiu',
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        NOW(), NOW()
                    )
                    """,
                    (
                        ex_id,
                        ex.get("exam_type", "bacalaureat"),
                        ex.get("profile", "mate-info"),
                        ex.get("statement_latex", ""),
                        ex.get("answer_latex"),
                        ex.get("solution_latex"),
                        ex.get("scoring_guide_latex"),
                        ex.get("difficulty", 3),
                        ex.get("points", 5),
                        ex.get("status", "READY"),
                        json.dumps(metadata),
                    ),
                )

                # Tag: subiect
                stag = get_or_create_tag(
                    "subiect", str(subiect), f"Subiectul {subiect}"
                )
                insert_tag(ex_id, stag)

                # Tag: topic/subtopic din JSON
                for tag in ex.get("tags", []):
                    tid = get_or_create_tag(
                        tag["namespace"], tag["key"], tag["label"]
                    )
                    insert_tag(ex_id, tid)

                # Tag sursă
                src_key = source_info.get("external_id", "grila").lower().replace("_", "-")
                insert_tag(ex_id, get_or_create_tag("source", src_key, source_info.get("name", "Grilă BAC")))
                # Tag diagnostic_grila (pentru filtrare în diagnostic test)
                insert_tag(ex_id, get_or_create_tag("source", "diagnostic-grila", "Diagnostic Grilă"))

                by_subiect[subiect] = by_subiect.get(subiect, 0) + 1
                inserted += 1

            conn.commit()

    print(f"\n✓ Importate cu succes: {inserted} exerciții")
    for s in sorted(by_subiect):
        print(f"  S{s}: {by_subiect[s]} exerciții")
    if skipped:
        print(f"  Sărite (fără opțiuni): {skipped}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = os.path.join(os.path.dirname(__file__), "grila_100.json")
    main(json_file)
