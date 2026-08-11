-- Conturile create prin invitație rămân retrimisibile și după expirarea
-- primului link. Un token invite nefolosit indică faptul că parola nu a fost
-- configurată niciodată; tokenurile folosite nu reactivează conturi.

UPDATE users u
SET invite_pending = TRUE
WHERE u.is_active = FALSE
  AND u.invite_pending = FALSE
  AND EXISTS (
      SELECT 1
      FROM password_reset_tokens prt
      WHERE prt.user_id = u.id
        AND prt.purpose = 'invite'
        AND prt.used_at IS NULL
  );
