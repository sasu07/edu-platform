import { useEffect, useState } from 'react';
import { getMyStudents, getStudentStats, type ParentStudentStats, type ParentStudentLink } from '../api';
import './ParentDashboard.css';

const SUBIECT_LABEL: Record<string, string> = { '1': 'Subiect I', '2': 'Subiect II', '3': 'Subiect III' };

function ActivityChart({ days }: { days: ParentStudentStats['activity_last_30_days'] }) {
  const maxVal = Math.max(...days.map(d => d.exercises_seen + d.variants_generated), 1);
  return (
    <div className="pd-chart">
      {days.map((d) => {
        const total = d.exercises_seen + d.variants_generated;
        const h = Math.round((total / maxVal) * 60);
        const hasActivity = total > 0 || d.flags_sent > 0;
        return (
          <div key={d.date} className="pd-chart-col" title={`${d.date}\nExercitii vazute: ${d.exercises_seen}\nRezolvate: ${d.exercises_completed}\nVariante: ${d.variants_generated}\nIntrebari: ${d.flags_sent}`}>
            <div
              className={`pd-chart-bar ${hasActivity ? 'active' : ''} ${d.exercises_completed > 0 ? 'has-completed' : ''}`}
              style={{ height: `${Math.max(h, hasActivity ? 4 : 0)}px` }}
            />
          </div>
        );
      })}
    </div>
  );
}

function StudentCard({ link }: { link: ParentStudentLink }) {
  const [stats, setStats] = useState<ParentStudentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getStudentStats(link.student_id)
      .then(r => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [link.student_id]);

  const lastActive = stats?.last_active_at
    ? new Date(stats.last_active_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long' })
    : 'Nicio activitate';

  const weekDays = stats?.activity_last_30_days.slice(-7) ?? [];
  const weekCompleted = weekDays.reduce((s, d) => s + d.exercises_completed, 0);
  const weekVariants = weekDays.reduce((s, d) => s + d.variants_generated, 0);
  const weekFlags = weekDays.reduce((s, d) => s + d.flags_sent, 0);
  const weekActiveDays = weekDays.filter(d => d.exercises_seen > 0 || d.variants_generated > 0).length;

  return (
    <div className="pd-student-card">
      <div className="pd-student-header" onClick={() => setExpanded(e => !e)}>
        <div className="pd-student-avatar">{link.student_name[0].toUpperCase()}</div>
        <div className="pd-student-info">
          <div className="pd-student-name">{link.student_name}</div>
          <div className="pd-student-meta">Ultima activitate: {lastActive}</div>
        </div>
        <div className="pd-student-expand">{expanded ? '▲' : '▼'}</div>
      </div>

      {loading && <div className="pd-loading">Se încarcă...</div>}

      {!loading && stats && (
        <>
          <div className="pd-stats-row">
            <div className="pd-stat">
              <span className="pd-stat-val">{stats.total_exercises_seen}</span>
              <span className="pd-stat-label">Exerciții văzute</span>
            </div>
            <div className="pd-stat">
              <span className="pd-stat-val pd-stat-green">{stats.total_exercises_completed}</span>
              <span className="pd-stat-label">Rezolvate</span>
            </div>
            <div className="pd-stat">
              <span className="pd-stat-val pd-stat-blue">{stats.total_variants_generated}</span>
              <span className="pd-stat-label">Variante</span>
            </div>
            <div className="pd-stat">
              <span className="pd-stat-val pd-stat-amber">{stats.total_flags_sent}</span>
              <span className="pd-stat-label">Întrebări</span>
            </div>
          </div>

          <div className="pd-section-title">Activitate — ultimele 30 zile</div>
          <ActivityChart days={stats.activity_last_30_days} />
          <div className="pd-chart-legend">
            <span className="pd-legend-dot active" /> Exerciții/variante &nbsp;
            <span className="pd-legend-dot has-completed" /> Include rezolvate
          </div>

          {expanded && (
            <>
              <div className="pd-section-title">Săptămâna curentă</div>
              <div className="pd-week-row">
                <div className="pd-week-item"><span>{weekActiveDays}/7</span> zile active</div>
                <div className="pd-week-item"><span>{weekCompleted}</span> rezolvate</div>
                <div className="pd-week-item"><span>{weekVariants}</span> variante</div>
                <div className="pd-week-item"><span>{weekFlags}</span> întrebări</div>
              </div>

              {Object.keys(stats.completion_by_subiect).length > 0 && (
                <>
                  <div className="pd-section-title">Exerciții rezolvate pe subiect</div>
                  <div className="pd-subiect-row">
                    {Object.entries(stats.completion_by_subiect).map(([k, v]) => (
                      <div key={k} className="pd-subiect-item">
                        <span className="pd-subiect-label">{SUBIECT_LABEL[k] ?? `S${k}`}</span>
                        <span className="pd-subiect-val">{v}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function ParentDashboard() {
  const [students, setStudents] = useState<ParentStudentLink[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyStudents()
      .then(r => setStudents(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="pd-container">
      <div className="pd-header">
        <h1 className="pd-title">Dashboard Progres Elev</h1>
        <p className="pd-subtitle">Urmărești activitatea copilului tău pe platforma EtoX.</p>
      </div>

      {loading && <div className="pd-loading">Se încarcă...</div>}

      {!loading && students.length === 0 && (
        <div className="pd-empty">
          <div className="pd-empty-icon">👨‍👩‍👧</div>
          <div className="pd-empty-text">Nu ești legat de niciun elev.</div>
          <div className="pd-empty-sub">Cere elevului să te adauge din secțiunea "Adaugă părinte" din contul său.</div>
        </div>
      )}

      <div className="pd-students-list">
        {students.map(s => <StudentCard key={s.id} link={s} />)}
      </div>
    </div>
  );
}
