# EtoX Academy - Brief de implementare pentru simplificarea platformei

**Versiune:** 1.0  
**Data:** 10 august 2026  
**Statut:** propunere pentru estimare si implementare  
**Public tinta:** dezvoltator frontend, dezvoltator backend, QA, product owner

## 1. Scopul proiectului

Platforma EtoX are deja functionalitati valoroase pentru elevi, parinti si profesori, dar numarul de optiuni si separarea lor in mai multe pagini pot face experienta greu de inteles la prima utilizare.

Scopul acestei etape este simplificarea fluxurilor existente, nu adaugarea unui nou set mare de functionalitati.

Rezultatul urmarit:

- un elev nou ajunge la primul exercitiu in maximum 60 de secunde;
- actiunea principala este accesibila in maximum 3 interactiuni;
- orice sesiune neterminata poate fi reluata imediat;
- elevul nu trebuie sa inteleaga arhitectura platformei pentru a o folosi;
- profesorul vede clar ce necesita actiune si ce este deja rezolvat;
- parintele vede un rezumat, nu un panou operational complicat;
- fluxurile functioneaza corect pe mobil, nu doar pe desktop.

## 2. Principii UX obligatorii

### 2.1 O singura actiune dominanta

Fiecare ecran trebuie sa aiba o actiune principala evidenta. Actiunile secundare nu trebuie sa concureze vizual cu aceasta.

Ordinea actiunii principale pe dashboard-ul elevului:

1. Daca exista o sesiune activa: `Continua sesiunea`.
2. Daca exista o activitate planificata astazi: `Incepe obiectivul de azi`.
3. Daca exista o recomandare bazata pe progres: `Lucreaza recomandarea`.
4. Altfel: `Incepe o sesiune de 10 minute`.

### 2.2 Dezvaluire progresiva

Informatiile secundare trebuie afisate doar atunci cand sunt cerute sau cand devin relevante.

Exemple:

- statisticile detaliate nu apar inaintea actiunii zilnice;
- solutia completa nu apare inaintea unei incercari sau a unei confirmari;
- filtrele avansate sunt ascunse initial;
- optiunile de contactare a profesorului apar dupa folosirea indiciilor disponibile;
- calendarul complet este accesibil din `Progres`, nu afisat integral pe dashboard.

### 2.3 Salvare automata si continuitate

Elevul nu trebuie sa piarda progresul daca inchide pagina, schimba ruta sau pierde temporar conexiunea.

Trebuie salvate automat:

- sesiunea activa;
- exercitiul curent;
- raspunsul final introdus;
- notitele de lucru;
- exercitiile marcate ca rezolvate;
- timpul activ, in limite rezonabile;
- ultima pagina sau ultima zona relevanta din sesiune.

### 2.4 Limbaj consecvent

Se va folosi acelasi verb pentru aceeasi actiune in intreaga platforma.

| Concept | Eticheta standard |
|---|---|
| Pornire sesiune | `Incepe sesiunea` |
| Reluare sesiune | `Continua sesiunea` |
| Verificare raspuns | `Verifica raspunsul` |
| Exercitiu terminat | `Marcheaza rezolvat` |
| Terminare sesiune | `Finalizeaza sesiunea` |
| Renuntare | `Inchide sesiunea` |
| Lista de revenire | `De revizuit` |
| Ajutor gradual | `Vezi un indiciu` |
| Escaladare | `Cere ajutor profesorului` |

Nu se vor alterna pentru acelasi concept etichete precum `Marcheaza`, `Gata`, `Finalizat`, `Trimite` sau `Rezolvat` fara o diferenta reala de comportament.

## 3. Arhitectura informationala propusa

### 3.1 Navigatie elev

Navigatia principala trebuie redusa la patru destinatii:

