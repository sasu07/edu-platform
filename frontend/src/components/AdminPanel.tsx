import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  Crown,
  KeyRound,
  Link2,
  LockKeyhole,
  Mail,
  RefreshCw,
  Save,
  Search,
  Shield,
  UserCheck,
  UserPlus,
  Users,
  XCircle,
} from 'lucide-react';
import {
  adminGetParentStudents,
  adminLinkParentStudent,
  adminRemoveParentStudentLink,
  cancelSubscription,
  createAdminUser,
  getAdminUsers,
  requestAdminPasswordReset,
  updateAdminUserRole,
  upgradeSubscription,
  type AdminUser,
  type ManagedUserRole,
} from '../api';
import { useAuth } from '../AuthContext';
import AuditLog from './AuditLog';
import './AdminPanel.css';

const PLAN_LABELS: Record<string, string> = {
  premium: '👑 Full',
  premium_help: '✍️ Help',
  premium_pdf: '📄 PDF',
  premium_gen: '⚡ Gen',
  free: 'Free',
};

const PLANS = [
  { key: 'premium_help', label: '✍️ Help', title: 'Activează Premium Help (cereri ajutor)' },
  { key: 'premium_pdf', label: '📄 PDF', title: 'Activează Premium PDF (descărcare PDF)' },
  { key: 'premium_gen', label: '⚡ Gen', title: 'Activează Premium Gen (generare nelimitată)' },
  { key: 'premium', label: '👑 Full', title: 'Activează Premium Full (toate facilitățile)' },
];

const ROLE_OPTIONS: Array<{ value: ManagedUserRole; label: string }> = [
  { value: 'student', label: 'Elev' },
  { value: 'teacher', label: 'Profesor platformă' },
  { value: 'school_teacher', label: 'Profesor de școală' },
  { value: 'parent', label: 'Părinte' },
];

const ROLE_LABELS: Record<string, string> = {
  student: 'Elev',
  teacher: 'Profesor platformă',
  school_teacher: 'Profesor de școală',
  parent: 'Părinte',
  admin: 'Administrator',
};

interface ParentStudentLinkRow {
  id: string;
  parent_name: string;
  parent_email: string;
  student_name: string;
  student_email: string;
}

function getApiError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const firstMessage = detail.find((item) => typeof item === 'object' && item !== null && 'msg' in item) as { msg?: unknown } | undefined;
    if (typeof firstMessage?.msg === 'string') return firstMessage.msg;
  }
  return fallback;
}

function isManagedRole(role: string): role is ManagedUserRole {
  return ROLE_OPTIONS.some((option) => option.value === role);
}

