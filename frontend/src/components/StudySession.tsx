import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Play, Clock, CheckCircle, XCircle, Zap, BarChart2, ChevronRight, BookOpen, Timer } from 'lucide-react';
import {
  startStudySession,
  completeStudySession,
  abandonStudySession,
  getStudySessions,
  getStudyStats,
  getStudySession,
  markExerciseComplete,
  getCompletedExerciseIds,
  type SessionType,
  type StudySession as StudySessionType,
  type StudyStats,
} from '../api';
import LatexRenderer from './LatexRenderer';
import './StudySession.css';

// ─── Constants ───────────────────────────────────────────────────────────────

const BAC_DATE = new Date('2026-07-01T08:00:00');

const SESSION_CONFIG = {
  test_scurt: { label: 'Test Scurt',   icon: '⚡', exercises: 10, minutes: 60,  desc: '10 exerciții · 60 minute' },
  test_bac:   { label: 'Test BAC',     icon: '🏆', exercises: 25, minutes: 180, desc: '~25 exerciții · 3 ore' },
};

const SUBIECT_OPTIONS = [
  { value: '',   label: 'Toate subiectele' },
  { value: '1', label: 'Subiectul I'  },
  { value: '2', label: 'Subiectul II' },
  { value: '3', label: 'Subiectul III'},
];

// ─── Countdown ────────────────────────────────────────────────────────────────

function BacCountdown() {
  const [diff, setDiff] = useState(BAC_DATE.getTime() - Date.now());
  useEffect(() => {
    const id = setInterval(() => setDiff(BAC_DATE.getTime() - Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (diff <= 0) return <div className="bac-countdown done">BAC 2026 — Mult succes!</div>;

  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);

  return (
    <div className="bac-countdown">
      <span className="bac-countdown-label">BAC 2026 în:</span>
      <span className="bac-countdown-unit">{d}<small>z</small></span>
      <span className="bac-countdown-unit">{String(h).padStart(2,'0')}<small>h</small></span>
      <span className="bac-countdown-unit">{String(m).padStart(2,'0')}<small>m</small></span>
      <span className="bac-countdown-unit">{String(s).padStart(2,'0')}<small>s</small></span>
    </div>
  );
}

// ─── Live timer ───────────────────────────────────────────────────────────────

function useTimer(running: boolean) {
  const [elapsed, setElapsed] = useState(0);
  const start = useRef(Date.now());
  useEffect(() => {
    if (!running) return;
    start.current = Date.now() - elapsed * 1000;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start.current) / 1000)), 500);
    return () => clearInterval(id);
  }, [running]);
  return elapsed;
}

function formatTime(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function normalizeNumericExpression(value: string) {
  let expr = value.trim();
  if (!expr) return '';
  expr = expr.replace(/\$/g, '');
  expr = expr.replace(/^\s*[a-zA-Z]\s*=\s*/, '');
  if (expr.includes('=')) {
    const parts = expr.split('=').map((part) => part.trim()).filter(Boolean);
    expr = parts[parts.length - 1] || expr;
  }
  expr = expr.replace(/,/g, '.');
  expr = expr.replace(/\\left|\\right/g, '');
  expr = expr.replace(/\\text\{[^}]*\}/g, '');
  expr = expr.replace(/\\mathrm\{([^}]*)\}/g, '$1');
  expr = expr.replace(/\\cdot|\\times/g, '*');
  expr = expr.replace(/\\div/g, '/');
  expr = expr.replace(/\\pi/g, 'Math.PI');
  expr = expr.replace(/\bpi\b/gi, 'Math.PI');
  expr = expr.replace(/\bsqrt\s*\(/gi, 'Math.sqrt(');

  const fracPattern = /\\(?:d)?frac\s*\{([^{}]+)\}\{([^{}]+)\}/g;
  while (fracPattern.test(expr)) {
    expr = expr.replace(fracPattern, '(($1)/($2))');
  }

  const sqrtPattern = /\\sqrt\s*\{([^{}]+)\}/g;
  while (sqrtPattern.test(expr)) {
    expr = expr.replace(sqrtPattern, 'Math.sqrt($1)');
  }

  expr = expr.replace(/\{/g, '(').replace(/\}/g, ')');
  expr = expr.replace(/\s+/g, '');
  return expr;
}

