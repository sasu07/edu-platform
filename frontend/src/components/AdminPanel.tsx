import { useState, useEffect } from 'react';
import { Shield, Crown, UserCheck, XCircle } from 'lucide-react';
import { getAdminUsers, upgradeSubscription, cancelSubscription } from '../api';
import './AdminPanel.css';

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  active_plan?: string;
  plan_expires_at?: string;
}

const PLAN_LABELS: Record<string, string> = {
  premium:      '👑 Full',
  premium_help: '✍️ Help',
  premium_pdf:  '📄 PDF',
  free:         'Free',
};

const ROLE_BADGE: Record<string, string> = {
  admin:          'badge-admin',
  teacher:        'badge-teacher',
  school_teacher: 'badge-teacher',
  student:        'badge-student',
};

const PLANS = [
  { key: 'premium_help', label: '✍️ Help', title: 'Activează Premium Help (cereri ajutor)' },
  { key: 'premium_pdf',  label: '📄 PDF',  title: 'Activează Premium PDF (descărcare PDF)' },
  { key: 'premium',      label: '👑 Full',  title: 'Activează Premium Full (toate facilitățile)' },
];

export default function AdminPanel() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ id: string; text: string; ok: boolean } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminUsers();
      setUsers(Array.isArray(res.data) ? res.data : []);
    } catch {
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleUpgrade = async (userId: string, planType: string) => {
    const key = `${userId}:${planType}`;
    setUpgrading(key);
    setMsg(null);
    try {
      await upgradeSubscription(userId, planType);
      const planLabel = PLANS.find(p => p.key === planType)?.label ?? planType;
      setMsg({ id: userId, text: `Abonament ${planLabel} activat!`, ok: true });
      load();
    } catch (err: any) {
      setMsg({ id: userId, text: err.response?.data?.detail || 'Eroare', ok: false });
    } finally {
      setUpgrading(null);
    }
  };

  const handleCancel = async (userId: string) => {
    setCancelling(userId);
    setMsg(null);
    try {
      await cancelSubscription(userId);
      setMsg({ id: userId, text: 'Abonament dezactivat.', ok: true });
      load();
    } catch (err: any) {
      setMsg({ id: userId, text: err.response?.data?.detail || 'Eroare', ok: false });
    } finally {
      setCancelling(null);
    }
  };

  if (loading) return <div className="admin-panel">Se încarcă...</div>;

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <h2><Shield size={20} /> Panou Administrator</h2>
        <button className="admin-refresh-btn" onClick={load}>Refresh</button>
      </div>

      <div className="admin-section">
        <h3 className="admin-section-title">Utilizatori înregistrați ({users.length})</h3>

        <div className="admin-users-table">
          <div className="admin-table-head">
            <span>Nume</span>
            <span>Email</span>
            <span>Rol</span>
            <span>Înregistrat</span>
            <span>Acțiuni</span>
          </div>

          {users.map((u) => (
            <div key={u.id} className="admin-table-row">
              <span className="admin-user-name">
                {u.full_name}
                {!u.is_active && <span className="admin-inactive-badge">Inactiv</span>}
              </span>
              <span className="admin-user-email">{u.email}</span>
              <span className={`navbar-user-badge ${ROLE_BADGE[u.role] || ''}`}>{u.role}</span>
              <span className="admin-user-date">
                {new Date(u.created_at).toLocaleDateString('ro-RO')}
              </span>
              <div className="admin-user-actions">
                {u.active_plan && (
                  <span className="admin-active-plan-badge" title={u.plan_expires_at ? `Expiră: ${new Date(u.plan_expires_at).toLocaleDateString('ro-RO')}` : 'Fără expirare'}>
                    {PLAN_LABELS[u.active_plan] ?? u.active_plan}
                  </span>
                )}
                {(u.role === 'student' || u.role === 'school_teacher') && PLANS.map((plan) => (
                  <button
                    key={plan.key}
                    className="admin-premium-btn"
                    onClick={() => handleUpgrade(u.id, plan.key)}
                    disabled={upgrading === `${u.id}:${plan.key}`}
                    title={plan.title}
                  >
                    <Crown size={14} />
                    {upgrading === `${u.id}:${plan.key}` ? '...' : plan.label}
                  </button>
                ))}
                {u.active_plan && u.active_plan !== 'free' && (u.role === 'student' || u.role === 'school_teacher') && (
                  <button
                    className="admin-cancel-btn"
                    onClick={() => handleCancel(u.id)}
                    disabled={cancelling === u.id}
                    title="Dezactivează abonamentul activ"
                  >
                    <XCircle size={14} />
                    {cancelling === u.id ? '...' : 'Dezactivează'}
                  </button>
                )}
                {msg?.id === u.id && (
                  <span className={`admin-msg ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</span>
                )}
              </div>
            </div>
          ))}

          {users.length === 0 && (
            <div className="admin-empty">Nu există utilizatori înregistrați.</div>
          )}
        </div>
      </div>

      <div className="admin-section admin-info">
        <h3 className="admin-section-title"><UserCheck size={16} /> Planuri de abonament</h3>
        <ul>
          <li><strong>Free</strong> — acces la exerciții + vizualizare rezolvări</li>
          <li><strong>✍️ Premium Help</strong> — cereri de ajutor profesorilor (scris, video, live Zoom)</li>
          <li><strong>📄 Premium PDF</strong> — descărcare PDF variante BAC</li>
          <li><strong>👑 Premium Full</strong> — toate facilitățile de mai sus</li>
          <li>Profesorii și adminii au implicit acces complet</li>
        </ul>
      </div>
    </div>
  );
}
