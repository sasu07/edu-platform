import { useEffect, useState } from 'react';
import { getReviewItems, resolveReviewItem, type ReviewItem } from '../../api';
import { LoadingState, EmptyState } from '../StateViews';
import LatexRenderer from '../LatexRenderer';
import ProgressiveHints from '../ProgressiveHints';
import './progress-panels.css';

/* „De revizuit" (Epic 3 §6.2): exerciții deschise automat sau manual.
   Fiecare card are cel mult trei acțiuni și motive în limbaj simplu. */

function reasonInfo(reason: string): { label: string; cls: string } {
  if (reason === 'wrong' || reason === 'failed') return { label: 'răspuns greșit', cls: 'wrong' };
  if (reason === 'blocked' || reason === 'partial' || reason === 'incomplete') return { label: 'lăsat neterminat', cls: 'incomplete' };
  return { label: 'marcat de tine', cls: 'manual' };
}

export default function ReviewList() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    getReviewItems()
      .then((r) => setItems(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggle = (id: string) => setExpanded((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const expand = (id: string) => setExpanded((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));

  const handleRemove = async (id: string) => {
    setBusyId(id);
    try {
      await resolveReviewItem(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
    } catch {
      /* rămâne în listă dacă a eșuat */
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <LoadingState lines={4} />;

  if (items.length === 0) {
    return (
      <EmptyState
        title="Nimic de revizuit"
        description="Când greșești un exercițiu sau îl marchezi, apare aici ca să te întorci la el."
      />
    );
  }

  return (
    <div>
      <p className="pg-review-lead">
        {items.length === 1 ? 'Un exercițiu' : `${items.length} exerciții`} de revenit. Rezolvă din nou, cere un indiciu sau scoate-l din listă când l-ai clarificat.
      </p>
      <div className="pg-review-list">
        {items.map((item) => {
          const info = reasonInfo(item.source_reason as string);
          const open = expanded.has(item.id);
          return (
            <div key={item.id} className="pg-review-card">
              <div className="pg-review-head">
                <span className={`pg-reason ${info.cls}`}>{info.label}</span>
                <span className="pg-review-meta">
                  ultima dată: {new Date(item.last_flagged_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long' })}
                </span>
              </div>

              {open && (
                <div className="pg-review-body">
                  <LatexRenderer text={item.statement_latex || item.statement_text || ''} />
                  <ProgressiveHints exerciseId={item.id} />
                  {item.answer_latex && (
                    <div className="pg-review-answer">
                      <span className="pg-review-answer-label">Răspuns:</span>
                      <LatexRenderer text={item.answer_latex} />
                    </div>
                  )}
                </div>
              )}

              <div className="pg-review-actions">
                <button className="pg-act primary" type="button" onClick={() => toggle(item.id)}>
                  {open ? 'Ascunde' : 'Rezolvă din nou'}
                </button>
                <button className="pg-act" type="button" onClick={() => expand(item.id)}>
                  Vezi un indiciu
                </button>
                <button
                  className="pg-act danger"
                  type="button"
                  onClick={() => handleRemove(item.id)}
                  disabled={busyId === item.id}
                >
                  {busyId === item.id ? 'Se scoate…' : 'Scoate din listă'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