| Destinatie | Ruta recomandata | Continut |
|---|---|---|
| Acasa | `/app` | actiunea de azi, sesiune activa, rezumat minimal |
| Exerseaza | `/app/practice` sau ruta existenta consolidata | sesiuni, exercitii, seturi si variante |
| Progres | `/app/progress` | traseu, statistici, istoric, calendar, exercitii de revizuit |
| Clasa mea | `/app/league` | clasa, clasament, provocari, XP si insigne |

Rutele vechi pot ramane active pentru compatibilitate, dar navigatia principala nu trebuie sa le afiseze individual.

Mapare recomandata:

| Ruta existenta | Destinatie noua |
|---|---|
| `/app/exercises` | tab in `Exerseaza` |
| `/app/subiecte` | tab sau filtru in `Exerseaza` |
| `/app/study-session` | actiune principala in `Exerseaza` |
| `/app/variants` | tip de antrenament in `Exerseaza` |
| `/app/study-plan` | sectiune in `Progres` |
| `/app/learning-path` | sectiune in `Progres` |
| `/app/my-requests` | sectiune `Ajutor primit` in `Progres` |
| tab-ul `review` din exercitii | sectiune `De revizuit` in `Progres` |

### 3.2 Navigatie profesor

| Destinatie | Continut |
|---|---|
| Panou | sumar, urgente, activitate recenta |
| Clase | clase, elevi, coduri, provocari, progres |
| Solicitari | inbox unificat pentru verificari, ajutor si sesiuni live |
| Continut | surse, import, exercitii, variante si PDF |

### 3.3 Navigatie parinte

Parintele nu are nevoie de o navigatie complexa. Dashboard-ul sau trebuie sa contina:

- selectarea copilului, daca are mai multi copii asociati;
- rezumatul saptamanii;
- ritmul de studiu si calendarul;
- capitolele care necesita atentie;
- numarul exercitiilor de revizuit;
- sesiunile live viitoare;
- o explicatie clara a indicatorilor.

## 4. Epic 1 - Dashboard elev orientat spre actiune

**Prioritate:** P0  
**Complexitate estimativa:** M  
**Componente principale:** `frontend/src/App.tsx`, `frontend/src/App.css`

### 4.1 Cerinte functionale

Dashboard-ul trebuie sa afiseze in aceasta ordine:

1. salut scurt si obiectivul zilei;
2. cardul principal `Ce faci acum`;
3. maximum trei indicatori: progres saptamanal, streak, exercitii de revizuit;
4. un rezumat compact al calendarului;
5. acces la detalii prin `Vezi progresul complet`.

Cardul principal trebuie sa respecte urmatoarea logica:

```text
activeSession exista
  -> Continua sesiunea
altfel todayPlanEntries are elemente
  -> Incepe activitatea planificata
altfel recommendation exista
  -> Exerseaza recomandarea
altfel
  -> Incepe o sesiune de 10 minute
```

### 4.2 Comportament obligatoriu

- CTA-ul principal trebuie sa arate ca un buton, nu ca text sau card pasiv.
- Nu trebuie sa existe texte suprapuse la 320 px, 375 px, 768 px sau desktop.
- Incarcarea separata a datelor nu trebuie sa produca salturi mari de layout.
- Daca un endpoint esueaza, CTA-ul principal trebuie sa ramana utilizabil cand este posibil.
- Starea goala trebuie sa explice urmatorul pas, nu doar lipsa datelor.
- Countdown-ul BAC nu trebuie calculat dintr-o data hardcodata in componenta.

### 4.3 Data BAC

In prezent exista valoarea hardcodata `2026-07-01` in `AppHub`. Aceasta trebuie eliminata.

Solutii acceptabile:

- data este stocata intr-o configuratie backend si furnizata prin API;
- data este stocata intr-o variabila de mediu frontend;
- countdown-ul este ascuns pana cand exista o data oficiala configurata.

Solutia recomandata este configurarea backend, astfel incat data sa poata fi schimbata fara rebuild frontend.

