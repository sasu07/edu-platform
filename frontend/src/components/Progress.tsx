import { lazy, Suspense, useEffect, useState } from 'react';
import { Route, CalendarDays, ClipboardList } from 'lucide-react';
import {
  getStudySessions, getStudyPlan, getMyGamification,
  type StudySession, type StudyPlanDay, type GamificationProfile,
} from '../api';
import { LoadingState } from './StateViews';
import StudyPrepCalendar from './StudyPrepCalendar';
import './Practice.css';

/* „Progres" (brief §3.1 / Epic 3) — o singură destinație pentru traseu, plan și calendar.
   (De revizuit + Istoric vor fi mutate aici într-un pas următor.) */

const LearningPath = lazy(() => import('./LearningPath'));
const StudyPlan = lazy(() => import('./StudyPlan'));

const TABS = [
  { id: 'traseu', label: 'Traseul meu', icon: Route },
  { id: 'plan', label: 'Plan', icon: ClipboardList },
  { id: 'calendar', label: 'Calendar', icon: CalendarDays },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function Progress() {
  const [tab, setTab] = useState<TabId>('traseu');
  const [sessions, setSessions] = useState<StudySession[]>([]);
  const [planDays, setPlanDays] = useState<StudyPlanDay[]>([]);
  const [gamification, setGamification] = useState<GamificationProfile | null>(null);
  const [loadedCal, setLoadedCal] = useState(false);

  // Datele pentru calendar se încarcă doar când e nevoie (când se deschide tab-ul).
  useEffect(() => {
    if (tab !== 'calendar' || loadedCal) return;
    Promise.all([getStudySessions(), getStudyPlan(), getMyGamification()])
      .then(([s, p, g]) => {
        setSessions(Array.isArray(s.data) ? s.data : []);
        setPlanDays(Array.isArray(p.data) ? p.data : []);
        setGamification(g.data || null);
      })
      .catch(() => {})
      .finally(() => setLoadedCal(true));
  }, [tab, loadedCal]);

  return (
    <div className="prac">
      <header className="prac-head">
        <div className="prac-head-copy">
          <h1>Progres</h1>
          <p>Traseul tău, planul și calendarul — tot ce arată cât ai avansat, într-un singur loc.</p>
        </div>
      </header>

      <div className="prac-tabs" role="tablist">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={`prac-tab${tab === id ? ' active' : ''}`}
            onClick={() => setTab(id)}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      <div className="prac-panel">
        <Suspense fallback={<LoadingState lines={4} />}>
          {tab === 'traseu' && <LearningPath />}
          {tab === 'plan' && <StudyPlan />}
          {tab === 'calendar' && (
            loadedCal ? (
              <StudyPrepCalendar
                title="Calendarul tău de pregătire"
                subtitle="Zilele în care ai lucrat, ce ai planificat și streak-ul tău."
                sessions={sessions}
                planDays={planDays}
                gamification={gamification}
              />
            ) : <LoadingState lines={5} />
          )}
        </Suspense>
      </div>
    </div>
  );
}
