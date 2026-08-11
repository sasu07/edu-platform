import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpenCheck,
  CalendarDays,
  Check,
  ChevronDown,
  CircleCheck,
  Flame,
  Gauge,
  GraduationCap,
  MessageCircleMore,
  Route,
  Target,
  TrendingUp,
  UsersRound,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { BRAND_LOGO_URL } from '../brand';
import './LandingPage.css';

const WHATSAPP_URL =
  'https://wa.me/40745960848?text=Salut!%20Vreau%20s%C4%83%20aflu%20ce%20plan%20mi%20se%20potrive%C8%99te.';

const NAV_ITEMS = [
  { id: 'platforma', label: 'Platforma' },
  { id: 'cum-functioneaza', label: 'Cum funcționează' },
  { id: 'pentru-cine', label: 'Pentru cine' },
  { id: 'planuri', label: 'Planuri' },
] as const;

type ChapterId = (typeof NAV_ITEMS)[number]['id'];

type Benefit = {
  icon: LucideIcon;
  title: string;
  text: string;
};

type Audience = {
  number: string;
  icon: LucideIcon;
  label: string;
  title: string;
  text: string;
  accent: 'blue' | 'lime' | 'violet';
};

type Plan = {
  name: string;
  price: string;
  note: string;
  features: string[];
  cta: string;
  href: string;
  featured?: boolean;
};

const BENEFITS: Benefit[] = [
  {
    icon: BookOpenCheck,
    title: 'Subiecte care chiar contează',
    text: 'Variante oficiale și exerciții organizate pe profil, capitol și dificultate.',
  },
  {
    icon: Route,
    title: 'Un traseu doar al tău',
    text: 'Planul se adaptează după fiecare răspuns, nu după un calendar generic.',
  },
  {
    icon: MessageCircleMore,
    title: 'Ajutor exact la blocaj',
    text: 'Indicii, verificare automată și sprijin de la profesor, în funcție de plan.',
  },
];

const AUDIENCES: Audience[] = [
  {
    number: '01',
    icon: GraduationCap,
    label: 'Pentru elevi',
    title: 'Știi mereu ce ai de făcut mai departe.',
    text: 'Sesiuni ghidate, răspunsuri verificate, calendar și Liga BAC într-un singur loc.',
    accent: 'blue',
  },
  {
    number: '02',
    icon: TrendingUp,
    label: 'Pentru părinți',
    title: 'Vezi progresul, fără să întrebi în fiecare zi.',
    text: 'Activitatea, calendarul și analiza lunară fac progresul ușor de înțeles.',
    accent: 'lime',
  },
  {
    number: '03',
    icon: UsersRound,
    label: 'Pentru profesori',
    title: 'Mai mult timp pentru explicațiile care contează.',
    text: 'Clase, generator de variante, leaderboard și solicitări organizate pe prioritate.',
    accent: 'violet',
  },
];

const PLANS: Plan[] = [
  {
    name: 'Free',
    price: '0',
    note: 'Pentru primul contact cu platforma',
    features: ['Toate variantele oficiale', '3 variante generate / lună', 'Cont fără card bancar'],
    cta: 'Creează cont',
    href: '/register',
  },
  {
    name: 'Start',
    price: '100',
    note: 'Pentru antrenament constant',
    features: ['10 variante generate / lună', 'Testare inițială și feedback', 'Ajutor disponibil 24/7'],
    cta: 'Alege Start',
    href: WHATSAPP_URL,
  },
  {
    name: 'Avansat',
    price: '250',
    note: 'Pentru o pregătire completă',
    features: [
      'Variante generate nelimitat',
      'Plan personalizat și sesiuni live',
      'XP, simulări și prioritate la întrebări',
    ],
    cta: 'Alege Avansat',
    href: WHATSAPP_URL,
    featured: true,
  },
  {
    name: 'Pro',
    price: '700',
    note: 'Pentru suport individual',
    features: [
      'Tot ce include planul Avansat',
      'Ședință individuală săptămânală',
      'Mentor personal și analiză lunară',
    ],
    cta: 'Discută cu noi',
    href: WHATSAPP_URL,
  },
];