### 4.4 Criterii de acceptanta

- Elevul cu sesiune activa vede `Continua sesiunea` fara scroll.
- Elevul fara sesiune activa vede o singura recomandare principala.
- CTA-ul duce la sesiunea corecta si pastreaza filtrele existente.
- Dashboard-ul poate fi folosit la latimea de 320 px fara scroll orizontal.
- Nicio eroare a statisticilor nu blocheaza pornirea unei sesiuni.
- Nu sunt afisate simultan mai mult de doua CTA-uri in zona principala.

## 5. Epic 2 - Flux unificat de exersare

**Prioritate:** P0  
**Complexitate estimativa:** L  
**Componente principale:** `StudySession.tsx`, `StudentExercises.tsx`, stilurile asociate, `api.ts`

### 5.1 Obiectiv

Elevul trebuie sa poata parcurge integral un exercitiu fara sa navigheze intre pagini separate pentru enunt, lucru, raspuns, verificare, indiciu, solutie si ajutor.

### 5.2 Structura ecranului

Pe desktop:

| Zona | Continut |
|---|---|
| Header compact | progres, timer optional, inchidere |
| Zona principala | enuntul si continutul matematic |
| Workspace | notite, instrumente matematice, incarcare fotografie optionala |
| Raspuns final | camp separat si buton de verificare |
| Ajutor gradual | indiciu 1, indiciu 2, explicatie, profesor |
| Footer sticky | anterior, urmator, marcheaza rezolvat |

Pe mobil zonele se afiseaza intr-o singura coloana, iar actiunile principale raman accesibile in partea de jos.

### 5.3 Durata sesiunii

Configurarea initiala trebuie simplificata la trei alegeri usor de inteles:

| Optiune | Comportament |
|---|---|
| 10 minute | sesiune scurta, prioritate pe recomandare |
| 20 minute | sesiune medie, mix recomandat |
| 40 minute | antrenament extins |

`Varianta BAC completa` ramane o optiune distincta si nu trebuie confundata cu sesiunile scurte.

### 5.4 Verificarea raspunsului

- Campul `Raspuns final` este vizibil pentru exercitiile verificabile automat.
- Butonul este dezactivat doar daca raspunsul este gol sau invalid.
- Mesajul explica de ce verificarea nu este disponibila.
- La raspuns corect se actualizeaza progresul fara refresh complet.
- La raspuns gresit se ofera urmatorul pas: reincearca, indiciu sau revizuire.
- Solutia oficiala nu este afisata automat dupa prima greseala.
- Verificarea trebuie sa accepte formate echivalente deja suportate de backend.

### 5.5 Ajutor gradual

Ordinea recomandata:

1. `Vezi un indiciu`.
2. `Mai arata-mi un pas`.
3. `Vezi explicatia`.
4. `Cere ajutor profesorului`.

Trimiterea catre profesor trebuie sa includa automat:

- exercitiul;
- raspunsul final introdus;
- notitele elevului, daca exista;
- indiciile deja consultate;
- numarul incercarilor;
- fotografia incarcata, daca exista;
- motivul selectat de elev.

### 5.6 Salvare automata

Se recomanda autosave cu debounce intre 500 si 1000 ms pentru text si salvare imediata pentru actiuni discrete.

La revenire trebuie restaurate:

- exercitiul curent;
- raspunsurile introduse;
- notitele;
- statusul fiecarui exercitiu;
- progresul sesiunii;
- timpul relevant al sesiunii.

### 5.7 Criterii de acceptanta

- Un exercitiu poate fi parcurs complet intr-un singur ecran.
- Refresh-ul paginii nu pierde raspunsul salvat.
- Reluarea din dashboard deschide exercitiul corect.
- Elevul poate continua chiar daca verificarea automata nu este disponibila.
- Solicitarea catre profesor contine contextul de lucru.
- Pe mobil nu exista actiuni esentiale inaccesibile din cauza tastaturii virtuale.

