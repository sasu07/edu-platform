import { useState, useEffect } from 'react';
import { CheckCircle, Camera, ThumbsUp, ThumbsDown, Eye, Paperclip, Users, Video, Calendar } from 'lucide-react';
import {
  getTeacherSubmissions,
  reviewSubmission,
  uploadTeacherFile,
  assignPendingSubmissions,
  getSubmissionStats,
  getLiveHelpRequests,
  scheduleLiveHelp,
  openAuthedFile,
  fetchAuthedObjectUrl,
} from '../api';
import LatexRenderer from './LatexRenderer';
import './TeacherDashboard.css';

interface SubmissionItem {
  id: string;
  student_name: string;
  student_email: string;
  exercise_id: string;
  statement_latex: string;
  difficulty?: number;
  self_eval: string;
  photo_path: string | null;
  photo_uploaded_at: string | null;
  teacher_status: string | null;
  teacher_note: string | null;
  teacher_file_path: string | null;
  assigned_teacher_id: string | null;
  assigned_teacher_name: string | null;
  created_at: string;
}

const SELF_EVAL_LABEL: Record<string, string> = {
  failed: '❌ Nu am rezolvat',
  partial: '⚠️ Parțial',
  complete: '✅ Complet',
};

function SubmissionsTab() {
  const [submissions, setSubmissions] = useState<SubmissionItem[]>([]);
  const [subStats, setSubStats] = useState<{ pending: number; correct: number; incorrect: number; total: number } | null>(null);
  const [filter, setFilter] = useState<'pending' | 'correct' | 'incorrect'>('pending');
  const [loading, setLoading] = useState(true);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [photoModal, setPhotoModal] = useState<string | null>(null);

  const openPhotoModal = async (path?: string | null) => {
    if (!path) return;
    try {
      setPhotoModal(await fetchAuthedObjectUrl(path));
    } catch {
      alert('Fișierul nu este disponibil.');
    }
  };
  const closePhotoModal = () => {
    setPhotoModal((url) => {
      if (url) URL.revokeObjectURL(url);
      return null;
    });
  };
  const [uploadingFileId, setUploadingFileId] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);

  const load = async (status = filter) => {
    setLoading(true);
    try {
      const [subRes, statsRes] = await Promise.all([
        getTeacherSubmissions(status),
        getSubmissionStats(),
      ]);
      setSubmissions(Array.isArray(subRes.data) ? subRes.data : []);
      setSubStats(statsRes.data);
    } catch {
      setSubmissions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleFilter = (f: 'pending' | 'correct' | 'incorrect') => {
    setFilter(f);
    load(f);
  };

  const handleReview = async (submissionId: string, status: 'correct' | 'incorrect') => {
    try {
      await reviewSubmission(submissionId, { status, note: noteText || undefined });
      setReviewingId(null);
      setNoteText('');
      load(filter);
    } catch {}
  };

  const handleFileUpload = async (submissionId: string, file: File) => {
    setUploadingFileId(submissionId);
    try {
      await uploadTeacherFile(submissionId, file);
      load(filter);
    } catch {}
    finally { setUploadingFileId(null); }
  };

  const handleAssignAll = async () => {
    setAssigning(true);
    try {
      const res = await assignPendingSubmissions();
      alert(`Ai preluat ${res.data.assigned} soluții.`);
      load(filter);
    } catch {}
    finally { setAssigning(false); }
  };

  return (
    <div className="submissions-tab">
      {subStats && (
        <div className="sub-stats-row">
          <div className="sub-stat-pill sub-pending" onClick={() => handleFilter('pending')}>
            <span className="sub-stat-num">{subStats.pending}</span>
            <span>În așteptare</span>
          </div>
          <div className="sub-stat-pill sub-correct" onClick={() => handleFilter('correct')}>
            <span className="sub-stat-num">{subStats.correct}</span>
            <span>Corecte</span>
          </div>
          <div className="sub-stat-pill sub-incorrect" onClick={() => handleFilter('incorrect')}>
            <span className="sub-stat-num">{subStats.incorrect}</span>
            <span>Incorecte</span>
          </div>
          <div className="sub-stat-pill">
            <span className="sub-stat-num">{subStats.total}</span>
            <span>Total</span>
          </div>
          {subStats.pending > 0 && (
            <button className="sub-assign-all-btn" onClick={handleAssignAll} disabled={assigning}>
              <Users size={14} /> {assigning ? 'Se preia...' : `Preia toate (${subStats.pending})`}
            </button>
          )}
        </div>
      )}

      <div className="sub-filter-bar">
        {(['pending', 'correct', 'incorrect'] as const).map((f) => (
          <button
            key={f}
            className={`sub-filter-btn${filter === f ? ' active' : ''}`}
            onClick={() => handleFilter(f)}
          >
            {f === 'pending' ? '⏳ În așteptare' : f === 'correct' ? '✅ Corecte' : '❌ Incorecte'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="teacher-empty">Se încarcă...</div>
      ) : submissions.length === 0 ? (
        <div className="teacher-empty">
          <CheckCircle size={40} />
          <p>Nu există soluții de verificat.</p>
        </div>
      ) : (
        <div className="submissions-list">
          {submissions.map((sub) => (
            <div key={sub.id} className={`submission-card sub-status-${sub.teacher_status || 'pending'}`}>
              <div className="sub-card-header">
                <div className="sub-card-student">
                  <strong>{sub.student_name}</strong>
                  <span className="sub-card-email">{sub.student_email}</span>
                </div>
                <div className="sub-card-meta">
                  {sub.difficulty && <span className="sub-diff">Dif: {sub.difficulty}/10</span>}
                  <span className={`sub-eval-badge eval-${sub.self_eval}`}>
                    {SELF_EVAL_LABEL[sub.self_eval] || sub.self_eval}
                  </span>
                  <span className="sub-date">{new Date(sub.created_at).toLocaleDateString('ro-RO')}</span>
                </div>
              </div>

              <div className="sub-statement">{sub.statement_latex}</div>

              {sub.photo_path && (
                <div className="sub-photo-row">
                  <Camera size={14} />
                  <button className="sub-photo-btn" onClick={() => openPhotoModal(sub.photo_path)}>
                    <Eye size={13} /> Vezi fișier elev
                  </button>
                  {sub.photo_uploaded_at && (
                    <span className="sub-photo-date">
                      {new Date(sub.photo_uploaded_at).toLocaleString('ro-RO')}
                    </span>
                  )}
                </div>
              )}

              {sub.teacher_file_path && (
                <div className="sub-photo-row">
                  <Paperclip size={14} />
                  <button type="button" className="sub-photo-btn" onClick={() => openAuthedFile(sub.teacher_file_path)}>
                    <Eye size={13} /> Fișier tău încărcat
                  </button>
                </div>
              )}

              {sub.assigned_teacher_name && (
                <div className="sub-assigned-badge">
                  <Users size={12} /> Preluat de: {sub.assigned_teacher_name}
                </div>
              )}

              {sub.teacher_note && (
                <div className="sub-teacher-note">
                  <strong>Notă profesor:</strong> {sub.teacher_note}
                </div>
              )}

              <div className="sub-review-area">
                {/* File upload by teacher */}
                <label className="sub-file-upload-label">
                  <Paperclip size={13} />
                  {uploadingFileId === sub.id ? 'Se încarcă...' : 'Încarcă fișier rezolvare'}
                  <input
                    type="file"
                    accept="image/*,.pdf"
                    style={{ display: 'none' }}
                    disabled={uploadingFileId === sub.id}
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(sub.id, f); }}
                  />
                </label>

                {sub.teacher_status === null || sub.teacher_status === 'pending' ? (
                  reviewingId === sub.id ? (
                    <>
                      <textarea
                        className="sub-note-input"
                        placeholder="Notă pentru student (opțional)..."
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        rows={2}
                      />
                      <div className="sub-review-btns">
                        <button className="sub-btn-correct" onClick={() => handleReview(sub.id, 'correct')}>
                          <ThumbsUp size={14} /> Corect
                        </button>
                        <button className="sub-btn-incorrect" onClick={() => handleReview(sub.id, 'incorrect')}>
                          <ThumbsDown size={14} /> Incorect
                        </button>
                        <button className="sub-btn-cancel" onClick={() => { setReviewingId(null); setNoteText(''); }}>
                          Anulează
                        </button>
                      </div>
                    </>
                  ) : (
                    <button className="sub-btn-review" onClick={() => setReviewingId(sub.id)}>
                      Corectează soluția
                    </button>
                  )
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}

      {photoModal && (
        <div className="sub-photo-overlay" onClick={closePhotoModal}>
          <div className="sub-photo-modal" onClick={(e) => e.stopPropagation()}>
            <button className="sub-photo-close" onClick={closePhotoModal}>✕</button>
            <img src={photoModal} alt="Soluție student" className="sub-photo-img" />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Live Help Requests Tab ───────────────────────────────────────────────────

interface LiveRequest {
  id: string;
  student_name: string;
  student_email: string;
  exercise_id: string;
  statement_text: string | null;
  statement_latex: string | null;
  difficulty: number | null;
  notes: string | null;
  status: string;
  scheduled_at: string | null;
  zoom_link: string | null;
  created_at: string;
}

function LiveRequestsTab() {
  const [requests, setRequests] = useState<LiveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [schedulingId, setSchedulingId] = useState<string | null>(null);
  const [schedDate, setSchedDate] = useState('');
  const [schedTime, setSchedTime] = useState('');
  const [schedZoom, setSchedZoom] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const load = () => {
    setLoading(true);
    getLiveHelpRequests()
      .then(r => setRequests(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSchedule = async (id: string) => {
    if (!schedDate || !schedTime) { setMsg('Selectează data și ora.'); return; }
    setSaving(true);
    setMsg('');
    try {
      const iso = `${schedDate}T${schedTime}:00`;
      await scheduleLiveHelp(id, { scheduled_at: iso, zoom_link: schedZoom || undefined });
      setSchedulingId(null);
      setSchedDate(''); setSchedTime(''); setSchedZoom('');
      load();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || 'Eroare la programare.');
    } finally { setSaving(false); }
  };

  if (loading) return <div className="teacher-empty">Se încarcă...</div>;

  if (requests.length === 0) return (
    <div className="teacher-empty">
      <Video size={40} />
      <p>Nu există cereri de ajutor live.</p>
    </div>
  );

  return (
    <div className="live-requests-list">
      {requests.map(req => (
        <div key={req.id} className={`live-req-card${req.scheduled_at ? ' scheduled' : ''}`}>
          <div className="live-req-header">
            <div>
              <strong>{req.student_name}</strong>
              <span className="sub-card-email">{req.student_email}</span>
            </div>
            <div className="live-req-meta">
              {req.difficulty && <span className="sub-diff">Dif: {req.difficulty}/10</span>}
              <span className="sub-date">{new Date(req.created_at).toLocaleDateString('ro-RO')}</span>
              {req.scheduled_at && (
                <span className="live-req-scheduled-badge">
                  📅 {new Date(req.scheduled_at).toLocaleString('ro-RO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          </div>

          {(req.statement_text || req.statement_latex) && (
            <div className="sub-statement">
              <LatexRenderer text={req.statement_latex || req.statement_text || ''} />
            </div>
          )}

          {req.notes && (
            <div className="live-req-notes">💬 <em>{req.notes}</em></div>
          )}

          {req.zoom_link && (
            <div className="live-req-zoom">
              🔗 <a href={req.zoom_link} target="_blank" rel="noopener noreferrer">{req.zoom_link}</a>
            </div>
          )}

          {!req.scheduled_at && (
            schedulingId === req.id ? (
              <div className="live-sched-form">
                <div className="live-sched-row">
                  <input type="date" className="live-sched-input" value={schedDate}
                    min={new Date().toISOString().split('T')[0]}
                    onChange={e => setSchedDate(e.target.value)} />
                  <input type="time" className="live-sched-input" value={schedTime}
                    onChange={e => setSchedTime(e.target.value)} />
                </div>
                <input type="url" className="live-sched-input" placeholder="Link Zoom/Meet (opțional)"
                  value={schedZoom} onChange={e => setSchedZoom(e.target.value)} />
                {msg && <div className="flag-msg-err">{msg}</div>}
                <div className="live-sched-btns">
                  <button className="sub-btn-cancel" onClick={() => { setSchedulingId(null); setMsg(''); }}>Anulează</button>
                  <button className="sub-btn-correct" onClick={() => handleSchedule(req.id)} disabled={saving}>
                    <Calendar size={14} /> {saving ? 'Se salvează...' : 'Confirmă programarea'}
                  </button>
                </div>
              </div>
            ) : (
              <button className="live-req-schedule-btn" onClick={() => { setSchedulingId(req.id); setMsg(''); }}>
                <Video size={14} /> Programează sesiunea live
              </button>
            )
          )}
        </div>
      ))}
    </div>
  );
}

export default function TeacherDashboard() {
  const [tab, setTab] = useState<'submissions' | 'live'>('submissions');

  return (
    <div className="teacher-dashboard">
      <div className="teacher-dash-header">
        <h2><Camera size={20} /> Dashboard Profesor</h2>
      </div>
      <div className="teacher-dash-tabs">
        <button className={`td-tab-btn${tab === 'submissions' ? ' active' : ''}`} onClick={() => setTab('submissions')}>
          📝 Verificare soluții
        </button>
        <button className={`td-tab-btn${tab === 'live' ? ' active' : ''}`} onClick={() => setTab('live')}>
          📹 Cereri ajutor live
        </button>
      </div>
      {tab === 'submissions' && <SubmissionsTab />}
      {tab === 'live' && <LiveRequestsTab />}
    </div>
  );
}
