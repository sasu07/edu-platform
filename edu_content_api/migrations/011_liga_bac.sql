-- Migration 011: Liga BAC classes, weekly leaderboard, and weekly challenges

CREATE TABLE IF NOT EXISTS class_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    class_code VARCHAR(16) NOT NULL UNIQUE,
    allow_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS class_group_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID NOT NULL REFERENCES class_groups(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pseudonym VARCHAR(80),
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(class_id, student_id)
);

CREATE TABLE IF NOT EXISTS weekly_class_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID NOT NULL REFERENCES class_groups(id) ON DELETE CASCADE,
    title VARCHAR(160) NOT NULL,
    description TEXT,
    target_count INTEGER NOT NULL DEFAULT 1,
    filters JSONB NOT NULL DEFAULT '{}',
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_class_groups_teacher ON class_groups(teacher_id);
CREATE INDEX IF NOT EXISTS idx_class_group_memberships_class ON class_group_memberships(class_id);
CREATE INDEX IF NOT EXISTS idx_class_group_memberships_student ON class_group_memberships(student_id);
CREATE INDEX IF NOT EXISTS idx_weekly_class_challenges_class_week ON weekly_class_challenges(class_id, week_start);
