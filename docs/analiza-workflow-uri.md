# Analiză workflow-uri platformă + plan de implementare

> Data: 2026-08-22. Bază: cod real (nu memorie), ramura `feature/simplificare-ux`.

## 0. Rezumat executiv

Am cartografiat toate căile prin care un elev interacționează cu un profesor pe un exercițiu. Există **trei sisteme paralele**, cu **trei intrări diferite** care arată aproape identic, și **două scurgeri reale** unde munca elevului se pierde. Instinctul tău („care e diferența dintre «m-am blocat» și «vreau corectare»?") atinge exact miezul problemei: sunt concepte suprapuse, prezentate ca butoane distincte cu același icon.

**Cele mai grave 3 constatări:**
1. 🔴 **Cererile scrise/video sunt gaură neagră** — profesorul nu are UI să le răspundă. Iar Sprint B.4 (pe care l-am făcut eu) trimite implicit „Rezolvare scrisă". Le trimit în gol. *(Asta e din vina mea, o asum.)*
2. 🟠 **Trei intrări confuze pe același exercițiu**: „M-am blocat", „Vreau corectare" (ambele cu icon Flag) + „Cere ajutor profesorului" (din sesiune). Fac lucruri diferite pe 3 tabele diferite.
3. 🟠 **„Activitatea mea" e îngropată** — ecranul unde elevul vede corecțiile și răspunsurile profesorului (`/app/my-requests`) NU e în meniul principal (Acasă/Exersează/Progres/Clasa mea) și nu are card în hub. Ajungi la el doar din notificări.

---

## 1. Harta workflow-urilor actuale

### 1.1 Cele trei sisteme paralele (backend)

| Sistem | Tabel | Ce e | Declanșat din |
|---|---|---|---|
| **Help requests** | `help_requests` (+`help_responses`) | Cerere de ajutor: `WRITTEN` / `VIDEO` / `LIVE` | „M-am blocat → Cer ajutor live", „Cere ajutor profesorului" (Sprint B.4) |
| **Submissions** | `exercise_submissions` | Elevul urcă poza soluției → profesorul corectează (corect/incorect + notă + fișier) | „Vreau corectare" (EvalModal) |
| **Review items** | `exercise_review_items` | Listă personală „de revizuit": `blocked`/`wrong`/`failed`/`partial`/`marked_unresolved` | „M-am blocat → Adaugă la revizuit", auto după a 2-a greșeală (Sprint B.2), marcare manuală |

### 1.2 Intrările elevului (pe un exercicțiu, în lista Exerciții)

- **Buton „M-am blocat"** (icon Flag) → modal cu 2 opțiuni:
  - „Adaugă la revizuit" → `review_items` (reason=blocked)
  - „📹 Cer ajutor live" → `help_requests` (LIVE), doar premium
- **Buton „Vreau corectare"** (icon Flag, identic vizual) → EvalModal → urcă poză → `submissions`
- **(În sesiune)** „Cere ajutor profesorului" (Sprint B.4) → `help_requests` (WRITTEN/VIDEO/LIVE + context)

Trei intrări, două cu același icon, trei destinații interne.

### 1.3 Vederile elevului (unde își regăsește lucrurile)

- **Progres → De revizuit** (Sprint C): `review_items`
- **„Activitatea mea"** (`/app/my-requests`, îngropat):
  - tab „Cereri ajutor" → `help_requests`
  - tab „Soluții trimise" → `submissions`

Deci pentru trei sisteme, elevul are trei locuri de căutat — plus unul dintre ele nu e în meniu.

### 1.4 Partea profesorului (TeacherDashboard, 2 tab-uri)

- **„Corectări"** → submissions (pending/corecte/incorecte) ✅ funcțional complet
- **„📹 Cereri ajutor live"** → DOAR `help_requests` cu `flag_type='LIVE'` (filtrat explicit în [main.py:2114](edu_content_api/main.py))

**Ce lipsește pe partea profesorului:**
- Cererile `WRITTEN` și `VIDEO` **nu apar nicăieri**. Endpoint-ul `respondToHelpRequest` (text) și `uploadHelpVideo` există în API, dar **nu sunt apelate din niciun component**. → gaură neagră (constatarea #1).

---

## 2. Probleme identificate (prioritizate)

| # | Severitate | Problemă | Impact |
|---|---|---|---|
| 1 | 🔴 Critic | Cererile WRITTEN/VIDEO nu au UI de răspuns la profesor; B.4 le face default | Elevul premium trimite cereri care nu primesc niciodată răspuns |
| 2 | 🟠 Mare | 3 intrări suprapuse pe exercițiu, 2 cu același icon Flag | Elevul nu înțelege ce buton face ce; alege greșit |
| 3 | 🟠 Mare | „Activitatea mea" nu e în navigație | Elevul nu-și găsește corecțiile/răspunsurile decât din notificări |
| 4 | 🟡 Mediu | 3 sisteme paralele = 3 vederi separate (De revizuit / Cereri / Soluții) | Fragmentare; nimic nu leagă „am flag-uit" de „lucrez cu profesorul" |
| 5 | 🟡 Mediu | Sesiunea live e per-cerere-unică; nu agregă exercițiile flag-uite | Exact golul pe care l-ai intuit tu — oportunitate, nu bug |
| 6 | 🟢 Minor | Terminologie inconsistentă (blocat/corectare/ajutor/activitate/soluții) | Sarcină cognitivă crescută |

---

## 3. Propunerea de model unificat

### Ideea centrală
Un singur concept mental pentru elev: **„Am nevoie de ajutor la exercițiul ăsta."** Nu trei butoane, ci **o intrare** care întreabă *ce fel* de ajutor, și o coloană vertebrală comună: **flag-ul / review-ul**.

### 3.1 O singură intrare pe exercițiu: „Cere ajutor"
Înlocuiește „M-am blocat" + „Vreau corectare" (+ escaladarea din sesiune) cu **un buton „Cere ajutor / Trimite profesorului"**, care deschide un pas de intenție clar:

| Vreau… | Ce se întâmplă | Sistem |
|---|---|---|
| „Să-mi verifice soluția" | urc poza → corectare | submissions |
| „O explicație scrisă" | trimit întrebarea + contextul → profesor răspunde în scris | help WRITTEN |
| „Să lămurim live" | intru pe lista pentru sesiune live | help LIVE |

Indiferent de alegere, exercițiul e **automat flag-uit** (intră în „De revizuit"). Așa, „flag" nu mai e o acțiune separată de „cer ajutor" — sunt același gest.

### 3.2 Flag-ul ca fir comun → sesiunea live pe exerciții flag-uite (propunerea ta)
Când elevul are o **sesiune live** programată, profesorul (și elevul) deschid o vedere care **agregă exercițiile flag-uite / de revizuit** ale elevului, cu tot contextul (răspuns introdus, notițe, indicii folosite, nr. încercări — pe care B.4 deja le colectează). Le parcurg împreună; „am clarificat" le scoate din listă. Exact ce ai descris.

### 3.3 Un inbox unic pentru profesor (Sprint D, deja planificat)
O singură listă prioritizată: **corectări + cereri scrise + live**, fiecare cu contextul complet. Rezolvă gaura neagră #1 și fragmentarea profesorului.

---

## 4. Plan de implementare pe faze

### Faza 0 — Oprire scurgere (urgent, mic) — ~0.5 zi
Închide gaura neagră WRITTEN/VIDEO **acum**, până există inbox-ul:
- **Opțiune rapidă (recomandată):** în Sprint B.4, restrânge temporar la ce știe profesorul să gestioneze — „Sesiune live" + „Verificare soluție (poză)"; ascunde „Rezolvare scrisă/video" până la Faza 2. Zero cereri pierdute.
- Alternativ: adaugă răspuns text în dashboard-ul profesorului (dar asta e deja Faza 2).

### Faza 1 — Unificarea intrării elevului — ~2-3 zile
- Un singur buton „Cere ajutor" pe fiecare exercițiu (în listă și în sesiune), cu pasul de intenție din §3.1.
- Flag automat la orice cerere.
- Terminologie unică (rezolv #2 și #6).

### Faza 2 — Inbox unificat profesor (Sprint D) — ~3-4 zile
- O listă prioritizată: corectări + scrise + live, cu context complet (răspuns, notițe, indicii, încercări).
- Adaugă UI de răspuns pentru WRITTEN/VIDEO (rezolvă definitiv #1).

### Faza 3 — Sesiune live pe exerciții flag-uite (propunerea ta) — ~3-4 zile
- Vedere de sesiune live care agregă review-ul elevului; profesor + elev lucrează împreună; „am clarificat" rezolvă itemii (rezolvă #5).

### Faza 4 — Consolidarea vederilor elevului — ~1-2 zile
- Mută „Activitatea mea" în Progres (sau adaug-o în navigație) și unifică De revizuit + Cereri + Soluții într-un singur „firul meu cu profesorul" (rezolvă #3 și #4).

### Ordine recomandată
**Faza 0 imediat** (oprește pierderea de cereri) → **Faza 1** (câștig mare de claritate, low risk) → **Faza 2** → **Faza 4** → **Faza 3** (feature nou, cel mai mult efort). Fazele 0-1 aduc 80% din claritate cu 20% din efort.

---

## 5. Răspuns direct la întrebările tale

**„Care e diferența dintre «m-am blocat» și «vreau corectare»?"**
- „M-am blocat" = *nu am reușit* → salvează în „de revizuit" și opțional cere ajutor live.
- „Vreau corectare" = *am o soluție* → o urc, profesorul o corectează.
Sunt momente diferite din același flux (blocat → încerc → am o soluție → verific), dar prezentate ca butoane rivale cu același icon. **Da, trebuie gândite ca o singură intrare** cu intenție aleasă în interior (§3.1).

**„Poate ar fi mai bine să dau flag și în sesiunea live să accesez ce am flag-uit."**
Corect și valoros. Azi flag-ul (review) și sesiunea live sunt sisteme deconectate. Propunerea leagă flag-ul de sesiunea live (§3.2 / Faza 3) — devine coloana vertebrală a colaborării elev–profesor.

---

## 6. Note

- Constatările #1 și #3 sunt bug-uri reale de UX (scurgeri), nu doar preferințe — le-aș prioritiza chiar dacă amânăm restul.
- Faza 0 e o măsură de siguranță pe care o pot face în aceeași zi cu un accept scurt.
- Nimic din plan nu atinge producția până nu decizi tu; totul stă pe branch.
