# Handoff tehnic — E2X ACADEMY / e2xacademy.ro

> Actualizat: 12 august 2026
>
> Release de cod pregătit: `7f5636b` — `Release: responsive UX, admin users and E2X landing`

## 0. Rezumat executiv

- Codul aplicației este integrat și împins în `origin/main`.
- Release-ul de cod care trebuie să ajungă în producție este `7f5636b`.
- Producția de pe VPS **nu a fost modificată de Codex**. Clientul face manual deploy-ul pe VPS.
- Conform handoff-ului anterior, versiunea aflată în producție înaintea acestui deploy este probabil `f091ac0` (`fix_landing_page`). Confirmă pe VPS cu `git rev-parse HEAD` înainte de lansare.
- Release-ul modifică simultan frontendul, backendul și schema bazei de date. Nu este suficient un deploy doar de frontend.
- Înainte de deploy sunt obligatorii un restore point/backup Neon și o copie pentru `edu_content_api/uploaded_files`.

## 1. Arhitectura

- **Frontend:** React + TypeScript + Vite + React Router + KaTeX + lucide-react.
- **Backend:** FastAPI + PostgreSQL + psycopg3 connection pool + JWT + bcrypt.
- **Bază producție:** Neon PostgreSQL extern; nu există container PostgreSQL în producție.
- **Producție:** VPS Hetzner, Docker Compose și Caddy cu HTTPS automat.
- **Frontend în producție:** fișierele din `frontend/dist`, montate read-only în containerul Caddy.
- **Backend în producție:** containerul `etox-backend`, construit din `edu_content_api/Dockerfile.prod`.
- **Fișiere persistente:** `edu_content_api/uploaded_files` pe discul VPS.
- **Email producție:** SMTP real; Mailpit există exclusiv în mediul local de test.

## 2. Starea Git

| Ramură | Rol | Stare la handoff |
|---|---|---|
| `main` | Release/producție | Conține release-ul `7f5636b`; `origin/main` a fost actualizat. |
| `feature/simplificare-ux` | Istoric ramură de lucru | Aliniată la același release `7f5636b`. |
| `feature/evaluare-nationala` | WIP separat | `57bd271`; nu este inclusă în release și trebuie rebazată ulterior pe `main`. |

Au rămas intenționat în afara release-ului:

- `.claude/settings.json` — configurație locală a editorului;
- orice secret sau fișier `.env`;
- buildul `frontend/dist`, care se generează pe VPS.

## 3. Ce livrează release-ul

### 3.1 Responsive și experiență mobilă

- shell-ul aplicației și navigația sunt adaptate pentru telefon;
- meniul mobil și zonele principale rămân accesibile pe ecrane înguste;
- admin, dashboarduri, exerciții, sesiuni, calendar, plan, cereri, notificări și formulare au stiluri responsive;
- navigația elevului este consolidată pe: Acasă, Exersează, Progres și Clasa mea;
- sesiunea de studiu acceptă durate de 10, 20 și 40 de minute.

### 3.2 Administrarea utilizatorilor

Adminul poate:

- crea utilizatori cu rolurile `student`, `teacher`, `school_teacher` și `parent`;
- retrimite o invitație;
- schimba rolul unui utilizator;
- activa/dezactiva un cont;
- iniția resetarea parolei;
- gestiona legături părinte–elev;
- vedea starea invitației și planurile active.

Protecții implementate:

- adminul nu poate crea sau acorda rolul `admin` prin aceste endpointuri;
- tokenurile de invitație/reset sunt one-time, expiră și sunt stocate doar hash-uit;
- schimbarea rolului sau parolei incrementează `auth_version` și invalidează JWT-urile vechi;
- schimbarea rolului curăță legături părinte–elev incompatibile;
- accesul premium este evaluat în funcție de rolul curent.

Durate token:

- invitație: 24 ore;
- resetare parolă: 30 minute.

### 3.3 Landing page și branding

- branding vizibil: `E2X ACADEMY` în header și footer, inclusiv pe mobil;
- au fost eliminate iconurile decorative tip „sparkles/AI”;
- planul Free apare primul pe toate dimensiunile;
- SEO folosește consecvent `E2X ACADEMY` în title, description, Open Graph și JSON-LD;
- au fost adăugate `robots.txt`, `sitemap.xml` și `site.webmanifest`;
- canonical: `https://e2xacademy.ro/`.

Fișierul logo se numește încă `logo_etox.png` pentru compatibilitate. Numele fișierului nu este afișat utilizatorului.

### 3.4 Alte corecții incluse

