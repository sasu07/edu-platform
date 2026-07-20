# Deploy EtoX pe Hetzner — runbook

Ghid pas-cu-pas de la „am domeniu + cont Hetzner" la „site live pe https://e2xacademy.ro".

**Ce e deja pregătit în cod** (nu trebuie să faci nimic aici):
- Imagine backend slim (`edu_content_api/Dockerfile.prod`, ~569MB, fără OCR).
- `docker-compose.prod.yml` + `Caddyfile` (HTTPS automat).
- CORS citește din `ALLOWED_ORIGINS`; fișierele elevilor sunt servite autentificat.

**Ce faci tu:** pașii de mai jos (server, DNS, config, lansare).

---

## 0. Pregătire (local, recomandat)

- **Mută repo-ul afară din `~/Desktop`** (ex. `~/dev/etox`) ca să eviți conflictele iCloud (motivul pentru care a apărut `edu_content_api 2`).
- **Pune-l pe un GitHub privat** — deploy-ul devine `git clone` pe server.
- **Alimentează cheia Anthropic** (console.anthropic.com → Plans & Billing) ca să meargă indiciile AI / planul / grilele. Fără credit, merg pe fallback.

## 1. Serverul Hetzner

- Hetzner Cloud → Create Server:
  - Tip: **CX22** (2 vCPU, 4GB RAM, 40GB disc) — ~€4.5/lună. Suficient pentru imaginea slim.
  - Imagine: **Ubuntu 24.04**.
  - Adaugă cheia ta **SSH**.
- Firewall (Hetzner Cloud Firewall sau `ufw` pe server): permite **inbound 22, 80, 443**.

## 2. DNS

La registrarul domeniului `.ro` (sau Hetzner DNS), adaugă înregistrări **A** către IP-ul serverului:

| Tip | Nume | Valoare |
|-----|------|---------|
| A | `e2xacademy.ro` (`@`) | `<IP_SERVER>` |
| A | `www` | `<IP_SERVER>` |
| A | `api` | `<IP_SERVER>` |

Verifică propagarea: `dig +short e2xacademy.ro` (trebuie să întoarcă IP-ul). Poate dura de la minute la câteva ore.

## 3. Setup server

```bash
ssh root@<IP_SERVER>

# Docker
curl -fsSL https://get.docker.com | sh

# Node 20 (pentru build-ul frontend-ului)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs

# Codul
git clone <URL_REPO_PRIVAT> etox && cd etox
# (alternativ, fără GitHub: de pe laptop  rsync -av --exclude node_modules --exclude venv ./ root@<IP>:~/etox/)
```

## 4. Configurare

**a) `edu_content_api/.env`** (creează-l pe server — NU e în git):

```env
DATABASE_URL="postgresql://...neon...?sslmode=require&channel_binding=require"
JWT_SECRET_KEY="<secretul-lung-rotit>"
ANTHROPIC_API_KEY="<cheia-alimentată>"

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
SMTP_FROM=...

# ── Producție ──
APP_URL=https://e2xacademy.ro
ALLOWED_ORIGINS=https://e2xacademy.ro,https://www.e2xacademy.ro
```

**b) Build frontend** cu URL-ul API de producție (backend-ul e pe subdomeniul `api`):

```bash
cd frontend
npm ci
VITE_API_URL=https://api.e2xacademy.ro npm run build
cd ..
```

## 5. Lansare

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Caddy cere automat certificatul TLS (necesită DNS-ul deja propagat + porturile 80/443 deschise). Prima pornire poate dura ~30s pentru certificat.

**Verificare:**
```bash
curl https://api.e2xacademy.ro/health          # {"status":"ok"}
curl -o /dev/null -w "%{http_code}\n" https://api.e2xacademy.ro/exercises/   # 401 (auth cerută)
```
Deschide **https://e2xacademy.ro** în browser.

## 6. După lansare

- **Cont admin:** creează-l (script de seed / SQL direct în Neon). Fără el nu poți administra conținut.
- **Rate limiting pe login** — recomandat înainte/imediat după public (brute-force). *De adăugat — vezi „Următorii pași".*
- **Ascunde `/docs`** în producție.
- **Backup:** Neon are backup-uri automate. `uploaded_files/` stă pe discul serverului — fă snapshot Hetzner periodic, sau migrează pe object storage mai târziu.

## Operare curentă

```bash
docker compose -f docker-compose.prod.yml logs -f backend   # loguri
docker compose -f docker-compose.prod.yml up -d --build      # redeploy după modificări
docker compose -f docker-compose.prod.yml down               # oprire
```

**Update de conținut / cod:** `git pull` (sau rsync) → rebuild frontend dacă s-a schimbat → `up -d --build`.

## Ingestia de conținut (OCR)

Imaginea de producție e slim și **nu** are OCR. Adăugarea de exerciții din PDF-uri (pix2text) o faci **local**, cu imaginea completă (`Dockerfile` + `requirements.txt`), apoi datele ajung în aceeași bază Neon. Producția servește doar elevii.
