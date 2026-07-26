-- Migration 017: Audit trail — jurnal de securitate/business.
-- Cine, ce, când, pe ce resursă. Populat de middleware (toate mutațiile + 401/403)
-- și de evenimente explicite (login, register, access denied).

CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_user_id UUID,                    -- cine (NULL = anonim / login eșuat)
    actor_role    VARCHAR(20),
    action        VARCHAR(80) NOT NULL,    -- ex: 'login.fail', 'DELETE /exercises/:id'
    method        VARCHAR(8),
    path          TEXT,
    resource_type VARCHAR(40),
    resource_id   VARCHAR(64),
    ip            VARCHAR(64),
    user_agent    TEXT,
    status        INTEGER,                 -- codul HTTP / rezultatul
    details       JSONB                    -- context suplimentar (ex: email încercat)
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor   ON audit_log (actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action  ON audit_log (action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_status  ON audit_log (status, created_at DESC);

-- Retenție: șterge periodic înregistrările vechi (rulează manual sau dintr-un cron):
--   DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL '180 days';
