-- Migration 002: School teacher role, variant fingerprint, variant ownership

-- Fingerprint pe variante (hash din exercițiile selectate)
ALTER TABLE variants ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64);
ALTER TABLE variants ADD COLUMN IF NOT EXISTS created_by_user_id_fk UUID REFERENCES users(id);

-- Index unic: același user nu poate genera aceeași variantă de două ori
CREATE UNIQUE INDEX IF NOT EXISTS idx_variants_user_fingerprint
    ON variants(created_by_user_id_fk, fingerprint)
    WHERE fingerprint IS NOT NULL AND created_by_user_id_fk IS NOT NULL;

-- Contor variante generate per user per lună (pentru limita free school_teacher)
-- Se calculează din tabelul variants, nu necesită tabel separat

-- Notificări pentru studenți (când vine un răspuns)
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,          -- 'help_response', 'variant_ready'
    title VARCHAR(255) NOT NULL,
    body TEXT,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    related_id UUID,                    -- help_request_id sau variant_id
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;
