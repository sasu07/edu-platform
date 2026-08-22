import { lazy, Suspense, useEffect, useState } from 'react';
import { LayoutDashboard, CalendarDays, RotateCcw, History, Route } from 'lucide-react';
import {
  getStudySessions, getStudyPlan, getMyGamification,
  type StudySession, type StudyPlanDay, type GamificationProfile,
} from '../api';
import { LoadingState } from './StateViews';
import StudyPrepCalendar from './StudyPrepCalendar';
import './Practice.css';

/* „Progres" (brief §3.1 / Epic 3) — o singură destinație pentru tot ce arată cât ai avansat:
   Rezumat, Calendar, De revizuit, Istoric și Traseul meu. */

const SummaryPanel = lazy(() => import('./progress/SummaryPanel'));
const ReviewList = lazy(() => import('./progress/ReviewList'));
const HistoryList = lazy(() => import('./progress/HistoryList'));
const LearningPath = lazy(() => import('./LearningPath'));

const TABS = [
  { id: 'rezumat', label: 'Rezumat', icon: LayoutDashboard },
  { id: 'calendar', label: 'Calendar', icon: CalendarDays },
  { id: 'revizuit', label: 'De revizuit', icon: RotateCcw },
  { id: 'istoric', label: 'Istoric', icon: History },
  { id: 'traseu', label: 'Traseul meu', icon: Route },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function Progress() {
  const [tab, setTab] = useState<TabId>('rezumat');
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
          <p>Tot ce arată cât ai avansat — rezumat, calendar, de revizuit, istoric și traseul tău — într-un singur loc.</p>
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
          {tab === 'rezumat' && <SummaryPanel />}
          {tab === 'revizuit' && <ReviewList />}
          {tab === 'istoric' && <HistoryList />}
          {tab === 'traseu' && <LearningPath />}
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
