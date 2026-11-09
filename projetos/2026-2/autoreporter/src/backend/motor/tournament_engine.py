import sys
import os
import threading
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import BancoDeDados

class MotorDoTorneio:
    """
    Classe responsável de forma exclusiva por gerenciar o avanço das chaves
    do campeonato, processar resultados e tomar decisões de chaveamento.
    """
    def __init__(self, db: BancoDeDados, driver_serial=None):
        self.db = db
        self.driver_serial = driver_serial

    def _determinar_cor_estacao(self, node_mac):
        """Determina a cor canônica em que o nó da mesa deve permanecer."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT m.status, m.pending_score1, m.score_conflict
                FROM matches m
                JOIN stations s ON m.station_id = s.id
                WHERE UPPER(s.node_mac) = UPPER(?) AND m.status IN ('READY', 'PLAYING')
                ORDER BY m.id DESC LIMIT 1
            """, (node_mac,))
            m = cursor.fetchone()
            if m:
                if m["score_conflict"] == 1:
                    return "RED"
                if m["pending_score1"] is not None:
                    return "YELLOW"
                if m["status"] == "PLAYING":
                    return "BLUE"
                if m["status"] == "READY":
                    return "YELLOW"
        except Exception:
            pass
        return "YELLOW"  # Estado padrão de prontidão (standby)

    def _piscar_alerta_temporario(self, node_mac, cor_alerta="RED", duracao=2.5):
        """
        Envia uma cor de alerta imediata (ex: RED) e agenda a restauração automática
        da cor canônica da mesa após `duracao` segundos em uma thread paralela.
        """
        if not self.driver_serial or not node_mac:
            return
            
        mac_clean = str(node_mac).strip().upper()
        # 1. Envia comando imediato de alerta
        self.driver_serial.enviar_comando_no(mac_clean, f"LED;{cor_alerta}")
        
        # 2. Agenda restauração do estado normal
        def _restaurar():
            cor_restaurada = self._determinar_cor_estacao(mac_clean)
            if self.driver_serial:
                self.driver_serial.enviar_comando_no(mac_clean, f"LED;{cor_restaurada}")
                
        t = threading.Timer(duracao, _restaurar)
        t.daemon = True
        t.start()

    def registrar_checkin_rfid(self, tag_uid, node_mac):
        """
        Recebe a leitura física de uma tag RFID em um Nó Repórter específico.
        Valida se o jogador está designado para aquela mesa (estação) e executa o check-in.
        """
        cursor = self.db.conn.cursor()
        current_node_mac = (node_mac or "").strip().upper()
        
        # 1. Identificar o jogador pela tag RFID
        cursor.execute("SELECT player_id FROM rfid_tags WHERE UPPER(tag_uid) = ?", (tag_uid.strip().upper(),))
        row_player = cursor.fetchone()
        if not row_player:
            print(f"[MOTOR] Tag RFID desconhecida: {tag_uid}")
            self._piscar_alerta_temporario(current_node_mac, "RED", duracao=2.0)
            return False, "Tag desconhecida"
        
        player_id = row_player["player_id"]
        
        # 2. Localizar a partida ativa do jogador ('READY' ou 'PLAYING')
        cursor.execute("""
            SELECT m.id, m.station_id, s.name as station_name, s.node_mac as station_mac,
                   m.player1_id, m.player2_id, m.player1_checked_in, m.player2_checked_in, m.status 
            FROM matches m
            LEFT JOIN stations s ON m.station_id = s.id
            WHERE (m.player1_id = ? OR m.player2_id = ?) 
              AND m.status IN ('READY', 'PLAYING')
            ORDER BY m.id DESC LIMIT 1
        """, (player_id, player_id))
        match = cursor.fetchone()

        if not match:
            print(f"[MOTOR] Atleta #{player_id} não possui partida ativa ('READY'/'PLAYING').")
            self._piscar_alerta_temporario(current_node_mac, "RED", duracao=2.0)
            return False, "Jogador sem partida ativa convocada"

        match_id = match["id"]
        station_id = match["station_id"]
        station_name = match["station_name"] or f"Mesa #{station_id}"
        station_mac = (match["station_mac"] or "").strip().upper()

        # 3. Validação Estrita de Prova de Presença e Localidade (PoPL):
        # O Nó físico onde a tag foi lida DEVE ser rigorosamente o Nó Repórter vinculado à mesa da partida!
        if not station_mac:
            # Auto-vínculo inteligente caso a mesa no banco ainda não tenha nó atribuído (ex: pós-limpeza de nós)
            cursor.execute("UPDATE stations SET node_mac = ? WHERE id = ?", (current_node_mac, station_id))
            self.db.conn.commit()
            station_mac = current_node_mac
            print(f"[MOTOR - POPL AUTO-VINCULO] Mesa '{station_name}' (#{station_id}) vinculada automaticamente ao Nó [{current_node_mac}] via check-in do atleta #{player_id}!")
        elif station_mac != current_node_mac:
            print(f"[MOTOR - POPL REJEITADO] Atleta #{player_id} aproximou tag no Nó [{current_node_mac}], mas sua partida #{match_id} está designada para a mesa '{station_name}' (Nó [{station_mac}])!")
            # Sinalização física visual temporária de erro no nó incorreto (Pisca Vermelho e restaura após 2s)
            self._piscar_alerta_temporario(current_node_mac, "RED", duracao=2.0)
            return False, f"Mesa incorreta! Sua partida está designada para a mesa '{station_name}'."
        
        p1_id = match["player1_id"]
        p2_id = match["player2_id"]
        p1_checked = match["player1_checked_in"]
        p2_checked = match["player2_checked_in"]
        status = match["status"]
        
        # 4. Atualizar o respectivo flag de check-in na mesa correta
        if player_id == p1_id:
            p1_checked = 1
            cursor.execute("UPDATE matches SET player1_checked_in = 1 WHERE id = ?", (match_id,))
        elif player_id == p2_id:
            p2_checked = 1
            cursor.execute("UPDATE matches SET player2_checked_in = 1 WHERE id = ?", (match_id,))
            
        self.db.conn.commit()
        
        # 5. Se ambos fizeram check-in na mesa correta, atualiza para PLAYING
        if p1_checked == 1 and p2_checked == 1:
            if status != 'PLAYING':
                cursor.execute("UPDATE matches SET status = 'PLAYING' WHERE id = ?", (match_id,))
                self.db.conn.commit()
            print(f"[MOTOR] Ambos os jogadores fizeram check-in na mesa {station_name}. Partida #{match_id} INICIADA!")
            if self.driver_serial and current_node_mac:
                self.driver_serial.enviar_comando_no(current_node_mac, "LED;CHECKIN2")
                self._piscar_alerta_temporario(current_node_mac, "GREEN", duracao=2.0)
            return True, f"Partida iniciada na mesa {station_name}"
        else:
            print(f"[MOTOR] Check-in de #{player_id} confirmado! Aguardando oponente na mesa {station_name}")
            if self.driver_serial and current_node_mac:
                self.driver_serial.enviar_comando_no(current_node_mac, "LED;CHECKIN1")
                self._piscar_alerta_temporario(current_node_mac, "GREEN", duracao=2.0)
            return True, f"Check-in confirmado! Aguardando oponente na mesa {station_name}"

    def normalizar_placar_bo3(self, score1, score2):
        """
        Aplica as regras de formato Melhor de 3 (Bo3):
        - Vence quem atingir 2 vitórias.
        - Se um placar excedente for enviado (ex: 5x1, 3x0, 4x2), normaliza o vencedor para 2 e o perdedor para min(perdedor, 1).
        - Se nenhum atingiu 2 vitórias (ex: 1x0, 0x1, 1x1, 0x0), a partida continua em andamento (is_finished = False).
        Returns (s1, s2, is_finished, winner_slot)
        """
        s1 = max(0, int(score1))
        s2 = max(0, int(score2))

        if s1 >= 2 or s2 >= 2:
            if s1 > s2:
                return 2, min(s2, 1), True, 1
            elif s2 > s1:
                return min(s1, 1), 2, True, 2
            else: # Empate em 2x2 ou maior -> força 2x1 a favor do jogador 1 por padrão
                return 2, 1, True, 1
        else:
            # Placar parcial: 0x0, 1x0, 0x1, 1x1
            return s1, s2, False, None

    def reportar_placar_ciberfisico(self, station_id, score_player1, score_player2):
        """
        Consolida o resultado de uma partida na mesa em formato Melhor de 3 (Bo3).
        Se a partida for concluída (2 vitórias), determina o vencedor, promove-o na árvore e finaliza a partida.
        Se for um placar parcial (ex: 1x0, 1x1), atualiza os placares parciais e mantém a partida em andamento (PLAYING).
        """
        cursor = self.db.conn.cursor()
        
        # 1. Buscar partida ativa na mesa
        cursor.execute("""
            SELECT * FROM matches 
            WHERE station_id = ? AND status = 'PLAYING'
        """, (station_id,))
        match = cursor.fetchone()
        
        if not match:
            print(f"[MOTOR] Nenhuma partida em andamento na mesa {station_id} para reportar.")
            return False
        
        match_id = match["id"]
        p1_id = match["player1_id"]
        p2_id = match["player2_id"]
        next_match_id = match["next_match_id"]
        next_slot = match["next_match_slot"]
        
        s1, s2, is_finished, winner_slot = self.normalizar_placar_bo3(score_player1, score_player2)

        if is_finished:
            winner_id = p1_id if winner_slot == 1 else p2_id
            cursor.execute("""
                UPDATE matches 
                SET score1 = ?, score2 = ?, winner_id = ?, status = 'FINISHED',
                    player1_checked_in = 0, player2_checked_in = 0,
                    pending_score1 = NULL, pending_score2 = NULL,
                    score_reporter_id = NULL, score_conflict = 0
                WHERE id = ?
            """, (s1, s2, winner_id, match_id))
            
            print(f"[MOTOR] Partida Bo3 #{match_id} finalizada com placar {s1}x{s2}. Vencedor: {winner_id}.")
            
            # Propagação na Árvore do Campeonato (Avançar vencedor para a próxima chave)
            if next_match_id:
                self._promover_jogador(next_match_id, next_slot, winner_id)

            # Aloca a mesa recém-liberada para a próxima partida da fila que estiver aguardando mesa
            cursor.execute("""
                SELECT id FROM matches 
                WHERE event_id = ? AND status = 'READY' AND station_id IS NULL
                ORDER BY round_number ASC, id ASC LIMIT 1
            """, (match["event_id"],))
            proxima = cursor.fetchone()
            if proxima:
                self._alocar_mesa_disponivel(proxima["id"])
        else:
            # Placar parcial (ex: 1x0, 1x1) -> partida continua em andamento (PLAYING)
            cursor.execute("""
                UPDATE matches 
                SET score1 = ?, score2 = ?, winner_id = NULL, status = 'PLAYING',
                    pending_score1 = NULL, pending_score2 = NULL,
                    score_reporter_id = NULL, score_conflict = 0
                WHERE id = ?
            """, (s1, s2, match_id))
            print(f"[MOTOR] Placar parcial de Bo3 {s1}x{s2} registrado para a partida #{match_id} (Em andamento).")
            
        self.db.conn.commit()
        if is_finished:
            self.verificar_e_finalizar_torneio(match["event_id"])
        return True

    def iniciar_reporte_placar(self, match_id, score1, score2, reporter_id=None):
        """
        Registra o placar proposto enviado via Web App por um dos competidores.
        Detecta divergências caso o oponente já tenha reportado um placar diferente.
        Dispara sinal Downlink (LED Amarelo para proposta, ou Vermelho para Conflito) para a mesa física.
        """
        try:
            s1 = int(score1)
            s2 = int(score2)
        except (ValueError, TypeError):
            return False, "Valores de placar inválidos"

        if s1 == s2:
            return False, "Não pode haver empate! Alguém precisa vencer a partida."

        cursor = self.db.conn.cursor()
        
        # 1. Buscar a partida correspondente
        cursor.execute("""
            SELECT m.id, m.status, m.station_id, m.player1_id, m.player2_id,
                   m.pending_score1, m.pending_score2, m.score_reporter_id, m.score_conflict,
                   s.name as station_name, s.node_mac
            FROM matches m
            LEFT JOIN stations s ON m.station_id = s.id
            WHERE m.id = ?
        """, (match_id,))
        match = cursor.fetchone()
        if not match:
            print(f"[MOTOR] Partida {match_id} não encontrada.")
            return False, "Partida não encontrada"
            
        status = match["status"]
        station_id = match["station_id"]
        node_mac = match["node_mac"]
        station_name = match["station_name"] or f"Mesa {station_id}"
        p1_id = match["player1_id"]
        p2_id = match["player2_id"]
        pending_s1 = match["pending_score1"]
        pending_s2 = match["pending_score2"]
        prev_reporter = match["score_reporter_id"]
        
        if status != 'PLAYING':
            print(f"[MOTOR] Partida {match_id} não está em andamento (status = {status}).")
            return False, "Partida não está em andamento"

        # 2. Se já existe um placar proposto e o reportador atual é o oponente:
        if pending_s1 is not None and prev_reporter and reporter_id and str(prev_reporter) != str(reporter_id):
            if int(score1) == int(pending_s1) and int(score2) == int(pending_s2):
                # Concordância mútua!
                print(f"[MOTOR] Ambos os competidores reportaram o mesmo placar {score1}x{score2} na mesa {station_name}!")
                cursor.execute("UPDATE matches SET score_conflict = 0 WHERE id = ?", (match_id,))
                self.db.conn.commit()
                return True, "Placar em acordo confirmado! Aproxime seu cartão RFID na mesa para chancelar a partida."
            else:
                # DIVERGÊNCIA / CONFLITO DE PLACAR!
                print(f"[MOTOR - DIVERGENCIA] Conflito de placar na mesa {station_name}! Atleta #{prev_reporter} propôs {pending_s1}x{pending_s2}, mas atleta #{reporter_id} enviou {score1}x{score2}!")
                cursor.execute("UPDATE matches SET score_conflict = 1 WHERE id = ?", (match_id,))
                self.db.conn.commit()
                # Sinalização de Alerta no Hardware físico da Mesa (LED Vermelho)
                if self.driver_serial and node_mac:
                    self.driver_serial.enviar_comando_no(node_mac, "LED;RED")
                return False, f"Divergência detectada! O oponente reportou {pending_s1}x{pending_s2} e você reportou {score1}x{score2}. A mesa foi sinalizada em alerta. Chame a organização para arbitrar."

        # 3. Primeiro reporte (ou reenvio pelo mesmo jogador):
        cursor.execute("""
            UPDATE matches 
            SET pending_score1 = ?, pending_score2 = ?, score_reporter_id = ?, score_conflict = 0
            WHERE id = ?
        """, (score1, score2, reporter_id, match_id))
        self.db.conn.commit()
        
        print(f"[MOTOR] Proposta de placar {score1}x{score2} registrada pelo atleta #{reporter_id} na mesa {station_name}.")
        print("[MOTOR] Aguardando validação do oponente ou chancela física RFID.")
        
        # Sinalização Downlink (LED Amarelo de verificação pendente)
        if self.driver_serial and node_mac:
            self.driver_serial.enviar_comando_no(node_mac, "LED;YELLOW")
        
        return True, "Placar submetido com sucesso! Aproxime o cartão RFID na mesa física para chancelar."

    def contestar_placar(self, match_id, player_id):
        """Marca formalmente a partida com conflito após recusa explícita de um competidor."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT m.id, m.station_id, s.node_mac, s.name as station_name 
            FROM matches m
            LEFT JOIN stations s ON m.station_id = s.id
            WHERE m.id = ?
        """, (match_id,))
        match = cursor.fetchone()
        if not match:
            return False, "Partida não encontrada"
        
        cursor.execute("UPDATE matches SET score_conflict = 1 WHERE id = ?", (match_id,))
        self.db.conn.commit()
        
        node_mac = match["node_mac"]
        station_name = match["station_name"] or f"Mesa {match['station_id']}"
        print(f"[MOTOR - CONTESTACAO] O atleta #{player_id} contestou formalmente o placar na mesa {station_name}!")
        if self.driver_serial and node_mac:
            self.driver_serial.enviar_comando_no(node_mac, "LED;RED")
            
        return True, "Contestação de placar registrada! A organização foi notificada para arbitrar na mesa."

    def confirmar_placar_rfid(self, tag_uid, node_mac):
        """
        Trata a leitura de tag RFID física que assina o placar.
        Valida se a tag pertence a um dos jogadores da partida em andamento com score pendente,
        e bloqueia a chancela caso haja divergência/conflito ativo (score_conflict = 1).
        """
        cursor = self.db.conn.cursor()
        current_node_mac = (node_mac or "").strip().upper()
        tag_clean = (tag_uid or "").strip().upper()

        # 1. Identificar jogador pela tag RFID
        cursor.execute("SELECT player_id FROM rfid_tags WHERE UPPER(tag_uid) = ?", (tag_clean,))
        row_player = cursor.fetchone()
        
        match = None
        player_id = None
        
        if row_player:
            player_id = row_player["player_id"]
            # 2. Localizar diretamente a partida ativa deste jogador com placar pendente
            cursor.execute("""
                SELECT m.*, s.name as station_name, s.node_mac as station_mac
                FROM matches m
                LEFT JOIN stations s ON m.station_id = s.id
                WHERE (m.player1_id = ? OR m.player2_id = ?)
                  AND m.status = 'PLAYING'
                  AND m.pending_score1 IS NOT NULL
                ORDER BY m.id DESC LIMIT 1
            """, (player_id, player_id))
            match = cursor.fetchone()

        # 3. Fallback: Se não encontrou por jogador (ex: leitura direta no nó ou admin),
        # busca partida ativa com placar pendente vinculada ao MAC deste nó físico
        if not match and current_node_mac:
            cursor.execute("""
                SELECT m.*, s.name as station_name, s.node_mac as station_mac
                FROM matches m
                JOIN stations s ON m.station_id = s.id
                WHERE UPPER(s.node_mac) = ?
                  AND m.status = 'PLAYING'
                  AND m.pending_score1 IS NOT NULL
                ORDER BY m.id DESC LIMIT 1
            """, (current_node_mac,))
            match = cursor.fetchone()

        if not match:
            return False, "Nenhum placar pendente para esta mesa/atleta"

        match_id = match["id"]
        station_id = match["station_id"]
        station_name = match["station_name"] or f"Mesa {station_id}"
        station_mac = (match["station_mac"] or "").strip().upper()
        p1_id = match["player1_id"]
        p2_id = match["player2_id"]
        pending_s1 = match["pending_score1"]
        pending_s2 = match["pending_score2"]
        score_conflict = match["score_conflict"]

        # 4. Validação Estrita de Prova de Presença e Localidade (PoPL):
        if not station_mac and current_node_mac:
            cursor.execute("UPDATE stations SET node_mac = ? WHERE id = ?", (current_node_mac, station_id))
            self.db.conn.commit()
            station_mac = current_node_mac
            print(f"[MOTOR - POPL AUTO-VINCULO] Mesa '{station_name}' (#{station_id}) vinculada automaticamente ao Nó [{current_node_mac}] na confirmação de placar!")
        elif station_mac and current_node_mac and station_mac != current_node_mac:
            print(f"[MOTOR - POPL REJEITADO] Atleta #{player_id} aproximou tag no Nó [{current_node_mac}], mas sua partida #{match_id} está designada para a mesa '{station_name}' (Nó [{station_mac}])!")
            self._piscar_alerta_temporario(current_node_mac, "RED", duracao=2.5)
            return False, f"Mesa incorreta! Sua partida está designada para a mesa '{station_name}'."

        # 5. Se houver divergência ativa, bloqueia chancela automática
        if score_conflict:
            print(f"[MOTOR - BLOQUEIO] Não é possível confirmar placar via RFID na mesa {station_name} devido a DIVERGENCIA ATIVA! Arbitragem necessária.")
            self._piscar_alerta_temporario(current_node_mac, "RED", duracao=2.5)
            return False, "Divergência de placar ativa! Chame a organização para arbitrar o resultado."

        # 6. Validar se o jogador pertence à partida (se identificado por tag)
        if player_id is not None and player_id not in (p1_id, p2_id):
            print(f"[MOTOR] Jogador #{player_id} não pertence à partida #{match_id}.")
            self._piscar_alerta_temporario(current_node_mac, "RED", duracao=2.5)
            return False, "Jogador não pertence a esta partida"

        # 7. Consolidar o resultado definitivamente
        print(f"[MOTOR] Placar confirmado pelo atleta #{player_id} na mesa {station_name} (#{match_id})!")
        sucesso = self.reportar_placar_ciberfisico(station_id, pending_s1, pending_s2)
        if sucesso:
            # Envia downlink liberando a mesa física (LED Verde)
            if self.driver_serial and current_node_mac:
                self.driver_serial.enviar_comando_no(current_node_mac, "LED;GREEN")
            return True, "Placar confirmado e partida finalizada"
        else:
            return False, "Erro ao finalizar partida"

    def desqualificar_jogador(self, match_id, player_id):
        """
        Desqualifica um competidor de uma partida ativa.
        O oponente é promovido com placar de 0x0.
        """
        cursor = self.db.conn.cursor()
        
        cursor.execute("SELECT event_id, player1_id, player2_id, station_id, next_match_id, next_match_slot, status FROM matches WHERE id = ?", (match_id,))
        match = cursor.fetchone()
        if not match:
            print(f"[MOTOR] Partida {match_id} não encontrada.")
            return False, "Partida não encontrada"
            
        status = match["status"]
        if status == "FINISHED":
            return False, "Partida já finalizada"
            
        p1 = match["player1_id"]
        p2 = match["player2_id"]
        station_id = match["station_id"]
        next_match_id = match["next_match_id"]
        next_slot = match["next_match_slot"]
        
        # Identificar o oponente
        if player_id == p1:
            winner = p2
        elif player_id == p2:
            winner = p1
        else:
            return False, "Jogador não pertence a esta partida"
            
        if winner is None:
            return False, "Adversário não definido para desqualificação"
            
        # Finalizar partida como 0x0
        cursor.execute("""
            UPDATE matches 
            SET score1 = 0, score2 = 0, winner_id = ?, status = 'FINISHED',
                player1_checked_in = 0, player2_checked_in = 0,
                pending_score1 = NULL, pending_score2 = NULL
            WHERE id = ?
        """, (winner, match_id))
        
        print(f"[MOTOR] Jogador {player_id} desqualificado. Vencedor: {winner}.")
        
        # Liberar mesa
        if station_id:
            cursor.execute("UPDATE stations SET node_mac = node_mac WHERE id = ?", (station_id,))
            
        # Promover vencedor
        if next_match_id:
            self._promover_jogador(next_match_id, next_slot, winner)
            
        self.db.conn.commit()
        self.verificar_e_finalizar_torneio(match["event_id"])
        return True, "Jogador desqualificado com sucesso."

    def inicializar_chave_torneio(self, event_id):
        """
        Gera a chave de brackets (Single Elimination) para o evento.
        Pads a lista de competidores com BYEs se necessário (próxima potência de 2).
        Cria as partidas no banco de dados e auto-resolve os confrontos contra BYEs.
        """
        cursor = self.db.conn.cursor()
        
        # 1. Obter todos os jogadores associados ao evento ordenados por seed
        cursor.execute("""
            SELECT player_id, seed FROM event_players 
            WHERE event_id = ? 
            ORDER BY seed ASC
        """, (event_id,))
        rows = cursor.fetchall()
        
        if not rows:
            print("[MOTOR] Nenhum jogador inscrito para o evento.")
            return False, "Nenhum jogador inscrito para o evento."
        
        players = [row["player_id"] for row in rows]
        N = len(players)
        
        # 2. Calcular próxima potência de 2 (P)
        import math
        P = 2 ** math.ceil(math.log2(N)) if N > 1 else 2
        
        # 3. Gerar a ordem de seeding padrão
        def get_seeding_order(n):
            order = [1]
            while len(order) < n:
                next_order = []
                target = len(order) * 2 + 1
                for x in order:
                    next_order.append(x)
                    next_order.append(target - x)
                order = next_order
            return order
        
        seeding_seeds = get_seeding_order(P)
        
        # Mapear os IDs reais para a lista de seeding (1-indexed seeds)
        players_by_seed = []
        for s in seeding_seeds:
            if s <= N:
                players_by_seed.append(players[s - 1])
            else:
                players_by_seed.append(None) # BYE
                
        # Limpar partidas anteriores para este evento caso já existam (idempotência)
        cursor.execute("DELETE FROM matches WHERE event_id = ?", (event_id,))

        # 4. Criar as partidas da árvore (do final para o início)
        rounds_count = int(math.log2(P))
        level_ids = {}
        
        # Nível 0 é a Final (1 partida)
        # Se rounds_count == 1 (ex: N=2 participantes), o Nível 0 é a própria rodada folha!
        if rounds_count == 1:
            player1 = players_by_seed[0]
            player2 = players_by_seed[1]
            status = "READY" if (player1 is not None and player2 is not None) else "WAITING"
        else:
            player1 = None
            player2 = None
            status = "WAITING"

        cursor.execute("""
            INSERT INTO matches (event_id, round_number, player1_id, player2_id, status)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, rounds_count, player1, player2, status))
        final_id = cursor.lastrowid
        level_ids[0] = [final_id]
        
        # Níveis subsequentes (de 1 até rounds_count - 1)
        for i in range(1, rounds_count):
            num_matches_in_level = 2 ** i
            level_ids[i] = []
            for j in range(num_matches_in_level):
                next_match_id = level_ids[i - 1][j // 2]
                next_slot = (j % 2) + 1
                
                player1 = None
                player2 = None
                status = "WAITING"
                
                if i == rounds_count - 1:
                    player1 = players_by_seed[2 * j]
                    player2 = players_by_seed[2 * j + 1]
                    status = "READY" if (player1 is not None and player2 is not None) else "WAITING"
                    
                cursor.execute("""
                    INSERT INTO matches (event_id, round_number, player1_id, player2_id, status, next_match_id, next_match_slot)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (event_id, rounds_count - i, player1, player2, status, next_match_id, next_slot))
                match_id = cursor.lastrowid
                level_ids[i].append(match_id)
                
        # Atualizar status do evento para 'IN_PROGRESS'
        cursor.execute("UPDATE events SET status = 'IN_PROGRESS' WHERE id = ?", (event_id,))
        self.db.conn.commit()
        
        # 5. Resolver BYEs no nível folha
        leaf_matches = level_ids[rounds_count - 1]
        for idx, m_id in enumerate(leaf_matches):
            p1 = players_by_seed[2 * idx]
            p2 = players_by_seed[2 * idx + 1]
            
            if p1 is None or p2 is None:
                winner = p1 if p1 is not None else p2
                if winner is not None:
                    cursor.execute("SELECT next_match_id, next_match_slot FROM matches WHERE id = ?", (m_id,))
                    row_m = cursor.fetchone()
                    next_id = row_m["next_match_id"]
                    n_slot = row_m["next_match_slot"]
                    
                    cursor.execute("""
                        UPDATE matches 
                        SET score1 = 0, score2 = 0, winner_id = ?, status = 'FINISHED'
                        WHERE id = ?
                    """, (winner, m_id))
                    self.db.conn.commit()
                    
                    if next_id:
                        self._promover_jogador(next_id, n_slot, winner)
                else:
                    cursor.execute("UPDATE matches SET status = 'FINISHED' WHERE id = ?", (m_id,))
                    self.db.conn.commit()
                    
        # 6. Alocar mesas disponíveis do evento para as primeiras partidas prontas (Round 1)
        cursor.execute("""
            SELECT id FROM matches 
            WHERE event_id = ? AND status = 'READY' AND station_id IS NULL
            ORDER BY id ASC
        """, (event_id,))
        ready_matches = cursor.fetchall()
        for rm in ready_matches:
            self._alocar_mesa_disponivel(rm["id"])
            
        self.db.conn.commit()
        return True, "Chave gerada e BYEs processados com sucesso."

    def _promover_jogador(self, next_match_id, slot, player_id):
        """
        Insere o vencedor na próxima partida de forma análoga a um ponteiro de dados.
        Garante que os flags de check-in sejam rigorosamente resetados para a nova partida.
        """
        cursor = self.db.conn.cursor()
        if slot == 1:
            cursor.execute("""
                UPDATE matches SET player1_id = ?, player1_checked_in = 0 WHERE id = ?
            """, (player_id, next_match_id))
        else:
            cursor.execute("""
                UPDATE matches SET player2_id = ?, player2_checked_in = 0 WHERE id = ?
            """, (player_id, next_match_id))
            
        cursor.execute("""
            SELECT player1_id, player2_id FROM matches WHERE id = ?
        """, (next_match_id,))
        next_match = cursor.fetchone()
        
        if next_match and next_match["player1_id"] and next_match["player2_id"]:
            cursor.execute("""
                UPDATE matches SET status = 'READY', player1_checked_in = 0, player2_checked_in = 0 WHERE id = ?
            """, (next_match_id,))
            print(f"[MOTOR] Próxima partida {next_match_id} está pronta para ser jogada.")
            self._alocar_mesa_disponivel(next_match_id)

    def _alocar_mesa_disponivel(self, match_id):
        """
        Busca uma mesa livre do evento atual e aloca para esta partida.
        """
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT event_id, station_id FROM matches WHERE id = ?", (match_id,))
        m = cursor.fetchone()
        if not m or m["station_id"]:
            return
        
        event_id = m["event_id"]
        cursor.execute("""
            SELECT id FROM stations 
            WHERE event_id = ? AND id NOT IN (
                SELECT DISTINCT station_id FROM matches 
                WHERE event_id = ? AND station_id IS NOT NULL AND status IN ('READY', 'PLAYING') AND id != ?
            ) ORDER BY id ASC LIMIT 1
        """, (event_id, event_id, match_id))
        row_station = cursor.fetchone()
        if row_station:
            station_id = row_station["id"]
            cursor.execute("""
                UPDATE matches SET station_id = ? WHERE id = ?
            """, (station_id, match_id))
            self.db.conn.commit()
            print(f"[MOTOR] Partida #{match_id} alocada automaticamente para a mesa #{station_id}.")
        else:
            print(f"[MOTOR] Nenhuma mesa livre no momento para a partida #{match_id}. Aguardará liberação.")

    def verificar_e_finalizar_torneio(self, event_id):
        """
        Verifica se todas as partidas do torneio foram concluídas (status = 'FINISHED').
        Caso positivo, atualiza o status do evento para 'FINISHED' e encerra o ciclo de vida.
        """
        if not event_id:
            return False
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'FINISHED' THEN 1 ELSE 0 END) as concluidas
            FROM matches
            WHERE event_id = ?
        """, (event_id,))
        row = cursor.fetchone()
        if row and row["total"] > 0 and row["total"] == row["concluidas"]:
            cursor.execute("UPDATE events SET status = 'FINISHED' WHERE id = ?", (event_id,))
            self.db.conn.commit()
            print(f"[MOTOR] [TORNEIO FINALIZADO] Todas as {row['total']} partidas do torneio #{event_id} foram concluídas com sucesso.")
            return True
        return False
            
if __name__ == "__main__":
    # Teste rápido de simulação de fluxo
    db = BancoDeDados()
    db.inicializar_banco()
    db.popular_dados_exemplo()
    
    motor = MotorDoTorneio(db)
    # Simula check-in do Bob na Mesa 1
    motor.registrar_checkin_rfid(tag_uid="E5F6A7B8", node_mac="AA:BB:CC:DD:EE:01")
    
    # Simula reporte de placar ciberfísico: Alice vence Bob por 2 a 1 na Mesa 1 (Estação 1)
    # Primeiro forçamos a partida 1 a entrar em PLAYING (já está)
    motor.reportar_placar_ciberfisico(station_id=1, score_player1=2, score_player2=1)
    
    db.fechar()