- pagină nouă `/reset-password`;
- parsing sigur pentru expresii numerice în frontend, fără evaluare arbitrară;
- îmbunătățiri responsive și de lizibilitate în numeroase componente;
- mediu local Mailpit pentru testarea invitațiilor și resetărilor.

## 4. Migrările de bază de date

Migrările rulează automat la startup și sunt urmărite în `schema_migrations`.

- `019_admin_user_management.sql`
  - adaugă `users.auth_version`;
  - creează `password_reset_tokens` și indexul aferent.
- `020_admin_invite_state.sql`
  - adaugă `users.invite_pending`;
  - marchează invitațiile existente în așteptare.
- `021_backfill_expired_admin_invites.sql`
  - păstrează retrimiterea invitațiilor nefolosite, inclusiv după expirarea linkului inițial.

Aceste migrări sunt aditive și nu au migrări `down`. Nu șterge tabelele/coloanele la un rollback de cod. Pentru o revenire exactă a datelor este necesar restore-ul Neon.

Backendul de producție pornește cu doi workeri. Pentru a evita rularea simultană a migrărilor, release-ul recomandă aplicarea lor o singură dată, controlat, înainte de recrearea backendului; comanda este în secțiunea de deploy.

## 5. Verificări executate local

Au trecut:

- build TypeScript/Vite de producție;
- smoke test frontend (`npm run smoke`);
- 16 teste backend;
- compilarea modulelor Python;
- aplicarea migrărilor `019–021` pe PostgreSQL local;
- testul end-to-end pentru:
  - creare utilizator;
  - email de invitație;
  - setare parolă;
  - schimbare rol;
  - invalidare JWT;
  - email de resetare;
  - token one-time;
  - curățare legături părinte–elev;
  - eliminare acces premium după schimbarea rolului.

`npm run lint` nu este încă green la nivelul întregului proiect: raportează 98 erori și 5 avertismente, în principal reguli stricte pentru cod existent (`no-explicit-any`, hook purity/set-state-in-effect și blocuri goale). Buildul și testele funcționale trec, dar curățarea lint trebuie tratată separat.

## 6. Mediul local de test

Folosește exclusiv numele de proiect și fișierul de test:

```bash
docker compose -p etox-test -f docker-compose.test.yml up -d --build
```

Servicii:

- frontend: `http://localhost:3001`;
- backend: `http://localhost:8001`;
- Mailpit: `http://localhost:8025`;
- PostgreSQL test: `localhost:5433`.

Conturi de test:

- admin: `admin@test.local` / `TestAdmin!2026`;
- elev: `student.mobile@test.local` / `StudentTest!2026`;
- profesor: `teacher.mobile@test.local` / `TeacherTest!2026`;
- părinte: `parent.mobile@test.local` / `ParentTest!2026`.

> Nu rula `docker compose up` fără fișierul explicit de test. Configurațiile locale vechi pot conține legături către baza Neon de producție.

## 7. Variabile necesare pe VPS

Fișierul efectiv este `edu_content_api/.env` de pe VPS și nu se comite.

```env
DATABASE_URL=<Neon production, SSL>
JWT_SECRET_KEY=<valoarea existentă; nu se rotește la acest release>
ENV=production
APP_URL=https://e2xacademy.ro
ALLOWED_ORIGINS=https://e2xacademy.ro,https://www.e2xacademy.ro
EXAM_DATE=<YYYY-MM-DD>

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<cont SMTP>
SMTP_PASS=<Gmail App Password sau parola SMTP>
SMTP_FROM=<adresa expeditorului>
SMTP_STARTTLS=true
```

Observații:

- dacă `EXAM_DATE` lipsește, countdown-ul este ascuns;
- dacă SMTP lipsește sau eșuează, invitațiile/resetările nu ajung prin email;
- contul și tokenul pot fi deja salvate înainte ca trimiterea emailului să eșueze; se folosește „Retrimite invitația”, nu se creează un duplicat;
- nu schimba `JWT_SECRET_KEY` decât dacă se dorește delogarea tuturor utilizatorilor.

## 8. Runbook de deploy pe VPS

### 8.1 Înainte de deploy

1. Confirmă SHA-ul live:

```bash
git rev-parse HEAD
```

2. Creează un restore point/branch de backup în Neon.
3. Salvează fișierele încărcate:

```bash
tar -czf ../uploaded_files-pre-release-2026-08-12.tar.gz edu_content_api/uploaded_files
```

4. Verifică starea repository-ului:

```bash
git status --short
```

Dacă există modificări pe VPS, nu folosi reset/force. Inspectează-le înainte de `git pull`.

### 8.2 Actualizare și migrări

