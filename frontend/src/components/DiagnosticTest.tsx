import { useRef, useState } from 'react';
import { CheckCircle, XCircle, BarChart2, Brain, Zap, Upload, FileText } from 'lucide-react';
import {
  startDiagnostic,
  submitDiagnostic,
  generateLearningPath,
  uploadDiagnosticSolution,
  type DiagnosticExercise,
  type DiagnosticResult,
  type DiagnosticWeakTopic,
} from '../api';
import LatexRenderer from './LatexRenderer';
import './DiagnosticTest.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scoreLabel(pct: number) {
  if (pct < 30) return { label: 'Necesită atenție', color: '#dc2626' };
  if (pct < 60) return { label: 'În formare', color: '#d97706' };
  if (pct < 80) return { label: 'Bun', color: '#2563eb' };
  return { label: 'Stăpânit', color: '#16a34a' };
}

function TopicBar({ topic }: { topic: DiagnosticWeakTopic }) {
  const s = scoreLabel(topic.score_pct);
  return (
    <div className="dt-topic-bar">
      <div className="dt-topic-bar-top">
        <span className="dt-topic-label">{topic.topic_label || topic.topic_key}</span>
        <span className="dt-topic-score" style={{ color: s.color }}>{topic.score_pct}%</span>
      </div>
      <div className="dt-topic-track">
        <div className="dt-topic-fill" style={{ width: `${topic.score_pct}%`, background: s.color }} />
      </div>
      <div className="dt-topic-meta">
        <span style={{ color: s.color, fontWeight: 700 }}>{s.label}</span>
        <span>{topic.correct}/{topic.seen} corecte</span>
      </div>
    </div>
  );
}

// ─── Phase: Welcome ───────────────────────────────────────────────────────────

function WelcomePhase({ onStart, loading }: { onStart: () => void; loading: boolean }) {
  return (
    <div className="dt-welcome">
      <div className="dt-welcome-icon"><Brain size={48} /></div>
      <h2 className="dt-welcome-title">Test Diagnostic de Nivel</h2>
      <p className="dt-welcome-desc">
        Răspunde la <strong>~15 întrebări grilă</strong> din toate subiectele BAC pentru a-ți
        identifica lacunele. La final, poți încărca și rezolvarea completă scrisă.
        Durează aproximativ <strong>15–25 de minute</strong>.
      </p>

      <div className="dt-welcome-pills">
        <div className="dt-pill"><span>📋</span> ~15 întrebări grilă</div>
        <div className="dt-pill"><span>🎯</span> S1 · S2 · S3</div>
        <div className="dt-pill"><span>📤</span> Upload soluție scrisă</div>
      </div>

      <div className="dt-welcome-free">
        <Zap size={14} /> Gratuit — nu necesită abonament
      </div>

      <button className="dt-start-btn" onClick={onStart} disabled={loading}>
        {loading ? 'Se generează testul…' : '▶ Începe testul diagnostic'}
      </button>
    </div>
  );
}

// ─── MCQ Option ───────────────────────────────────────────────────────────────

function MCQOption({
  label, text, selected, onSelect, revealed, isCorrect,
}: {
  label: string;
  text: string;
  selected: boolean;
  onSelect: () => void;
  revealed: boolean;
  isCorrect: boolean;
}) {
  let cls = 'dt-mcq-option';
  if (revealed) {
    cls += isCorrect ? ' correct' : selected ? ' wrong' : '';
  } else if (selected) {
    cls += ' selected';
  }

  return (
    <button className={cls} onClick={onSelect} disabled={revealed}>
      <span className="dt-mcq-label">{label}</span>
      <span className="dt-mcq-text"><LatexRenderer text={text} /></span>
      {revealed && isCorrect && <CheckCircle size={16} className="dt-mcq-icon correct" />}
      {revealed && selected && !isCorrect && <XCircle size={16} className="dt-mcq-icon wrong" />}
    </button>
  );
}

// ─── Phase: Test ──────────────────────────────────────────────────────────────