## 6. Epic 3 - Zona Progres consolidata

**Prioritate:** P1  
**Complexitate estimativa:** M  
**Componente reutilizate:** `StudyPlan.tsx`, `StudyPrepCalendar.tsx`, `LearningPath.tsx`, istoricul din `StudySession.tsx`, `ReviewTab` din `StudentExercises.tsx`

### 6.1 Tab-uri recomandate

| Tab | Continut |
|---|---|
| Rezumat | progres pe subiecte, recomandare, activitate recenta |
| Calendar | zile active, zile planificate, streak |
| De revizuit | exercitii deschise automat sau manual |
| Istoric | sesiuni finalizate si abandonate |
| Traseul meu | diagnostic si plan adaptat |

### 6.2 Lista `De revizuit`

Fiecare card trebuie sa aiba maximum trei actiuni:

- `Rezolva din nou`;
- `Vezi un indiciu`;
- `Scoate din lista`.

Nu se va cere elevului sa inteleaga statusuri tehnice. Motivele pot fi afisate simplu: `raspuns gresit`, `lasat neterminat`, `marcat de tine`.

### 6.3 Criterii de acceptanta

- Toate datele de progres sunt accesibile dintr-o singura destinatie principala.
- Revenirea la un exercitiu pastreaza contextul si rezultatul anterior.
- Calendarul foloseste aceleasi date pe dashboard-ul elevului si al parintelui.
- Istoricul distinge clar intre activ, finalizat si inchis.
- Elevul poate porni o noua sesiune direct dintr-o recomandare.

## 7. Epic 4 - Inbox unificat pentru profesor

**Prioritate:** P1  
**Complexitate estimativa:** M-L  
**Componente principale:** `TeacherDashboard.tsx`, endpoint-urile pentru submissions, help requests si statistici

### 7.1 Obiectiv

Profesorul nu trebuie sa verifice mai multe zone pentru elemente care necesita aceeasi decizie operationala.

### 7.2 Structura inbox

Filtre principale:

- `Necesita actiune`;
- `Preluate de mine`;
- `Programate`;
- `Rezolvate`.

Fiecare solicitare trebuie sa arate:

- tipul solicitarii;
- elevul si clasa;
- exercitiul;
- timpul de asteptare;
- nivelul de urgenta;
- incercarile si indiciile elevului;
- profesorul asignat;
- actiunea urmatoare.

### 7.3 Prioritizare

Ordinea implicita recomandata:

1. sesiuni live apropiate;
2. solicitari vechi nepreluate;
3. raspunsuri retrimise dupa feedback;
4. solicitari noi;
5. elemente deja rezolvate.

### 7.4 Instrumente de eficienta

- sabloane editabile pentru raspunsuri frecvente;
- preluare rapida a unei solicitari;
- actiuni de lot doar unde nu exista risc pedagogic;
- actualizarea imediata a contoarelor dupa fiecare actiune;
- refresh automat discret sau invalidare de cache;
- link direct catre exercitiul complet.

### 7.5 Criterii de acceptanta

- Contoarele pending, corect, incorect si total se actualizeaza fara refresh manual.
- O solicitare rezolvata dispare din `Necesita actiune` imediat.
- Doua cadre didactice nu pot prelua aceeasi solicitare fara avertizare.
- Profesorul poate raspunde fara sa piarda pozitia din lista.
- Starile goale explica daca nu exista solicitari sau daca filtrul este prea restrictiv.

## 8. Epic 5 - Dashboard parinte simplificat

**Prioritate:** P2  
**Complexitate estimativa:** S-M  
**Componenta principala:** `ParentDashboard.tsx`

### 8.1 Informatii afisate

Ordinea recomandata:

1. `Cum a fost saptamana aceasta`;
2. zile active si timp de studiu;
3. exercitii rezolvate si rata de completare;
4. zone care necesita atentie;
5. exercitii de revizuit;
6. activitati si sesiuni viitoare;
7. calendar complet.

