import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import { getMyVariants, getMyAccess, getMyLimits, type GenLimits } from "../api";
import LatexRenderer from "./LatexRenderer";
import "./VariantBuilder.css";

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

interface VariantExercise {
  id: string;
  exercise_id: string;
  order_index: number;
  section_name?: string;
  statement_latex: string;
  statement_text: string;
  points: number;
  item_type: string;
  subject_part: string;
  difficulty: number;
}

type MsgType = "info" | "success" | "error";
type UiMsg = { type: MsgType; text: string };

const DEFAULT_API_BASE = "http://localhost:8000";


export default function VariantBuilderAuto() {
  const apiBase = (import.meta as any).env?.VITE_API_URL ?? DEFAULT_API_BASE;

  const [variants, setVariants] = useState<Variant[]>([]);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [variantExercises, setVariantExercises] = useState<VariantExercise[]>([]);

  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [msg, setMsg] = useState<UiMsg | null>(null);
  const [canDownloadPdf, setCanDownloadPdf] = useState(false);
  const [limits, setLimits] = useState<GenLimits | null>(null);

  const [newVariant, setNewVariant] = useState({
    name: "",
    exam_type: "bacalaureat",
    profile: "mate-info",
    year: new Date().getFullYear(),
    session: "iunie",
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

  const setInfo = (text: string) => setMsg({ type: "info", text });
  const setSuccess = (text: string) => setMsg({ type: "success", text });
  const setError = (text: string) => setMsg({ type: "error", text });

  const authHeaders = (): Record<string, string> => {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchVariants = async () => {
    const res = await getMyVariants();
    return res.data as Variant[];
  };

  const fetchVariantExercises = async (variantId: string) => {
    const r = await fetch(`${apiBase}/variants/${variantId}/exercises/`, {
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error("Nu pot încărca exercițiile pentru variantă.");
    return (await r.json()) as VariantExercise[];
  };

  const refreshAll = async () => {
    setLoading(true);
    setInfo("Se reîncarcă…");
    try {
      const [v, access, lim] = await Promise.all([
        fetchVariants(),
        getMyAccess().then(r => r.data),
        getMyLimits().then(r => r.data).catch(() => null),
      ]);
      setVariants(v);
      setCanDownloadPdf(access.can_download_pdf);
      setLimits(lim);
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
        setError(err?.message ?? "Eroare la încărcarea exercițiilor.");
      }
    })();
  }, [selectedVariantId]);

  const createVariant = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setInfo("Se creează varianta…");
    try {
      const r = await fetch(`${apiBase}/variants/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(newVariant),
      });

      if (!r.ok) throw new Error("Eroare la crearea variantei.");

      const created = (await r.json()) as Variant;
      setVariants((prev) => [created, ...prev]);
      setSelectedVariantId(created.id);
      setShowCreate(false);
      setSuccess("Variantă creată.");
      getMyLimits().then(r => setLimits(r.data)).catch(() => {});
    } catch (err: any) {
      setError(err?.message ?? "Eroare la crearea variantei.");
    } finally {
      setLoading(false);
    }
  };

  const generateExercises = async () => {
    if (!selectedVariantId) {
      setError("Selectează o variantă.");
      return;
    }

    setLoading(true);
    setInfo("Se generează automat exercițiile…");
    try {
      const r = await fetch(`${apiBase}/variants/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ variant_id: selectedVariantId }),
      });

      if (!r.ok) {
        const errData = await r.json().catch(() => ({}));
        throw new Error(errData.detail || "Eroare la generare.");
      }

      const ve = await fetchVariantExercises(selectedVariantId);
      setVariantExercises(ve);
      setSuccess("Generare completă.");
      getMyLimits().then(r => setLimits(r.data)).catch(() => {});
    } catch (err: any) {
      setError(err?.message ?? "Eroare la generare.");
    } finally {
      setLoading(false);
    }
  };

  const openPreview = async (endpoint: string, requiresPdf = false) => {
    if (!selectedVariantId) { setError("Selectează o variantă."); return; }
    if (requiresPdf && !canDownloadPdf) {
      setError("Descărcarea PDF necesită abonamentul Premium PDF. Contactează un administrator.");
      return;
    }
    setInfo("Se generează documentul…");
    try {
      const r = await fetch(`${apiBase}/variants/${selectedVariantId}/${endpoint}`, {
        headers: authHeaders(),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "Eroare la generare.");
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setMsg(null);
    } catch (err: any) {
      setError(err.message ?? "Eroare la generare.");
    }
  };

  return (
    <div className="vx-page">
      <div className="vx-header">
        <div className="vx-title">
          <div className="vx-icon" aria-hidden>
            <Sparkles size={18} />
          </div>
          <div>
            <h2>Auto Variant Builder</h2>
            <p>Generează automat subiecte și descarcă PDF.</p>
          </div>
        </div>

        <div className="vx-header-actions">
          <button className="vx-btn vx-btn-secondary" type="button" onClick={refreshAll} disabled={loading}>
            <RefreshCw size={16} />
            Refresh
          </button>

          <button className="vx-btn vx-btn-primary" type="button" onClick={() => setShowCreate((v) => !v)} disabled={loading}>
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

      <div className="vx-grid vx-grid-auto">
        <section className="vx-card">
          <div className="vx-card-head">
            <div>
              <div className="vx-card-title">Variante</div>
              <div className="vx-card-sub">Selectează o variantă pentru generare / PDF</div>
            </div>
            <div className="vx-header-actions">
              {selectedVariant ? <span className="vx-pill">{totalPoints}p</span> : null}
              <button
                className="vx-btn vx-btn-primary"
                type="button"
                onClick={generateExercises}
                disabled={loading || !selectedVariantId || (limits !== null && !limits.has_unlimited_gen && limits.variant_gen_limit !== null && limits.variant_gen_used >= limits.variant_gen_limit)}
                title={limits && !limits.has_unlimited_gen && limits.variant_gen_limit !== null && limits.variant_gen_used >= limits.variant_gen_limit ? 'Limita de 1 variantă/lună atinsă. Upgrade la Premium Gen.' : undefined}
              >
                {loading ? <Loader2 size={16} className="vx-spin" /> : <Sparkles size={16} />}
                Generează
              </button>
            </div>
          </div>

          {limits && !limits.has_unlimited_gen && limits.variant_gen_limit !== null && (
            <div className={`vx-gen-limit ${limits.variant_gen_used >= limits.variant_gen_limit ? 'vx-gen-limit--full' : ''}`}>
              <Zap size={14} />
              <span>
                Variante generate luna aceasta: <strong>{limits.variant_gen_used}/{limits.variant_gen_limit}</strong>
                {limits.variant_gen_used >= limits.variant_gen_limit && ' — Upgrade la Premium Gen pentru generare nelimitată.'}
              </span>
            </div>
          )}

          <div className="vx-toolbar">
            <button
              className={`vx-btn ${canDownloadPdf ? 'vx-btn-secondary' : 'vx-btn-locked'}`}
              type="button"
              onClick={() => openPreview("preview-exam", true)}
              disabled={!selectedVariantId || loading}
              title={canDownloadPdf ? 'Descarcă subiect PDF' : 'Necesită Premium PDF'}
            >
              {canDownloadPdf ? <Download size={15} /> : <Lock size={15} />}
              Subiect
            </button>
            <button
              className={`vx-btn ${canDownloadPdf ? 'vx-btn-secondary' : 'vx-btn-locked'}`}
              type="button"
              onClick={() => openPreview("preview-solutions", true)}
              disabled={!selectedVariantId || loading}
              title={canDownloadPdf ? 'Descarcă rezolvare PDF' : 'Necesită Premium PDF'}
            >
              {canDownloadPdf ? <Download size={15} /> : <Lock size={15} />}
              Rezolvare
            </button>
            <button
              className={`vx-btn ${canDownloadPdf ? 'vx-btn-secondary' : 'vx-btn-locked'}`}
              type="button"
              onClick={() => openPreview("preview-barem", true)}
              disabled={!selectedVariantId || loading}
              title={canDownloadPdf ? 'Descarcă barem PDF' : 'Necesită Premium PDF'}
            >
              {canDownloadPdf ? <Download size={15} /> : <Lock size={15} />}
              Barem
            </button>
            {!canDownloadPdf && (
              <span className="vx-pdf-lock-notice">
                <Lock size={13} /> Premium PDF necesar
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
                  placeholder="Ex: Bac 2025 MI Auto"
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

          <div className="vx-list vx-list-scroll">
            {variants.length === 0 ? (
              <div className="vx-empty">Nu există variante.</div>
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
                    {v.exam_type} • {v.year} • {v.status}
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="vx-footer">
            <div className="vx-footer-left">
              {selectedVariant ? (
                <>
                  Selectată: <b>{selectedVariant.name}</b>
                </>
              ) : (
                "Selectează o variantă."
              )}
            </div>
          </div>
        </section>

        <section className="vx-card vx-card-wide">
          <div className="vx-card-head">
            <div>
              <div className="vx-card-title">Exerciții în variantă</div>
              <div className="vx-card-sub">Preview + punctaj</div>
            </div>
            {selectedVariant ? <span className="vx-pill">Total: {totalPoints}p</span> : null}
          </div>

          {!selectedVariant ? (
            <div className="vx-empty">Selectează o variantă.</div>
          ) : variantExercises.length === 0 ? (
            <div className="vx-empty">Niciun exercițiu încă. Apasă “Generează”.</div>
          ) : (
            <div className="vx-list vx-list-scroll">
              {variantExercises
                .slice()
                .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
                .map((ex) => (
                  <div key={ex.id} className="vx-ve">
                    <div className="vx-ve-n">{(ex.order_index ?? 0) + 1}</div>
                    <div className="vx-ve-main">
                      <div className="vx-ve-title">
                        <LatexRenderer text={ex.statement_latex || ex.statement_text || "(fără enunț)"} />
                      </div>
                      <div className="vx-ve-sub">
                        {ex.item_type} • {ex.subject_part} • {ex.points || 0}p
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}