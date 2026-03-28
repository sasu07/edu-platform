-- Migration 003: Generation limits tracking
-- Tracks exercise generation events per user for monthly quota enforcement

CREATE TABLE IF NOT EXISTS exercise_generation_logs (
    id         UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exgen_logs_user_month
    ON exercise_generation_logs (user_id, created_at);
