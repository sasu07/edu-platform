import { lazy, Suspense, useState } from 'react';
import { Link } from 'react-router-dom';
import { Play, BookOpen, FileText, Layers } from 'lucide-react';
import { LoadingState } from './StateViews';
import './Practice.css';

/* „Exersează" (brief §3.1) — o singură destinație care găzduiește exerciții,
   subiecte și variante ca tab-uri, cu sesiunea ghidată ca acțiune principală. */

const StudentExercises = lazy(() => import('./StudentExercises'));
const SourceLibrary = lazy(() => import('./SourceLibrary'));
const VariantBuilderAuto = lazy(() => import('./VariantBuilderAuto'));

const TABS = [
  { id: 'exercitii', label: 'Exerciții', icon: BookOpen },
  { id: 'subiecte', label: 'Subiecte', icon: FileText },
  { id: 'variante', label: 'Variante', icon: Layers },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function Practice() {
  const [tab, setTab] = useState<TabId>('exercitii');

  return (
    <div className="prac">
      <header className="prac-head">
        <div className="prac-head-copy">
          <h1>Exersează</h1>
          <p>Alege ce vrei să lucrezi azi — sau pornește direct o sesiune ghidată.</p>
        </div>
        <Link to="/app/study-session?type=test_scurt" className="prac-cta">
          <Play size={18} /> Începe o sesiune
        </Link>
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
          {tab === 'exercitii' && <StudentExercises />}
          {tab === 'subiecte' && <SourceLibrary />}
          {tab === 'variante' && <VariantBuilderAuto />}
        </Suspense>
      </div>
    </div>
  );
}
