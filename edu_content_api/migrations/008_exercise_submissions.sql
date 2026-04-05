-- Migration 008: Exercise submissions cu autoevaluare, foto, corecție profesor

CREATE TABLE IF NOT EXISTS exercise_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,

    -- Autoevaluare
    self_eval VARCHAR(20) NOT NULL DEFAULT 'complete',  -- 'failed' | 'partial' | 'complete'

    -- Foto soluție
    photo_path VARCHAR(512),
    photo_uploaded_at TIMESTAMP,

    -- Corecție profesor
    teacher_status VARCHAR(20) DEFAULT NULL,     -- NULL | 'pending' | 'correct' | 'incorrect'
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    teacher_note TEXT,

    -- XP acordat pe etape
    xp_self_eval INTEGER NOT NULL DEFAULT 0,
    xp_photo INTEGER NOT NULL DEFAULT 0,
    xp_teacher INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_submissions_user ON exercise_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_submissions_exercise ON exercise_submissions(exercise_id);
CREATE INDEX IF NOT EXISTS idx_submissions_teacher_status ON exercise_submissions(teacher_status);
