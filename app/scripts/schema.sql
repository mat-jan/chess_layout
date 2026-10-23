-- ♟ Turniej Szachowy — schemat PostgreSQL
-- Uruchom: psql -U chess -d chess_db -f schema.sql

-- ─── UŻYTKOWNICY ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'teacher'
                  CHECK (role IN ('teacher', 'superadmin')),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── UCZESTNICY ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS participants (
    id         SERIAL PRIMARY KEY,
    imie       VARCHAR(100) NOT NULL,
    klasa      VARCHAR(20)  NOT NULL,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── PARY ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pairs (
    id           SERIAL PRIMARY KEY,
    round_number INTEGER      NOT NULL,
    white_id     INTEGER      NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    black_id     INTEGER               REFERENCES participants(id) ON DELETE CASCADE,
    result       VARCHAR(20)  NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── INDEKSY ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pairs_round ON pairs(round_number);
CREATE INDEX IF NOT EXISTS idx_pairs_white ON pairs(white_id);
CREATE INDEX IF NOT EXISTS idx_pairs_black ON pairs(black_id);

-- ─── UNIKALNOŚĆ PAR ──────────────────────────────────────────────────────────
-- Zapobiega podwójnemu wygenerowaniu par dla tej samej rundy (np. dwa kliknięcia
-- "Generuj pary" w tym samym czasie) poprzez wymuszenie unikalności udziału
-- zawodnika w rundzie, niezależnie od tego, czy gra białymi czy czarnymi.
CREATE UNIQUE INDEX IF NOT EXISTS uq_pairs_round_white ON pairs(round_number, white_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pairs_round_black ON pairs(round_number, black_id)
    WHERE black_id IS NOT NULL;

-- ─── SPÓJNOŚĆ DANYCH (idempotentne; bezpieczne dla istniejących baz) ────────
-- Zawodnik nie gra sam ze sobą; dozwolone wyniki; para bez przeciwnika = wolny los.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pairs_distinct_players') THEN
        ALTER TABLE pairs ADD CONSTRAINT pairs_distinct_players
            CHECK (black_id IS NULL OR black_id <> white_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pairs_result_valid') THEN
        ALTER TABLE pairs ADD CONSTRAINT pairs_result_valid
            CHECK (result IN ('', '1-0', '0-1', '0.5-0.5', 'wolny los'));
    END IF;
END $$;