### 8.2 Reguli de prezentare

- Se vor afisa tendinte, nu doar totaluri istorice.
- Indicatorii vor avea explicatii in limbaj normal.
- Nu se vor folosi culori alarmante pentru lipsa unei singure zile de activitate.
- Nu se vor afisa clasamente comparative parintelui fara o justificare pedagogica.
- Informatiile trebuie formulate ca suport, nu ca instrument de presiune.

## 9. Onboarding

**Prioritate:** P1  
**Complexitate estimativa:** M

La prima autentificare, elevul raspunde la maximum trei intrebari:

| Intrebare | Utilizare |
|---|---|
| Ce profil urmezi? | filtre si continut relevant |
| Cand sustii BAC-ul? | calendar si ritm |
| Cat timp poti aloca intr-o saptamana? | recomandari si plan |

Testul diagnostic trebuie recomandat, dar nu trebuie sa blocheze accesul la exercitii.

Turul initial trebuie sa aiba maximum trei pasi si sa apara contextual:

1. aici continui ce ai inceput;
2. aici introduci si verifici raspunsul;
3. aici vezi progresul si ce ai de revizuit.

Utilizatorul poate inchide turul si nu il va vedea din nou automat.

## 10. Stari de incarcare, eroare si continut gol

Fiecare ecran modificat trebuie sa implementeze explicit:

| Stare | Cerinta |
|---|---|
| Loading | skeleton stabil, fara salt major de layout |
| Empty | explicatie si CTA relevant |
| Error recuperabil | mesaj concret si `Reincearca` |
| Error de autentificare | revenire controlata la login |
| Offline | continutul deja incarcat ramane vizibil unde este posibil |
| Success | feedback vizibil, dar neintruziv |

Mesajele generice precum `A aparut o eroare` sunt acceptabile doar impreuna cu o actiune si un identificator util pentru diagnostic.

## 11. Cerinte de accesibilitate si responsive

- Toate actiunile sunt accesibile din tastatura.
- Focus-ul vizibil nu este eliminat.
- Butoanele interactive au minimum 44 x 44 px pe mobil.
- Contrastul respecta WCAG AA pentru text si controale esentiale.
- Iconurile fara text au `aria-label`.
- Modalele mentin focus-ul si il returneaza la inchidere.
- Formulele lungi pot fi derulate orizontal in interiorul containerului.
- Nu exista scroll orizontal la 320 px, 375 px, 768 px, 1024 px si 1440 px.
- Actiunile sticky nu acopera continutul sau campurile cand tastatura mobila este deschisa.
- `prefers-reduced-motion` este respectat.

## 12. Masurare si analytics

Inainte de modificare trebuie stabilite valorile de baza. Dupa lansare se compara aceleasi intervale.

Evenimente minime:

| Eveniment | Proprietati recomandate |
|---|---|
| `dashboard_primary_cta_viewed` | tip CTA, rol |
| `dashboard_primary_cta_clicked` | tip CTA, sursa |
| `study_session_started` | durata, sursa, filtre |
| `study_session_resumed` | vechime sesiune, progres anterior |
| `answer_checked` | disponibil automat, rezultat, incercare |
| `hint_opened` | nivel indiciu, numar incercari |
| `teacher_help_requested` | tip, indicii consultate |
| `study_session_completed` | durata, completare, exercitii |
| `study_session_abandoned` | exercitiul curent, durata |
| `review_item_reopened` | motiv, vechime |

KPI propusi:

- timpul median pana la primul exercitiu;
- rata de pornire a unei sesiuni dupa login;
- rata de finalizare a sesiunilor;
- rata de reluare a sesiunilor active;
- numarul mediu de clickuri pana la primul raspuns;
- procentul solicitarilor profesor precedate de indicii;
- timpul median de raspuns al profesorului;
- utilizatori activi saptamanal pe rol;
- rata de revenire dupa 7 zile.