```bash
git switch main
git pull --ff-only origin main

docker compose -f docker-compose.prod.yml build backend

docker compose -f docker-compose.prod.yml run --rm --no-deps backend \
  python -c "from bootstrap import run_pending_migrations; from database import close_db_pool; run_pending_migrations(); close_db_pool()"

docker compose -f docker-compose.prod.yml up -d --no-deps backend
```

Dacă migrarea eșuează, nu continua cu frontendul. Verifică logul și restaurează doar dacă este necesar.

### 8.3 Frontend și Caddy

```bash
cd frontend
npm ci
VITE_API_URL=https://api.e2xacademy.ro npm run build
cd ..

docker compose -f docker-compose.prod.yml restart caddy
```

### 8.4 Verificări după deploy

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=200 backend
curl -fsS https://api.e2xacademy.ro/health
curl -fsS https://api.e2xacademy.ro/config/public
curl -I https://e2xacademy.ro
```

Smoke test manual recomandat:

1. login cu adminul existent;
2. deschide Administrare → Utilizatori;
3. creează un cont cu o adresă controlată;
4. confirmă primirea invitației;
5. setează parola și autentifică noul cont;
6. inițiază o resetare și confirmă invalidarea sesiunii vechi;
7. verifică landing page-ul pe telefon și planul Free primul.

Monitorizează logurile pentru evenimente de forma `*_email_failed`.

## 9. Rollback

Commitul anterior cunoscut ca stabil este `f091ac0`.

Rollback de cod:

```bash
git switch --detach f091ac0

docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d --no-deps backend

cd frontend
npm ci
VITE_API_URL=https://api.e2xacademy.ro npm run build
cd ..

docker compose -f docker-compose.prod.yml restart caddy
```

Nu rula `docker compose down -v`; volumele Caddy conțin certificatele/configurația persistentă.

Schema nouă poate rămâne după rollbackul codului deoarece modificările sunt aditive. Pentru revenirea exactă a datelor, restaurează restore point-ul Neon și copia `uploaded_files` în coordonare cu revenirea backendului și frontendului.

## 10. Riscuri și datorii tehnice cunoscute

- `/health` nu verifică efectiv conexiunea la DB; verifică separat loginul și un endpoint care citește baza.
- runnerul de migrări nu are advisory lock și urmărește numele fișierului, nu checksum-ul; de aceea se recomandă migrarea one-off.
- frontendul nu este publicat atomic; buildul scrie direct în `frontend/dist`.
- nu există retry/outbox pentru email; retrimiterea se face din UI.
- nu există rollback automat, imagini Docker versionate sau procedură de restore testată automat.
- rezultatele Google nu se actualizează imediat; după deploy, trimite sitemap-ul în Google Search Console și cere reindexarea paginii principale.
- `www.e2xacademy.ro` și domeniul fără `www` sunt servite ambele de Caddy; canonicalul indică domeniul fără `www`, dar un redirect 301 dedicat pentru `www` ar fi o îmbunătățire SEO ulterioară.

## 11. Lucru rămas / backlog

### Sesiune de studiu

- soluția completă să fie disponibilă la cerere numai după folosirea indiciilor;
- după a doua greșeală, exercițiul să intre automat în „De revizuit”;
- workspace unificat: enunț, verificare, indicii, explicație și solicitare profesor;
- autosave pentru notițe/răspuns și rezumat de sesiune simplificat.

### Progres și profesor

- consolidarea taburilor De revizuit, Istoric și Rezumat în zona Progres;
- Inbox profesor și prioritizarea cererilor.

### Ramura Evaluare Națională

- `feature/evaluare-nationala` este WIP separat;
- înainte de reluare trebuie rebazată/îmbinată controlat cu noul `main` și retestată complet.

## 12. Fișiere-cheie

- `docker-compose.test.yml` — mediul local izolat;
- `docker-compose.prod.yml` — serviciile de producție;
- `Caddyfile` — domenii, TLS, CSP și reverse proxy;
- `DEPLOY.md` — ghidul general de deploy;
- `edu_content_api/bootstrap.py` — runnerul de migrări;
- `edu_content_api/routers/auth_router.py` — administrare utilizatori și resetări;
- `edu_content_api/email_service.py` — SMTP și template-uri email;
- `edu_content_api/migrations/019_admin_user_management.sql`;
- `edu_content_api/migrations/020_admin_invite_state.sql`;
- `edu_content_api/migrations/021_backfill_expired_admin_invites.sql`;
- `frontend/src/components/AdminPanel.tsx`;
- `frontend/src/components/ResetPassword.tsx`;
- `frontend/src/components/LandingPage.tsx`;
- `frontend/index.html` — metadata SEO.
