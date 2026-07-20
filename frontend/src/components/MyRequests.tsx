import { useState, useEffect } from 'react';
import React from 'react';
import { Flag, CheckCircle, Clock, AlertCircle, ExternalLink, BookCheck, ThumbsUp, ThumbsDown, Paperclip, Hourglass } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import api, { openAuthedFile } from '../api';
import LatexRenderer from './LatexRenderer';
import './MyRequests.css';

// ─── Help Requests ───────────────────────────────────────────────────────────

const FLAG_INFO: Record<string, { icon: string; label: string }> = {
  WRITTEN: { icon: '✍️', label: 'Rezolvare scrisă' },
  VIDEO:   { icon: '🎥', label: 'Rezolvare video' },
  LIVE:    { icon: '🎙️', label: 'Sesiune live' },
};

const STATUS_INFO: Record<string, { label: string; color: string }> = {
  pending:  { label: 'În așteptare', color: 'status-pending' },
  assigned: { label: 'Preluat de profesor', color: 'status-assigned' },
  resolved: { label: 'Rezolvat', color: 'status-resolved' },
};

interface RequestFull {
  id: string;
  flag_type: string;
  status: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  statement_latex: string;
  difficulty?: number;
  points?: number;
  exercise_path?: string;
  exercise_id: string;
  content_text?: string;
  video_path?: string;
  zoom_link?: string;
  scheduled_at?: string;
  responded_at?: string;
  teacher_name?: string;
}

