import { useState, useEffect } from 'react';
import { Shield, Crown, UserCheck, XCircle, UserPlus, Link2 } from 'lucide-react';
import {
  getAdminUsers, upgradeSubscription, cancelSubscription, createTeacher,
  adminGetParentStudents, adminLinkParentStudent, adminRemoveParentStudentLink,
} from '../api';
import AuditLog from './AuditLog';
import './AdminPanel.css';

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  active_plans: string[];
}

const PLAN_LABELS: Record<string, string> = {
  premium:      '👑 Full',
  premium_help: '✍️ Help',
  premium_pdf:  '📄 PDF',
  premium_gen:  '⚡ Gen',
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
  { key: 'premium_gen',  label: '⚡ Gen',  title: 'Activează Premium Gen (generare nelimitată exerciții + variante BAC)' },
  { key: 'premium',      label: '👑 Full',  title: 'Activează Premium Full (toate facilitățile)' },
];

function AdminParentSection({ users }: { users: UserRow[] }) {
  const [links, setLinks] = useState<any[]>([]);
  const [loadingLinks, setLoadingLinks] = useState(true);
  const [parentId, setParentId] = useState('');
  const [studentId, setStudentId] = useState('');
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const loadLinks = () => {
    setLoadingLinks(true);
    adminGetParentStudents()
      .then(r => setLinks(r.data))
      .catch(() => {})
      .finally(() => setLoadingLinks(false));
  };

  useEffect(() => { loadLinks(); }, []);

  const parents = users.filter(u => u.role === 'parent');
  const students = users.filter(u => u.role === 'student' || u.role === 'school_teacher');

  const handleAdd = async () => {
    if (!parentId || !studentId) return;
    setAdding(true); setMsg(null);
    try {
      await adminLinkParentStudent({ parent_id: parentId, student_id: studentId });
      setMsg({ text: 'Legătură creată.', ok: true });
      setParentId(''); setStudentId('');
      loadLinks();
    } catch (e: any) {
      setMsg({ text: e?.response?.data?.detail || 'Eroare.', ok: false });
    } finally { setAdding(false); }
  };

  const handleRemove = async (linkId: string) => {
    try {
      await adminRemoveParentStudentLink(linkId);
      setLinks(l => l.filter(x => x.id !== linkId));
    } catch { /* ignore */ }
  };

  return (
    <div className="admin-section">
      <h3 className="admin-section-title"><Link2 size={16} /> Legătură Părinte–Elev</h3>

      <div className="admin-parent-form">
        <select className="admin-select" value={parentId} onChange={e => setParentId(e.target.value)}>
          <option value="">— Selectează părinte —</option>
          {parents.map(p => <option key={p.id} value={p.id}>{p.full_name} ({p.email})</option>)}
        </select>
        <select className="admin-select" value={studentId} onChange={e => setStudentId(e.target.value)}>
          <option value="">— Selectează elev —</option>
          {students.map(s => <option key={s.id} value={s.id}>{s.full_name} ({s.email})</option>)}
        </select>
        <button className="admin-btn" onClick={handleAdd} disabled={adding || !parentId || !studentId}>
          {adding ? '...' : '+ Leagă'}
        </button>
      </div>
      {msg && <div className={`admin-msg ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</div>}

      {loadingLinks && <div className="admin-empty">Se încarcă...</div>}
      {!loadingLinks && links.length === 0 && <div className="admin-empty">Nicio legătură activă.</div>}
      <div className="admin-links-list">
        {links.map(l => (
          <div key={l.id} className="admin-link-row">
            <span className="admin-link-parent">👨‍👩‍👧 {l.parent_name} <small>({l.parent_email})</small></span>
            <span className="admin-link-arrow">→</span>
            <span className="admin-link-student">🎓 {l.student_name} <small>({l.student_email})</small></span>
            <button className="admin-cancel-btn" onClick={() => handleRemove(l.id)} title="Șterge legătura">
              <XCircle size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AdminPanel() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ id: string; text: string; ok: boolean } | null>(null);

  const [showNewTeacher, setShowNewTeacher] = useState(false);
  const [newTeacher, setNewTeacher] = useState({ full_name: '', email: '', password: '' });
  const [teacherMsg, setTeacherMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [creatingTeacher, setCreatingTeacher] = useState(false);

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

  const handleCreateTeacher = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingTeacher(true);
    setTeacherMsg(null);
    try {
      await createTeacher(newTeacher);
      setTeacherMsg({ text: 'Cont profesor creat cu succes.', ok: true });
      setNewTeacher({ full_name: '', email: '', password: '' });
      setShowNewTeacher(false);
      load();
    } catch (err: any) {
      setTeacherMsg({ text: err.response?.data?.detail || 'Eroare', ok: false });
    } finally {
      setCreatingTeacher(false);
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
        <div className="admin-section-head">
          <h3 className="admin-section-title">Profesori platformă</h3>
          <button className="admin-add-teacher-btn" onClick={() => setShowNewTeacher(v => !v)}>
            <UserPlus size={15} />
            {showNewTeacher ? 'Anulează' : 'Adaugă profesor'}
          </button>
        </div>

        {showNewTeacher && (
          <form className="admin-new-teacher-form" onSubmit={handleCreateTeacher}>
            <div className="admin-nt-fields">
              <input
                placeholder="Nume complet"
                value={newTeacher.full_name}
                onChange={e => setNewTeacher({ ...newTeacher, full_name: e.target.value })}
                required
              />
              <input
                type="email"
                placeholder="Email"
                value={newTeacher.email}
                onChange={e => setNewTeacher({ ...newTeacher, email: e.target.value })}
                required
              />
              <input
                type="password"
                placeholder="Parolă temporară"
                value={newTeacher.password}
                onChange={e => setNewTeacher({ ...newTeacher, password: e.target.value })}
                required
                minLength={6}
              />
              <button type="submit" className="admin-premium-btn" disabled={creatingTeacher}>
                {creatingTeacher ? '...' : 'Creează cont'}
              </button>
            </div>
            {teacherMsg && (
              <span className={`admin-msg ${teacherMsg.ok ? 'ok' : 'err'}`}>{teacherMsg.text}</span>
            )}
          </form>
        )}
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
                {u.active_plans?.length > 0 && u.active_plans.map((plan) => (
                  <span key={plan} className="admin-active-plan-badge">
                    {PLAN_LABELS[plan] ?? plan}
                  </span>
                ))}
                {(u.role === 'student' || u.role === 'school_teacher') && PLANS.map((plan) => (
                  <button
                    key={plan.key}
                    className={`admin-premium-btn ${u.active_plans?.includes(plan.key) ? 'admin-premium-btn--active' : ''}`}
                    onClick={() => handleUpgrade(u.id, plan.key)}
                    disabled={upgrading === `${u.id}:${plan.key}`}
                    title={u.active_plans?.includes(plan.key) ? `${plan.title} (deja activ)` : plan.title}
                  >
                    <Crown size={14} />
                    {upgrading === `${u.id}:${plan.key}` ? '...' : plan.label}
                  </button>
                ))}
                {u.active_plans?.length > 0 && (u.role === 'student' || u.role === 'school_teacher') && (
                  <button
                    className="admin-cancel-btn"
                    onClick={() => handleCancel(u.id)}
                    disabled={cancelling === u.id}
                    title="Dezactivează toate abonamentele active"
                  >
                    <XCircle size={14} />
                    {cancelling === u.id ? '...' : 'Dezactivează tot'}
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
          <li><strong>Free</strong> — 3 generări exerciții/lună · 1 variantă BAC/lună · vizualizare rezolvări</li>
          <li><strong>✍️ Premium Help</strong> — generare nelimitată + cereri de ajutor (scris, video, live Zoom)</li>
          <li><strong>📄 Premium PDF</strong> — generare nelimitată + descărcare PDF variante BAC</li>
          <li><strong>⚡ Premium Gen</strong> — generare nelimitată exerciții + variante BAC nelimitate + PDF</li>
          <li><strong>👑 Premium Full</strong> — toate facilitățile: generare, PDF, ajutor profesori, sesiuni live</li>
          <li>Profesorii platformă și adminii au implicit acces complet</li>
        </ul>
      </div>

      <AdminParentSection users={users} />

      <div className="admin-section">
        <h3 className="admin-section-title"><Shield size={16} /> Jurnal de audit</h3>
        <AuditLog />
      </div>
    </div>
  );
}
