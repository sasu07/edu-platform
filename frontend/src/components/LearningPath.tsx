import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, Star, Lock, CheckCircle, Zap, RotateCcw, BookOpen } from 'lucide-react';
import {
  getLearningPath,
  getTodayRecommendations,
  getSkillTree,
  getDiagnosticHistory,
  updateNodeProgress,
  submitSRReview,
  type LearningPathNode,
  type LearningPathResponse,
  type TodayRecommendation,
  type SkillTreeSubiect,
  type AIPlan,
  type DiagnosticHistoryEntry,
  type DiagnosticWeakTopic,
} from '../api';
import DiagnosticTest from './DiagnosticTest';
import LatexRenderer from './LatexRenderer';
import { evaluateNumericExpression } from '../utils/numericExpression';
import './LearningPath.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusIcon(status: LearningPathNode['status']) {
  if (status === 'mastered') return <CheckCircle size={16} color="#16a34a" />;
  if (status === 'in_progress') return <Zap size={16} color="#d97706" />;
  return <div className="lp-node-dot pending" />;
}

function priorityLabel(p: number) {
  if (p === 1) return { label: 'Urgent', color: '#dc2626', bg: '#fef2f2' };
  if (p === 2) return { label: 'Important', color: '#d97706', bg: '#fffbeb' };
  if (p === 4) return { label: 'OK', color: '#2563eb', bg: '#eff6ff' };
  return { label: 'Neexaminat', color: '#6b7280', bg: '#f3f4f6' };
}

// ─── AI Plan Card ─────────────────────────────────────────────────────────────

