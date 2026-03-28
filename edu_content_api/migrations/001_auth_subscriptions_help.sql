-- Migration 001: Auth, Subscriptions, Help Requests
-- Run once against the database

-- USERS (DROP dacă există cu schemă incompatibilă, recreează)
DROP TABLE IF EXISTS users CASCADE;
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'student',  -- student | teacher | admin
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- SUBSCRIPTIONS
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_type VARCHAR(50) NOT NULL DEFAULT 'free',       -- free | premium
    status VARCHAR(50) NOT NULL DEFAULT 'active',        -- active | expired | cancelled
    expires_at TIMESTAMP,                                -- NULL = fără expirare
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);

-- HELP REQUESTS (flag-uri de la studenți)
CREATE TABLE IF NOT EXISTS help_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    flag_type VARCHAR(50) NOT NULL,                      -- WRITTEN | VIDEO | LIVE
    status VARCHAR(50) NOT NULL DEFAULT 'pending',       -- pending | assigned | resolved
    notes TEXT,
    assigned_teacher_id UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_help_requests_student_id ON help_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_help_requests_status ON help_requests(status);
CREATE INDEX IF NOT EXISTS idx_help_requests_teacher_id ON help_requests(assigned_teacher_id);

-- HELP RESPONSES (răspunsuri de la profesori)
CREATE TABLE IF NOT EXISTS help_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES help_requests(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES users(id),
    content_text TEXT,                                   -- pentru WRITTEN
    video_path VARCHAR(512),                             -- pentru VIDEO (cale locală)
    zoom_link VARCHAR(512),                              -- pentru LIVE
    scheduled_at TIMESTAMP,                              -- pentru LIVE (ora programată)
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_help_responses_request_id ON help_responses(request_id);

-- STUDENT PROGRESS
CREATE TABLE IF NOT EXISTS student_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, exercise_id)
);

CREATE INDEX IF NOT EXISTS idx_student_progress_student_id ON student_progress(student_id);