function evaluateNumericExpression(value: string): number | null {
  const expr = normalizeNumericExpression(value);
  if (!expr) return null;
  if (/[a-zA-Z]/.test(expr.replace(/Math|PI|sqrt/g, ''))) {
    const fallbackMatch = expr.match(/([\-]?\d+(?:\.\d+)?(?:\/[\-]?\d+(?:\.\d+)?)?)$/);
    if (!fallbackMatch) return null;
    return evaluateNumericExpression(fallbackMatch[1]);
  }
  if (!/^[0-9+\-*/().MathPIsqrt]+$/.test(expr)) return null;
  try {
    const result = Function(`"use strict"; return (${expr});`)();
    if (typeof result !== 'number' || !Number.isFinite(result)) return null;
    return result;
  } catch {
    return null;
  }
}

function isNumericAutoCheckAvailable(answer: string | undefined | null, numericValue?: number | null) {
  if (typeof numericValue === 'number' && Number.isFinite(numericValue)) return true;
  if (!answer) return false;
  return evaluateNumericExpression(answer) !== null;
}

function isCloseEnough(actual: number, expected: number) {
  return Math.abs(actual - expected) < 1e-6;
}

// ─── Configure Phase ──────────────────────────────────────────────────────────

interface ConfigureProps {
  onStart: (session: StudySessionType) => void;
  planDayId?: string;
  defaultType?: SessionType;
  defaultFilters?: Record<string, any>;
}

function getStartErrorMessage(error: any) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') {
    if (detail.toLowerCase().includes('no exercises') || detail.toLowerCase().includes('nu există')) {
      return 'Nu am găsit suficiente exerciții pentru filtrele alese. Încearcă fără filtru pe subiect sau schimbă tipul sesiunii.';
    }
    return detail;
  }
  return 'Eroare la pornirea sesiunii.';
}