function HelpRequestsTab() {
  const [requests, setRequests] = useState<RequestFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get('/help-requests/my-full')
      .then((r) => setRequests(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="my-req-loading">Se încarcă...</div>;

  if (requests.length === 0) return (
    <div className="my-req-empty">
      <AlertCircle size={36} />
      <p>Nu ai trimis nicio cerere de ajutor încă.</p>
      <p className="my-req-hint">Mergi la <strong>Exerciții</strong> și apasă butonul „Ajutor" pe un exercițiu.</p>
    </div>
  );

  return (
    <div className="my-req-list">
      {requests.map((req) => {
        const flag = FLAG_INFO[req.flag_type] || { icon: '?', label: req.flag_type };
        const st = STATUS_INFO[req.status] || { label: req.status, color: '' };
        const isOpen = expanded === req.id;
        const hasResponse = !!(req.content_text || req.zoom_link || req.video_path);

        return (
          <div key={req.id} className={`my-req-card ${hasResponse ? 'has-response' : ''}`}>
            <div className="my-req-card-header" onClick={() => setExpanded(isOpen ? null : req.id)}>
              <div className="my-req-left">
                <span className="my-req-flag-icon">{flag.icon}</span>
                <div>
                  <div className="my-req-flag-label">{flag.label}</div>
                  <div className="my-req-date">
                    {new Date(req.created_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </div>
                </div>
              </div>
              <div className="my-req-right">
                {req.exercise_path && <span className="my-req-path">{req.exercise_path}</span>}
                <span className={`my-req-status ${st.color}`}>
                  {req.status === 'resolved' ? <CheckCircle size={13} /> : <Clock size={13} />}
                  {st.label}
                </span>
              </div>
            </div>

            {isOpen && (
              <div className="my-req-body">
                <div className="my-req-exercise">
                  <div className="my-req-section-label">Exercițiu</div>
                  <div className="my-req-statement">
                    <LatexRenderer text={req.statement_latex} />
                  </div>
                </div>

                {req.notes && (
                  <div className="my-req-notes">
                    <div className="my-req-section-label">Mesajul tău</div>
                    <p>{req.notes}</p>
                  </div>
                )}

                {hasResponse ? (
                  <div className="my-req-response">
                    <div className="my-req-section-label response-label">
                      <CheckCircle size={13} /> Răspuns de la {req.teacher_name || 'profesor'}
                      {req.responded_at && (
                        <span className="my-req-resp-date">
                          · {new Date(req.responded_at).toLocaleDateString('ro-RO')}
                        </span>
                      )}
                    </div>

                    {req.content_text && (
                      <div className="my-req-resp-text">
                        <LatexRenderer text={req.content_text} />
                      </div>
                    )}

                    {req.zoom_link && (
                      <div className="my-req-zoom">
                        <a href={req.zoom_link} target="_blank" rel="noreferrer" className="my-req-zoom-btn">
                          <ExternalLink size={15} />
                          Intră în sesiunea Zoom
                        </a>
                        {req.scheduled_at && (
                          <span className="my-req-zoom-time">
                            Programat: {new Date(req.scheduled_at).toLocaleString('ro-RO')}
                          </span>
                        )}
                      </div>
                    )}

                    {req.video_path && (
                      <div className="my-req-video">
                        <button type="button" className="sol-file-btn" onClick={() => openAuthedFile(req.video_path)}>
                          ▶ Vezi rezolvarea video
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="my-req-waiting">
                    <Clock size={16} />
                    {req.status === 'assigned'
                      ? 'Un profesor a preluat cererea și lucrează la răspuns.'
                      : 'Cererea ta este în așteptare. Vei fi notificat când primești răspuns.'}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Solutions Tab ────────────────────────────────────────────────────────────

interface SubmissionFull {
  id: string;
  exercise_id: string;
  statement_text?: string;
  statement_latex?: string;
  self_eval: string;
  photo_path: string | null;
  teacher_status: string | null;
  teacher_note: string | null;
  teacher_file_path: string | null;
  xp_self_eval: number;
  xp_photo: number;
  xp_teacher: number;
  created_at: string;
  reviewed_at?: string | null;
}

const SELF_EVAL_LABEL: Record<string, { label: string; cls: string }> = {
  failed:   { label: 'Nu am reușit',     cls: 'eval-failed' },
  partial:  { label: 'Parțial',          cls: 'eval-partial' },
  complete: { label: 'Rezolvat complet', cls: 'eval-complete' },
};

const TEACHER_STATUS_INFO: Record<string, { icon: React.ReactNode; label: string; cls: string }> = {
  pending:   { icon: <Hourglass size={13} />,  label: 'Așteptare corecție', cls: 'ts-pending' },
  correct:   { icon: <ThumbsUp size={13} />,   label: 'Corect ✅',          cls: 'ts-correct' },
  incorrect: { icon: <ThumbsDown size={13} />, label: 'Incorect ❌',        cls: 'ts-incorrect' },
};

function SolutionsTab() {
  const [submissions, setSubmissions] = useState<SubmissionFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get('/student/submissions')
      .then((r) => setSubmissions(Array.isArray(r.data) ? r.data : []))
      .catch(() => setSubmissions([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="my-req-loading">Se încarcă...</div>;

  if (submissions.length === 0) return (
    <div className="my-req-empty">
      <BookCheck size={36} />
      <p>Nu ai trimis nicio soluție încă.</p>
      <p className="my-req-hint">
        Mergi la <strong>Exerciții</strong>, rezolvă un exercițiu și apasă „○ Rezolvat" pentru a trimite autoevaluarea.
      </p>
    </div>
  );

  return (
    <div className="my-req-list">
      {submissions.map((sub) => {
        const isOpen = expanded === sub.id;
        const evalInfo = SELF_EVAL_LABEL[sub.self_eval] || { label: sub.self_eval, cls: '' };
        const tsInfo = sub.teacher_status ? TEACHER_STATUS_INFO[sub.teacher_status] : null;
        const totalXp = sub.xp_self_eval + sub.xp_photo + sub.xp_teacher;
        const shortStatement = (sub.statement_text || sub.statement_latex || '').slice(0, 80);
        const hasTeacherAction = !!(sub.teacher_note || sub.teacher_file_path || sub.teacher_status === 'correct' || sub.teacher_status === 'incorrect');

        return (
          <div
            key={sub.id}
            className={`my-req-card sol-card${hasTeacherAction ? ' sol-has-feedback' : ''}${sub.teacher_status === 'incorrect' ? ' sol-incorrect' : ''}`}
          >
            <div className="my-req-card-header" onClick={() => setExpanded(isOpen ? null : sub.id)}>
              <div className="my-req-left">
                <span className="my-req-flag-icon">📝</span>
                <div>
                  <div className="my-req-flag-label sol-statement-preview">
                    {shortStatement || 'Exercițiu'}
                    {(sub.statement_text || sub.statement_latex || '').length > 80 ? '…' : ''}
                  </div>
                  <div className="my-req-date">
                    {new Date(sub.created_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long', year: 'numeric' })}
                    {totalXp > 0 && <span className="sol-xp-badge">+{totalXp} XP</span>}
                  </div>
                </div>
              </div>

              <div className="my-req-right sol-badges">
                <span className={`sol-eval-badge ${evalInfo.cls}`}>{evalInfo.label}</span>
                {tsInfo ? (
                  <span className={`my-req-status ${tsInfo.cls}`}>
                    {tsInfo.icon} {tsInfo.label}
                  </span>
                ) : (
                  <span className="my-req-status status-pending">
                    <Clock size={13} /> Fără corecție
                  </span>
                )}
              </div>
            </div>

            {isOpen && (
              <div className="my-req-body">
                {/* Enunț */}
                <div className="my-req-exercise">
                  <div className="my-req-section-label">Exercițiu</div>
                  <div className="my-req-statement">
                    <LatexRenderer text={sub.statement_latex || sub.statement_text || ''} />
                  </div>
                </div>

                {/* Fișierul elevului */}
                {sub.photo_path && (
                  <div className="sol-file-row">
                    <div className="my-req-section-label">Soluția ta</div>
                    <button
                      type="button"
                      className="sol-file-btn"
                      onClick={() => openAuthedFile(sub.photo_path)}
                    >
                      <Paperclip size={14} /> Vezi fișierul tău
                    </button>
                  </div>
                )}

                {/* Corecție profesor */}
                {hasTeacherAction ? (
                  <div className={`sol-feedback-block${sub.teacher_status === 'correct' ? ' feedback-correct' : sub.teacher_status === 'incorrect' ? ' feedback-incorrect' : ' feedback-pending'}`}>
                    <div className="my-req-section-label sol-feedback-label">
                      {sub.teacher_status === 'correct' && <><ThumbsUp size={13} /> Feedback profesor — Corect</>}
                      {sub.teacher_status === 'incorrect' && <><ThumbsDown size={13} /> Feedback profesor — Incorect</>}
                      {sub.teacher_status === 'pending' && <><Hourglass size={13} /> Soluție primită, în așteptare corecție</>}
                      {sub.reviewed_at && (
                        <span className="my-req-resp-date">
                          · {new Date(sub.reviewed_at).toLocaleDateString('ro-RO')}
                        </span>
                      )}
                    </div>

                    {sub.teacher_note && (
                      <div className="sol-teacher-note">{sub.teacher_note}</div>
                    )}

                    {sub.teacher_file_path && (
                      <button
                        type="button"
                        className="sol-file-btn sol-file-teacher"
                        onClick={() => openAuthedFile(sub.teacher_file_path)}
                      >
                        <Paperclip size={14} /> Fișier rezolvare de la profesor
                      </button>
                    )}

                    {sub.xp_teacher > 0 && (
                      <div className="sol-xp-row">⚡ +{sub.xp_teacher} XP acordat pentru soluție corectă</div>
                    )}
                  </div>
                ) : (
                  !sub.photo_path ? null : (
                    <div className="my-req-waiting">
                      <Clock size={16} />
                      Soluția ta a fost primită și este în așteptare pentru corecție.
                    </div>
                  )
                )}

                {/* XP detaliat */}
                <div className="sol-xp-breakdown">
                  {sub.xp_self_eval > 0 && <span>Autoevaluare: +{sub.xp_self_eval} XP</span>}
                  {sub.xp_photo > 0 && <span>Foto: +{sub.xp_photo} XP</span>}
                  {sub.xp_teacher > 0 && <span>Corecție: +{sub.xp_teacher} XP</span>}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function MyRequests() {
  const [searchParams] = useSearchParams();
  const defaultTab = searchParams.get('tab') === 'solutions' ? 'solutions' : 'requests';
  const [activeTab, setActiveTab] = useState<'requests' | 'solutions'>(defaultTab);

  return (
    <div className="my-requests">
      <div className="my-req-header">
        <h2>Activitatea mea</h2>
      </div>

      <div className="my-req-tabs">
        <button
          className={`my-req-tab-btn${activeTab === 'requests' ? ' active' : ''}`}
          onClick={() => setActiveTab('requests')}
        >
          <Flag size={15} /> Cereri ajutor
        </button>
        <button
          className={`my-req-tab-btn${activeTab === 'solutions' ? ' active' : ''}`}
          onClick={() => setActiveTab('solutions')}
        >
          <BookCheck size={15} /> Soluții trimise
        </button>
      </div>

      {activeTab === 'requests' && <HelpRequestsTab />}
      {activeTab === 'solutions' && <SolutionsTab />}
    </div>
  );
}
