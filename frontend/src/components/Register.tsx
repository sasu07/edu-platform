import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authRegister } from '../api';
import { useAuth } from '../AuthContext';

export default function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'student',
    school_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authRegister(form);
      login(res.data.access_token, res.data.user);
      // Elevii noi intră direct în testul diagnostic (→ plan personalizat pe baza scorului).
      // Profesorii de școală merg în platformă (diagnosticul nu li se aplică).
      navigate(res.data.user.role === 'student' ? '/app/learning-path' : '/app');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Eroare la înregistrare');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">EX</div>
        <h1 className="auth-title">Creează cont</h1>
        <p className="auth-subtitle">EtoX Platform</p>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="auth-field">
            <label>Nume complet</label>
            <input
              name="full_name"
              type="text"
              value={form.full_name}
              onChange={handleChange}
              placeholder="Ion Popescu"
              required
              autoFocus
            />
          </div>

          <div className="auth-field">
            <label>Email</label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="email@exemplu.com"
              required
            />
          </div>

          <div className="auth-field">
            <label>Parolă</label>
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="Minim 8 caractere"
              required
              minLength={8}
            />
          </div>

          <div className="auth-field">
            <label>Tip cont</label>
            <select name="role" value={form.role} onChange={handleChange}>
              <option value="student">Student</option>
              <option value="school_teacher">Profesor de școală</option>
            </select>
          </div>

          {form.role === 'school_teacher' && (
            <div className="auth-field">
              <label>Instituție / Școală</label>
              <input
                name="school_name"
                type="text"
                value={form.school_name}
                onChange={handleChange}
                placeholder="Ex: Colegiul Național Mihai Eminescu"
              />
              <span style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 2 }}>
                Plan Free: 3 generări exerciții/lună · 1 variantă BAC/lună · Premium Gen: nelimitat
              </span>
            </div>
          )}

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? 'Se creează contul...' : 'Creează cont'}
          </button>
        </form>

        <p className="auth-footer">
          Ai deja cont?{' '}
          <Link to="/login" className="auth-link">
            Intră în cont
          </Link>
        </p>
      </div>
    </div>
  );
}
