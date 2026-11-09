import sys, os
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
import os
import sqlite3
import unittest
from database.db_manager import BancoDeDados
from motor.tournament_engine import MotorDoTorneio

class TestTournamentModule1Backend(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_autoreporter.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        self.db = BancoDeDados(self.db_path)
        self.db.inicializar_banco()
        self.motor = MotorDoTorneio(self.db)
        
        # Inserir alguns competidores iniciais
        self.p1 = self.db.cadastrar_jogador("Alice Silva", "Alice", "A1B2C3D4")
        self.p2 = self.db.cadastrar_jogador("Bob Santos", "Bob", "E5F6A7B8")
        self.p3 = self.db.cadastrar_jogador("Carlos Oliveira", "Carlos", "C9D0E1F2")
        self.p4 = self.db.cadastrar_jogador("Diana Souza", "Diana", "8A7B6C5D")

    def tearDown(self):
        self.db.fechar()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_fluxo_completo_torneio(self):
        print("\n--- [TEST] Iniciando fluxo de teste ciberfísico do Módulo 1 ---")
        
        # 1. Cadastrar Evento
        event_id = self.db.cadastrar_evento("PUCPR Championship 2026", "2026-07-24", "DRAFT")
        self.assertIsNotNone(event_id)
        print(f"[OK] Evento cadastrado em estado DRAFT com ID: {event_id}")

        # 2. Inscrever participantes no evento
        jogadores_inscritos = [self.p1, self.p2, self.p3, self.p4]
        self.db.atualizar_participantes_evento(event_id, jogadores_inscritos)
        
        parts = self.db.obter_participantes_evento(event_id)
        self.assertEqual(len(parts), 4)
        print(f"[OK] {len(parts)} competidores inscritos no evento.")

        # 3. Cadastrar Estações (Mesas) de teste
        cursor = self.db.conn.cursor()
        cursor.execute("INSERT INTO nodes (mac_address, nickname, type) VALUES ('MAC-MESA-A', 'Nó Mesa A', 'REPORTER')")
        cursor.execute("INSERT INTO nodes (mac_address, nickname, type) VALUES ('MAC-MESA-B', 'Nó Mesa B', 'REPORTER')")
        cursor.execute("INSERT INTO stations (id, event_id, name, node_mac) VALUES (1, ?, 'Mesa A', 'MAC-MESA-A')", (event_id,))
        cursor.execute("INSERT INTO stations (id, event_id, name, node_mac) VALUES (2, ?, 'Mesa B', 'MAC-MESA-B')", (event_id,))
        self.db.conn.commit()

        # 4. Inicializar chave (Engine)
        sucesso, msg = self.motor.inicializar_chave_torneio(event_id)
        self.assertTrue(sucesso)
        print(f"[OK] Chave gerada e iniciada: {msg}")

        # Verificar se o evento mudou para IN_PROGRESS
        ev = self.db.obter_evento(event_id)
        self.assertEqual(ev["status"], "IN_PROGRESS")
        print(f"[OK] Status do evento migrado para: {ev['status']}")

        # 5. Buscar partidas criadas no banco
        cursor.execute("SELECT id, player1_id, player2_id, status, station_id, next_match_id FROM matches WHERE event_id = ?", (event_id,))
        partidas = cursor.fetchall()
        # Para 4 jogadores, devemos ter 3 partidas (2 semifinais + 1 final)
        self.assertEqual(len(partidas), 3)
        print(f"[OK] {len(partidas)} partidas geradas no banco de dados SQLite.")

        # Identificar as partidas
        semis = [p for p in partidas if p["next_match_id"] is not None]
        final = [p for p in partidas if p["next_match_id"] is None][0]
        self.assertEqual(len(semis), 2)
        print(f"[OK] Estrutura da árvore validada: 2 Semifinais e 1 Final (ID {final['id']}).")

        # 6. Identificar a partida da Alice
        cursor.execute("""
            SELECT id, player1_id, player2_id, station_id, status 
            FROM matches 
            WHERE event_id = ? AND (player1_id = ? OR player2_id = ?)
        """, (event_id, self.p1, self.p1))
        alice_match = cursor.fetchone()
        self.assertIsNotNone(alice_match)
        alice_match_id = alice_match["id"]
        
        # Obter o oponente da Alice nesta partida
        opp_id = alice_match["player2_id"] if alice_match["player1_id"] == self.p1 else alice_match["player1_id"]
        
        # Obter a tag RFID do oponente
        cursor.execute("SELECT tag_uid FROM rfid_tags WHERE player_id = ?", (opp_id,))
        opp_tag = cursor.fetchone()["tag_uid"]
        
        # Alocar Mesa A (estação 1) para a partida da Alice e forçar status READY
        cursor.execute("UPDATE matches SET station_id = 1, status = 'READY' WHERE id = ?", (alice_match_id,))
        self.db.conn.commit()
        
        station_mac = "MAC-MESA-A"
        station_id = 1

        # 7. Simular Check-in RFID na Mesa A (Alice vs Oponente)
        # Alice aproxima RFID na Mesa A
        sucesso, msg = self.motor.registrar_checkin_rfid("A1B2C3D4", station_mac)
        self.assertTrue(sucesso)
        self.assertIn("Aguardando", msg)
        print(f"[OK] Check-in RFID Alice (Mesa A): {msg}")

        # Oponente aproxima RFID na Mesa A
        sucesso, msg = self.motor.registrar_checkin_rfid(opp_tag, station_mac)
        self.assertTrue(sucesso)
        self.assertIn("iniciada", msg)
        print(f"[OK] Check-in RFID Oponente {opp_id} (Mesa A) -> Partida INICIADA: {msg}")

        # Verificar se status da partida mudou para 'PLAYING'
        cursor.execute("SELECT status FROM matches WHERE id = ?", (alice_match_id,))
        p1_st = cursor.fetchone()["status"]
        self.assertEqual(p1_st, "PLAYING")
        print(f"[OK] Status da Partida {alice_match_id} atualizado para: {p1_st}")

        # 8. Reportar Placar e Chancelar (Alice vence por 2x1)
        # Web App envia placar
        sucesso, msg = self.motor.iniciar_reporte_placar(alice_match_id, 2, 1)
        self.assertTrue(sucesso)
        print(f"[OK] Reporte via Web App (Alice 2 x 1 Oponente): {msg}")

        # Alice chancela com tag RFID na Mesa A
        sucesso, msg = self.motor.confirmar_placar_rfid("A1B2C3D4", "MAC-MESA-A")
        self.assertTrue(sucesso)
        print(f"[OK] Chancela RFID Alice (Mesa A) -> Partida FINALIZADA: {msg}")

        # Verificar se a partida semifinal foi concluída e o vencedor foi promovido para a final
        cursor.execute("SELECT status, winner_id FROM matches WHERE id = ?", (alice_match_id,))
        p1_res = cursor.fetchone()
        self.assertEqual(p1_res["status"], "FINISHED")
        self.assertEqual(p1_res["winner_id"], self.p1) # Alice venceu
        print(f"[OK] Semifinal {alice_match_id} concluída. Vencedora: Alice (#ID {p1_res['winner_id']}).")

        # Verificar se Alice foi promovida para a final
        cursor.execute("SELECT player1_id, player2_id FROM matches WHERE id = ?", (final["id"],))
        fin_players = cursor.fetchone()
        self.assertIn(self.p1, (fin_players["player1_id"], fin_players["player2_id"]))
        print(f"[OK] Promoção automática executada: Alice avançou para a partida Final (#ID {final['id']}).")

        # 9. Clonar Evento
        clone_id = self.db.clonar_evento(event_id, "PUCPR Championship 2026 - Edição II", "2026-08-24")
        self.assertIsNotNone(clone_id)
        print(f"[OK] Clonagem de Evento concluída. Novo Evento ID: {clone_id}")
        
        clone_parts = self.db.obter_participantes_evento(clone_id)
        self.assertEqual(len(clone_parts), 4)
        print(f"[OK] Evento Clonado possui os mesmos {len(clone_parts)} competidores.")

        # 10. Concluir todas as partidas restantes e validar transição para status 'FINISHED'
        cursor.execute("SELECT id FROM matches WHERE event_id = ? AND status != 'FINISHED'", (event_id,))
        restantes = cursor.fetchall()
        for rm in restantes:
            cursor.execute("UPDATE matches SET status = 'FINISHED', score1 = 2, score2 = 0, winner_id = ? WHERE id = ?", (self.p1, rm["id"]))
        self.db.conn.commit()
        self.motor.verificar_e_finalizar_torneio(event_id)
        
        cursor.execute("SELECT status FROM events WHERE id = ?", (event_id,))
        ev_final = cursor.fetchone()
        self.assertEqual(ev_final["status"], "FINISHED")
        print(f"[OK] Ciclo de vida encerrado: Evento #{event_id} atualizado automaticamente para status FINISHED!")

        print("--- [TEST] Todos os testes de backend do Módulo 1 passaram com sucesso! ---")

if __name__ == "__main__":
    unittest.main()
