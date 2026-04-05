-- Migration 006: Parent-Student relationship + exercise completions via student_progress

-- Tabel legătură părinte-elev
CREATE TABLE IF NOT EXISTS parent_student (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    linked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(parent_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_parent_student_parent ON parent_student(parent_id);
CREATE INDEX IF NOT EXISTS idx_parent_student_student ON parent_student(student_id);

-- student_progress.completed era deja definit în 001, dar asigurăm că există coloana
-- (idempotent: ALTER COLUMN nu schimbă nimic dacă tipul e deja corect)
ALTER TABLE student_progress ADD COLUMN IF NOT EXISTS completed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE student_progress ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;
