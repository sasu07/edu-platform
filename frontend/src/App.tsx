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

import { AuthProvider, useAuth } from "./AuthContext";
import NotificationBell from "./components/NotificationBell";
import "./App.css";

// --- Route guard pentru utilizatori autentificați ---
function RequireAuth({ children }: { children: React.ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-loading">Se încarcă...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function LandingPage() {
  const { user } = useAuth();
  return (
    <div className="landing">
      <div className="landing-top">
        <div className="landing-brand">
          <div className="landing-logo" aria-hidden>
            EX
          </div>
          <div className="landing-brand-text">
            <div className="landing-brand-title">EtoX Platform</div>
            <div className="landing-brand-sub">
              Platforma de Generare Subiecte BAC
            </div>
          </div>
        </div>

        <div className="landing-actions">
          {user ? (
            <Link to="/app" className="landing-btn landing-btn-primary">
              Intră în platformă
            </Link>
          ) : (
            <>
              <Link to="/login" className="landing-btn landing-btn-primary">
                Intră în cont
              </Link>
              <Link to="/register" className="landing-btn landing-btn-ghost">
                Creează cont
              </Link>
            </>
          )}
        </div>
      </div>

      <div className="landing-hero">
        <div className="landing-hero-content">
          <h1 className="landing-title">
            Construiește, verifică și generează subiecte – rapid și curat.
          </h1>
          <p className="landing-subtitle">
            Import JSON OCR, verificare exerciții, generare variante și export PDF.
          </p>

          <div className="landing-cta">
            <Link
              to={user ? "/app" : "/login"}
              className="landing-btn landing-btn-primary landing-btn-lg"
            >
              Începe acum
            </Link>
          </div>
        </div>

        <div className="landing-panel">
          <div className="landing-panel-card">
            <div className="landing-panel-title">Flux recomandat</div>
            <ul className="landing-list">
              <li>1) Import JSON (OCR) + tag-uri + soluții/barem</li>
              <li>2) Verificare și editare exerciții</li>
              <li>3) Generare variante + export PDF</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="landing-footer">
        <div className="landing-footer-left">© 2026 EtoX Academy</div>
        <div className="landing-footer-right">EtoXPlatform • Admin UI</div>
      </div>
    </div>
  );
}

function AppHub() {
  const { user, isTeacher, isAdmin } = useAuth();
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
  const { isTeacher, isAdmin } = useAuth();

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
          <Route path="admin" element={<AdminPanel />} />
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
