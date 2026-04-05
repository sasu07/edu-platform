-- Migration 009: Teacher file upload + assignment tracking for submissions

ALTER TABLE exercise_submissions
ADD COLUMN IF NOT EXISTS teacher_file_path VARCHAR(512),
ADD COLUMN IF NOT EXISTS assigned_teacher_id UUID REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_submissions_assigned ON exercise_submissions(assigned_teacher_id);
