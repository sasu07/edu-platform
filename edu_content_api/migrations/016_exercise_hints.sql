-- Migration 016: Indicii progresive per exercițiu (cache generare AI)
-- Indiciile se generează o singură dată per exercițiu (din enunț + soluție)
-- și se refolosesc pentru toți elevii, deci costul AI e mărginit de numărul
-- de exerciții, nu de numărul de accesări.

CREATE TABLE IF NOT EXISTS exercise_hints (
    exercise_id UUID PRIMARY KEY REFERENCES exercises(id) ON DELETE CASCADE,
    hints       JSONB NOT NULL,                    -- ["indiciu 1", "indiciu 2", ...] ordonate progresiv
    source      VARCHAR(20) NOT NULL DEFAULT 'ai', -- 'ai' | 'manual' | 'fallback'
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