function Brand() {
  return (
    <span className="lp-brand">
      <span className="lp-brand-mark" aria-hidden="true">
        <img src={BRAND_LOGO_URL} alt="" />
      </span>
      <span className="lp-brand-name">E2X ACADEMY</span>
    </span>
  );
}

function ChapterNav({
  className,
  label,
  activeChapter,
  onSelect,
}: {
  className: string;
  label: string;
  activeChapter: ChapterId;
  onSelect: (event: MouseEvent<HTMLAnchorElement>, id: ChapterId) => void;
}) {
  return (
    <nav className={className} aria-label={label}>
      {NAV_ITEMS.map(({ id, label: itemLabel }) => (
        <a
          className={activeChapter === id ? 'is-active' : undefined}
          href={`#${id}`}
          aria-current={activeChapter === id ? 'location' : undefined}
          onClick={(event) => onSelect(event, id)}
          key={id}
        >
          {itemLabel}
        </a>
      ))}
    </nav>
  );
}

function PrimaryLink({ to, children, light = false }: { to: string; children: ReactNode; light?: boolean }) {
  return (
    <Link className={`lp-button ${light ? 'lp-button-light' : 'lp-button-primary'}`} to={to}>
      <span>{children}</span>
      <ArrowUpRight size={18} aria-hidden="true" />
    </Link>
  );
}

function PlanLink({ plan, primaryTo, isSignedIn }: { plan: Plan; primaryTo: string; isSignedIn: boolean }) {
  if (plan.href.startsWith('http')) {
    return (
      <a className="lp-price-cta" href={plan.href} target="_blank" rel="noopener noreferrer">
        {plan.cta} <ArrowUpRight size={17} aria-hidden="true" />
      </a>
    );
  }

  return (
    <Link className="lp-price-cta" to={primaryTo}>
      {isSignedIn ? 'Deschide platforma' : plan.cta} <ArrowUpRight size={17} aria-hidden="true" />
    </Link>
  );
}

