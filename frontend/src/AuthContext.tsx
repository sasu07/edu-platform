import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authMe, authMySubscription, type User, type Subscription } from './api';

interface AuthContextType {
  user: User | null;
  subscription: Subscription | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isPremium: boolean;       // are orice plan activ (help, pdf sau full)
  canHelpRequests: boolean; // poate trimite cereri de ajutor (premium_help sau full)
  isTeacher: boolean;
  isAdmin: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    // Verifică token-ul și încarcă datele utilizatorului
    authMe()
      .then((userRes) => {
        setUser(userRes.data);
        // Abonamentul e opțional — profesorii/adminii nu au subscription
        return authMySubscription().then((subRes) => setSubscription(subRes.data)).catch(() => {});
      })
      .catch(() => {
        // Doar authMe() eșuat înseamnă token invalid
        localStorage.removeItem('access_token');
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const login = (newToken: string, newUser: User) => {
    localStorage.setItem('access_token', newToken);
    setToken(newToken);
    setUser(newUser);
    // Încarcă abonamentul
    authMySubscription()
      .then((res) => setSubscription(res.data))
      .catch(() => setSubscription(null));
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
    setSubscription(null);
  };

  const isStaff = !!user && (user.role === 'teacher' || user.role === 'school_teacher' || user.role === 'admin');
  const activePlan = subscription?.status === 'active' ? subscription.plan_type : null;

  // are orice plan premium activ
  const isPremium = isStaff || ['premium', 'premium_help', 'premium_pdf', 'premium_gen'].includes(activePlan ?? '');

  // poate trimite cereri de ajutor
  const canHelpRequests = isStaff || ['premium', 'premium_help'].includes(activePlan ?? '');

  return (
    <AuthContext.Provider
      value={{
        user,
        subscription,
        token,
        login,
        logout,
        isPremium,
        canHelpRequests,
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
