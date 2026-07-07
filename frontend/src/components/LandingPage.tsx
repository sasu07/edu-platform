import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import './LandingPage.css';

const FEATURES = [
  {
    icon: '📚',
    color: 'blue',
    title: 'Bază de exerciții autentice',
    desc: 'Mii de exerciții din subiecte reale de BAC, organizate pe subiect, domeniu și nivel de dificultate. Filtrează exact ce îți trebuie.',
  },
  {
    icon: '⚡',
    color: 'amber',
    title: 'Generator automat de variante',
    desc: 'Generează variante complete tip BAC în câteva secunde — Subiectul I, II și III, echilibrate și personalizate.',
  },
  {
    icon: '📄',
    color: 'green',
    title: 'Export PDF profesional',
    desc: 'Descarcă subiectul, rezolvarea detaliată și baremul de corectare în format PDF, gata de tipărit.',
  },
  {
    icon: '✍️',
    color: 'purple',
    title: 'Ajutor de la profesori',
    desc: 'Ești blocat la un exercițiu? Semnalează-l și primești o rezolvare scrisă, un clip video sau o sesiune live.',
  },
  {
    icon: '🎙️',
    color: 'red',
    title: 'Sesiuni live & video',
    desc: 'Conectează-te direct cu un profesor pentru o sesiune online 1-la-1 sau cere un clip explicativ personalizat.',
  },
  {
    icon: '🎮',
    color: 'indigo',
    title: 'Gamificare & motivare',
    desc: 'Câștigă XP, urci în ligi și ții streak-ul activ. Competiția sănătoasă te ține motivat zi de zi.',
  },
];

const STEPS = [
  {
    num: '01',
    icon: '👤',
    title: 'Creează un cont gratuit',
    desc: 'Înregistrarea durează 30 de secunde. Niciun card de credit necesar.',
  },
  {
    num: '02',
    icon: '⚡',
    title: 'Generează exerciții sau variante BAC',
    desc: 'Alege filtrele dorite și lasă platforma să construiască setul de exerciții sau varianta completă.',
  },
  {
    num: '03',
    icon: '🎯',
    title: 'Exersează și cere ajutor',
    desc: 'Rezolvă exercițiile în ritmul tău. Dacă ești blocat, un profesor îți răspunde în câteva ore.',
  },
];

const PLANS = [
  {
    key: 'free',
    name: 'Gratuit',
    price: '0 lei',
    features: [
      '3 generări de exerciții / lună',
      '1 variantă BAC / lună',
      'Acces la biblioteca de exerciții',
      'Vizualizare soluții disponibile',
    ],
    cta: 'Începe gratuit',
    ctaTo: '/register',
    highlight: false,
  },
  {
    key: 'premium_help',
    name: 'Premium Help',
    price: 'Contact',
    features: [
      'Generare nelimitată exerciții',
      'Cereri de ajutor către profesori',
      'Rezolvare scrisă sau video',
      'Sesiuni live pe Zoom',
    ],
    cta: 'Activează',
    ctaTo: '/login',
    highlight: false,
  },
  {
    key: 'premium_pdf',
    name: 'Premium PDF',
    price: 'Contact',
    features: [
      'Generare nelimitată exerciții',
      'Variante BAC nelimitate / lună',
      'Export PDF — subiect, rezolvare, barem',
      'Tipărești și studiezi offline',
    ],
    cta: 'Activează',
    ctaTo: '/login',
    highlight: false,
  },
  {
    key: 'premium_gen',
    name: 'Premium Gen',
    price: 'Contact',
    badge: '★ Recomandat',
    features: [
      'Generare nelimitată exerciții',
      'Variante BAC nelimitate / lună',
      'Export PDF — subiect, rezolvare, barem',
      'Acces complet la filtru avansat',
    ],
    cta: 'Activează',
    ctaTo: '/login',
    highlight: true,
  },
  {
    key: 'premium',
    name: 'Premium Full',
    price: 'Contact',
    features: [
      'Tot ce include Premium Gen',
      'Cereri de ajutor nelimitate',
      'Sesiuni live + video personalizate',
      'Prioritate la răspunsuri',
    ],
    cta: 'Activează',
    ctaTo: '/login',
    highlight: false,
  },
];

const PERSONAS = [
  {
    emoji: '🎓',
    color: 'blue',
    title: 'Elev la liceu',
    desc: 'Pregătești BAC-ul și vrei să exersezi cu exerciții reale, să generezi variante de antrenament și să primești ajutor când te blochezi.',
  },
  {
    emoji: '🏫',
    color: 'green',
    title: 'Profesor de școală',
    desc: 'Pregătești elevi pentru BAC și vrei să generezi variante personalizate pentru ore sau simulări, pe care să le și tipărești rapid.',
  },
  {
    emoji: '👨‍💻',
    color: 'purple',
    title: 'Profesor platformă',
    desc: 'Răspunzi la cererile de ajutor ale elevilor, trimiți rezolvări scrise, înregistrezi clipuri sau organizezi sesiuni live.',
  },
];

