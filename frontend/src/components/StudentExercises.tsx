import { useState, useEffect, useRef } from 'react';
import { Eye, EyeOff, Flag, ChevronDown, ChevronUp, BookOpen, Zap, Layers, Trash2, ChevronRight, ChevronLeft, SlidersHorizontal, X, CalendarDays, Play, Pencil } from 'lucide-react';
import {
  getExercises, getBatchChildren, createHelpRequest,
  getMyLimits, logExerciseGeneration, saveExerciseSet, getExerciseSets,
  getExerciseSet, updateExerciseSet, deleteExerciseSet, getExerciseFilterOptions,
  getCompletedExerciseIds, getReviewItems, openReviewItem,
  resolveReviewItem,
  submitExercise, uploadSubmissionPhoto, getMySubmission,
  linkParent, getMyParents, removeParentLink,
  createStudyPlanDay,
  buildApiUrl,
  type Exercise, type GenLimits, type ExerciseSet, type ExerciseSetDetail, type FilterOptions,
  type ParentStudentLink, type SelfEval, type ExerciseSubmission, type SessionType, type ReviewItem,
} from '../api';
import { useAuth } from '../AuthContext';
import LatexRenderer from './LatexRenderer';
import GamificationBar, { XPToast } from './GamificationBar';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './StudentExercises.css';

const PAGE_SIZE = 22;
const WORKSPACE_SAVE_DEBOUNCE_MS = 350;

const MATH_TEMPLATES = [
  { label: 'Fracție', snippet: '\\frac{a}{b}' },
  { label: 'Putere', snippet: 'x^{2}' },
  { label: 'Radical', snippet: '\\sqrt{x}' },
  { label: 'Integrală', snippet: '\\int_a^b f(x)\\,dx' },
  { label: 'Limită', snippet: '\\lim_{x \\to a} f(x)' },
  { label: 'Vector', snippet: '\\overrightarrow{AB}' },
  { label: 'Sistem', snippet: '\\begin{cases} x + y = 1 \\\\ x - y = 3 \\end{cases}' },
];

interface ExerciseWorkspaceDraft {
  notes: string;
  finalAnswer: string;
  updatedAt: string;
}

function getWorkspaceStorageKey(userId: string, exerciseId: string) {
  return `exercise-workspace:${userId}:${exerciseId}`;
}

