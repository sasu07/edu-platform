import { useState, useEffect, useMemo, type ReactNode } from 'react';
import { Clock, ExternalLink, Paperclip, ThumbsUp, ThumbsDown, Hourglass, Bookmark } from 'lucide-react';
import api, { openAuthedFile, getReviewItems, resolveReviewItem } from '../api';
import LatexRenderer from './LatexRenderer';
import ProgressiveHints from './ProgressiveHints';
import './MyRequests.css';

/* „Activitatea mea" — firul meu unificat (Faza 5): un card per exercițiu, care adună
   tot ce s-a întâmplat la el — de revizuit, soluții trimise spre corectură și cereri
   de ajutor (scris / live). Combinăm client-side cele trei surse existente. */

const FLAG_INFO: Record<string, { icon: string; label: string }> = {
  WRITTEN: { icon: '✍️', label: 'Explicație scrisă' },
  VIDEO:   { icon: '🎥', label: 'Rezolvare video' },
  LIVE:    { icon: '🎙️', label: 'Sesiune live' },
};

const TEACHER_STATUS: Record<string, { icon: ReactNode; label: string; cls: string }> = {
  pending:   { icon: <Hourglass size={13} />,  label: 'Așteaptă corecția', cls: 'ts-pending' },
  correct:   { icon: <ThumbsUp size={13} />,   label: 'Corect',           cls: 'ts-correct' },
  incorrect: { icon: <ThumbsDown size={13} />, label: 'Incorect',         cls: 'ts-incorrect' },
};

function reviewReasonLabel(r: string): string {
  if (r === 'wrong' || r === 'failed') return 'răspuns greșit';
  if (r === 'blocked' || r === 'partial' || r === 'incomplete') return 'lăsat neterminat';
  return 'marcat de tine';
}

interface ReviewSrc {
  exercise_id: string;
  source_reason: string;
  last_flagged_at: string;
  statement_latex?: string | null;
  statement_text?: string | null;
  answer_latex?: string | null;
}

interface SubmissionSrc {
  id: string;
  exercise_id: string;
  statement_text?: string;
  statement_latex?: string;
  self_eval: string;
  photo_path: string | null;
  teacher_status: string | null;
  teacher_note: string | null;
  teacher_file_path: string | null;
  xp_teacher: number;
  created_at: string;
  reviewed_at?: string | null;
}

interface HelpSrc {
  id: string;
  exercise_id: string;
  flag_type: string;
  status: string;
  notes?: string;
  created_at: string;
  statement_latex?: string;
  content_text?: string;
  video_path?: string;
  zoom_link?: string;
  scheduled_at?: string;
  responded_at?: string;
  teacher_name?: string;
}

interface ThreadItem {
  exerciseId: string;
  statement: string;
  lastActivity: number;
  review?: ReviewSrc;
  submission?: SubmissionSrc;
  help: HelpSrc[];
}

type Filter = 'all' | 'review' | 'teacher';

