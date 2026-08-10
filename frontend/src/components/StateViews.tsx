import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, RefreshCw } from 'lucide-react';
import './StateViews.css';

/* Componente comune de stare (brief §10) — folosite consecvent în ecranele simplificate. */

export function LoadingState({ lines = 3, label }: { lines?: number; label?: string }) {
  return (
    <div className="sv-loading" role="status" aria-live="polite" aria-label={label || 'Se încarcă'}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="sv-skeleton" style={{ width: `${100 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({
  icon, title, description, action,
}: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="sv-empty">
      {icon && <div className="sv-empty-icon">{icon}</div>}
      <div className="sv-empty-title">{title}</div>
      {description && <p className="sv-empty-desc">{description}</p>}
      {action && <div className="sv-empty-action">{action}</div>}
    </div>
  );
}

export function ErrorState({
  message = 'A apărut o eroare la încărcare.', onRetry, code,
}: { message?: string; onRetry?: () => void; code?: string }) {
  return (
    <div className="sv-error" role="alert">
      <AlertCircle size={22} className="sv-error-icon" />
      <div className="sv-error-body">
        <span>{message}</span>
        {code && <small className="sv-error-code">Cod: {code}</small>}
      </div>
      {onRetry && (
        <button className="sv-retry" onClick={onRetry}>
          <RefreshCw size={15} /> Reîncearcă
        </button>
      )}
    </div>
  );
}

/**
 * Acțiunea principală dominantă (brief §2.1). Un singur CTA evident, ca buton,
 * nu ca text sau card pasiv. Poate fi link (to) sau buton (onClick).
 */
export function PrimaryCTA({
  label, sublabel, icon, to, onClick, disabled, tone = 'primary',
}: {
  label: string;
  sublabel?: string;
  icon?: ReactNode;
  to?: string;
  onClick?: () => void;
  disabled?: boolean;
  tone?: 'primary' | 'neutral';
}) {
  const inner = (
    <>
      {icon && <span className="sv-cta-icon">{icon}</span>}
      <span className="sv-cta-text">
        <span className="sv-cta-label">{label}</span>
        {sublabel && <span className="sv-cta-sub">{sublabel}</span>}
      </span>
    </>
  );
  const cls = `sv-cta sv-cta-${tone}`;
  if (to && !disabled) return <Link to={to} className={cls}>{inner}</Link>;
  return (
    <button className={cls} onClick={onClick} disabled={disabled} type="button">
      {inner}
    </button>
  );
}
