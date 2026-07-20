import { useState } from 'react';
import { Lightbulb } from 'lucide-react';
import { getExerciseHints } from '../api';
import LatexRenderer from './LatexRenderer';
import './ProgressiveHints.css';

/**
 * Indicii progresive pentru un exercițiu.
 * Elevul cere câte un indiciu pe rând (mic → mare → decisiv) înainte de a
 * vedea răspunsul — încurajează să încerce singur. Indiciile se încarcă lazy
 * la primul click și sunt cache-uite pe backend per exercițiu.
 */
export default function ProgressiveHints({ exerciseId }: { exerciseId: string }) {
  const [hints, setHints] = useState<string[] | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const handleNext = async () => {
    if (hints === null) {
      setLoading(true);
      setError(false);
      try {
        const res = await getExerciseHints(exerciseId);
        const list = res.data.hints || [];
        setHints(list);
        setRevealed(list.length ? 1 : 0);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
      return;
    }
    setRevealed((r) => Math.min(r + 1, hints.length));
  };

  const noHints = hints !== null && hints.length === 0;
  const allShown = hints !== null && revealed >= hints.length;
  const showButton = !noHints && !allShown;

  const buttonLabel = loading
    ? 'Se încarcă…'
    : hints === null
      ? 'Cere un indiciu'
      : `Următorul indiciu (${revealed}/${hints.length})`;

  return (
    <div className="hints-block">
      {hints && revealed > 0 && (
        <ol className="hints-list">
          {hints.slice(0, revealed).map((h, i) => (
            <li key={i} className="hint-item">
              <span className="hint-num">{i + 1}</span>
              <span className="hint-text"><LatexRenderer text={h} /></span>
            </li>
          ))}
        </ol>
      )}

      {noHints && (
        <div className="hints-empty">Nu sunt indicii disponibile pentru acest exercițiu.</div>
      )}

      {showButton && (
        <button type="button" className="hint-btn" onClick={handleNext} disabled={loading}>
          <Lightbulb size={15} />
          {error ? 'Reîncearcă' : buttonLabel}
        </button>
      )}
    </div>
  );
}
