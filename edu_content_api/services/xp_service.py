from datetime import datetime

from psycopg.rows import dict_row


def calc_base_xp(difficulty: float) -> int:
    """XP de bază recalibrat pe dificultate."""
    d = difficulty or 5
    if d <= 2:
        return 10
    if d <= 4:
        return 20
    if d <= 6:
        return 35
    if d <= 8:
        return 55
    return 80


def award_xp(conn, user_id: str, xp: int, reason: str, ref_id: str | None = None) -> int:
    """Adaugă XP cu cap zilnic de 300. Returnează XP efectiv acordat."""
    if xp <= 0:
        return 0

    today = datetime.now().date()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT COALESCE(SUM(xp_gained),0) as total FROM xp_log WHERE user_id=%s AND DATE(created_at)=%s",
            (user_id, today),
        )
        xp_today = cur.fetchone()["total"]
        xp_allowed = min(xp, max(0, 300 - xp_today))
        if xp_allowed <= 0:
            return 0

        cur.execute(
            """INSERT INTO student_gamification (user_id, xp_total, streak_current, streak_max, last_active_date)
               VALUES (%s, %s, 1, 1, %s)
               ON CONFLICT (user_id) DO UPDATE
               SET xp_total = student_gamification.xp_total + %s,
                   last_active_date = EXCLUDED.last_active_date,
                   updated_at = NOW()""",
            (user_id, xp_allowed, today, xp_allowed),
        )
        cur.execute(
            "INSERT INTO xp_log (user_id, xp_gained, reason, reference_id) VALUES (%s, %s, %s, %s)",
            (user_id, xp_allowed, reason, ref_id),
        )
    return xp_allowed

