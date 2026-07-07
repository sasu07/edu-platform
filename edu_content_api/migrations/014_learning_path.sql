-- Migration 014: Learning Path — diagnostic test, adaptive plan, spaced repetition

CREATE TABLE IF NOT EXISTS diagnostic_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',   -- active, completed, abandoned
    total_exercises INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    score_pct INTEGER NOT NULL DEFAULT 0,
    weak_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_user ON diagnostic_tests(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS diagnostic_exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES diagnostic_tests(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    subiect_num INTEGER,
    topic_key VARCHAR(100),
    topic_label VARCHAR(200),
    user_answer TEXT,
    is_correct BOOLEAN,
    answered_at TIMESTAMP,
    UNIQUE(test_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_diag_ex_test ON diagnostic_exercises(test_id);

CREATE TABLE IF NOT EXISTS learning_paths (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    diagnostic_test_id UUID REFERENCES diagnostic_tests(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    total_nodes INTEGER NOT NULL DEFAULT 0,
    completed_nodes INTEGER NOT NULL DEFAULT 0,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS learning_path_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path_id UUID NOT NULL REFERENCES learning_paths(id) ON DELETE CASCADE,
    topic_key VARCHAR(100) NOT NULL,
    topic_label VARCHAR(200) NOT NULL,
    subiect_num INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3,    -- 1=very weak, 3=untested, 5=strong
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending, in_progress, mastered
    exercises_seen INTEGER NOT NULL DEFAULT 0,
    exercises_correct INTEGER NOT NULL DEFAULT 0,
    target_exercises INTEGER NOT NULL DEFAULT 8,
    score_pct INTEGER NOT NULL DEFAULT 0,
    diagnostic_score_pct INTEGER,           -- NULL = not tested in diagnostic
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lpn_path ON learning_path_nodes(path_id, sort_order);

CREATE TABLE IF NOT EXISTS spaced_repetition_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    interval_days INTEGER NOT NULL DEFAULT 1,
    repetitions INTEGER NOT NULL DEFAULT 0,
    ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    next_review_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at TIMESTAMP,
    UNIQUE(user_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_sr_user_date ON spaced_repetition_items(user_id, next_review_date);
