import { Suspense, lazy, useEffect, useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  NavLink,
  Navigate,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { Menu, X } from "lucide-react";

import Login from "./components/Login";
import Register from "./components/Register";
import { AuthProvider, useAuth } from "./AuthContext";
import NotificationBell from "./components/NotificationBell";
import StudyPrepCalendar from "./components/StudyPrepCalendar";
import {
  buildApiUrl,
  getLearningPath,
  getMyGamification,
  getStudyPlan,
  getStudySessions,
  getStudyStats,
  type GamificationProfile,
  type StudyPlanDay,
  type StudySession,
  type StudyStats,
} from "./api";
import { BRAND_LOGO_URL } from "./brand";
import "./App.css";

const LandingPage = lazy(() => import("./components/LandingPage"));
const SourceList = lazy(() => import("./components/SourceList"));
const ExerciseList = lazy(() => import("./components/ExerciseList"));
const ExerciseEditor = lazy(() => import("./components/ExerciseEditor"));
const JSONImport = lazy(() => import("./components/JSONImport"));
const VariantBuilderAuto = lazy(() => import("./components/VariantBuilderAuto"));
const SourceDetails = lazy(() => import("./components/SourceDetails"));
const StudentExercises = lazy(() => import("./components/StudentExercises"));
const TeacherDashboard = lazy(() => import("./components/TeacherDashboard"));
const LeagueHub = lazy(() => import("./components/LeagueHub"));
const AdminPanel = lazy(() => import("./components/AdminPanel"));
const MyRequests = lazy(() => import("./components/MyRequests"));
const ParentDashboard = lazy(() => import("./components/ParentDashboard"));
const StudySession = lazy(() => import("./components/StudySession"));
const StudyPlan = lazy(() => import("./components/StudyPlan"));
const LearningPath = lazy(() => import("./components/LearningPath"));
const SourceLibrary = lazy(() => import("./components/SourceLibrary"));

function RouteLoader() {
  return <div className="auth-loading">Se încarcă...</div>;
}

// --- Route guard pentru utilizatori autentificați ---
function RequireAuth({ children }: { children: React.ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-loading">Se încarcă...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}


function AppHub() {
  const { user, isTeacher, isAdmin, isParent } = useAuth();
  const [allSessions, setAllSessions] = useState<StudySession[]>([]);
  const [allPlanDays, setAllPlanDays] = useState<StudyPlanDay[]>([]);
  const [activeSession, setActiveSession] = useState<StudySession | null>(null);
  const [todayPlanEntries, setTodayPlanEntries] = useState<StudyPlanDay[]>([]);
  const [studyStats, setStudyStats] = useState<StudyStats | null>(null);
  const [gamification, setGamification] = useState<GamificationProfile | null>(null);
  const [needsDiagnostic, setNeedsDiagnostic] = useState(false);

  const bacDate = new Date('2026-07-01');
  const daysLeft = Math.max(0, Math.ceil((bacDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24)));
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Bună dimineața' : hour < 18 ? 'Bună ziua' : 'Bună seara';
  const firstName = user?.full_name?.split(' ')[0] || user?.full_name || '';
  const weakestSubiect =
    studyStats?.subiect_progress?.length
      ? [...studyStats.subiect_progress].sort((a, b) => a.pct - b.pct)[0]
      : null;
  const recommendedSubiect =
    studyStats?.recommendation?.match(/([123])/)?.[1] || weakestSubiect?.subiect || "";

  useEffect(() => {
    if (isTeacher || isParent) return;

    Promise.all([getStudySessions(), getStudyPlan(), getStudyStats(), getMyGamification()])
      .then(([sessionsRes, planRes, statsRes, gamificationRes]) => {
        const sessions = Array.isArray(sessionsRes.data) ? sessionsRes.data : [];
        const plans = Array.isArray(planRes.data) ? planRes.data : [];
        const today = new Date().toISOString().slice(0, 10);

        setAllSessions(sessions);
        setAllPlanDays(plans);
        const active = sessions.find((session) => session.status === "active") || null;
        setActiveSession(active);
        setStudyStats(statsRes.data || null);
        setGamification(gamificationRes.data || null);
        setTodayPlanEntries(
          plans
            .filter((entry) => entry.plan_date === today)
            .sort((a, b) => a.created_at.localeCompare(b.created_at)),
        );
      })
      .catch(() => {
        setAllSessions([]);
        setAllPlanDays([]);
        setActiveSession(null);
        setTodayPlanEntries([]);
        setStudyStats(null);
        setGamification(null);
      });
  }, [isParent, isTeacher]);

  // Nudge diagnostic: elevii fără plan (n-au terminat diagnosticul) primesc un banner pe hub
  useEffect(() => {
    if (isTeacher || isParent) return;
    getLearningPath()
      .then((r) => setNeedsDiagnostic(!r.data.path))
      .catch(() => {});
  }, [isParent, isTeacher]);

  if (isParent) return <Navigate to="/app/parent" replace />;
  return (
    <div className="hub">
      <header className="hub-head">
        <div className="hub-greeting-block">
          <h1 className="hub-greeting">{greeting}, {firstName}!</h1>
          <p className="hub-subtitle">Hai să vedem care e cel mai bun pas pentru azi.</p>
        </div>
        {!isTeacher && !isAdmin && (
          <div className="hub-bac-pill">
            <span className="hub-bac-icon">🎓</span>
            <div>
              <div className="hub-bac-days">{daysLeft}</div>
              <div className="hub-bac-label">zile până la BAC</div>
            </div>
          </div>
        )}
      </header>

      {needsDiagnostic && !isTeacher && !isParent && (
        <Link to="/app/learning-path" className="hub-diag-nudge">
          <span className="hub-diag-nudge-icon">🎯</span>
          <span className="hub-diag-nudge-text">
            <span className="hub-diag-nudge-title">Începe cu testul diagnostic</span>
            <span className="hub-diag-nudge-sub">~10 min · gratuit · îți deblochează planul personalizat pe lacunele tale</span>
          </span>
          <span className="hub-diag-nudge-cta">Începe →</span>
        </Link>
      )}

      {!isTeacher && !isParent && (
        <section className="hub-dashboard">
          <div className="hub-dashboard-main">
            <div className="hub-dashboard-kicker">Astăzi</div>
            <h2 className="hub-dashboard-title">Hai să intrăm în ritm</h2>
            <p className="hub-dashboard-subtitle">
              Tot ce ai nevoie ca să știi rapid de unde să începi, fără aglomerație inutilă.
            </p>
          </div>

          <div className="hub-student-hero">
            <div className="hub-student-hero-main">
              <div className="hub-panel-label">Pasul tău de acum</div>
              <div className="hub-student-hero-title">
                {activeSession
                  ? "Continuă ce ai început"
                  : todayPlanEntries.length > 0
                    ? "Ai ceva pregătit pentru azi"
                    : weakestSubiect
                      ? `Merită să lucrezi pe Subiectul ${weakestSubiect.subiect}`
                      : "Pornește cu o sesiune scurtă"}
              </div>
              <div className="hub-panel-text">
                {activeSession
                  ? `Ai deja un ${activeSession.session_type === "test_bac" ? "Test BAC" : "Test Scurt"} în desfășurare. Închide-l întâi și păstrezi ritmul.`
                  : todayPlanEntries.length > 0
                    ? `Ai ${todayPlanEntries.length} activități planificate azi. Începe cu prima și intri imediat în modul de lucru.`
                    : weakestSubiect
                      ? `Aici ai cel mai mult loc de progres acum: ${weakestSubiect.completed} din ${weakestSubiect.total} exerciții completate.`
                      : "După primele sesiuni, pagina asta o să-ți arate automat unde merită să insiști mai întâi."}
              </div>

              <div className="hub-student-hero-actions">
                {activeSession ? (
                  <Link to={`/app/study-session?resume=${activeSession.id}`} className="hub-panel-action">
                    Continuă acum
                  </Link>
                ) : todayPlanEntries.length > 0 ? (
                  <Link
                    to={`/app/study-session?plan=${todayPlanEntries[0].id}&type=${todayPlanEntries[0].session_type}${todayPlanEntries[0].filters?.subiect_tag ? `&subiect=${todayPlanEntries[0].filters.subiect_tag}` : ""}${todayPlanEntries[0].filters?.exercise_set_id ? `&set=${todayPlanEntries[0].filters.exercise_set_id}` : ""}`}
                    className="hub-panel-action"
                  >
                    Începe ce ai planificat
                  </Link>
                ) : (
                  <Link
                    to={`/app/study-session?type=test_scurt${recommendedSubiect ? `&subiect=${recommendedSubiect}` : ""}`}
                    className="hub-panel-action"
                  >
                    Pornește o sesiune
                  </Link>
                )}

                <Link
                  to={recommendedSubiect ? `/app/exercises?subiect=${recommendedSubiect}` : "/app/exercises"}
                  className="hub-panel-action secondary"
                >
                  Lucrează pe subiect
                </Link>
              </div>
            </div>

            <div className="hub-student-summary">
              <div className="hub-student-summary-card">
                <div className="hub-student-summary-value">{studyStats?.total_sessions || 0}</div>
                <div className="hub-student-summary-label">sesiuni</div>
              </div>
              <div className="hub-student-summary-card">
                <div className="hub-student-summary-value">{studyStats?.total_xp || 0}</div>
                <div className="hub-student-summary-label">XP</div>
              </div>
              <div className="hub-student-summary-card">
                <div className="hub-student-summary-value">{gamification?.streak_current || 0}</div>
                <div className="hub-student-summary-label">zile streak</div>
              </div>
              <div className="hub-student-summary-card">
                <div className="hub-student-summary-value">{weakestSubiect ? `${weakestSubiect.pct}%` : "-"}</div>
                <div className="hub-student-summary-label">pe focus</div>
              </div>
            </div>
          </div>

          <div className="hub-compact-links">
            <Link to="/app/study-plan" className="hub-compact-link">Planul meu</Link>
            <Link to="/app/exercises" className="hub-compact-link">Exerciții</Link>
            <Link to="/app/variants" className="hub-compact-link">Antrenament BAC</Link>
          </div>

          <div className="hub-details-stack">
            <details className="hub-detail-card">
              <summary>Vezi cum stau</summary>
              <div className="hub-detail-grid">
                {gamification && (
                  <div className="hub-panel">
                    <div className="hub-panel-label">Nivelul meu</div>
                    <div className="hub-panel-value">{gamification.level.name}</div>
                    <div className="hub-panel-text">
                      Ai {gamification.xp_total} XP, un streak de {gamification.streak_current} zile și un record de {gamification.streak_max}.
                    </div>
                    {!!gamification.badges.length && (
                      <div className="hub-hero-badge-row">
                        {gamification.badges.slice(0, 4).map((badge) => (
                          <span key={badge.key} className="hub-mini-badge" title={badge.label}>
                            {badge.icon}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="hub-panel">
                  <div className="hub-panel-label">Unde stai acum</div>
                  {studyStats?.subiect_progress?.length ? (
                    <div className="hub-progress-list">
                      {studyStats.subiect_progress.map((item) => (
                        <div key={item.subiect} className="hub-progress-row">
                          <div className="hub-progress-top">
                            <span>{`Subiectul ${item.subiect}`}</span>
                            <span>{item.pct}%</span>
                          </div>
                          <div className="hub-progress-track">
                            <div className="hub-progress-fill" style={{ width: `${item.pct}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="hub-panel-foot">După câteva sesiuni, aici o să vezi clar ce merge bine și ce mai ai de lucrat.</div>
                  )}
                </div>

                <div className="hub-panel">
                  <div className="hub-panel-label">Ce ai făcut recent</div>
                  {studyStats?.daily_last_30?.length ? (
                    <div className="hub-activity-list">
                      {studyStats.daily_last_30
                        .filter((day) => day.sessions > 0 || day.exercises > 0)
                        .slice(-5)
                        .reverse()
                        .map((day) => (
                          <div key={day.date} className="hub-activity-row">
                            <div>
                              <div className="hub-activity-date">
                                {new Date(day.date).toLocaleDateString("ro-RO", { day: "numeric", month: "long" })}
                              </div>
                              <div className="hub-activity-meta">
                                {day.sessions} sesiuni · {day.exercises} exerciții
                              </div>
                            </div>
                            <div className="hub-activity-pill">
                              {day.exercises > 0 ? "Activ" : "Light"}
                            </div>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <div className="hub-panel-foot">Încă nu ai activitate recentă înregistrată aici.</div>
                  )}
                </div>
              </div>
            </details>

            <details className="hub-detail-card">
              <summary>Vezi calendarul meu</summary>
              <StudyPrepCalendar
                title="Calendarul tău de pregătire"
                subtitle="Aici vezi zilele în care ai lucrat, ce ai planificat și cum arată streak-ul tău."
                sessions={allSessions}
                planDays={allPlanDays}
                gamification={gamification}
                className="hub-prep-calendar"
              />
            </details>
          </div>
        </section>
      )}

      <div className="hub-grid">
        {isTeacher && (
          <Link to="/app/content/import" className="hub-card">
            <div className="hub-card-icon hub-icon-blue">📂</div>
            <div className="hub-card-title">Conținut</div>
            <div className="hub-card-sub">Import JSON + gestionare/verificare exerciții</div>
            <div className="hub-card-cta">Deschide</div>
          </Link>
        )}

        <Link to="/app/exercises" className="hub-card">
          <div className="hub-card-icon hub-icon-blue">📖</div>
          <div className="hub-card-title">Exerciții</div>
          <div className="hub-card-sub">Generează exerciții pe topic și verifică-ți soluțiile</div>
          <div className="hub-card-cta">Deschide</div>
        </Link>

        {!isTeacher && !isParent && (
          <Link to="/app/learning-path" className="hub-card hub-card-learning">
            <div className="hub-card-icon hub-icon-purple">🧠</div>
            <div className="hub-card-title">Traseu adaptat</div>
            <div className="hub-card-sub">Test diagnostic + plan personalizat pe lacunele tale</div>
            <div className="hub-card-cta">Începe</div>
          </Link>
        )}

        {!isTeacher && (
          <Link to="/app/study-session" className="hub-card hub-card-session">
            <div className="hub-card-icon hub-icon-purple">⚡</div>
            <div className="hub-card-title">Sesiune de studiu</div>
            <div className="hub-card-sub">Test scurt (10 ex · 60 min) sau Test BAC (25 ex · 3h) cu timer live</div>
            <div className="hub-card-cta">Pornește</div>
          </Link>
        )}

        {!isTeacher && (
          <Link to="/app/study-plan" className="hub-card hub-card-plan">
            <div className="hub-card-icon hub-icon-green">📅</div>
            <div className="hub-card-title">Plan săptămânal</div>
            <div className="hub-card-sub">Planifică sesiunile de studiu și urmărește countdown-ul până la BAC</div>
            <div className="hub-card-cta">Deschide</div>
          </Link>
        )}

        {!isParent && (
          <Link to="/app/league" className="hub-card">
            <div className="hub-card-icon hub-icon-amber">🏆</div>
            <div className="hub-card-title">Liga BAC</div>
            <div className="hub-card-sub">Clasament săptămânal, cod de clasă și provocări care țin ritmul viu</div>
            <div className="hub-card-cta">Intră</div>
          </Link>
        )}

        <Link to="/app/variants" className="hub-card">
          <div className="hub-card-icon hub-icon-blue">📄</div>
          <div className="hub-card-title">Variante BAC</div>
          <div className="hub-card-sub">Generare automată subiecte tip BAC + download PDF</div>
          <div className="hub-card-cta">Deschide</div>
        </Link>

        {isTeacher && (
          <Link to="/app/teacher/requests" className="hub-card">
            <div className="hub-card-icon hub-icon-amber">✉️</div>
            <div className="hub-card-title">Cereri de ajutor</div>
            <div className="hub-card-sub">Răspunde la flag-urile trimise de studenți</div>
            <div className="hub-card-cta">Deschide</div>
          </Link>
        )}

        {isAdmin && (
          <Link to="/app/admin" className="hub-card hub-card-admin">
            <div className="hub-card-icon hub-icon-amber">⚙️</div>
            <div className="hub-card-title">Administrator</div>
            <div className="hub-card-sub">Gestionează utilizatori și abonamente</div>
            <div className="hub-card-cta">Deschide</div>
          </Link>
        )}

        {isParent && (
          <Link to="/app/parent" className="hub-card hub-card-parent">
            <div className="hub-card-icon hub-icon-purple">📊</div>
            <div className="hub-card-title">Dashboard Progres</div>
            <div className="hub-card-sub">Urmărește activitatea și progresul elevului tău</div>
            <div className="hub-card-cta">Deschide</div>
          </Link>
        )}
      </div>
    </div>
  );
}

function SourcesPage({ refreshKey }: { refreshKey: number }) {
  return (
    <>
      <header className="page-header">
        <h1 className="page-title">Surse</h1>
        <p className="page-description">
          Listă cu surse importate și informațiile principale.
        </p>
      </header>

      <div className="content-grid single-column">
        <Suspense fallback={<RouteLoader />}>
          <SourceList refreshKey={refreshKey} />
        </Suspense>
      </div>
    </>
  );
}

function ContentShell({
  refreshKey,
  onImportSuccess,
}: {
  refreshKey: number;
  onImportSuccess: () => void;
}) {
  return (
    <div className="content-shell">
      <header className="content-head">
        <div>
          <h1 className="page-title">Conținut</h1>
          <p className="page-description">
            Import JSON și verificare/editare exerciții.
          </p>
        </div>

        <div className="subtabs">
          <NavLink
            to="/app/content/import"
            className={({ isActive }) => (isActive ? "subtab active" : "subtab")}
          >
            Import JSON
          </NavLink>
          <NavLink
            to="/app/content/exercises"
            className={({ isActive }) => (isActive ? "subtab active" : "subtab")}
          >
            Exerciții
          </NavLink>
          <NavLink
            to="/app/content/sources"
            className={({ isActive }) => (isActive ? "subtab active" : "subtab")}
          >
            Surse
          </NavLink>
        </div>
      </header>

      <Routes>
        <Route
          path="import"
          element={
            <Suspense fallback={<RouteLoader />}>
              <div className="content-grid single-column">
                <JSONImport onImportSuccess={onImportSuccess} />
              </div>
            </Suspense>
          }
        />
        <Route
          path="exercises"
          element={
            <Suspense fallback={<RouteLoader />}>
              <ExerciseList refreshKey={refreshKey} />
            </Suspense>
          }
        />
        <Route
          path="exercises/:id"
          element={
            <Suspense fallback={<RouteLoader />}>
              <ExerciseEditor />
            </Suspense>
          }
        />
        <Route
          path="sources/:sourceId"
          element={
            <Suspense fallback={<RouteLoader />}>
              <SourceDetails />
            </Suspense>
          }
        />
        <Route path="sources" element={<SourcesPage refreshKey={refreshKey} />} />
        <Route path="*" element={<Navigate to="/app/content/import" replace />} />
      </Routes>
    </div>
  );
}

function NavbarUser() {
  const { user, logout, isTeacher, isAdmin, isParent } = useAuth();
  const navigate = useNavigate();
  const [gamif, setGamif] = useState<GamificationProfile | null>(null);
  const isStudent = !isTeacher && !isAdmin && !isParent;

  useEffect(() => {
    if (isStudent && user) {
      getMyGamification().then((r) => setGamif(r.data)).catch(() => {});
    }
  }, [isStudent, user]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!user) return null;

  const firstName = user.full_name?.split(' ')[0] || user.full_name;

  return (
    <div className="navbar-user">
      {gamif && isStudent && (
        <div className="navbar-xp-strip">
          <span className="navbar-xp-level">⚡ {gamif.level.name}</span>
          <div className="navbar-xp-track">
            <div
              className="navbar-xp-fill"
              style={{ width: `${Math.min(100, (gamif.xp_total % 500) / 5)}%` }}
            />
          </div>
          <span className="navbar-xp-val">{gamif.xp_total} XP</span>
          {gamif.streak_current > 0 && (
            <span className="navbar-streak">🔥{gamif.streak_current}</span>
          )}
        </div>
      )}
      <NotificationBell />
      <span className="navbar-user-name">{firstName}</span>
      <span className={`navbar-user-badge badge-${user.role}`}>{user.role}</span>
      <button onClick={handleLogout} className="navbar-logout-btn">
        Ieși
      </button>
    </div>
  );
}

function AppShell() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [isOnline, setIsOnline] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const { isTeacher, isAdmin, isParent } = useAuth();
  const location = useLocation();

  const bumpRefresh = () => setRefreshKey((k) => k + 1);

  // Închide meniul mobil la orice schimbare de rută.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Blochează scroll-ul din spate cât timp drawer-ul mobil e deschis.
  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch(buildApiUrl("/health"));
        setIsOnline(response.ok);
      } catch {
        setIsOnline(false);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app">
      <nav className="navbar">
        <div className="navbar-content">
          <Link to="/app" className="navbar-brand">
            <img
              src={BRAND_LOGO_URL}
              alt="EtoX Academy"
              className="navbar-logo"
            />
            <div>
              <div className="navbar-title">EtoX Platform</div>
              <div className="navbar-subtitle">
                Platforma de Generare Subiecte BAC
              </div>
            </div>
          </Link>

          <button
            className="navbar-burger"
            aria-label={menuOpen ? "Închide meniul" : "Deschide meniul"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>

          {menuOpen && (
            <div
              className="navbar-overlay"
              onClick={() => setMenuOpen(false)}
              aria-hidden="true"
            />
          )}

          <div
            className={`navbar-links${menuOpen ? " open" : ""}`}
            onClick={() => setMenuOpen(false)}
          >
            {isParent ? (
              <NavLink
                to="/app/parent"
                className={({ isActive }) =>
                  isActive ? "nav-link active" : "nav-link"
                }
              >
                Progres Elev
              </NavLink>
            ) : (
              <>
                <NavLink
                  to="/app/exercises"
                  className={({ isActive }) =>
                    isActive ? "nav-link active" : "nav-link"
                  }
                >
                  Exerciții
                </NavLink>
                <NavLink
                  to="/app/subiecte"
                  className={({ isActive }) =>
                    isActive ? "nav-link active" : "nav-link"
                  }
                >
                  Subiecte BAC
                </NavLink>
                <NavLink
                  to="/app/my-requests"
                  className={({ isActive }) =>
                    isActive ? "nav-link active" : "nav-link"
                  }
                >
                  Cererile mele
                </NavLink>
                {!isTeacher && (
                  <NavLink
                    to="/app/learning-path"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Traseu
                  </NavLink>
                )}
                {!isTeacher && (
                  <NavLink
                    to="/app/study-session"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Sesiuni
                  </NavLink>
                )}
                {!isTeacher && (
                  <NavLink
                    to="/app/study-plan"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Plan
                  </NavLink>
                )}
                <NavLink
                  to="/app/league"
                  className={({ isActive }) =>
                    isActive ? "nav-link active" : "nav-link"
                  }
                >
                  Liga BAC
                </NavLink>
                <NavLink
                  to="/app/variants"
                  className={({ isActive }) =>
                    isActive ? "nav-link active" : "nav-link"
                  }
                >
                  Variante
                </NavLink>
                {isTeacher && (
                  <NavLink
                    to="/app/content/import"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Conținut
                  </NavLink>
                )}
                {isTeacher && (
                  <NavLink
                    to="/app/study-plan"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Plan studiu
                  </NavLink>
                )}
                {isTeacher && (
                  <NavLink
                    to="/app/teacher/requests"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Cereri
                  </NavLink>
                )}
                {isAdmin && (
                  <NavLink
                    to="/app/admin"
                    className={({ isActive }) =>
                      isActive ? "nav-link active" : "nav-link"
                    }
                  >
                    Admin
                  </NavLink>
                )}
              </>
            )}
          </div>

          <div className="navbar-right">
            <div className="navbar-status">
              <span className={`status-dot ${isOnline ? "online" : "offline"}`} />
              <span className="status-text">{isOnline ? "Online" : "Offline"}</span>
            </div>
            <NavbarUser />
          </div>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route index element={<AppHub />} />
          <Route
            path="content/*"
            element={<ContentShell refreshKey={refreshKey} onImportSuccess={bumpRefresh} />}
          />
          <Route
            path="variants"
            element={
              <Suspense fallback={<RouteLoader />}>
                <VariantBuilderAuto />
              </Suspense>
            }
          />
          <Route
            path="exercises"
            element={
              <Suspense fallback={<RouteLoader />}>
                <StudentExercises />
              </Suspense>
            }
          />
          <Route
            path="subiecte"
            element={
              <Suspense fallback={<RouteLoader />}>
                <SourceLibrary />
              </Suspense>
            }
          />
          <Route
            path="teacher/requests"
            element={
              <Suspense fallback={<RouteLoader />}>
                <TeacherDashboard />
              </Suspense>
            }
          />
          <Route
            path="my-requests"
            element={
              <Suspense fallback={<RouteLoader />}>
                <MyRequests />
              </Suspense>
            }
          />
          <Route
            path="study-session"
            element={
              <Suspense fallback={<RouteLoader />}>
                <StudySession />
              </Suspense>
            }
          />
          <Route
            path="study-plan"
            element={
              <Suspense fallback={<RouteLoader />}>
                <StudyPlan />
              </Suspense>
            }
          />
          <Route
            path="learning-path/*"
            element={
              <Suspense fallback={<RouteLoader />}>
                <LearningPath />
              </Suspense>
            }
          />
          <Route
            path="league"
            element={
              <Suspense fallback={<RouteLoader />}>
                <LeagueHub />
              </Suspense>
            }
          />
          <Route
            path="admin"
            element={
              <Suspense fallback={<RouteLoader />}>
                <AdminPanel />
              </Suspense>
            }
          />
          <Route
            path="parent"
            element={
              <Suspense fallback={<RouteLoader />}>
                <ParentDashboard />
              </Suspense>
            }
          />
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="footer-content">
          <div className="footer-left">
            <img src={BRAND_LOGO_URL} alt="EtoX" className="footer-logo" />
            <span>© 2026 EtoX Academy</span>
          </div>
          <div className="footer-right">Platforma de Generare Subiecte BAC</div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route
            path="/"
            element={
              <Suspense fallback={<RouteLoader />}>
                <LandingPage />
              </Suspense>
            }
          />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/app/*"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
