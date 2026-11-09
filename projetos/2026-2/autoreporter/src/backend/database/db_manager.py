import os
import sqlite3

class BancoDeDados:
    def __init__(self, db_path="autoreporter.db"):
        self.db_path = db_path
        self.conn = None
        self.conectar()

    def conectar(self):
        """Estabelece conexão com o banco de dados SQLite."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Habilita suporte a chaves estrangeiras
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def inicializar_banco(self, schema_path=None):
        """Lê o arquivo schema.sql e inicializa a estrutura de tabelas."""
        if schema_path is None:
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        cursor = self.conn.cursor()
        cursor.executescript(schema_sql)
        self.conn.commit()
        
        # Migração: Garantir que a coluna status existe na tabela events
        try:
            cursor.execute("SELECT status FROM events LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migração: Adicionando coluna 'status' na tabela 'events'.")
            cursor.execute("ALTER TABLE events ADD COLUMN status TEXT DEFAULT 'DRAFT'")
            self.conn.commit()

        # Migração: Garantir que a coluna seed existe na tabela event_players
        try:
            cursor.execute("SELECT seed FROM event_players LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migração: Adicionando coluna 'seed' na tabela 'event_players'.")
            cursor.execute("ALTER TABLE event_players ADD COLUMN seed INTEGER DEFAULT 0")
            self.conn.commit()

        # Migração: Garantir que a coluna round_number existe na tabela matches
        try:
            cursor.execute("SELECT round_number FROM matches LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migração: Adicionando coluna 'round_number' na tabela 'matches'.")
            cursor.execute("ALTER TABLE matches ADD COLUMN round_number INTEGER DEFAULT 1")
            self.conn.commit()

        # Migração: Garantir colunas de reporte e divergência de placar
        try:
            cursor.execute("SELECT score_reporter_id FROM matches LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migração: Adicionando coluna 'score_reporter_id' na tabela 'matches'.")
            cursor.execute("ALTER TABLE matches ADD COLUMN score_reporter_id INTEGER DEFAULT NULL")
            self.conn.commit()

        try:
            cursor.execute("SELECT score_conflict FROM matches LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migração: Adicionando coluna 'score_conflict' na tabela 'matches'.")
            cursor.execute("ALTER TABLE matches ADD COLUMN score_conflict INTEGER DEFAULT 0")
            self.conn.commit()

        # Executa a rotina mestre de integridade referencial e eliminação de dados órfãos
        self.sanitizar_e_limpar_dados_orfaos()

        print("[DATABASE] Estrutura de tabelas inicializada e migrada com sucesso.")

    def sanitizar_e_limpar_dados_orfaos(self):
        """
        Varredura profunda e reparo de integridade referencial:
        Elimina dados órfãos, referências mortas e inconsistências em cascata
        em todos os componentes do banco (eventos, jogadores, mesas, tags, partidas).
        Retorna um dicionário com o sumário de itens auditados e corrigidos.
        """
        cursor = self.conn.cursor()
        relatorio = {
            "jogadores_duplicados_removidos": 0,
            "tags_orfas_removidas": 0,
            "macs_duplicados_desvinculados": 0,
            "estacoes_orfas_removidas": 0,
            "inscricoes_orfas_removidas": 0,
            "partidas_orfas_removidas": 0,
            "referencias_partidas_corrigidas": 0
        }

        # 1. Deduplicação de Jogadores por Nickname (mantém o menor ID)
        try:
            cursor.execute("""
                DELETE FROM players 
                WHERE id NOT IN (
                    SELECT MIN(id) FROM players GROUP BY LOWER(nickname)
                )
            """)
            relatorio["jogadores_duplicados_removidos"] = cursor.rowcount
        except Exception:
            pass

        # 2. Tags RFID Órfãs (sem jogador ou apontando para jogador inexistente)
        try:
            cursor.execute("""
                DELETE FROM rfid_tags 
                WHERE player_id IS NULL 
                   OR player_id NOT IN (SELECT id FROM players)
            """)
            relatorio["tags_orfas_removidas"] = cursor.rowcount
        except Exception:
            pass

        # 3. Deduplicação de Tags por Jogador (se um atleta tiver múltiplas tags registradas acidentalmente)
        try:
            cursor.execute("""
                DELETE FROM rfid_tags 
                WHERE rowid NOT IN (
                    SELECT MAX(rowid) FROM rfid_tags GROUP BY player_id
                )
            """)
        except Exception:
            pass

        # 4. Inscrições Órfãs em Torneios (event_players apontando para evento ou jogador inexistente)
        try:
            cursor.execute("""
                DELETE FROM event_players 
                WHERE event_id NOT IN (SELECT id FROM events)
                   OR player_id NOT IN (SELECT id FROM players)
            """)
            relatorio["inscricoes_orfas_removidas"] = cursor.rowcount
        except Exception:
            pass

        # 5. Mesas Órfãs (stations apontando para eventos excluídos ou mesas fantasmas sem evento/MAC/partidas)
        try:
            cursor.execute("""
                DELETE FROM stations 
                WHERE (event_id IS NOT NULL AND event_id NOT IN (SELECT id FROM events))
                   OR (event_id IS NULL AND node_mac IS NULL AND id NOT IN (SELECT station_id FROM matches WHERE station_id IS NOT NULL))
            """)
            relatorio["estacoes_orfas_removidas"] = cursor.rowcount
        except Exception:
            pass

        # 5.1 Deduplicação e Fusão de Mesas com mesmo nome no mesmo evento
        try:
            cursor.execute("""
                SELECT event_id, name, COUNT(*) as cnt 
                FROM stations 
                GROUP BY event_id, name 
                HAVING cnt > 1
            """)
            dup_stations = cursor.fetchall()
            mesas_fundidas = 0
            for dup in dup_stations:
                cursor.execute("""
                    SELECT id, node_mac FROM stations 
                    WHERE (event_id IS ? OR event_id = ?) AND name = ? 
                    ORDER BY (CASE WHEN node_mac IS NOT NULL AND TRIM(node_mac) != '' THEN 1 ELSE 0 END) DESC, id DESC
                """, (dup["event_id"], dup["event_id"], dup["name"]))
                rows = cursor.fetchall()
                if len(rows) > 1:
                    primary_id = rows[0]["id"]
                    for secondary in rows[1:]:
                        cursor.execute("UPDATE matches SET station_id = ? WHERE station_id = ?", (primary_id, secondary["id"]))
                        cursor.execute("DELETE FROM stations WHERE id = ?", (secondary["id"],))
                        mesas_fundidas += 1
            relatorio["mesas_duplicadas_fundidas"] = mesas_fundidas
        except Exception:
            pass

        # 5.2 Remoção de Nós Fantasmas com MACs inválidos (ex: 'COORDINATOR')
        try:
            cursor.execute("""
                DELETE FROM nodes 
                WHERE LENGTH(TRIM(mac_address)) != 17 
                   OR mac_address NOT LIKE '__:__:__:__:__:__'
            """)
            relatorio["nos_invalidos_removidos"] = cursor.rowcount
        except Exception:
            pass

        # 6. Deduplicação Estrita de MAC de Hardware (Um nó físico só pode pertencer a 1 mesa ativa)
        try:
            # Desvincula MAC de mesas sem evento se o mesmo MAC já estiver numa mesa com evento ativo
            cursor.execute("""
                UPDATE stations 
                SET node_mac = NULL 
                WHERE event_id IS NULL 
                  AND node_mac IS NOT NULL 
                  AND UPPER(node_mac) IN (
                      SELECT UPPER(node_mac) FROM stations WHERE event_id IS NOT NULL AND node_mac IS NOT NULL
                  )
            """)
            # Desvincula duplicatas mantendo apenas a mesa com maior ID
            cursor.execute("""
                UPDATE stations 
                SET node_mac = NULL 
                WHERE node_mac IS NOT NULL 
                  AND id NOT IN (
                      SELECT MAX(id) FROM stations WHERE node_mac IS NOT NULL GROUP BY UPPER(node_mac)
                  )
            """)
            relatorio["macs_duplicados_desvinculados"] = cursor.rowcount
        except Exception:
            pass

        # 7. Partidas Órfãs (matches apontando para eventos excluídos)
        try:
            cursor.execute("""
                DELETE FROM matches 
                WHERE event_id NOT IN (SELECT id FROM events)
            """)
            relatorio["partidas_orfas_removidas"] = cursor.rowcount
        except Exception:
            pass

        # 8. Correção de Referências Mortas em Partidas
        try:
            # Station inexistente
            cursor.execute("""
                UPDATE matches 
                SET station_id = NULL 
                WHERE station_id IS NOT NULL 
                  AND station_id NOT IN (SELECT id FROM stations)
            """)
            # Jogadores inexistentes
            cursor.execute("""
                UPDATE matches 
                SET player1_id = NULL 
                WHERE player1_id IS NOT NULL 
                  AND player1_id NOT IN (SELECT id FROM players)
            """)
            cursor.execute("""
                UPDATE matches 
                SET player2_id = NULL 
                WHERE player2_id IS NOT NULL 
                  AND player2_id NOT IN (SELECT id FROM players)
            """)
            cursor.execute("""
                UPDATE matches 
                SET winner_id = NULL 
                WHERE winner_id IS NOT NULL 
                  AND winner_id NOT IN (SELECT id FROM players)
            """)
            # Próxima partida inexistente
            cursor.execute("""
                UPDATE matches 
                SET next_match_id = NULL 
                WHERE next_match_id IS NOT NULL 
                  AND next_match_id NOT IN (SELECT id FROM matches)
            """)
            # Normalização de partidas WAITING (não podem ter placares pendentes ou conflitos de partidas anteriores)
            cursor.execute("""
                UPDATE matches 
                SET pending_score1 = NULL, pending_score2 = NULL, 
                    score_reporter_id = NULL, score_conflict = 0,
                    player1_checked_in = 0, player2_checked_in = 0
                WHERE status = 'WAITING'
            """)
            relatorio["referencias_partidas_corrigidas"] = cursor.rowcount
        except Exception:
            pass

        # 9. Conclusão de eventos cujas partidas já foram 100% concluídas
        try:
            cursor.execute("""
                UPDATE events 
                SET status = 'FINISHED'
                WHERE status = 'IN_PROGRESS'
                  AND id IN (
                      SELECT event_id FROM matches GROUP BY event_id 
                      HAVING COUNT(*) > 0 AND COUNT(*) = SUM(CASE WHEN status = 'FINISHED' THEN 1 ELSE 0 END)
                  )
            """)
            relatorio["eventos_finalizados"] = cursor.rowcount
        except Exception:
            pass

        self.conn.commit()
        print(f"[DATABASE INTEGRITY] Sanitização de dados órfãos concluída: {relatorio}")
        return relatorio

    def popular_dados_exemplo(self):
        """Garante que a base inicial de atletas cadastrados existe para a demonstração (sem eventos ou partidas fictícias)."""
        cursor = self.conn.cursor()
        
        # Inserir Jogadores base caso a tabela esteja vazia
        cursor.execute("SELECT COUNT(*) as cnt FROM players")
        if cursor.fetchone()["cnt"] == 0:
            jogadores = [
                (1, "Alice Silva", "Alice", 1),
                (2, "Bob Santos", "Bob", 1),
                (3, "Carlos Oliveira", "Carlos", 1),
                (4, "Diana Souza", "Diana", 1),
                (5, "Dani Heart", "Heartwell", 1),
                (6, "Fernanda Costa", "Shallan", 1),
                (7, "Gabriel Furnaça", "TrollOculto", 1),
                (8, "Helena Rocha", "Helena", 1)
            ]
            cursor.executemany("INSERT OR IGNORE INTO players (id, real_name, nickname, is_active) VALUES (?, ?, ?, ?)", jogadores)
            self.conn.commit()
            print("[DATABASE] Base padrão de atletas cadastrada.")

    def limpar_torneios_para_apresentacao(self):
        """Remove todos os torneios, partidas e estações residuais de teste, preservando 100% dos atletas cadastrados e suas tags RFID."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM stations")
        cursor.execute("DELETE FROM event_players")
        cursor.execute("DELETE FROM events")
        self.conn.commit()
        print("[DATABASE] [OK] Torneios limpos! Base pronta para apresentacao ao vivo com atletas intactos.")

    def fechar(self):
        if self.conn:
            self.conn.close()

    # -------------------------------------------------------------------------
    # MÉTODOS DE GESTÃO DE JOGADORES (PLAYER MANAGEMENT)
    # -------------------------------------------------------------------------
    def cadastrar_jogador(self, real_name, nickname, tag_uid=None):
        """Cadastra um novo atleta garantindo nickname único (reutiliza se já existir)."""
        cursor = self.conn.cursor()
        
        # Evitar cadastros duplicados por nickname
        cursor.execute("SELECT id FROM players WHERE LOWER(nickname) = LOWER(?) AND is_active = 1", (nickname.strip(),))
        row = cursor.fetchone()
        if row:
            player_id = row["id"]
            cursor.execute("UPDATE players SET real_name = ? WHERE id = ?", (real_name, player_id))
        else:
            cursor.execute("INSERT INTO players (real_name, nickname, is_active) VALUES (?, ?, 1)", (real_name, nickname.strip()))
            player_id = cursor.lastrowid

        if tag_uid and str(tag_uid).strip():
            tag_clean = str(tag_uid).strip().upper()
            cursor.execute("DELETE FROM rfid_tags WHERE player_id = ? OR tag_uid = ?", (player_id, tag_clean))
            cursor.execute("INSERT OR REPLACE INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag_clean, player_id))
        else:
            # Atleta sem tag: não gera tag artificial!
            cursor.execute("DELETE FROM rfid_tags WHERE player_id = ?", (player_id,))

        self.conn.commit()
        return player_id

    def atualizar_jogador(self, player_id, real_name, nickname, tag_uid=None):
        """Atualiza nome real, nickname e tag RFID de um jogador existente."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE players SET real_name = ?, nickname = ? WHERE id = ?", (real_name, nickname, player_id))

        if tag_uid is not None:
            tag_clean = tag_uid.strip().upper() if tag_uid.strip() else None
            # Remover tag anterior vinculada a este jogador
            cursor.execute("DELETE FROM rfid_tags WHERE player_id = ?", (player_id,))
            if tag_clean:
                # Remove a tag se estivesse com outro jogador para evitar colisão
                cursor.execute("DELETE FROM rfid_tags WHERE tag_uid = ?", (tag_clean,))
                cursor.execute("INSERT INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag_clean, player_id))

        self.conn.commit()

    def desativar_jogador(self, player_id):
        """Soft Delete: desativa o jogador definindo is_active = 0, mantendo o histórico intacto."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE players SET is_active = 0 WHERE id = ?", (player_id,))
        self.conn.commit()

    def reativar_jogador(self, player_id):
        """Reativa o jogador definindo is_active = 1."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE players SET is_active = 1 WHERE id = ?", (player_id,))
        self.conn.commit()

    def limpar_tags_rfid(self, apenas_artificiais=False):
        """Remove tags do banco. Se apenas_artificiais=True, remove TAG-% e tags de simulação."""
        cursor = self.conn.cursor()
        if apenas_artificiais:
            cursor.execute("DELETE FROM rfid_tags WHERE tag_uid LIKE 'TAG-%' OR tag_uid LIKE 'SIM-%' OR tag_uid IN ('A1B2C3D4', 'E5F6A7B8', 'C9D0E1F2', '8A7B6C5D')")
        else:
            cursor.execute("DELETE FROM rfid_tags")
        self.conn.commit()

    def buscar_jogadores(self, query="", incluir_inativos=True):
        """Busca jogadores por Nome, Nickname ou Tag RFID com filtro de ativos/inativos."""
        cursor = self.conn.cursor()
        q = f"%{query.strip()}%"
        
        sql = """
            SELECT p.id, p.real_name, p.nickname, p.is_active, r.tag_uid
            FROM players p
            LEFT JOIN rfid_tags r ON p.id = r.player_id
            WHERE (p.real_name LIKE ? OR p.nickname LIKE ? OR r.tag_uid LIKE ?)
        """
        params = [q, q, q]

        if not incluir_inativos:
            sql += " AND p.is_active = 1"

        sql += " ORDER BY p.id ASC"
        cursor.execute(sql, params)
        return cursor.fetchall()

    def obter_historico_partidas_jogador(self, player_id):
        """Retorna o histórico detalhado de confrontos do atleta em todos os torneios."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT m.id as match_id, e.name as event_name, e.date as event_date,
                   p1.nickname as p1_nick, p2.nickname as p2_nick,
                   m.score1, m.score2, m.winner_id, m.status,
                   w.nickname as winner_nick
            FROM matches m
            JOIN events e ON m.event_id = e.id
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            LEFT JOIN players w ON m.winner_id = w.id
            WHERE m.player1_id = ? OR m.player2_id = ?
            ORDER BY m.id DESC
        """, (player_id, player_id))
        return cursor.fetchall()

    # -------------------------------------------------------------------------
    # MÉTODOS DE GESTÃO DE EVENTOS E TORNEIOS (MODULE 1 BACKEND)
    # -------------------------------------------------------------------------
    def cadastrar_evento(self, name, date, status="DRAFT"):
        """Cadastra um novo evento/campeonato no sistema."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO events (name, date, status) VALUES (?, ?, ?)", (name, date, status))
        self.conn.commit()
        return cursor.lastrowid

    def obter_evento(self, event_id):
        """Retorna os dados de um evento específico."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, date, status FROM events WHERE id = ?", (event_id,))
        return cursor.fetchone()

    def obter_todos_eventos(self, query="", status_filter="Todos"):
        """Retorna todos os eventos cadastrados filtrados por query e status."""
        cursor = self.conn.cursor()
        q = f"%{query.strip()}%"
        sql = "SELECT id, name, date, status FROM events WHERE name LIKE ?"
        params = [q]

        if status_filter != "Todos":
            sql += " AND status = ?"
            params.append(status_filter)

        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
        return cursor.fetchall()

    def obter_participantes_evento(self, event_id):
        """Retorna todos os competidores inscritos no evento, incluindo se fizeram check-in."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.id, p.real_name, p.nickname, ep.checked_in, ep.seed, r.tag_uid
            FROM event_players ep
            JOIN players p ON ep.player_id = p.id
            LEFT JOIN rfid_tags r ON p.id = r.player_id
            WHERE ep.event_id = ?
            ORDER BY ep.seed ASC, p.id ASC
        """, (event_id,))
        return cursor.fetchall()

    def atualizar_participantes_evento(self, event_id, player_ids):
        """Atualiza a lista de inscritos do evento na tabela event_players, redistribuindo seeds."""
        cursor = self.conn.cursor()
        # 1. Remover todos os participantes existentes desse evento
        cursor.execute("DELETE FROM event_players WHERE event_id = ?", (event_id,))
        
        # 2. Inserir a nova lista de participantes
        for index, p_id in enumerate(player_ids):
            seed = index + 1
            cursor.execute("""
                INSERT INTO event_players (event_id, player_id, checked_in, seed)
                VALUES (?, ?, 0, ?)
            """, (event_id, p_id, seed))
            
        self.conn.commit()

    def clonar_evento(self, event_id, new_name, new_date):
        """Clona participantes e configurações de mesas de um torneio selecionado para um novo rascunho (DRAFT)."""
        cursor = self.conn.cursor()
        
        # 1. Obter informações básicas
        original = self.obter_evento(event_id)
        if not original:
            return None

        # 2. Criar novo evento como DRAFT
        new_event_id = self.cadastrar_evento(new_name, new_date, "DRAFT")

        # 3. Clonar participantes
        cursor.execute("""
            INSERT INTO event_players (event_id, player_id, checked_in, seed)
            SELECT ?, player_id, 0, seed FROM event_players WHERE event_id = ?
        """, (new_event_id, event_id))

        # 4. Clonar estações/mesas associadas ao evento
        cursor.execute("""
            INSERT INTO stations (event_id, name, node_mac)
            SELECT ?, name, node_mac FROM stations WHERE event_id = ?
        """, (new_event_id, event_id))

        self.conn.commit()
        return new_event_id

    def excluir_evento(self, event_id):
        """Exclui permanentemente um evento/torneio e todos os seus registros associados."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM matches WHERE event_id = ?", (event_id,))
        cursor.execute("DELETE FROM stations WHERE event_id = ?", (event_id,))
        cursor.execute("DELETE FROM event_players WHERE event_id = ?", (event_id,))
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self.conn.commit()
        # Garante que nenhuma referência órfã permaneça
        self.sanitizar_e_limpar_dados_orfaos()

    def obter_relatorio_evento(self, event_id):
        """Gera um dicionário completo com os dados do evento, participantes e partidas."""
        evento = self.obter_evento(event_id)
        if not evento:
            return None

        cursor = self.conn.cursor()
        
        # Participantes
        cursor.execute("""
            SELECT p.id, p.nickname, p.real_name, r.tag_uid, ep.seed
            FROM event_players ep
            JOIN players p ON ep.player_id = p.id
            LEFT JOIN rfid_tags r ON p.id = r.player_id
            WHERE ep.event_id = ?
            ORDER BY ep.seed ASC
        """, (event_id,))
        participantes = [dict(row) for row in cursor.fetchall()]

        # Partidas
        cursor.execute("""
            SELECT m.id, m.round_number, m.status, m.score1, m.score2,
                   p1.nickname AS player1_name, p2.nickname AS player2_name,
                   w.nickname AS winner_name, s.name AS station_name
            FROM matches m
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            LEFT JOIN players w ON m.winner_id = w.id
            LEFT JOIN stations s ON m.station_id = s.id
            WHERE m.event_id = ?
            ORDER BY m.round_number ASC, m.id ASC
        """, (event_id,))
        partidas = [dict(row) for row in cursor.fetchall()]

        return {
            "evento": dict(evento),
            "participantes": participantes,
            "partidas": partidas
        }

    def exportar_evento_json(self, event_id, filepath):
        """Exporta os dados de um evento para um arquivo JSON."""
        import json
        relatorio = self.obter_relatorio_evento(event_id)
        if not relatorio:
            return False, "Evento não encontrado."

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(relatorio, f, indent=4, ensure_ascii=False)
            return True, f"Relatório JSON salvo com sucesso em '{filepath}'."
        except Exception as e:
            return False, f"Erro ao salvar arquivo JSON: {str(e)}"

    def exportar_evento_csv(self, event_id, filepath):
        """Exporta as partidas e resultados de um evento para um arquivo CSV."""
        import csv
        relatorio = self.obter_relatorio_evento(event_id)
        if not relatorio:
            return False, "Evento não encontrado."

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                # Cabeçalho do evento
                writer.writerow(["TORNEIO", relatorio["evento"]["name"], "DATA", relatorio["evento"]["date"], "STATUS", relatorio["evento"]["status"]])
                writer.writerow([])
                
                # Cabeçalho de partidas
                writer.writerow(["ID Partida", "Rodada", "Jogador 1", "Placar 1", "Placar 2", "Jogador 2", "Vencedor", "Status", "Estação"])
                for m in relatorio["partidas"]:
                    writer.writerow([
                        m["id"],
                        m["round_number"],
                        m["player1_name"] or "BYE",
                        m["score1"],
                        m["score2"],
                        m["player2_name"] or "BYE",
                        m["winner_name"] or "-",
                        m["status"],
                        m["station_name"] or "Não Alocada"
                    ])
            return True, f"Relatório CSV salvo com sucesso em '{filepath}'."
        except Exception as e:
            return False, f"Erro ao salvar arquivo CSV: {str(e)}"

    def importar_participantes_lote(self, lista_jogadores):
        """
        Recebe uma lista de dicionários [{'nickname': ..., 'real_name': ..., 'tag_uid': ...}]
        e cadastra/atualiza os competidores e suas tags RFID no banco de dados.
        Retorna a contagem de inseridos/atualizados.
        """
        cursor = self.conn.cursor()
        inseridos = 0
        atualizados = 0

        for item in lista_jogadores:
            nick = item.get("nickname", "").strip()
            real = item.get("real_name", "").strip() or nick
            tag = item.get("tag_uid", "").strip().upper() if item.get("tag_uid") else None

            if not nick:
                continue

            # Verificar se jogador já existe por nickname
            cursor.execute("SELECT id FROM players WHERE LOWER(nickname) = LOWER(?)", (nick,))
            row = cursor.fetchone()

            if row:
                player_id = row["id"]
                cursor.execute("UPDATE players SET real_name = ?, is_active = 1 WHERE id = ?", (real, player_id))
                atualizados += 1
            else:
                cursor.execute("INSERT INTO players (nickname, real_name, is_active) VALUES (?, ?, 1)", (nick, real))
                player_id = cursor.lastrowid
                inseridos += 1

            # Atualizar Tag RFID se fornecida
            if tag:
                cursor.execute("DELETE FROM rfid_tags WHERE tag_uid = ? OR player_id = ?", (tag, player_id))
                cursor.execute("INSERT INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag, player_id))

        self.conn.commit()
        return inseridos, atualizados

    # -------------------------------------------------------------------------
    # MÉTODOS DE GESTÃO DE NÓS REPÓRTERES E ESTAÇÕES (MESAS)
    # -------------------------------------------------------------------------
    def cadastrar_ou_atualizar_no(self, mac_address, nickname=None, type="REPORTER"):
        """Cadastra um novo nó no inventário de hardware ou atualiza seu apelido."""
        cursor = self.conn.cursor()
        mac_clean = mac_address.strip().upper()
        nick_val = nickname.strip() if nickname and nickname.strip() else f"Nó {mac_clean[-5:]}"
        
        cursor.execute("SELECT mac_address FROM nodes WHERE mac_address = ?", (mac_clean,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE nodes SET nickname = ?, type = ? WHERE mac_address = ?", (nick_val, type, mac_clean))
        else:
            cursor.execute("INSERT INTO nodes (mac_address, nickname, type) VALUES (?, ?, ?)", (mac_clean, nick_val, type))
            
        self.conn.commit()
        return mac_clean

    def remover_no(self, mac_address):
        """Remove nó do inventário de hardware, garantindo que mesas associadas fiquem com node_mac = NULL."""
        cursor = self.conn.cursor()
        mac_clean = mac_address.strip().upper()
        cursor.execute("UPDATE stations SET node_mac = NULL WHERE node_mac = ?", (mac_clean,))
        cursor.execute("DELETE FROM nodes WHERE mac_address = ?", (mac_clean,))
        self.conn.commit()

    def limpar_nos_falsos(self):
        """Remove todos os nós com MACs simulados/artificiais (AA:BB:CC... e 11:22:33...)."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE stations SET node_mac = NULL WHERE node_mac LIKE 'AA:BB:CC%' OR node_mac LIKE '11:22:33%'")
        cursor.execute("DELETE FROM nodes WHERE mac_address LIKE 'AA:BB:CC%' OR mac_address LIKE '11:22:33%'")
        self.conn.commit()

    def listar_nos_inventario(self):
        """Retorna todos os nós físicos cadastrados e a estação a que estão vinculados no momento."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.mac_address, n.nickname, n.type,
                   s.id AS station_id, s.name AS station_name, s.event_id AS station_event_id
            FROM nodes n
            LEFT JOIN stations s ON n.mac_address = s.node_mac
            ORDER BY n.nickname ASC, n.mac_address ASC
        """)
        return cursor.fetchall()

    def vincular_no_estacao(self, station_id, node_mac):
        """Associa um nó a uma mesa. Se o nó já estiver em outra mesa, desvincula da anterior."""
        cursor = self.conn.cursor()
        mac_clean = node_mac.strip().upper() if node_mac else None
        
        if mac_clean:
            # Desvincula o nó de qualquer outra mesa previamente associada
            cursor.execute("UPDATE stations SET node_mac = NULL WHERE node_mac = ? AND id != ?", (mac_clean, station_id))
            
        cursor.execute("UPDATE stations SET node_mac = ? WHERE id = ?", (mac_clean, station_id))
        self.conn.commit()

    def desvincular_no_estacao(self, station_id):
        """Desassocia o nó de uma mesa, deixando-a em modo de operação manual (Sem Nó)."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE stations SET node_mac = NULL WHERE id = ?", (station_id,))
        self.conn.commit()

    def cadastrar_estacao(self, event_id, name, node_mac=None):
        """Cadastra uma nova mesa de jogo (estação) para o evento especificado."""
        cursor = self.conn.cursor()
        mac_clean = node_mac.strip().upper() if node_mac and node_mac.strip() else None
        
        if mac_clean:
            # Garante que o nó existe no inventário
            cursor.execute("INSERT OR IGNORE INTO nodes (mac_address, nickname, type) VALUES (?, ?, 'REPORTER')", 
                           (mac_clean, f"Nó {name.strip()}"))
            # Desvincula da mesa anterior se houver
            cursor.execute("UPDATE stations SET node_mac = NULL WHERE node_mac = ?", (mac_clean,))
            
        cursor.execute("INSERT INTO stations (event_id, name, node_mac) VALUES (?, ?, ?)", (event_id, name.strip(), mac_clean))
        self.conn.commit()
        return cursor.lastrowid

    def obter_estacoes_disponiveis(self, event_id, match_id=None):
        """
        Retorna as estações cadastradas que estão livres (não ocupadas por partidas em READY ou PLAYING).
        Se match_id for fornecido, inclui a estação atualmente alocada para esta partida (se houver).
        """
        cursor = self.conn.cursor()
        current_station_id = None
        if match_id:
            cursor.execute("SELECT station_id FROM matches WHERE id = ?", (match_id,))
            m = cursor.fetchone()
            if m and m["station_id"]:
                current_station_id = m["station_id"]

        cursor.execute("""
            SELECT s.id, s.name, s.node_mac
            FROM stations s
            WHERE (s.event_id = ? OR s.event_id IS NULL)
              AND (
                  s.id NOT IN (
                      SELECT DISTINCT station_id FROM matches 
                      WHERE station_id IS NOT NULL 
                        AND status IN ('READY', 'PLAYING') 
                        AND (id != ? OR ? IS NULL)
                  )
                  OR (s.id = ? AND ? IS NOT NULL)
              )
            ORDER BY s.id ASC
        """, (event_id, match_id, match_id, current_station_id, current_station_id))
        return cursor.fetchall()

    def renomear_estacao(self, station_id, novo_nome, renomear_global=False):
        """
        Renomeia uma estação pelo seu ID.
        Se renomear_global for True, renomeia todas as ocorrências do nome antigo em outros torneios.
        """
        cursor = self.conn.cursor()
        novo_nome_clean = novo_nome.strip()
        if not novo_nome_clean:
            return False
            
        if renomear_global:
            cursor.execute("SELECT name FROM stations WHERE id = ?", (station_id,))
            row = cursor.fetchone()
            if row:
                nome_antigo = row["name"]
                cursor.execute("UPDATE stations SET name = ? WHERE name = ?", (novo_nome_clean, nome_antigo))
            else:
                cursor.execute("UPDATE stations SET name = ? WHERE id = ?", (novo_nome_clean, station_id))
        else:
            cursor.execute("UPDATE stations SET name = ? WHERE id = ?", (novo_nome_clean, station_id))
            
        self.conn.commit()
        return True

    def excluir_estacao(self, station_id, expurgar_global=False):
        """
        Exclui uma mesa do evento com segurança referencial.
        Se expurgar_global for True, remove todas as mesas com o mesmo nome que não tenham partidas em andamento.
        """
        cursor = self.conn.cursor()
        if expurgar_global:
            cursor.execute("SELECT name FROM stations WHERE id = ?", (station_id,))
            row = cursor.fetchone()
            if row:
                nome_alvo = row["name"]
                cursor.execute("UPDATE matches SET station_id = NULL WHERE station_id IN (SELECT id FROM stations WHERE name = ?)", (nome_alvo,))
                cursor.execute("DELETE FROM stations WHERE name = ?", (nome_alvo,))
            else:
                cursor.execute("UPDATE matches SET station_id = NULL WHERE station_id = ?", (station_id,))
                cursor.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        else:
            cursor.execute("UPDATE matches SET station_id = NULL WHERE station_id = ?", (station_id,))
            cursor.execute("DELETE FROM stations WHERE id = ?", (station_id,))
            
        self.conn.commit()

    def obter_detalhes_estacao(self, station_id):
        """
        Retorna dados completos da mesa:
        - Dados da estação e evento
        - Nó repórter alocado (se houver)
        - Partida ativa no momento (com competidores, flags de check-in e scores pendentes)
        - Histórico de partidas jogadas nessa mesa no torneio atual
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name, s.event_id, s.node_mac,
                   n.nickname AS node_nickname, n.type AS node_type,
                   e.name AS event_name
            FROM stations s
            LEFT JOIN nodes n ON s.node_mac = n.mac_address
            LEFT JOIN events e ON s.event_id = e.id
            WHERE s.id = ?
        """, (station_id,))
        st_row = cursor.fetchone()
        if not st_row:
            return None

        station_data = dict(st_row)

        # Partida ativa (READY ou PLAYING)
        cursor.execute("""
            SELECT m.id, m.round_number, m.status, m.score1, m.score2,
                   m.player1_id, m.player2_id,
                   m.player1_checked_in, m.player2_checked_in,
                   m.pending_score1, m.pending_score2,
                   m.score_reporter_id, m.score_conflict,
                   p1.nickname AS p1_nick, p1.real_name AS p1_real,
                   p2.nickname AS p2_nick, p2.real_name AS p2_real
            FROM matches m
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            WHERE m.station_id = ? AND m.status IN ('READY', 'PLAYING')
            ORDER BY m.id DESC
            LIMIT 1
        """, (station_id,))
        active_match = cursor.fetchone()
        station_data["partida_ativa"] = dict(active_match) if active_match else None

        # Histórico de partidas concluídas ou passadas nesta mesa
        cursor.execute("""
            SELECT m.id, m.round_number, m.status, m.score1, m.score2,
                   p1.nickname AS p1_nick, p2.nickname AS p2_nick,
                   w.nickname AS winner_nick
            FROM matches m
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            LEFT JOIN players w ON m.winner_id = w.id
            WHERE m.station_id = ? AND m.status = 'FINISHED'
            ORDER BY m.round_number ASC, m.id ASC
        """, (station_id,))
        historico = [dict(r) for r in cursor.fetchall()]
        station_data["historico_partidas"] = historico

        return station_data

    def obter_detalhes_no(self, node_mac, event_id=None):
        """
        Retorna dados completos do nó:
        - Metadados do hardware no inventário
        - Mesa associada atualmente (se houver)
        - Histórico de partidas jogadas na mesa vinculada
        """
        cursor = self.conn.cursor()
        mac_clean = node_mac.strip().upper()
        cursor.execute("""
            SELECT n.mac_address, n.nickname, n.type,
                   s.id AS station_id, s.name AS station_name, s.event_id AS station_event_id,
                   e.name AS event_name
            FROM nodes n
            LEFT JOIN stations s ON n.mac_address = s.node_mac
            LEFT JOIN events e ON s.event_id = e.id
            WHERE n.mac_address = ?
        """, (mac_clean,))
        row = cursor.fetchone()
        if not row:
            return None

        node_data = dict(row)

        # Se vinculado a uma mesa, buscar histórico de partidas
        station_id = node_data.get("station_id")
        if station_id:
            cursor.execute("""
                SELECT m.id, m.round_number, m.status, m.score1, m.score2,
                       p1.nickname AS p1_nick, p2.nickname AS p2_nick,
                       w.nickname AS winner_nick
                FROM matches m
                LEFT JOIN players p1 ON m.player1_id = p1.id
                LEFT JOIN players p2 ON m.player2_id = p2.id
                LEFT JOIN players w ON m.winner_id = w.id
                WHERE m.station_id = ?
                ORDER BY m.id DESC
            """, (station_id,))
            node_data["historico_partidas"] = [dict(r) for r in cursor.fetchall()]
        else:
            node_data["historico_partidas"] = []

        return node_data

if __name__ == "__main__":
    # Teste rápido de inicialização do banco
    db = BancoDeDados()
    db.inicializar_banco()
    db.popular_dados_exemplo()
    db.fechar()