export default function MyRequests() {
  const [reviews, setReviews] = useState<ReviewSrc[]>([]);
  const [submissions, setSubmissions] = useState<SubmissionSrc[]>([]);
  const [help, setHelp] = useState<HelpSrc[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [hintFor, setHintFor] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');

  const load = () => {
    setLoading(true);
    Promise.all([
      getReviewItems().then(r => r.data as unknown as ReviewSrc[]).catch(() => [] as ReviewSrc[]),
      api.get('/student/submissions').then(r => r.data).catch(() => []),
      api.get('/help-requests/my-full').then(r => r.data).catch(() => []),
    ]).then(([rev, sub, hlp]) => {
      setReviews(Array.isArray(rev) ? rev : []);
      setSubmissions(Array.isArray(sub) ? sub : []);
      setHelp(Array.isArray(hlp) ? hlp : []);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const items = useMemo<ThreadItem[]>(() => {
    const map = new Map<string, ThreadItem>();
    const ensure = (exId: string, statement: string, ts: number): ThreadItem => {
      let it = map.get(exId);
      if (!it) {
        it = { exerciseId: exId, statement, lastActivity: ts, help: [] };
        map.set(exId, it);
      }
      if (!it.statement && statement) it.statement = statement;
      if (ts > it.lastActivity) it.lastActivity = ts;
      return it;
    };
    for (const r of reviews) {
      const it = ensure(r.exercise_id, r.statement_latex || r.statement_text || '', new Date(r.last_flagged_at).getTime());
      it.review = r;
    }
    for (const s of submissions) {
      const it = ensure(s.exercise_id, s.statement_latex || s.statement_text || '', new Date(s.reviewed_at || s.created_at).getTime());
      it.submission = s;
    }
    for (const h of help) {
      const it = ensure(h.exercise_id, h.statement_latex || '', new Date(h.responded_at || h.created_at).getTime());
      it.help.push(h);
    }
    return Array.from(map.values()).sort((a, b) => b.lastActivity - a.lastActivity);
  }, [reviews, submissions, help]);

  const filtered = useMemo(() => {
    if (filter === 'review') return items.filter(i => i.review);
    if (filter === 'teacher') return items.filter(i => i.submission || i.help.length > 0);
    return items;
  }, [items, filter]);

  const handleRemoveReview = async (exId: string) => {
    setBusyId(exId);
    try {
      await resolveReviewItem(exId);
      setReviews(prev => prev.filter(r => r.exercise_id !== exId));
    } catch { /* rămâne */ } finally { setBusyId(null); }
  };

  if (loading) return <div className="my-req-loading">Se încarcă...</div>;

  return (
    <div className="my-requests">
      <div className="my-req-header">
        <h2>Activitatea mea</h2>
        <p className="my-req-sub">Exercițiile la care lucrezi cu ajutor — de revizuit, trimise spre corectură sau cu o cerere către profesor.</p>
      </div>

      <div className="my-req-filters">
        {([['all', 'Toate'], ['review', 'De revizuit'], ['teacher', 'Cu profesorul']] as const).map(([f, label]) => (
          <button key={f} className={`my-req-filter${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="my-req-empty">
          <Bookmark size={36} />
          <p>Nimic aici încă.</p>
          <p className="my-req-hint">
            Mergi la <strong>Exerciții</strong> și apasă „Cere ajutor" pe un exercițiu — de aici urmărești tot ce ai trimis și tot ce ai de revizuit.
          </p>
        </div>
      ) : (
        <div className="my-req-list">
          {filtered.map((it) => {
            const isOpen = expanded === it.exerciseId;
            const sub = it.submission;
            const tsInfo = sub?.teacher_status ? TEACHER_STATUS[sub.teacher_status] : null;
            return (
              <div key={it.exerciseId} className="thread-card">
                <div className="thread-head" onClick={() => setExpanded(isOpen ? null : it.exerciseId)}>
                  <div className="thread-statement">
                    <LatexRenderer text={(it.statement || 'Exercițiu').slice(0, 160)} />
                  </div>
                  <div className="thread-chips">
                    {it.review && <span className="thread-chip chip-review">🔖 De revizuit</span>}
                    {sub && (
                      <span className={`thread-chip ${tsInfo ? tsInfo.cls : 'ts-pending'}`}>
                        📤 {tsInfo ? tsInfo.label : 'Soluție trimisă'}
                      </span>
                    )}
                    {it.help.map(h => (
                      <span key={h.id} className={`thread-chip chip-help ${h.status === 'resolved' ? 'chip-done' : ''}`}>
                        {(FLAG_INFO[h.flag_type] || { icon: '❓' }).icon} {h.status === 'resolved' ? 'Răspuns primit' : 'În așteptare'}
                      </span>
                    ))}
                  </div>
                </div>

                {isOpen && (
                  <div className="thread-body">
                    {/* De revizuit */}
                    {it.review && (
                      <div className="thread-section">
                        <div className="thread-section-label">🔖 De revizuit · {reviewReasonLabel(it.review.source_reason)}</div>
                        {hintFor === it.exerciseId && <ProgressiveHints exerciseId={it.exerciseId} />}
                        {it.review.answer_latex && (
                          <div className="thread-answer">Răspuns oficial: <LatexRenderer text={it.review.answer_latex} /></div>
                        )}
                        <div className="thread-actions">
                          <button className="thread-act" onClick={() => setHintFor(hintFor === it.exerciseId ? null : it.exerciseId)}>
                            Vezi un indiciu
                          </button>
                          <button className="thread-act danger" onClick={() => handleRemoveReview(it.exerciseId)} disabled={busyId === it.exerciseId}>
                            {busyId === it.exerciseId ? 'Se scoate…' : 'Scoate din listă'}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Soluție trimisă */}
                    {sub && (
                      <div className="thread-section">
                        <div className="thread-section-label">📤 Soluție trimisă spre corectură</div>
                        {sub.photo_path && (
                          <button type="button" className="sol-file-btn" onClick={() => openAuthedFile(sub.photo_path)}>
                            <Paperclip size={14} /> Vezi fișierul tău
                          </button>
                        )}
                        {sub.teacher_status && sub.teacher_status !== 'pending' ? (
                          <div className={`thread-feedback ${sub.teacher_status === 'correct' ? 'ok' : 'bad'}`}>
                            <strong>{sub.teacher_status === 'correct' ? '✅ Corect' : '❌ Incorect'}</strong>
                            {sub.teacher_note && <div className="thread-note">{sub.teacher_note}</div>}
                            {sub.teacher_file_path && (
                              <button type="button" className="sol-file-btn" onClick={() => openAuthedFile(sub.teacher_file_path)}>
                                <Paperclip size={14} /> Fișier de la profesor
                              </button>
                            )}
                            {sub.xp_teacher > 0 && <div className="thread-xp">⚡ +{sub.xp_teacher} XP</div>}
                          </div>
                        ) : (
                          <div className="thread-waiting"><Clock size={15} /> Soluția e în așteptare pentru corecție.</div>
                        )}
                      </div>
                    )}

                    {/* Cereri de ajutor */}
                    {it.help.map(h => {
                      const flag = FLAG_INFO[h.flag_type] || { icon: '❓', label: h.flag_type };
                      const hasResponse = !!(h.content_text || h.zoom_link || h.video_path);
                      return (
                        <div key={h.id} className="thread-section">
                          <div className="thread-section-label">{flag.icon} {flag.label}</div>
                          {h.notes && <div className="thread-note">💬 {h.notes}</div>}
                          {hasResponse ? (
                            <div className="thread-feedback ok">
                              <strong>Răspuns de la {h.teacher_name || 'profesor'}</strong>
                              {h.content_text && <div className="thread-resp"><LatexRenderer text={h.content_text} /></div>}
                              {h.zoom_link && (
                                <div className="thread-zoom">
                                  <a href={h.zoom_link} target="_blank" rel="noreferrer" className="my-req-zoom-btn">
                                    <ExternalLink size={15} /> Intră în sesiunea live
                                  </a>
                                  {h.scheduled_at && <span className="thread-zoom-time">Programat: {new Date(h.scheduled_at).toLocaleString('ro-RO')}</span>}
                                </div>
                              )}
                              {h.video_path && (
                                <button type="button" className="sol-file-btn" onClick={() => openAuthedFile(h.video_path!)}>▶ Vezi rezolvarea video</button>
                              )}
                            </div>
                          ) : (
                            <div className="thread-waiting">
                              <Clock size={15} /> {h.status === 'assigned' ? 'Un profesor lucrează la răspuns.' : 'Cererea e în așteptare.'}
                            </div>
                          )}
                        </div>
                      );
                    })}
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