function AdminParentSection({ users }: { users: AdminUser[] }) {
  const [links, setLinks] = useState<ParentStudentLinkRow[]>([]);
  const [loadingLinks, setLoadingLinks] = useState(true);
  const [parentId, setParentId] = useState('');
  const [studentId, setStudentId] = useState('');
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const loadLinks = useCallback(() => {
    setLoadingLinks(true);
    adminGetParentStudents()
      .then((response) => setLinks(Array.isArray(response.data) ? response.data : []))
      .catch(() => setMsg({ text: 'Legăturile nu au putut fi încărcate.', ok: false }))
      .finally(() => setLoadingLinks(false));
  }, []);

  useEffect(() => { loadLinks(); }, [loadLinks]);

  const parents = users.filter((user) => user.role === 'parent');
  const students = users.filter((user) => user.role === 'student');

  const handleAdd = async () => {
    if (!parentId || !studentId) return;
    setAdding(true);
    setMsg(null);
    try {
      await adminLinkParentStudent({ parent_id: parentId, student_id: studentId });
      setMsg({ text: 'Legătura părinte–elev a fost creată.', ok: true });
      setParentId('');
      setStudentId('');
      loadLinks();
    } catch (error: unknown) {
      setMsg({ text: getApiError(error, 'Legătura nu a putut fi creată.'), ok: false });
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (linkId: string) => {
    if (!window.confirm('Ștergi această legătură părinte–elev?')) return;
    try {
      await adminRemoveParentStudentLink(linkId);
      setLinks((current) => current.filter((link) => link.id !== linkId));
      setMsg({ text: 'Legătura a fost ștearsă.', ok: true });
    } catch (error: unknown) {
      setMsg({ text: getApiError(error, 'Legătura nu a putut fi ștearsă.'), ok: false });
    }
  };

  return (
    <section className="admin-section" aria-labelledby="parent-student-title">
      <h3 id="parent-student-title" className="admin-section-title">
        <Link2 size={18} /> Legături părinte–elev
      </h3>

      <div className="admin-parent-form">
        <label>
          <span>Părinte</span>
          <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
            <option value="">Selectează părintele</option>
            {parents.map((parent) => (
              <option key={parent.id} value={parent.id}>{parent.full_name} ({parent.email})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Elev</span>
          <select value={studentId} onChange={(event) => setStudentId(event.target.value)}>
            <option value="">Selectează elevul</option>
            {students.map((student) => (
              <option key={student.id} value={student.id}>{student.full_name} ({student.email})</option>
            ))}
          </select>
        </label>
        <button className="admin-btn admin-btn--primary" onClick={handleAdd} disabled={adding || !parentId || !studentId}>
          {adding ? 'Se salvează…' : 'Creează legătura'}
        </button>
      </div>

      {msg && <div className={`admin-msg ${msg.ok ? 'ok' : 'err'}`} role="status">{msg.text}</div>}
      {loadingLinks && <div className="admin-empty">Se încarcă legăturile…</div>}
      {!loadingLinks && links.length === 0 && <div className="admin-empty">Nu există legături active.</div>}

      <div className="admin-links-list">
        {links.map((link) => (
          <article key={link.id} className="admin-link-row">
            <div>
              <strong>{link.parent_name}</strong>
              <span>{link.parent_email}</span>
            </div>
            <span className="admin-link-arrow" aria-hidden="true">→</span>
            <div>
              <strong>{link.student_name}</strong>
              <span>{link.student_email}</span>
            </div>
            <button className="admin-btn admin-btn--danger admin-link-remove" onClick={() => handleRemove(link.id)}>
              <XCircle size={16} /> Șterge
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function AdminPanel() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [savingRole, setSavingRole] = useState<string | null>(null);
  const [resettingPassword, setResettingPassword] = useState<string | null>(null);
  const [roleDrafts, setRoleDrafts] = useState<Record<string, ManagedUserRole>>({});
  const [msg, setMsg] = useState<{ id: string; text: string; ok: boolean } | null>(null);

  const [showNewUser, setShowNewUser] = useState(false);
  const [newUser, setNewUser] = useState<{ full_name: string; email: string; role: ManagedUserRole }>({
    full_name: '',
    email: '',
    role: 'student',
  });
  const [createMsg, setCreateMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [creatingUser, setCreatingUser] = useState(false);

  const load = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setLoadError('');
    try {
      const response = await getAdminUsers();
      const nextUsers = Array.isArray(response.data) ? response.data : [];
      setUsers(nextUsers);
      setRoleDrafts((current) => {
        const next = { ...current };
        nextUsers.forEach((account) => {
          if (isManagedRole(account.role)) next[account.id] = account.role;
        });
        return next;
      });
    } catch (error: unknown) {
      setLoadError(getApiError(error, 'Utilizatorii nu au putut fi încărcați.'));
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const visibleUsers = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('ro-RO');
    return users.filter((account) => {
      const matchesQuery = !normalizedQuery
        || account.full_name.toLocaleLowerCase('ro-RO').includes(normalizedQuery)
        || account.email.toLocaleLowerCase('ro-RO').includes(normalizedQuery);
      const matchesRole = roleFilter === 'all' || account.role === roleFilter;
      return matchesQuery && matchesRole;
    });
  }, [query, roleFilter, users]);

  const handleCreateUser = async (event: FormEvent) => {
    event.preventDefault();
    setCreatingUser(true);
    setCreateMsg(null);
    try {
      await createAdminUser({
        full_name: newUser.full_name.trim(),
        email: newUser.email.trim().toLocaleLowerCase('ro-RO'),
        role: newUser.role,
      });
      setCreateMsg({ text: 'Contul a fost creat. Utilizatorul a primit linkul securizat pentru alegerea parolei.', ok: true });
      setNewUser({ full_name: '', email: '', role: 'student' });
      setShowNewUser(false);
      await load(false);
    } catch (error: unknown) {
      setCreateMsg({ text: getApiError(error, 'Contul nu a putut fi creat.'), ok: false });
      await load(false);
    } finally {
      setCreatingUser(false);
    }
  };

  const handleRoleChange = async (account: AdminUser) => {
    const nextRole = roleDrafts[account.id];
    const previousRole = isManagedRole(account.role) ? account.role : null;
    if (!nextRole || nextRole === account.role || account.role === 'admin' || account.id === currentUser?.id) return;
    const confirmed = window.confirm(
      `Schimbi rolul lui ${account.full_name} din „${ROLE_LABELS[account.role]}” în „${ROLE_LABELS[nextRole]}”? Utilizatorul va trebui să se autentifice din nou.`,
    );
    if (!confirmed) {
      if (previousRole) setRoleDrafts((current) => ({ ...current, [account.id]: previousRole }));
      return;
    }

    setSavingRole(account.id);
    setMsg(null);
    try {
      await updateAdminUserRole(account.id, nextRole);
      setMsg({ id: account.id, text: 'Rolul a fost actualizat, iar sesiunile vechi au fost închise.', ok: true });
      await load(false);
    } catch (error: unknown) {
      if (previousRole) setRoleDrafts((current) => ({ ...current, [account.id]: previousRole }));
      setMsg({ id: account.id, text: getApiError(error, 'Rolul nu a putut fi actualizat.'), ok: false });
    } finally {
      setSavingRole(null);
    }
  };

  const handlePasswordReset = async (account: AdminUser) => {
    if (account.role === 'admin' || (!account.is_active && !account.invite_pending)) return;
    const action = account.invite_pending ? 'activarea contului' : 'resetarea parolei';
    if (!window.confirm(`Trimiți către ${account.email} un link securizat pentru ${action}?`)) return;

    setResettingPassword(account.id);
    setMsg(null);
    try {
      await requestAdminPasswordReset(account.id);
      setMsg({ id: account.id, text: 'Linkul securizat a fost trimis pe email.', ok: true });
    } catch (error: unknown) {
      setMsg({ id: account.id, text: getApiError(error, 'Linkul nu a putut fi trimis.'), ok: false });
    } finally {
      setResettingPassword(null);
    }
  };

  const handleUpgrade = async (userId: string, planType: string) => {
    const key = `${userId}:${planType}`;
    setUpgrading(key);
    setMsg(null);
    try {
      await upgradeSubscription(userId, planType);
      const planLabel = PLANS.find((plan) => plan.key === planType)?.label ?? planType;
      setMsg({ id: userId, text: `Abonamentul ${planLabel} a fost activat.`, ok: true });
      await load(false);
    } catch (error: unknown) {
      setMsg({ id: userId, text: getApiError(error, 'Abonamentul nu a putut fi activat.'), ok: false });
    } finally {
      setUpgrading(null);
    }
  };

  const handleCancel = async (userId: string) => {
    if (!window.confirm('Dezactivezi toate abonamentele active ale acestui utilizator?')) return;
    setCancelling(userId);
    setMsg(null);
    try {
      await cancelSubscription(userId);
      setMsg({ id: userId, text: 'Abonamentele active au fost dezactivate.', ok: true });
      await load(false);
    } catch (error: unknown) {
      setMsg({ id: userId, text: getApiError(error, 'Abonamentele nu au putut fi dezactivate.'), ok: false });
    } finally {
      setCancelling(null);
    }
  };

  if (loading) return <div className="admin-panel admin-panel--loading">Se încarcă panoul de administrare…</div>;

  return (
    <main className="admin-panel">
      <header className="admin-header">
        <div>
          <span className="admin-eyebrow">Control central</span>
          <h1><Shield size={24} /> Administrare</h1>
          <p>Utilizatori, acces și legături — într-un singur loc.</p>
        </div>
        <button className="admin-btn admin-btn--secondary" onClick={() => void load(false)} aria-label="Reîncarcă datele">
          <RefreshCw size={17} /> <span>Reîncarcă</span>
        </button>
      </header>

      {loadError && <div className="admin-alert admin-alert--error" role="alert">{loadError}</div>}

      <section className="admin-section admin-create-section" aria-labelledby="create-user-title">
        <div className="admin-section-head">
          <div>
            <h2 id="create-user-title" className="admin-section-title"><UserPlus size={19} /> Utilizator nou</h2>
            <p className="admin-section-description">Fără parole temporare: utilizatorul își alege parola dintr-un link securizat primit pe email.</p>
          </div>
          <button
            className="admin-btn admin-btn--primary"
            onClick={() => { setShowNewUser((current) => !current); setCreateMsg(null); }}
            aria-expanded={showNewUser}
          >
            <UserPlus size={17} /> {showNewUser ? 'Închide formularul' : 'Creează utilizator'}
          </button>
        </div>

        {showNewUser && (
          <form className="admin-create-form" onSubmit={handleCreateUser}>
            <label>
              <span>Nume complet</span>
              <input
                value={newUser.full_name}
                onChange={(event) => setNewUser({ ...newUser, full_name: event.target.value })}
                placeholder="Ex. Maria Popescu"
                autoComplete="name"
                minLength={2}
                maxLength={120}
                required
              />
            </label>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={newUser.email}
                onChange={(event) => setNewUser({ ...newUser, email: event.target.value })}
                placeholder="maria@exemplu.ro"
                autoComplete="email"
                maxLength={254}
                required
              />
            </label>
            <label>
              <span>Rol inițial</span>
              <select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value as ManagedUserRole })}>
                {ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <button type="submit" className="admin-btn admin-btn--primary admin-create-submit" disabled={creatingUser}>
              <Mail size={17} /> {creatingUser ? 'Se creează…' : 'Creează și trimite invitația'}
            </button>
          </form>
        )}
        {createMsg && <div className={`admin-alert ${createMsg.ok ? 'admin-alert--success' : 'admin-alert--error'}`} role="status">{createMsg.text}</div>}
      </section>

      <section className="admin-section" aria-labelledby="users-title">
        <div className="admin-section-head admin-users-heading">
          <div>
            <h2 id="users-title" className="admin-section-title"><Users size={19} /> Utilizatori</h2>
            <p className="admin-section-description">{visibleUsers.length} din {users.length} conturi afișate</p>
          </div>
          <div className="admin-filters">
            <label className="admin-search">
              <Search size={17} aria-hidden="true" />
              <span className="sr-only">Caută utilizator</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Caută nume sau email" />
            </label>
            <label>
              <span className="sr-only">Filtrează după rol</span>
              <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
                <option value="all">Toate rolurile</option>
                {ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                <option value="admin">Administrator</option>
              </select>
            </label>
          </div>
        </div>

        <div className="admin-user-list">
          {visibleUsers.map((account) => {
            const protectedAccount = account.role === 'admin';
            const ownAccount = account.id === currentUser?.id;
            const draftRole = roleDrafts[account.id];
            const canSaveRole = !!draftRole && draftRole !== account.role && !protectedAccount && !ownAccount;
            const hasPlans = account.active_plans?.length > 0;
            const canManagePlans = account.role === 'student' || account.role === 'school_teacher';

            return (
              <article key={account.id} className="admin-user-card">
                <header className="admin-user-card-head">
                  <div className="admin-user-avatar" aria-hidden="true">{account.full_name.trim().charAt(0).toLocaleUpperCase('ro-RO') || '?'}</div>
                  <div className="admin-user-identity">
                    <h3>{account.full_name}</h3>
                    <a href={`mailto:${account.email}`}>{account.email}</a>
                  </div>
                  <div className="admin-user-badges">
                    <span className={`admin-role-badge admin-role-badge--${account.role}`}>{ROLE_LABELS[account.role] || account.role}</span>
                    <span className={`admin-status-badge ${account.is_active ? 'is-active' : 'is-inactive'}`}>
                      {account.is_active ? 'Activ' : account.invite_pending ? 'Invitație în așteptare' : 'Dezactivat'}
                    </span>
                  </div>
                </header>

                <div className="admin-user-meta">
                  <span>Creat la {new Date(account.created_at).toLocaleDateString('ro-RO', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
                  {ownAccount && <span>Acesta este contul tău</span>}
                </div>

                {protectedAccount ? (
                  <div className="admin-protected-note"><LockKeyhole size={16} /> Conturile de administrator sunt protejate și nu se modifică din această listă.</div>
                ) : (
                  <div className="admin-user-management">
                    <label className="admin-role-field">
                      <span>Rol</span>
                      <select
                        value={draftRole || account.role}
                        onChange={(event) => setRoleDrafts((current) => ({ ...current, [account.id]: event.target.value as ManagedUserRole }))}
                        disabled={ownAccount || savingRole === account.id}
                      >
                        {ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                      </select>
                    </label>
                    <button
                      className="admin-btn admin-btn--secondary"
                      onClick={() => void handleRoleChange(account)}
                      disabled={!canSaveRole || savingRole === account.id}
                    >
                      <Save size={16} /> {savingRole === account.id ? 'Se salvează…' : 'Salvează rolul'}
                    </button>
                    <button
                      className="admin-btn admin-btn--outline"
                      onClick={() => void handlePasswordReset(account)}
                      disabled={resettingPassword === account.id || (!account.is_active && !account.invite_pending)}
                      title={!account.is_active && !account.invite_pending ? 'Contul dezactivat nu poate fi reactivat prin resetarea parolei.' : undefined}
                    >
                      <KeyRound size={16} />
                      {resettingPassword === account.id
                        ? 'Se trimite…'
                        : account.invite_pending ? 'Retrimite invitația' : 'Trimite resetare parolă'}
                    </button>
                  </div>
                )}

                {canManagePlans && (
                  <details className="admin-plan-details">
                    <summary>Abonamente și acces</summary>
                    <div className="admin-plan-content">
                      {hasPlans ? (
                        <div className="admin-active-plans">
                          {account.active_plans.map((plan) => <span key={plan}>{PLAN_LABELS[plan] ?? plan}</span>)}
                        </div>
                      ) : <p>Niciun plan premium activ.</p>}
                      <div className="admin-plan-actions">
                        {PLANS.map((plan) => (
                          <button
                            key={plan.key}
                            className={`admin-btn admin-plan-btn ${account.active_plans?.includes(plan.key) ? 'is-active' : ''}`}
                            onClick={() => void handleUpgrade(account.id, plan.key)}
                            disabled={upgrading === `${account.id}:${plan.key}`}
                            title={plan.title}
                          >
                            <Crown size={15} /> {upgrading === `${account.id}:${plan.key}` ? '…' : plan.label}
                          </button>
                        ))}
                        {hasPlans && (
                          <button className="admin-btn admin-btn--danger" onClick={() => void handleCancel(account.id)} disabled={cancelling === account.id}>
                            <XCircle size={15} /> {cancelling === account.id ? 'Se dezactivează…' : 'Dezactivează toate'}
                          </button>
                        )}
                      </div>
                    </div>
                  </details>
                )}

                {msg?.id === account.id && <div className={`admin-alert ${msg.ok ? 'admin-alert--success' : 'admin-alert--error'}`} role="status">{msg.text}</div>}
              </article>
            );
          })}

          {visibleUsers.length === 0 && <div className="admin-empty">Nu am găsit utilizatori pentru filtrele alese.</div>}
        </div>
      </section>

      <section className="admin-section admin-info" aria-labelledby="plans-title">
        <h2 id="plans-title" className="admin-section-title"><UserCheck size={18} /> Planuri de abonament</h2>
        <ul>
          <li><strong>Free</strong> — accesul de bază al elevului</li>
          <li><strong>Premium Help</strong> — generare nelimitată și cereri de ajutor</li>
          <li><strong>Premium PDF</strong> — generare nelimitată și descărcare PDF</li>
          <li><strong>Premium Gen</strong> — exerciții și variante BAC nelimitate</li>
          <li><strong>Premium Full</strong> — toate facilitățile platformei</li>
        </ul>
      </section>

      <AdminParentSection users={users} />

      <section className="admin-section" aria-labelledby="audit-title">
        <h2 id="audit-title" className="admin-section-title"><Shield size={18} /> Jurnal de audit</h2>
        <AuditLog />
      </section>
    </main>
  );
}
