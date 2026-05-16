import { useEffect, useMemo, useState } from 'react';
import {
  createTeacherClass,
  createWeeklyClassChallenge,
  getLeagueOverview,
  getStudentLeagueClasses,
  getTeacherClasses,
  joinLeagueClass,
  updateLeagueMembership,
  type LeagueClass,
  type LeagueOverview,
} from '../api';
import { useAuth } from '../AuthContext';
import './LeagueHub.css';

function formatWeekLabel(start: string, end: string) {
  const startDate = new Date(`${start}T12:00:00`);
  const endDate = new Date(`${end}T12:00:00`);
  return `${startDate.toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })} - ${endDate.toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}`;
}

function subiectLabel(filters: Record<string, any>) {
  const value = filters?.subiect_tag;
  return value ? `Subiectul ${value}` : 'Toate subiectele';
}

function Leaderboard({ overview }: { overview: LeagueOverview | null }) {
  if (!overview) return null;

  return (
    <div className="league-card">
      <div className="league-card-kicker">Clasament săptămânal</div>
      <div className="league-card-title">Clasa mea</div>
      <div className="league-week-label">Săptămâna {formatWeekLabel(overview.week.start, overview.week.end)}</div>
      <div className="league-leaderboard">
        {overview.leaderboard.map((entry) => (
          <div key={entry.student_id} className={`league-row${entry.is_you ? ' you' : ''}`}>
            <div className="league-rank">#{entry.rank}</div>
            <div className="league-name">{entry.display_name}</div>
            <div className="league-xp">{entry.xp_week} XP</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Challenges({ overview }: { overview: LeagueOverview | null }) {
  if (!overview) return null;

  return (
    <div className="league-card">
      <div className="league-card-kicker">Provocări săptămânale</div>
      <div className="league-card-title">Ce se joacă săptămâna asta</div>
      {overview.challenges.length === 0 ? (
        <div className="league-empty-note">Profesorul nu a lansat încă o provocare pentru săptămâna aceasta.</div>
      ) : (
        <div className="league-challenges">
          {overview.challenges.map((challenge) => {
            const myProgress = challenge.participant_progress.find((item) => item.is_you);
            return (
              <div key={challenge.id} className="league-challenge">
                <div className="league-challenge-head">
                  <div>
                    <div className="league-challenge-title">{challenge.title}</div>
                    <div className="league-challenge-meta">
                      Țintă: {challenge.target_count} exerciții · {subiectLabel(challenge.filters)}
                    </div>
                  </div>
                  {myProgress && (
                    <div className={`league-challenge-status${myProgress.completed ? ' done' : ''}`}>
                      {myProgress.completed ? 'Completat' : `${myProgress.progress_count}/${challenge.target_count}`}
                    </div>
                  )}
                </div>
                {challenge.description && <div className="league-challenge-desc">{challenge.description}</div>}
                <div className="league-progress-list">
                  {challenge.participant_progress.map((item) => (
                    <div key={item.student_id} className={`league-progress-row${item.is_you ? ' you' : ''}`}>
                      <span>{item.display_name}</span>
                      <span>{item.completed ? '✓' : `${item.progress_count}/${challenge.target_count}`}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StudentLeague() {
  const [classes, setClasses] = useState<LeagueClass[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [overview, setOverview] = useState<LeagueOverview | null>(null);
  const [joinCode, setJoinCode] = useState('');
  const [pseudonym, setPseudonym] = useState('');
  const [anonymous, setAnonymous] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [error, setError] = useState('');

  const loadClasses = async () => {
    const res = await getStudentLeagueClasses();
    const items = Array.isArray(res.data) ? res.data : [];
    setClasses(items);
    setSelectedClassId((current) => current || items[0]?.id || '');
    return items;
  };

  const loadOverview = async (classId: string) => {
    if (!classId) {
      setOverview(null);
      return;
    }
    const res = await getLeagueOverview(classId);
    setOverview(res.data);
  };

  useEffect(() => {
    loadClasses().catch(() => setClasses([]));
  }, []);

  useEffect(() => {
    loadOverview(selectedClassId).catch(() => setOverview(null));
  }, [selectedClassId]);

  const selectedClass = useMemo(
    () => classes.find((item) => item.id === selectedClassId) || null,
    [classes, selectedClassId],
  );

  const handleJoin = async () => {
    setError('');
    try {
      await joinLeagueClass({ class_code: joinCode, pseudonym, is_anonymous: anonymous });
      const items = await loadClasses();
      const joined = items.find((item) => item.class_code.toUpperCase() === joinCode.trim().toUpperCase());
      setSelectedClassId(joined?.id || items[0]?.id || '');
      setJoinCode('');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Nu am reușit să te alătur clasei.');
    }
  };

  const handleProfileSave = async () => {
    if (!selectedClassId) return;
    setSavingProfile(true);
    setError('');
    try {
      await updateLeagueMembership(selectedClassId, { pseudonym, is_anonymous: anonymous });
      await loadOverview(selectedClassId);
      await loadClasses();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Nu am reușit să salvez setările tale.');
    } finally {
      setSavingProfile(false);
    }
  };

  useEffect(() => {
    if (overview?.my_membership) {
      setPseudonym(overview.my_membership.pseudonym || '');
      setAnonymous(overview.my_membership.is_anonymous);
    }
  }, [overview?.my_membership]);

  return (
    <div className="league-page">
      <div className="league-hero">
        <div>
          <div className="league-hero-kicker">Liga BAC</div>
          <h1>Joacă săptămâna asta în clasa ta</h1>
          <p>Intri cu codul dat de profesor, vezi clasamentul săptămânal și urmărești provocările fără presiune inutilă.</p>
        </div>
        <div className="league-join-box">
          <div className="league-join-title">Alătură-te unei clase</div>
          <input className="league-input" placeholder="Cod de clasă" value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} />
          <input className="league-input" placeholder="Pseudonim opțional" value={pseudonym} onChange={(e) => setPseudonym(e.target.value)} />
          <label className="league-checkbox">
            <input type="checkbox" checked={anonymous} onChange={(e) => setAnonymous(e.target.checked)} />
            Vreau să apar cu pseudonim în clasament
          </label>
          {error && <div className="league-error">{error}</div>}
          <button className="league-primary-btn" onClick={handleJoin} disabled={!joinCode.trim()}>
            Intră în clasă
          </button>
        </div>
      </div>

      {classes.length > 0 && (
        <>
          <div className="league-class-tabs">
            {classes.map((item) => (
              <button
                key={item.id}
                className={`league-class-tab${selectedClassId === item.id ? ' active' : ''}`}
                onClick={() => setSelectedClassId(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>

          {selectedClass && (
            <div className="league-class-meta">
              <span>Profesor: {selectedClass.teacher_name}</span>
              <span>Cod: {selectedClass.class_code}</span>
            </div>
          )}

          <div className="league-grid">
            <Leaderboard overview={overview} />
            <div className="league-card">
              <div className="league-card-kicker">Setările tale</div>
              <div className="league-card-title">Cum apari în clasă</div>
              <input className="league-input" placeholder="Pseudonim" value={pseudonym} onChange={(e) => setPseudonym(e.target.value)} />
              <label className="league-checkbox">
                <input
                  type="checkbox"
                  checked={anonymous}
                  disabled={overview?.class_info.allow_anonymous === false}
                  onChange={(e) => setAnonymous(e.target.checked)}
                />
                Arată-mi pseudonimul în leaderboard
              </label>
              <button className="league-secondary-btn" onClick={handleProfileSave} disabled={savingProfile || !selectedClassId}>
                {savingProfile ? 'Se salvează...' : 'Salvează'}
              </button>
            </div>
          </div>

          <Challenges overview={overview} />
        </>
      )}

      {classes.length === 0 && (
        <div className="league-empty-state">
          Intră prima dată într-o clasă cu codul primit de la profesor și aici vei vedea imediat clasamentul și provocările săptămânale.
        </div>
      )}
    </div>
  );
}

function TeacherLeague() {
  const [classes, setClasses] = useState<LeagueClass[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [overview, setOverview] = useState<LeagueOverview | null>(null);
  const [className, setClassName] = useState('');
  const [allowAnonymous, setAllowAnonymous] = useState(true);
  const [challengeTitle, setChallengeTitle] = useState('');
  const [challengeDescription, setChallengeDescription] = useState('');
  const [challengeTarget, setChallengeTarget] = useState(10);
  const [challengeSubiect, setChallengeSubiect] = useState('1');
  const [error, setError] = useState('');

  const loadClasses = async () => {
    const res = await getTeacherClasses();
    const items = Array.isArray(res.data) ? res.data : [];
    setClasses(items);
    setSelectedClassId((current) => current || items[0]?.id || '');
  };

  const loadOverview = async (classId: string) => {
    if (!classId) {
      setOverview(null);
      return;
    }
    const res = await getLeagueOverview(classId);
    setOverview(res.data);
  };

  useEffect(() => {
    loadClasses().catch(() => setClasses([]));
  }, []);

  useEffect(() => {
    loadOverview(selectedClassId).catch(() => setOverview(null));
  }, [selectedClassId]);

  const handleCreateClass = async () => {
    setError('');
    try {
      await createTeacherClass({ name: className, allow_anonymous: allowAnonymous });
      setClassName('');
      await loadClasses();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Nu am reușit să creez clasa.');
    }
  };

  const handleCreateChallenge = async () => {
    if (!selectedClassId) return;
    setError('');
    try {
      await createWeeklyClassChallenge(selectedClassId, {
        title: challengeTitle,
        description: challengeDescription,
        target_count: challengeTarget,
        subiect_tag: challengeSubiect,
      });
      setChallengeTitle('');
      setChallengeDescription('');
      await loadOverview(selectedClassId);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Nu am reușit să creez provocarea.');
    }
  };

  return (
    <div className="league-page">
      <div className="league-hero teacher">
        <div>
          <div className="league-hero-kicker">Liga BAC</div>
          <h1>Construiește competiție sănătoasă în clasă</h1>
          <p>Creezi clasa, dai codul elevilor și lansezi provocări săptămânale care țin ritmul viu.</p>
        </div>
        <div className="league-join-box">
          <div className="league-join-title">Creează o clasă</div>
          <input className="league-input" placeholder="Ex: 12B Mate-Info" value={className} onChange={(e) => setClassName(e.target.value)} />
          <label className="league-checkbox">
            <input type="checkbox" checked={allowAnonymous} onChange={(e) => setAllowAnonymous(e.target.checked)} />
            Permite pseudonime în clasament
          </label>
          {error && <div className="league-error">{error}</div>}
          <button className="league-primary-btn" onClick={handleCreateClass} disabled={!className.trim()}>
            Creează clasa
          </button>
        </div>
      </div>

      {classes.length > 0 && (
        <>
          <div className="league-class-tabs">
            {classes.map((item) => (
              <button
                key={item.id}
                className={`league-class-tab${selectedClassId === item.id ? ' active' : ''}`}
                onClick={() => setSelectedClassId(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>

          {overview && (
            <div className="league-class-meta">
              <span>Cod de clasă: <strong>{overview.class_info.class_code}</strong></span>
              <span>{overview.class_info.member_count} elevi în clasă</span>
            </div>
          )}

          <div className="league-grid">
            <Leaderboard overview={overview} />
            <div className="league-card">
              <div className="league-card-kicker">Provocare nouă</div>
              <div className="league-card-title">Lansează provocarea săptămânii</div>
              <input className="league-input" placeholder="Ex: Rezolvă 10 exerciții S1" value={challengeTitle} onChange={(e) => setChallengeTitle(e.target.value)} />
              <textarea className="league-textarea" placeholder="Descriere opțională" value={challengeDescription} onChange={(e) => setChallengeDescription(e.target.value)} rows={3} />
              <div className="league-form-row">
                <input className="league-input" type="number" min={1} max={100} value={challengeTarget} onChange={(e) => setChallengeTarget(Number(e.target.value) || 1)} />
                <select className="league-input" value={challengeSubiect} onChange={(e) => setChallengeSubiect(e.target.value)}>
                  <option value="1">Subiectul I</option>
                  <option value="2">Subiectul II</option>
                  <option value="3">Subiectul III</option>
                </select>
              </div>
              <button className="league-secondary-btn" onClick={handleCreateChallenge} disabled={!selectedClassId || !challengeTitle.trim()}>
                Publică provocarea
              </button>
            </div>
          </div>

          <Challenges overview={overview} />
        </>
      )}

      {classes.length === 0 && (
        <div className="league-empty-state">
          Creează prima clasă și platforma îți generează instant un cod pe care îl poți da elevilor.
        </div>
      )}
    </div>
  );
}

export default function LeagueHub() {
  const { isTeacher, isAdmin } = useAuth();
  return isTeacher || isAdmin ? <TeacherLeague /> : <StudentLeague />;
}
