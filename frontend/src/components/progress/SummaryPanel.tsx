import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Play } from 'lucide-react';
import { getStudyStats, getStudySessions, type StudyStats, type StudySession } from '../../api';
import { LoadingState, EmptyState, PrimaryCTA } from '../StateViews';
import { SESSION_META, statusLabel } from './sessionMeta';
import './progress-panels.css';

/* „Rezumat" (Epic 3 §6.1): progres pe subiecte, recomandare, activitate recentă. */

export default function SummaryPanel() {
  const [stats, setStats] = useState<StudyStats | null>(null);
  const [sessions, setSessions] = useState<StudySession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStudyStats(), getStudySessions()])
      .then(([st, s]) => {
        setStats(st.data || null);
        setSessions(Array.isArray(s.data) ? s.data : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState lines={5} />;

  const noActivity = !stats || stats.total_sessions === 0;
  if (noActivity) {
    return (
      <EmptyState
        title="Încă nu ai activitate"
        description="Pornește prima sesiune și aici vei vedea progresul tău pe subiecte și recomandările."
        action={<PrimaryCTA label="Începe o sesiune" to="/app/study-session?type=test_scurt" icon={<Play size={18} />} />}
      />
    );
  }

  const recent = sessions.slice(0, 3);

  return (
    <div>
      <div className="pg-stats-grid">
        <div className="pg-stat">
          <div className="pg-stat-val">{stats!.total_sessions}</div>
          <div className="pg-stat-label">Sesiuni</div>
        </div>
        <div className="pg-stat">
          <div className="pg-stat-val">{stats!.total_exercises}</div>
          <div className="pg-stat-label">Exerciții rezolvate</div>
        </div>
        <div className="pg-stat">
          <div className="pg-stat-val">{stats!.total_xp}</div>
          <div className="pg-stat-label">XP total</div>
        </div>
        <div className="pg-stat">
          <div className="pg-stat-val">{stats!.avg_completion_pct}%</div>
          <div className="pg-stat-label">Completare medie</div>
        </div>
      </div>

      {stats!.recommendation && (
        <div className="pg-reco">
          <div className="pg-reco-text">
            💡 Următorul pas recomandat: lucrează mai mult la <strong>{stats!.recommendation}</strong>.
          </div>
          <Link className="pg-reco-btn" to="/app/study-session?type=test_scurt">
            <Play size={15} /> Exersează recomandarea
          </Link>
        </div>
      )}

      {stats!.subiect_progress && stats!.subiect_progress.length > 0 && (
        <div className="pg-subject-block">
          <h3 className="pg-section-title">Progres pe subiecte</h3>
          {stats!.subiect_progress.map((sp) => (
            <div key={sp.subiect} className="pg-subject-row">
              <span className="pg-subject-label" title={sp.subiect}>{sp.subiect}</span>
              <div className="pg-subject-bar">
                <div className="pg-subject-fill" style={{ width: `${sp.pct}%` }} />
              </div>
              <span className="pg-subject-pct">{sp.pct}%</span>
            </div>
          ))}
        </div>
      )}

      {recent.length > 0 && (
        <div>
          <h3 className="pg-section-title">Activitate recentă</h3>
          <div className="pg-session-list">
            {recent.map((s) => {
              const meta = SESSION_META[s.session_type] || SESSION_META._default;
              return (
                <div key={s.id} className={`pg-session-card status-${s.status}`}>
                  <div className="pg-session-left">
                    <span className="pg-session-icon">{meta.icon}</span>
                    <div>
                      <div className="pg-session-type">{meta.label}</div>
                      <div className="pg-session-date">
                        {new Date(s.started_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long' })}
                      </div>
                    </div>
                  </div>
                  <div className="pg-session-right">
                    <span className="pg-session-stat">{s.exercises_completed}/{s.exercises_total} ex.</span>
                    <span className={`pg-badge ${s.status}`}>{statusLabel(s.status)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
