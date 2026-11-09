-- Schema do Banco de Dados SQLite - Autoreporter
-- Em conformidade com a modelagem do Capítulo 2 do TCC

PRAGMA foreign_keys = ON;

-- Tabela de Eventos
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    status TEXT DEFAULT 'DRAFT'
);

-- Tabela de Jogadores
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    real_name TEXT NOT NULL,
    nickname TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS event_players (
    event_id INTEGER,
    player_id INTEGER,
    checked_in INTEGER DEFAULT 0,
    seed INTEGER DEFAULT 0,
    PRIMARY KEY (event_id, player_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

-- Tabela de Tags RFID (Âncora Ciberfísica)
CREATE TABLE IF NOT EXISTS rfid_tags (
    tag_uid TEXT PRIMARY KEY,
    player_id INTEGER,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

-- Tabela de Nós de Hardware (ESP32)
CREATE TABLE IF NOT EXISTS nodes (
    mac_address TEXT PRIMARY KEY,
    nickname TEXT,
    type TEXT CHECK(type IN ('REPORTER', 'COORDINATOR')) NOT NULL
);

-- Tabela de Estações de Jogo (Mesas)
CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    name TEXT NOT NULL,
    node_mac TEXT,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (node_mac) REFERENCES nodes(mac_address) ON DELETE SET NULL
);

-- Tabela de Partidas (Centro da Lógica do Torneio)
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    round_number INTEGER DEFAULT 1,
    player1_id INTEGER,
    player2_id INTEGER,
    score1 INTEGER DEFAULT 0,
    score2 INTEGER DEFAULT 0,
    winner_id INTEGER,
    status TEXT CHECK(status IN ('WAITING', 'READY', 'PLAYING', 'FINISHED')) DEFAULT 'WAITING',
    station_id INTEGER,
    next_match_id INTEGER,
    next_match_slot INTEGER CHECK(next_match_slot IN (1, 2)),
    player1_checked_in INTEGER DEFAULT 0,
    player2_checked_in INTEGER DEFAULT 0,
    pending_score1 INTEGER DEFAULT NULL,
    pending_score2 INTEGER DEFAULT NULL,
    score_reporter_id INTEGER DEFAULT NULL,
    score_conflict INTEGER DEFAULT 0,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (player1_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (player2_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (winner_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE SET NULL,
    FOREIGN KEY (next_match_id) REFERENCES matches(id) ON DELETE SET NULL
);
