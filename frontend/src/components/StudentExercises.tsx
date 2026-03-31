import { useState, useEffect } from 'react';
import { Eye, EyeOff, Flag, ChevronDown, ChevronUp, BookOpen, Zap, Layers, Trash2, ChevronRight } from 'lucide-react';
import {
  getExercises, getBatchChildren, getTags, createHelpRequest,
  getMyLimits, logExerciseGeneration, saveExerciseSet, getExerciseSets,
  getExerciseSet, deleteExerciseSet,
  type Exercise, type Tag, type GenLimits, type ExerciseSet, type ExerciseSetDetail,
} from '../api';
import { useAuth } from '../AuthContext';
import LatexRenderer from './LatexRenderer';
import './StudentExercises.css';

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

function SimpleExerciseCard({ exercise, index, isPremium }: { exercise: Exercise; index: number; isPremium: boolean }) {
  const [showSolution, setShowSolution] = useState(false);
  const path = exercise.metadata?.path;
  const hasSolution = !!(exercise.solution_latex || exercise.answer_latex);

  return (
    <div className="student-exercise-card">
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
}

function GroupedExerciseCard({ parent, children, index, isPremium }: GroupedCardProps) {
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

const EXAM_TYPES = [
  { value: 'all', label: 'Toate tipurile' },
  { value: 'bacalaureat', label: 'Bacalaureat' },
  { value: 'evaluare_nationala', label: 'Evaluare Națională' },
  { value: 'simulare', label: 'Simulare' },
];

const SUBIECT_OPTIONS = [
  { value: 'all', label: 'Toate subiectele' },
  { value: '1', label: 'Subiectul I (exerciții rapide)' },
  { value: '2', label: 'Subiectul II (probleme)' },
  { value: '3', label: 'Subiectul III (probleme)' },
];

const DIFFICULTY_LABELS: Record<number, string> = {
  1: 'Foarte ușor', 2: 'Ușor', 3: 'Mediu-ușor', 4: 'Mediu', 5: 'Mediu',
  6: 'Mediu-greu', 7: 'Greu', 8: 'Greu', 9: 'Foarte greu', 10: 'Expert',
};

// --- Saved Sets Components ---

function SetCard({ set, onOpen, onDelete }: {
  set: ExerciseSet;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
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
          {filterSummary && <span className="saved-set-filters">{filterSummary}</span>}
          <span className="saved-set-date">{date}</span>
        </div>
      </div>
      <div className="saved-set-actions">
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

function SavedSetsTab({ canHelpRequests }: { canHelpRequests: boolean }) {
  const [sets, setSets] = useState<ExerciseSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [openSet, setOpenSet] = useState<ExerciseSetDetail | null>(null);
  const [loadingSet, setLoadingSet] = useState(false);

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

  if (loading) return <div className="student-empty">Se încarcă seturile...</div>;
  if (sets.length === 0) return (
    <div className="student-empty">
      Nu ai seturi salvate. Generează un set de exerciții și acesta va fi salvat automat.
    </div>
  );

  return (
    <div className="saved-sets-container">
      <div className="saved-sets-list">
        {sets.map((s) => (
          <SetCard key={s.id} set={s} onOpen={handleOpen} onDelete={handleDelete} />
        ))}
      </div>

      {loadingSet && <div className="student-empty">Se încarcă exercițiile...</div>}

      {openSet && !loadingSet && (
        <div className="saved-set-exercises">
          <div className="saved-set-exercises-header">
            <h3>{openSet.name}</h3>
            <button className="saved-set-close" onClick={() => setOpenSet(null)}>Închide ×</button>
          </div>
          <div className="student-exercises-list">
            {openSet.exercises.map((ex, i) => (
              ex.metadata?.is_container ? null :
              <SimpleExerciseCard key={ex.id} exercise={ex} index={i + 1} isPremium={canHelpRequests} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Main Component ---

export default function StudentExercises() {
  const { canHelpRequests, canUnlimitedGen } = useAuth();
  const [activeTab, setActiveTab] = useState<'generate' | 'sets'>('generate');
  const [groups, setGroups] = useState<ExerciseGroup[]>([]);
  const [topics, setTopics] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [generated, setGenerated] = useState(false);
  const [limits, setLimits] = useState<GenLimits | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [savedSetId, setSavedSetId] = useState<string | null>(null);

  // Filters
  const [examType, setExamType] = useState('all');
  const [subiectTag, setSubiectTag] = useState('all');
  const [topicTag, setTopicTag] = useState('all');
  const [diffMin, setDiffMin] = useState(1);
  const [diffMax, setDiffMax] = useState(10);
  const [hasSolution, setHasSolution] = useState(false);
  const [count, setCount] = useState(10);

  const refreshLimits = () => {
    getMyLimits()
      .then((res) => setLimits(res.data))
      .catch(() => {});
  };

  useEffect(() => {
    getTags('topic')
      .then((res) => setTopics(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
    refreshLimits();
  }, []);

  const loadExercises = async () => {
    setGenError(null);
    setSavedSetId(null);
    setLoading(true);
    setGroups([]);

    // Verifică limita — dacă primim 403 blocăm, orice altă eroare o ignorăm silențios
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
      // 404 / 500 / rețea — continuăm fără a bloca
    }

    try {
      const maxContainers = Math.max(1, Math.floor(count / 3));
      const simpleLimit = count * 4;
      const containerLimit = maxContainers * 4;

      const baseParams = {
        only_roots: true,
        exclude_seen: true,
        ...(examType !== 'all' && { exam_type: examType }),
        ...(subiectTag !== 'all' && { subiect_tag: subiectTag }),
        ...(topicTag !== 'all' && { topic_tag: topicTag }),
        ...(diffMin > 1 && { difficulty_min: diffMin }),
        ...(diffMax < 10 && { difficulty_max: diffMax }),
        ...(hasSolution && { has_solution: true }),
      };

      const [simplesRes, containersRes] = await Promise.all([
        getExercises({ ...baseParams, is_container: false, limit: simpleLimit }),
        getExercises({ ...baseParams, is_container: true, limit: containerLimit }),
      ]);

      const simples: Exercise[] = Array.isArray(simplesRes.data) ? simplesRes.data : [];
      const containers: Exercise[] = Array.isArray(containersRes.data) ? containersRes.data : [];

      const pickSimples = simples.slice(0, count - Math.min(maxContainers, containers.length));
      const pickContainers = containers.slice(0, Math.min(maxContainers, containers.length));

      const result: ExerciseGroup[] = [];

      for (const ex of pickSimples) {
        result.push({ type: 'simple', exercise: ex });
      }

      if (pickContainers.length > 0) {
        const batchRes = await getBatchChildren(pickContainers.map((p) => p.id));
        const childrenMap: Record<string, Exercise[]> = batchRes.data || {};
        for (const parent of pickContainers) {
          const children = childrenMap[parent.id] || [];
          if (children.length > 0) result.push({ type: 'grouped', exercise: parent, children });
          else result.push({ type: 'simple', exercise: parent });
        }
      }

      result.sort(() => Math.random() - 0.5);
      setGroups(result);
      setGenerated(true);
      refreshLimits();

      // Salvează setul în backend
      const allIds = result.map((g) => g.exercise.id);
      if (allIds.length > 0) {
        const filters: Record<string, any> = {};
        if (examType !== 'all') filters.exam_type = examType;
        if (subiectTag !== 'all') filters.subiect_tag = subiectTag;
        if (topicTag !== 'all') filters.topic_tag = topicTag;
        if (diffMin > 1) filters.difficulty_min = diffMin;
        if (diffMax < 10) filters.difficulty_max = diffMax;
        if (hasSolution) filters.has_solution = true;

        const linked_plan = canUnlimitedGen ? 'premium_gen' : null;

        saveExerciseSet({ exercise_ids: allIds, filters, linked_plan })
          .then((r) => setSavedSetId(r.data.id))
          .catch(() => {});
      }
    } catch {
      setGroups([]);
    } finally {
      setLoading(false);
    }
  };

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
            Filtre {showFilters ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
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
      </div>

      {activeTab === 'sets' && <SavedSetsTab canHelpRequests={canHelpRequests} />}

      {activeTab === 'generate' && (
        <>
          {showFilters && (
            <div className="student-filters">
              <div className="student-filters-row">
                <div className="student-filter-group">
                  <label>Tip examen</label>
                  <select value={examType} onChange={(e) => setExamType(e.target.value)}>
                    {EXAM_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="student-filter-group">
                  <label>Subiect BAC</label>
                  <select value={subiectTag} onChange={(e) => setSubiectTag(e.target.value)}>
                    {SUBIECT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="student-filter-group">
                  <label>Domeniu / Topic</label>
                  <select value={topicTag} onChange={(e) => setTopicTag(e.target.value)}>
                    <option value="all">Toate domeniile</option>
                    {topics.map((t) => (
                      <option key={t.id} value={t.key}>{t.label || t.key}</option>
                    ))}
                  </select>
                </div>
                <div className="student-filter-group">
                  <label>Număr exerciții</label>
                  <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>
              </div>

              <div className="student-filters-row">
                <div className="student-filter-group student-filter-difficulty">
                  <label>
                    Dificultate: <strong>{DIFFICULTY_LABELS[diffMin] || diffMin}</strong> → <strong>{DIFFICULTY_LABELS[diffMax] || diffMax}</strong>
                  </label>
                  <div className="difficulty-range">
                    <span className="diff-label">1</span>
                    <input
                      type="range" min={1} max={10} value={diffMin}
                      onChange={(e) => setDiffMin(Math.min(Number(e.target.value), diffMax))}
                      className="diff-slider"
                    />
                    <input
                      type="range" min={1} max={10} value={diffMax}
                      onChange={(e) => setDiffMax(Math.max(Number(e.target.value), diffMin))}
                      className="diff-slider"
                    />
                    <span className="diff-label">10</span>
                  </div>
                </div>

                <div className="student-filter-group student-filter-checkbox">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={hasSolution}
                      onChange={(e) => setHasSolution(e.target.checked)}
                    />
                    Doar cu rezolvare disponibilă
                  </label>
                </div>
              </div>
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

          <div className="student-exercises-list">
            {!generated && !loading && (
              <div className="student-empty">Configurează filtrele și apasă „Generează exerciții".</div>
            )}
            {loading && <div className="student-empty">Se încarcă exercițiile...</div>}
            {!loading && generated && groups.length === 0 && (
              <div className="student-empty">Nu s-au găsit exerciții cu filtrele selectate. Încearcă să relaxezi criteriile sau ai parcurs deja toate exercițiile disponibile.</div>
            )}
            {!loading && groups.map((g, i) =>
              g.type === 'simple' ? (
                <SimpleExerciseCard key={g.exercise.id} exercise={g.exercise} index={i + 1} isPremium={canHelpRequests} />
              ) : (
                <GroupedExerciseCard key={g.exercise.id} parent={g.exercise} children={g.children || []} index={i + 1} isPremium={canHelpRequests} />
              )
            )}
          </div>
        </>
      )}
    </div>
  );
}
