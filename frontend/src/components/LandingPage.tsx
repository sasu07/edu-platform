import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  Check,
  GraduationCap,
  MessageCircle,
  Minus,
  Sparkles,
  Target,
  Trophy,
  Users,
  WandSparkles,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { BRAND_LOGO_URL } from '../brand';
import './LandingPage.css';

// ⚠️ Numărul de WhatsApp (format internațional, fără +, spații sau 0 inițial).
const WHATSAPP_URL =
  'https://wa.me/40745960848?text=Salut!%20Vreau%20s%C4%83%20aflu%20ce%20plan%20mi%20se%20potrive%C8%99te.';

type Feature = { icon: LucideIcon; title: string; description: string };

const FEATURES: Feature[] = [
  {
    icon: BookOpenCheck,
    title: 'Variante oficiale și exerciții',
    description:
      'Toate subiectele oficiale și exerciții organizate pe profil, subiect, capitol și dificultate — fără căutări.',
  },
  {
    icon: WandSparkles,
    title: 'Generezi variante noi',
    description:
      'Un nou antrenament în câteva secunde: variante echilibrate pe care le rezolvi în platformă sau pe hârtie.',
  },
  {
    icon: BarChart3,
    title: 'Progres vizibil',
    description:
      'Testare inițială, plan personalizat, tablou de bord cu puncte XP și jurnalul greșelilor — legate de activitatea ta.',
  },
  {
    icon: MessageCircle,
    title: 'Ajutor când contează',
    description:
      'Indicii pas cu pas, verificare automată și ajutor de la profesor — inclusiv ședințe live, în funcție de plan.',
  },
  {
    icon: Trophy,
    title: 'Motivație constantă',
    description:
      'Câștigi XP, îți păstrezi seria de studiu și intri în simulările și provocările noastre alături de colegi.',
  },
  {
    icon: Target,
    title: 'Totul într-un singur loc',
    description:
      'Nu o bibliotecă de exerciții, ci un sistem de pregătire în care fiecare pas actualizează traseul tău.',
  },
];

const AUDIENCES = [
  {
    icon: GraduationCap,
    label: 'Elevi',
    title: 'Pregătire pentru examen, fără haos',
    points: ['Sesiuni de lucru ghidate', 'Răspuns verificat automat', 'Calendar și Liga BAC'],
  },
  {
    icon: Users,
    label: 'Părinți',
    title: 'Vezi progresul copilului',
    points: ['Calendar comun', 'Rezumat de activitate', 'Analiză lunară'],
  },
  {
    icon: BookOpenCheck,
    label: 'Profesori',
    title: 'Îți pregătești elevii de la clasă',
    points: ['Clase și leaderboard', 'Generator de variante', 'Solicitări prioritizate'],
  },
];

type CellValue = boolean | string;

const PLANS = [
  { key: 'free', name: 'Free', price: 'Gratis', suffix: '', cta: 'Creează cont', to: '/register', featured: false },
  { key: 'start', name: 'Start', price: '100 lei', suffix: '/ lună', cta: 'Scrie-ne', to: WHATSAPP_URL, featured: false },
  { key: 'avansat', name: 'Avansat', price: '250 lei', suffix: '/ lună', cta: 'Scrie-ne', to: WHATSAPP_URL, featured: true },
  { key: 'pro', name: 'Pro', price: '700 lei', suffix: '/ lună', cta: 'Scrie-ne', to: WHATSAPP_URL, featured: false },
];

const COMPARE: { label: string; values: [CellValue, CellValue, CellValue, CellValue] }[] = [
  { label: 'Acces la toate variantele oficiale', values: [true, true, true, true] },
  { label: 'Generează variante noi', values: ['3 / lună', '10 / lună', 'Nelimitat', 'Nelimitat'] },
  { label: 'Testare inițială și feedback (elev și părinte)', values: [false, true, true, true] },
  { label: 'Primești ajutor 24/7', values: [false, true, true, true] },
  { label: 'Acces la ședințele LIVE', values: [false, false, true, true] },
  { label: 'Plan personalizat pentru pregătirea ta', values: [false, false, true, true] },
  { label: 'Tablou de bord cu puncte XP', values: [false, false, true, true] },
  { label: 'Prioritate la întrebări', values: [false, false, true, true] },
  { label: 'Participi la simulările noastre', values: [false, false, true, true] },
  { label: 'Analiză lunară pentru părinte și elev', values: [false, false, false, true] },
  { label: 'Ședință individuală săptămânală', values: [false, false, false, true] },
  { label: 'Mentor personal dedicat', values: [false, false, false, true] },
];