function TestPhase({
  exercises,
  onSubmit,
  submitting,
}: {
  exercises: DiagnosticExercise[];
  onSubmit: (answers: { exercise_id: string; selected_option?: number; answer?: string }[]) => void;
  submitting: boolean;
}) {
  const [current, setCurrent] = useState(0);
  // MCQ: selected option index (null = neselectat)
  const [selections, setSelections] = useState<Record<string, number | null>>({});
  // Exerciții fără opțiuni MCQ: răspuns text
  const [textAnswers, setTextAnswers] = useState<Record<string, string>>({});

  const ex = exercises[current];
  const total = exercises.length;
  const pct = Math.round((current / total) * 100);
  const answered = exercises.filter(e =>
    e.options ? selections[e.id] !== undefined && selections[e.id] !== null : Boolean(textAnswers[e.id])
  ).length;

  const LABELS = ['A', 'B', 'C', 'D', 'E'];

  const handleFinish = () => {
    const ans = exercises.map(e => {
      if (e.options) {
        return { exercise_id: e.id, selected_option: selections[e.id] ?? undefined };
      }
      return { exercise_id: e.id, answer: textAnswers[e.id] || '' };
    });
    onSubmit(ans);
  };

  return (
    <div className="dt-test">
      {/* Progress */}
      <div className="dt-test-header">
        <div className="dt-test-progress-text">
          Întrebarea {current + 1} din {total}
          <span className="dt-test-answered">{answered} răspunse</span>
        </div>
        <div className="dt-test-progress-bar">
          <div className="dt-test-progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Exercise card */}
      <div className="dt-ex-card">
        <div className="dt-ex-meta">
          {ex.topic_label && <span className="dt-ex-topic">{ex.topic_label}</span>}
          {ex.difficulty && <span className="dt-ex-diff">Dif. {ex.difficulty}/10</span>}
          <span className="dt-ex-type">{ex.options ? '● Grilă' : '✏ Deschis'}</span>
        </div>

        <div className="dt-ex-statement">
          <LatexRenderer text={ex.statement_latex} />
        </div>

        {ex.options ? (
          /* MCQ */
          <div className="dt-mcq-options">
            {ex.options.map((opt, idx) => (
              <MCQOption
                key={idx}
                label={LABELS[idx]}
                text={opt}
                selected={selections[ex.id] === idx}
                onSelect={() => setSelections(prev => ({ ...prev, [ex.id]: idx }))}
                revealed={false}
                isCorrect={false}
              />
            ))}
          </div>
        ) : (
          /* Open answer */
          <div className="dt-ex-answer-row">
            <label className="dt-ex-answer-label">Răspunsul tău</label>
            <input
              className="dt-ex-input"
              type="text"
              placeholder="Scrie valoarea numerică sau expresia…"
              value={textAnswers[ex.id] || ''}
              onChange={e => setTextAnswers(prev => ({ ...prev, [ex.id]: e.target.value }))}
              onKeyDown={e => { if (e.key === 'Enter' && current < total - 1) setCurrent(c => c + 1); }}
              autoFocus
            />
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="dt-test-nav">
        <button className="dt-nav-btn" onClick={() => setCurrent(c => c - 1)} disabled={current === 0}>
          ← Înapoi
        </button>

        <div className="dt-test-dots">
          {exercises.map((e, i) => {
            const done = e.options
              ? selections[e.id] !== undefined && selections[e.id] !== null
              : Boolean(textAnswers[e.id]);
            return (
              <button
                key={e.id}
                className={`dt-dot${i === current ? ' active' : ''}${done ? ' done' : ''}`}
                onClick={() => setCurrent(i)}
                title={`Ex. ${i + 1}`}
              />
            );
          })}
        </div>

        {current < total - 1 ? (
          <button className="dt-nav-btn primary" onClick={() => setCurrent(c => c + 1)}>
            Următor →
          </button>
        ) : (
          <button className="dt-nav-btn primary" onClick={handleFinish} disabled={submitting}>
            {submitting ? 'Se trimite…' : 'Finalizează →'}
          </button>
        )}
      </div>

      <div className="dt-test-skip-note">
        Poți lăsa întrebări fără răspuns — vor fi marcate automat ca necunoscute.
      </div>
    </div>
  );
}

// ─── Solution Upload ──────────────────────────────────────────────────────────

function SolutionUpload({ testId }: { testId: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [error, setError] = useState('');

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      await uploadDiagnosticSolution(testId, file);
      setUploaded(true);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Eroare la upload.');
    } finally {
      setUploading(false);
    }
  };

  if (uploaded) {
    return (
      <div className="dt-upload-success">
        <CheckCircle size={18} color="#16a34a" />
        Soluția a fost încărcată cu succes!
      </div>
    );
  }

  return (
    <div className="dt-upload-section">
      <div className="dt-upload-title">
        <Upload size={16} /> Încarcă rezolvarea scrisă (opțional)
      </div>
      <p className="dt-upload-desc">
        Poți încărca o poză sau PDF cu rezolvarea completă — aceasta va fi vizibilă profesorului.
      </p>

      <div className="dt-upload-zone" onClick={() => fileRef.current?.click()}>
        {file ? (
          <div className="dt-upload-selected">
            <FileText size={20} />
            <span>{file.name}</span>
          </div>
        ) : (
          <div className="dt-upload-placeholder">
            <Upload size={24} />
            <span>Apasă pentru a selecta fișierul</span>
            <small>PDF, JPG, PNG, WEBP — max 10 MB</small>
          </div>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.webp"
        className="dt-upload-input"
        onChange={handleFile}
      />

      {error && <div className="dt-upload-error">{error}</div>}

      {file && (
        <button className="dt-upload-btn" onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Se încarcă…' : '↑ Trimite soluția'}
        </button>
      )}
    </div>
  );
}

// ─── Phase: Results ───────────────────────────────────────────────────────────

function ResultsPhase({
  result,
  onGeneratePath,
  generating,
}: {
  result: DiagnosticResult;
  onGeneratePath: () => void;
  generating: boolean;
}) {
  const overall = scoreLabel(result.score_pct);
  const sorted = [...result.weak_topics].sort((a, b) => a.score_pct - b.score_pct);
  const weakCount = result.weak_topics.filter(t => t.score_pct < 60).length;

  return (
    <div className="dt-results">
      <div className="dt-results-header">
        <BarChart2 size={28} className="dt-results-icon" />
        <h2 className="dt-results-title">Rezultatele tale</h2>
      </div>

      {/* Score overview */}
      <div className="dt-score-card">
        <div className="dt-score-circle" style={{ '--score-color': overall.color } as React.CSSProperties}>
          <div className="dt-score-pct">{result.score_pct}%</div>
          <div className="dt-score-label">{overall.label}</div>
        </div>
        <div className="dt-score-stats">
          <div className="dt-score-stat">
            <CheckCircle size={16} color="#16a34a" />
            <span>{result.correct_count} corecte din {result.total}</span>
          </div>
          <div className="dt-score-stat">
            <XCircle size={16} color="#dc2626" />
            <span>{result.total - result.correct_count} greșite / nelucrate</span>
          </div>
          {weakCount > 0 && (
            <div className="dt-score-weak-note">
              ⚠️ {weakCount} {weakCount === 1 ? 'topic necesită' : 'topicuri necesită'} atenție
            </div>
          )}
        </div>
      </div>

      {/* Topic breakdown */}
      {sorted.length > 0 && (
        <div className="dt-topics-section">
          <div className="dt-topics-title">Detalii pe topicuri</div>
          {sorted.map(t => <TopicBar key={t.topic_key} topic={t} />)}
        </div>
      )}

      {/* Solution upload */}
      <SolutionUpload testId={result.test_id} />

      {/* Generate plan CTA */}
      <div className="dt-cta-section">
        <div className="dt-cta-title">🧠 Planul tău personalizat generat de AI</div>
        <p className="dt-cta-desc">
          Pe baza lacunelor identificate, Claude generează un plan de studiu săptămânal
          adaptat exact nivelului tău — cu priorități, obiective și sfaturi practice.
        </p>
        <div className="dt-cta-pills">
          <div className="dt-cta-pill free">✓ Primele 3 topicuri + Plan AI — Gratuit</div>
          <div className="dt-cta-pill premium">★ Plan complet + Zilnic + Spaced Repetition — Premium</div>
        </div>
        <button className="dt-generate-btn" onClick={onGeneratePath} disabled={generating}>
          {generating
            ? <><span className="dt-spinner" />Claude generează planul…</>
            : '✦ Generează planul meu cu AI'}
        </button>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

type Phase = 'welcome' | 'test' | 'results' | 'done';

interface DiagnosticTestProps {
  onPathGenerated?: (pathId: string) => void;
}

export default function DiagnosticTest({ onPathGenerated }: DiagnosticTestProps) {
  const [phase, setPhase] = useState<Phase>('welcome');
  const [testId, setTestId] = useState('');
  const [exercises, setExercises] = useState<DiagnosticExercise[]>([]);
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const handleStart = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await startDiagnostic();
      setTestId(res.data.test_id);
      setExercises(res.data.exercises);
      setPhase('test');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Eroare la pornirea testului.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (answers: { exercise_id: string; selected_option?: number; answer?: string }[]) => {
    setSubmitting(true);
    setError('');
    try {
      const res = await submitDiagnostic(testId, answers);
      setResult(res.data);
      setPhase('results');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Eroare la trimiterea răspunsurilor.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGeneratePath = async () => {
    if (!result) return;
    setGenerating(true);
    setError('');
    try {
      const res = await generateLearningPath(result.test_id);
      setPhase('done');
      onPathGenerated?.(res.data.path_id);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Eroare la generarea planului.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="dt-wrap">
      {error && <div className="dt-error">{error}</div>}

      {phase === 'welcome' && <WelcomePhase onStart={handleStart} loading={loading} />}
      {phase === 'test' && (
        <TestPhase exercises={exercises} onSubmit={handleSubmit} submitting={submitting} />
      )}
      {phase === 'results' && result && (
        <ResultsPhase result={result} onGeneratePath={handleGeneratePath} generating={generating} />
      )}
      {phase === 'done' && (
        <div className="dt-done">
          <CheckCircle size={48} color="#16a34a" />
          <h2>Planul tău e gata!</h2>
          <p>Redirecționăm către traseul tău de învățare…</p>
        </div>
      )}
    </div>
  );
}
