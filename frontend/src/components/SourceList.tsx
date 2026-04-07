import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, FileText, BookOpen, ChevronDown, ChevronRight } from "lucide-react";
import api, { buildApiUrl } from "../api";
import "./SourceList.css";

interface Source {
  id: string;
  name: string;
  type: string;
  year: number | null;
  session: string | null;
  profile: string | null;
  url_file_path: string | null;
  url_barem_path: string | null;
  created_at: string;
  notes?: string | null;
}

interface SourceStats {
  source_id: string;
  segments_count: number;
  exercises_count: number;
  tags_count: number;
}

interface SourceListProps {
  refreshKey: number;
}

const PROFILE_LABELS: Record<string, string> = {
  "mate-info": "Mate-Info",
  "stiinte-natura": "Științe ale Naturii",
  "tehnologic": "Tehnologic",
  "uman": "Uman",
};

function downloadFile(url: string, label: string) {
  const a = document.createElement("a");
  const token = localStorage.getItem("access_token");
  // Use fetch with auth header then create object URL
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then((res) => {
      if (!res.ok) throw new Error("Fișier indisponibil");
      return res.blob();
    })
    .then((blob) => {
      const objUrl = URL.createObjectURL(blob);
      a.href = objUrl;
      a.download = label + ".pdf";
      a.click();
      URL.revokeObjectURL(objUrl);
    })
    .catch(() => alert("Fișierul nu este disponibil pe server."));
}

function SourceRow({ source, stats }: { source: Source; stats: SourceStats | undefined }) {
  const navigate = useNavigate();
  const [dlLoading, setDlLoading] = useState<"varianta" | "barem" | null>(null);

  const handleDownload = async (type: "varianta" | "barem") => {
    setDlLoading(type);
    const url =
      type === "varianta"
        ? buildApiUrl(`/sources/${source.id}/download`)
        : buildApiUrl(`/sources/${source.id}/download-barem`);
    const label =
      type === "varianta"
        ? `Varianta_${source.name}`
        : `Barem_${source.name}`;
    downloadFile(url, label);
    setTimeout(() => setDlLoading(null), 2000);
  };

  const st = stats ?? { segments_count: 0, exercises_count: 0, tags_count: 0 };

  return (
    <div className="source-row">
      <div className="source-row-main">
        <div className="source-row-name">
          <span className="source-row-title">{source.name}</span>
          {source.session && <span className="source-row-session">{source.session}</span>}
        </div>
        <div className="source-row-meta">
          <span className="source-kpi" title="Exerciții">{st.exercises_count} ex.</span>
          <span className="source-kpi source-kpi--muted" title="Segmente">{st.segments_count} seg.</span>
        </div>
        <div className="source-row-actions">
          <button
            className={`source-dl-btn source-dl-btn--varianta ${!source.url_file_path ? 'source-dl-btn--disabled' : ''}`}
            onClick={() => source.url_file_path && handleDownload("varianta")}
            disabled={!source.url_file_path || dlLoading === "varianta"}
            title={source.url_file_path ? "Descarcă varianta originală" : "Fișier indisponibil"}
          >
            <Download size={13} />
            {dlLoading === "varianta" ? "..." : "Variantă"}
          </button>
          <button
            className={`source-dl-btn source-dl-btn--barem ${!source.url_barem_path ? 'source-dl-btn--disabled' : ''}`}
            onClick={() => source.url_barem_path && handleDownload("barem")}
            disabled={!source.url_barem_path || dlLoading === "barem"}
            title={source.url_barem_path ? "Descarcă baremul" : "Barem indisponibil"}
          >
            <BookOpen size={13} />
            {dlLoading === "barem" ? "..." : "Barem"}
          </button>
          <button
            className="details-btn"
            onClick={() => navigate(`/app/content/sources/${source.id}`)}
          >
            Vezi
          </button>
        </div>
      </div>
    </div>
  );
}

interface YearGroup {
  year: number | null;
  profileGroups: { profile: string | null; sources: Source[] }[];
}

function buildGroups(sources: Source[]): YearGroup[] {
  const byYear = new Map<string, Map<string, Source[]>>();

  for (const s of sources) {
    const yearKey = s.year !== null ? String(s.year) : "__none__";
    const profileKey = s.profile || "__none__";

    if (!byYear.has(yearKey)) byYear.set(yearKey, new Map());
    const profiles = byYear.get(yearKey)!;
    if (!profiles.has(profileKey)) profiles.set(profileKey, []);
    profiles.get(profileKey)!.push(s);
  }

  // Sort years descending (nulls last)
  const sortedYears = [...byYear.keys()].sort((a, b) => {
    if (a === "__none__") return 1;
    if (b === "__none__") return -1;
    return Number(b) - Number(a);
  });

  return sortedYears.map((yearKey) => {
    const profileMap = byYear.get(yearKey)!;
    const profileKeys = [...profileMap.keys()].sort((a, b) => {
      if (a === "__none__") return 1;
      if (b === "__none__") return -1;
      return a.localeCompare(b);
    });

    return {
      year: yearKey === "__none__" ? null : Number(yearKey),
      profileGroups: profileKeys.map((pk) => ({
        profile: pk === "__none__" ? null : pk,
        sources: profileMap.get(pk)!,
      })),
    };
  });
}

