# EtoX Platform

Platformă web pentru pregătirea la examenul de bacalaureat (matematică). Permite studenților să exerseze exerciții din subiecte reale de BAC, să ceară ajutor de la profesori și să urmărească progresul. Profesorii pot genera variante și fișe de lucru personalizate.

## Ce face

- **Exerciții BAC** cu randare LaTeX, filtrare pe subiect/topic/dificultate și soluții afișabile
- **Cereri de ajutor** în 3 forme: rezolvare scrisă, clip video sau sesiune Zoom live (necesită abonament)
- **Generare variante** după structura oficială BAC (S1 × 6 exerciții, S2 × 2 probleme, S3 × 2 probleme)
- **Export PDF** pentru subiecte, rezolvări și bareme
- **Abonamente** pe niveluri: Premium Help (cereri ajutor), Premium PDF (export), Premium Full
- **Dashboard profesor** cu statistici cereri rezolvate

## Stack

Backend: FastAPI + PostgreSQL (Neon) + psycopg3
Frontend: React 18 + TypeScript + Vite + KaTeX
Auth: JWT (python-jose) + bcrypt
Deploy: Docker Compose (nginx pentru frontend, uvicorn pentru API)

## Setup local

**Cerințe:** Docker + Docker Compose

1. Clonează repo-ul
2. Copiază `.env.example` în `.env` și completează variabilele
3. Rulează migrările SQL din `edu_content_api/migrations/` în ordinea numerică
4. Pornește containerele:

```bash
docker compose up -d --build
```

Frontend disponibil la `http://localhost:3000`, API la `http://localhost:8000`.

**Creare cont admin inițial** (după ce backend-ul pornește):

```python
# rulează o dată din interiorul containerului sau local cu venv activ
import bcrypt, psycopg, os

conn = psycopg.connect(os.getenv("DATABASE_URL"))
pw = bcrypt.hashpw(b"parola_ta", bcrypt.gensalt()).decode()
conn.execute(
    "INSERT INTO users (email, full_name, role, password_hash, is_active) VALUES (%s,%s,'admin',%s,true)",
    ("admin@domeniu.ro", "Administrator", pw)
)
conn.commit()
```

## Import exerciții

Exercițiile se importă prin `POST /import-hierarchical/` cu un JSON structurat. Format și exemple în `docs/workflow.md`.

## Variabile de mediu

Vezi `.env.example`. Obligatorii: `DATABASE_URL` și `JWT_SECRET_KEY`.

## Structura proiect

```
edu_content_api/   ← FastAPI backend
frontend/          ← React frontend
docs/              ← workflow, diagrame
docker-compose.yml
```

Diagrama completă a fluxului aplicației: [`docs/workflow.md`](docs/workflow.md)
