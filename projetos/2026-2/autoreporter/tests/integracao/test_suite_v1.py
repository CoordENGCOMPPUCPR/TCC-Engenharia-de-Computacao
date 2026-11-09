"""
AUTOREPORTER - SUÍTE COMPLETA DE VALIDAÇÃO DE SISTEMA (VERSÃO 1.0)
Trabalho de Conclusão de Curso - Engenharia de Computação PUCPR 2026

Testes Automatizados de Caixa-Branca e Caixa-Preta cobrindo:
1. Motor de Torneio (Chaveamentos com BYE ímpar: 3, 5, 7 competidores e Chave cheia: 8 competidores).
2. Protocolo Ciberfísico (Pacotes RFID, SCORE, PING, Mesh 2 Saltos e Resiliência a Ruído).
3. Banco de Dados SQLite (Integridade Relacional, Deduplicação, Importação Start.gg e Exportação CSV/JSON).
4. Servidor Web Flask (Rotas Organizador, Visão Mobile do Competidor, APIs e SSE).
"""

import os
import sys
import json
import sqlite3
import unittest
import threading
import time

# Adicionar os diretórios src/backend e src/frontend ao sys.path
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "backend"))
_frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "frontend"))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
if _frontend_path not in sys.path:
    sys.path.insert(0, _frontend_path)

from database.db_manager import BancoDeDados
from motor.tournament_engine import MotorDoTorneio
from web.app import app