function ConfigurePhase({ onStart, planDayId, defaultType = 'test_scurt', defaultFilters = {} }: ConfigureProps) {
  const [sessionType, setSessionType] = useState<SessionType>(defaultType);
  const [subiect, setSubiect] = useState<string>(defaultFilters.subiect_tag || '');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const exactSetMode = Boolean(defaultFilters.exercise_set_id);

  const handleStart = async () => {
    setStarting(true);
    setError('');
    try {
      const filters: Record<string, any> = { ...defaultFilters };
      if (!exactSetMode) {
        if (subiect) filters.subiect_tag = subiect;
      }
      const res = await startStudySession({ session_type: sessionType, filters, plan_day_id: planDayId });
      onStart(res.data);
    } catch (e: any) {
      setError(getStartErrorMessage(e));
      setStarting(false);
    }
  };

  const cfg = SESSION_CONFIG[sessionType];

  return (
    <div className="ss-configure">
      <BacCountdown />

      <div className="ss-section-title">Alege tipul sesiunii</div>
      <div className="ss-type-cards">
        {(Object.entries(SESSION_CONFIG) as [SessionType, typeof SESSION_CONFIG.test_scurt][]).map(([key, c]) => (
          <button
            key={key}
            className={`ss-type-card${sessionType === key ? ' selected' : ''}`}
            onClick={() => setSessionType(key)}
          >
            <span className="ss-type-icon">{c.icon}</span>
            <div>
              <div className="ss-type-name">{c.label}</div>
              <div className="ss-type-desc">{c.desc}</div>
            </div>
            {sessionType === key && <CheckCircle size={18} className="ss-type-check" />}
          </button>
        ))}
      </div>

      <div className="ss-section-title">Filtre exerciții</div>
      <div className="ss-filters">
        <label className="ss-filter-label">Subiect
          <select className="ss-select" value={subiect} onChange={e => setSubiect(e.target.value)} disabled={exactSetMode}>
            {SUBIECT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </div>

      {exactSetMode && (
        <div className="ss-info-row">
          <BookOpen size={15} />
          <span>Sesiunea va folosi exact setul salvat pe care l-ai planificat.</span>
        </div>
      )}

      <div className="ss-info-row">
        <Timer size={15} />
        <span>Vei lucra <strong>{cfg.exercises} exerciții</strong> în maxim <strong>{cfg.minutes} minute</strong>.</span>
      </div>

      {error && <div className="ss-error">{error}</div>}

      <button className="ss-start-btn" onClick={handleStart} disabled={starting}>
        {starting ? 'Se generează…' : <><Play size={16} /> Pornește sesiunea</>}
      </button>
    </div>
  );
}

// ─── Active Phase ─────────────────────────────────────────────────────────────

interface ActiveProps {
  session: StudySessionType;
  onComplete: (durationSec: number, doneCount: number) => void;
  onAbandon: () => void;
}

function ActivePhase({ session, onComplete, onAbandon }: ActiveProps) {
  const elapsed = useTimer(true);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<string | null>(null);
  const [revealedAnswers, setRevealedAnswers] = useState<Set<string>>(new Set());
  const [answerInputs, setAnswerInputs] = useState<Record<string, string>>({});
  const [answerChecks, setAnswerChecks] = useState<Record<string, { status: 'correct' | 'incorrect' | 'invalid' | 'pending'; message: string }>>({});
  const [completing, setCompleting] = useState(false);
  const limitSec = SESSION_CONFIG[session.session_type].minutes * 60;
  const exercises = session.exercises || [];

  useEffect(() => {
    if (exercises.length > 0) {
      setExpanded(exercises[0].id);
    }
  }, [session.id]);

  useEffect(() => {
    // load already-completed from API to sync with existing progress
    getCompletedExerciseIds().then(r => {
      const set = new Set(r.data as string[]);
      setCompletedIds(new Set(exercises.map((e: any) => e.id).filter((id: string) => set.has(id))));
    }).catch(() => {});
  }, []);

  const toggleDone = useCallback(async (exerciseId: string) => {
    if (completedIds.has(exerciseId)) return; // already done, no toggle back
    try {
      await markExerciseComplete(exerciseId);
      setCompletedIds(prev => new Set([...prev, exerciseId]));
    } catch {}
  }, [completedIds]);

  const handleQuickCheck = async (exerciseId: string, expectedAnswer: string | undefined | null, expectedNumericValue?: number | null) => {
    const expected = typeof expectedNumericValue === 'number' && Number.isFinite(expectedNumericValue)
      ? expectedNumericValue
      : evaluateNumericExpression(expectedAnswer || '');
    const userValue = evaluateNumericExpression(answerInputs[exerciseId] || '');

    if (userValue === null) {
      setAnswerChecks((prev) => ({
        ...prev,
        [exerciseId]: {
          status: 'invalid',
          message: 'Scrie o valoare numerică simplă, de tip 2, 1/3, 2.5 sau sqrt(3).',
        },
      }));
      return;
    }

    if (expected === null) {
      setAnswerChecks((prev) => ({
        ...prev,
        [exerciseId]: {
          status: 'pending',
          message: 'Încă nu pot verifica automat acest răspuns. Poți continua și apoi compara cu răspunsul oficial.',
        },
      }));
      return;
    }

    if (isCloseEnough(userValue, expected)) {
      setAnswerChecks((prev) => ({
        ...prev,
        [exerciseId]: {
          status: 'correct',
          message: 'Corect. Valoarea finală este bună.',
        },
      }));
      if (!completedIds.has(exerciseId)) {
        await toggleDone(exerciseId);
      }
      return;
    }

    setAnswerChecks((prev) => ({
      ...prev,
      [exerciseId]: {
        status: 'incorrect',
        message: 'Nu pare să fie valoarea corectă. Mai verifică încă o dată calculele.',
      },
    }));
  };

  const handleComplete = async () => {
    setCompleting(true);
    await onComplete(elapsed, completedIds.size);
  };

  const doneCount = completedIds.size;
  const total = exercises.length;
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;
  const timeLeft = limitSec - elapsed;
  const timeWarning = timeLeft < 300 && timeLeft > 0;

  return (
    <div className="ss-active">
      {/* Header bar */}
      <div className="ss-active-header">
        <div className="ss-active-type">
          <span>{SESSION_CONFIG[session.session_type].icon}</span>
          <span>{SESSION_CONFIG[session.session_type].label}</span>
        </div>
        <div className={`ss-active-timer${timeWarning ? ' warning' : ''}`}>
          <Clock size={14} />
          {formatTime(elapsed)}
          {timeLeft > 0 && <span className="ss-timer-limit">/ {formatTime(limitSec)}</span>}
        </div>
        <div className="ss-active-progress-text">{doneCount}/{total} rezolvate</div>
      </div>

      {/* Progress bar */}
      <div className="ss-progress-bar">
        <div className="ss-progress-fill" style={{ width: `${pct}%` }} />
      </div>

      {/* Exercise list */}
      <div className="ss-ex-list">
        {exercises.map((ex: any, idx: number) => {
          const done = completedIds.has(ex.id);
          const open = expanded === ex.id;
          const canAutoCheck = isNumericAutoCheckAvailable(ex.answer_latex, ex.answer_numeric_value);
          const revealed = revealedAnswers.has(ex.id);
          const checkResult = answerChecks[ex.id];
          return (
            <div key={ex.id} className={`ss-ex-item${done ? ' done' : ''}`}>
              <div className="ss-ex-row" onClick={() => setExpanded(open ? null : ex.id)}>
                <span className="ss-ex-num">{idx + 1}</span>
                <div className="ss-ex-preview">
                  <LatexRenderer text={(ex.statement_text || ex.statement_latex || '').slice(0, 120)} />
                </div>
                <div className="ss-ex-actions">
                  {canAutoCheck && <span className="ss-ex-quick-badge">Verificare rapidă</span>}
                  {done
                    ? <span className="ss-ex-done-badge"><CheckCircle size={15} /> Rezolvat</span>
                    : <button className="ss-ex-done-btn" onClick={e => { e.stopPropagation(); toggleDone(ex.id); }}>
                        <CheckCircle size={14} /> Am terminat
                      </button>
                  }
                  <button
                    className="ss-ex-open-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpanded(open ? null : ex.id);
                    }}
                  >
                    {open ? 'Ascunde' : 'Deschide'}
                  </button>
                  <ChevronRight size={14} className={`ss-ex-chevron${open ? ' open' : ''}`} />
                </div>
              </div>
              {open && (
                <div className="ss-ex-body">
                  <LatexRenderer text={ex.statement_latex || ex.statement_text || ''} />

                  <div className={`ss-answer-checker${canAutoCheck ? '' : ' disabled'}`}>
                    <div className="ss-answer-checker-label">Răspunsul meu</div>
                    <div className="ss-answer-checker-hint">
                      {canAutoCheck
                        ? 'Dacă răspunsul final este o valoare numerică, scrie aici unde ai ajuns și îți spun imediat dacă este corect.'
                        : 'Poți nota aici răspunsul final la care ai ajuns. Pentru acest exercițiu nu am încă verificare automată disponibilă.'}
                    </div>
                    <div className="ss-answer-checker-row">
                      <input
                        className="ss-answer-input"
                        value={answerInputs[ex.id] || ''}
                        onChange={(e) => setAnswerInputs((prev) => ({ ...prev, [ex.id]: e.target.value }))}
                        placeholder={canAutoCheck ? 'Ex: 2, 1/3, 2.5, sqrt(3)' : 'Scrie răspunsul final aici'}
                      />
                      <button
                        className="ss-answer-check-btn"
                        onClick={() => handleQuickCheck(ex.id, ex.answer_latex, ex.answer_numeric_value)}
                        disabled={!answerInputs[ex.id]?.trim()}
                      >
                        Verifică
                      </button>
                    </div>
                    {!canAutoCheck && !checkResult && (
                      <div className="ss-answer-feedback pending">
                        Verificarea automată merge acum doar pentru răspunsuri finale numerice clare.
                      </div>
                    )}
                    {checkResult && (
                      <div className={`ss-answer-feedback ${checkResult.status}`}>
                        {checkResult.message}
                      </div>
                    )}
                  </div>

                  {ex.answer_latex && (
                    <div className="ss-answer-toggle-wrap">
                      <button
                        className="ss-answer-toggle-btn"
                        onClick={() => setRevealedAnswers((prev) => {
                          const next = new Set(prev);
                          if (next.has(ex.id)) next.delete(ex.id);
                          else next.add(ex.id);
                          return next;
                        })}
                      >
                        {revealed ? 'Ascunde răspunsul oficial' : 'Vezi răspunsul oficial'}
                      </button>
                    </div>
                  )}

                  {revealed && ex.answer_latex && (
                    <div className="ss-ex-answer">
                      <span className="ss-ex-answer-label">Răspuns:</span>
                      <LatexRenderer text={ex.answer_latex} />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer actions */}
      <div className="ss-active-footer">
        <button className="ss-abandon-btn" onClick={onAbandon} disabled={completing}>
          <XCircle size={15} /> Abandonează
        </button>
        <button className="ss-complete-btn" onClick={handleComplete} disabled={completing || doneCount === 0}>
          {completing ? 'Se finalizează…' : <><CheckCircle size={15} /> Finalizează sesiunea</>}
        </button>
      </div>
    </div>
  );
}

// ─── Summary Phase ────────────────────────────────────────────────────────────

interface SummaryProps {
  session: StudySessionType;
  durationSec: number;
  doneCount: number;
  xpGained: number;
  onNew: () => void;
}

function recommendationToSubiect(recommendation: string | null | undefined) {
  if (!recommendation) return '';
  const match = recommendation.match(/([123])/);
  return match?.[1] || '';
}

function SummaryPhase({ session, durationSec, doneCount, xpGained, onNew }: SummaryProps) {
  const navigate = useNavigate();
  const total = session.exercises_total || session.exercises?.length || 0;
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;
  const cfg = SESSION_CONFIG[session.session_type];
  const isGood = pct >= 80;
  const [stats, setStats] = useState<StudyStats | null>(null);

  useEffect(() => {
    getStudyStats()
      .then((res) => setStats(res.data))
      .catch(() => setStats(null));
  }, []);

  const recommendation = stats?.recommendation || null;
  const recommendationSubiect = recommendationToSubiect(recommendation);

  const handleRecommendedSession = () => {
    const params = new URLSearchParams({ type: 'test_scurt' });
    if (recommendationSubiect) {
      params.set('subiect', recommendationSubiect);
    }
    navigate(`/app/study-session?${params.toString()}`);
  };

  const handleRecommendedExercises = () => {
    if (!recommendationSubiect) {
      navigate('/app/exercises');
      return;
    }
    navigate(`/app/exercises?subiect=${recommendationSubiect}`);
  };

  return (
    <div className="ss-summary">
      <div className={`ss-summary-hero${isGood ? ' good' : ''}`}>
        <div className="ss-summary-icon">{isGood ? '🏆' : '📊'}</div>
        <div className="ss-summary-title">{isGood ? 'Sesiune excelentă!' : 'Sesiune finalizată'}</div>
        <div className="ss-summary-subtitle">{cfg.label}</div>
      </div>

      <div className="ss-summary-stats">
        <div className="ss-stat-card">
          <CheckCircle size={20} className="ss-stat-icon green" />
          <div className="ss-stat-val">{doneCount}/{total}</div>
          <div className="ss-stat-label">Exerciții rezolvate</div>
        </div>
        <div className="ss-stat-card">
          <Clock size={20} className="ss-stat-icon blue" />
          <div className="ss-stat-val">{formatTime(durationSec)}</div>
          <div className="ss-stat-label">Timp petrecut</div>
        </div>
        <div className="ss-stat-card">
          <BarChart2 size={20} className="ss-stat-icon orange" />
          <div className="ss-stat-val">{pct}%</div>
          <div className="ss-stat-label">Completare</div>
        </div>
        <div className="ss-stat-card highlight">
          <Zap size={20} className="ss-stat-icon yellow" />
          <div className="ss-stat-val">+{xpGained}</div>
          <div className="ss-stat-label">XP câștigat</div>
        </div>
      </div>

      {session.avg_difficulty != null && (
        <div className="ss-summary-diff">
          Dificultate medie: <strong>{Number(session.avg_difficulty).toFixed(1)}</strong>
        </div>
      )}

      {isGood && session.session_type === 'test_bac' && (
        <div className="ss-summary-bonus">
          ⚡ Bonus XP aplicat pentru completare ≥80% la Test BAC!
        </div>
      )}

      {recommendation && (
        <div className="ss-recommendation">
          💡 Următorul pas recomandat: lucrează mai mult la <strong>{recommendation}</strong>
        </div>
      )}

      <div className="ss-summary-actions">
        <button className="ss-start-btn" onClick={onNew}>
          <Play size={15} /> Sesiune nouă
        </button>
        {recommendation && (
          <>
            <button className="ss-start-btn" onClick={handleRecommendedSession}>
              <Timer size={15} /> Sesiune recomandată
            </button>
            <button className="ss-start-btn" onClick={handleRecommendedExercises}>
              <BookOpen size={15} /> Exersează {recommendation}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ─── History ──────────────────────────────────────────────────────────────────

function HistoryTab({ onStartNew }: { onStartNew: () => void }) {
  const [sessions, setSessions] = useState<StudySessionType[]>([]);
  const [stats, setStats] = useState<StudyStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStudySessions(), getStudyStats()])
      .then(([s, st]) => {
        setSessions(Array.isArray(s.data) ? s.data : []);
        setStats(st.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="ss-loading">Se încarcă...</div>;

  return (
    <div className="ss-history">
      {stats && (
        <div className="ss-stats-row">
          <div className="ss-mini-stat">
            <div className="ss-mini-val">{stats.total_sessions}</div>
            <div className="ss-mini-label">Sesiuni totale</div>
          </div>
          <div className="ss-mini-stat">
            <div className="ss-mini-val">{stats.total_exercises}</div>
            <div className="ss-mini-label">Exerciții rezolvate</div>
          </div>
          <div className="ss-mini-stat">
            <div className="ss-mini-val">{stats.total_xp}</div>
            <div className="ss-mini-label">XP total</div>
          </div>
          <div className="ss-mini-stat">
            <div className="ss-mini-val">{stats.avg_completion_pct}%</div>
            <div className="ss-mini-label">Completare medie</div>
          </div>
        </div>
      )}

      {stats?.subiect_progress && stats.subiect_progress.length > 0 && (
        <div className="ss-chapter-progress">
          <div className="ss-section-title">Progres pe subiecte</div>
          {stats.subiect_progress.map(sp => (
            <div key={sp.subiect} className="ss-chapter-row">
              <span className="ss-chapter-label">{sp.subiect}</span>
              <div className="ss-chapter-bar">
                <div className="ss-chapter-fill" style={{ width: `${sp.pct}%` }} />
              </div>
              <span className="ss-chapter-pct">{sp.pct}%</span>
            </div>
          ))}
        </div>
      )}

      {stats?.recommendation && (
        <div className="ss-recommendation">
          💡 Recomandare: lucrează mai mult la <strong>{stats.recommendation}</strong>
        </div>
      )}

      {sessions.length === 0 ? (
        <div className="ss-empty">
          <div>Nu ai sesiuni de studiu înregistrate.</div>
          <button className="ss-start-btn" onClick={onStartNew}>
            <Play size={15} /> Pornește prima sesiune
          </button>
        </div>
      ) : (
        <div className="ss-history-list">
          {sessions.map(s => {
            const cfg = SESSION_CONFIG[s.session_type];
            const pct = s.exercises_total > 0 ? Math.round((s.exercises_completed / s.exercises_total) * 100) : 0;
            return (
              <div key={s.id} className={`ss-history-card status-${s.status}`}>
                <div className="ss-history-left">
                  <span className="ss-history-icon">{cfg.icon}</span>
                  <div>
                    <div className="ss-history-type">{cfg.label}</div>
                    <div className="ss-history-date">
                      {new Date(s.started_at).toLocaleDateString('ro-RO', { day: 'numeric', month: 'long', year: 'numeric' })}
                    </div>
                  </div>
                </div>
                <div className="ss-history-right">
                  <span className="ss-history-stat">{s.exercises_completed}/{s.exercises_total} ex.</span>
                  <span className="ss-history-stat">{pct}%</span>
                  {s.xp_gained > 0 && <span className="ss-history-xp">+{s.xp_gained} XP</span>}
                  <span className={`ss-history-status ss-status-${s.status}`}>
                    {s.status === 'completed' ? 'Finalizat' : s.status === 'abandoned' ? 'Abandonat' : 'Activ'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

type Phase = 'configure' | 'active' | 'summary';
type Tab = 'new' | 'history';

interface StudySessionProps {
  planDayId?: string;
  defaultType?: SessionType;
  defaultFilters?: Record<string, any>;
  onSessionDone?: () => void;
}

export default function StudySession({ planDayId: planDayIdProp, defaultType: defaultTypeProp, defaultFilters, onSessionDone }: StudySessionProps) {
  const [searchParams] = useSearchParams();
  const planDayId = planDayIdProp || searchParams.get('plan') || undefined;
  const resumeSessionId = searchParams.get('resume') || undefined;
  const defaultType = (defaultTypeProp || searchParams.get('type') as SessionType || 'test_scurt');
  const mergedDefaultFilters = {
    ...(defaultFilters || {}),
    ...(searchParams.get('subiect') ? { subiect_tag: searchParams.get('subiect') } : {}),
    ...(searchParams.get('set') ? { exercise_set_id: searchParams.get('set') } : {}),
  };
  const [tab, setTab] = useState<Tab>('new');
  const [phase, setPhase] = useState<Phase>('configure');
  const [session, setSession] = useState<StudySessionType | null>(null);
  const [summaryDuration, setSummaryDuration] = useState(0);
  const [summaryDone, setSummaryDone] = useState(0);
  const [summaryXp, setSummaryXp] = useState(0);
  const [loadingResume, setLoadingResume] = useState(Boolean(resumeSessionId));

  useEffect(() => {
    if (!resumeSessionId) return;

    setLoadingResume(true);
    getStudySession(resumeSessionId)
      .then((res) => {
        const resumedSession = res.data;
        if (resumedSession?.status === 'active') {
          setSession(resumedSession);
          setPhase('active');
          setTab('new');
        }
      })
      .catch(() => {})
      .finally(() => setLoadingResume(false));
  }, [resumeSessionId]);

  const handleStart = (s: StudySessionType) => {
    setSession(s);
    setPhase('active');
  };

  const handleComplete = async (durationSec: number, doneCount: number) => {
    if (!session) return;
    try {
      const res = await completeStudySession(session.id, { duration_sec: durationSec, exercises_completed: doneCount });
      setSummaryDuration(durationSec);
      setSummaryDone(doneCount);
      setSummaryXp(res.data.xp_gained || 0);
      setSession(res.data);
      setPhase('summary');
      onSessionDone?.();
    } catch {
      // still show summary with local data
      setSummaryDuration(durationSec);
      setSummaryDone(doneCount);
      setPhase('summary');
    }
  };

  const handleAbandon = async () => {
    if (!session) return;
    try { await abandonStudySession(session.id); } catch {}
    setPhase('configure');
    setSession(null);
  };

  const handleNew = () => {
    setPhase('configure');
    setSession(null);
    setTab('new');
  };

  return (
    <div className="study-session-wrap">
      <div className="ss-page-header">
        <BookOpen size={22} />
        <h2>Sesiuni de studiu</h2>
      </div>

      {loadingResume && <div className="ss-loading">Se reia sesiunea activă...</div>}

      {!loadingResume && phase !== 'active' && (
        <div className="ss-tabs">
          <button className={`ss-tab-btn${tab === 'new' ? ' active' : ''}`} onClick={() => { setTab('new'); if (phase === 'summary') handleNew(); }}>
            <Play size={14} /> Sesiune nouă
          </button>
          <button className={`ss-tab-btn${tab === 'history' ? ' active' : ''}`} onClick={() => setTab('history')}>
            <BarChart2 size={14} /> Istoric & statistici
          </button>
        </div>
      )}

      {!loadingResume && tab === 'new' && phase === 'configure' && (
        <ConfigurePhase
          onStart={handleStart}
          planDayId={planDayId}
          defaultType={defaultType}
          defaultFilters={mergedDefaultFilters}
        />
      )}

      {!loadingResume && tab === 'new' && phase === 'active' && session && (
        <ActivePhase
          session={session}
          onComplete={handleComplete}
          onAbandon={handleAbandon}
        />
      )}

      {!loadingResume && tab === 'new' && phase === 'summary' && session && (
        <SummaryPhase
          session={session}
          durationSec={summaryDuration}
          doneCount={summaryDone}
          xpGained={summaryXp}
          onNew={handleNew}
        />
      )}

      {!loadingResume && tab === 'history' && <HistoryTab onStartNew={() => { setTab('new'); setPhase('configure'); }} />}
    </div>
  );
}
