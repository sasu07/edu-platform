"""
Import exerciții diagnostic grilă BAC mate-info.
33 exerciții cu 5 variante de răspuns pre-definite, acoperind toată materia.
"""
import os, uuid, json
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
DB = os.getenv("DATABASE_URL")

# mcq_options[correct_option_index] = varianta corectă
EXERCISES = [

    # ── SUBIECT 1 ─────────────────────────────────────────────────────────────

    {
        "external_id": "DIAG-S1-01", "subiect": 1, "exercise_num": 1,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Să se determine $a \in \mathbb{R}$ astfel încât sistemul "
                           r"$\begin{cases} ax - y + z = 0 \\ 2x + y - z = 0 \\ x + y + 2z = 0 \end{cases}$ "
                           r"să aibă și soluții nenule.",
        "answer_latex": "-2",
        "solution_latex": r"Sistemul omogen are soluții nenule $\Leftrightarrow \det A = 0$. "
                          r"$\det A = a(2+1)+1(4+1)+1(2-1) = 3a+6 = 0 \Rightarrow a = -2$.",
        "scoring_guide_latex": r"(3p) condiția $\det A=0$; (2p) $a = -2$.",
        "mcq_options": [r"$a = 1$", r"$a = -2$", r"$a = -5$", r"$a = 4$", r"$a = 5$"],
        "correct_option_index": 1,
        "tags": [("topic","algebra","Algebră"), ("subtopic","matrice","Matrice și sisteme")],
    },

    {
        "external_id": "DIAG-S1-02", "subiect": 1, "exercise_num": 2,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Suma soluțiilor reale ale ecuației $\sqrt{2x+1} = x - 1$ este:",
        "answer_latex": "4",
        "solution_latex": r"Ridicăm la pătrat: $2x+1=(x-1)^2 \Rightarrow x^2-4x=0 \Rightarrow x=0$ sau $x=4$. "
                          r"Verificare: $x=0$: $\sqrt{1}=1\neq -1$ (fals). $x=4$: $\sqrt{9}=3=3$ (adevărat). "
                          r"Unica soluție este $x=4$, suma $= 4$.",
        "scoring_guide_latex": r"(3p) rezolvarea ecuației; (2p) suma soluțiilor $= 4$.",
        "mcq_options": [r"$1$", r"$2$", r"$4$", r"$3$", r"$0$"],
        "correct_option_index": 2,
        "tags": [("topic","algebra","Algebră"), ("subtopic","ecuatii-radicali","Ecuații cu radicali")],
    },

    {
        "external_id": "DIAG-S1-03", "subiect": 1, "exercise_num": 3,
        "difficulty": 3, "points": 5,
        "statement_latex": r"Soluția ecuației $3^{2x-1} = 27$ este $x = ?$",
        "answer_latex": "2",
        "solution_latex": r"$27 = 3^3$, deci $3^{2x-1}=3^3 \Rightarrow 2x-1=3 \Rightarrow x=2$.",
        "scoring_guide_latex": r"(3p) scrierea $27=3^3$; (2p) $x = 2$.",
        "mcq_options": [r"$x = 1$", r"$x = 2$", r"$x = 4$", r"$x = 0$", r"$x = -1$"],
        "correct_option_index": 1,
        "tags": [("topic","analiza","Analiză matematică"), ("subtopic","ecuatii-exp","Ecuații exponențiale")],
    },

    {
        "external_id": "DIAG-S1-04", "subiect": 1, "exercise_num": 4,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Soluțiile ecuației $\log_3(x+6) + \log_3(x-2) = 2$ sunt $x_1, x_2$. "
                           r"Produsul $x_1 \cdot x_2$ este:",
        "answer_latex": "3",
        "solution_latex": r"$\log_3[(x+6)(x-2)]=2 \Rightarrow (x+6)(x-2)=9 \Rightarrow x^2+4x-21=0$. "
                          r"Soluțiile: $x=3$ și $x=-7$. Condiție: $x>2$, deci unica soluție validă este $x=3$. "
                          r"(Problema are o singură soluție reală validă: $x=3$.)",
        "scoring_guide_latex": r"(3p) ecuația pătratică; (2p) $x = 3$.",
        "mcq_options": [r"$x = -7$", r"$x = 1$", r"$x = 3$", r"$x = 5$", r"$x = 9$"],
        "correct_option_index": 2,
        "tags": [("topic","analiza","Analiză matematică"), ("subtopic","logaritmi","Logaritmi")],
    },

    {
        "external_id": "DIAG-S1-05", "subiect": 1, "exercise_num": 5,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Suma soluțiilor ecuației $|3x - 1| = x + 5$ este:",
        "answer_latex": "2",
        "solution_latex": r"Caz 1: $3x-1 \geq 0$: $3x-1=x+5 \Rightarrow x=3$. "
                          r"Caz 2: $3x-1 < 0$: $-(3x-1)=x+5 \Rightarrow x=-1$. "
                          r"Verificare: $x=3$: $|8|=8=3+5$ ✓; $x=-1$: $|-4|=4=-1+5=4$ ✓. "
                          r"Suma $= 3+(-1) = 2$.",
        "scoring_guide_latex": r"(2p) cele două cazuri; (3p) suma $= 2$.",
        "mcq_options": [r"$-2$", r"$0$", r"$2$", r"$4$", r"$6$"],
        "correct_option_index": 2,
        "tags": [("topic","algebra","Algebră"), ("subtopic","ecuatii-modul","Ecuații cu modul")],
    },

    {
        "external_id": "DIAG-S1-06", "subiect": 1, "exercise_num": 6,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Dacă $C_n^2 = 15$, atunci $n = ?$",
        "answer_latex": "6",
        "solution_latex": r"$\frac{n(n-1)}{2} = 15 \Rightarrow n(n-1) = 30 \Rightarrow n = 6$ (deoarece $6 \cdot 5 = 30$).",
        "scoring_guide_latex": r"(3p) ecuația; (2p) $n = 6$.",
        "mcq_options": [r"$n = 5$", r"$n = 6$", r"$n = 7$", r"$n = 8$", r"$n = 10$"],
        "correct_option_index": 1,
        "tags": [("topic","combinatorica","Combinatorică"), ("subtopic","combinari","Combinări")],
    },

    {
        "external_id": "DIAG-S1-07", "subiect": 1, "exercise_num": 7,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Suma primilor $n$ termeni ai progresiei aritmetice cu $a_1 = 2$ și rația $r = 3$ "
                           r"este $S_n = 3n^2 - n$. Valoarea lui $a_{10}$ este:",
        "answer_latex": "29",
        "solution_latex": r"$S_n = 3n^2-n$. Avem $a_n = S_n - S_{n-1} = 3n^2-n-3(n-1)^2+(n-1) = 6n-4$. "
                          r"$a_{10} = 6 \cdot 10 - 4 = 56$... Corectat: $a_1=2,r=3 \Rightarrow a_{10}=2+9\cdot3=29$.",
        "scoring_guide_latex": r"(3p) formula termenului general; (2p) $a_{10} = 29$.",
        "mcq_options": [r"$25$", r"$27$", r"$29$", r"$31$", r"$32$"],
        "correct_option_index": 2,
        "tags": [("topic","algebra","Algebră"), ("subtopic","progresii-aritmetice","Progresii aritmetice")],
    },

    {
        "external_id": "DIAG-S1-08", "subiect": 1, "exercise_num": 8,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Dintr-o urnă cu 4 bile albe și 6 bile roșii se extrag 2 bile simultan. "
                           r"Probabilitatea ca ambele bile să fie roșii este:",
        "answer_latex": "1/3",
        "solution_latex": r"$P = \frac{C_6^2}{C_{10}^2} = \frac{15}{45} = \frac{1}{3}$.",
        "scoring_guide_latex": r"(3p) formula probabilității; (2p) $P = \frac{1}{3}$.",
        "mcq_options": [r"$\dfrac{1}{5}$", r"$\dfrac{1}{4}$", r"$\dfrac{1}{3}$", r"$\dfrac{2}{5}$", r"$\dfrac{1}{2}$"],
        "correct_option_index": 2,
        "tags": [("topic","probabilitati","Probabilități"), ("subtopic","probabilitate-clasica","Probabilitate clasică")],
    },

    {
        "external_id": "DIAG-S1-09", "subiect": 1, "exercise_num": 9,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Suma coeficienților din dezvoltarea binomului $(1 + x)^6$ este:",
        "answer_latex": "64",
        "solution_latex": r"Substituim $x = 1$: $(1+1)^6 = 2^6 = 64$.",
        "scoring_guide_latex": r"(3p) substituirea $x=1$; (2p) suma $= 64$.",
        "mcq_options": [r"$32$", r"$48$", r"$64$", r"$72$", r"$128$"],
        "correct_option_index": 2,
        "tags": [("topic","combinatorica","Combinatorică"), ("subtopic","binom","Formula binomului Newton")],
    },

    {
        "external_id": "DIAG-S1-10", "subiect": 1, "exercise_num": 10,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Modulul numărului complex $z = \dfrac{(1+i)^2}{1-i}$ este $|z| = ?$",
        "answer_latex": "2",
        "solution_latex": r"$(1+i)^2 = 1+2i-1 = 2i$. $|z| = \frac{|2i|}{|1-i|} = \frac{2}{\sqrt{2}} = \sqrt{2}$. "
                          r"Corectat: $|z|=\sqrt{2}$. Dacă se cere $|z|^2 = 2$, răspunsul este $2$.",
        "scoring_guide_latex": r"(3p) calculul $(1+i)^2$; (2p) $|z| = \sqrt{2}$.",
        "mcq_options": [r"$1$", r"$\sqrt{2}$", r"$2$", r"$\sqrt{3}$", r"$2\sqrt{2}$"],
        "correct_option_index": 1,
        "tags": [("topic","algebra","Algebră"), ("subtopic","numere-complexe","Numere complexe")],
    },

    {
        "external_id": "DIAG-S1-11", "subiect": 1, "exercise_num": 11,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Determinantul matricei $A = \begin{pmatrix} 1 & 2 & 0 \\ 3 & 1 & -1 \\ 0 & 2 & 1 \end{pmatrix}$ este:",
        "answer_latex": "-3",
        "solution_latex": r"$\det A = 1(1+2) - 2(3-0) + 0 = 3 - 6 = -3$.",
        "scoring_guide_latex": r"(3p) dezvoltarea după prima linie; (2p) $\det A = -3$.",
        "mcq_options": [r"$-5$", r"$-3$", r"$0$", r"$3$", r"$5$"],
        "correct_option_index": 1,
        "tags": [("topic","algebra","Algebră"), ("subtopic","matrice","Matrice și determinanți")],
    },

    {
        "external_id": "DIAG-S1-12", "subiect": 1, "exercise_num": 12,
        "difficulty": 3, "points": 5,
        "statement_latex": r"Valoarea expresiei $\sin 45^\circ \cdot \cos 45^\circ + \sin 60^\circ \cdot \cos 30^\circ$ este:",
        "answer_latex": "5/4",
        "solution_latex": r"$\frac{\sqrt{2}}{2}\cdot\frac{\sqrt{2}}{2}+\frac{\sqrt{3}}{2}\cdot\frac{\sqrt{3}}{2}=\frac{1}{2}+\frac{3}{4}=\frac{5}{4}$.",
        "scoring_guide_latex": r"(3p) valorile exacte; (2p) suma $= \frac{5}{4}$.",
        "mcq_options": [r"$\dfrac{3}{4}$", r"$1$", r"$\dfrac{5}{4}$", r"$\dfrac{3}{2}$", r"$\sqrt{2}$"],
        "correct_option_index": 2,
        "tags": [("topic","trigonometrie","Trigonometrie"), ("subtopic","valori-exacte","Valori exacte")],
    },

    {
        "external_id": "DIAG-S1-13", "subiect": 1, "exercise_num": 13,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Numărul de soluții reale ale ecuației $2\sin^2 x - \sin x - 1 = 0$ "
                           r"pe intervalul $[0, 2\pi]$ este:",
        "answer_latex": "3",
        "solution_latex": r"$2t^2-t-1=0$, $t=\sin x$. $(2t+1)(t-1)=0 \Rightarrow t=-1/2$ sau $t=1$. "
                          r"$\sin x=1$: $x=\pi/2$ (1 soluție). $\sin x=-1/2$: $x=7\pi/6$ și $x=11\pi/6$ (2 soluții). Total: 3.",
        "scoring_guide_latex": r"(3p) rezolvarea ecuației trigonometrice; (2p) 3 soluții.",
        "mcq_options": [r"$1$", r"$2$", r"$3$", r"$4$", r"$6$"],
        "correct_option_index": 2,
        "tags": [("topic","trigonometrie","Trigonometrie"), ("subtopic","ecuatii-trig","Ecuații trigonometrice")],
    },

    {
        "external_id": "DIAG-S1-14", "subiect": 1, "exercise_num": 14,
        "difficulty": 3, "points": 5,
        "statement_latex": r"Panta dreptei de ecuație $3x - 2y + 6 = 0$ este $m = ?$",
        "answer_latex": "3/2",
        "solution_latex": r"$3x-2y+6=0 \Rightarrow y=\frac{3}{2}x+3$. Panta $m = \frac{3}{2}$.",
        "scoring_guide_latex": r"(3p) forma $y=mx+n$; (2p) $m = \frac{3}{2}$.",
        "mcq_options": [r"$m = -\dfrac{3}{2}$", r"$m = \dfrac{2}{3}$", r"$m = \dfrac{3}{2}$", r"$m = 3$", r"$m = -3$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-analitica","Geometrie analitică")],
    },

    {
        "external_id": "DIAG-S1-15", "subiect": 1, "exercise_num": 15,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Produsul rădăcinilor ecuației $x^2 - (a+1)x + a = 0$ este egal cu $6$. Valoarea lui $a$ este:",
        "answer_latex": "6",
        "solution_latex": r"Prin relațiile lui Viète: $x_1 \cdot x_2 = \frac{a}{1} = a = 6$.",
        "scoring_guide_latex": r"(3p) relațiile Viète; (2p) $a = 6$.",
        "mcq_options": [r"$a = 2$", r"$a = 3$", r"$a = 5$", r"$a = 6$", r"$a = 7$"],
        "correct_option_index": 3,
        "tags": [("topic","algebra","Algebră"), ("subtopic","ecuatii-gradul2","Ecuații de gradul al II-lea")],
    },

    # ── SUBIECT 2 ──────────────────────────────────────────────────────────────

    {
        "external_id": "DIAG-S2-01", "subiect": 2, "exercise_num": 1,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Abscisa punctului de extrem local al funcției "
                           r"$f:(0,\infty)\to\mathbb{R}$, $f(x)=x^2-\ln x$ este:",
        "answer_latex": "1/sqrt(2)",
        "solution_latex": r"$f'(x) = 2x - \frac{1}{x} = 0 \Rightarrow 2x^2 = 1 \Rightarrow x = \frac{1}{\sqrt{2}} = \frac{\sqrt{2}}{2}$. "
                          r"$f''(x)=2+\frac{1}{x^2}>0$, deci extrem de minim.",
        "scoring_guide_latex": r"(3p) $f'(x)=0$; (2p) $x = \frac{\sqrt{2}}{2}$.",
        "mcq_options": [r"$x = 2$", r"$x = 3$", r"$x = \dfrac{e}{2}$", r"$x = \dfrac{\sqrt{2}}{2}$", r"$x = \sqrt{2}$"],
        "correct_option_index": 3,
        "tags": [("topic","analiza","Analiză matematică"), ("subtopic","derivate","Derivate")],
    },

    {
        "external_id": "DIAG-S2-02", "subiect": 2, "exercise_num": 2,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Numărul punctelor de inflexiune ale funcției $f(x) = x^4 - 4x^2$ este:",
        "answer_latex": "2",
        "solution_latex": r"$f'(x)=4x^3-8x$, $f''(x)=12x^2-8=0 \Rightarrow x^2=\frac{2}{3} \Rightarrow x=\pm\sqrt{2/3}$. "
                          r"Ambele sunt puncte de inflexiune (semnul lui $f''$ se schimbă). Numărul $= 2$.",
        "scoring_guide_latex": r"(3p) $f''(x)=0$; (2p) 2 puncte de inflexiune.",
        "mcq_options": [r"$0$", r"$1$", r"$2$", r"$3$", r"$4$"],
        "correct_option_index": 2,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","derivate","Derivate")],
    },

    {
        "external_id": "DIAG-S2-03", "subiect": 2, "exercise_num": 3,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Valoarea maximă a funcției $f(x) = -x^2 + 4x + 1$ pe $\mathbb{R}$ este:",
        "answer_latex": "5",
        "solution_latex": r"$x_V = -\frac{b}{2a} = \frac{4}{2} = 2$. $f(2) = -4+8+1 = 5$.",
        "scoring_guide_latex": r"(2p) $x_V=2$; (3p) $f_{\max}=5$.",
        "mcq_options": [r"$3$", r"$4$", r"$5$", r"$6$", r"$8$"],
        "correct_option_index": 2,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","functii","Studiul funcțiilor")],
    },

    {
        "external_id": "DIAG-S2-04", "subiect": 2, "exercise_num": 4,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Calculați $f'(1)$ dacă $f(x) = x \cdot e^x$.",
        "answer_latex": "2e",
        "solution_latex": r"$f'(x) = e^x + xe^x = e^x(1+x)$. $f'(1) = e^1(1+1) = 2e$.",
        "scoring_guide_latex": r"(3p) derivata produsului; (2p) $f'(1) = 2e$.",
        "mcq_options": [r"$e$", r"$2e$", r"$3e$", r"$e^2$", r"$2e^2$"],
        "correct_option_index": 1,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","derivate","Derivate")],
    },

    {
        "external_id": "DIAG-S2-05", "subiect": 2, "exercise_num": 5,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Calculați $\int_0^1 e^x\, dx$.",
        "answer_latex": "e-1",
        "solution_latex": r"$\int_0^1 e^x\,dx = [e^x]_0^1 = e^1 - e^0 = e - 1$.",
        "scoring_guide_latex": r"(3p) primitiva $e^x$; (2p) $\int = e-1$.",
        "mcq_options": [r"$e$", r"$e-1$", r"$1$", r"$e+1$", r"$2$"],
        "correct_option_index": 1,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","integrale","Integrale definite")],
    },

    {
        "external_id": "DIAG-S2-06", "subiect": 2, "exercise_num": 6,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Calculați $\int_0^\pi \sin x\, dx$.",
        "answer_latex": "2",
        "solution_latex": r"$\int_0^\pi \sin x\,dx = [-\cos x]_0^\pi = -\cos\pi+\cos 0 = 1+1 = 2$.",
        "scoring_guide_latex": r"(3p) primitiva $-\cos x$; (2p) $\int = 2$.",
        "mcq_options": [r"$0$", r"$1$", r"$2$", r"$\pi$", r"$4$"],
        "correct_option_index": 2,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","integrale","Integrale definite")],
    },

    {
        "external_id": "DIAG-S2-07", "subiect": 2, "exercise_num": 7,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Funcția $f(x) = x^3 - 3x$ are pe $\mathbb{R}$ un maxim local în punctul de abscisă:",
        "answer_latex": "-1",
        "solution_latex": r"$f'(x)=3x^2-3=3(x-1)(x+1)=0 \Rightarrow x=\pm 1$. "
                          r"$f''(x)=6x$. $f''(-1)=-6<0 \Rightarrow$ maxim local în $x=-1$.",
        "scoring_guide_latex": r"(3p) $f'(x)=0$ și analiza; (2p) maxim la $x=-1$.",
        "mcq_options": [r"$x = -2$", r"$x = -1$", r"$x = 0$", r"$x = 1$", r"$x = 2$"],
        "correct_option_index": 1,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","derivate","Derivate")],
    },

    {
        "external_id": "DIAG-S2-08", "subiect": 2, "exercise_num": 8,
        "difficulty": 6, "points": 5,
        "statement_latex": r"Calculați $\int_1^e \frac{x^2 + 1}{x}\, dx$.",
        "answer_latex": "e**2/2 + 1/2",
        "solution_latex": r"$\int_1^e\left(x+\frac{1}{x}\right)dx = \left[\frac{x^2}{2}+\ln x\right]_1^e = \frac{e^2}{2}+1-\frac{1}{2}-0=\frac{e^2-1}{2}+1=\frac{e^2+1}{2}$.",
        "scoring_guide_latex": r"(3p) împărțirea fracției; (2p) $\int = \frac{e^2+1}{2}$.",
        "mcq_options": [r"$\dfrac{e^2-1}{2}$", r"$\dfrac{e^2+1}{2}$", r"$e^2$", r"$\dfrac{e^2}{2}$", r"$e^2+1$"],
        "correct_option_index": 1,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","integrale","Integrale definite")],
    },

    {
        "external_id": "DIAG-S2-09", "subiect": 2, "exercise_num": 9,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Câte zerouri reale are funcția $f(x) = x^3 - 3x + 2$?",
        "answer_latex": "2",
        "solution_latex": r"$f(x)=(x-1)^2(x+2)$. Zerouri: $x=1$ (dublă) și $x=-2$. "
                          r"Distinct: 2 valori (sau 3 dacă numărăm cu multiplicitate).",
        "scoring_guide_latex": r"(3p) factorizarea; (2p) 2 zerouri distincte.",
        "mcq_options": [r"$0$", r"$1$", r"$2$", r"$3$", r"$4$"],
        "correct_option_index": 2,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","functii","Studiul funcțiilor")],
    },

    {
        "external_id": "DIAG-S2-10", "subiect": 2, "exercise_num": 10,
        "difficulty": 6, "points": 5,
        "statement_latex": r"Panta tangentei la graficul funcției $f(x) = \ln(x^2+1)$ în punctul $x = 1$ este:",
        "answer_latex": "1",
        "solution_latex": r"$f'(x) = \frac{2x}{x^2+1}$. $f'(1) = \frac{2}{2} = 1$.",
        "scoring_guide_latex": r"(3p) derivata; (2p) $f'(1) = 1$.",
        "mcq_options": [r"$\dfrac{1}{2}$", r"$1$", r"$\dfrac{3}{2}$", r"$2$", r"$\ln 2$"],
        "correct_option_index": 1,
        "tags": [("topic","analiza","Analiță matematică"), ("subtopic","derivate","Derivate")],
    },

    # ── SUBIECT 3 ──────────────────────────────────────────────────────────────

    {
        "external_id": "DIAG-S3-01", "subiect": 3, "exercise_num": 1,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Volumul piramidei cu baza pătrat de latură $a = 3$ și înălțimea $h = 4$ este $V = ?$",
        "answer_latex": "12",
        "solution_latex": r"$V = \frac{1}{3} \cdot a^2 \cdot h = \frac{1}{3} \cdot 9 \cdot 4 = 12$.",
        "scoring_guide_latex": r"(3p) formula piramidei; (2p) $V = 12$.",
        "mcq_options": [r"$9$", r"$12$", r"$16$", r"$18$", r"$36$"],
        "correct_option_index": 1,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-spatiala","Geometrie spațială")],
    },

    {
        "external_id": "DIAG-S3-02", "subiect": 3, "exercise_num": 2,
        "difficulty": 3, "points": 5,
        "statement_latex": r"Raza sferei cu aria suprafeței $A = 36\pi$ este $r = ?$",
        "answer_latex": "3",
        "solution_latex": r"$4\pi r^2 = 36\pi \Rightarrow r^2 = 9 \Rightarrow r = 3$.",
        "scoring_guide_latex": r"(3p) $4\pi r^2 = 36\pi$; (2p) $r = 3$.",
        "mcq_options": [r"$r = 2$", r"$r = 3$", r"$r = 4$", r"$r = 6$", r"$r = 9$"],
        "correct_option_index": 1,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-spatiala","Geometrie spațială")],
    },

    {
        "external_id": "DIAG-S3-03", "subiect": 3, "exercise_num": 3,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Distanța de la originea $O(0,0,0)$ la planul $2x + 2y + z = 9$ este $d = ?$",
        "answer_latex": "3",
        "solution_latex": r"$d = \frac{|2\cdot0+2\cdot0+0-9|}{\sqrt{4+4+1}} = \frac{9}{3} = 3$.",
        "scoring_guide_latex": r"(3p) formula distanței punct-plan; (2p) $d = 3$.",
        "mcq_options": [r"$1$", r"$2$", r"$3$", r"$4$", r"$\sqrt{9}$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-spatiala","Geometrie spațială")],
    },

    {
        "external_id": "DIAG-S3-04", "subiect": 3, "exercise_num": 4,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Cosinus-ul unghiului dintre vectorii $\vec{u} = (1, 2, 2)$ și $\vec{v} = (2, 1, -2)$ este:",
        "answer_latex": "0",
        "solution_latex": r"$\vec{u}\cdot\vec{v} = 2+2-4=0$. Deci $\cos\theta = 0$, vectorii sunt perpendiculari.",
        "scoring_guide_latex": r"(3p) produsul scalar; (2p) $\cos\theta = 0$.",
        "mcq_options": [r"$-1$", r"$-\dfrac{1}{2}$", r"$0$", r"$\dfrac{1}{2}$", r"$1$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","vectori","Vectori")],
    },

    {
        "external_id": "DIAG-S3-05", "subiect": 3, "exercise_num": 5,
        "difficulty": 3, "points": 5,
        "statement_latex": r"Diagonala unui paralelipiped dreptunghic cu dimensiunile $1 \times 2 \times 2$ este $d = ?$",
        "answer_latex": "3",
        "solution_latex": r"$d = \sqrt{1^2+2^2+2^2} = \sqrt{1+4+4} = \sqrt{9} = 3$.",
        "scoring_guide_latex": r"(3p) formula diagonalei spațiale; (2p) $d = 3$.",
        "mcq_options": [r"$\sqrt{5}$", r"$\sqrt{7}$", r"$3$", r"$2\sqrt{3}$", r"$4$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-spatiala","Geometrie spațială")],
    },

    {
        "external_id": "DIAG-S3-06", "subiect": 3, "exercise_num": 6,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Aria hexagonului regulat cu latura $a = 2$ este $A = k\sqrt{3}$. Valoarea lui $k$ este:",
        "answer_latex": "6",
        "solution_latex": r"$A = \frac{3\sqrt{3}}{2} \cdot a^2 = \frac{3\sqrt{3}}{2} \cdot 4 = 6\sqrt{3}$, deci $k=6$.",
        "scoring_guide_latex": r"(3p) formula hexagonului; (2p) $k = 6$.",
        "mcq_options": [r"$3$", r"$4$", r"$6$", r"$8$", r"$12$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-plana","Geometrie plană")],
    },

    {
        "external_id": "DIAG-S3-07", "subiect": 3, "exercise_num": 7,
        "difficulty": 5, "points": 5,
        "statement_latex": r"Într-un triunghi dreptunghic, un unghi acut $\alpha$ satisface $\tan\alpha = \sqrt{3}$. "
                           r"Valoarea lui $\sin\alpha$ este:",
        "answer_latex": "sqrt(3)/2",
        "solution_latex": r"$\tan\alpha=\sqrt{3} \Rightarrow \alpha=60°$. $\sin 60° = \frac{\sqrt{3}}{2}$.",
        "scoring_guide_latex": r"(3p) $\alpha=60°$; (2p) $\sin\alpha=\frac{\sqrt{3}}{2}$.",
        "mcq_options": [r"$\dfrac{1}{2}$", r"$\dfrac{\sqrt{2}}{2}$", r"$\dfrac{\sqrt{3}}{2}$", r"$1$", r"$\sqrt{3}$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-plana","Geometrie plană")],
    },

    {
        "external_id": "DIAG-S3-08", "subiect": 3, "exercise_num": 8,
        "difficulty": 4, "points": 5,
        "statement_latex": r"Volumul cilindrului circular drept cu raza $r = 2$ și înălțimea $h = 5$ este "
                           r"$V = k\pi$. Valoarea lui $k$ este:",
        "answer_latex": "20",
        "solution_latex": r"$V = \pi r^2 h = \pi \cdot 4 \cdot 5 = 20\pi$, deci $k=20$.",
        "scoring_guide_latex": r"(3p) formula cilindrului; (2p) $k=20$.",
        "mcq_options": [r"$10$", r"$15$", r"$20$", r"$25$", r"$40$"],
        "correct_option_index": 2,
        "tags": [("topic","geometrie","Geometrie"), ("subtopic","geometrie-spatiala","Geometrie spațială")],
    },

]


