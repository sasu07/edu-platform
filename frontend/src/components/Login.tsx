import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authLogin } from '../api';
import { useAuth } from '../AuthContext';
import { BRAND_LOGO_URL } from '../brand';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authLogin({ email, password });
      login(res.data.access_token, res.data.user);
      navigate(res.data.user.role === 'parent' ? '/app/parent' : '/app');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Email sau parolă incorectă');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-logo-link" aria-label="Înapoi la e2x Academy">
          <img src={BRAND_LOGO_URL} alt="e2x Academy" className="auth-brand-logo" />
        </Link>
        <h1 className="auth-title">Intră în cont</h1>
        <p className="auth-subtitle">e2x Platform</p>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="auth-field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@exemplu.com"
              required
              autoFocus
            />
          </div>

          <div className="auth-field">
            <label>Parolă</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Parola ta"
              required
            />
          </div>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? 'Se conectează...' : 'Intră în cont'}
          </button>
        </form>

        <p className="auth-footer">
          Nu ai cont?{' '}
          <Link to="/register" className="auth-link">
            Înregistrează-te
          </Link>
        </p>
      </div>
    </div>
  );
}