function AIPlanCard({ plan }: { plan: AIPlan }) {
  const [expanded, setExpanded] = useState(false);
  const nivelColors: Record<string, string> = {
    incepator: '#dc2626',
    mediu: '#d97706',
    avansat: '#16a34a',
  };
  const nivelLabels: Record<string, string> = {
    incepator: 'Începător',
    mediu: 'Mediu',
    avansat: 'Avansat',
  };
  const color = nivelColors[plan.nivel_general] || '#6b7280';

  return (
    <div className="lp-ai-plan">
      <div className="lp-ai-plan-header">
        <div className="lp-ai-plan-badge">
          {plan._source === 'claude' ? '✦ Plan generat de Claude AI' : '📋 Plan recomandat'}
        </div>
        <span className="lp-ai-nivel" style={{ color, borderColor: color }}>
          {nivelLabels[plan.nivel_general] || plan.nivel_general}
        </span>
      </div>

      <p className="lp-ai-rezumat">{plan.rezumat}</p>

      {plan.prioritati_urgente?.length > 0 && (
        <div className="lp-ai-urgente">
          <div className="lp-ai-section-title">⚠️ Priorități urgente</div>
          <ul className="lp-ai-list">
            {plan.prioritati_urgente.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}

      {/* Săptămâni — primele 2 mereu vizibile, restul sub toggle */}
      <div className="lp-ai-weeks">
        <div className="lp-ai-section-title">📅 Plan săptămânal</div>
        {plan.saptamani.slice(0, expanded ? 999 : 2).map(week => (
          <div key={week.numar} className="lp-ai-week">
            <div className="lp-ai-week-header">
              <span className="lp-ai-week-num">Săpt. {week.numar}</span>
              <span className="lp-ai-week-title">{week.titlu}</span>
              <span className="lp-ai-week-time">{week.timp_zilnic_minute} min/zi</span>
            </div>
            <div className="lp-ai-week-focus">{week.focus_principal}</div>
            {week.obiective?.length > 0 && (
              <ul className="lp-ai-week-objectives">
                {week.obiective.map((o, i) => <li key={i}>{o}</li>)}
              </ul>
            )}
            {week.strategie && (
              <div className="lp-ai-week-strategy">💡 {week.strategie}</div>
            )}
          </div>
        ))}
        {plan.saptamani.length > 2 && (
          <button className="lp-ai-expand-btn" onClick={() => setExpanded(e => !e)}>
            {expanded ? '▲ Arată mai puțin' : `▼ Vezi toate ${plan.saptamani.length} săptămânile`}
          </button>
        )}
      </div>

      {plan.sfaturi_practice?.length > 0 && (
        <div className="lp-ai-sfaturi">
          <div className="lp-ai-section-title">💪 Sfaturi practice</div>
          <ul className="lp-ai-list">
            {plan.sfaturi_practice.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}

      <div className="lp-ai-motivatie">
        <span>🎯</span>
        <em>{plan.motivatie}</em>
      </div>
    </div>
  );
}

// ─── Node Card ────────────────────────────────────────────────────────────────

function NodeCard({ node, blurred }: { node: LearningPathNode; blurred?: boolean }) {
  const p = priorityLabel(node.priority);
  const pct = node.target_exercises > 0
    ? Math.min(100, Math.round((node.exercises_seen / node.target_exercises) * 100))
    : 0;

  return (
    <div className={`lp-node-card${blurred ? ' blurred' : ''}`}>
      <div className="lp-node-left">
        {statusIcon(node.status)}
        <div className="lp-node-info">
          <div className="lp-node-topic">{node.topic_label}</div>
          <div className="lp-node-meta">
            <span className="lp-node-subiect">S{node.subiect_num}</span>
            <span className="lp-node-priority-tag" style={{ color: p.color, background: p.bg }}>
              {p.label}
            </span>
            {node.diagnostic_score_pct !== null && (
              <span className="lp-node-diag">Diagnostic: {node.diagnostic_score_pct}%</span>
            )}
          </div>
        </div>
      </div>
      <div className="lp-node-right">
        <div className="lp-node-progress-row">
          <div className="lp-node-track">
            <div className="lp-node-fill" style={{ width: `${pct}%` }} />
          </div>
          <span className="lp-node-pct">{pct}%</span>
        </div>
        <div className="lp-node-count">
          {node.exercises_seen}/{node.target_exercises} ex.
        </div>
      </div>
    </div>
  );
}

// ─── Skill Tree ───────────────────────────────────────────────────────────────

function SkillTreeView({ subiects }: { subiects: SkillTreeSubiect[] }) {
  return (
    <div className="lp-skill-tree">
      {subiects.map(s => (
        <div key={s.subiect} className="lp-subiect-block">
          <div className="lp-subiect-header">
            <div className="lp-subiect-title">{s.label}</div>
            <div className="lp-subiect-badge">
              {s.mastered}/{s.total} stăpânite
            </div>
          </div>
          <div className="lp-subiect-nodes">
            {s.topics.map(t => {
              const s_icon = t.status === 'mastered'
                ? '✅' : t.status === 'in_progress' ? '🔄' : '⬜';
              return (
                <div key={t.id} className={`lp-tree-node lp-tree-${t.status}`}>
                  <span>{s_icon}</span>
                  <div className="lp-tree-node-label">{t.topic_label}</div>
                  {t.score_pct > 0 && (
                    <div className="lp-tree-node-score">{t.score_pct}%</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Today Recommendations ────────────────────────────────────────────────────

function TodayView() {
  const [recs, setRecs] = useState<TodayRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [answered, setAnswered] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, boolean | null>>({});
  const [error, setError] = useState('');

  useEffect(() => {
    getTodayRecommendations()
      .then(r => setRecs(r.data.recommendations))
      .catch(e => setError(e?.response?.data?.detail || 'Eroare la încărcarea recomandărilor.'))
      .finally(() => setLoading(false));
  }, []);

  const handleCheck = async (rec: TodayRecommendation) => {
    const ans = answered[rec.id] || '';
    if (!ans.trim()) return;

    let correct = false;
    const target = rec.answer_numeric_value;
    if (target !== undefined && target !== null) {
      const value = evaluateNumericExpression(ans);
      correct = value !== null && Math.abs(value - target) < 1e-4;
    }

    setResults(prev => ({ ...prev, [rec.id]: correct }));

    if (rec.source === 'spaced_repetition') {
      await submitSRReview(rec.id, correct ? 4 : 1).catch(() => {});
    } else if (rec.node_id) {
      await updateNodeProgress(rec.node_id, rec.id, correct).catch(() => {});
    }
  };

  if (loading) return <div className="lp-loading">Se încarcă recomandările…</div>;
  if (error) return <div className="lp-error">{error}</div>;
  if (recs.length === 0) {
    return (
      <div className="lp-empty">
        <CheckCircle size={32} color="#16a34a" />
        <div>Nu ai exerciții recomandate azi. Revino mâine!</div>
      </div>
    );
  }

  return (
    <div className="lp-today">
      {recs.map(rec => {
        const res = results[rec.id];
        const isAnswered = res !== undefined;
        return (
          <div key={rec.id} className={`lp-today-card${isAnswered ? (res ? ' correct' : ' wrong') : ''}`}>
            <div className="lp-today-meta">
              <span className={`lp-today-source ${rec.source}`}>
                {rec.source === 'spaced_repetition' ? <><RotateCcw size={12} /> Recapitulare</> : <><BookOpen size={12} /> Nou</>}
              </span>
              {rec.topic_label && <span className="lp-today-topic">{rec.topic_label}</span>}
            </div>
            <div className="lp-today-statement">
              <LatexRenderer text={rec.statement_latex} />
            </div>
            {!isAnswered ? (
              <div className="lp-today-answer-row">
                <input
                  className="lp-today-input"
                  placeholder="Răspunsul tău…"
                  value={answered[rec.id] || ''}
                  onChange={e => setAnswered(prev => ({ ...prev, [rec.id]: e.target.value }))}
                  onKeyDown={e => { if (e.key === 'Enter') handleCheck(rec); }}
                />
                <button className="lp-today-check-btn" onClick={() => handleCheck(rec)}>
                  Verifică
                </button>
              </div>
            ) : (
              <div className={`lp-today-result ${res ? 'correct' : 'wrong'}`}>
                {res ? <><CheckCircle size={15} /> Corect!</> : <><span>✗</span> Greșit — exercițiul va fi recapitulat</>}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Locked Overlay ───────────────────────────────────────────────────────────

function PremiumLock({ feature }: { feature: string }) {
  const navigate = useNavigate();
  return (
    <div className="lp-lock-overlay">
      <Lock size={32} />
      <div className="lp-lock-title">Funcționalitate Premium</div>
      <div className="lp-lock-desc">{feature} este disponibil doar cu abonament Premium.</div>
      <button className="lp-lock-btn" onClick={() => navigate('/app/admin')}>
        <Star size={14} /> Upgrade la Premium
      </button>
    </div>
  );
}

// ─── History Tab ──────────────────────────────────────────────────────────────

function scoreColor(pct: number) {
  if (pct < 30) return '#dc2626';
  if (pct < 60) return '#d97706';
  if (pct < 80) return '#2563eb';
  return '#16a34a';
}

function HistoryTab({ onRetake }: { onRetake: () => void }) {
  const [entries, setEntries] = useState<DiagnosticHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    getDiagnosticHistory()
      .then(r => setEntries(r.data))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="lp-loading">Se încarcă istoricul…</div>;

  if (entries.length === 0) {
    return (
      <div className="lp-history-empty">
        <div>Nu ai nicio încercare salvată.</div>
        <button className="lp-retake-cta" onClick={onRetake}>
          <RotateCcw size={14} /> Dă primul test diagnostic
        </button>
      </div>
    );
  }

  return (
    <div className="lp-history">
      <div className="lp-history-header">
        <span>{entries.length} {entries.length === 1 ? 'încercare' : 'încercări'}</span>
        <button className="lp-retake-cta" onClick={onRetake}>
          <RotateCcw size={14} /> Reia testul
        </button>
      </div>

      {entries.map((entry, idx) => {
        const isOpen = expanded === entry.id;
        const date = new Date(entry.created_at).toLocaleDateString('ro-RO', {
          day: '2-digit', month: 'long', year: 'numeric',
          hour: '2-digit', minute: '2-digit',
        });
        const color = scoreColor(entry.score_pct);
        const weakTopics = (entry.weak_topics || [])
          .filter((t: DiagnosticWeakTopic) => t.score_pct < 60)
          .sort((a: DiagnosticWeakTopic, b: DiagnosticWeakTopic) => a.score_pct - b.score_pct);

        return (
          <div key={entry.id} className={`lp-history-card${isOpen ? ' open' : ''}`}>
            <button
              className="lp-history-card-head"
              onClick={() => setExpanded(isOpen ? null : entry.id)}
            >
              <div className="lp-history-rank">#{entries.length - idx}</div>
              <div className="lp-history-info">
                <div className="lp-history-date">{date}</div>
                <div className="lp-history-meta">
                  {entry.status === 'completed'
                    ? `${entry.correct_count}/${entry.total_exercises} corecte`
                    : entry.status === 'abandoned' ? 'Abandonat' : 'Activ'}
                  {entry.solution_file_path && (
                    <span className="lp-history-upload-badge">📎 Soluție încărcată</span>
                  )}
                </div>
              </div>
              {entry.status === 'completed' && (
                <div className="lp-history-score" style={{ color, borderColor: color }}>
                  {entry.score_pct}%
                </div>
              )}
              <span className={`lp-history-chevron${isOpen ? ' open' : ''}`}>›</span>
            </button>

            {isOpen && entry.status === 'completed' && (
              <div className="lp-history-detail">
                {weakTopics.length > 0 ? (
                  <>
                    <div className="lp-history-weak-title">Topicuri slabe:</div>
                    <div className="lp-history-weak-list">
                      {weakTopics.map((t: DiagnosticWeakTopic) => (
                        <div key={t.topic_key} className="lp-history-weak-item">
                          <span className="lp-history-weak-label">
                            {t.topic_label || t.topic_key}
                          </span>
                          <div className="lp-history-weak-bar">
                            <div
                              className="lp-history-weak-fill"
                              style={{ width: `${t.score_pct}%`, background: scoreColor(t.score_pct) }}
                            />
                          </div>
                          <span className="lp-history-weak-pct" style={{ color: scoreColor(t.score_pct) }}>
                            {t.score_pct}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="lp-history-strong">Toate topicurile stăpânite! 🎉</div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

type Tab = 'plan' | 'today' | 'tree' | 'history';

export default function LearningPath() {
  const [pathData, setPathData] = useState<LearningPathResponse | null>(null);
  const [aiPlan, setAiPlan] = useState<AIPlan | null>(null);
  const [skillTree, setSkillTree] = useState<SkillTreeSubiect[] | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('plan');
  const [loading, setLoading] = useState(true);
  const [treeLoading, setTreeLoading] = useState(false);
  const [error, setError] = useState('');
  const [showRetake, setShowRetake] = useState(false);

  const loadPath = () => {
    setLoading(true);
    getLearningPath()
      .then(r => {
        setPathData(r.data);
        if (r.data.ai_plan) setAiPlan(r.data.ai_plan as AIPlan);
      })
      .catch(e => setError(e?.response?.data?.detail || 'Eroare la încărcarea planului.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadPath(); }, []);

  useEffect(() => {
    if (activeTab !== 'tree' || !pathData?.is_premium) return;
    setTreeLoading(true);
    getSkillTree()
      .then(r => setSkillTree(r.data.subiects))
      .catch(() => setSkillTree(null))
      .finally(() => setTreeLoading(false));
  }, [activeTab, pathData?.is_premium]);

  const handlePathGenerated = () => {
    setShowRetake(false);
    loadPath();
    setActiveTab('plan');
  };

  const handleRetake = () => {
    setShowRetake(true);
    setActiveTab('plan');
  };

  if (loading) {
    return <div className="lp-page-loading">Se încarcă traseul de învățare…</div>;
  }

  // Nu există plan sau utilizatorul vrea să refacă testul
  if (!pathData?.path || showRetake) {
    return (
      <div className="lp-wrap">
        <div className="lp-page-header">
          <Brain size={24} />
          <h1 className="lp-page-title">
            {showRetake ? 'Reface testul diagnostic' : 'Traseu de Învățare Adaptat'}
          </h1>
          {showRetake && (
            <button className="lp-retake-btn" onClick={() => setShowRetake(false)}>
              ← Înapoi la plan
            </button>
          )}
        </div>
        {!showRetake && (
          <div className="lp-no-path-intro">
            <p>
              Începe cu un test diagnostic scurt pentru a-ți evalua nivelul pe toate subiectele BAC.
              Vom genera automat un plan personalizat cu exercițiile cele mai utile pentru tine.
            </p>
          </div>
        )}
        <DiagnosticTest onPathGenerated={handlePathGenerated} />
      </div>
    );
  }

  const { path, nodes, total_nodes, preview_only, is_premium } = pathData;

  return (
    <div className="lp-wrap">
      {/* Header */}
      <div className="lp-page-header">
        <Brain size={24} />
        <div>
          <h1 className="lp-page-title">Traseul tău de învățare</h1>
          <div className="lp-page-sub">
            {path!.completed_nodes}/{total_nodes} topicuri stăpânite
            {!is_premium && <span className="lp-free-badge"> · Preview gratuit</span>}
          </div>
        </div>
        <button className="lp-retake-btn" onClick={handleRetake}>
          <RotateCcw size={14} /> Reface diagnostic
        </button>
      </div>

      {/* Tabs */}
      <div className="lp-tabs">
        <button className={`lp-tab${activeTab === 'plan' ? ' active' : ''}`} onClick={() => setActiveTab('plan')}>
          Planul meu
        </button>
        <button
          className={`lp-tab${activeTab === 'today' ? ' active' : ''}`}
          onClick={() => setActiveTab('today')}
        >
          Azi
          {!is_premium && <Lock size={12} className="lp-tab-lock" />}
        </button>
        <button
          className={`lp-tab${activeTab === 'tree' ? ' active' : ''}`}
          onClick={() => setActiveTab('tree')}
        >
          Skill Tree
          {!is_premium && <Lock size={12} className="lp-tab-lock" />}
        </button>
        <button className={`lp-tab${activeTab === 'history' ? ' active' : ''}`} onClick={() => setActiveTab('history')}>
          Istoric
        </button>
      </div>

      {error && <div className="lp-error">{error}</div>}

      {/* Plan Tab */}
      {activeTab === 'plan' && (
        <div className="lp-plan">
          {aiPlan && <AIPlanCard plan={aiPlan} />}
          {nodes.map(node => <NodeCard key={node.id} node={node} />)}

          {preview_only && total_nodes > 3 && (
            <div className="lp-preview-wall">
              <div className="lp-preview-blur-nodes">
                {Array.from({ length: Math.min(2, total_nodes - 3) }).map((_, i) => (
                  <div key={i} className="lp-node-card blurred mock">
                    <div className="lp-node-left">
                      <div className="lp-node-dot pending" />
                      <div className="lp-node-info">
                        <div className="lp-node-topic">████████████</div>
                        <div className="lp-node-meta">
                          <span className="lp-node-subiect">S{i % 3 + 1}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="lp-preview-lock">
                <Lock size={28} />
                <div className="lp-preview-lock-title">
                  Mai sunt {total_nodes - 3} topicuri în planul tău
                </div>
                <div className="lp-preview-lock-desc">
                  Deblochează planul complet, recomandările zilnice și spaced repetition cu Premium.
                </div>
                <button className="lp-upgrade-btn">
                  <Star size={14} /> Upgrade la Premium
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Today Tab */}
      {activeTab === 'today' && (
        is_premium
          ? <TodayView />
          : <div className="lp-lock-wrap"><PremiumLock feature="Recomandările zilnice și spaced repetition" /></div>
      )}

      {/* Skill Tree Tab */}
      {activeTab === 'tree' && (
        is_premium
          ? (treeLoading
              ? <div className="lp-loading">Se încarcă skill tree…</div>
              : skillTree
                ? <SkillTreeView subiects={skillTree} />
                : <div className="lp-error">Nu am putut încărca skill tree.</div>
            )
          : <div className="lp-lock-wrap"><PremiumLock feature="Skill Tree cu progres vizual" /></div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <HistoryTab onRetake={handleRetake} />
      )}
    </div>
  );
}
