import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import "./SourceDetails.css";

type Source = {
  id: string;
  name: string;
  type: string;
  year: number | null;
  session: string | null;
  created_at: string;
  notes?: string | null;
};

type SourceStats = {
  source_id: string;
  segments_count: number;
  exercises_count: number;
  tags_count: number;
};

type Segment = {
  id: string;
  source_id: string;
  page_start: number;
  page_end: number;
  status: string;
  extraction_method?: string | null;
  created_at: string;
};

type SourceExercise = {
  id: string;
  exam_type: string;
  profile?: string | null;
  subject_part?: string | null;
  item_type: string;
  statement_text?: string | null;
  statement_latex?: string | null;
  points: number;
  difficulty?: number | null;
  status: string;
  created_at: string;
};

function previewText(ex: Pick<SourceExercise, "statement_text" | "statement_latex">) {
  const raw = (ex.statement_text || ex.statement_latex || "").trim();
  if (!raw) return "(fără enunț)";
  return raw.length > 140 ? `${raw.slice(0, 140)}…` : raw;
}

export default function SourceDetails() {
  const { sourceId } = useParams();

  const [source, setSource] = useState<Source | null>(null);
  const [stats, setStats] = useState<SourceStats | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [exercises, setExercises] = useState<SourceExercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const title = useMemo(() => source?.name ?? "Sursă", [source]);

  useEffect(() => {
    if (!sourceId) return;

    const run = async () => {
      setLoading(true);
      setErr(null);
      try {
        const [s, st, seg, ex] = await Promise.all([
          api.get<Source>(`/sources/${sourceId}`),
          api.get<SourceStats>(`/sources/${sourceId}/stats`),
          api.get<Segment[]>(`/source-segments/?source_id=${sourceId}`),
          api.get<SourceExercise[]>(`/sources/${sourceId}/exercises`),
        ]);

        setSource(s.data);
        setStats(st.data);
        setSegments(Array.isArray(seg.data) ? seg.data : []);
        setExercises(Array.isArray(ex.data) ? ex.data : []);
      } catch (e) {
        console.error(e);
        setErr("Nu pot încărca detaliile sursei.");
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [sourceId]);

  if (loading) {
    return (
      <div className="sd-card">
        <div className="sd-loading">Se încarcă…</div>
      </div>
    );
  }

  if (err || !source) {
    return (
      <div className="sd-card">
        <div className="sd-error">{err ?? "Sursa nu există."}</div>
        <Link className="sd-back" to="/app/content/sources">Înapoi</Link>
      </div>
    );
  }

  return (
    <div className="sd-wrap">
      <div className="sd-head">
        <div>
          <div className="sd-title">{title}</div>
          <div className="sd-sub">
            {source.type} {source.year ? `• ${source.year}` : ""} {source.session ? `• ${source.session}` : ""} • ID:{" "}
            <span className="sd-mono">{source.id}</span>
          </div>
        </div>

        <div className="sd-actions">
          <Link className="sd-back" to="/app/content/sources">Înapoi la Surse</Link>
        </div>
      </div>

      <div className="sd-kpis">
        <div className="sd-kpi">
          <div className="sd-k">Segmente</div>
          <div className="sd-v">{stats?.segments_count ?? 0}</div>
        </div>
        <div className="sd-kpi">
          <div className="sd-k">Exerciții</div>
          <div className="sd-v">{stats?.exercises_count ?? 0}</div>
        </div>
        <div className="sd-kpi">
          <div className="sd-k">Tag-uri</div>
          <div className="sd-v">{stats?.tags_count ?? 0}</div>
        </div>
      </div>

      <div className="sd-grid">
        <section className="sd-card">
          <div className="sd-card-head">
            <div className="sd-card-title">Segmente</div>
            <div className="sd-card-sub">Pagini + status</div>
          </div>

          {segments.length === 0 ? (
            <div className="sd-empty">Nu există segmente pentru această sursă.</div>
          ) : (
            <div className="sd-table-wrap">
              <table className="sd-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Pagini</th>
                    <th>Status</th>
                    <th>Metodă</th>
                  </tr>
                </thead>
                <tbody>
                  {segments.map((s, idx) => (
                    <tr key={s.id}>
                      <td>{idx + 1}</td>
                      <td>{s.page_start}–{s.page_end}</td>
                      <td><span className="sd-badge">{s.status}</span></td>
                      <td>{s.extraction_method ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="sd-card">
          <div className="sd-card-head">
            <div className="sd-card-title">Exerciții</div>
            <div className="sd-card-sub">Click pentru editare</div>
          </div>

          {exercises.length === 0 ? (
            <div className="sd-empty">Nu există exerciții legate de această sursă.</div>
          ) : (
            <div className="sd-table-wrap">
              <table className="sd-table">
                <thead>
                  <tr>
                    <th>Preview</th>
                    <th>Puncte</th>
                    <th>Status</th>
                    <th>Acțiune</th>
                  </tr>
                </thead>
                <tbody>
                  {exercises.map((e) => (
                    <tr key={e.id}>
                      <td className="sd-preview">{previewText(e)}</td>
                      <td>{e.points ?? 0}</td>
                      <td><span className="sd-badge">{e.status}</span></td>
                      <td>
                        <Link className="sd-link" to={`/app/content/exercises/${e.id}`}>
                          Deschide
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}