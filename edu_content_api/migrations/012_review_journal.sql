-- Migration 012: Review journal for unresolved exercises

CREATE TABLE IF NOT EXISTS exercise_review_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    source_reason VARCHAR(30) NOT NULL DEFAULT 'failed',
    fail_count INTEGER NOT NULL DEFAULT 0,
    revisit_count INTEGER NOT NULL DEFAULT 0,
    first_flagged_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_flagged_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP,
    UNIQUE(student_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_review_items_student_status ON exercise_review_items(student_id, status);
CREATE INDEX IF NOT EXISTS idx_review_items_last_flagged ON exercise_review_items(last_flagged_at);