function Cell({ value }: { value: CellValue }) {
  if (value === true) return <span className="lp-cell lp-cell-yes"><Check size={16} /></span>;
  if (value === false) return <span className="lp-cell lp-cell-no"><Minus size={15} /></span>;
  return <span className="lp-cell lp-cell-text">{value}</span>;
}

export default function LandingPage() {
  const { user } = useAuth();
  const primaryTo = user ? '/app' : '/register';
  const primaryLabel = user ? 'Deschide platforma' : 'Hai să începem';

  return (
    <div className="lp">
      {/* NAV */}
      <nav className="lp-nav" aria-label="Navigație principală">
        <div className="lp-nav-inner">
          <Link to="/" className="lp-brand" aria-label="EtoX Academy - Acasă">
            <span className="lp-brand-mark"><img src={BRAND_LOGO_URL} alt="" /></span>
            <span className="lp-brand-copy"><strong>EtoX</strong><small>Academy</small></span>
          </Link>
          <div className="lp-nav-links">
            <a href="#despre">Despre noi</a>
            <a href="#ce-facem">Ce facem</a>
            <a href="#cum-incep">Cum încep</a>
            <a href="#pentru-cine">Pentru cine</a>
            <a href="#planuri">Planuri</a>
          </div>
          <div className="lp-nav-actions">
            {!user && <Link to="/login" className="lp-login-link">Intră în cont</Link>}
            <Link to={primaryTo} className="lp-btn lp-btn-primary lp-btn-sm">{primaryLabel}</Link>
          </div>
        </div>
      </nav>

      <main>
        {/* HERO */}
        <section className="lp-hero">
          <div className="lp-hero-inner">
            <span className="lp-pill"><Sparkles size={14} /> Pregătire pentru BAC la matematică</span>
            <h1>Totul începe cu un plan. <span>Noi îl construim împreună cu tine.</span></h1>
            <p>
              Exerciții autentice, un plan care se adaptează progresului tău și ajutor exact atunci când ai nevoie.
              Totul într-un singur loc, învățat simplu.
            </p>
            <div className="lp-hero-actions">
              <Link to={primaryTo} className="lp-btn lp-btn-primary lp-btn-lg">{primaryLabel}<ArrowRight size={18} /></Link>
              <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-ghost lp-btn-lg">
                <MessageCircle size={18} /> Scrie-ne pe WhatsApp
              </a>
            </div>
            <div className="lp-hero-trust">Elev, părinte și profesor — pe același traseu de progres.</div>
          </div>
        </section>

        {/* CE FACEM */}
        <section className="lp-section" id="ce-facem">
          <div className="lp-head">
            <span className="lp-kicker">Ce facem</span>
            <h2>Totul este organizat și eficient</h2>
            <p>Fiecare exercițiu rezolvat actualizează traseul, calendarul, statisticile și pasul următor.</p>
          </div>
          <div className="lp-feature-grid">
            {FEATURES.map(({ icon: Icon, ...f }) => (
              <article className="lp-feature" key={f.title}>
                <span className="lp-feature-icon"><Icon size={20} /></span>
                <h3>{f.title}</h3>
                <p>{f.description}</p>
              </article>
            ))}
          </div>
        </section>

        {/* DESPRE NOI */}
        <section className="lp-section lp-about" id="despre">
          <div className="lp-about-inner">
            <span className="lp-kicker">Despre noi</span>
            <h2>Suntem o echipă tânără, dar cu experiență în educație.</h2>
            <p>
              Ne dorim să oferim mai departe tot ce am învățat în anii trecuți, astfel încât elevilor noștri să le
              fie mai ușor să își atingă obiectivele. Știm cum e și înțelegem.
            </p>
            <p>
              Oferim totul într-un singur loc, ca fiecare elev să-și poată construi propriul ritm și să devină ceea
              ce își dorește.
            </p>
            <Link to={primaryTo} className="lp-btn lp-btn-primary lp-btn-lg">Hai să începem<ArrowRight size={18} /></Link>
          </div>
        </section>

        {/* CUM ȘI DE UNDE ÎNCEP */}
        <section className="lp-section" id="cum-incep">
          <div className="lp-head">
            <span className="lp-kicker">Primul pas</span>
            <h2>Cum și de unde încep?</h2>
            <p>Auzim întrebarea asta de la toți elevii și părinții. Ai două variante — alege ce ți se potrivește.</p>
          </div>
          <div className="lp-start-grid">
            <article className="lp-start-card">
              <span className="lp-start-num">1</span>
              <h3>Vrei să discutăm întâi</h3>
              <p>Scrie-ne pe WhatsApp ca să stabilim o convorbire și să găsim împreună planul care ți se potrivește cel mai bine.</p>
              <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-whatsapp">
                <MessageCircle size={18} /> Scrie-ne pe WhatsApp
              </a>
            </article>
            <article className="lp-start-card">
              <span className="lp-start-num">2</span>
              <h3>Ești deja hotărât</h3>
              <p>Îți creezi contul, alegi direct nivelul pe care îl vrei și începi pregătirea. Bine ai venit în echipă!</p>
              <Link to={primaryTo} className="lp-btn lp-btn-primary">{user ? 'Deschide platforma' : 'Creează cont'}<ArrowRight size={17} /></Link>
            </article>
          </div>
        </section>

        {/* PENTRU CINE */}
        <section className="lp-section" id="pentru-cine">
          <div className="lp-head">
            <span className="lp-kicker">Pentru cine este EtoX</span>
            <h2>Pentru elevi, părinți și profesori</h2>
            <p>Aceleași date, prezentate diferit pentru fiecare. Mai puține mesaje pierdute, mai multă continuitate.</p>
          </div>
          <div className="lp-audience-grid">
            {AUDIENCES.map(({ icon: Icon, ...a }) => (
              <article className="lp-audience" key={a.label}>
                <div className="lp-audience-head"><span className="lp-feature-icon"><Icon size={20} /></span><small>{a.label}</small></div>
                <h3>{a.title}</h3>
                <ul>{a.points.map((p) => <li key={p}><Check size={15} />{p}</li>)}</ul>
              </article>
            ))}
          </div>
        </section>

        {/* PLANURI */}
        <section className="lp-section" id="planuri">
          <div className="lp-head">
            <span className="lp-kicker">Planuri de abonament</span>
            <h2>Începi gratuit. Alegi nivelul de care ai nevoie.</h2>
            <p>Poți începe oricând cu planul gratuit. Pentru planurile plătite, scrie-ne și le activăm împreună.</p>
          </div>
          <div className="lp-table-wrap">
            <div className="lp-table" role="table" aria-label="Comparație planuri">
              <div className="lp-table-head" role="row">
                <div className="lp-th-corner" role="columnheader">Ce include</div>
                {PLANS.map((plan) => (
                  <div key={plan.key} className={`lp-th ${plan.featured ? 'is-featured' : ''}`} role="columnheader">
                    {plan.featured && <span className="lp-th-tag">Recomandat</span>}
                    <strong>{plan.name}</strong>
                    <div className="lp-th-price"><b>{plan.price}</b>{plan.suffix && <span>{plan.suffix}</span>}</div>
                    {plan.to.startsWith('http')
                      ? <a href={plan.to} target="_blank" rel="noopener noreferrer" className="lp-th-cta">{plan.cta}</a>
                      : <Link to={user ? '/app' : plan.to} className="lp-th-cta">{user ? 'Deschide' : plan.cta}</Link>}
                  </div>
                ))}
              </div>
              {COMPARE.map((row) => (
                <div className="lp-tr" role="row" key={row.label}>
                  <div className="lp-td-label" role="cell">{row.label}</div>
                  {row.values.map((v, i) => (
                    <div className={`lp-td ${PLANS[i].featured ? 'is-featured' : ''}`} role="cell" key={i}><Cell value={v} /></div>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <p className="lp-note"><Sparkles size={15} /> Nu ai nevoie de card pentru contul gratuit. Poți schimba planul oricând.</p>
        </section>

        {/* FINAL CTA */}
        <section className="lp-cta-band">
          <h2>Începe și tu să exersezi.</h2>
          <p>Contul gratuit îți oferă suficient cât să vezi dacă EtoX este potrivit pentru tine.</p>
          <div className="lp-hero-actions">
            <Link to={primaryTo} className="lp-btn lp-btn-primary lp-btn-lg">{primaryLabel}<ArrowRight size={18} /></Link>
            <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-ghost lp-btn-lg">
              <MessageCircle size={18} /> Scrie-ne pe WhatsApp
            </a>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-footer-brand">
            <Link to="/" className="lp-brand"><span className="lp-brand-mark"><img src={BRAND_LOGO_URL} alt="" /></span><span className="lp-brand-copy"><strong>EtoX</strong><small>Academy</small></span></Link>
            <p>Pregătire BAC la matematică, construită în jurul progresului real.</p>
          </div>
          <div className="lp-footer-col"><strong>Platforma</strong><a href="#ce-facem">Ce facem</a><a href="#cum-incep">Cum încep</a><a href="#planuri">Planuri</a></div>
          <div className="lp-footer-col"><strong>Cont</strong><Link to="/register">Înregistrare</Link><Link to="/login">Autentificare</Link><Link to="/app">Platforma</Link></div>
          <div className="lp-footer-col"><strong>Contact</strong><a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer">Scrie-ne pe WhatsApp</a></div>
        </div>
        <div className="lp-footer-bottom">© 2026 EtoX Academy. Toate drepturile rezervate.</div>
      </footer>
    </div>
  );
}
