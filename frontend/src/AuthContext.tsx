import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authMe, getMyAccess, type User } from './api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isPremium: boolean;
  canHelpRequests: boolean;
  canDownloadPdf: boolean;
  canUnlimitedGen: boolean;
  isTeacher: boolean;
  isAdmin: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [access, setAccess] = useState({ can_help_requests: false, can_download_pdf: false, can_unlimited_gen: false });
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  const loadAccess = () => {
    getMyAccess()
      .then((res) => setAccess(res.data))
      .catch(() => {});
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    authMe()
      .then((userRes) => {
        setUser(userRes.data);
        loadAccess();
      })
      .catch(() => {
        localStorage.removeItem('access_token');
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const login = (newToken: string, newUser: User) => {
    localStorage.setItem('access_token', newToken);
    setToken(newToken);
    setUser(newUser);
    getMyAccess().then((res) => setAccess(res.data)).catch(() => {});
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
    setAccess({ can_help_requests: false, can_download_pdf: false, can_unlimited_gen: false });
  };

  const isStaff = !!user && (user.role === 'teacher' || user.role === 'school_teacher' || user.role === 'admin');

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isPremium: isStaff || access.can_help_requests || access.can_download_pdf || access.can_unlimited_gen,
        canHelpRequests: access.can_help_requests,
        canDownloadPdf: access.can_download_pdf,
        canUnlimitedGen: access.can_unlimited_gen,
        isTeacher: user?.role === 'teacher' || user?.role === 'admin',
        isAdmin: user?.role === 'admin',
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
