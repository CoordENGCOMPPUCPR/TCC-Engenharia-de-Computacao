-- 001: novas colunas em `leituras`. Pode rodar mais de uma vez.
-- Só acrescenta colunas; as leituras antigas ficam com NULL
-- (membro NULL é tratado como membro único "U" pelo detector).

ALTER TABLE leituras ADD COLUMN IF NOT EXISTS membro TEXT
    CONSTRAINT leituras_membro_valido CHECK (membro IN ('E', 'D'));
ALTER TABLE leituras ADD COLUMN IF NOT EXISTS pacote_id BIGINT;   -- gerado pelo backend a cada POST
ALTER TABLE leituras ADD COLUMN IF NOT EXISTS seq INTEGER;        -- opcional, enviado pelo gateway

CREATE SEQUENCE IF NOT EXISTS leituras_pacote_id_seq;

-- Consulta por animal em ordem de tempo (/estado, /leituras?vaca_id=&de=&ate=, delta_t)
CREATE INDEX IF NOT EXISTS idx_leituras_vaca_ts ON leituras (vaca_id, timestamp DESC);
-- Dedupe de retentativa do gateway: só linhas com seq
CREATE INDEX IF NOT EXISTS idx_leituras_dedupe ON leituras (vaca_id, membro, seq, timestamp DESC)
    WHERE seq IS NOT NULL;
