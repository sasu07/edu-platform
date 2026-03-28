import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Filter,
  LayoutGrid,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import "./VariantBuilder.css";

interface Exercise {
  id: string;
  statement_latex: string;
  statement_text: string;
  points: number;
  item_type: string;
  subject_part: string;
  difficulty: number;
  exam_type: string;
}

interface Variant {
  id: string;
  name: string;
  exam_type: string;
  profile: string;
  year: number;
  session: string;
  total_points: number;
  duration_minutes: number;
  instructions: string;
  status: string;
  created_at: string;
}

interface VariantExercise extends Exercise {
  order_index: number;
  section_name?: string;
  exercise_id?: string;
}

type MsgType = "info" | "success" | "error";
type UiMsg = { type: MsgType; text: string };

const DEFAULT_API_BASE = "http://localhost:8000";

function previewText(ex: Pick<Exercise, "statement_text" | "statement_latex">) {
  const raw = (ex.statement_text || ex.statement_latex || "").trim();
  if (!raw) return "(fără enunț)";
  return raw.length > 160 ? `${raw.slice(0, 160)}…` : raw;
}

function examLabel(v: string) {
  const map: Record<string, string> = {
    bacalaureat: "Bacalaureat",
    evaluare_nationala: "Evaluare Națională",
    simulare: "Simulare",
    olimpiada: "Olimpiadă",
    alta: "Altă",
  };
  return map[v] ?? v;
}

