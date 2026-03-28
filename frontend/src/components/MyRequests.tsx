import { useState, useEffect } from 'react';
import { Flag, CheckCircle, Clock, AlertCircle, ExternalLink } from 'lucide-react';
import api from '../api';
import LatexRenderer from './LatexRenderer';
import './MyRequests.css';

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
  // răspuns
  content_text?: string;
  video_path?: string;
  zoom_link?: string;
  scheduled_at?: string;
  responded_at?: string;
  teacher_name?: string;
}

export default function MyRequests() {
  const [requests, setRequests] = useState<RequestFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get('/help-requests/my-full')
      .then((r) => setRequests(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="my-requests">Se încarcă...</div>;

  return (
    <div className="my-requests">
      <div className="my-req-header">
        <h2><Flag size={20} /> Cererile mele de ajutor</h2>
        <span className="my-req-count">{requests.length} cereri</span>
      </div>

      {requests.length === 0 ? (
        <div className="my-req-empty">
          <AlertCircle size={36} />
          <p>Nu ai trimis nicio cerere de ajutor încă.</p>
          <p className="my-req-hint">Mergi la <strong>Exerciții</strong> și apasă butonul „Ajutor" pe un exercițiu.</p>
        </div>
      ) : (
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
                    {/* Exercițiu */}
                    <div className="my-req-exercise">
                      <div className="my-req-section-label">Exercițiu</div>
                      <div className="my-req-statement">
                        <LatexRenderer text={req.statement_latex} />
                      </div>
                    </div>

                    {/* Mesajul trimis */}
                    {req.notes && (
                      <div className="my-req-notes">
                        <div className="my-req-section-label">Mesajul tău</div>
                        <p>{req.notes}</p>
                      </div>
                    )}

                    {/* Răspunsul profesorului */}
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
                            <video controls style={{ maxWidth: '100%', borderRadius: 8 }}>
                              <source src={`http://localhost:8000/files/${req.video_path}`} />
                              Browser-ul tău nu suportă video.
                            </video>
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
      )}
    </div>
  );
}
