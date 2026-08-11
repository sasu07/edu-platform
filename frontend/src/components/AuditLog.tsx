import { useCallback, useEffect, useState } from 'react';
import { getAuditLog } from '../api';
import './AuditLog.css';

interface AuditItem {
  id: number;
  created_at: string;
  actor_role: string | null;
  actor_email: string | null;
  action: string;
  method: string | null;
  path: string | null;
  resource_type: string | null;
  resource_id: string | null;
  ip: string | null;
  status: number | null;
  details: Record<string, unknown> | null;
}

const PAGE = 50;

function statusColor(s: number | null): string {
  if (s == null) return '#6b7280';
  if (s === 401 || s === 403 || s >= 500) return '#dc2626';
  if (s >= 400) return '#d97706';
  if (s >= 200 && s < 300) return '#16a34a';
  return '#6b7280';
}

export default function AuditLog() {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [action, setAction] = useState('');
  const [since, setSince] = useState<number | ''>('');

  const loadPage = useCallback((o: number) => {
    setLoading(true);
    setOffset(o);
    getAuditLog({
      limit: PAGE,
      offset: o,
      q: q || undefined,
      action: action || undefined,
      since_hours: since || undefined,
    })
      .then((r) => {
        setItems(r.data.items);
        setTotal(r.data.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [action, q, since]);

  useEffect(() => {
    setLoading(true);
    getAuditLog({ limit: PAGE, offset: 0 })
      .then((response) => {
        setItems(response.data.items);
        setTotal(response.data.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="audit-log">
      <div className="audit-filters">
        <input
          placeholder="Caută în path (ex: /exercises)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadPage(0)}
          aria-label="Caută în cale"
        />
        <input
          placeholder="Acțiune (ex: login.fail)"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadPage(0)}
          aria-label="Caută după acțiune"
        />
        <select value={since} onChange={(e) => setSince(e.target.value ? Number(e.target.value) : '')} aria-label="Interval audit">
          <option value="">Oricând</option>
          <option value={1}>Ultima oră</option>
          <option value={24}>Ultimele 24h</option>
          <option value={168}>Ultimele 7 zile</option>
        </select>
        <button className="audit-filter-button" onClick={() => loadPage(0)}>Filtrează</button>
        <span className="audit-total">{total} evenimente</span>
      </div>

      {loading ? (
        <div className="audit-loading">Se încarcă…</div>
      ) : (
        <div className="audit-table-wrap">
          <table className="audit-table">
            <thead>
              <tr>
                <th>Când</th>
                <th>Cine</th>
                <th>Acțiune</th>
                <th>Status</th>
                <th>Resursă</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id}>
                  <td data-label="Când" className="audit-date">{new Date(it.created_at).toLocaleString('ro-RO')}</td>
                  <td data-label="Cine">
                    {it.actor_email ? (
                      <span>{it.actor_email} <span className="audit-muted">({it.actor_role})</span></span>
                    ) : (
                      <span className="audit-muted">
                        anonim{typeof it.details?.email === 'string' ? ` · ${it.details.email}` : ''}
                      </span>
                    )}
                  </td>
                  <td data-label="Acțiune" className="audit-mono">{it.action}</td>
                  <td data-label="Status">
                    <span className="audit-status" style={{ color: statusColor(it.status) }}>{it.status ?? '—'}</span>
                  </td>
                  <td data-label="Resursă" className="audit-mono audit-muted">
                    {it.resource_type || ''}{it.resource_id ? ` ${String(it.resource_id).slice(0, 8)}…` : ''}
                  </td>
                  <td data-label="IP" className="audit-mono audit-muted">{it.ip || '—'}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr className="audit-empty-row">
                  <td colSpan={6}>Niciun eveniment.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE && (
        <div className="audit-pagination">
          <button disabled={offset === 0} onClick={() => loadPage(Math.max(0, offset - PAGE))}>← Înapoi</button>
          <span>{offset + 1}–{Math.min(offset + PAGE, total)} din {total}</span>
          <button disabled={offset + PAGE >= total} onClick={() => loadPage(offset + PAGE)}>Înainte →</button>
        </div>
      )}
    </div>
  );
}
