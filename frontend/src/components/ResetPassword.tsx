import { useLayoutEffect, useState, type FormEvent } from 'react';
import { Check, CheckCircle2, Eye, EyeOff, KeyRound, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { completePasswordReset } from '../api';
import { BRAND_LOGO_URL } from '../brand';
import './ResetPassword.css';

function getApiError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const firstMessage = detail.find((item) => typeof item === 'object' && item !== null && 'msg' in item) as { msg?: unknown } | undefined;
    if (typeof firstMessage?.msg === 'string') return firstMessage.msg;
  }
  return 'Linkul nu a putut fi folosit. Cere administratorului un link nou.';
}

export default function ResetPassword() {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token')?.trim() || '');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useLayoutEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, document.title, `${window.location.pathname}${window.location.search}`);
    }
  }, []);

  const checks = {
    length: password.length >= 12,
    letter: /[A-Za-zĂÂÎȘȚăâîșț]/.test(password),
    number: /\d/.test(password),
  };
  const validPassword = checks.length && checks.letter && checks.number;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (!token) {
      setError('Linkul este incomplet. Cere administratorului o invitație nouă.');
      return;
    }
    if (!validPassword) {
      setError('Alege o parolă care respectă toate cerințele.');
      return;
    }
    if (password !== confirmation) {
      setError('Parolele introduse nu coincid.');
      return;
    }

    setLoading(true);
    try {
      await completePasswordReset({ token, new_password: password });
      setPassword('');
      setConfirmation('');
      setSuccess(true);
    } catch (requestError: unknown) {
      setError(getApiError(requestError));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="reset-page">
      <div className="reset-shell">
        <Link to="/" className="reset-brand" aria-label="Înapoi la e2x Academy">
          <img src={BRAND_LOGO_URL} alt="e2x Academy" />
        </Link>

        <section className="reset-card" aria-labelledby="reset-title">
          {success ? (
            <div className="reset-success" role="status">
              <span className="reset-icon reset-icon--success"><CheckCircle2 size={30} /></span>
              <h1 id="reset-title">Parola este pregătită</h1>
              <p>Contul tău este activ, iar sesiunile vechi au fost închise. Te poți autentifica în siguranță.</p>
              <Link to="/login" className="reset-primary-link">Intră în cont</Link>
            </div>
          ) : (
            <>
              <span className="reset-icon"><KeyRound size={28} /></span>
              <div className="reset-heading">
                <span><ShieldCheck size={16} /> Link securizat</span>
                <h1 id="reset-title">{token ? 'Alege o parolă nouă' : 'Link incomplet'}</h1>
                <p>
                  {token
                    ? 'Folosește o parolă unică, pe care nu o mai utilizezi pentru alt cont.'
                    : 'Acest link nu conține informațiile necesare pentru activarea contului.'}
                </p>
              </div>

              {token ? (
                <form className="reset-form" onSubmit={handleSubmit}>
                  <label>
                    <span>Parolă nouă</span>
                    <div className="reset-password-field">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        minLength={12}
                        maxLength={64}
                        autoComplete="new-password"
                        autoFocus
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((visible) => !visible)}
                        aria-label={showPassword ? 'Ascunde parola' : 'Arată parola'}
                      >
                        {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                      </button>
                    </div>
                  </label>

                  <div className="reset-requirements" aria-label="Cerințe parolă">
                    <span className={checks.length ? 'is-valid' : ''}><Check size={15} /> Minimum 12 caractere</span>
                    <span className={checks.letter ? 'is-valid' : ''}><Check size={15} /> Cel puțin o literă</span>
                    <span className={checks.number ? 'is-valid' : ''}><Check size={15} /> Cel puțin o cifră</span>
                  </div>

                  <label>
                    <span>Confirmă parola</span>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={confirmation}
                      onChange={(event) => setConfirmation(event.target.value)}
                      minLength={12}
                      maxLength={64}
                      autoComplete="new-password"
                      required
                    />
                  </label>

                  {error && <div className="reset-error" role="alert">{error}</div>}

                  <button type="submit" className="reset-submit" disabled={loading || !validPassword || password !== confirmation}>
                    {loading ? 'Se salvează în siguranță…' : 'Salvează parola'}
                  </button>
                </form>
              ) : (
                <div className="reset-missing">
                  <p>Cere administratorului să retrimită invitația sau linkul de resetare.</p>
                  <Link to="/login" className="reset-primary-link">Înapoi la autentificare</Link>
                </div>
              )}
            </>
          )}
        </section>

        <p className="reset-footnote">e2x Academy · Parola și linkul tău nu sunt vizibile administratorului.</p>
      </div>
    </main>
  );
}