export default function LandingPage() {
  const { user } = useAuth();
  const primaryTo = user ? '/app' : '/register';
  const primaryLabel = user ? 'Deschide platforma' : 'Începe evaluarea gratuită';
  const [activeChapter, setActiveChapter] = useState<ChapterId>('platforma');
  const [motionReady, setMotionReady] = useState(false);

  useEffect(() => {
    const revealItems = Array.from(document.querySelectorAll<HTMLElement>('[data-lp-reveal]'));
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduceMotion || !('IntersectionObserver' in window)) {
      revealItems.forEach((item) => item.classList.add('is-visible'));
      return undefined;
    }

    setMotionReady(true);
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.12 },
    );

    revealItems.forEach((item) => observer.observe(item));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const sections = NAV_ITEMS.map(({ id }) => document.getElementById(id)).filter(Boolean) as HTMLElement[];
    let animationFrame = 0;

    const updateActiveChapter = () => {
      animationFrame = 0;
      const marker = Math.min(window.innerHeight * 0.34, 340);
      let nextChapter: ChapterId = NAV_ITEMS[0].id;

      sections.forEach((section) => {
        if (section.getBoundingClientRect().top <= marker) nextChapter = section.id as ChapterId;
      });

      setActiveChapter((current) => (current === nextChapter ? current : nextChapter));
    };

    const scheduleUpdate = () => {
      if (animationFrame) return;
      animationFrame = window.requestAnimationFrame(updateActiveChapter);
    };

    updateActiveChapter();
    window.addEventListener('scroll', scheduleUpdate, { passive: true });
    window.addEventListener('resize', scheduleUpdate);

    return () => {
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      window.removeEventListener('scroll', scheduleUpdate);
      window.removeEventListener('resize', scheduleUpdate);
    };
  }, []);

  useEffect(() => {
    const activeTab = document.querySelector<HTMLElement>('.lp-mobile-tabs a[aria-current="location"]');
    const tabList = activeTab?.parentElement;
    if (!activeTab || !tabList) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const centeredLeft = activeTab.offsetLeft - (tabList.clientWidth - activeTab.clientWidth) / 2;
    tabList.scrollTo({ left: Math.max(0, centeredLeft), behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [activeChapter]);

  const handleChapterSelect = (event: MouseEvent<HTMLAnchorElement>, id: ChapterId) => {
    event.preventDefault();
    const target = document.getElementById(id);
    if (!target) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setActiveChapter(id);
    window.history.replaceState(null, '', `#${id}`);
    target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  };

  return (
    <div className={`lp ${motionReady ? 'lp-motion-ready' : ''}`}>
      <a className="lp-skip-link" href="#continut">
        Sari la conținut
      </a>

      <div className="lp-header-fixed">
        <header className="lp-site-header lp-shell">
          <Link to="/" className="lp-brand-link" aria-label="E2X ACADEMY — Acasă">
            <Brand />
          </Link>

          <ChapterNav
            className="lp-desktop-nav"
            label="Navigație principală"
            activeChapter={activeChapter}
            onSelect={handleChapterSelect}
          />

          <div className="lp-header-actions">
            {!user && <Link to="/login" className="lp-login-link">Intră în cont</Link>}
            <Link to={primaryTo} className="lp-header-cta">
              {user ? 'Deschide platforma' : 'Începe gratuit'}
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          </div>

          <Link to={primaryTo} className="lp-mobile-header-cta">
            {user ? 'Platforma' : 'Începe'}
            <ArrowUpRight size={15} aria-hidden="true" />
          </Link>

          <ChapterNav
            className="lp-mobile-tabs"
            label="Capitolele paginii"
            activeChapter={activeChapter}
            onSelect={handleChapterSelect}
          />
        </header>
      </div>

      <section className="lp-hero" id="acasa">
        <div className="lp-hero-glow lp-hero-glow-one" aria-hidden="true" />
        <div className="lp-hero-glow lp-hero-glow-two" aria-hidden="true" />
        <div className="lp-math-note lp-math-note-one" aria-hidden="true">x² − 3x + 2 = 0</div>
        <div className="lp-math-note lp-math-note-two" aria-hidden="true">f&apos;(x) ↗</div>

        <div className="lp-hero-content lp-shell" id="continut">
          <div className="lp-hero-copy">
            <p className="lp-hero-kicker">Pregătire structurată pentru BAC la matematică</p>
            <h1>
              Nu înveți mai mult.
              <span>Înveți ce trebuie.</span>
            </h1>
            <p className="lp-hero-lead">
              E2X ACADEMY aduce într-un singur loc evaluarea nivelului, exercițiile potrivite,
              calendarul și progresul până în ziua examenului.
            </p>
            <div className="lp-hero-buttons">
              <PrimaryLink to={primaryTo}>{primaryLabel}</PrimaryLink>
              <a className="lp-text-link" href="#platforma">
                Vezi platforma <ArrowRight size={18} aria-hidden="true" />
              </a>
            </div>
            <div className="lp-hero-assurances" aria-label="Avantaje cont gratuit">
              <span><CircleCheck size={17} aria-hidden="true" /> Fără card</span>
              <span><CircleCheck size={17} aria-hidden="true" /> Începi în câteva minute</span>
            </div>
          </div>

          <div className="lp-hero-product" role="img" aria-label="Exemplu vizual al platformei E2X ACADEMY">
            <div className="lp-product-orbit lp-product-orbit-one" aria-hidden="true" />
            <div className="lp-product-orbit lp-product-orbit-two" aria-hidden="true" />

            <div className="lp-floating-card lp-floating-streak" aria-hidden="true">
              <span className="lp-floating-icon"><Flame size={18} /></span>
              <span><small>Seria ta</small><strong>12 zile</strong></span>
            </div>

            <div className="lp-floating-card lp-floating-next" aria-hidden="true">
              <span className="lp-floating-icon is-blue"><Target size={18} /></span>
              <span><small>Următorul pas</small><strong>Funcții · 20 min</strong></span>
            </div>

            <div className="lp-product-window" aria-hidden="true">
              <div className="lp-window-topbar">
                <div className="lp-window-dots"><span /><span /><span /></div>
                <div className="lp-demo-badge">Previzualizare platformă</div>
                <div className="lp-window-avatar">A</div>
              </div>

              <div className="lp-mock-dashboard">
                <aside className="lp-mock-sidebar">
                    <div className="lp-sidebar-logo">E2X</div>
                  <span className="lp-sidebar-item is-active" />
                  <span className="lp-sidebar-item" />
                  <span className="lp-sidebar-item is-short" />
                  <span className="lp-sidebar-item" />
                </aside>

                <div className="lp-mock-main">
                  <div className="lp-mock-heading">
                    <div>
                      <span className="lp-mock-kicker">Bună, Andrei</span>
                      <h2>Traseul tău spre BAC</h2>
                    </div>
                    <span className="lp-mock-date"><CalendarDays size={13} /> Săptămâna 8</span>
                  </div>

                  <div className="lp-mock-stat-row">
                    <div className="lp-mock-progress-card">
                      <div className="lp-progress-ring"><span>72%</span></div>
                      <div>
                        <small>Plan săptămânal</small>
                        <strong>Pe drumul cel bun</strong>
                        <span className="lp-positive-line">+8% față de săptămâna trecută</span>
                      </div>
                    </div>

                    <div className="lp-mock-score-card">
                      <div className="lp-score-icon"><Gauge size={18} /></div>
                      <small>Nivel estimat</small>
                      <strong>8,35</strong>
                      <span>Obiectiv personal: 9,00</span>
                    </div>
                  </div>

                  <div className="lp-mock-bottom-row">
                    <div className="lp-mock-chart-card">
                      <div className="lp-chart-title"><span>Ritmul tău</span><BarChart3 size={16} /></div>
                      <div className="lp-mini-chart"><span /><span /><span /><span /><span /><span /><span /></div>
                      <div className="lp-chart-days"><span>L</span><span>M</span><span>M</span><span>J</span><span>V</span><span>S</span><span>D</span></div>
                    </div>

                    <div className="lp-mock-task-card">
                      <span className="lp-task-label">Astăzi</span>
                      <strong>Ecuații și inecuații</strong>
                      <span className="lp-task-meta">12 exerciții · 25 min</span>
                      <div className="lp-task-progress"><span /></div>
                      <span className="lp-mock-button">Continuă <ArrowRight size={13} /></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="lp-hero-bottom lp-shell">
          <span>Un singur sistem.</span>
          <div className="lp-role-strip">
            <span><GraduationCap size={18} /> Elevul exersează</span>
            <i aria-hidden="true" />
            <span><TrendingUp size={18} /> Părintele vede progresul</span>
            <i aria-hidden="true" />
            <span><UsersRound size={18} /> Profesorul intervine</span>
          </div>
        </div>
      </section>

      <main>
        <section className="lp-benefits-bar" aria-label="Principalele beneficii">
          <div className="lp-shell lp-benefits-grid" data-lp-reveal="up">
            {BENEFITS.map(({ icon: Icon, title, text }) => (
              <article className="lp-benefit-item" key={title}>
                <span className="lp-benefit-icon"><Icon size={21} strokeWidth={1.8} /></span>
                <div><h2>{title}</h2><p>{text}</p></div>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-platform lp-section lp-chapter" id="platforma">
          <div className="lp-shell">
            <div className="lp-section-heading lp-split-heading" data-lp-reveal="up">
              <div>
                <span className="lp-section-index">01 — Platforma</span>
                <h2>Din „nu știu de unde să încep” într-un traseu clar.</h2>
              </div>
              <p>
                Nu primești încă un folder cu materiale. Primești un sistem care leagă
                diagnosticul, exercițiile, feedbackul și progresul într-o singură experiență.
              </p>
            </div>

            <div className="lp-bento-grid">
              <article className="lp-bento-card lp-bento-diagnostic" data-lp-reveal="up">
                <div className="lp-card-copy">
                  <span className="lp-card-number">01</span>
                  <div className="lp-card-icon"><Gauge size={22} /></div>
                  <h3>Începi cu nivelul tău real</h3>
                  <p>Testarea inițială identifică ce stăpânești și unde merită să investești timp.</p>
                </div>
                <div className="lp-diagnostic-visual" aria-hidden="true">
                  <div className="lp-diagnostic-top"><span>Diagnostic inițial</span><span>Finalizat</span></div>
                  <div className="lp-diagnostic-score"><strong>7,40</strong><span>nivel estimat</span></div>
                  <div className="lp-skill-row"><span>Algebră</span><i><b style={{ width: '84%' }} /></i><em>84%</em></div>
                  <div className="lp-skill-row"><span>Geometrie</span><i><b style={{ width: '62%' }} /></i><em>62%</em></div>
                  <div className="lp-skill-row"><span>Analiză</span><i><b style={{ width: '71%' }} /></i><em>71%</em></div>
                </div>
              </article>

              <article className="lp-bento-card lp-bento-plan lp-reveal-delay-1" data-lp-reveal="up">
                <div className="lp-card-copy">
                  <span className="lp-card-number">02</span>
                  <div className="lp-card-icon is-lime"><Route size={22} /></div>
                  <h3>Planul se mișcă odată cu tine</h3>
                  <p>Fiecare rezultat actualizează calendarul și pasul următor.</p>
                </div>
                <div className="lp-plan-visual" aria-hidden="true">
                  <span className="lp-plan-line" />
                  <div className="lp-plan-step is-done"><i><Check size={13} /></i><span><small>Luni</small><strong>Funcții</strong></span></div>
                  <div className="lp-plan-step is-current"><i>2</i><span><small>Astăzi</small><strong>Derivate</strong></span></div>
                  <div className="lp-plan-step"><i>3</i><span><small>Vineri</small><strong>Simulare</strong></span></div>
                </div>
              </article>

              <article className="lp-bento-card lp-bento-feedback lp-reveal-delay-1" data-lp-reveal="up">
                <div className="lp-feedback-visual" aria-hidden="true">
                  <div className="lp-exercise-tag">Exercițiul 4 / 12</div>
                  <div className="lp-formula">x² − 5x + 6 = 0</div>
                  <div className="lp-answer-row"><span>x₁ = 2, x₂ = 3</span><CircleCheck size={20} /></div>
                  <div className="lp-feedback-message"><CircleCheck size={15} /> Răspuns corect. Metoda este potrivită.</div>
                </div>
                <div className="lp-card-copy">
                  <span className="lp-card-number">03</span>
                  <div className="lp-card-icon is-violet"><BookOpenCheck size={22} /></div>
                  <h3>Primești feedback, nu doar un punctaj</h3>
                  <p>Răspunsul este verificat, iar blocajele devin lecții concrete.</p>
                </div>
              </article>

              <article className="lp-bento-card lp-bento-progress lp-reveal-delay-2" data-lp-reveal="up">
                <div className="lp-card-copy">
                  <span className="lp-card-number">04</span>
                  <div className="lp-card-icon is-coral"><BarChart3 size={22} /></div>
                  <h3>Progresul devine vizibil</h3>
                  <p>Elevul, părintele și profesorul văd același traseu, în limbajul potrivit.</p>
                </div>
                <div className="lp-progress-visual" aria-hidden="true">
                  <div className="lp-progress-chart-line">
                    <span className="lp-line-segment lp-line-one" />
                    <span className="lp-line-segment lp-line-two" />
                    <span className="lp-line-segment lp-line-three" />
                    <i className="lp-point lp-point-one" /><i className="lp-point lp-point-two" />
                    <i className="lp-point lp-point-three" /><i className="lp-point lp-point-four" />
                  </div>
                  <span className="lp-chart-start">Test inițial</span>
                  <span className="lp-chart-end">Obiectiv</span>
                  <strong className="lp-chart-value">+1,45</strong>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="lp-how lp-section lp-section-dark lp-chapter" id="cum-functioneaza">
          <div className="lp-shell lp-how-layout">
            <div className="lp-how-copy" data-lp-reveal="left">
              <span className="lp-section-index is-dark">02 — Cum funcționează</span>
              <h2>Un pas bun.<br />Apoi încă unul.</h2>
              <p>
                e2x reduce pregătirea la un ciclu simplu, repetabil și ușor de urmărit.
                Fără improvizație. Fără materiale pierdute.
              </p>
              <PrimaryLink to={primaryTo}>{user ? 'Deschide platforma' : 'Construiește-mi traseul'}</PrimaryLink>
            </div>

            <div className="lp-steps-list">
              <article className="lp-step-item" data-lp-reveal="right">
                <span className="lp-step-number">01</span>
                <div><h3>Îți testezi nivelul</h3><p>Rezolvi evaluarea inițială, iar platforma identifică punctele forte și lacunele.</p></div>
                <Gauge size={24} />
              </article>
              <article className="lp-step-item lp-reveal-delay-1" data-lp-reveal="right">
                <span className="lp-step-number">02</span>
                <div><h3>Primești un plan adaptiv</h3><p>Ai un calendar concret, cu exercițiile potrivite și un ritm realist pentru obiectivul tău.</p></div>
                <CalendarDays size={24} />
              </article>
              <article className="lp-step-item lp-reveal-delay-2" data-lp-reveal="right">
                <span className="lp-step-number">03</span>
                <div><h3>Exersezi. Verifici. Progresezi.</h3><p>Fiecare răspuns actualizează statisticile, jurnalul greșelilor și următorul pas.</p></div>
                <TrendingUp size={24} />
              </article>
            </div>
          </div>
        </section>

        <section className="lp-audience lp-section lp-chapter" id="pentru-cine">
          <div className="lp-shell">
            <div className="lp-section-heading lp-audience-heading" data-lp-reveal="up">
              <div>
                <span className="lp-section-index">03 — Pentru cine</span>
                <h2>Același progres.<br />Trei perspective.</h2>
              </div>
              <p>Mai puține mesaje pierdute între elev, familie și profesor. Mai multă continuitate.</p>
            </div>

            <div className="lp-audience-grid">
              {AUDIENCES.map(({ number, icon: Icon, label, title, text, accent }, index) => (
                <article className={`lp-audience-card is-${accent} lp-reveal-delay-${index}`} data-lp-reveal="up" key={label}>
                  <div className="lp-audience-card-top">
                    <span>{number}</span>
                    <div className="lp-audience-icon"><Icon size={25} /></div>
                  </div>
                  <span className="lp-audience-label">{label}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-pricing lp-section lp-chapter" id="planuri">
          <div className="lp-shell">
            <div className="lp-section-heading lp-pricing-heading" data-lp-reveal="up">
              <div>
                <span className="lp-section-index">04 — Planuri</span>
                <h2>Începi gratuit.<br />Crești când ai nevoie.</h2>
              </div>
              <div className="lp-pricing-note">
                <CircleCheck size={19} />
                <p>Contul Free nu cere card. Planurile plătite se activează împreună cu echipa E2X ACADEMY.</p>
              </div>
            </div>

            <div className="lp-pricing-grid">
              {PLANS.map((plan, index) => (
                <article className={`lp-price-card lp-reveal-delay-${Math.min(index, 3)} ${plan.featured ? 'is-featured' : ''}`} data-lp-reveal="up" key={plan.name}>
                  {plan.featured && <span className="lp-recommended">Recomandat</span>}
                  <div className="lp-price-name">{plan.name}</div>
                  <p>{plan.note}</p>
                  <div className="lp-price"><strong>{plan.price}</strong><span>{plan.price === '0' ? 'lei' : 'lei / lună'}</span></div>
                  <ul>
                    {plan.features.map((feature) => <li key={feature}><Check size={16} /> {feature}</li>)}
                  </ul>
                  <PlanLink plan={plan} primaryTo={primaryTo} isSignedIn={Boolean(user)} />
                </article>
              ))}
            </div>
            <p className="lp-pricing-footnote">Poți schimba planul oricând. Pentru recomandare, ne poți scrie direct pe WhatsApp.</p>
          </div>
        </section>

        <section className="lp-faq lp-section">
          <div className="lp-shell lp-faq-layout">
            <div className="lp-faq-intro" data-lp-reveal="left">
              <span className="lp-section-index">05 — Întrebări</span>
              <h2>Înainte să începi.</h2>
              <p>Răspunsuri scurte la lucrurile pe care elevii și părinții ni le întreabă cel mai des.</p>
              <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="lp-whatsapp-link">
                <MessageCircleMore size={20} /> Mai ai o întrebare? Scrie-ne
              </a>
            </div>

            <div className="lp-faq-list" data-lp-reveal="right">
              <details open>
                <summary>Pot să încerc platforma înainte să plătesc?<ChevronDown size={20} /></summary>
                <p>Da. Planul Free îți oferă acces la variantele oficiale și la trei variante generate în fiecare lună, fără card bancar.</p>
              </details>
              <details>
                <summary>Cum se activează un plan plătit?<ChevronDown size={20} /></summary>
                <p>Ne scrii pe WhatsApp, alegem împreună nivelul de suport potrivit și echipa e2x îți activează planul.</p>
              </details>
              <details>
                <summary>Poate părintele să urmărească progresul?<ChevronDown size={20} /></summary>
                <p>Da. Informațiile despre activitate, calendar și evoluție sunt prezentate clar, astfel încât progresul să poată fi urmărit fără presiune zilnică.</p>
              </details>
              <details>
                <summary>Primesc ajutor dacă mă blochez?<ChevronDown size={20} /></summary>
                <p>Platforma oferă indicii, verificare automată și, în funcție de plan, ajutor de la profesor și ședințe live.</p>
              </details>
            </div>
          </div>
        </section>

        <section className="lp-final-cta">
          <div className="lp-shell lp-final-cta-card" data-lp-reveal="up">
            <div className="lp-final-cta-decor" aria-hidden="true">E2X</div>
            <div>
              <span className="lp-final-kicker">Primul pas este gratuit</span>
              <h2>BAC-ul nu se pregătește la întâmplare.</h2>
              <p>Descoperă unde ești acum și primește traseul care te duce mai aproape de obiectiv.</p>
            </div>
            <PrimaryLink to={primaryTo} light>{user ? 'Deschide platforma' : 'Începe evaluarea'}</PrimaryLink>
          </div>
        </section>
      </main>

      <footer className="lp-site-footer">
        <div className="lp-shell lp-footer-main">
          <div className="lp-footer-brand">
            <Link to="/" aria-label="E2X ACADEMY — Acasă"><Brand /></Link>
            <p>Pregătire pentru BAC la matematică, construită în jurul progresului real.</p>
          </div>
          <div className="lp-footer-links">
            <div><strong>Platforma</strong><a href="#platforma">Ce primești</a><a href="#cum-functioneaza">Cum funcționează</a><a href="#planuri">Planuri</a></div>
            <div><strong>Cont</strong><Link to="/register">Înregistrare</Link><Link to="/login">Autentificare</Link><Link to="/app">Intră în platformă</Link></div>
            <div><strong>Contact</strong><a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer">WhatsApp</a><a href="tel:+40745960848">+40 745 960 848</a></div>
          </div>
        </div>
        <div className="lp-shell lp-footer-bottom"><span>© 2026 E2X ACADEMY</span><span>Creat pentru progres, nu pentru presiune.</span></div>
      </footer>
    </div>
  );
}
