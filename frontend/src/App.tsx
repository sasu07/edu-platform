import { useEffect, useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  NavLink,
  Navigate,
  useNavigate,
} from "react-router-dom";

import SourceList from "./components/SourceList";
import ExerciseList from "./components/ExerciseList";
import ExerciseEditor from "./components/ExerciseEditor";
import JSONImport from "./components/JSONImport";
import VariantBuilderAuto from "./components/VariantBuilderAuto";
import SourceDetails from "./components/SourceDetails";
import Login from "./components/Login";
import Register from "./components/Register";
import StudentExercises from "./components/StudentExercises";
import TeacherDashboard from "./components/TeacherDashboard";
import AdminPanel from "./components/AdminPanel";
import MyRequests from "./components/MyRequests";
import ParentDashboard from "./components/ParentDashboard";
import StudySession from "./components/StudySession";
import StudyPlan from "./components/StudyPlan";

import { AuthProvider, useAuth } from "./AuthContext";
import NotificationBell from "./components/NotificationBell";
import LandingPage from "./components/LandingPage";
import "./App.css";

// --- Route guard pentru utilizatori autentificați ---
function RequireAuth({ children }: { children: React.ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-loading">Se încarcă...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}


function AppHub() {
  const { user, isTeacher, isAdmin, isParent } = useAuth();
  if (isParent) return <Navigate to="/app/parent" replace />;
  return (
    <div className="hub">
      <header className="hub-head">
        <h1 className="hub-title">EtoXPlatform</h1>
        <p className="hub-subtitle">Bună ziua, {user?.full_name}! Alege zona în care vrei să lucrezi.</p>
      </header>

      <div className="hub-grid">
        {isTeacher && (
          <Link to="/app/content/import" className="hub-card">
            <div className="hub-card-title">Conținut</div>
            <div className="hub-card-sub">
              Import JSON + gestionare/verificare exerciții
            </div>
            <div className="hub-card-cta">Deschide →</div>
          </Link>
        )}

        <Link to="/app/exercises" className="hub-card">
          <div className="hub-card-title">Exerciții</div>
          <div className="hub-card-sub">
            Generează exerciții pe topic și verifică-ți soluțiile
          </div>
          <div className="hub-card-cta">Deschide →</div>
        </Link>

        {!isTeacher && (
          <Link to="/app/study-session" className="hub-card hub-card-session">
            <div className="hub-card-title">⚡ Sesiune de studiu</div>
            <div className="hub-card-sub">
              Test scurt (10 ex · 60 min) sau Test BAC (25 ex · 3h) cu timer live
            </div>
            <div className="hub-card-cta">Pornește →</div>
          </Link>
        )}

        {!isTeacher && (
          <Link to="/app/study-plan" className="hub-card hub-card-plan">
            <div className="hub-card-title">📅 Plan săptămânal</div>
            <div className="hub-card-sub">
              Planifică sesiunile de studiu și urmărește countdown-ul până la BAC
            </div>
            <div className="hub-card-cta">Deschide →</div>
          </Link>
        )}

        <Link to="/app/variants" className="hub-card">
          <div className="hub-card-title">Variante BAC</div>
          <div className="hub-card-sub">
            Generare automată subiecte tip BAC + download PDF
          </div>
          <div className="hub-card-cta">Deschide →</div>
        </Link>

        {isTeacher && (
          <Link to="/app/teacher/requests" className="hub-card">
            <div className="hub-card-title">Cereri de ajutor</div>
            <div className="hub-card-sub">
              Răspunde la flag-urile trimise de studenți
            </div>
            <div className="hub-card-cta">Deschide →</div>
          </Link>
        )}
        {isAdmin && (
          <Link to="/app/admin" className="hub-card hub-card-admin">
            <div className="hub-card-title">Administrator</div>
            <div className="hub-card-sub">
              Gestionează utilizatori și abonamente
            </div>
            <div className="hub-card-cta">Deschide →</div>
          </Link>
        )}
        {isParent && (
          <Link to="/app/parent" className="hub-card hub-card-parent">
            <div className="hub-card-title">Dashboard Progres</div>
            <div className="hub-card-sub">
              Urmărește activitatea și progresul elevului tău
            </div>
            <div className="hub-card-cta">Deschide →</div>
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
        <SourceList refreshKey={refreshKey} />
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
            <div className="content-grid single-column">
              <JSONImport onImportSuccess={onImportSuccess} />
            </div>
          }
        />
        <Route path="exercises" element={<ExerciseList refreshKey={refreshKey} />} />
        <Route path="exercises/:id" element={<ExerciseEditor />} />
        <Route path="sources/:sourceId" element={<SourceDetails />} />
        <Route path="sources" element={<SourcesPage refreshKey={refreshKey} />} />
        <Route path="*" element={<Navigate to="/app/content/import" replace />} />
      </Routes>
    </div>
  );
}

function NavbarUser() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!user) return null;

  return (
    <div className="navbar-user">
      <NotificationBell />
      <span className="navbar-user-name">{user.full_name}</span>
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
  const { isTeacher, isAdmin, isParent } = useAuth();

  const bumpRefresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch("http://localhost:8000/");
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
              src="/logo_etox.png"
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

          <div className="navbar-links">
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
                  to="/app/my-requests"
                  className={({ isActive }) =>
                    isActive ? "nav-link active" : "nav-link"
                  }
                >
                  Cererile mele
                </NavLink>
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
          <Route path="variants" element={<VariantBuilderAuto />} />
          <Route path="exercises" element={<StudentExercises />} />
          <Route path="teacher/requests" element={<TeacherDashboard />} />
          <Route path="my-requests" element={<MyRequests />} />
          <Route path="study-session" element={<StudySession />} />
          <Route path="study-plan" element={<StudyPlan />} />
          <Route path="admin" element={<AdminPanel />} />
          <Route path="parent" element={<ParentDashboard />} />
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="footer-content">
          <div className="footer-left">
            <img src="/logo_etox.png" alt="EtoX" className="footer-logo" />
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
          <Route path="/" element={<LandingPage />} />
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
