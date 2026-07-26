import { useState, useEffect, useMemo } from 'react';
import { FileText, Download, BookOpen, Search, X } from 'lucide-react';
import { getDownloadableSources, buildApiUrl, type DownloadableSource } from '../api';
import './SourceLibrary.css';

const PROFILE_LABELS: Record<string, string> = {
  'mate-info': 'Mate-Info',
  'st-nat': 'Științe ale Naturii',
  'tehnologic': 'Tehnologic',
  'pedagogic': 'Pedagogic',
};

// Descărcare autentificată (token în header) → blob → salvare, fără expunere anonimă.
function downloadFile(url: string, label: string) {
  const token = localStorage.getItem('access_token');
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then((res) => {
      if (!res.ok) throw new Error('indisponibil');
      return res.blob();
    })
    .then((blob) => {
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = label.replace(/[^\w.-]+/g, '_') + '.pdf';
      a.click();
      setTimeout(() => URL.revokeObjectURL(objUrl), 1000);
    })
    .catch(() => alert('Fișierul nu este disponibil pe server.'));
}

export default function SourceLibrary() {
  const [sources, setSources] = useState<DownloadableSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [year, setYear] = useState('');
  const [profile, setProfile] = useState('');
  const [session, setSession] = useState('');

  useEffect(() => {
    getDownloadableSources()
      .then((r) => setSources(Array.isArray(r.data) ? r.data : []))
      .catch(() => setError('Nu s-au putut încărca subiectele.'))
      .finally(() => setLoading(false));
  }, []);

  const years = useMemo(
    () => [...new Set(sources.map((s) => s.year).filter(Boolean))].sort((a, b) => (b as number) - (a as number)),
    [sources],
  );
  const profiles = useMemo(() => [...new Set(sources.map((s) => s.profile).filter(Boolean))].sort(), [sources]);
  const sessions = useMemo(() => [...new Set(sources.map((s) => s.session).filter(Boolean))].sort(), [sources]);

  const filtered = useMemo(
    () =>
      sources.filter((s) => {
        if (year && String(s.year) !== year) return false;
        if (profile && s.profile !== profile) return false;
        if (session && s.session !== session) return false;
        if (q && !s.name.toLowerCase().includes(q.toLowerCase())) return false;
        return true;
      }),
    [sources, year, profile, session, q],
  );

  const hasFilters = !!(q || year || profile || session);
  const resetFilters = () => { setQ(''); setYear(''); setProfile(''); setSession(''); };

  return (
    <div className="lib-wrap">
      <header className="lib-head">
        <h1 className="lib-title"><FileText size={24} /> Subiecte BAC</h1>
        <p className="lib-sub">Subiecte și bareme oficiale — descarcă-le în PDF pentru exersare.</p>
      </header>

      <div className="lib-filters">
        <div className="lib-search">
          <Search size={16} />
          <input placeholder="Caută după nume…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select value={year} onChange={(e) => setYear(e.target.value)}>
          <option value="">Toți anii</option>
          {years.map((y) => <option key={y} value={String(y)}>{y}</option>)}
        </select>
        <select value={profile} onChange={(e) => setProfile(e.target.value)}>
          <option value="">Toate profilurile</option>
          {profiles.map((p) => <option key={p} value={p as string}>{PROFILE_LABELS[p as string] || p}</option>)}
        </select>
        <select value={session} onChange={(e) => setSession(e.target.value)}>
          <option value="">Toate sesiunile</option>
          {sessions.map((s) => <option key={s} value={s as string}>{s}</option>)}
        </select>
        {hasFilters && (
          <button className="lib-reset" onClick={resetFilters}><X size={14} /> Resetează</button>
        )}
      </div>

      {!loading && !error && (
        <div className="lib-count">{filtered.length} {filtered.length === 1 ? 'subiect' : 'subiecte'}</div>
      )}

      {loading ? (
        <div className="lib-loading">Se încarcă subiectele…</div>
      ) : error ? (
        <div className="lib-error">{error}</div>
      ) : filtered.length === 0 ? (
        <div className="lib-empty">Niciun subiect pentru filtrele alese.</div>
      ) : (
        <div className="lib-grid">
          {filtered.map((s) => (
            <div key={s.id} className="lib-card">
              <div className="lib-card-icon"><FileText size={20} /></div>
              <div className="lib-card-body">
                <div className="lib-card-name">{s.name}</div>
                <div className="lib-card-badges">
                  {s.year && <span className="lib-badge">{s.year}</span>}
                  {s.session && <span className="lib-badge">{s.session}</span>}
                  {s.profile && <span className="lib-badge lib-badge-profile">{PROFILE_LABELS[s.profile] || s.profile}</span>}
                </div>
              </div>
              <div className="lib-card-actions">
                <button
                  className="lib-dl lib-dl-primary"
                  onClick={() => downloadFile(buildApiUrl(`/sources/${s.id}/download`), `Subiect_${s.name}`)}
                >
                  <Download size={14} /> Subiect
                </button>
                {s.has_barem && (
                  <button
                    className="lib-dl"
                    onClick={() => downloadFile(buildApiUrl(`/sources/${s.id}/download-barem`), `Barem_${s.name}`)}
                  >
                    <BookOpen size={14} /> Barem
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
