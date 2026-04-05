-- Migration 007: Gamification — XP, streak, badges

-- Progresul gamification al fiecărui utilizator
CREATE TABLE IF NOT EXISTS student_gamification (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    xp_total INTEGER NOT NULL DEFAULT 0,
    streak_current INTEGER NOT NULL DEFAULT 0,
    streak_max INTEGER NOT NULL DEFAULT 0,
    last_active_date DATE,                      -- ultima zi în care a rezolvat ceva
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insigne câștigate
CREATE TABLE IF NOT EXISTS student_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_key VARCHAR(100) NOT NULL,            -- ex: "streak_5", "first_s3", "exercises_100"
    earned_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, badge_key)
);

CREATE INDEX IF NOT EXISTS idx_student_badges_user ON student_badges(user_id);

-- Log XP per eveniment (pentru audit + grafice)
CREATE TABLE IF NOT EXISTS xp_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    xp_gained INTEGER NOT NULL,
    reason VARCHAR(100) NOT NULL,               -- "exercise_completed", "streak_bonus", "session_completed"
    reference_id UUID,                          -- exercise_id sau session_id
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_xp_log_user ON xp_log(user_id);