Analytics-ul nu trebuie sa colecteze continut sensibil din raspunsuri sau notite.

## 13. Impact tehnic si reutilizare

### 13.1 Frontend existent care trebuie reutilizat

| Zona | Componenta sau fisier existent |
|---|---|
| Dashboard si navigatie | `frontend/src/App.tsx`, `frontend/src/App.css` |
| Sesiune | `frontend/src/components/StudySession.tsx` |
| Exercitii si review | `frontend/src/components/StudentExercises.tsx` |
| Plan | `frontend/src/components/StudyPlan.tsx` |
| Calendar | `frontend/src/components/StudyPrepCalendar.tsx` |
| Traseu | `frontend/src/components/LearningPath.tsx` |
| Profesor | `frontend/src/components/TeacherDashboard.tsx` |
| Parinte | `frontend/src/components/ParentDashboard.tsx` |
| Liga BAC | `frontend/src/components/LeagueHub.tsx` |
| Contracte API | `frontend/src/api.ts` |

### 13.2 API-uri existente relevante

| Scop | API existent |
|---|---|
| Lista sesiuni | `GET /study-sessions/` |
| Reluare sesiune | `GET /study-sessions/{id}` |
| Pornire | `POST /study-sessions/start` |
| Finalizare | `POST /study-sessions/{id}/complete` |
| Inchidere | `POST /study-sessions/{id}/abandon` |
| Statistici elev | `GET /student/study-stats` |
| Plan elev | `GET /study-plan/` |
| Gamification | endpoint-ul folosit de `getMyGamification()` |
| Review elev | `GET /student/review-items` |
| Statistici profesor | `GET /teacher/submissions/stats` |

### 13.3 Endpoint agregat optional

Dashboard-ul elevului incarca in prezent sesiuni, plan, statistici, gamification si traseu prin cereri separate. Se poate pastra aceasta abordare in prima iteratie.

Daca apar intarzieri, stari partiale greu de controlat sau prea multe cereri, se recomanda:

```http
GET /student/today
```

Raspuns orientativ:

```json
{
  "active_session": null,
  "today_plan": [],
  "recommendation": {
    "type": "short_session",
    "subiect": "2",
    "reason": "Ai cel mai mult loc de progres la Subiectul II"
  },
  "weekly": {
    "sessions": 3,
    "exercises": 24,
    "streak": 4,
    "review_open": 3
  },
  "needs_diagnostic": false,
  "exam_date": "2027-06-30"
}
```

Data din exemplu este ilustrativa. Data reala trebuie configurata, nu introdusa direct in cod.

## 14. Strategie de implementare

### Sprint A - Fundatia UX

- simplificarea navigatiei pe roluri;
- dashboard elev orientat spre o actiune;
- eliminarea datei BAC hardcodate;
- componente comune pentru loading, empty, error si CTA;
- instrumentare analytics pentru valorile de baza.

### Sprint B - Sesiunea unificata

- configurare prin durata;
- workspace unic pentru exercitiu;
- raspuns final si verificare;
- ajutor gradual;
- autosave si reluare completa;
- rezumat final simplificat.

### Sprint C - Progres si continuitate

- ruta consolidata `Progres`;
- calendar, istoric, review si traseu in aceeasi zona;
- CTA-uri directe spre urmatoarea sesiune;
- alinierea dashboard-ului parintelui.

### Sprint D - Profesor

- inbox unificat;
- prioritizare si filtre;
- contoare reactive;
- sabloane si actiuni rapide;
- verificare concurenta la preluarea solicitarilor.

Fiecare sprint trebuie sa poata fi lansat independent, fara a lasa rute sau fluxuri nefunctionale.

## 15. Plan de testare

### 15.1 Teste automate minime

