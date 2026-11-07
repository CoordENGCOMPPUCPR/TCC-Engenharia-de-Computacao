-- Esquema inicial do banco de telemetria (TCC - monitoramento vestível bovino).
-- Rodar uma vez no console SQL do Aiven (ou via psql) antes de subir a API.
-- Depois, aplicar as migrações da pasta migrations/: python scripts/migrar.py

CREATE TABLE IF NOT EXISTS leituras (
    id             SERIAL PRIMARY KEY,
    vaca_id        TEXT NOT NULL,
    quarto         INTEGER NOT NULL,      -- número do sensor (hoje de 1 a 5)
    temp_raw       REAL,                  -- NULL quando o sensor dá erro (aberto/curto)
    temp_ambiente  REAL,
    delta_t        REAL,
    rssi           INTEGER,
    snr            REAL,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Histórico por vaca, ordenado por tempo
CREATE INDEX IF NOT EXISTS idx_leituras_vaca_id ON leituras (vaca_id);
CREATE INDEX IF NOT EXISTS idx_leituras_timestamp ON leituras (timestamp DESC);

-- Se a tabela já existia com temp_raw NOT NULL, rodar uma vez:
-- ALTER TABLE leituras ALTER COLUMN temp_raw DROP NOT NULL;