function readWorkspaceDraft(userId: string | undefined, exerciseId: string): ExerciseWorkspaceDraft | null {
  if (!userId || typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(getWorkspaceStorageKey(userId, exerciseId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ExerciseWorkspaceDraft>;
    return {
      notes: parsed.notes || '',
      finalAnswer: parsed.finalAnswer || '',
      updatedAt: parsed.updatedAt || '',
    };
  } catch {
    return null;
  }
}

function saveWorkspaceDraft(userId: string | undefined, exerciseId: string, draft: ExerciseWorkspaceDraft) {
  if (!userId || typeof window === 'undefined') return;
  window.localStorage.setItem(getWorkspaceStorageKey(userId, exerciseId), JSON.stringify(draft));
}

function clearWorkspaceDraft(userId: string | undefined, exerciseId: string) {
  if (!userId || typeof window === 'undefined') return;
  window.localStorage.removeItem(getWorkspaceStorageKey(userId, exerciseId));
}

const BLOCK_REASONS = [
  {
    key: 'statement',
    label: 'Nu înțeleg cerința',
    tips: [
      'Recitește enunțul și separă datele de ce se cere efectiv.',
      'Deschide rezolvarea doar după ce încerci să reformulezi cerința în cuvintele tale.',
      'Caută în aceeași listă un exercițiu cu structură asemănătoare.',
    ],
  },
  {
    key: 'start',
    label: 'Nu știu de unde să încep',
    tips: [
      'Încearcă să identifici formula, teorema sau metoda care apare cel mai des pe tipul acesta de exercițiu.',
      'Lucrează mai întâi pe un exemplu mai ușor din același subiect.',
      'Scrie primul pas posibil, chiar dacă nu vezi toată rezolvarea.',
    ],
  },
  {
    key: 'calculation',
    label: 'Mă pierd la calcule',
    tips: [
      'Verifică dacă ai simplificat prea devreme sau ai omis o paranteză.',
      'Împarte rezolvarea în pași scurți și validează fiecare transformare.',
      'Compară cu baremul doar punctul unde simți că se rupe logica.',
    ],
  },
  {
    key: 'method',
    label: 'Nu înțeleg metoda',
    tips: [
      'Uită-te dacă exercițiul cere o tehnică pe care ai mai întâlnit-o: substituție, funcții, sisteme, trigonometrie.',
      'Încearcă un exercițiu similar mai ușor înainte de a reveni aici.',
      'Dacă te blochezi repetat, salvează-l în lista de revăzut și escaladează doar după încă o încercare.',
    ],
  },
];

function BlockedModal({ exerciseId, onClose, isPremium }: { exerciseId: string; onClose: () => void; isPremium: boolean }) {
  const [selectedReason, setSelectedReason] = useState(BLOCK_REASONS[0].key);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const reason = BLOCK_REASONS.find((item) => item.key === selectedReason) || BLOCK_REASONS[0];

  const handleSaveForReview = async () => {
    setBusy(true);
    setMessage('');
    try {
      await openReviewItem(exerciseId, 'blocked');
      setMessage('Exercițiul a fost adăugat în lista ta de revizuit.');
    } catch {
      setMessage('Nu am putut salva exercițiul în jurnalul de erori.');
    } finally {
      setBusy(false);
    }
  };

  const handleEscalate = async () => {
    if (!isPremium) return;
    setBusy(true);
    setMessage('');
    try {
      await openReviewItem(exerciseId, 'blocked');
      await createHelpRequest({
        exercise_id: exerciseId,
        flag_type: 'WRITTEN',
        notes: `Blocaj: ${reason.label}${notes.trim() ? `\n\nDetalii elev: ${notes.trim()}` : ''}`,
      });
      setMessage('Cererea a fost trimisă profesorului, iar exercițiul a rămas în lista ta de revizuit.');
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Nu am putut trimite cererea către profesor.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flag-modal-overlay" onClick={onClose}>
      <div className="flag-modal" onClick={(e) => e.stopPropagation()}>
        <div className="flag-modal-header">
          <h3>M-am blocat</h3>
          <button className="flag-modal-close" onClick={onClose}>×</button>
        </div>

        <p className="flag-modal-subtitle">Spune-ne unde te-ai blocat. Mai întâi îl salvăm pentru revizuire, iar dacă încă rămâi blocat poți escalada către profesor.</p>

        <div className="eval-options">
          {BLOCK_REASONS.map((item) => (
            <button
              key={item.key}
              className={`eval-option ${selectedReason === item.key ? 'selected' : ''}`}
              onClick={() => setSelectedReason(item.key)}
            >
              <div className="eval-option-text">
                <div className="eval-option-label">{item.label}</div>
                <div className="eval-option-desc">Alege varianta care descrie cel mai bine blocajul tău.</div>
              </div>
            </button>
          ))}
        </div>

        <div className="review-summary-card" style={{ marginTop: 12 }}>
          <div className="review-summary-text">
            {reason.tips.map((tip) => (
              <div key={tip}>• {tip}</div>
            ))}
          </div>
        </div>

        <div className="flag-notes">
          <label>Ce ai încercat până acum? (opțional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Ex: am încercat metoda cu substituție, dar nu-mi iese pasul 2"
            rows={3}
          />
        </div>

        {message && <div className={`parents-msg ${message.includes('nu') || message.includes('Nu') ? 'err' : 'ok'}`}>{message}</div>}

        <div className="flag-modal-actions">
          <button className="flag-cancel-btn" onClick={onClose}>Închide</button>
          <button className="flag-submit-btn" onClick={handleSaveForReview} disabled={busy}>
            {busy ? 'Se salvează...' : 'Adaugă la revizuit'}
          </button>
          <button className="flag-submit-btn" onClick={handleEscalate} disabled={busy || !isPremium}>
            Escaladează la profesor
          </button>
        </div>
      </div>
    </div>
  );
}

function BlockedButton({ exerciseId, isPremium }: { exerciseId: string; isPremium: boolean }) {
  const [showModal, setShowModal] = useState(false);
  return (
    <>
      <button className="student-btn-flag" onClick={() => setShowModal(true)} title="Salvează blocajul sau cere sprijin">
        <Flag size={15} />
        M-am blocat
      </button>
      {showModal && <BlockedModal exerciseId={exerciseId} onClose={() => setShowModal(false)} isPremium={isPremium} />}
    </>
  );
}

function CorrectionButton({ exerciseId, completedIds, onToggleComplete }: {
  exerciseId: string;
  completedIds: Set<string>;
  onToggleComplete: (id: string, val: boolean, xp: number, badges: string[]) => void;
}) {
  const [showModal, setShowModal] = useState(false);
  const [existing, setExisting] = useState<ExerciseSubmission | null>(null);
  const isCompleted = completedIds.has(exerciseId);

  const handleOpen = async () => {
    try {
      const res = await getMySubmission(exerciseId);
      setExisting(res.data ?? null);
    } catch {
      setExisting(null);
    }
    setShowModal(true);
  };

  const handleDone = (xp: number) => {
    setShowModal(false);
    onToggleComplete(exerciseId, true, xp, []);
  };

  return (
    <>
      <button
        className={`student-btn-correction ${isCompleted ? 'active' : ''}`}
        onClick={handleOpen}
        title="Trimite soluția pentru corectare"
      >
        <Flag size={15} />
        Vreau corectare
      </button>
      {showModal && (
        <EvalModal
          exerciseId={exerciseId}
          existing={existing}
          onDone={handleDone}
          onClose={() => setShowModal(false)}
          initialSelfEval={existing?.self_eval ?? 'partial'}
          preferPhotoFlow
        />
      )}
    </>
  );
}

function buildMatrixLatex(values: string[][]) {
  const rows = values
    .map((row) => row.map((cell) => cell.trim() || '\\square').join(' & '))
    .join(' \\\\ ');
  return `\\begin{bmatrix} ${rows} \\end{bmatrix}`;
}

function buildValueTableLatex(xValues: string[], yValues: string[], yLabel: string) {
  const cols = 'c|' + 'c'.repeat(Math.max(xValues.length, 1));
  const xRow = ['x', ...xValues.map((value) => value.trim() || '\\square')].join(' & ');
  const yRow = [yLabel || 'f(x)', ...yValues.map((value) => value.trim() || '\\square')].join(' & ');
  return `\\begin{array}{${cols}} ${xRow} \\\\ \\hline ${yRow} \\end{array}`;
}

function wrapForPreview(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return '';
  const mathy = /\\|[_^{}]|\\begin|\\frac|\\sqrt|\\int|\\lim|\\sum/.test(trimmed);
  return mathy ? `$$${trimmed}$$` : trimmed;
}

function ExerciseWorkspace({ exerciseId }: { exerciseId: string }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState('');
  const [finalAnswer, setFinalAnswer] = useState('');
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [hydrated, setHydrated] = useState(false);
  const [activeField, setActiveField] = useState<'notes' | 'final'>('notes');
  const [showMatrixBuilder, setShowMatrixBuilder] = useState(false);
  const [showTableBuilder, setShowTableBuilder] = useState(false);
  const [matrixValues, setMatrixValues] = useState([
    ['', ''],
    ['', ''],
  ]);
  const [tableXValues, setTableXValues] = useState(['', '', '']);
  const [tableYValues, setTableYValues] = useState(['', '', '']);
  const [tableYLabel, setTableYLabel] = useState('f(x)');
  const notesRef = useRef<HTMLTextAreaElement | null>(null);
  const finalRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const draft = readWorkspaceDraft(user?.id, exerciseId);
    if (draft) {
      setNotes(draft.notes);
      setFinalAnswer(draft.finalAnswer);
    } else {
      setNotes('');
      setFinalAnswer('');
    }
    setHydrated(true);
  }, [exerciseId, user?.id]);

  useEffect(() => {
    if (!hydrated) return;
    const hasContent = notes.trim() || finalAnswer.trim();
    if (!hasContent) {
      clearWorkspaceDraft(user?.id, exerciseId);
      setSaveState('idle');
      return;
    }
    setSaveState('saving');
    const timer = window.setTimeout(() => {
      saveWorkspaceDraft(user?.id, exerciseId, {
        notes,
        finalAnswer,
        updatedAt: new Date().toISOString(),
      });
      setSaveState('saved');
    }, WORKSPACE_SAVE_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [exerciseId, finalAnswer, hydrated, notes, user?.id]);

  const hasDraft = notes.trim().length > 0 || finalAnswer.trim().length > 0;

  const handleReset = () => {
    setNotes('');
    setFinalAnswer('');
    clearWorkspaceDraft(user?.id, exerciseId);
    setSaveState('idle');
  };

  const insertIntoActiveField = (snippet: string) => {
    const targetRef = activeField === 'notes' ? notesRef.current : finalRef.current;
    const currentValue = activeField === 'notes' ? notes : finalAnswer;
    const start = targetRef?.selectionStart ?? currentValue.length;
    const end = targetRef?.selectionEnd ?? currentValue.length;
    const nextValue = `${currentValue.slice(0, start)}${snippet}${currentValue.slice(end)}`;
    if (activeField === 'notes') {
      setNotes(nextValue);
    } else {
      setFinalAnswer(nextValue);
    }
    window.setTimeout(() => {
      targetRef?.focus();
      const pos = start + snippet.length;
      targetRef?.setSelectionRange(pos, pos);
    }, 0);
  };

  const resizeMatrix = (size: number) => {
    setMatrixValues(Array.from({ length: size }, (_, rowIdx) =>
      Array.from({ length: size }, (_, colIdx) => matrixValues[rowIdx]?.[colIdx] || '')
    ));
  };

  const insertMatrix = () => {
    insertIntoActiveField(buildMatrixLatex(matrixValues));
    setShowMatrixBuilder(false);
  };

  const insertValueTable = () => {
    insertIntoActiveField(buildValueTableLatex(tableXValues, tableYValues, tableYLabel));
    setShowTableBuilder(false);
  };

  return (
    <div className={`exercise-workspace ${open ? 'open' : ''}`}>
      <div className="exercise-workspace-header">
        <button
          className={`exercise-workspace-toggle ${hasDraft ? 'has-draft' : ''}`}
          onClick={() => setOpen((value) => !value)}
        >
          <Pencil size={15} />
          {open ? 'Ascunde schița' : hasDraft ? 'Continuă schița' : 'Rezolv aici'}
        </button>
        {hasDraft && (
          <span className="exercise-workspace-status">
            {saveState === 'saving' ? 'Se salvează...' : 'Salvat automat'}
          </span>
        )}
      </div>

      {open && (
        <div className="exercise-workspace-panel">
          <div className="exercise-workspace-hint">
            Lucrează direct aici, fără să ieși din exercițiu. Ciorna rămâne salvată automat pe dispozitivul tău.
          </div>

          <div className="exercise-workspace-toolbar">
            <div className="exercise-workspace-targets">
              <button
                className={`exercise-workspace-target ${activeField === 'notes' ? 'active' : ''}`}
                onClick={() => setActiveField('notes')}
              >
                Inserează în ciornă
              </button>
              <button
                className={`exercise-workspace-target ${activeField === 'final' ? 'active' : ''}`}
                onClick={() => setActiveField('final')}
              >
                Inserează în răspuns
              </button>
            </div>

            <div className="exercise-workspace-template-list">
              {MATH_TEMPLATES.map((template) => (
                <button
                  key={template.label}
                  className="exercise-workspace-chip"
                  onClick={() => insertIntoActiveField(template.snippet)}
                >
                  {template.label}
                </button>
              ))}
              <button className="exercise-workspace-chip special" onClick={() => setShowMatrixBuilder((value) => !value)}>
                Matrice
              </button>
              <button className="exercise-workspace-chip special" onClick={() => setShowTableBuilder((value) => !value)}>
                Tabel valori
              </button>
            </div>
          </div>

          {showMatrixBuilder && (
            <div className="exercise-builder-card">
              <div className="exercise-builder-header">
                <strong>Builder matrice</strong>
                <div className="exercise-builder-size">
                  <button onClick={() => resizeMatrix(2)}>2x2</button>
                  <button onClick={() => resizeMatrix(3)}>3x3</button>
                </div>
              </div>
              <div className="exercise-matrix-grid" style={{ gridTemplateColumns: `repeat(${matrixValues[0]?.length || 2}, minmax(0, 1fr))` }}>
                {matrixValues.flatMap((row, rowIdx) =>
                  row.map((cell, colIdx) => (
                    <input
                      key={`${rowIdx}-${colIdx}`}
                      value={cell}
                      onChange={(e) => {
                        const next = matrixValues.map((matrixRow) => [...matrixRow]);
                        next[rowIdx][colIdx] = e.target.value;
                        setMatrixValues(next);
                      }}
                      placeholder="0"
                    />
                  ))
                )}
              </div>
              <div className="exercise-builder-actions">
                <button onClick={() => setShowMatrixBuilder(false)}>Închide</button>
                <button className="primary" onClick={insertMatrix}>Inserează matricea</button>
              </div>
            </div>
          )}

          {showTableBuilder && (
            <div className="exercise-builder-card">
              <div className="exercise-builder-header">
                <strong>Builder tabel de valori</strong>
              </div>
              <div className="exercise-value-table">
                <div className="exercise-value-row">
                  <span>x</span>
                  {tableXValues.map((value, idx) => (
                    <input
                      key={`x-${idx}`}
                      value={value}
                      onChange={(e) => {
                        const next = [...tableXValues];
                        next[idx] = e.target.value;
                        setTableXValues(next);
                      }}
                      placeholder={`x${idx + 1}`}
                    />
                  ))}
                </div>
                <div className="exercise-value-row">
                  <input
                    className="exercise-value-label"
                    value={tableYLabel}
                    onChange={(e) => setTableYLabel(e.target.value)}
                    placeholder="f(x)"
                  />
                  {tableYValues.map((value, idx) => (
                    <input
                      key={`y-${idx}`}
                      value={value}
                      onChange={(e) => {
                        const next = [...tableYValues];
                        next[idx] = e.target.value;
                        setTableYValues(next);
                      }}
                      placeholder={`y${idx + 1}`}
                    />
                  ))}
                </div>
              </div>
              <div className="exercise-builder-actions">
                <button onClick={() => setShowTableBuilder(false)}>Închide</button>
                <button className="primary" onClick={insertValueTable}>Inserează tabelul</button>
              </div>
            </div>
          )}

          <div className="exercise-workspace-field">
            <label>Ciornă / pași de rezolvare</label>
            <textarea
              ref={notesRef}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onFocus={() => setActiveField('notes')}
              placeholder="Scrie ideea, calculele și pașii tăi aici..."
              rows={8}
            />
          </div>

          <div className="exercise-workspace-field">
            <label>Răspuns final</label>
            <textarea
              ref={finalRef}
              value={finalAnswer}
              onChange={(e) => setFinalAnswer(e.target.value)}
              onFocus={() => setActiveField('final')}
              placeholder="Ex: x = 2 sau P(AB) = 1/3"
              rows={2}
            />
          </div>

          {finalAnswer.trim() && (
            <div className="exercise-workspace-preview">
              <div className="exercise-workspace-preview-label">Preview</div>
              <LatexRenderer text={wrapForPreview(finalAnswer)} />
            </div>
          )}

          <div className="exercise-workspace-actions">
            <button className="exercise-workspace-clear" onClick={handleReset}>
              Șterge schița
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SolutionBlock({ exercise }: { exercise: Exercise }) {
  const has = !!(exercise.solution_latex || exercise.answer_latex || exercise.scoring_guide_latex);
  if (!has) return <p className="no-solution">Soluția nu este disponibilă pentru acest exercițiu.</p>;

  return (
    <div className="student-ex-solution">
      {exercise.answer_latex && (
        <div className="solution-section">
          <div className="solution-label">Răspuns</div>
          <LatexRenderer text={exercise.answer_latex} />
        </div>
      )}
      {exercise.solution_latex && (
        <div className="solution-section">
          <div className="solution-label">Rezolvare detaliată</div>
          <LatexRenderer text={exercise.solution_latex} />
        </div>
      )}
      {exercise.scoring_guide_latex && (
        <div className="solution-section solution-barem">
          <div className="solution-label">Barem de corectare</div>
          <LatexRenderer text={exercise.scoring_guide_latex} />
        </div>
      )}
    </div>
  );
}

const SELF_EVAL_OPTIONS: { value: SelfEval; label: string; icon: string; desc: string; color: string }[] = [
  { value: 'failed',   label: 'Nu am reușit',       icon: '❌', desc: '0% XP — exercițiul merge în lista de revăzut', color: '#ef4444' },
  { value: 'partial',  label: 'Parțial rezolvat',   icon: '⚠️', desc: '10% XP — ai rezolvat o parte', color: '#f59e0b' },
  { value: 'complete', label: 'Rezolvat complet',   icon: '✅', desc: '10% XP + poți încărca foto pentru +40% XP', color: '#22c55e' },
];

function EvalModal({ exerciseId, existing, onDone, onClose, initialSelfEval = 'complete', preferPhotoFlow = false }: {
  exerciseId: string;
  existing: ExerciseSubmission | null;
  onDone: (xp: number) => void;
  onClose: () => void;
  initialSelfEval?: SelfEval;
  preferPhotoFlow?: boolean;
}) {
  const [step, setStep] = useState<'eval' | 'photo'>(existing ? 'photo' : 'eval');
  const [selfEval, setSelfEval] = useState<SelfEval>(existing?.self_eval ?? initialSelfEval);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [totalXp, setTotalXp] = useState(0);

  useEffect(() => {
    setStep(existing ? 'photo' : 'eval');
    setSelfEval(existing?.self_eval ?? initialSelfEval);
  }, [existing, initialSelfEval, preferPhotoFlow, exerciseId]);

  const handlePreparePhotoFlow = async () => {
    setBusy(true);
    setMsg('');
    try {
      if (existing) {
        setTotalXp(existing.xp_self_eval ?? 0);
        setStep('photo');
        return;
      }
      const res = await submitExercise(exerciseId, selfEval);
      setTotalXp(res.data.xp_self_eval);
      setStep('photo');
    } catch {
      setMsg('Nu am putut pregăti exercițiul pentru corectare. Încearcă din nou.');
    } finally {
      setBusy(false);
    }
  };

  const handleEvalSubmit = async () => {
    setBusy(true);
    try {
      const res = await submitExercise(exerciseId, selfEval);
      const xp = res.data.xp_self_eval;
      setTotalXp(xp);
      if (selfEval === 'failed') { onDone(xp); return; }
      setStep('photo');
    } catch { setMsg('Eroare. Încearcă din nou.'); }
    finally { setBusy(false); }
  };

  const handlePhotoUpload = async () => {
    if (!photoFile) { onDone(totalXp); return; }
    setBusy(true);
    try {
      const res = await uploadSubmissionPhoto(exerciseId, photoFile);
      onDone(totalXp + (res.data.xp_awarded ?? 0));
    } catch { setMsg('Eroare la upload. Încearcă din nou.'); }
    finally { setBusy(false); }
  };

  return (
    <div className="eval-modal-overlay" onClick={onClose}>
      <div className="eval-modal" onClick={e => e.stopPropagation()}>
        <div className="eval-modal-header">
          <span>
            {step === 'eval'
              ? (preferPhotoFlow ? 'Pregătește soluția pentru corectare' : 'Cum te-ai descurcat?')
              : 'Adaugă fotografia soluției'}
          </span>
          <button className="eval-modal-close" onClick={onClose}>×</button>
        </div>

        {step === 'eval' && (
          <div className="eval-modal-body">
            {preferPhotoFlow && (
              <div className="eval-photo-hint">
                Profesorul corectează doar soluțiile încărcate, nu fiecare blocaj punctual. Alege mai jos cât ai reușit și apoi încarcă fotografia sau PDF-ul rezolvării tale.
              </div>
            )}
            <div className="eval-options">
              {SELF_EVAL_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  className={`eval-option ${selfEval === opt.value ? 'selected' : ''}`}
                  style={selfEval === opt.value ? { borderColor: opt.color } : {}}
                  onClick={() => setSelfEval(opt.value)}
                >
                  <span className="eval-option-icon">{opt.icon}</span>
                  <div className="eval-option-text">
                    <div className="eval-option-label">{opt.label}</div>
                    <div className="eval-option-desc">{opt.desc}</div>
                  </div>
                </button>
              ))}
            </div>
            {msg && <div className="eval-msg">{msg}</div>}
            <button
              className="eval-submit-btn"
              onClick={preferPhotoFlow ? handlePreparePhotoFlow : handleEvalSubmit}
              disabled={busy}
            >
              {busy ? 'Se pregătește...' : preferPhotoFlow ? 'Continuă către upload' : 'Confirmă →'}
            </button>
          </div>
        )}

        {step === 'photo' && (
          <div className="eval-modal-body">
            {existing?.teacher_status && (
              <div className={`eval-review-result eval-review-${existing.teacher_status}`}>
                {existing.teacher_status === 'correct' && '✅ Profesorul a marcat soluția ca CORECTĂ'}
                {existing.teacher_status === 'incorrect' && '❌ Profesorul a marcat soluția ca INCORECTĂ'}
                {existing.teacher_status === 'pending' && '⏳ Soluția ta este în așteptare pentru corecție'}
                {existing.teacher_note && <div className="eval-review-note">Notă: {existing.teacher_note}</div>}
                {existing.teacher_file_path && (
                  <a
                    className="eval-teacher-file-btn"
                    href={buildApiUrl(existing.teacher_file_path)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    📎 Vezi fișierul profesorului
                  </a>
                )}
              </div>
            )}
            <p className="eval-photo-hint">
              Încarcă o fotografie sau PDF cu rezolvarea pentru <strong>+40% XP</strong> suplimentar.
              După upload, soluția intră în coada de corectare a profesorilor și poate primi încă <strong>+50% XP</strong> dacă este corectă.
            </p>
            {existing?.photo_path && (
              <div className="eval-photo-existing">📷 Ai deja un fișier încărcat</div>
            )}
            <input
              type="file"
              accept="image/*,.pdf"
              className="eval-photo-input"
              onChange={e => setPhotoFile(e.target.files?.[0] ?? null)}
            />
            {photoFile && <div className="eval-photo-name">📎 {photoFile.name}</div>}
            {msg && <div className="eval-msg">{msg}</div>}
            <div className="eval-photo-actions">
              <button className="eval-skip-btn" onClick={() => onDone(totalXp)} disabled={busy}>
                Finalizează fără fișier
              </button>
              <button className="eval-submit-btn" onClick={handlePhotoUpload} disabled={busy || !photoFile}>
                {busy ? 'Se încarcă...' : '📤 Încarcă și finalizează'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CompleteButton({ exerciseId, completedIds, onToggleComplete }: {
  exerciseId: string;
  completedIds: Set<string>;
  onToggleComplete: (id: string, val: boolean, xp: number, badges: string[]) => void;
}) {
  const [showModal, setShowModal] = useState(false);
  const [existing, setExisting] = useState<ExerciseSubmission | null>(null);
  const isCompleted = completedIds.has(exerciseId);

  const handleOpen = async () => {
    try {
      const res = await getMySubmission(exerciseId);
      setExisting(res.data ?? null);
    } catch { setExisting(null); }
    setShowModal(true);
  };

  const handleDone = (xp: number) => {
    setShowModal(false);
    onToggleComplete(exerciseId, true, xp, []);
  };

  return (
    <>
      <button
        className={`student-btn-complete ${isCompleted ? 'completed' : ''}`}
        onClick={handleOpen}
        title={isCompleted ? 'Actualizează autoevaluarea' : 'Deschide autoevaluarea'}
      >
        {isCompleted ? '✓ Autoevaluat' : '○ Autoevaluează'}
      </button>
      {showModal && (
        <EvalModal
          exerciseId={exerciseId}
          existing={existing}
          onDone={handleDone}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}

function SimpleExerciseCard({ exercise, index, isPremium, completedIds, onToggleComplete }: { exercise: Exercise; index: number; isPremium: boolean; completedIds: Set<string>; onToggleComplete: (id: string, val: boolean, xp: number, badges: string[]) => void }) {
  const [showSolution, setShowSolution] = useState(false);
  const path = exercise.metadata?.path;
  const hasSolution = !!(exercise.solution_latex || exercise.answer_latex);

  return (
    <div className={`student-exercise-card ${completedIds.has(exercise.id) ? 'card-completed' : ''}`}>
      <div className="student-ex-header">
        <div className="student-ex-meta">
          <span className="student-ex-index">{index}</span>
          {path && <span className="student-ex-path">{path}</span>}
          {exercise.difficulty != null && (
            <span className="student-ex-diff" title={`Dificultate ${exercise.difficulty}/10`}>
              {'★'.repeat(Math.ceil(exercise.difficulty / 2))}{'☆'.repeat(5 - Math.ceil(exercise.difficulty / 2))}
            </span>
          )}
          {exercise.points != null && <span className="student-ex-points">{exercise.points} pct</span>}
        </div>
        <div className="student-ex-actions">
          <CompleteButton exerciseId={exercise.id} completedIds={completedIds} onToggleComplete={onToggleComplete} />
          <BlockedButton exerciseId={exercise.id} isPremium={isPremium} />
          <CorrectionButton exerciseId={exercise.id} completedIds={completedIds} onToggleComplete={onToggleComplete} />
          {hasSolution && (
            <button
              className={`student-btn-solution ${showSolution ? 'active' : ''}`}
              onClick={() => setShowSolution((v) => !v)}
            >
              {showSolution ? <EyeOff size={15} /> : <Eye size={15} />}
              {showSolution ? 'Ascunde' : 'Rezolvare'}
            </button>
          )}
        </div>
      </div>

      <div className="student-ex-statement">
        <LatexRenderer text={exercise.statement_latex || exercise.statement_text || ''} />
      </div>

      <ExerciseWorkspace exerciseId={exercise.id} />

      {showSolution && <SolutionBlock exercise={exercise} />}
    </div>
  );
}

interface GroupedCardProps {
  parent: Exercise;
  children: Exercise[];
  index: number;
  isPremium: boolean;
  completedIds: Set<string>;
  onToggleComplete: (id: string, val: boolean, xp: number, badges: string[]) => void;
}

function GroupedExerciseCard({ parent, children, index, isPremium, completedIds, onToggleComplete }: GroupedCardProps) {
  const [showSolutions, setShowSolutions] = useState<Record<string, boolean>>({});
  const path = parent.metadata?.path;

  const toggleSolution = (id: string) =>
    setShowSolutions((prev) => ({ ...prev, [id]: !prev[id] }));

  const sorted = [...children].sort((a, b) =>
    (a.metadata?.subpoint || '').localeCompare(b.metadata?.subpoint || '')
  );

  return (
    <div className="student-exercise-card grouped-card">
      <div className="student-ex-header grouped-header">
        <div className="student-ex-meta">
          <span className="student-ex-index">{index}</span>
          {path && <span className="student-ex-path">{path}</span>}
          {parent.points != null && <span className="student-ex-points">{parent.points} pct total</span>}
        </div>
        <span className="grouped-badge">Problemă cu subpuncte</span>
      </div>

      {parent.statement_latex && (
        <div className="student-ex-statement grouped-parent-statement">
          <LatexRenderer text={parent.statement_latex} />
        </div>
      )}

      <div className="subpoints-list">
        {sorted.map((child) => {
          const subpoint = child.metadata?.subpoint || '';
          const hasSolution = !!(child.solution_latex || child.answer_latex);
          const isOpen = !!showSolutions[child.id];

          return (
            <div key={child.id} className="subpoint-item">
              <div className="subpoint-header">
                <div className="subpoint-left">
                  <span className="subpoint-letter">{subpoint})</span>
                  <div className="subpoint-statement">
                    <LatexRenderer text={child.statement_latex || child.statement_text || ''} />
                  </div>
                </div>
                <div className="subpoint-actions">
                  {child.points != null && (
                    <span className="student-ex-points">{child.points} pct</span>
                  )}
                  <CompleteButton exerciseId={child.id} completedIds={completedIds} onToggleComplete={onToggleComplete} />
                  <BlockedButton exerciseId={child.id} isPremium={isPremium} />
                  <CorrectionButton exerciseId={child.id} completedIds={completedIds} onToggleComplete={onToggleComplete} />
                  {hasSolution && (
                    <button
                      className={`student-btn-solution ${isOpen ? 'active' : ''}`}
                      onClick={() => toggleSolution(child.id)}
                    >
                      {isOpen ? <EyeOff size={14} /> : <Eye size={14} />}
                      {isOpen ? 'Ascunde' : 'Rezolvare'}
                    </button>
                  )}
                </div>
              </div>

              <ExerciseWorkspace exerciseId={child.id} />

              {isOpen && <SolutionBlock exercise={child} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface ExerciseGroup {
  type: 'simple' | 'grouped';
  exercise: Exercise;
  children?: Exercise[];
}

const SUBIECT_OPTIONS = [
  { value: 'all', label: 'Toate subiectele' },
  { value: '1', label: 'Subiectul I' },
  { value: '2', label: 'Subiectul II' },
  { value: '3', label: 'Subiectul III' },
];

const PROFILE_LABELS: Record<string, string> = {
  'mate-info': 'Mate-Info',
  'st-nat': 'Științe ale naturii',
  'tehnologic': 'Tehnologic',
  'pedagogic': 'Pedagogic',
};

const DIFFICULTY_LABELS: Record<number, string> = {
  1: 'Foarte ușor', 2: 'Ușor', 3: 'Mediu-ușor', 4: 'Mediu', 5: 'Mediu',
  6: 'Mediu-greu', 7: 'Greu', 8: 'Greu', 9: 'Foarte greu', 10: 'Expert',
};

function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return null;

  const pages: (number | '...')[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  return (
    <div className="pagination">
      <button
        className="pagination-btn"
        disabled={page === 1}
        onClick={() => { onChange(page - 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
      >
        <ChevronLeft size={16} /> Înapoi
      </button>

      <div className="pagination-pages">
        {pages.map((p, i) =>
          p === '...' ? (
            <span key={`dots-${i}`} className="pagination-dots">…</span>
          ) : (
            <button
              key={p}
              className={`pagination-page ${p === page ? 'active' : ''}`}
              onClick={() => { onChange(p as number); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
            >
              {p}
            </button>
          )
        )}
      </div>

      <button
        className="pagination-btn"
        disabled={page === totalPages}
        onClick={() => { onChange(page + 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
      >
        Înainte <ChevronRight size={16} />
      </button>
    </div>
  );
}

// --- Saved Sets Components ---

function toInputDate(date: Date) {
  const cloned = new Date(date);
  cloned.setMinutes(cloned.getMinutes() - cloned.getTimezoneOffset());
  return cloned.toISOString().slice(0, 10);
}

function buildStudySessionUrl(sessionType: SessionType, filters?: Record<string, any> | null, exerciseSetId?: string | null) {
  const params = new URLSearchParams({ type: sessionType });
  if (filters?.subiect_tag) {
    params.set('subiect', String(filters.subiect_tag));
  }
  if (exerciseSetId) {
    params.set('set', exerciseSetId);
  }
  return `/app/study-session?${params.toString()}`;
}

function ScheduleSetModal({
  set,
  onClose,
  onScheduled,
}: {
  set: ExerciseSet;
  onClose: () => void;
  onScheduled: () => void;
}) {
  const [planDate, setPlanDate] = useState(toInputDate(new Date()));
  const [sessionType, setSessionType] = useState<SessionType>('test_scurt');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const res = await createStudyPlanDay({
        plan_date: planDate,
        session_type: sessionType,
        filters: {
          ...(set.filters || {}),
          exercise_set_id: set.id,
        },
        note: `Pornit din setul: ${set.name}`,
      });
      await updateExerciseSet(set.id, { linked_plan: res.data.id });
      onScheduled();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Nu am putut planifica sesiunea.');
      setSaving(false);
    }
  };

  return (
    <div className="flag-modal-overlay" onClick={onClose}>
      <div className="flag-modal" onClick={(e) => e.stopPropagation()}>
        <div className="flag-modal-header">
          <h3>Planifică sesiune din set</h3>
          <button className="flag-modal-close" onClick={onClose}>×</button>
        </div>

        <p className="flag-modal-subtitle">
          Vom folosi filtrele salvate în setul <strong>{set.name}</strong>.
        </p>

        <div className="flag-notes">
          <label>Data</label>
          <input type="date" value={planDate} min={toInputDate(new Date())} onChange={(e) => setPlanDate(e.target.value)} />
        </div>

        <div className="flag-notes">
          <label>Tip sesiune</label>
          <select value={sessionType} onChange={(e) => setSessionType(e.target.value as SessionType)}>
            <option value="test_scurt">Test Scurt</option>
            <option value="test_bac">Test BAC</option>
          </select>
        </div>

        {error && <div className="flag-error">{error}</div>}

        <div className="flag-modal-actions">
          <button className="flag-cancel-btn" onClick={onClose}>Anulează</button>
          <button className="flag-submit-btn" disabled={saving || !planDate} onClick={handleSave}>
            {saving ? 'Se salvează...' : 'Adaugă în plan'}
          </button>
        </div>
      </div>
    </div>
  );
}

function RenameSetModal({
  set,
  onClose,
  onRenamed,
}: {
  set: ExerciseSet;
  onClose: () => void;
  onRenamed: (updated: ExerciseSet) => void;
}) {
  const [name, setName] = useState(set.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const res = await updateExerciseSet(set.id, { name: name.trim() || set.name });
      onRenamed(res.data);
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Nu am putut redenumi setul.');
      setSaving(false);
    }
  };

  return (
    <div className="flag-modal-overlay" onClick={onClose}>
      <div className="flag-modal" onClick={(e) => e.stopPropagation()}>
        <div className="flag-modal-header">
          <h3>Redenumește setul</h3>
          <button className="flag-modal-close" onClick={onClose}>×</button>
        </div>

        <div className="flag-notes">
          <label>Nume set</label>
          <input type="text" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        </div>

        {error && <div className="flag-error">{error}</div>}

        <div className="flag-modal-actions">
          <button className="flag-cancel-btn" onClick={onClose}>Anulează</button>
          <button className="flag-submit-btn" disabled={saving || !name.trim()} onClick={handleSave}>
            {saving ? 'Se salvează...' : 'Salvează'}
          </button>
        </div>
      </div>
    </div>
  );
}

function SetCard({ set, onOpen, onDelete, onPlan, onPractice, onRename }: {
  set: ExerciseSet;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onPlan: (set: ExerciseSet) => void;
  onPractice: (set: ExerciseSet, sessionType: SessionType) => void;
  onRename: (set: ExerciseSet) => void;
}) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Ștergi acest set de exerciții?')) return;
    setDeleting(true);
    try {
      await deleteExerciseSet(set.id);
      onDelete(set.id);
    } catch {
      setDeleting(false);
    }
  };

  const date = new Date(set.created_at).toLocaleDateString('ro-RO', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  const filterSummary = set.filters
    ? Object.entries(set.filters)
        .filter(([, v]) => v && v !== 'all')
        .map(([k, v]) => `${k}: ${v}`)
        .join(' · ')
    : null;

  return (
    <div className="saved-set-card" onClick={() => onOpen(set.id)}>
      <div className="saved-set-info">
        <div className="saved-set-name">{set.name}</div>
        <div className="saved-set-meta">
          <span>{set.exercise_count} exerciții</span>
          {set.linked_plan && <span className="saved-set-filters">Planificat</span>}
          {filterSummary && <span className="saved-set-filters">{filterSummary}</span>}
          <span className="saved-set-date">{date}</span>
        </div>
      </div>
      <div className="saved-set-actions">
        <button
          className="saved-set-delete"
          onClick={(e) => { e.stopPropagation(); onPractice(set, 'test_scurt'); }}
          title="Pornește Test Scurt din aceste filtre"
        >
          <Play size={15} />
        </button>
        <button
          className="saved-set-delete"
          onClick={(e) => { e.stopPropagation(); onPractice(set, 'test_bac'); }}
          title="Pornește Test BAC din aceste filtre"
        >
          BAC
        </button>
        <button
          className="saved-set-delete"
          onClick={(e) => { e.stopPropagation(); onPlan(set); }}
          title="Adaugă în planul de studiu"
        >
          <CalendarDays size={15} />
        </button>
        <button
          className="saved-set-delete"
          onClick={(e) => { e.stopPropagation(); onRename(set); }}
          title="Redenumește setul"
        >
          <Pencil size={15} />
        </button>
        <ChevronRight size={18} className="saved-set-arrow" />
        <button
          className="saved-set-delete"
          onClick={handleDelete}
          disabled={deleting}
          title="Șterge setul"
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );
}

function SavedSetsTab({ canHelpRequests, completedIds, onToggleComplete }: {
  canHelpRequests: boolean;
  completedIds: Set<string>;
  onToggleComplete: (id: string, val: boolean, xp: number, badges: string[]) => void;
}) {
  const navigate = useNavigate();
  const [sets, setSets] = useState<ExerciseSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [openSet, setOpenSet] = useState<ExerciseSetDetail | null>(null);
  const [loadingSet, setLoadingSet] = useState(false);
  const [planningSet, setPlanningSet] = useState<ExerciseSet | null>(null);
  const [renamingSet, setRenamingSet] = useState<ExerciseSet | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    getExerciseSets()
      .then((res) => setSets(Array.isArray(res.data) ? res.data : []))
      .catch(() => setSets([]))
      .finally(() => setLoading(false));
  }, []);

  const handleOpen = async (id: string) => {
    if (openSet?.id === id) { setOpenSet(null); return; }
    setLoadingSet(true);
    try {
      const res = await getExerciseSet(id);
      setOpenSet(res.data);
    } catch {
      setOpenSet(null);
    } finally {
      setLoadingSet(false);
    }
  };

  const handleDelete = (id: string) => {
    setSets((prev) => prev.filter((s) => s.id !== id));
    if (openSet?.id === id) setOpenSet(null);
  };

  const updateLocalSet = (updated: ExerciseSet) => {
    setSets((prev) => prev.map((set) => (set.id === updated.id ? { ...set, ...updated } : set)));
    setOpenSet((prev) => (prev && prev.id === updated.id ? { ...prev, name: updated.name, linked_plan: updated.linked_plan } : prev));
  };

  const handlePractice = (set: ExerciseSet, sessionType: SessionType) => {
    navigate(buildStudySessionUrl(sessionType, set.filters, set.id));
  };

  const handlePlanSuccess = async () => {
    const refreshed = await getExerciseSets().catch(() => null);
    if (refreshed?.data) {
      setSets(Array.isArray(refreshed.data) ? refreshed.data : []);
    }
    setSuccessMessage('Sesiunea a fost adăugată în planul de studiu.');
    window.setTimeout(() => setSuccessMessage(null), 3000);
  };

  if (loading) return <div className="student-empty">Se încarcă seturile...</div>;
  if (sets.length === 0) return (
    <div className="student-empty">
      Nu ai seturi salvate. Generează un set de exerciții și acesta va fi salvat automat.
    </div>
  );

  return (
    <div className="saved-sets-container">
      {successMessage && <div className="saved-set-notice">{successMessage}</div>}

      <div className="saved-sets-list">
        {sets.map((s) => (
          <SetCard
            key={s.id}
            set={s}
            onOpen={handleOpen}
            onDelete={handleDelete}
            onPlan={setPlanningSet}
            onPractice={handlePractice}
            onRename={setRenamingSet}
          />
        ))}
      </div>

      {loadingSet && <div className="student-empty">Se încarcă exercițiile...</div>}

      {openSet && !loadingSet && (
        <div className="saved-set-exercises">
          <div className="saved-set-exercises-header">
            <h3>{openSet.name}</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {openSet.linked_plan && (
                <span className="saved-set-filters">Deja planificat</span>
              )}
              <button className="saved-set-close" onClick={() => navigate(buildStudySessionUrl('test_scurt', openSet.filters, openSet.id))}>
                <Play size={14} /> Test Scurt
              </button>
              <button className="saved-set-close" onClick={() => navigate(buildStudySessionUrl('test_bac', openSet.filters, openSet.id))}>
                BAC
              </button>
              <button className="saved-set-close" onClick={() => setOpenSet(null)}>Închide ×</button>
            </div>
          </div>
          <div className="student-exercises-list">
            {openSet.exercises.map((ex, i) => (
              ex.metadata?.is_container ? null :
              <SimpleExerciseCard key={ex.id} exercise={ex} index={i + 1} isPremium={canHelpRequests} completedIds={completedIds} onToggleComplete={onToggleComplete} />
            ))}
          </div>
        </div>
      )}

      {planningSet && (
        <ScheduleSetModal
          set={planningSet}
          onClose={() => setPlanningSet(null)}
          onScheduled={() => {
            void handlePlanSuccess();
          }}
        />
      )}

      {renamingSet && (
        <RenameSetModal
          set={renamingSet}
          onClose={() => setRenamingSet(null)}
          onRenamed={updateLocalSet}
        />
      )}
    </div>
  );
}

// --- Parents Tab ---

function ParentsTab() {
  const [parents, setParents] = useState<ParentStudentLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const load = () => {
    setLoading(true);
    getMyParents()
      .then(r => setParents(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!email.trim()) return;
    setAdding(true);
    setMsg(null);
    try {
      await linkParent({ parent_email: email.trim(), parent_name: name.trim() || undefined });
      setMsg({ text: 'Părintele a fost adăugat. Va primi un email de invitație.', ok: true });
      setEmail(''); setName('');
      load();
    } catch (e: any) {
      setMsg({ text: e?.response?.data?.detail || 'Eroare la adăugare.', ok: false });
    } finally { setAdding(false); }
  };

  const handleRemove = async (parentId: string) => {
    try {
      await removeParentLink(parentId);
      setParents(p => p.filter(x => x.parent_id !== parentId));
    } catch { /* ignore */ }
  };

  return (
    <div className="parents-tab">
      <div className="parents-section-title">Adaugă un părinte</div>
      <p className="parents-hint">
        Introdu emailul părintelui. Dacă nu are cont, îi vom crea unul automat și îi vom trimite un email cu datele de acces.
      </p>
      <div className="parents-add-form">
        <input
          className="parents-input"
          type="email"
          placeholder="Email părinte *"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />
        <input
          className="parents-input"
          type="text"
          placeholder="Nume (opțional, dacă e cont nou)"
          value={name}
          onChange={e => setName(e.target.value)}
        />
        <button className="parents-add-btn" onClick={handleAdd} disabled={adding || !email.trim()}>
          {adding ? 'Se adaugă...' : '+ Adaugă'}
        </button>
      </div>
      {msg && <div className={`parents-msg ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</div>}

      <div className="parents-section-title" style={{ marginTop: 24 }}>Părinți conectați</div>
      {loading && <div className="parents-hint">Se încarcă...</div>}
      {!loading && parents.length === 0 && (
        <div className="parents-hint">Nu ai adăugat niciun părinte încă.</div>
      )}
      <div className="parents-list">
        {parents.map(p => (
          <div key={p.id} className="parents-item">
            <div className="parents-item-avatar">{p.parent_name[0].toUpperCase()}</div>
            <div className="parents-item-info">
              <div className="parents-item-name">{p.parent_name}</div>
              <div className="parents-item-email">{p.parent_email}</div>
            </div>
            <button className="parents-remove-btn" onClick={() => handleRemove(p.parent_id)} title="Elimină legătura">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReviewTab({ canHelpRequests, completedIds, onToggleComplete }: {
  canHelpRequests: boolean;
  completedIds: Set<string>;
  onToggleComplete: (id: string, val: boolean, xp: number, badges: string[]) => void;
}) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadItems = () => {
    setLoading(true);
    getReviewItems()
      .then((res) => setItems(Array.isArray(res.data) ? res.data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadItems();
  }, []);

  const handleResolved = async (exerciseId: string) => {
    setBusyId(exerciseId);
    try {
      await resolveReviewItem(exerciseId);
      setItems((prev) => prev.filter((item) => item.id !== exerciseId));
    } finally {
      setBusyId(null);
    }
  };

  const reasonLabel = (reason: ReviewItem['source_reason']) => {
    if (reason === 'failed') return 'Nerezolvat';
    if (reason === 'partial') return 'Parțial';
    return 'De revăzut';
  };

  if (loading) return <div className="student-empty">Se încarcă jurnalul de erori...</div>;
  if (items.length === 0) {
    return (
      <div className="student-empty">
        Nu ai exerciții în lista de revizuit. Când marchezi un exercițiu ca nerezolvat, îl vei vedea aici.
      </div>
    );
  }

  return (
    <div className="review-tab">
      <div className="review-summary-card">
        <div className="review-summary-value">{items.length}</div>
        <div className="review-summary-text">
          exerciții de revăzut. Ține flow-ul simplu: vezi rezolvarea, retrimite la corectare dacă vrei feedback, apoi apasă pe „Am clarificat”.
        </div>
      </div>

      <div className="review-list">
        {items.map((item, index) => (
          <div key={item.id} className="review-item-shell">
            <div className="review-item-meta">
              <span className={`review-reason-badge reason-${item.source_reason}`}>{reasonLabel(item.source_reason)}</span>
              <span>reveniri: {item.revisit_count}</span>
              <span>încercări grele: {item.fail_count}</span>
              <span>ultima dată: {new Date(item.last_flagged_at).toLocaleDateString('ro-RO')}</span>
            </div>
            <div className="review-item-toolbar">
              <button
                className="review-item-resolve-btn"
                onClick={() => handleResolved(item.id)}
                disabled={busyId === item.id}
              >
                {busyId === item.id ? 'Se actualizează...' : 'Am clarificat'}
              </button>
            </div>
            <SimpleExerciseCard
              exercise={item}
              index={index + 1}
              isPremium={canHelpRequests}
              completedIds={completedIds}
              onToggleComplete={(id, val, xp, badges) => {
                onToggleComplete(id, val, xp, badges);
                loadItems();
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Main Component ---

export default function StudentExercises() {
  const { canHelpRequests, canUnlimitedGen } = useAuth();
  const [searchParams] = useSearchParams();
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [gamRefresh, setGamRefresh] = useState(0);
  const [xpToast, setXpToast] = useState<{ xp: number; badges: string[] } | null>(null);
  const initialTab = searchParams.get('tab');
  const normalizeTab = (value: string | null) => (
    value === 'sets' || value === 'parents' || value === 'review' ? value : 'generate'
  ) as 'generate' | 'sets' | 'parents' | 'review';
  const [activeTab, setActiveTab] = useState<'generate' | 'sets' | 'parents' | 'review'>(normalizeTab(initialTab));
  const [groups, setGroups] = useState<ExerciseGroup[]>([]);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [generated, setGenerated] = useState(false);
  const [limits, setLimits] = useState<GenLimits | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [savedSetId, setSavedSetId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Filters
  const [count, setCount] = useState(10);
  const [subiectTag, setSubiectTag] = useState(searchParams.get('subiect') || 'all');
  const [profile, setProfile] = useState('all');
  const [year, setYear] = useState('all');
  const [topicTag, setTopicTag] = useState('all');
  const [methodTag, setMethodTag] = useState('all');
  const [diffMin, setDiffMin] = useState(1);
  const [diffMax, setDiffMax] = useState(10);
  const [hasSolution, setHasSolution] = useState(false);
  const [hasScoringGuide, setHasScoringGuide] = useState(false);

  const activeFilterCount = [
    subiectTag !== 'all', profile !== 'all', year !== 'all',
    topicTag !== 'all', methodTag !== 'all',
    diffMin > 1 || diffMax < 10, hasSolution, hasScoringGuide,
  ].filter(Boolean).length;

  const resetFilters = () => {
    setSubiectTag('all'); setProfile('all'); setYear('all');
    setTopicTag('all'); setMethodTag('all');
    setDiffMin(1); setDiffMax(10);
    setHasSolution(false); setHasScoringGuide(false);
  };

  const refreshLimits = () => {
    getMyLimits()
      .then((res) => setLimits(res.data))
      .catch(() => {});
  };

  const onToggleComplete = (id: string, val: boolean, xp: number, badges: string[]) => {
    setCompletedIds(prev => { const s = new Set(prev); val ? s.add(id) : s.delete(id); return s; });
    if (val && (xp > 0 || badges.length > 0)) { setXpToast({ xp, badges }); setGamRefresh(r => r + 1); }
  };

  // Load static options + completed exercise ids on mount
  useEffect(() => {
    getExerciseFilterOptions()
      .then((res) => setFilterOptions(res.data))
      .catch(() => {});
    refreshLimits();
    getCompletedExerciseIds()
      .then((res) => setCompletedIds(new Set(res.data)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setActiveTab(normalizeTab(searchParams.get('tab')));
  }, [searchParams]);

  // Refresh topics & methods when context filters change
  useEffect(() => {
    const params: Parameters<typeof getExerciseFilterOptions>[0] = {};
    if (subiectTag !== 'all') params.subiect_tag = subiectTag;
    if (profile !== 'all') params.profile = profile;
    if (year !== 'all') params.year = parseInt(year);
    if (topicTag !== 'all') params.topic_tag = topicTag;

    getExerciseFilterOptions(params)
      .then((res) => {
        setFilterOptions((prev) => prev ? {
          ...prev,
          topics: res.data.topics,
          methods: res.data.methods,
        } : res.data);
        // Reset topic/method if no longer available
        const topicKeys = res.data.topics.map((t) => t.key);
        const methodKeys = res.data.methods.map((m) => m.key);
        if (topicTag !== 'all' && !topicKeys.includes(topicTag)) setTopicTag('all');
        if (methodTag !== 'all' && !methodKeys.includes(methodTag)) setMethodTag('all');
      })
      .catch(() => {});
  }, [subiectTag, profile, year, topicTag]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadExercises = async () => {
    setGenError(null);
    setSavedSetId(null);
    setLoading(true);
    setGroups([]);
    setPage(1);

    try {
      await logExerciseGeneration();
    } catch (err: any) {
      const s = err.response?.status;
      if (s === 403) {
        setLoading(false);
        setGenError(err.response?.data?.detail || 'Limita de generări a fost atinsă.');
        refreshLimits();
        return;
      }
    }

    try {
      const baseParams = {
        only_roots: true,
        exclude_seen: true,
        ...(subiectTag !== 'all' && { subiect_tag: subiectTag }),
        ...(profile !== 'all' && { profile }),
        ...(year !== 'all' && { year: parseInt(year) }),
        ...(topicTag !== 'all' && { topic_tag: topicTag }),
        ...(methodTag !== 'all' && { method_tag: methodTag }),
        ...(diffMin > 1 && { difficulty_min: diffMin }),
        ...(diffMax < 10 && { difficulty_max: diffMax }),
        ...(hasSolution && { has_solution: true }),
        ...(hasScoringGuide && { has_scoring_guide: true }),
      };

      const maxContainers = Math.max(1, Math.floor(count / 3));

      const [simplesRes, containersRes] = await Promise.all([
        getExercises({ ...baseParams, is_container: false, limit: count * 3 }),
        getExercises({ ...baseParams, is_container: true, limit: maxContainers * 3 }),
      ]);

      const simples: Exercise[] = Array.isArray(simplesRes.data) ? simplesRes.data : [];
      const containers: Exercise[] = Array.isArray(containersRes.data) ? containersRes.data : [];

      const pickContainers = containers.slice(0, maxContainers);
      const pickSimples = simples.slice(0, count - pickContainers.length);

      const result: ExerciseGroup[] = pickSimples.map((ex) => ({ type: 'simple' as const, exercise: ex }));

      if (pickContainers.length > 0) {
        const batchRes = await getBatchChildren(pickContainers.map((p) => p.id));
        const childrenMap: Record<string, Exercise[]> = batchRes.data || {};
        for (const parent of pickContainers) {
          const children = childrenMap[parent.id] || [];
          if (children.length > 0) result.push({ type: 'grouped', exercise: parent, children });
          else result.push({ type: 'simple', exercise: parent });
        }
      }

      // Shuffle
      result.sort(() => Math.random() - 0.5);
      setGroups(result);
      setGenerated(true);
      refreshLimits();

      const allIds = result.map((g) => g.exercise.id);
      if (allIds.length > 0) {
        const filters: Record<string, any> = {};
        if (subiectTag !== 'all') filters.subiect_tag = subiectTag;
        if (profile !== 'all') filters.profile = profile;
        if (year !== 'all') filters.year = year;
        if (topicTag !== 'all') filters.topic_tag = topicTag;
        if (methodTag !== 'all') filters.method_tag = methodTag;
        if (diffMin > 1) filters.difficulty_min = diffMin;
        if (diffMax < 10) filters.difficulty_max = diffMax;
        if (hasSolution) filters.has_solution = true;
        if (hasScoringGuide) filters.has_scoring_guide = true;

        saveExerciseSet({ exercise_ids: allIds, filters })
          .then((r) => setSavedSetId(r.data.id))
          .catch(() => {});
      }
    } catch (err: any) {
      console.error('loadExercises error:', err?.response?.status, err?.response?.data, err?.message);
      setGenError('Eroare la încărcarea exercițiilor: ' + (err?.message || 'necunoscută'));
      setGroups([]);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(groups.length / PAGE_SIZE);
  const pageGroups = groups.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const atLimit = limits !== null && !limits.has_unlimited_gen && limits.exercise_gen_limit !== null && limits.exercise_gen_used >= limits.exercise_gen_limit;

  return (
    <div className="student-exercises">
      <div className="student-ex-toolbar">
        <div className="student-ex-toolbar-left">
          <h2 className="student-ex-title">
            <BookOpen size={22} /> Exersează
          </h2>
          <p className="student-ex-sub">Selectează filtrele și generează exerciții personalizate</p>
        </div>
        {activeTab === 'generate' && (
          <button className="student-filters-toggle" onClick={() => setShowFilters((v) => !v)}>
            <SlidersHorizontal size={15} />
            Filtre
            {activeFilterCount > 0 && <span className="filters-badge">{activeFilterCount}</span>}
            {showFilters ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="student-tabs">
        <button
          className={`student-tab ${activeTab === 'generate' ? 'active' : ''}`}
          onClick={() => setActiveTab('generate')}
        >
          <Zap size={15} /> Generează
        </button>
        <button
          className={`student-tab ${activeTab === 'sets' ? 'active' : ''}`}
          onClick={() => setActiveTab('sets')}
        >
          <Layers size={15} /> Seturile mele
        </button>
        <button
          className={`student-tab ${activeTab === 'review' ? 'active' : ''}`}
          onClick={() => setActiveTab('review')}
        >
          ↺ Greșelile mele
        </button>
        <button
          className={`student-tab ${activeTab === 'parents' ? 'active' : ''}`}
          onClick={() => setActiveTab('parents')}
        >
          👨‍👩‍👧 Părinții mei
        </button>
      </div>

      {activeTab === 'sets' && <SavedSetsTab canHelpRequests={canHelpRequests} completedIds={completedIds} onToggleComplete={onToggleComplete} />}
      {activeTab === 'review' && <ReviewTab canHelpRequests={canHelpRequests} completedIds={completedIds} onToggleComplete={onToggleComplete} />}
      {activeTab === 'parents' && <ParentsTab />}

      <GamificationBar refreshTrigger={gamRefresh} />

      {xpToast && (
        <XPToast xp={xpToast.xp} badges={xpToast.badges} onDone={() => setXpToast(null)} />
      )}

      {activeTab === 'generate' && (
        <>
          {showFilters && (
            <div className="student-filters">
              <div className="filters-section-title">
                Structură examen
              </div>
              <div className="student-filters-row">
                {canUnlimitedGen ? (
                  <div className="student-filter-group">
                    <label>Număr exerciții</label>
                    <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={50}>50</option>
                    </select>
                  </div>
                ) : (
                  <div className="student-filter-group">
                    <label>Număr exerciții</label>
                    <div className="filter-locked">
                      10 <span className="filter-locked-badge">Premium Gen</span>
                    </div>
                  </div>
                )}
                <div className="student-filter-group">
                  <label>Subiect</label>
                  <select value={subiectTag} onChange={(e) => setSubiectTag(e.target.value)}>
                    {SUBIECT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="student-filter-group">
                  <label>Profil</label>
                  <select value={profile} onChange={(e) => setProfile(e.target.value)}>
                    <option value="all">Toate profilurile</option>
                    {(filterOptions?.profiles || []).map((p) => (
                      <option key={p} value={p}>{PROFILE_LABELS[p] || p}</option>
                    ))}
                  </select>
                </div>
                <div className="student-filter-group">
                  <label>An examen</label>
                  <select value={year} onChange={(e) => setYear(e.target.value)}>
                    <option value="all">Toți anii</option>
                    {(filterOptions?.years || []).map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
              </div>

              {canUnlimitedGen ? (
                <>
                  <div className="filters-section-title">Conținut</div>
                  <div className="student-filters-row">
                    <div className="student-filter-group">
                      <label>Domeniu matematic</label>
                      <select value={topicTag} onChange={(e) => setTopicTag(e.target.value)}>
                        <option value="all">Toate domeniile</option>
                        {(filterOptions?.topics || []).map((t) => (
                          <option key={t.key} value={t.key}>{t.label} ({t.count})</option>
                        ))}
                      </select>
                    </div>
                    <div className="student-filter-group">
                      <label>Metodă de rezolvare</label>
                      <select value={methodTag} onChange={(e) => setMethodTag(e.target.value)}>
                        <option value="all">Orice metodă</option>
                        {(filterOptions?.methods || []).slice(0, 30).map((m) => (
                          <option key={m.key} value={m.key}>{m.label} ({m.count})</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="filters-section-title">Dificultate & disponibilitate</div>
                  <div className="student-filters-row">
                    <div className="student-filter-group student-filter-difficulty">
                      <label>
                        Dificultate: <strong>{DIFFICULTY_LABELS[diffMin] || diffMin}</strong> — <strong>{DIFFICULTY_LABELS[diffMax] || diffMax}</strong>
                      </label>
                      <div className="difficulty-range">
                        <span className="diff-label">1</span>
                        <input type="range" min={1} max={10} value={diffMin}
                          onChange={(e) => setDiffMin(Math.min(Number(e.target.value), diffMax))}
                          className="diff-slider" />
                        <input type="range" min={1} max={10} value={diffMax}
                          onChange={(e) => setDiffMax(Math.max(Number(e.target.value), diffMin))}
                          className="diff-slider" />
                        <span className="diff-label">10</span>
                      </div>
                    </div>
                    <div className="student-filter-checks">
                      <label className="checkbox-label">
                        <input type="checkbox" checked={hasSolution} onChange={(e) => setHasSolution(e.target.checked)} />
                        Cu rezolvare
                      </label>
                      <label className="checkbox-label">
                        <input type="checkbox" checked={hasScoringGuide} onChange={(e) => setHasScoringGuide(e.target.checked)} />
                        Cu barem
                      </label>
                    </div>
                  </div>
                </>
              ) : (
                <div className="filters-premium-banner">
                  <span className="filter-locked-badge">Premium Gen</span>
                  Filtre avansate: domeniu, metodă, dificultate, disponibilitate
                </div>
              )}

              {activeFilterCount > 0 && (
                <div className="filters-reset-row">
                  <button className="filters-reset-btn" onClick={resetFilters}>
                    <X size={13} /> Resetează filtrele ({activeFilterCount})
                  </button>
                </div>
              )}
            </div>
          )}

          {limits && !limits.has_unlimited_gen && limits.exercise_gen_limit !== null && (
            <div className={`gen-limit-bar ${atLimit ? 'gen-limit-bar--full' : ''}`}>
              <Zap size={14} />
              <span>
                Generări exerciții luna aceasta: <strong>{limits.exercise_gen_used}/{limits.exercise_gen_limit}</strong>
                {atLimit && ' — Limită atinsă. Upgrade la Premium Gen pentru generare nelimitată.'}
              </span>
            </div>
          )}

          {genError && (
            <div className="gen-limit-bar gen-limit-bar--full">{genError}</div>
          )}

          <button
            className="student-generate-btn"
            onClick={loadExercises}
            disabled={loading || atLimit}
          >
            <Zap size={18} />
            {loading ? 'Se generează...' : generated ? 'Generează din nou' : 'Generează exerciții'}
          </button>

          {savedSetId && generated && (
            <div className="saved-set-notice">
              Set salvat automat.{' '}
              <button className="saved-set-notice-link" onClick={() => setActiveTab('sets')}>
                Vezi seturile mele
              </button>
            </div>
          )}

          {!canHelpRequests && generated && (
            <div className="student-premium-banner">
              <Flag size={16} />
              <span>
                <strong>Premium Help</strong> — Activează pentru a cere ajutor de la profesori
                (rezolvare scrisă, video sau sesiune live).
              </span>
            </div>
          )}

          {generated && !loading && groups.length > 0 && (
            <div className="pagination-info">
              {groups.length} exerciții · pagina {page} din {totalPages}
            </div>
          )}

          <div className="student-exercises-list">
            {!generated && !loading && (
              <div className="student-empty">Configurează filtrele și apasă „Generează exerciții".</div>
            )}
            {loading && <div className="student-empty">Se încarcă exercițiile...</div>}
            {!loading && generated && groups.length === 0 && (
              <div className="student-empty">Nu s-au găsit exerciții cu filtrele selectate. Încearcă să relaxezi criteriile sau ai parcurs deja toate exercițiile disponibile.</div>
            )}
            {!loading && pageGroups.map((g, i) =>
              g.type === 'simple' ? (
                <SimpleExerciseCard key={g.exercise.id} exercise={g.exercise} index={(page - 1) * PAGE_SIZE + i + 1} isPremium={canHelpRequests} completedIds={completedIds} onToggleComplete={onToggleComplete} />
              ) : (
                <GroupedExerciseCard key={g.exercise.id} parent={g.exercise} children={g.children || []} index={(page - 1) * PAGE_SIZE + i + 1} isPremium={canHelpRequests} completedIds={completedIds} onToggleComplete={onToggleComplete} />
              )
            )}
          </div>

          <Pagination page={page} totalPages={totalPages} onChange={setPage} />
        </>
      )}
    </div>
  );
}
