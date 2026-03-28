import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import "./SourceList.css";

interface Source {
  id: string;
  name: string;
  type: string;
  year: number | null;
  session: string | null;
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

type SortField = "name" | "type" | "year" | "created_at" | "segments" | "exercises" | "tags";
type SortOrder = "asc" | "desc";

const SourceList: React.FC<SourceListProps> = ({ refreshKey }) => {
  const navigate = useNavigate();

  const [sources, setSources] = useState<Source[]>([]);
  const [statsById, setStatsById] = useState<Record<string, SourceStats>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState("");
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [selectedType, setSelectedType] = useState<string>("all");

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.get<Source[]>("/sources/");
        const src = Array.isArray(response.data) ? response.data : [];
        setSources(src);

        // fetch stats in parallel
        const statsResults = await Promise.all(
          src.map(async (s) => {
            try {
              const r = await api.get<SourceStats>(`/sources/${s.id}/stats`);
              return r.data;
            } catch {
              return {
                source_id: s.id,
                segments_count: 0,
                exercises_count: 0,
                tags_count: 0,
              } as SourceStats;
            }
          })
        );

        const map: Record<string, SourceStats> = {};
        for (const st of statsResults) map[st.source_id] = st;
        setStatsById(map);
      } catch (err) {
        setError("Eroare la preluarea surselor. Verificați conexiunea la server.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [refreshKey]);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const uniqueTypes = useMemo(
    () => (Array.isArray(sources) ? [...new Set(sources.map((s) => s.type))] : []),
    [sources]
  );

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("ro-RO", { day: "2-digit", month: "short", year: "numeric" });
  };

  const getTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case "pdf":
        return "type-pdf";
      case "oficial":
        return "type-oficial";
      case "culegere":
        return "type-culegere";
      default:
        return "type-default";
    }
  };

  const filteredAndSortedSources = useMemo(() => {
    const list = Array.isArray(sources) ? sources : [];
    const filtered = list.filter((source) => {
      const matchesSearch = source.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesType = selectedType === "all" || source.type === selectedType;
      return matchesSearch && matchesType;
    });

    const getStat = (id: string) => statsById[id] ?? { segments_count: 0, exercises_count: 0, tags_count: 0 };

    const sorted = filtered.sort((a, b) => {
      const sa = getStat(a.id);
      const sb = getStat(b.id);
      let cmp = 0;

      switch (sortField) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "type":
          cmp = a.type.localeCompare(b.type);
          break;
        case "year":
          cmp = (a.year || 0) - (b.year || 0);
          break;
        case "created_at":
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case "segments":
          cmp = sa.segments_count - sb.segments_count;
          break;
        case "exercises":
          cmp = sa.exercises_count - sb.exercises_count;
          break;
        case "tags":
          cmp = sa.tags_count - sb.tags_count;
          break;
      }
      return sortOrder === "asc" ? cmp : -cmp;
    });

    return sorted;
  }, [sources, statsById, searchTerm, selectedType, sortField, sortOrder]);

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
          <button className="retry-button" onClick={() => window.location.reload()}>
            Reîncearcă
          </button>
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
              <option key={type} value={type}>
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {filteredAndSortedSources.length === 0 ? (
        <div className="empty-state">
          <h3>{searchTerm || selectedType !== "all" ? "Niciun rezultat găsit" : "Nu există surse încă"}</h3>
          <p>{searchTerm || selectedType !== "all" ? "Schimbă criteriile de căutare." : "Importă/încarcă o sursă ca să apară aici."}</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="source-table">
            <thead>
              <tr>
                <th onClick={() => handleSort("name")} className="sortable">Nume</th>
                <th onClick={() => handleSort("type")} className="sortable">Tip</th>
                <th onClick={() => handleSort("year")} className="sortable">An</th>
                <th onClick={() => handleSort("segments")} className="sortable">Segmente</th>
                <th onClick={() => handleSort("exercises")} className="sortable">Exerciții</th>
                <th onClick={() => handleSort("tags")} className="sortable">Tag-uri</th>
                <th onClick={() => handleSort("created_at")} className="sortable">Creat</th>
                <th>Detalii</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedSources.map((source) => {
                const st = statsById[source.id] ?? { segments_count: 0, exercises_count: 0, tags_count: 0 };
                return (
                  <tr key={source.id}>
                    <td>
                      <div className="source-name">
                        <div className="source-avatar">{source.name.charAt(0).toUpperCase()}</div>
                        <div className="source-name-text">
                          <span className="name-primary">{source.name}</span>
                          <span className="name-secondary">ID: {source.id.substring(0, 8)}…</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`type-badge ${getTypeColor(source.type)}`}>{source.type}</span>
                    </td>
                    <td><span className="year-text">{source.year || "—"}</span></td>
                    <td><span className="kpi">{st.segments_count}</span></td>
                    <td><span className="kpi">{st.exercises_count}</span></td>
                    <td><span className="kpi">{st.tags_count}</span></td>
                    <td><span className="date-text">{formatDate(source.created_at)}</span></td>
                    <td>
                      <button
                        className="details-btn"
                        onClick={() => navigate(`/app/content/sources/${source.id}`)}
                      >
                        Vezi
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {filteredAndSortedSources.length > 0 && (
        <div className="table-footer">
          <span>
            Afișate {filteredAndSortedSources.length} din {sources.length}
          </span>
        </div>
      )}
    </div>
  );
};

export default SourceList;