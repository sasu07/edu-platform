import { useState, useEffect } from 'react';
import { CheckCircle, UserCheck, Send, Upload, BarChart2, Clock, MessageSquare, ChevronDown } from 'lucide-react';
import {
  pendingHelpRequests,
  assignHelpRequest,
  respondToHelpRequest,
  getTeacherStats,
  type TeacherStats,
} from '../api';
import { useAuth } from '../AuthContext';
import api from '../api';
import './TeacherDashboard.css';

const FLAG_LABELS: Record<string, { icon: string; label: string }> = {
  WRITTEN: { icon: '✍️', label: 'Rezolvare scrisă' },
  VIDEO:   { icon: '🎥', label: 'Rezolvare video' },
  LIVE:    { icon: '🎙️', label: 'Sesiune live' },
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'În așteptare',
  assigned: 'Preluat',
  resolved: 'Rezolvat',
};

interface Request {
  id: string;
  flag_type: 'WRITTEN' | 'VIDEO' | 'LIVE';
  status: string;
  notes?: string;
  created_at: string;
  student_name: string;
  student_email: string;
  statement_latex: string;
  difficulty?: number;
  points?: number;
  exercise_path?: string;
  exercise_id: string;
  assigned_teacher_id?: string;
}

interface RespondFormProps {
  request: Request;
  onDone: () => void;
}

function RespondForm({ request, onDone }: RespondFormProps) {
  const [contentText, setContentText] = useState('');
  const [zoomLink, setZoomLink] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await respondToHelpRequest(request.id, {
        content_text: contentText || undefined,
        zoom_link: zoomLink || undefined,
        scheduled_at: scheduledAt || undefined,
      });
      onDone();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Eroare la trimitere');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="respond-form" onSubmit={handleSubmit}>
      {request.flag_type === 'WRITTEN' && (
        <div className="respond-field">
          <label>Rezolvare detaliată</label>
          <textarea
            value={contentText}
            onChange={(e) => setContentText(e.target.value)}
            placeholder="Scrie rezolvarea passo cu passo..."
            rows={6}
            required
          />
        </div>
      )}

      {request.flag_type === 'VIDEO' && (
        <div className="respond-field">
          <label>Mesaj pentru student (opțional)</label>
          <textarea
            value={contentText}
            onChange={(e) => setContentText(e.target.value)}
            placeholder="Ex: Am înregistrat explicația, o poți găsi atașată..."
            rows={3}
          />
          <div className="respond-video-note">
            <Upload size={14} />
            Upload video — disponibil în curând
          </div>
        </div>
      )}

      {request.flag_type === 'LIVE' && (
        <>
          <div className="respond-field">
            <label>Link Zoom</label>
            <input
              type="url"
              value={zoomLink}
              onChange={(e) => setZoomLink(e.target.value)}
              placeholder="https://zoom.us/j/..."
              required
            />
          </div>
          <div className="respond-field">
            <label>Data și ora sesiunii</label>
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
            />
          </div>
          <div className="respond-field">
            <label>Mesaj (opțional)</label>
            <textarea
              value={contentText}
              onChange={(e) => setContentText(e.target.value)}
              placeholder="Ex: Ne întâlnim la ora indicată pe linkul de mai sus..."
              rows={2}
            />
          </div>
        </>
      )}

      {error && <div className="respond-error">{error}</div>}

      <div className="respond-actions">
        <button type="submit" className="respond-submit-btn" disabled={loading}>
          <Send size={15} />
          {loading ? 'Se trimite...' : 'Trimite răspunsul'}
        </button>
      </div>
    </form>
  );
}

const FLAG_TYPE_LABELS: Record<string, string> = {
  WRITTEN: '✍️ Scris',
  VIDEO: '🎥 Video',
  LIVE: '🎙️ Live',
};

