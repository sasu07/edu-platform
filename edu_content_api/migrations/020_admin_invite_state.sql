-- Distinge invitațiile în așteptare de conturile dezactivate intenționat.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS invite_pending BOOLEAN NOT NULL DEFAULT FALSE;

-- Păstrează funcționale invitațiile emise înainte de această migrare.
UPDATE users u
SET invite_pending = TRUE
WHERE u.is_active = FALSE
  AND EXISTS (
      SELECT 1
      FROM password_reset_tokens prt
      WHERE prt.user_id = u.id
        AND prt.purpose = 'invite'
        AND prt.used_at IS NULL
  );
