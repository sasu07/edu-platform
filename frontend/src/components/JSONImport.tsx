import React, { useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileJson2,
  FileUp,
  Loader2,
  Trash2,
  Wand2,
} from "lucide-react";
import api from "../api";
import "./JSONImport.css";

interface JSONImportProps {
  onImportSuccess: () => void;
}

type MessageType = "info" | "success" | "error";

interface ImportStatistics {
  sources: number;
  segments: number;
  tags: number;
  exercises: number;
  exercise_tags: number;
  exercise_source_segments: number;
}

type UiMessage = {
  text: string;
  type: MessageType;
};

function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let u = 0;
  while (n >= 1024 && u < units.length - 1) {
    n /= 1024;
    u += 1;
  }
  const value = u === 0 ? Math.round(n) : Math.round(n * 10) / 10;
  return `${value} ${units[u]}`;
}

function iconForMessage(type: MessageType) {
  switch (type) {
    case "success":
      return <CheckCircle2 size={18} />;
    case "error":
      return <AlertCircle size={18} />;
    default:
      return <Wand2 size={18} />;
  }
}

const JSONImport: React.FC<JSONImportProps> = ({ onImportSuccess }) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [jsonFile, setJsonFile] = useState<File | null>(null);
  const [includeContainers, setIncludeContainers] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const [message, setMessage] = useState<UiMessage | null>(null);
  const [statistics, setStatistics] = useState<ImportStatistics | null>(null);

  const fileMeta = useMemo(() => {
    if (!jsonFile) return null;
    return {
      name: jsonFile.name,
      size: formatBytes(jsonFile.size),
      updated: new Date(jsonFile.lastModified).toLocaleString(),
    };
  }, [jsonFile]);

  const setInfo = (text: string) => setMessage({ text, type: "info" });
  const setSuccess = (text: string) => setMessage({ text, type: "success" });
  const setError = (text: string) => setMessage({ text, type: "error" });

  const validateAndSetFile = (file: File) => {
    const isJson =
      file.type === "application/json" ||
      file.name.toLowerCase().endsWith(".json");

    if (!isJson) {
      setError("Fișier invalid. Încarcă un fișier .json.");
      setJsonFile(null);
      return;
    }

    setJsonFile(file);
    setMessage(null);
    setStatistics(null);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSetFile(file);
  };

  const openFileDialog = () => {
    if (loading) return;
    fileInputRef.current?.click();
  };

  const clearSelectedFile = () => {
    if (loading) return;
    setJsonFile(null);
    setStatistics(null);
    setMessage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (loading) return;

    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (loading) return;

    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) validateAndSetFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!jsonFile) {
      setError("Selectează un fișier JSON înainte de import.");
      return;
    }

    setLoading(true);
    setInfo("Import în curs…");
    setStatistics(null);

    const formData = new FormData();
    formData.append("json_file", jsonFile);
    formData.append("include_containers", includeContainers.toString());

    try {
      const response = await api.post("/import-json/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setSuccess(`Import reușit: ${response.data.message}`);
      setStatistics(response.data.statistics);
      onImportSuccess();

      setJsonFile(null);
      setIncludeContainers(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      const errorMsg =
        axiosError.response?.data?.detail || "Eroare la importul JSON.";
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="jx-card" aria-label="Import JSON">
      <header className="jx-head">
        <div className="jx-brand">
          <div className="jx-mark" aria-hidden>
            <FileJson2 size={18} />
          </div>
          <div className="jx-title-wrap">
            <h2 className="jx-title">Import JSON (OCR)</h2>
            <p className="jx-subtitle">
              Încarcă fișierul JSON generat (exerciții + tag-uri + soluții/barem)
              și salvează în baza de date.
            </p>
          </div>
        </div>

        <div className="jx-actions">
          <button
            type="button"
            className="jx-btn jx-btn-secondary"
            onClick={openFileDialog}
            disabled={loading}
          >
            <FileUp size={16} />
            Alege fișier
          </button>

          <button
            type="button"
            className="jx-btn jx-btn-ghost"
            onClick={clearSelectedFile}
            disabled={loading || !jsonFile}
            title="Curăță selecția"
          >
            <Trash2 size={16} />
            Curăță
          </button>
        </div>
      </header>

      <div className="jx-grid">
        <div className="jx-col">
          <form className="jx-form" onSubmit={handleSubmit}>
            <input
              ref={fileInputRef}
              className="jx-file-hidden"
              type="file"
              accept=".json,application/json"
              onChange={handleFileSelect}
              disabled={loading}
            />

            <div
              className={[
                "jx-drop",
                dragActive ? "is-active" : "",
                jsonFile ? "has-file" : "",
              ].join(" ")}
              onClick={() => (!jsonFile ? openFileDialog() : undefined)}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (!jsonFile) openFileDialog();
                }
              }}
              aria-label="Dropzone pentru fișier JSON"
            >
              {!jsonFile ? (
                <div className="jx-drop-inner">
                  <div className="jx-drop-ico" aria-hidden>
                    <FileUp size={28} />
                  </div>
                  <p className="jx-drop-text">
                    Trage aici fișierul <span>JSON</span> sau apasă pentru
                    selectare.
                  </p>
                  <p className="jx-drop-hint">
                    Acceptat: <code>*.json</code>
                  </p>
                </div>
              ) : (
                <div className="jx-file">
                  <div className="jx-file-ico" aria-hidden>
                    <FileJson2 size={20} />
                  </div>
                  <div className="jx-file-meta">
                    <div className="jx-file-name">{fileMeta?.name}</div>
                    <div className="jx-file-sub">
                      {fileMeta?.size} • modificat {fileMeta?.updated}
                    </div>
                  </div>

                  <button
                    type="button"
                    className="jx-icon-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      clearSelectedFile();
                    }}
                    disabled={loading}
                    aria-label="Elimină fișierul selectat"
                    title="Elimină"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}
            </div>

            <div className="jx-option">
              <label className="jx-check">
                <input
                  type="checkbox"
                  checked={includeContainers}
                  onChange={(e) => setIncludeContainers(e.target.checked)}
                  disabled={loading}
                />
                <span className="jx-check-title">
                  Include și “containers” (points = 0)
                </span>
                <span className="jx-check-hint">
                  Recomandat doar pentru debug/validare structură.
                </span>
              </label>
            </div>

            <button
              type="submit"
              className="jx-btn jx-btn-primary jx-btn-full"
              disabled={loading || !jsonFile}
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="jx-spin" />
                  Import în curs…
                </>
              ) : (
                <>
                  <Wand2 size={18} />
                  Rulează import
                </>
              )}
            </button>

            {message && (
              <div className={`jx-msg ${message.type}`}>
                <div className="jx-msg-ico" aria-hidden>
                  {iconForMessage(message.type)}
                </div>
                <div className="jx-msg-text">{message.text}</div>
              </div>
            )}

            {statistics && (
              <div className="jx-stats" aria-label="Statistici import">
                <div className="jx-stats-head">Rezultat import</div>
                <div className="jx-stats-grid">
                  <div className="jx-stat">
                    <div className="jx-stat-v">{statistics.sources}</div>
                    <div className="jx-stat-k">sources</div>
                  </div>
                  <div className="jx-stat">
                    <div className="jx-stat-v">{statistics.segments}</div>
                    <div className="jx-stat-k">segments</div>
                  </div>
                  <div className="jx-stat">
                    <div className="jx-stat-v">{statistics.tags}</div>
                    <div className="jx-stat-k">tags</div>
                  </div>
                  <div className="jx-stat">
                    <div className="jx-stat-v">{statistics.exercises}</div>
                    <div className="jx-stat-k">exercises</div>
                  </div>
                  <div className="jx-stat">
                    <div className="jx-stat-v">{statistics.exercise_tags}</div>
                    <div className="jx-stat-k">exercise_tags</div>
                  </div>
                  <div className="jx-stat">
                    <div className="jx-stat-v">
                      {statistics.exercise_source_segments}
                    </div>
                    <div className="jx-stat-k">exercise_source_segments</div>
                  </div>
                </div>
              </div>
            )}
          </form>
        </div>

        <aside className="jx-col jx-side" aria-label="Ghid import">
          <div className="jx-side-card">
            <div className="jx-side-title">Checklist</div>
            <ul className="jx-list">
              <li>
                <span className="jx-dot" aria-hidden />
                Fișierul are <b>schema_version</b> și <b>source</b>
              </li>
              <li>
                <span className="jx-dot" aria-hidden />
                Fiecare exercițiu are <b>external_id</b> stabil
              </li>
              <li>
                <span className="jx-dot" aria-hidden />
                Include <b>solution_latex</b> / <b>scoring_guide_text</b> dacă
                vrei soluții & barem
              </li>
            </ul>
          </div>

          <div className="jx-side-card">
            <div className="jx-side-title">Exemplu minimal</div>
            <pre className="jx-code" aria-label="Exemplu JSON">
{`{
  "schema_version": "1.0",
  "source": { "external_id": "bac-2025-mi-v09", "page_count": 2 },
  "exercises": [
    {
      "external_id": "B2025-MI-V09-S1-1",
      "points": 5,
      "statement_latex": "...",
      "solution_latex": "...",
      "scoring_guide_text": "Barem: ..."
    }
  ]
}`}
            </pre>
          </div>
        </aside>
      </div>
    </section>
  );
};

export default JSONImport;