const PARENT_FEATURES = [
  { icon: '🔔', text: 'Notificări automate când este programată o sesiune live' },
  { icon: '📊', text: 'Rapoarte de progres — exerciții rezolvate, XP acumulat, streak' },
  { icon: '📅', text: 'Calendarul sesiunilor viitoare cu profesorii' },
  { icon: '✅', text: 'Confirmare că exercițiile au fost verificate de profesor' },
];

function BacCountdown() {
  const bacDate = new Date('2026-07-01');
  const today = new Date();
  const daysLeft = Math.max(0, Math.ceil((bacDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));
  return (
    <div className="lp-announcement">
      <span className="lp-ann-pulse" />
      <span>
        🔥 BAC 2026: mai sunt <strong>{daysLeft} de zile</strong> — nu lăsa pregătirea pe ultima sută de metri!
      </span>
      <Link to="/register" className="lp-ann-cta">Începe gratuit →</Link>
    </div>
  );
}

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="lp">

      {/* ── Announcement bar ── */}
      <BacCountdown />

      {/* ── Navbar ── */}
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <div className="lp-nav-brand">
            <img src="/logo_etox.png" alt="EtoX Academy" className="lp-nav-logo" />
            <div>
              <div className="lp-nav-name">EtoX Platform</div>
              <div className="lp-nav-tagline">Pregătire BAC</div>
            </div>
          </div>

          <div className="lp-nav-links">
            <a href="#features" className="lp-nav-link">Funcții</a>
            <a href="#how" className="lp-nav-link">Cum funcționează</a>
            <a href="#parents" className="lp-nav-link">Părinți</a>
            <a href="#plans" className="lp-nav-link">Planuri</a>
          </div>

          <div className="lp-nav-actions">
            {user ? (
              <Link to="/app" className="lp-btn lp-btn-primary">
                Intră în platformă →
              </Link>
            ) : (
              <>
                <Link to="/login" className="lp-btn lp-btn-ghost">
                  Intră în cont
                </Link>
                <Link to="/register" className="lp-btn lp-btn-primary">
                  Înregistrare gratuită
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="lp-hero">
        <div className="lp-hero-blob lp-hero-blob-1" aria-hidden />
        <div className="lp-hero-blob lp-hero-blob-2" aria-hidden />
        <div className="lp-hero-inner">
          <div className="lp-hero-content">
            <div className="lp-hero-badge">
              <span className="lp-badge-dot" />
              Platforma nr. 1 pentru pregătire BAC Matematică
            </div>

            <h1 className="lp-hero-title">
              Exerciții BAC autentice.<br />
              <span className="lp-hero-accent">Variante generate automat.</span><br />
              Profesori la un click distanță.
            </h1>

            <p className="lp-hero-sub">
              EtoX Platform reunește mii de exerciții din subiecte reale de bacalaureat,
              un generator inteligent de variante și profesori dedicați care îți răspund
              atunci când ai nevoie.
            </p>

            <div className="lp-hero-cta">
              {user ? (
                <Link to="/app" className="lp-btn lp-btn-primary lp-btn-lg">
                  Deschide platforma →
                </Link>
              ) : (
                <>
                  <Link to="/register" className="lp-btn lp-btn-primary lp-btn-lg">
                    Începe gratuit →
                  </Link>
                  <Link to="/login" className="lp-btn lp-btn-outline lp-btn-lg">
                    Am deja cont
                  </Link>
                </>
              )}
            </div>

            <div className="lp-hero-stats">
              <div className="lp-stat">
                <div className="lp-stat-val">2 500+</div>
                <div className="lp-stat-key">Exerciții în baza de date</div>
              </div>
              <div className="lp-stat-divider" />
              <div className="lp-stat">
                <div className="lp-stat-val">100%</div>
                <div className="lp-stat-key">Din subiecte reale BAC</div>
              </div>
              <div className="lp-stat-divider" />
              <div className="lp-stat">
                <div className="lp-stat-val">3 tipuri</div>
                <div className="lp-stat-key">De ajutor personalizat</div>
              </div>
            </div>
          </div>

          <div className="lp-hero-visual" aria-hidden>
            <div className="lp-mockup">
              <div className="lp-mockup-bar">
                <span /><span /><span />
                <div className="lp-mockup-url">etox.academy/app</div>
              </div>
              <div className="lp-mockup-body">
                {/* XP bar */}
                <div className="lp-mockup-xp">
                  <div className="lp-mockup-xp-label">
                    <span>🏆 Liga Bronz</span>
                    <span>1 240 XP</span>
                  </div>
                  <div className="lp-mockup-xp-track">
                    <div className="lp-mockup-xp-fill" style={{ width: '62%' }} />
                  </div>
                </div>

                <div className="lp-mockup-chip lp-chip-blue">Subiectul I</div>
                <div className="lp-mockup-ex">
                  <div className="lp-mockup-label">Exercițiu 3</div>
                  <div className="lp-mockup-text">Fie funcția <em>f : ℝ → ℝ</em>, f(x) = x² + 2x − 3. Determinați intervalele de monotonie ale lui <em>f</em>.</div>
                  <div className="lp-mockup-actions">
                    <div className="lp-mockup-btn lp-mockup-btn-done">✓ Rezolvat</div>
                    <div className="lp-mockup-btn lp-mockup-btn-help">Ajutor</div>
                  </div>
                </div>

                <div className="lp-mockup-chip lp-chip-purple">Subiectul II</div>
                <div className="lp-mockup-ex lp-mockup-ex-sm">
                  <div className="lp-mockup-label">Problemă cu subpuncte</div>
                  <div className="lp-mockup-text">Fie triunghiul ABC cu AB = 6 cm, BC = 8 cm...</div>
                  <div className="lp-mockup-pending">⏳ În verificare de profesor</div>
                </div>

                <div className="lp-mockup-footer">
                  <div className="lp-mockup-generate">⚡ Generează variantă BAC completă</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Trust strip ── */}
      <div className="lp-trust">
        <div className="lp-trust-inner">
          <span className="lp-trust-label">Recomandat de profesori din</span>
          <div className="lp-trust-items">
            <span className="lp-trust-item">🏫 Colegii Naționale</span>
            <span className="lp-trust-sep">·</span>
            <span className="lp-trust-item">📐 Licee de Matematică-Informatică</span>
            <span className="lp-trust-sep">·</span>
            <span className="lp-trust-item">🎓 Centre de meditații</span>
          </div>
        </div>
      </div>

      {/* ── Features ── */}
      <section className="lp-section lp-section-light" id="features">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-section-label">Ce oferă platforma</div>
            <h2 className="lp-section-title">Tot ce ai nevoie pentru BAC, într-un singur loc</h2>
            <p className="lp-section-sub">
              De la exerciții filtrate pe profil și dificultate, până la variante complete
              și profesori care îți explică pas cu pas.
            </p>
          </div>

          <div className="lp-features-grid">
            {FEATURES.map((f) => (
              <div key={f.title} className={`lp-feature-card lp-feature-${f.color}`}>
                <div className="lp-feature-icon-wrap">
                  <span className="lp-feature-icon">{f.icon}</span>
                </div>
                <div className="lp-feature-title">{f.title}</div>
                <div className="lp-feature-desc">{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="lp-section" id="how">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-section-label">Simplu de folosit</div>
            <h2 className="lp-section-title">Trei pași și ești gata de exersat</h2>
          </div>

          <div className="lp-steps">
            {STEPS.map((s, i) => (
              <div key={s.num} className="lp-step">
                {i < STEPS.length - 1 && <div className="lp-step-connector" aria-hidden />}
                <div className="lp-step-num">
                  <span className="lp-step-icon">{s.icon}</span>
                </div>
                <div className="lp-step-content">
                  <div className="lp-step-num-label">{s.num}</div>
                  <div className="lp-step-title">{s.title}</div>
                  <div className="lp-step-desc">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── For who ── */}
      <section className="lp-section lp-section-light">
        <div className="lp-section-inner">
          <div className="lp-section-head">
            <div className="lp-section-label">Pentru cine este EtoX</div>
            <h2 className="lp-section-title">Construit pentru elevi și profesori</h2>
          </div>

          <div className="lp-personas">
            {PERSONAS.map((p) => (
              <div key={p.title} className={`lp-persona lp-persona-${p.color}`}>
                <div className="lp-persona-emoji">{p.emoji}</div>
                <div className="lp-persona-title">{p.title}</div>
                <div className="lp-persona-desc">{p.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Parents section ── */}
      <section className="lp-section lp-section-parent" id="parents">
        <div className="lp-section-inner lp-parent-grid">
          <div className="lp-parent-content">
            <div className="lp-section-label lp-label-parent">Pentru părinți</div>
            <h2 className="lp-section-title lp-title-dark">
              Fiți mereu la curent cu progresul copilului
            </h2>
            <p className="lp-section-sub lp-sub-dark">
              Nu trebuie să întrebați "ai studiat azi?" — EtoX vă trimite actualizări
              automate și vă arată exact unde se află copilul în pregătire.
            </p>
            <ul className="lp-parent-list">
              {PARENT_FEATURES.map((pf) => (
                <li key={pf.text} className="lp-parent-item">
                  <span className="lp-parent-icon">{pf.icon}</span>
                  <span>{pf.text}</span>
                </li>
              ))}
            </ul>
            <Link to="/register" className="lp-btn lp-btn-primary" style={{ marginTop: '28px', alignSelf: 'flex-start' }}>
              Creez cont pentru copilul meu →
            </Link>
          </div>

          <div className="lp-parent-visual" aria-hidden>
            <div className="lp-notif-mockup">
              <div className="lp-notif-header">
                <span className="lp-notif-app-icon">📱</span>
                <span>EtoX · Notificări</span>
              </div>
              <div className="lp-notif-item lp-notif-new">
                <div className="lp-notif-dot" />
                <div>
                  <div className="lp-notif-title">Sesiune live programată</div>
                  <div className="lp-notif-body">Prof. Ionescu a programat o sesiune pentru <strong>mâine, 18:00</strong> — Limite și continuitate</div>
                  <div className="lp-notif-time">acum 2 minute</div>
                </div>
              </div>
              <div className="lp-notif-item">
                <div>
                  <div className="lp-notif-title">Exercițiu verificat ✅</div>
                  <div className="lp-notif-body">Andrei a primit OK de la profesor pentru exercițiul de la Geometrie în spațiu</div>
                  <div className="lp-notif-time">acum 1 oră</div>
                </div>
              </div>
              <div className="lp-notif-item">
                <div>
                  <div className="lp-notif-title">Raport săptămânal 📊</div>
                  <div className="lp-notif-body">Andrei a rezolvat <strong>14 exerciții</strong> săptămâna aceasta și a câștigat <strong>320 XP</strong></div>
                  <div className="lp-notif-time">ieri, 20:00</div>
                </div>
              </div>
              <div className="lp-notif-progress">
                <div className="lp-notif-prog-label">Progres BAC <span>62%</span></div>
                <div className="lp-notif-prog-track">
                  <div className="lp-notif-prog-fill" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Plans ── */}
      <section className="lp-section lp-section-dark" id="plans">
        <div className="lp-section-inner">
          <div className="lp-section-head lp-head-dark">
            <div className="lp-section-label lp-label-light">Planuri de abonament</div>
            <h2 className="lp-section-title lp-title-light">Alege planul potrivit pentru tine</h2>
            <p className="lp-section-sub lp-sub-light">
              Începe gratuit și extinde accesul pe măsură ce ai nevoie.
            </p>
          </div>

          <div className="lp-plans-grid">
            {PLANS.map((plan) => (
              <div key={plan.key} className={`lp-plan ${plan.highlight ? 'lp-plan-highlight' : ''}`}>
                {plan.badge && <div className="lp-plan-badge">{plan.badge}</div>}
                <div className="lp-plan-name">{plan.name}</div>
                <div className="lp-plan-price">{plan.price}</div>
                <ul className="lp-plan-features">
                  {plan.features.map((feat) => (
                    <li key={feat}>
                      <span className="lp-check">✓</span> {feat}
                    </li>
                  ))}
                </ul>
                <Link
                  to={plan.ctaTo}
                  className={`lp-plan-cta ${plan.highlight ? 'lp-plan-cta-highlight' : ''}`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>

          <p className="lp-plans-note">
            Planurile Premium se activează de către un administrator. Contactează-ne pentru detalii.
          </p>
        </div>
      </section>

      {/* ── CTA banner ── */}
      <section className="lp-cta-banner">
        <div className="lp-cta-banner-inner">
          <img src="/logo_etox.png" alt="EtoX" className="lp-cta-logo" />
          <div>
            <h2 className="lp-cta-title">Pregătit să dai BAC-ul cu încredere?</h2>
            <p className="lp-cta-sub">Creează un cont gratuit și începe să exersezi chiar acum.</p>
          </div>
          <Link to={user ? '/app' : '/register'} className="lp-btn lp-btn-primary lp-btn-lg">
            {user ? 'Deschide platforma' : 'Înregistrare gratuită'} →
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-footer-brand">
            <img src="/logo_etox.png" alt="EtoX" className="lp-footer-logo" />
            <div>
              <div className="lp-footer-name">EtoX Platform</div>
              <div className="lp-footer-tagline">Pregătire BAC Matematică</div>
              <div className="lp-footer-copy">© 2026 EtoX Academy. Toate drepturile rezervate.</div>
            </div>
          </div>

          <div className="lp-footer-cols">
            <div className="lp-footer-col">
              <div className="lp-footer-col-title">Platformă</div>
              <a href="#features" className="lp-footer-link">Funcții</a>
              <a href="#how" className="lp-footer-link">Cum funcționează</a>
              <a href="#plans" className="lp-footer-link">Planuri</a>
              <a href="#parents" className="lp-footer-link">Părinți</a>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-col-title">Cont</div>
              <Link to="/login" className="lp-footer-link">Intră în cont</Link>
              <Link to="/register" className="lp-footer-link">Înregistrare</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
