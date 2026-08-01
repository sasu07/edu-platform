# Protecție anti-scanare — Caddy 403 + fail2ban (VPS Hetzner)

Două straturi de apărare împotriva boților care scanează platforma:

1. **Caddy** respinge direct cu `403` orice cerere de tip WordPress/PHP/fișier secret
   (`wp-*`, `*.php`, `.env`, `.git` etc.) — nu ajung niciodată la backend.
2. **fail2ban** citește log-urile Caddy și **banează IP-ul la firewall** (chain
   `DOCKER-USER`, compatibil cu Docker) după 5 lovituri în 2 minute.

## Pași de instalare (o singură dată, pe VPS)

Rulează pe server, ca `root` (sau cu `sudo`).

### 1. Adu la zi codul și repornește Caddy cu noul Caddyfile + montarea de log

```bash
cd ~/edu-platform            # calea unde ai făcut git clone/pull
git pull
mkdir -p /var/log/caddy
# Recreează containerul Caddy ca să preia noul mount de log + Caddyfile
docker compose -f docker-compose.prod.yml up -d caddy
# Verifică că log-ul începe să se scrie (fă o cerere pe site și apoi):
tail -f /var/log/caddy/access.log
```

### 2. Instalează fail2ban

```bash
apt update && apt install -y fail2ban
```

### 3. Copiază configurațiile din repo

```bash
cd ~/edu-platform
cp deploy/fail2ban/filter.d/caddy-scan.conf   /etc/fail2ban/filter.d/
cp deploy/fail2ban/action.d/docker-user.conf  /etc/fail2ban/action.d/
cp deploy/fail2ban/jail.d/caddy.local         /etc/fail2ban/jail.d/
```

### 4. (Opțional) Adaugă IP-ul tău în allowlist

Ca să nu te banezi singur din greșeală, editează `/etc/fail2ban/jail.d/caddy.local`
și adaugă IP-ul tău la linia `ignoreip`.

### 5. Pornește fail2ban

```bash
systemctl enable fail2ban
systemctl restart fail2ban
```

## Verificare că merge

```bash
# Starea jail-ului + lista IP-urilor banate
fail2ban-client status caddy-scan

# Testează filtrul pe log-ul real (câte potriviri găsește)
fail2ban-client -d | grep caddy-scan
fail2ban-regex /var/log/caddy/access.log /etc/fail2ban/filter.d/caddy-scan.conf

# Vezi regulile de firewall aplicate (IP-urile DROP-uite)
iptables -L f2b-caddy-scan -n
```

## Comenzi utile

```bash
# Banează manual un IP
fail2ban-client set caddy-scan banip 45.148.10.247

# Scoate un IP din ban
fail2ban-client set caddy-scan unbanip 45.148.10.247
```

## Blocare manuală rapidă a unui IP (fără fail2ban)

Dacă vrei doar să tai un IP pe loc, fără să aștepți fail2ban:

```bash
iptables -I DOCKER-USER -s 45.148.10.247 -j DROP
apt install -y iptables-persistent && netfilter-persistent save   # persistă la reboot
```

> **De ce `DOCKER-USER` și nu UFW?** Docker își scrie propriile reguli de iptables
> și ocolește chain-ul `INPUT` (deci UFW). `DOCKER-USER` e evaluat înaintea
> regulilor de forwarding ale Docker, deci acolo trebuie inserate blocările.
