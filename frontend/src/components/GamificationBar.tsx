import { useEffect, useState } from 'react';
import { getMyGamification, type GamificationProfile, type GamificationBadge } from '../api';
import './GamificationBar.css';

interface XPToastProps {
  xp: number;
  badges: string[];
  onDone: () => void;
}

export function XPToast({ xp, badges, onDone }: XPToastProps) {
  useEffect(() => {
    const t = setTimeout(onDone, 2800);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <div className="xp-toast">
      {xp > 0 && <div className="xp-toast-xp">+{xp} XP</div>}
      {badges.map(b => (
        <div key={b} className="xp-toast-badge">🏅 Insignă nouă!</div>
      ))}
    </div>
  );
}

function BadgeModal({ badges, onClose }: { badges: GamificationBadge[]; onClose: () => void }) {
  return (
    <div className="gam-modal-overlay" onClick={onClose}>
      <div className="gam-modal" onClick={e => e.stopPropagation()}>
        <div className="gam-modal-header">
          <span>Insignele mele</span>
          <button className="gam-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="gam-modal-badges">
          {badges.length === 0 && (
            <div className="gam-modal-empty">Rezolvă exerciții pentru a câștiga insigne!</div>
          )}
          {badges.map(b => (
            <div key={b.key} className="gam-modal-badge-item">
              <span className="gam-modal-badge-icon">{b.icon}</span>
              <div>
                <div className="gam-modal-badge-label">{b.label}</div>
                <div className="gam-modal-badge-desc">{b.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface GamificationBarProps {
  refreshTrigger?: number;
}

export default function GamificationBar({ refreshTrigger = 0 }: GamificationBarProps) {
  const [profile, setProfile] = useState<GamificationProfile | null>(null);
  const [showBadges, setShowBadges] = useState(false);

  useEffect(() => {
    getMyGamification()
      .then(r => setProfile(r.data))
      .catch(() => {});
  }, [refreshTrigger]);

  if (!profile) return null;

  const { level, streak_current, xp_total, badges } = profile;

  return (
    <>
      <div className="gam-bar">
        {/* Nivel */}
        <div className="gam-level">
          <span className="gam-level-icon">{level.icon}</span>
          <div className="gam-level-info">
            <span className="gam-level-name">{level.name}</span>
            <div className="gam-xp-bar-wrap">
              <div className="gam-xp-bar" style={{ width: `${level.progress_pct}%` }} />
            </div>
          </div>
          <span className="gam-xp-label">
            {level.is_max ? `${xp_total} XP` : `${level.xp_in_level}/${level.xp_for_next} XP`}
          </span>
        </div>

        {/* Streak */}
        <div className="gam-streak" title={`Record: ${profile.streak_max} zile`}>
          <span className="gam-streak-fire">{streak_current >= 3 ? '🔥' : '❄️'}</span>
          <div className="gam-streak-info">
            <span className="gam-streak-val">{streak_current}</span>
            <span className="gam-streak-label">zile</span>
          </div>
        </div>

        {/* Insigne */}
        <button className="gam-badges-btn" onClick={() => setShowBadges(true)} title="Vezi insignele mele">
          🏅 <span className="gam-badges-count">{badges.length}</span>
        </button>
      </div>

      {showBadges && <BadgeModal badges={badges} onClose={() => setShowBadges(false)} />}
    </>
  );
}
