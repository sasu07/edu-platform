-- Migration 005: Add profile and barem file path to sources
ALTER TABLE sources ADD COLUMN IF NOT EXISTS profile VARCHAR(100);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS url_barem_path VARCHAR(512);
