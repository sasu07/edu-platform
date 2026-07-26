# Mediu de test

Un mediu **complet izolat de producție**, pentru a verifica funcționalități noi înainte
de a le pune live. Are propria bază de date Postgres (locală, efemeră) — **niciun risc
pentru datele reale din Neon**.

## Cum funcționează

- `docker-compose.test.yml` pornește un **Postgres local** (container) + **backend-ul pe portul 8001**.
- Schema se creează **automat** la pornire (migrările rulează singure).
- Frontend-ul îl rulezi cu `npm run dev`, țintind backend-ul de test.
- Nimic nu atinge producția: DB diferit, port diferit, secret JWT de test.

## 1. Pornește backend-ul de test

```bash
docker compose -f docker-compose.test.yml up -d --build
```

- Backend: **http://localhost:8001** (documentația API la `/docs`, fiindcă `ENV=development`).
- Verifică: `curl http://localhost:8001/health` → `{"status":"ok"}`.
- Postgres-ul de test e accesibil pe host la `localhost:5433` (user/parolă/db: `etox` / `etox_test` / `etox_test`).

## 2. Pune date de test (baza pornește goală)

**a) Cont admin de test** (rulează o dată):
```bash
docker compose -f docker-compose.test.yml exec backend python -c "
import bcrypt, psycopg, os
conn = psycopg.connect(os.getenv('DATABASE_URL'))
pw = bcrypt.hashpw(b'admin1234', bcrypt.gensalt()).decode()
conn.execute(\"INSERT INTO users (email, full_name, role, password_hash, is_active) VALUES (%s,%s,'admin',%s,true) ON CONFLICT (email) DO NOTHING\", ('admin@test.local','Admin Test', pw))
conn.commit(); print('admin creat: admin@test.local / admin1234')
"
```

**b) Exerciții de test** — importă un JSON prin `POST /import-hierarchical/` (ai `edu_content_api/test_hierarchical.json` ca exemplu). Sau creezi din UI ca admin.

## 3. Rulează frontend-ul pe mediul de test

```bash
cd frontend
VITE_API_URL=http://localhost:8001 npm run dev
```
→ Frontend cu hot-reload la **http://localhost:5173**, care vorbește cu backend-ul de test (8001).
(Prefixul `VITE_API_URL` e necesar — implicit `npm run dev` țintește 8000.)

## 4. Resetează baza de test (start curat)

```bash
docker compose -f docker-compose.test.yml down -v
```
`-v` șterge volumul → data se pierde, schema se recreează la următoarea pornire. Ideal ca să testezi migrări noi de la zero.

## Fluxul recomandat

```
Dezvolți feature  →  testezi pe mediul de test (DB local, 8001)  →  merge?  →  git push + deploy prod
```
Așa nu pui niciodată ceva netestat direct pe e2xacademy.ro.

## Alternativă: test pe o copie a datelor reale (Neon branching)

Când vrei să testezi pe date **realiste** (nu goale), Neon îți permite să faci un **branch** al bazei de producție (copie instant, izolată):

1. Neon Console → proiectul tău → **Branches** → **Create branch** (ex. `test`).
2. Copiază connection string-ul branch-ului.
3. Pornește backend-ul de test cu acel `DATABASE_URL` (în loc de Postgres-ul local) — ex. temporar:
   ```bash
   DATABASE_URL="<connection-string-branch-neon>" docker compose -f docker-compose.test.yml up backend
   ```
   (sau pui valoarea în `environment` pentru `backend` în `docker-compose.test.yml`).

Branch-ul e izolat: modificările de pe el **nu** ating producția. Îl ștergi când termini.