const SourceList: React.FC<SourceListProps> = ({ refreshKey }) => {
  const [sources, setSources] = useState<Source[]>([]);
  const [statsById, setStatsById] = useState<Record<string, SourceStats>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [collapsedYears, setCollapsedYears] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.get<Source[]>("/sources/");
        const src = Array.isArray(response.data) ? response.data : [];
        setSources(src);

        const statsResults = await Promise.all(
          src.map(async (s) => {
            try {
              const r = await api.get<SourceStats>(`/sources/${s.id}/stats`);
              return r.data;
            } catch {
              return { source_id: s.id, segments_count: 0, exercises_count: 0, tags_count: 0 } as SourceStats;
            }
          })
        );
        const map: Record<string, SourceStats> = {};
        for (const st of statsResults) map[st.source_id] = st;
        setStatsById(map);
      } catch (err) {
        setError("Eroare la preluarea surselor.");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [refreshKey]);

  const uniqueTypes = useMemo(
    () => [...new Set(sources.map((s) => s.type))],
    [sources]
  );

  const filtered = useMemo(() => {
    return sources.filter((s) => {
      const matchSearch = s.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchType = selectedType === "all" || s.type === selectedType;
      return matchSearch && matchType;
    });
  }, [sources, searchTerm, selectedType]);

  const groups = useMemo(() => buildGroups(filtered), [filtered]);

  const toggleYear = (yearKey: string) => {
    setCollapsedYears((prev) => {
      const next = new Set(prev);
      if (next.has(yearKey)) next.delete(yearKey);
      else next.add(yearKey);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="source-list-card">
        <div className="loading-state">
          <div className="loading-spinner" />
          <p>Se încarcă sursele…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="source-list-card">
        <div className="error-state">
          <h3>Eroare de conexiune</h3>
          <p>{error}</p>
          <button className="retry-button" onClick={() => window.location.reload()}>Reîncearcă</button>
        </div>
      </div>
    );
  }

  return (
    <div className="source-list-card">
      <div className="source-list-header">
        <div className="header-title">
          <h2>Surse</h2>
          <span className="source-count">{sources.length} total</span>
        </div>

        <div className="filters">
          <div className="search-box">
            <input
              type="text"
              placeholder="Caută surse…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select className="type-filter" value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
            <option value="all">Toate tipurile</option>
            {uniqueTypes.map((type) => (
              <option key={type} value={type}>{type.charAt(0).toUpperCase() + type.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <h3>{searchTerm || selectedType !== "all" ? "Niciun rezultat găsit" : "Nu există surse încă"}</h3>
          <p>{searchTerm || selectedType !== "all" ? "Schimbă criteriile de căutare." : "Importă/încarcă o sursă ca să apară aici."}</p>
        </div>
      ) : (
        <div className="source-groups">
          {groups.map((yg) => {
            const yearKey = yg.year !== null ? String(yg.year) : "__none__";
            const isCollapsed = collapsedYears.has(yearKey);
            const totalInYear = yg.profileGroups.reduce((acc, pg) => acc + pg.sources.length, 0);

            return (
              <div key={yearKey} className="year-group">
                <button className="year-group-header" onClick={() => toggleYear(yearKey)}>
                  <div className="year-group-left">
                    {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                    <span className="year-group-title">
                      {yg.year !== null ? yg.year : "An nespecificat"}
                    </span>
                    <span className="year-group-count">{totalInYear} surse</span>
                  </div>
                </button>

                {!isCollapsed && (
                  <div className="year-group-body">
                    {yg.profileGroups.map((pg) => (
                      <div key={pg.profile ?? "__none__"} className="profile-group">
                        {pg.profile && (
                          <div className="profile-group-label">
                            <FileText size={13} />
                            {PROFILE_LABELS[pg.profile] ?? pg.profile}
                          </div>
                        )}
                        <div className="profile-group-sources">
                          {pg.sources.map((s) => (
                            <SourceRow key={s.id} source={s} stats={statsById[s.id]} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="table-footer">
        <span>Afișate {filtered.length} din {sources.length}</span>
      </div>
    </div>
  );
};

export default SourceList;
