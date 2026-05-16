-- Migration 013: numeric answer cache for automatic checking

ALTER TABLE exercises
ADD COLUMN IF NOT EXISTS answer_numeric_value DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS answer_numeric_expression TEXT;

CREATE INDEX IF NOT EXISTS idx_exercises_answer_numeric_value
ON exercises(answer_numeric_value)
WHERE answer_numeric_value IS NOT NULL;
