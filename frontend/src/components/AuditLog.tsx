import { useState, useEffect, type CSSProperties } from 'react';
import { getAuditLog } from '../api';

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
  details: any;
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

  const loadPage = (o: number) => {
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
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadPage(0); }, []);

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14, alignItems: 'center' }}>
        <input
          placeholder="Caută în path (ex: /exercises)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadPage(0)}
          style={inp}
        />
        <input
          placeholder="Acțiune (ex: login.fail)"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadPage(0)}
          style={inp}
        />
        <select value={since} onChange={(e) => setSince(e.target.value ? Number(e.target.value) : '')} style={inp}>
          <option value="">Oricând</option>
          <option value={1}>Ultima oră</option>
          <option value={24}>Ultimele 24h</option>
          <option value={168}>Ultimele 7 zile</option>
        </select>
        <button onClick={() => loadPage(0)} style={btn}>Filtrează</button>
        <span style={{ marginLeft: 'auto', color: '#6b7280', fontSize: 13 }}>{total} evenimente</span>
      </div>

      {loading ? (
        <div style={{ color: '#6b7280', padding: 20 }}>Se încarcă…</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>
                <th style={th}>Când</th>
                <th style={th}>Cine</th>
                <th style={th}>Acțiune</th>
                <th style={th}>Status</th>
                <th style={th}>Resursă</th>
                <th style={th}>IP</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} style={{ borderBottom: '1px solid #f1f3f5' }}>
                  <td style={{ ...td, whiteSpace: 'nowrap' }}>{new Date(it.created_at).toLocaleString('ro-RO')}</td>
                  <td style={td}>
                    {it.actor_email ? (
                      <span>{it.actor_email} <span style={{ color: '#9ca3af' }}>({it.actor_role})</span></span>
                    ) : (
                      <span style={{ color: '#9ca3af' }}>anonim{it.details?.email ? ` · ${it.details.email}` : ''}</span>
                    )}
                  </td>
                  <td style={{ ...td, fontFamily: 'monospace' }}>{it.action}</td>
                  <td style={td}>
                    <span style={{ color: statusColor(it.status), fontWeight: 700 }}>{it.status ?? '—'}</span>
                  </td>
                  <td style={{ ...td, fontFamily: 'monospace', color: '#6b7280' }}>
                    {it.resource_type || ''}{it.resource_id ? ` ${String(it.resource_id).slice(0, 8)}…` : ''}
                  </td>
                  <td style={{ ...td, fontFamily: 'monospace', color: '#9ca3af' }}>{it.ip || '—'}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ ...td, color: '#9ca3af', textAlign: 'center', padding: 24 }}>Niciun eveniment.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE && (
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 16, alignItems: 'center' }}>
          <button disabled={offset === 0} onClick={() => loadPage(Math.max(0, offset - PAGE))} style={btn}>← Înapoi</button>
          <span style={{ color: '#6b7280', fontSize: 13 }}>{offset + 1}–{Math.min(offset + PAGE, total)} din {total}</span>
          <button disabled={offset + PAGE >= total} onClick={() => loadPage(offset + PAGE)} style={btn}>Înainte →</button>
        </div>
      )}
    </div>
  );
}

const inp: CSSProperties = { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13 };
const btn: CSSProperties = { padding: '8px 14px', border: '1px solid #d1d5db', borderRadius: 8, background: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 600 };
const th: CSSProperties = { padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap' };
const td: CSSProperties = { padding: '8px 10px', verticalAlign: 'top' };