- test pentru ordinea CTA-ului principal pe cele patru stari ale dashboard-ului;
- test pentru construirea URL-ului de reluare cu `resume`;
- test pentru pastrarea filtrelor din plan;
- test pentru pornire, finalizare si inchidere sesiune;
- test pentru autosave si restaurare;
- test pentru activarea butonului de verificare;
- test pentru fallback cand raspunsul nu este verificabil automat;
- test pentru actualizarea contoarelor profesorului;
- smoke test pentru rutele principale pe fiecare rol;
- build TypeScript si lint pe fisierele modificate.

### 15.2 Verificare manuala

Matrice minima:

| Rol | Desktop | Mobil |
|---|---:|---:|
| Elev nou | obligatoriu | obligatoriu |
| Elev cu sesiune activa | obligatoriu | obligatoriu |
| Elev cu plan | obligatoriu | obligatoriu |
| Profesor | obligatoriu | obligatoriu |
| Parinte | obligatoriu | obligatoriu |
| Admin | smoke | smoke |

Scenarii critice:

1. Elevul porneste o sesiune si inchide browserul.
2. Elevul revine si continua exact de unde a ramas.
3. Elevul introduce un raspuns corect si primeste feedback.
4. Elevul introduce un raspuns gresit, foloseste indicii si incearca din nou.
5. Exercitiul nu are raspuns verificabil automat, dar sesiunea poate continua.
6. Elevul solicita ajutor dupa folosirea indiciilor.
7. Profesorul preia si rezolva solicitarea.
8. Statisticile profesorului se actualizeaza imediat.
9. Parintele vede activitatea si numarul de exercitii de revizuit.
10. Conexiunea esueaza temporar in timpul unei sesiuni.

## 16. Definitia de finalizat

O etapa este finalizata doar daca:

- criteriile de acceptanta sunt indeplinite;
- nu exista regresii pe rutele vechi;
- build-ul frontend trece;
- smoke test-ele backend si frontend trec;
- fisierele modificate trec lint-ul;
- fluxurile critice sunt verificate pe desktop si mobil;
- starile loading, empty si error sunt implementate;
- analytics-ul necesar este documentat si validat;
- documentatia rutelor si componentelor este actualizata;
- modificarile pot fi dezactivate sau revenite controlat daca apare o problema in productie.

## 17. Ce nu intra in aceasta etapa

- procesator nou de plati;
- schimbarea completa a modelelor de abonament;
- aplicatie mobila nativa;
- rescrierea backend-ului existent;
- inlocuirea generatorului de exercitii;
- redesign complet al panoului admin;
- sistem nou de mesagerie in timp real;
- functionalitati sociale suplimentare in Liga BAC.

Acestea pot fi planificate separat dupa validarea noilor fluxuri.

## 18. Decizii care trebuie confirmate de product owner

Inainte de Sprint B trebuie confirmate:

1. duratele finale ale sesiunilor: 10/20/40 minute sau alta combinatie;
2. momentul in care solutia oficiala devine vizibila;
3. daca notitele elevului sunt salvate pe server sau doar local;
4. daca un exercitiu gresit intra automat in `De revizuit` dupa prima sau a doua incercare;
5. limita si regulile solicitarilor catre profesor;
6. sursa oficiala pentru data BAC;
7. instrumentul de analytics si politica de confidentialitate;
8. daca rutele consolidate se lanseaza gradual sau pentru toti utilizatorii simultan.

## 19. Rezultatul asteptat

La final, EtoX trebuie sa fie perceputa ca un traseu de pregatire, nu ca o colectie de module separate.

Elevul intra, vede ce are de facut, lucreaza, primeste feedback si stie ce urmeaza. Profesorul vede doar ce necesita actiune. Parintele intelege progresul fara sa navigheze prin instrumentele elevului.

Aceasta este directia de produs care trebuie pastrata in toate deciziile tehnice si vizuale din implementare.
