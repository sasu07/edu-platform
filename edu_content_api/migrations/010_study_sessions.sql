-- Migration 010: Study sessions + weekly study plan

CREATE TABLE IF NOT EXISTS study_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Tipul sesiunii
    session_type VARCHAR(20) NOT NULL DEFAULT 'test_scurt',  -- 'test_scurt' | 'test_bac'

    -- Filtrele folosite la generare
    filters JSONB NOT NULL DEFAULT '{}',

    -- Setul de exerciții generat
    exercise_set_id UUID REFERENCES user_exercise_sets(id) ON DELETE SET NULL,

    -- Status sesiune
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active' | 'completed' | 'abandoned'

    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_sec INTEGER,  -- secunde reale petrecute

    -- Statistici finale
    exercises_total INTEGER NOT NULL DEFAULT 0,
    exercises_completed INTEGER NOT NULL DEFAULT 0,
    avg_difficulty NUMERIC(4,2),
    xp_gained INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS study_plan_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,   -- elevul
    plan_date DATE NOT NULL,                                         -- ziua planificată
    session_type VARCHAR(20) NOT NULL DEFAULT 'test_scurt',         -- 'test_scurt' | 'test_bac'
    filters JSONB NOT NULL DEFAULT '{}',
    note TEXT,

    -- Cine a creat
    created_by VARCHAR(20) NOT NULL DEFAULT 'student',  -- 'student' | 'teacher'
    teacher_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Legătura cu sesiunea efectivă (se completează când elevul o face)
    session_id UUID REFERENCES study_sessions(id) ON DELETE SET NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_study_sessions_user ON study_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_status ON study_sessions(status);
CREATE INDEX IF NOT EXISTS idx_study_plan_user_date ON study_plan_days(user_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_study_plan_teacher ON study_plan_days(teacher_id);
