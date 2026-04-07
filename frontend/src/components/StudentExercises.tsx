import { useState, useEffect } from 'react';
import { Eye, EyeOff, Flag, ChevronDown, ChevronUp, BookOpen, Zap, Layers, Trash2, ChevronRight, ChevronLeft, SlidersHorizontal, X, CalendarDays, Play, Pencil } from 'lucide-react';
import {
  getExercises, getBatchChildren, createHelpRequest,
  getMyLimits, logExerciseGeneration, saveExerciseSet, getExerciseSets,
  getExerciseSet, updateExerciseSet, deleteExerciseSet, getExerciseFilterOptions,
  getCompletedExerciseIds,
  submitExercise, uploadSubmissionPhoto, getMySubmission,
  linkParent, getMyParents, removeParentLink,
  createStudyPlanDay,
  buildApiUrl,
  type Exercise, type GenLimits, type ExerciseSet, type ExerciseSetDetail, type FilterOptions,
  type ParentStudentLink, type SelfEval, type ExerciseSubmission, type SessionType,
} from '../api';
import { useAuth } from '../AuthContext';
import LatexRenderer from './LatexRenderer';
import GamificationBar, { XPToast } from './GamificationBar';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './StudentExercises.css';

const PAGE_SIZE = 22;

const FLAG_OPTIONS = [
  { type: 'WRITTEN', icon: '✍️', label: 'Rezolvare scrisă',  desc: 'Profesorul îți trimite rezolvarea detaliată în scris' },
  { type: 'VIDEO',   icon: '🎥', label: 'Rezolvare video',    desc: 'Profesorul înregistrează un clip explicativ' },
  { type: 'LIVE',    icon: '🎙️', label: 'Sesiune live',       desc: 'Intri online cu un profesor în timp real (Zoom)' },
];

interface FlagModalProps {
  exerciseId: string;
  onClose: () => void;
  onSuccess: () => void;
}

function FlagModal({ exerciseId, onClose, onSuccess }: FlagModalProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!selected) return;
    setLoading(true);
    setError('');
    try {
      await createHelpRequest({ exercise_id: exerciseId, flag_type: selected, notes });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Eroare la trimiterea cererii');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flag-modal-overlay" onClick={onClose}>
      <div className="flag-modal" onClick={(e) => e.stopPropagation()}>
        <div className="flag-modal-header">
          <h3>Cere ajutor pentru acest exercițiu</h3>
          <button className="flag-modal-close" onClick={onClose}>×</button>
        </div>
        <p className="flag-modal-subtitle">Alege cum vrei să primești ajutorul:</p>

        <div className="flag-options">
          {FLAG_OPTIONS.map((opt) => (
            <button
              key={opt.type}
              className={`flag-option ${selected === opt.type ? 'selected' : ''}`}
              onClick={() => setSelected(opt.type)}
            >
              <span className="flag-option-icon">{opt.icon}</span>
              <div className="flag-option-text">
                <div className="flag-option-label">{opt.label}</div>
                <div className="flag-option-desc">{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>

        <div className="flag-notes">
          <label>Mesaj pentru profesor (opțional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Ex: Nu înțeleg pasul de la integrare..."
            rows={3}
          />
        </div>

        {error && <div className="flag-error">{error}</div>}

        <div className="flag-modal-actions">
          <button className="flag-cancel-btn" onClick={onClose}>Anulează</button>
          <button className="flag-submit-btn" disabled={!selected || loading} onClick={handleSubmit}>
            {loading ? 'Se trimite...' : 'Trimite cererea'}
          </button>
        </div>
      </div>
    </div>
  );
}

function HelpButton({ exerciseId, isPremium }: { exerciseId: string; isPremium: boolean }) {
  const [showModal, setShowModal] = useState(false);
  const [sent, setSent] = useState(false);

  if (!isPremium) {
    return (
      <span className="student-flag-locked" title="Necesită abonament Premium">
        <Flag size={15} /> Premium
      </span>
    );
  }

  return (
    <>
      <button
        className={`student-btn-flag ${sent ? 'sent' : ''}`}
        onClick={() => !sent && setShowModal(true)}
        disabled={sent}
        title="Cere ajutor de la un profesor"
      >
        <Flag size={15} />
        {sent ? 'Trimis ✓' : 'Ajutor'}
      </button>
      {showModal && (
        <FlagModal
          exerciseId={exerciseId}
          onClose={() => setShowModal(false)}
          onSuccess={() => setSent(true)}
        />
      )}
    </>
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

function EvalModal({ exerciseId, existing, onDone, onClose }: {
  exerciseId: string;
  existing: ExerciseSubmission | null;
  onDone: (xp: number) => void;
  onClose: () => void;
}) {
  const [step, setStep] = useState<'eval' | 'photo'>(existing ? 'photo' : 'eval');
  const [selfEval, setSelfEval] = useState<SelfEval>(existing?.self_eval ?? 'complete');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [totalXp, setTotalXp] = useState(0);

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
          <span>{step === 'eval' ? 'Cum te-ai descurcat?' : 'Adaugă fotografia soluției'}</span>
          <button className="eval-modal-close" onClick={onClose}>×</button>
        </div>

        {step === 'eval' && (
          <div className="eval-modal-body">
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
            <button className="eval-submit-btn" onClick={handleEvalSubmit} disabled={busy}>
              {busy ? 'Se trimite...' : 'Confirmă →'}
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
              Un profesor EtoX o va verifica și îți va acorda încă <strong>+50% XP</strong> dacă e corectă.
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
        title={isCompleted ? 'Actualizează evaluarea' : 'Marchează ca rezolvat'}
      >
        {isCompleted ? '✓ Rezolvat' : '○ Rezolvat'}
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
          {hasSolution && (
            <button
              className={`student-btn-solution ${showSolution ? 'active' : ''}`}
              onClick={() => setShowSolution((v) => !v)}
            >
              {showSolution ? <EyeOff size={15} /> : <Eye size={15} />}
              {showSolution ? 'Ascunde' : 'Rezolvare'}
            </button>
          )}
          <HelpButton exerciseId={exercise.id} isPremium={isPremium} />
        </div>
      </div>

      <div className="student-ex-statement">
        <LatexRenderer text={exercise.statement_latex || exercise.statement_text || ''} />
      </div>

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
                  {hasSolution && (
                    <button
                      className={`student-btn-solution ${isOpen ? 'active' : ''}`}
                      onClick={() => toggleSolution(child.id)}
                    >
                      {isOpen ? <EyeOff size={14} /> : <Eye size={14} />}
                      {isOpen ? 'Ascunde' : 'Rezolvare'}
                    </button>
                  )}
                  <HelpButton exerciseId={child.id} isPremium={isPremium} />
                </div>
              </div>

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

// --- Main Component ---

export default function StudentExercises() {
  const { canHelpRequests, canUnlimitedGen } = useAuth();
  const [searchParams] = useSearchParams();
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [gamRefresh, setGamRefresh] = useState(0);
  const [xpToast, setXpToast] = useState<{ xp: number; badges: string[] } | null>(null);
  const [activeTab, setActiveTab] = useState<'generate' | 'sets' | 'parents'>('generate');
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
          className={`student-tab ${activeTab === 'parents' ? 'active' : ''}`}
          onClick={() => setActiveTab('parents')}
        >
          👨‍👩‍👧 Părinții mei
        </button>
      </div>

      {activeTab === 'sets' && <SavedSetsTab canHelpRequests={canHelpRequests} completedIds={completedIds} onToggleComplete={onToggleComplete} />}
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
