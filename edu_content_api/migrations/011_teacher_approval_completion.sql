-- Migration 011: Teacher approval required for exercise completion
-- Reset all student progress; add live help scheduling support

-- 1. Reset all student progress (clean slate)
TRUNCATE student_progress;

-- 2. Reset all submissions to pending (remove any 'correct'/'incorrect' markers)
UPDATE exercise_submissions SET teacher_status = 'pending', reviewed_by = NULL, reviewed_at = NULL,
    xp_self_eval = 0, xp_photo = 0, xp_teacher = 0;

-- 3. Reset all gamification XP (optional: comment out if you want to keep existing XP)
UPDATE student_gamification SET xp_total = 0, streak_current = 0, streak_max = 0;
DELETE FROM student_badges;
DELETE FROM xp_log;

-- 4. Add scheduled_at and zoom_link to help_requests for live session scheduling
ALTER TABLE help_requests
    ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS zoom_link VARCHAR(512),
    ADD COLUMN IF NOT EXISTS scheduled_by UUID REFERENCES users(id);

-- 5. Add 'live_session' as allowed session_type (VARCHAR, no constraint change needed)
-- study_plan_days.session_type is VARCHAR, so 'live_session' is already valid

-- 6. Add index for pending submissions lookup
CREATE INDEX IF NOT EXISTS idx_submissions_pending ON exercise_submissions(user_id, teacher_status);