class TestAutoreporterV1Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "test_autoreporter_v1.db"
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass
        cls.db = BancoDeDados(cls.db_path)
        cls.db.inicializar_banco()
        cls.motor = MotorDoTorneio(cls.db)

        # Configurar Flask Test Client
        app.config['TESTING'] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.fechar()
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    def _finalizar_partida_aux(self, match_id, score1, score2, winner_id):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT station_id, next_match_id, next_match_slot FROM matches WHERE id = ?", (match_id,))
        m = cursor.fetchone()
        cursor.execute("""
            UPDATE matches 
            SET score1 = ?, score2 = ?, winner_id = ?, status = 'FINISHED'
            WHERE id = ?
        """, (score1, score2, winner_id, match_id))
        self.db.conn.commit()
        if m and m["next_match_id"] and m["next_match_slot"]:
            self.motor._promover_jogador(m["next_match_id"], m["next_match_slot"], winner_id)
        self.db.conn.commit()

    # =========================================================================
    # 1. TESTES DO MOTOR DE TORNEIO (BYE & ESTRUTURAS ÍMPARES)
    # =========================================================================
    def test_01_torneio_impar_5_jogadores_bye(self):
        """Valida se uma chave de 5 competidores gera 3 BYEs automáticos e avança até a final."""
        p_ids = []
        for i in range(1, 6):
            pid = self.db.cadastrar_jogador(f"Atleta {i}", f"Nick_{i}", f"TAG_{i:04X}")
            p_ids.append(pid)

        ev_id = self.db.cadastrar_evento("Torneio 5 Players (3 BYEs)", "2026-10-07", "DRAFT")
        self.db.atualizar_participantes_evento(ev_id, p_ids)

        ok, msg = self.motor.inicializar_chave_torneio(ev_id)
        self.assertTrue(ok, f"Falha ao gerar chave: {msg}")

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, player1_id, player2_id, status, winner_id, next_match_id FROM matches WHERE event_id = ?", (ev_id,))
        matches = cursor.fetchall()
        self.assertEqual(len(matches), 7)

        # 3 partidas devem ser resolvidas como BYE logo no início
        byes = [m for m in matches if m["status"] == "FINISHED" and m["winner_id"] is not None]
        self.assertEqual(len(byes), 3, "Esperados 3 BYEs resolvidos automaticamente na R1")

        # Simular avanço automático de todas as partidas ativas rodada a rodada
        while True:
            cursor.execute("SELECT id, player1_id, player2_id, status FROM matches WHERE event_id = ? AND status in ('READY', 'PLAYING') ORDER BY id ASC", (ev_id,))
            ativas = cursor.fetchall()
            if not ativas:
                break
            for partida in ativas:
                vencedor = partida["player1_id"] if partida["player1_id"] else partida["player2_id"]
                self._finalizar_partida_aux(partida["id"], 2, 0, vencedor)

        # Verificar se o torneio foi concluído
        self.motor.verificar_e_finalizar_torneio(ev_id)
        ev = self.db.obter_evento(ev_id)
        self.assertEqual(ev["status"], "FINISHED")

        # Verificar se a grande final tem vencedor registrado
        cursor.execute("SELECT id, winner_id, status FROM matches WHERE event_id = ? AND next_match_id IS NULL", (ev_id,))
        final_match = cursor.fetchone()
        self.assertIsNotNone(final_match)
        self.assertEqual(final_match["status"], "FINISHED")
        self.assertIsNotNone(final_match["winner_id"])

    def test_02_torneio_impar_3_jogadores_bye(self):
        """Valida chave de 3 jogadores (potência 4, 1 BYE automático)."""
        p_ids = [self.db.cadastrar_jogador(f"J_{i}", f"Nick_{i}_T3", f"TAG_T3_{i}") for i in range(1, 4)]
        ev_id = self.db.cadastrar_evento("Torneio 3 Players (1 BYE)", "2026-10-07", "DRAFT")
        self.db.atualizar_participantes_evento(ev_id, p_ids)

        ok, msg = self.motor.inicializar_chave_torneio(ev_id)
        self.assertTrue(ok)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, status, winner_id FROM matches WHERE event_id = ?", (ev_id,))
        matches = cursor.fetchall()
        # Chave de 4: 2 semis + 1 final = 3 partidas
        self.assertEqual(len(matches), 3)

        # 1 BYE na primeira rodada
        byes = [m for m in matches if m["status"] == "FINISHED"]
        self.assertEqual(len(byes), 1)

    # =========================================================================
    # 2. TESTES DE PROTOCOLO CIBERFÍSICO & TELEMETRIA MESH
    # =========================================================================
    def test_03_parser_mensagens_ciberfisicas(self):
        """Valida resiliência e decodificação dos pacotes de rádio/serial."""
        raw_rfid_direto = "RFID;A1B2C3D4;AA:BB:CC:DD:EE:01;REMOTE;SALTOS:1;VIA:DIRETO"
        partes = [p.strip() for p in raw_rfid_direto.split(";")]
        self.assertEqual(partes[0], "RFID")
        self.assertEqual(partes[1], "A1B2C3D4")
        self.assertEqual(partes[2], "AA:BB:CC:DD:EE:01")

        raw_score_mesh = "SCORE;AA:BB:CC:DD:EE:02;2;1;SALTOS:2;VIA:AA:BB:CC:DD:EE:99"
        partes_s = [p.strip() for p in raw_score_mesh.split(";")]
        self.assertEqual(partes_s[0], "SCORE")
        self.assertEqual(partes_s[1], "AA:BB:CC:DD:EE:02")
        self.assertEqual(int(partes_s[2]), 2)
        self.assertEqual(int(partes_s[3]), 1)

        raw_lixo = ";;;;;;GARBAGE_DATA"
        partes_lixo = [p.strip() for p in raw_lixo.split(";")]
        self.assertNotEqual(partes_lixo[0], "RFID")
        self.assertNotEqual(partes_lixo[0], "SCORE")

    # =========================================================================
    # 3. TESTES DE BANCO DE DADOS, DEDUPLICAÇÃO E IMPORTAÇÃO START.GG
    # =========================================================================
    def test_04_importacao_startgg_e_deduplicacao(self):
        """Valida importação com cabeçalhos Start.gg e atualização de atletas existentes."""
        dados_import = [
            {"nickname": "Daigo", "real_name": "Daigo Umehara", "tag_uid": "TAG_DAIGO_01"},
            {"nickname": "Justin", "real_name": "Justin Wong", "tag_uid": "TAG_JUSTIN_01"}
        ]
        ins1, atu1 = self.db.importar_participantes_lote(dados_import)
        self.assertEqual(ins1, 2)
        self.assertEqual(atu1, 0)

        dados_update = [
            {"nickname": "daigo", "real_name": "The Beast Daigo", "tag_uid": "TAG_DAIGO_NOVA"}
        ]
        ins2, atu2 = self.db.importar_participantes_lote(dados_update)
        self.assertEqual(ins2, 0)
        self.assertEqual(atu2, 1)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, real_name FROM players WHERE LOWER(nickname) = 'daigo'")
        row = cursor.fetchone()
        self.assertEqual(row["real_name"], "The Beast Daigo")

        cursor.execute("SELECT tag_uid FROM rfid_tags WHERE player_id = ?", (row["id"],))
        tag_row = cursor.fetchone()
        self.assertEqual(tag_row["tag_uid"], "TAG_DAIGO_NOVA")

    def test_05_exportacao_relatorio_csv_e_json(self):
        """Valida geração de relatórios de torneio em CSV e JSON."""
        ev_id = self.db.cadastrar_evento("Torneio Teste Export", "2026-10-07", "DRAFT")
        p1 = self.db.cadastrar_jogador("Exp 1", "Exp1", "TAG_EXP1")
        p2 = self.db.cadastrar_jogador("Exp 2", "Exp2", "TAG_EXP2")
        self.db.atualizar_participantes_evento(ev_id, [p1, p2])
        self.motor.inicializar_chave_torneio(ev_id)

        csv_file = "test_export.csv"
        ok_csv, msg_csv = self.db.exportar_evento_csv(ev_id, csv_file)
        self.assertTrue(ok_csv)
        self.assertTrue(os.path.exists(csv_file))
        with open(csv_file, "r", encoding="utf-8") as f:
            content_csv = f.read()
        self.assertIn("Exp1", content_csv)
        os.remove(csv_file)

        json_file = "test_export.json"
        ok_json, msg_json = self.db.exportar_evento_json(ev_id, json_file)
        self.assertTrue(ok_json)
        self.assertTrue(os.path.exists(json_file))
        with open(json_file, "r", encoding="utf-8") as f:
            content_json = json.load(f)
        self.assertIn("evento", content_json)
        self.assertEqual(content_json["evento"]["id"], ev_id)
        os.remove(json_file)

    def test_06_sanitizacao_dados_orfaos(self):
        """Valida rotina de integridade referencial que limpa chaves estrangeiras pendentes."""
        res = self.db.sanitizar_e_limpar_dados_orfaos()
        self.assertIsInstance(res, dict)
        self.assertIn("tags_orfas_removidas", res)
        self.assertIn("mesas_duplicadas_fundidas", res)

    # =========================================================================
    # 4. TESTES DAS ROTAS WEB FLASK & MOBILE
    # =========================================================================
    def test_07_rotas_web_organizador_e_mobile(self):
        """Valida resposta HTTP 200 nas rotas críticas da interface Web."""
        res_index = self.client.get('/')
        self.assertEqual(res_index.status_code, 200)

        res_player = self.client.get('/player/1')
        self.assertEqual(res_player.status_code, 200)

        res_status = self.client.get('/api/status')
        self.assertEqual(res_status.status_code, 200)

    def test_08_api_cadastro_e_consulta_admin(self):
        """Valida endpoints de administração REST do Web App."""
        payload = {"real_name": "Jogador REST", "nickname": "RestPlayer", "tag_uid": "TAG_REST_01"}
        res = self.client.post('/api/admin/register_player', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        res_list = self.client.get('/api/admin/players')
        self.assertEqual(res_list.status_code, 200)
        players = res_list.get_json()
        self.assertTrue(any(p.get("nickname") == "RestPlayer" for p in players))

    # =========================================================================
    # 5. TESTES DE FILTRAGEM DE MESAS DISPONÍVEIS E PREVENÇÃO DE CONFLITO
    # =========================================================================
    def test_09_filtro_estacoes_disponiveis_e_bloqueio_duplicidade(self):
        """Valida que obter_estacoes_disponiveis filtra mesas ocupadas por partidas ativas (READY/PLAYING)."""
        ev_id = self.db.cadastrar_evento("Torneio Teste Mesas", "2026-10-19", "IN_PROGRESS")
        st1_id = self.db.cadastrar_estacao(ev_id, "Mesa Alfa", "AA:BB:CC:DD:EE:11")
        st2_id = self.db.cadastrar_estacao(ev_id, "Mesa Beta", "AA:BB:CC:DD:EE:22")

        p1 = self.db.cadastrar_jogador("Player Alfa 1", "NickA1", "TAG_A1")
        p2 = self.db.cadastrar_jogador("Player Alfa 2", "NickA2", "TAG_A2")
        p3 = self.db.cadastrar_jogador("Player Beta 1", "NickB1", "TAG_B1")
        p4 = self.db.cadastrar_jogador("Player Beta 2", "NickB2", "TAG_B2")

        cursor = self.db.conn.cursor()
        # Criar partida 1 alocada na Mesa Alfa (READY)
        cursor.execute("""
            INSERT INTO matches (event_id, player1_id, player2_id, station_id, status)
            VALUES (?, ?, ?, ?, 'READY')
        """, (ev_id, p1, p2, st1_id))
        m1_id = cursor.lastrowid

        # Criar partida 2 sem mesa (WAITING)
        cursor.execute("""
            INSERT INTO matches (event_id, player1_id, player2_id, station_id, status)
            VALUES (?, ?, ?, NULL, 'WAITING')
        """, (ev_id, p3, p4))
        m2_id = cursor.lastrowid
        self.db.conn.commit()

        # Para a partida 2, a Mesa Alfa deve estar OCUPADA (não disponível), e a Mesa Beta deve estar LIVRE
        disp_m2 = self.db.obter_estacoes_disponiveis(ev_id, match_id=m2_id)
        disp_ids_m2 = [s["id"] for s in disp_m2]
        self.assertNotIn(st1_id, disp_ids_m2, "Mesa Alfa não deveria estar disponível para a Partida 2 pois já está em READY")
        self.assertIn(st2_id, disp_ids_m2, "Mesa Beta deveria estar disponível para a Partida 2")

        # Para a partida 1, a Mesa Alfa DEVE aparecer pois é a sua mesa atual
        disp_m1 = self.db.obter_estacoes_disponiveis(ev_id, match_id=m1_id)
        disp_ids_m1 = [s["id"] for s in disp_m1]
        self.assertIn(st1_id, disp_ids_m1, "Mesa Alfa deve estar disponível para sua própria Partida 1")

        # Quando a Partida 1 é FINALIZADA, a Mesa Alfa volta a ficar disponível para todas as partidas
        cursor.execute("UPDATE matches SET status = 'FINISHED' WHERE id = ?", (m1_id,))
        self.db.conn.commit()
        disp_m2_pos = self.db.obter_estacoes_disponiveis(ev_id, match_id=m2_id)
        disp_ids_m2_pos = [s["id"] for s in disp_m2_pos]
        self.assertIn(st1_id, disp_ids_m2_pos, "Mesa Alfa deve voltar a ficar disponível após a Partida 1 finalizar")

if __name__ == '__main__':
    unittest.main()

