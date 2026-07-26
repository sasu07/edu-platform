# EtoX Platform

Platformă web pentru pregătirea la examenul de bacalaureat (matematică). Permite elevilor să exerseze exerciții din subiecte reale de BAC, să ceară ajutor de la profesori și să urmărească progresul. Profesorii pot genera variante și fișe de lucru personalizate.

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
3. Pornește containerele (migrările SQL rulează automat la pornirea backend-ului):

```bash
docker compose up -d --build
```

Acest fișier `docker-compose.yml` este pentru rulare locală. Frontend-ul va fi disponibil la `http://localhost:3000`, iar API-ul la `http://localhost:8000`.

## Deploy producție

Pentru producție folosește separat:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Documentația completă de deploy este în [`DEPLOY.md`](/Users/admin/Desktop/run-apps/edu_content_app/edu-platform/DEPLOY.md).

Pe scurt:
- backend-ul rulează din `edu_content_api/Dockerfile.prod`
- frontend-ul trebuie build-uit cu `VITE_API_URL=https://api.domeniul-tau.ro`
- CORS se configurează din `ALLOWED_ORIGINS`
- `ENV=production` ascunde documentația API

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

Vezi `edu_content_api/.env.example`. Minimul necesar:
- `DATABASE_URL`
- `JWT_SECRET_KEY`

Pentru producție setează explicit și:
- `ENV=production`
- `APP_URL=https://domeniul-tau.ro`
- `ALLOWED_ORIGINS=https://domeniul-tau.ro,https://www.domeniul-tau.ro`

## Structura proiect

```text
edu_content_api/   <- FastAPI backend
frontend/          <- React frontend
docs/              <- workflow, diagrame
docker-compose.yml <- rulare locală
docker-compose.prod.yml <- rulare producție
```

Diagrama completă a fluxului aplicației: [`docs/workflow.md`](/Users/admin/Desktop/run-apps/edu_content_app/edu-platform/docs/workflow.md)
