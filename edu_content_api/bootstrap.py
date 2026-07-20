import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import close_db_pool

UPLOAD_DIR = "uploaded_files"

_DEFAULT_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]


def _get_allowed_origins() -> list:
    """Originile permise (CORS). În producție se setează prin variabila de mediu
    ALLOWED_ORIGINS (listă separată prin virgulă), ex.:
        ALLOWED_ORIGINS=https://e2xacademy.ro,https://www.e2xacademy.ro
    Fără ea, se folosesc originile de dezvoltare (localhost)."""
    env = os.getenv("ALLOWED_ORIGINS", "").strip()
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return _DEFAULT_ORIGINS


ORIGINS = _get_allowed_origins()


def configure_app(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # NB: fișierele din UPLOAD_DIR NU se mai servesc static/public.
    # Sunt servite prin endpoint-ul autentificat GET /uploads/{path} din main.py
    # (verificare de proprietar). Vezi serve_uploaded_file.

    app.add_event_handler("startup", run_pending_migrations)
    app.add_event_handler("startup", backfill_numeric_answers)
    app.add_event_handler("shutdown", close_db_pool)


def run_pending_migrations() -> None:
    import glob as glob_mod

    from database import conn_pool

    if conn_pool is None:
        return

    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    sql_files = sorted(glob_mod.glob(os.path.join(migrations_dir, "*.sql")))

    with conn_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        for sql_file in sql_files:
            filename = os.path.basename(sql_file)
            if filename in applied:
                continue
            with open(sql_file, "r") as file_obj:
                sql = file_obj.read()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                        (filename,),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                # Dacă alt worker a rulat deja migrația (race condition), ignorăm
                if "duplicate key" in str(exc).lower() or "already exists" in str(exc).lower():
                    print(f"Migration {filename} skipped: already applied by another worker")
                    continue
                print(f"Migration {filename} failed: {exc}")
                raise RuntimeError(f"Migration {filename} failed") from exc


def backfill_numeric_answers() -> None:
    from answer_numeric import evaluate_numeric_answer
    from database import conn_pool

    if conn_pool is None:
        return

    with conn_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, answer_latex
                FROM exercises
                WHERE answer_latex IS NOT NULL
                  AND (answer_numeric_value IS NULL OR answer_numeric_expression IS NULL)
                """
            )
            rows = cur.fetchall()

        if not rows:
            conn.commit()
            return

        updated = 0
        with conn.cursor() as cur:
            for exercise_id, answer_latex in rows:
                numeric_value, numeric_expression = evaluate_numeric_answer(answer_latex)
                if numeric_value is None or not numeric_expression:
                    continue
                cur.execute(
                    """
                    UPDATE exercises
                    SET answer_numeric_value = %s,
                        answer_numeric_expression = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (numeric_value, numeric_expression, exercise_id),
                )
                updated += 1
        conn.commit()
        if updated:
            print(f"Backfilled numeric answers for {updated} exercises")