function StatsPanel({ stats, showAvgTime }: { stats: TeacherStats; showAvgTime: boolean }) {
  const resolvedPct = stats.total_requests > 0
    ? Math.round((stats.resolved / stats.total_requests) * 100)
    : 0;

  return (
    <div className="teacher-stats-panel">
      <div className="teacher-stats-title">
        <BarChart2 size={18} /> Statistici
      </div>
      <div className="teacher-stats-grid">
        <div className="teacher-stat-card">
          <div className="teacher-stat-value">{stats.total_requests}</div>
          <div className="teacher-stat-label">Total cereri</div>
        </div>
        <div className="teacher-stat-card stat-pending">
          <div className="teacher-stat-value">{stats.pending}</div>
          <div className="teacher-stat-label">În așteptare</div>
        </div>
        <div className="teacher-stat-card stat-assigned">
          <div className="teacher-stat-value">{stats.assigned}</div>
          <div className="teacher-stat-label">Preluate</div>
        </div>
        <div className="teacher-stat-card stat-resolved">
          <div className="teacher-stat-value">{stats.resolved}</div>
          <div className="teacher-stat-label">Rezolvate</div>
        </div>
        {showAvgTime && stats.avg_response_hours != null && (
          <div className="teacher-stat-card">
            <div className="teacher-stat-value">
              <Clock size={16} style={{ display: 'inline', marginRight: 4 }} />
              {stats.avg_response_hours}h
            </div>
            <div className="teacher-stat-label">Timp mediu răspuns</div>
          </div>
        )}
        {stats.total_requests > 0 && (
          <div className="teacher-stat-card">
            <div className="teacher-stat-value">{resolvedPct}%</div>
            <div className="teacher-stat-label">Rată rezolvare</div>
          </div>
        )}
      </div>
      {Object.keys(stats.by_type).length > 0 && (
        <div className="teacher-stats-by-type">
          <div className="teacher-stats-by-type-title">
            <MessageSquare size={14} /> Cereri pe tip
          </div>
          <div className="teacher-by-type-list">
            {Object.entries(stats.by_type).map(([type, cnt]) => (
              <span key={type} className="teacher-type-pill">
                {FLAG_TYPE_LABELS[type] || type}: <strong>{cnt}</strong>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface TeacherOption { id: string; full_name: string; email: string; }

export default function TeacherDashboard() {
  const { isAdmin } = useAuth();
  const [requests, setRequests] = useState<Request[]>([]);
  const [stats, setStats] = useState<TeacherStats | null>(null);
  const [teachers, setTeachers] = useState<TeacherOption[]>([]);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [respondingId, setRespondingId] = useState<string | null>(null);

  // Admin: fetch lista de profesori la mount
  useEffect(() => {
    if (!isAdmin) return;
    api.get<TeacherOption[]>('/admin/teachers')
      .then((res) => setTeachers(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, [isAdmin]);

  const loadStats = async (teacherId?: string) => {
    try {
      const params = teacherId ? { teacher_id: teacherId } : undefined;
      const res = await getTeacherStats(params);
      setStats(res.data);
    } catch {
      setStats(null);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const [reqRes] = await Promise.allSettled([pendingHelpRequests()]);
      if (reqRes.status === 'fulfilled') setRequests(Array.isArray(reqRes.value.data) ? reqRes.value.data : []);
      await loadStats(selectedTeacherId || undefined);
    } catch {
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleTeacherChange = async (id: string) => {
    setSelectedTeacherId(id);
    await loadStats(id || undefined);
  };

  const handleAssign = async (id: string) => {
    try {
      await assignHelpRequest(id);
      load();
    } catch {}
  };

  const handleRespondDone = () => {
    setRespondingId(null);
    load();
  };

  if (loading) return <div className="teacher-dashboard">Se încarcă...</div>;

  return (
    <div className="teacher-dashboard">
      <div className="teacher-dash-header">
        <h2>Dashboard Profesor</h2>
        <button className="teacher-refresh-btn" onClick={load}>Refresh</button>
      </div>

      {isAdmin && teachers.length > 0 && (
        <div className="teacher-selector-bar">
          <ChevronDown size={16} />
          <label>Statistici pentru:</label>
          <select
            value={selectedTeacherId}
            onChange={(e) => handleTeacherChange(e.target.value)}
            className="teacher-selector-select"
          >
            <option value="">Toți profesorii (global)</option>
            {teachers.map((t) => (
              <option key={t.id} value={t.id}>{t.full_name} — {t.email}</option>
            ))}
          </select>
        </div>
      )}

      {stats && <StatsPanel stats={stats} showAvgTime={isAdmin} />}

      <div className="teacher-requests-section-title">
        <h3>Cereri de ajutor active</h3>
        <span className="teacher-count-badge">{requests.length}</span>
      </div>

      {requests.length === 0 ? (
        <div className="teacher-empty">
          <CheckCircle size={40} />
          <p>Nu există cereri active. Revino mai târziu.</p>
        </div>
      ) : (
        <div className="teacher-requests-list">
          {requests.map((req) => {
            const flag = FLAG_LABELS[req.flag_type] || { icon: '?', label: req.flag_type };
            const isExpanded = expandedId === req.id;
            const isResponding = respondingId === req.id;

            return (
              <div key={req.id} className={`teacher-request-card status-${req.status}`}>
                <div
                  className="teacher-request-header"
                  onClick={() => setExpandedId(isExpanded ? null : req.id)}
                >
                  <div className="teacher-req-left">
                    <span className="teacher-flag-icon">{flag.icon}</span>
                    <div>
                      <div className="teacher-req-title">{flag.label}</div>
                      <div className="teacher-req-student">
                        {req.student_name} · {req.student_email}
                      </div>
                    </div>
                  </div>

                  <div className="teacher-req-right">
                    {req.exercise_path && (
                      <span className="teacher-req-path">{req.exercise_path}</span>
                    )}
                    <span className={`teacher-req-status status-badge-${req.status}`}>
                      {STATUS_LABELS[req.status] || req.status}
                    </span>
                    <span className="teacher-req-date">
                      {new Date(req.created_at).toLocaleDateString('ro-RO')}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="teacher-request-body">
                    <div className="teacher-req-exercise">
                      <div className="teacher-req-label">Exercițiu</div>
                      <div className="teacher-req-statement">
                        {req.statement_latex}
                      </div>
                      <div className="teacher-req-meta">
                        {req.difficulty && <span>Dificultate: {req.difficulty}/10</span>}
                        {req.points && <span>{req.points} puncte</span>}
                      </div>
                    </div>

                    {req.notes && (
                      <div className="teacher-req-notes">
                        <div className="teacher-req-label">Mesaj student</div>
                        <p>{req.notes}</p>
                      </div>
                    )}

                    <div className="teacher-req-actions">
                      {req.status === 'pending' && (
                        <button
                          className="teacher-assign-btn"
                          onClick={() => handleAssign(req.id)}
                        >
                          <UserCheck size={15} /> Preia cererea
                        </button>
                      )}

                      {(req.status === 'assigned' || req.status === 'pending') && !isResponding && (
                        <button
                          className="teacher-respond-btn"
                          onClick={() => setRespondingId(req.id)}
                        >
                          <Send size={15} /> Răspunde
                        </button>
                      )}
                    </div>

                    {isResponding && (
                      <RespondForm request={req} onDone={handleRespondDone} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