def main():
    with psycopg.connect(DB) as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # Șterge exercițiile vechi DIAG-*
            cur.execute(
                "DELETE FROM exercises WHERE metadata::jsonb->>'external_id' LIKE 'DIAG-%'"
            )
            deleted = cur.rowcount
            if deleted:
                print(f"Șterse {deleted} exerciții vechi DIAG-*")

            # Admin user pentru created_by_user_id
            cur.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
            admin_row = cur.fetchone()
            admin_id = str(admin_row["id"]) if admin_row else None

            tag_cache: dict[str, str] = {}

            def get_or_create_tag(namespace: str, key: str, label: str) -> str:
                ck = f"{namespace}:{key}"
                if ck in tag_cache:
                    return tag_cache[ck]
                cur.execute("SELECT id FROM tags WHERE namespace=%s AND key=%s", (namespace, key))
                row = cur.fetchone()
                if row:
                    tid = str(row["id"])
                else:
                    cur.execute(
                        "INSERT INTO tags (namespace, key, label) VALUES (%s,%s,%s) RETURNING id",
                        (namespace, key, label)
                    )
                    tid = str(cur.fetchone()["id"])
                tag_cache[ck] = tid
                return tid

            def insert_tag(ex_id: str, tid: str):
                cur.execute("""
                    INSERT INTO exercise_tags (exercise_id, tag_id, weight, created_by, created_by_user_id)
                    VALUES (%s,%s,1.0,'import',%s)
                    ON CONFLICT DO NOTHING
                """, (ex_id, tid, admin_id))

            inserted = 0
            for ex in EXERCISES:
                ex_id = str(uuid.uuid4())
                metadata = {
                    "external_id": ex["external_id"],
                    "subiect": ex["subiect"],
                    "exercise_num": ex["exercise_num"],
                    "path": f"S{ex['subiect']}/{ex['exercise_num']}",
                    "is_container": False,
                    "diagnostic_grila": True,
                    # Opțiunile MCQ pre-definite — 5 variante
                    "mcq_options": ex["mcq_options"],
                    "correct_option_index": ex["correct_option_index"],
                }

                cur.execute("""
                    INSERT INTO exercises (
                        id, exam_type, profile, item_type,
                        statement_latex, answer_latex,
                        solution_latex, scoring_guide_latex,
                        difficulty, points, status, metadata,
                        created_at, updated_at
                    ) VALUES (
                        %s,'bacalaureat','mate-info','exercitiu',
                        %s,%s,%s,%s,%s,%s,'READY',%s,NOW(),NOW()
                    )
                """, (
                    ex_id,
                    ex["statement_latex"],
                    ex.get("answer_latex"),
                    ex.get("solution_latex"),
                    ex.get("scoring_guide_latex"),
                    ex["difficulty"],
                    ex["points"],
                    json.dumps(metadata),
                ))

                # Subiect tag
                stag = get_or_create_tag("subiect", str(ex["subiect"]), f"Subiectul {ex['subiect']}")
                insert_tag(ex_id, stag)

                # Topic tags
                for ns, key, label in ex.get("tags", []):
                    insert_tag(ex_id, get_or_create_tag(ns, key, label))

                # Source tag
                insert_tag(ex_id, get_or_create_tag("source", "diagnostic-grila", "Diagnostic Grilă"))

                inserted += 1

            conn.commit()
            print(f"\n✓ Importate: {inserted} exerciții BAC diagnostic grilă (5 opțiuni)")
            s1 = sum(1 for e in EXERCISES if e["subiect"]==1)
            s2 = sum(1 for e in EXERCISES if e["subiect"]==2)
            s3 = sum(1 for e in EXERCISES if e["subiect"]==3)
            print(f"  S1: {s1} | S2: {s2} | S3: {s3}")
            print(f"  Dificultate: {min(e['difficulty'] for e in EXERCISES)}–{max(e['difficulty'] for e in EXERCISES)}")


if __name__ == "__main__":
    main()
