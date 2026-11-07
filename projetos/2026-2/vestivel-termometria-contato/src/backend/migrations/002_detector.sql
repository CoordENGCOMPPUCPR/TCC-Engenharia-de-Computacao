-- 002: tabelas do detector. Pode rodar mais de uma vez.

-- Parâmetros do detector. Dá para mudar sem deploy, por exemplo:
--   UPDATE detector_config SET valor = '2.5' WHERE chave = 'lambda_b';
-- Chave ausente ou valor inválido usa o padrão de detector/config.py.
CREATE TABLE IF NOT EXISTS detector_config (
    chave          TEXT PRIMARY KEY,
    valor          JSONB NOT NULL,
    descricao      TEXT,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Valores definidos ao fim da Fase 1C. Rodar de novo não sobrescreve o que
-- já foi editado (ON CONFLICT DO NOTHING).
INSERT INTO detector_config (chave, valor, descricao) VALUES
    ('ciclo_s',          '300',                 'Tamanho do bin (s)'),
    ('n_sensores',       '5',                   'Sensores por nó'),
    ('t_min',            '5.0',                 'Faixa absoluta de validade: mínimo (°C)'),
    ('t_max',            '45.0',                'Faixa absoluta de validade: máximo (°C)'),
    ('frio_delta',       '3.0',                 'Sensor abaixo da mediana menos isto é inválido (°C)'),
    ('filtro_frio',      'true',                'Filtro de perda de contato'),
    ('n_min_validos',    '3',                   'Abaixo disto: FALHA_SENSOR'),
    ('baseline_dias',    '14',                  'Janela da linha de base (dias)'),
    ('arm_dias',         '3',                   'Dias distintos mínimos por célula sensor-hora'),
    ('arm_min_amostras', '10',                  'Amostras mínimas por célula sensor-hora'),
    ('fuso',             '"America/Sao_Paulo"', 'Fuso da hora do dia da linha de base'),
    ('congela_frac',     '0.5',                 'Congela se dT_b > congela_frac * lambda_b (null = só alerta aberto)'),
    ('congelamento',     'true',                'Congelamento ligado'),
    ('congela_max_h',    '168.0',               'Tempo máximo de congelamento contínuo (h; null desliga)'),
    ('congela_max_modo', '"liberar"',           '"liberar" ou "reset"'),
    ('lambda_s',         '1.5',                 'Limiar do espacial (°C)'),
    ('lambda_b',         '2.0',                 'Limiar do temporal (°C)'),
    ('lambda_c',         '2.0',                 'Limiar do contralateral (°C)'),
    ('n_persist',        '24',                  'Bins válidos consecutivos acima do limiar (N)'),
    ('g_ausentes',       '3',                   'Mais que isto de bins ausentes seguidos zera o contador'),
    ('histerese',        '0.7',                 'Fecha após N bins abaixo de histerese * lambda'),
    ('sem_dados_min',    '30.0',                'Idade do último pacote para SEM_DADOS (min)')
ON CONFLICT (chave) DO NOTHING;

-- Estado do detector por animal (JSON do `step`). Os dois membros ficam juntos
-- porque o contralateral compara E com D.
CREATE TABLE IF NOT EXISTS estado_detector (
    vaca_id        TEXT PRIMARY KEY,
    versao         INTEGER NOT NULL,
    estado         JSONB NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Linha de base por animal, membro, sensor e hora local.
CREATE TABLE IF NOT EXISTS baseline (
    vaca_id        TEXT NOT NULL,
    membro         TEXT NOT NULL,
    sensor         INTEGER NOT NULL,
    hora           INTEGER NOT NULL CHECK (hora BETWEEN 0 AND 23),
    b              DOUBLE PRECISION NOT NULL,
    n              INTEGER NOT NULL,
    dias           INTEGER NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (vaca_id, membro, sensor, hora)
);

-- Quando a linha de base de cada hora foi recalculada pela última vez, por animal.
CREATE TABLE IF NOT EXISTS baseline_recalculo (
    vaca_id         TEXT NOT NULL,
    hora            INTEGER NOT NULL,
    recalculado_em  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (vaca_id, hora)
);

-- Evento reset_baseline (só com congela_max_modo = "reset"): ciclos antes de `desde` não contam.
CREATE TABLE IF NOT EXISTS baseline_reset (
    vaca_id  TEXT NOT NULL,
    membro   TEXT NOT NULL,
    desde    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (vaca_id, membro)
);

-- Um registro por ciclo (bin de 5 min) fechado, por membro.
CREATE TABLE IF NOT EXISTS deteccao_ciclos (
    vaca_id     TEXT NOT NULL,
    membro      TEXT NOT NULL,
    ciclo_ts    TIMESTAMPTZ NOT NULL,
    hora_local  INTEGER NOT NULL,
    t_media     REAL,
    dt_b        REAL,
    dt_c        REAL,            -- sempre E - D
    dt_i_max    REAL,
    n_validos   INTEGER NOT NULL,
    n_pacotes   INTEGER NOT NULL,
    estado      TEXT NOT NULL,
    congelado   BOOLEAN NOT NULL,
    t           DOUBLE PRECISION[],        -- mediana válida por sensor (NULL = inválido); base da linha de base
    dt_i        DOUBLE PRECISION[],        -- dT_i por sensor (NULL = inválido ou sem componentes)
    PRIMARY KEY (vaca_id, membro, ciclo_ts)
);
CREATE INDEX IF NOT EXISTS idx_deteccao_baseline
    ON deteccao_ciclos (vaca_id, hora_local, ciclo_ts) WHERE NOT congelado;

CREATE TABLE IF NOT EXISTS alertas (
    id                SERIAL PRIMARY KEY,
    vaca_id           TEXT NOT NULL,
    membro            TEXT NOT NULL,
    componentes       TEXT[] NOT NULL,
    primeiro          TEXT,
    inicio            TIMESTAMPTZ NOT NULL,   -- fim do bin que completou a persistência
    inicio_elevacao   TIMESTAMPTZ NOT NULL,   -- início do primeiro bin da sequência
    fim               TIMESTAMPTZ,            -- NULL = aberto
    picos             JSONB,
    parametros_json   JSONB NOT NULL,         -- parâmetros em uso na abertura
    UNIQUE (vaca_id, membro, inicio)
);
CREATE INDEX IF NOT EXISTS idx_alertas_vaca ON alertas (vaca_id, inicio DESC);
CREATE INDEX IF NOT EXISTS idx_alertas_abertos ON alertas (vaca_id) WHERE fim IS NULL;
