-- Migration 004: Exercise set persistence
-- Tracks seen exercises per user, saves generated sets, links sets to subscription plan

-- Tracks all exercises ever shown to a user (prevents repeats)
CREATE TABLE IF NOT EXISTS user_seen_exercises (
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    seen_at    TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    PRIMARY KEY (user_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_seen_ex_user ON user_seen_exercises (user_id);

-- Saved exercise sets per user (one per generation)
CREATE TABLE IF NOT EXISTS user_exercise_sets (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         VARCHAR(255),
    linked_plan  VARCHAR(50),   -- premium_gen, free, etc. — NULL = free user
    filters      JSONB,         -- filters used when generating (for display)
    created_at   TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ex_sets_user ON user_exercise_sets (user_id, created_at DESC);

-- Items inside each saved set (root exercise IDs only — containers + simples)
CREATE TABLE IF NOT EXISTS user_exercise_set_items (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    set_id       UUID NOT NULL REFERENCES user_exercise_sets(id) ON DELETE CASCADE,
    exercise_id  UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    sort_order   INT  DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ex_set_items_set ON user_exercise_set_items (set_id, sort_order);
