import { useEffect, useState } from 'react';
import { getStudySessions, type StudySession } from '../../api';
import { LoadingState, EmptyState, PrimaryCTA } from '../StateViews';
import { Play } from 'lucide-react';
import { SESSION_META, statusLabel } from './sessionMeta';
import './progress-panels.css';

/* „Istoric" (Epic 3 §6.1): sesiuni finalizate, abandonate și active — clar diferențiate. */

export default function HistoryList() {
  const [sessions, setSessions] = useState<StudySession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudySessions()
      .then((r) => setSessions(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState lines={5} />;

  if (sessions.length === 0) {
    return (
      <EmptyState
        title="Nu ai sesiuni înregistrate"
        description="Sesiunile pe care le pornești vor apărea aici, cu tot cu rezultat."
        action={<PrimaryCTA label="Pornește prima sesiune" to="/app/study-session?type=test_scurt" icon={<Play size={18} />} />}
      />
    );
  }

  return (
    <div className="pg-session-list">
      {sessions.map((s) => {
        const meta = SESSION_META[s.session_type] || SESSION_META._default;
        const pct = s.exercises_total > 0 ? Math.round((s.exercises_completed / s.exercises_total) * 100) : 0;
        return (
          <div key={s.id} className={`pg-session-card status-${s.status}`}>
            <div className="pg-session-left">
              <span className="pg-session-icon">{meta.icon}</span>
              <div>
                <div className="pg-session-type">{meta.label}</div>
                <div className="pg-session-date">
                  {new Date(s.started_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long', year: 'numeric' })}
                </div>
              </div>
            </div>
            <div className="pg-session-right">
              <span className="pg-session-stat">{s.exercises_completed}/{s.exercises_total} ex.</span>
              <span className="pg-session-stat">{pct}%</span>
              {s.xp_gained > 0 && <span className="pg-session-xp">+{s.xp_gained} XP</span>}
              <span className={`pg-badge ${s.status}`}>{statusLabel(s.status)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
