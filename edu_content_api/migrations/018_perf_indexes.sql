-- Migration 018: indexuri de performanță pentru zona de conținut.
-- Join-urile pe tag_id și pe exercise_source_segments erau nescanate → lente
-- la 5000+ exerciții / 49000+ tag-uri. Aceste indexuri accelerează:
--   • filtrarea/afișarea pe tag-uri
--   • statisticile pe sursă (câte exerciții/tag-uri per sursă)

CREATE INDEX IF NOT EXISTS idx_exercise_tags_tag       ON exercise_tags (tag_id);
CREATE INDEX IF NOT EXISTS idx_ess_exercise            ON exercise_source_segments (exercise_id);
CREATE INDEX IF NOT EXISTS idx_ess_segment             ON exercise_source_segments (source_segment_id);