export default function VariantBuilder() {
  const apiBase = (import.meta as any).env?.VITE_API_URL ?? DEFAULT_API_BASE;

  const [variants, setVariants] = useState<Variant[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);

  const [variantExercises, setVariantExercises] = useState<VariantExercise[]>([]);
  const [selectedExercises, setSelectedExercises] = useState<Set<string>>(new Set());

  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const [filterExamType, setFilterExamType] = useState("");
  const [query, setQuery] = useState("");
  const [msg, setMsg] = useState<UiMsg | null>(null);

  const [newVariant, setNewVariant] = useState({
    name: "",
    exam_type: "bacalaureat",
    profile: "",
    year: new Date().getFullYear(),
    session: "",
    duration_minutes: 180,
    instructions: "",
  });

  const selectedVariant = useMemo(
    () => variants.find((v) => v.id === selectedVariantId) ?? null,
    [variants, selectedVariantId]
  );

  const totalPoints = useMemo(
    () => variantExercises.reduce((sum, e) => sum + (e.points || 0), 0),
    [variantExercises]
  );

  const filteredExercises = useMemo(() => {
    const q = query.trim().toLowerCase();
    return exercises
      .filter((ex) => (!filterExamType ? true : ex.exam_type === filterExamType))
      .filter((ex) => {
        if (!q) return true;
        const t = (ex.statement_text || ex.statement_latex || "").toLowerCase();
        return (
          t.includes(q) ||
          (ex.item_type || "").toLowerCase().includes(q) ||
          (ex.subject_part || "").toLowerCase().includes(q)
        );
      });
  }, [exercises, filterExamType, query]);

  const setInfo = (text: string) => setMsg({ type: "info", text });
  const setSuccess = (text: string) => setMsg({ type: "success", text });
  const setError = (text: string) => setMsg({ type: "error", text });

  const fetchVariants = async () => {
    const r = await fetch(`${apiBase}/variants/`);
    if (!r.ok) throw new Error("Nu pot încărca lista de variante.");
    return (await r.json()) as Variant[];
  };

  const fetchExercises = async () => {
    const r = await fetch(`${apiBase}/exercises/`);
    if (!r.ok) throw new Error("Nu pot încărca lista de exerciții.");
    return (await r.json()) as Exercise[];
  };

  const fetchVariantExercises = async (variantId: string) => {
    const r = await fetch(`${apiBase}/variants/${variantId}/exercises/`);
    if (!r.ok) throw new Error("Nu pot încărca exercițiile pentru variantă.");
    return (await r.json()) as VariantExercise[];
  };

  const refreshAll = async () => {
    setLoading(true);
    setInfo("Se reîncarcă datele…");
    try {
      const [v, e] = await Promise.all([fetchVariants(), fetchExercises()]);
      setVariants(v);
      setExercises(e);
      setMsg(null);
    } catch (err: any) {
      setError(err?.message ?? "Eroare la refresh.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedVariantId) {
      setVariantExercises([]);
      return;
    }
    (async () => {
      try {
        const ve = await fetchVariantExercises(selectedVariantId);
        setVariantExercises(ve);
      } catch (err: any) {
        setError(err?.message ?? "Eroare la încărcarea exercițiilor din variantă.");
      }
    })();
  }, [selectedVariantId]);

  const toggleExercise = (id: string) => {
    setSelectedExercises((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const createVariant = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setInfo("Se creează varianta…");
    try {
      const r = await fetch(`${apiBase}/variants/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newVariant),
      });

      if (!r.ok) throw new Error("Eroare la crearea variantei.");

      const created = (await r.json()) as Variant;
      setVariants((prev) => [created, ...prev]);
      setSelectedVariantId(created.id);
      setShowCreate(false);
      setNewVariant({
        name: "",
        exam_type: "bacalaureat",
        profile: "",
        year: new Date().getFullYear(),
        session: "",
        duration_minutes: 180,
        instructions: "",
      });
      setSuccess("Variantă creată cu succes.");
    } catch (err: any) {
      setError(err?.message ?? "Eroare la crearea variantei.");
    } finally {
      setLoading(false);
    }
  };

  const addSelectedExercises = async () => {
    if (!selectedVariantId) {
      setError("Selectează o variantă.");
      return;
    }
    if (selectedExercises.size === 0) {
      setError("Selectează cel puțin un exercițiu.");
      return;
    }

    setLoading(true);
    setInfo("Se adaugă exercițiile în variantă…");
    try {
      const r = await fetch(`${apiBase}/variants/${selectedVariantId}/exercises/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Array.from(selectedExercises)),
      });

      if (!r.ok) throw new Error("Eroare la adăugarea exercițiilor.");

      const ve = await fetchVariantExercises(selectedVariantId);
      setVariantExercises(ve);
      setSelectedExercises(new Set());
      setSuccess("Exerciții adăugate cu succes.");
    } catch (err: any) {
      setError(err?.message ?? "Eroare la adăugare.");
    } finally {
      setLoading(false);
    }
  };

  const removeExercise = async (exerciseId: string) => {
    if (!selectedVariantId) return;

    setLoading(true);
    setInfo("Se șterge exercițiul…");
    try {
      const r = await fetch(`${apiBase}/variants/${selectedVariantId}/exercises/${exerciseId}`, {
        method: "DELETE",
      });

      if (!r.ok) throw new Error("Eroare la ștergerea exercițiului.");

      const ve = await fetchVariantExercises(selectedVariantId);
      setVariantExercises(ve);
      setSuccess("Exercițiu șters.");
    } catch (err: any) {
      setError(err?.message ?? "Eroare la ștergere.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="vx-page">
      <div className="vx-header">
        <div className="vx-title">
          <div className="vx-icon" aria-hidden>
            <LayoutGrid size={18} />
          </div>
          <div>
            <h2>Variant Builder</h2>
            <p>Construiește subiecte din exercițiile disponibile.</p>
          </div>
        </div>

        <div className="vx-header-actions">
          <button className="vx-btn vx-btn-secondary" type="button" onClick={refreshAll} disabled={loading}>
            <RefreshCw size={16} />
            Refresh
          </button>

          <button
            className="vx-btn vx-btn-primary"
            type="button"
            onClick={() => setShowCreate((v) => !v)}
            disabled={loading}
          >
            <Plus size={16} />
            {showCreate ? "Închide" : "Variantă nouă"}
          </button>
        </div>
      </div>

      {msg && (
        <div className={`vx-msg ${msg.type}`}>
          <div className="vx-msg-ico" aria-hidden>
            {msg.type === "success" ? <CheckCircle2 size={18} /> : msg.type === "error" ? <AlertCircle size={18} /> : <Loader2 size={18} className="vx-spin" />}
          </div>
          <div className="vx-msg-text">{msg.text}</div>
        </div>
      )}

      <div className="vx-grid">
        {/* Variants */}
        <section className="vx-card">
          <div className="vx-card-head">
            <div>
              <div className="vx-card-title">Variante</div>
              <div className="vx-card-sub">Selectează sau creează o variantă</div>
            </div>

            {selectedVariant && (
              <span className="vx-pill" title="Total puncte în variantă">
                Total: {totalPoints}p
              </span>
            )}
          </div>

          {showCreate && (
            <form className="vx-form" onSubmit={createVariant}>
              <div className="vx-form-title">Creare variantă</div>

              <div className="vx-field">
                <label>Nume</label>
                <input
                  value={newVariant.name}
                  onChange={(e) => setNewVariant({ ...newVariant, name: e.target.value })}
                  placeholder="Ex: Bac 2025 MI Varianta 9"
                  required
                />
              </div>

              <div className="vx-row">
                <div className="vx-field">
                  <label>Tip</label>
                  <select
                    value={newVariant.exam_type}
                    onChange={(e) => setNewVariant({ ...newVariant, exam_type: e.target.value })}
                  >
                    <option value="bacalaureat">Bacalaureat</option>
                    <option value="evaluare_nationala">Evaluare Națională</option>
                    <option value="simulare">Simulare</option>
                    <option value="olimpiada">Olimpiadă</option>
                    <option value="alta">Altă</option>
                  </select>
                </div>

                <div className="vx-field">
                  <label>An</label>
                  <input
                    type="number"
                    value={newVariant.year}
                    onChange={(e) => setNewVariant({ ...newVariant, year: parseInt(e.target.value || "0", 10) })}
                  />
                </div>
              </div>

              <div className="vx-row">
                <div className="vx-field">
                  <label>Profil</label>
                  <input
                    value={newVariant.profile}
                    onChange={(e) => setNewVariant({ ...newVariant, profile: e.target.value })}
                    placeholder="Ex: mate-info"
                  />
                </div>

                <div className="vx-field">
                  <label>Sesiune</label>
                  <input
                    value={newVariant.session}
                    onChange={(e) => setNewVariant({ ...newVariant, session: e.target.value })}
                    placeholder="Ex: iunie"
                  />
                </div>
              </div>

              <div className="vx-row">
                <div className="vx-field">
                  <label>Durată (min)</label>
                  <input
                    type="number"
                    value={newVariant.duration_minutes}
                    onChange={(e) =>
                      setNewVariant({ ...newVariant, duration_minutes: parseInt(e.target.value || "0", 10) })
                    }
                  />
                </div>

                <div className="vx-field">
                  <label>Status</label>
                  <input value="DRAFT" disabled />
                </div>
              </div>

              <div className="vx-field">
                <label>Instrucțiuni</label>
                <textarea
                  value={newVariant.instructions}
                  onChange={(e) => setNewVariant({ ...newVariant, instructions: e.target.value })}
                  rows={3}
                  placeholder="Opțional"
                />
              </div>

              <button className="vx-btn vx-btn-primary vx-btn-full" type="submit" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 size={18} className="vx-spin" />
                    Se creează…
                  </>
                ) : (
                  <>
                    <Plus size={18} />
                    Creează
                  </>
                )}
              </button>
            </form>
          )}

          <div className="vx-list">
            {variants.length === 0 ? (
              <div className="vx-empty">Nu există variante încă.</div>
            ) : (
              variants.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  className={`vx-item ${selectedVariantId === v.id ? "selected" : ""}`}
                  onClick={() => setSelectedVariantId(v.id)}
                >
                  <div className="vx-item-title">{v.name}</div>
                  <div className="vx-item-sub">
                    {examLabel(v.exam_type)} • {v.year}
                    {v.profile ? ` • ${v.profile}` : ""} • {v.status}
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        {/* Exercises */}
        <section className="vx-card vx-card-wide">
          <div className="vx-card-head">
            <div>
              <div className="vx-card-title">Exerciții</div>
              <div className="vx-card-sub">Selectează exerciții și adaugă la variantă</div>
            </div>

            <div className="vx-tools">
              <div className="vx-search">
                <Search size={16} />
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Caută…" />
              </div>

              <div className="vx-select">
                <Filter size={16} />
                <select value={filterExamType} onChange={(e) => setFilterExamType(e.target.value)}>
                  <option value="">Toate</option>
                  <option value="bacalaureat">Bacalaureat</option>
                  <option value="evaluare_nationala">Evaluare Națională</option>
                  <option value="simulare">Simulare</option>
                  <option value="olimpiada">Olimpiadă</option>
                </select>
              </div>
            </div>
          </div>

          <div className="vx-list vx-list-scroll">
            {filteredExercises.length === 0 ? (
              <div className="vx-empty">Nu există exerciții pentru filtrul curent.</div>
            ) : (
              filteredExercises.map((ex) => {
                const checked = selectedExercises.has(ex.id);
                return (
                  <button
                    key={ex.id}
                    type="button"
                    className={`vx-ex ${checked ? "selected" : ""}`}
                    onClick={() => toggleExercise(ex.id)}
                  >
                    <div className="vx-ex-main">
                      <div className="vx-ex-title">{previewText(ex)}</div>
                      <div className="vx-ex-sub">
                        {ex.item_type} • {ex.subject_part} • {ex.points || 0}p
                        {ex.difficulty ? ` • Dif: ${ex.difficulty}/10` : ""}
                      </div>
                    </div>
                    <div className="vx-check" aria-hidden>
                      <input type="checkbox" checked={checked} readOnly />
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="vx-footer">
            <div className="vx-footer-left">
              Selectate: <b>{selectedExercises.size}</b>
              {selectedVariant ? (
                <>
                  {" "}
                  • Variantă: <b>{selectedVariant.name}</b>
                </>
              ) : null}
            </div>

            <button
              className="vx-btn vx-btn-primary"
              type="button"
              onClick={addSelectedExercises}
              disabled={loading || !selectedVariantId || selectedExercises.size === 0}
              title={!selectedVariantId ? "Selectează o variantă" : undefined}
            >
              {loading ? <Loader2 size={16} className="vx-spin" /> : <Plus size={16} />}
              Adaugă
            </button>
          </div>
        </section>

        {/* Variant exercises */}
        <section className="vx-card">
          <div className="vx-card-head">
            <div>
              <div className="vx-card-title">În variantă</div>
              <div className="vx-card-sub">Ordinea actuală a exercițiilor</div>
            </div>
            {selectedVariant ? <span className="vx-pill">{totalPoints}p</span> : null}
          </div>

          {!selectedVariant ? (
            <div className="vx-empty">Selectează o variantă ca să vezi conținutul.</div>
          ) : variantExercises.length === 0 ? (
            <div className="vx-empty">Niciun exercițiu încă. Adaugă din listă.</div>
          ) : (
            <div className="vx-list vx-list-scroll">
              {variantExercises.map((ex, idx) => (
                <div key={`${ex.id}-${idx}`} className="vx-ve">
                  <div className="vx-ve-n">{idx + 1}</div>
                  <div className="vx-ve-main">
                    <div className="vx-ve-title">{previewText(ex)}</div>
                    <div className="vx-ve-sub">{ex.item_type} • {ex.points || 0}p</div>
                  </div>
                  <button
                    className="vx-icon-btn"
                    type="button"
                    onClick={() => removeExercise((ex as any).exercise_id ?? ex.id)}
                    disabled={loading}
                    title="Șterge"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}