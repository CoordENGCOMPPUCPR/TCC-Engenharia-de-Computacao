import sys, os
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
import sys
import os
import time
import json
import sqlite3
from flask import Flask, render_template, jsonify, request, Response, g

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor.tournament_engine import MotorDoTorneio
from gateway.serial_driver import AdaptadorCoordenador

app = Flask(__name__)
user_dir = os.path.join(os.path.expanduser("~"), ".autoreporter")
os.makedirs(user_dir, exist_ok=True)
db_path = os.path.join(user_dir, "autoreporter.db")

class RequestDBWrapper:
    def __init__(self, conn):
        self.conn = conn

def on_serial_message(msg):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    motor = MotorDoTorneio(RequestDBWrapper(conn))
    try:
        partes = msg.strip().split(";")
        if partes[0] == "RFID":
            tag_uid = partes[1]
            node_mac = partes[2]
            sucesso, resultado = motor.confirmar_placar_rfid(tag_uid, node_mac)
            if not sucesso:
                sucesso, resultado = motor.registrar_checkin_rfid(tag_uid, node_mac)
            print(f"[SERIAL CALLBACK] RFID Tap Result: {resultado}")
        elif partes[0] == "SCORE":
            node_mac = partes[1]
            s1 = int(partes[2])
            s2 = int(partes[3])
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM stations WHERE node_mac = ?", (node_mac,))
            row = cursor.fetchone()
            if row:
                station_id = row["id"]
                motor.reportar_placar_ciberfisico(station_id, s1, s2)
                print(f"[SERIAL CALLBACK] Placar {s1}x{s2} na mesa {station_id}")
    except Exception as e:
        print(f"[SERIAL CALLBACK ERROR] {e}")
    finally:
        conn.close()

# Permite que uma aplicação externa (como gui_app.py) compartilhe o driver serial existente
driver = None

def get_or_create_driver():
    global driver
    if driver is None:
        driver = AdaptadorCoordenador(porta_com=None, callback_mensagem=on_serial_message, mock=False)
        driver.start()
    return driver
def get_db():
    if 'db_conn' not in g:
        g.db_conn = sqlite3.connect(db_path)
        g.db_conn.row_factory = sqlite3.Row
        g.db_conn.execute("PRAGMA foreign_keys = ON;")
    return g.db_conn

@app.teardown_appcontext
def teardown_db(exception):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        db_conn.close()

@app.route("/")
def index():
    """Rota raiz: Informa que o acesso Web é exclusivo para competidores via seu ID."""
    host_atual = request.host
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Autoreporter - Acesso ao Competidor</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;800&display=swap" rel="stylesheet">
        <style>
            body {{
                background-color: #09090b;
                color: #f4f4f5;
                font-family: 'Outfit', sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 1.5rem;
                text-align: center;
            }}
            .card {{
                background: #121214;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 2.5rem;
                max-width: 480px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            }}
            h1 {{ font-size: 1.8rem; font-weight: 800; text-transform: uppercase; margin-bottom: 0.5rem; }}
            p {{ color: #a1a1aa; font-size: 0.95rem; margin-bottom: 1.5rem; line-height: 1.5; }}
            .badge {{
                display: inline-block;
                background: #27272a;
                color: #f4f4f5;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                font-weight: 700;
                font-size: 0.85rem;
                letter-spacing: 0.05em;
                margin-bottom: 1rem;
            }}
            .code-box {{
                background: #000;
                border: 1px dashed #3f3f46;
                color: #e4e4e7;
                padding: 0.75rem;
                border-radius: 6px;
                font-family: monospace;
                font-size: 1rem;
                margin-top: 1rem;
                word-break: break-all;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">AUTOREPORTER CPS</div>
            <h1>Área do Competidor</h1>
            <p>O acesso administrativo ao torneio é realizado exclusivamente através do aplicativo Desktop executável (<strong>Autoreporter.exe</strong>).</p>
            <p>Para acessar sua área pessoal de jogador, utilize a URL com o seu <strong>ID numérico</strong> ou <strong>Tag RFID física</strong>:</p>
            <div class="code-box">http://{host_atual}/player/&lt;seu_id_ou_tag&gt;</div>
            <p style="margin-top: 1rem; font-size: 0.85rem; color: #a1a1aa;">
                Exemplos:<br>
                Por ID: <a href="/player/1" style="color: #38bdf8; font-weight: bold;">/player/1</a> (Alice Silva)<br>
                Por Tag RFID: <a href="/player/B633BC06" style="color: #38bdf8; font-weight: bold;">/player/B633BC06</a> (Cartão da Alice)
            </p>
        </div>
    </body>
    </html>
    """, 200

def resolve_player_by_identifier(conn, identifier):
    """
    Resolve um identificador para os dados do competidor no banco SQLite.
    Prioridade:
    1. Busca por tag_uid na tabela rfid_tags (Case-insensitive, ex: 'B633BC06')
    2. Se for número inteiro, busca por players.id (ex: '1')
    Retorna: (player_row, tag_uid) ou ('UNASSIGNED', tag_uid) ou (None, None)
    """
    ident_str = str(identifier).strip()
    cursor = conn.cursor()
    
    # 1. Tenta resolver por tag_uid na tabela rfid_tags
    cursor.execute("""
        SELECT p.id, p.real_name, p.nickname, t.tag_uid
        FROM rfid_tags t
        JOIN players p ON t.player_id = p.id
        WHERE UPPER(t.tag_uid) = UPPER(?)
    """, (ident_str,))
    player = cursor.fetchone()
    if player:
        return player, player["tag_uid"]

    # 1.1 Tag RFID existe no banco, mas ainda não está associada a nenhum competidor
    cursor.execute("SELECT tag_uid FROM rfid_tags WHERE UPPER(tag_uid) = UPPER(?)", (ident_str,))
    unassigned = cursor.fetchone()
    if unassigned:
        return "UNASSIGNED", unassigned["tag_uid"]
        
    # 2. Se for numérico, tenta resolver diretamente por players.id
    if ident_str.isdigit():
        p_id = int(ident_str)
        cursor.execute("""
            SELECT p.id, p.real_name, p.nickname,
                   (SELECT tag_uid FROM rfid_tags WHERE player_id = p.id LIMIT 1) as tag_uid
            FROM players p
            WHERE p.id = ?
        """, (p_id,))
        player = cursor.fetchone()
        if player:
            return player, player["tag_uid"]
            
    return None, None

@app.route("/<string:identifier>")
@app.route("/player/<string:identifier>")
def player_view(identifier):
    """Página do competidor com suporte a UID de Tag RFID ou ID numérico."""
    # Ignora rotas do sistema
    if identifier.lower() in ("api", "static", "favicon.ico"):
        return "Não encontrado", 404
        
    conn = get_db()
    player, tag_uid = resolve_player_by_identifier(conn, identifier)
    
    if player == "UNASSIGNED":
        return f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Autoreporter - Crachá RFID Não Vinculado</title>
            <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@700&family=Rajdhani:wght@600&display=swap" rel="stylesheet">
            <style>
                body {{ background: #0B0E14; color: #F8FAFC; font-family: 'Rajdhani', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 1.5rem; text-align: center; }}
                .card {{ background: #141922; border: 1px solid #2DB5F6; border-radius: 8px; padding: 2.5rem; max-width: 440px; box-shadow: 0 0 25px rgba(45, 181, 246, 0.2); }}
                h2 {{ font-family: 'Chakra Petch', sans-serif; color: #F59E0B; text-transform: uppercase; margin-top: 0; }}
                .uid-box {{ background: #07090D; border: 1px dashed #2DB5F6; padding: 0.75rem 1rem; font-family: monospace; font-size: 1.3rem; color: #2DB5F6; letter-spacing: 0.1em; border-radius: 4px; margin: 1.5rem 0; }}
                p {{ color: #8A99AD; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>🏷️ Crachá RFID Reconhecido</h2>
                <div class="uid-box">{tag_uid}</div>
                <p>Este cartão RFID físico está registrado no inventário, porém <strong>ainda não foi vinculado</strong> a nenhum competidor.</p>
                <p style="font-size: 0.9rem; color: #64748B;">Apresente este cartão na mesa de recepção/credenciamento para associá-lo ao seu nome no torneio.</p>
            </div>
        </body>
        </html>
        """, 200

    if not player:
        return f"Competidor ou Tag RFID '{identifier}' não encontrado no sistema.", 404
        
    player_id = player["id"]
    cursor = conn.cursor()
    
    # Busca os eventos em que o jogador participa ou participou
    cursor.execute("""
        SELECT DISTINCT e.id, e.name, e.date, e.status
        FROM events e
        JOIN event_players ep ON e.id = ep.event_id
        WHERE ep.player_id = ?
        ORDER BY e.id DESC
    """, (player_id,))
    events = [dict(row) for row in cursor.fetchall()]
    
    # Caso não tenha registros em event_players, busca todos os eventos ativos para fallback
    if not events:
        cursor.execute("SELECT id, name, date, status FROM events ORDER BY id DESC")
        events = [dict(row) for row in cursor.fetchall()]
        
    return render_template("player.html", 
                           player_id=player_id, 
                           player_name=player["nickname"] or player["real_name"],
                           tag_uid=tag_uid,
                           events=events)


def get_player_full_state(conn, player_id):
    """Constrói o estado em tempo real do competidor com suporte resiliente a LEFT JOIN stations."""
    cursor = conn.cursor()
    # 1. Buscar se há partida ativa ('READY' ou 'PLAYING')
    cursor.execute("""
        SELECT m.id, s.name as station_name, s.node_mac,
               p1.nickname as player1_name, p2.nickname as player2_name,
               m.player1_id, m.player2_id,
               m.player1_checked_in, m.player2_checked_in,
               m.pending_score1, m.pending_score2,
               m.score_reporter_id, m.score_conflict,
               m.status
        FROM matches m
        LEFT JOIN stations s ON m.station_id = s.id
        LEFT JOIN players p1 ON m.player1_id = p1.id
        LEFT JOIN players p2 ON m.player2_id = p2.id
        WHERE (m.player1_id = ? OR m.player2_id = ?) AND m.status IN ('READY', 'PLAYING')
        ORDER BY m.id DESC LIMIT 1
    """, (player_id, player_id))
    partida = cursor.fetchone()
    
    # 2. Buscar histórico completo de resultados do jogador
    cursor.execute("""
        SELECT m.id, ev.name as event_name, ev.status as event_status,
               p1.nickname as p1_name, p2.nickname as p2_name,
               m.score1, m.score2, w.nickname as winner_name,
               m.status as match_status
        FROM matches m
        JOIN events ev ON m.event_id = ev.id
        LEFT JOIN players p1 ON m.player1_id = p1.id
        LEFT JOIN players p2 ON m.player2_id = p2.id
        LEFT JOIN players w ON m.winner_id = w.id
        WHERE (m.player1_id = ? OR m.player2_id = ?) AND m.status = 'FINISHED'
        ORDER BY m.id DESC
    """, (player_id, player_id))
    historico = [dict(row) for row in cursor.fetchall()]
    ultimo_dict = historico[0] if historico else None

    if partida:
        st_name = partida["station_name"] or "Aguardando Mesa"
        return {
            "has_match": True,
            "match_id": partida["id"],
            "station_name": st_name,
            "node_mac": partida["node_mac"] or "",
            "player1": partida["player1_name"] or "A Definir",
            "player2": partida["player2_name"] or "A Definir",
            "player1_id": partida["player1_id"],
            "player2_id": partida["player2_id"],
            "player1_checked_in": bool(partida["player1_checked_in"]),
            "player2_checked_in": bool(partida["player2_checked_in"]),
            "pending_score1": partida["pending_score1"],
            "pending_score2": partida["pending_score2"],
            "score_reporter_id": partida["score_reporter_id"],
            "score_conflict": bool(partida["score_conflict"]),
            "status": partida["status"],
            "preview_match": None,
            "last_result": ultimo_dict,
            "history": historico
        }
    else:
        # 3. Buscar prévia da próxima partida agendada na chave ('WAITING' ou 'READY')
        cursor.execute("""
            SELECT m.id, m.round_number, m.status, m.player1_id, m.player2_id,
                   s.name as station_name,
                   p1.nickname as p1_name, p2.nickname as p2_name
            FROM matches m
            LEFT JOIN stations s ON m.station_id = s.id
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            WHERE (m.player1_id = ? OR m.player2_id = ?)
              AND m.status IN ('WAITING', 'READY')
            ORDER BY m.round_number ASC, m.id ASC LIMIT 1
        """, (player_id, player_id))
        prox = cursor.fetchone()
        preview_match = None
        if prox:
            is_p1 = (prox["player1_id"] == player_id)
            opp_nick = prox["p2_name"] if is_p1 else prox["p1_name"]
            st_name = prox["station_name"] or "Aguardando mesa livre"
            preview_match = {
                "match_id": prox["id"],
                "round_number": prox["round_number"],
                "opponent_name": opp_nick or "A determinar",
                "station_name": st_name
            }

        return {
            "has_match": False,
            "preview_match": preview_match,
            "last_result": ultimo_dict,
            "history": historico
        }

@app.route("/api/player_state/<string:identifier>")
def api_player_state(identifier):
    """Endpoint REST imediato para recuperação de estado em tempo real (0 delay)."""
    conn = get_db()
    player, _ = resolve_player_by_identifier(conn, identifier)
    if not player or player == "UNASSIGNED":
        return jsonify({"has_match": False, "error": "Competidor não encontrado"}), 404
    state = get_player_full_state(conn, player["id"])
    return jsonify(state)

@app.route("/api/stream/<string:identifier>")
def api_stream(identifier):
    """Canal Server-Sent Events (SSE) para atualização reativa do jogador via UID ou ID."""
    def event_stream():
        local_conn = sqlite3.connect(db_path, timeout=5.0)
        local_conn.row_factory = sqlite3.Row
        local_conn.execute("PRAGMA foreign_keys = ON;")
        
        player, _ = resolve_player_by_identifier(local_conn, identifier)
        if not player or player == "UNASSIGNED":
            local_conn.close()
            return
            
        player_id = player["id"]
        last_state_json = ""
        
        try:
            while True:
                state = get_player_full_state(local_conn, player_id)
                state_json = json.dumps(state)
                if state_json != last_state_json:
                    last_state_json = state_json
                    yield f"data: {state_json}\n\n"
                else:
                    # Envia ping de heartbeat para detectar desconexão do cliente imediatamente
                    yield ": ping\n\n"
                    
                time.sleep(1)
        except (GeneratorExit, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            local_conn.close()
            
    resp = Response(event_stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp

@app.route("/api/stream/admin")
def api_stream_admin():
    """Canal SSE para enviar atualizações de todas as mesas e partidas para o painel de admin."""
    def event_stream():
        local_conn = sqlite3.connect(db_path, timeout=5.0)
        local_conn.row_factory = sqlite3.Row
        local_conn.execute("PRAGMA foreign_keys = ON;")
        local_cursor = local_conn.cursor()
        
        last_state_json = ""
        
        try:
            while True:
                # 1. Buscar status de todas as estações (mesas)
                local_cursor.execute("""
                    SELECT s.id, s.name, s.node_mac, m.id as match_id, 
                           p1.nickname as player1, p2.nickname as player2, m.status,
                           m.player1_checked_in, m.player2_checked_in,
                           m.pending_score1, m.pending_score2
                    FROM stations s
                    LEFT JOIN matches m ON s.id = m.station_id AND m.status IN ('READY', 'PLAYING')
                    LEFT JOIN players p1 ON m.player1_id = p1.id
                    LEFT JOIN players p2 ON m.player2_id = p2.id
                """)
                mesas = [dict(row) for row in local_cursor.fetchall()]
                
                for m in mesas:
                    if m["match_id"]:
                        m["player1_checked_in"] = bool(m["player1_checked_in"])
                        m["player2_checked_in"] = bool(m["player2_checked_in"])
                
                # 2. Buscar todas as partidas
                local_cursor.execute("""
                    SELECT m.id, p1.nickname as player1, p2.nickname as player2, 
                           m.score1, m.score2, m.status, w.nickname as winner,
                           m.player1_id, m.player2_id, m.winner_id,
                           m.player1_checked_in, m.player2_checked_in,
                           m.pending_score1, m.pending_score2
                    FROM matches m
                    LEFT JOIN players p1 ON m.player1_id = p1.id
                    LEFT JOIN players p2 ON m.player2_id = p2.id
                    LEFT JOIN players w ON m.winner_id = w.id
                """)
                partidas = [dict(row) for row in local_cursor.fetchall()]
                
                state = {
                    "mesas": mesas,
                    "partidas": partidas,
                    "coordinator_connected": driver.connected if driver else False
                }
                
                state_json = json.dumps(state)
                if state_json != last_state_json:
                    last_state_json = state_json
                    yield f"data: {state_json}\n\n"
                else:
                    # Heartbeat ping
                    yield ": ping\n\n"
                    
                time.sleep(1)
        except (GeneratorExit, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            local_conn.close()
            
    resp = Response(event_stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp

@app.route("/api/report_score", methods=["POST"])
def report_score():
    """Submete a pontuação informada pelo competidor e aguarda chancela."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Dados inválidos"}), 400
        
    match_id = data.get("match_id")
    score1 = data.get("score1")
    score2 = data.get("score2")
    reporter_id = data.get("reporter_id")
    
    if match_id is None or score1 is None or score2 is None:
        return jsonify({"success": False, "message": "Campos obrigatórios ausentes"}), 400
        
    try:
        s1 = int(score1)
        s2 = int(score2)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valores de placar inválidos"}), 400

    if s1 == s2:
        return jsonify({"success": False, "message": "Não pode haver empate! Alguém precisa vencer a partida."}), 400

    conn = get_db()
    motor = MotorDoTorneio(RequestDBWrapper(conn), driver_serial=driver)
    
    sucesso, msg = motor.iniciar_reporte_placar(match_id, score1, score2, reporter_id=reporter_id)
    if sucesso:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "message": msg}), 400

@app.route("/api/dispute_score", methods=["POST"])
def dispute_score():
    """Permite ao atleta contestar formalmente um placar divergente proposto pelo oponente."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Dados inválidos"}), 400
    match_id = data.get("match_id")
    player_id = data.get("player_id")
    if not match_id or not player_id:
        return jsonify({"success": False, "message": "Campos obrigatórios ausentes"}), 400
    conn = get_db()
    motor = MotorDoTorneio(RequestDBWrapper(conn), driver_serial=driver)
    sucesso, msg = motor.contestar_placar(match_id, player_id)
    return jsonify({"success": sucesso, "message": msg})

@app.route("/api/admin/force_winner", methods=["POST"])
def admin_force_winner():
    """Força manualmente o resultado de uma partida (ex: W.O. ou intervenção)."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Dados inválidos"}), 400
        
    match_id = data.get("match_id")
    score1 = data.get("score1")
    score2 = data.get("score2")
    
    if match_id is None or score1 is None or score2 is None:
        return jsonify({"success": False, "message": "Campos obrigatórios ausentes"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Buscar partida e station_id
    cursor.execute("SELECT event_id, station_id, status FROM matches WHERE id = ?", (match_id,))
    match = cursor.fetchone()
    if not match:
        return jsonify({"success": False, "message": "Partida não encontrada"}), 404
        
    station_id = match["station_id"]
    
    # 2. Inicializar o Motor
    motor = MotorDoTorneio(RequestDBWrapper(conn))
    
    # 3. Forçar status para PLAYING caso estivesse em READY para permitir a finalização
    if match["status"] == 'READY':
        cursor.execute("UPDATE matches SET status = 'PLAYING' WHERE id = ?", (match_id,))
        conn.commit()
        
    # 4. Executar o reporte definitivo do placar
    if station_id:
        sucesso = motor.reportar_placar_ciberfisico(station_id, score1, score2)
    else:
        # Se não tiver estação alocada (por exemplo, na final não alocada ainda)
        cursor.execute("SELECT player1_id, player2_id, next_match_id, next_match_slot FROM matches WHERE id = ?", (match_id,))
        m_det = cursor.fetchone()
        p1_id = m_det["player1_id"]
        p2_id = m_det["player2_id"]
        next_match_id = m_det["next_match_id"]
        next_slot = m_det["next_match_slot"]
        
        calc_winner = p1_id if score1 > score2 else p2_id
        
        cursor.execute("""
            UPDATE matches 
            SET score1 = ?, score2 = ?, winner_id = ?, status = 'FINISHED',
                player1_checked_in = 0, player2_checked_in = 0,
                pending_score1 = NULL, pending_score2 = NULL
            WHERE id = ?
        """, (score1, score2, calc_winner, match_id))
        
        if next_match_id:
            motor._promover_jogador(next_match_id, next_slot, calc_winner)
        conn.commit()
        motor.verificar_e_finalizar_torneio(match["event_id"])
        sucesso = True
        
    if sucesso:
        return jsonify({"success": True, "message": "Resultado consolidado manualmente com sucesso!"})
    else:
        return jsonify({"success": False, "message": "Erro ao finalizar a partida manualmente."}), 400

@app.route("/api/admin/free_station", methods=["POST"])
def admin_free_station():
    """Libera manualmente uma mesa física desvinculando sua partida ativa."""
    data = request.get_json()
    if not data or "station_id" not in data:
        return jsonify({"success": False, "message": "ID da mesa ausente"}), 400
        
    station_id = data.get("station_id")
    conn = get_db()
    cursor = conn.cursor()
    
    # Desvincula qualquer partida READY ou PLAYING associada a essa mesa
    cursor.execute("""
        UPDATE matches SET station_id = NULL 
        WHERE station_id = ? AND status IN ('READY', 'PLAYING')
    """, (station_id,))
    
    conn.commit()
    return jsonify({"success": True, "message": "Mesa liberada manualmente!"})

@app.route("/api/admin/reset", methods=["POST"])
def admin_reset():
    """Zera o banco de dados e reinsere os dados fictícios do início para teste."""
    global db_path
    
    # Fecha conexão ativa na thread do request Flask
    db_conn = g.pop('db_conn', None)
    if db_conn:
        db_conn.close()
        
    try:
        # Exclui o arquivo do SQLite para limpar o estado físico
        if os.path.exists(db_path):
            os.remove(db_path)
            
        # Recria estrutura básica do zero
        new_conn = sqlite3.connect(db_path)
        new_conn.row_factory = sqlite3.Row
        new_conn.execute("PRAGMA foreign_keys = ON;")
        
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        new_conn.executescript(schema_sql)
        new_conn.commit()
        
        # Copia dados fictícios de exemplo
        from database.db_manager import BancoDeDados
        db_temp = BancoDeDados(db_path)
        db_temp.popular_dados_exemplo()
        db_temp.fechar()
        
        new_conn.close()
        return jsonify({"success": True, "message": "Campeonato reiniciado com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao resetar: {str(e)}"}), 500

@app.route("/api/admin/register_player", methods=["POST"])
def admin_register_player():
    """Cadastra um novo jogador no banco de dados e opcionalmente associa uma tag RFID."""
    data = request.get_json()
    if not data or "real_name" not in data or "nickname" not in data:
        return jsonify({"success": False, "message": "Nome Real ou Apelido Gamer ausentes"}), 400
        
    real_name = data.get("real_name").strip()
    nickname = data.get("nickname").strip()
    tag_uid = data.get("tag_uid", "").strip()
    
    if not real_name or not nickname:
        return jsonify({"success": False, "message": "Campos vazios não permitidos"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO players (real_name, nickname, is_active) VALUES (?, ?, 1)", (real_name, nickname))
        player_id = cursor.lastrowid
        if tag_uid:
            cursor.execute("INSERT OR REPLACE INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag_uid, player_id))
        conn.commit()
        return jsonify({"success": True, "message": f"Jogador {nickname} cadastrado com sucesso!"})
    except sqlite3.IntegrityError as e:
        return jsonify({"success": False, "message": f"Erro de banco: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro inesperado: {str(e)}"}), 500

@app.route("/api/admin/delete_player", methods=["POST"])
def admin_delete_player():
    """Realiza a exclusão lógica (Soft Delete) do jogador."""
    data = request.get_json()
    if not data or "player_id" not in data:
        return jsonify({"success": False, "message": "ID do jogador ausente"}), 400
        
    player_id = data.get("player_id")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE players SET is_active = 0 WHERE id = ?", (player_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Jogador excluído (desativado) com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/admin/update_player", methods=["POST"])
def admin_update_player():
    """Edita os dados cadastrais (Nome, Apelido, RFID) de um jogador."""
    data = request.get_json()
    if not data or "player_id" not in data or "real_name" not in data or "nickname" not in data:
        return jsonify({"success": False, "message": "Dados obrigatórios ausentes"}), 400
        
    player_id = data.get("player_id")
    real_name = data.get("real_name").strip()
    nickname = data.get("nickname").strip()
    tag_uid = data.get("tag_uid", "").strip()
    
    if not real_name or not nickname:
        return jsonify({"success": False, "message": "Campos vazios não permitidos"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE players SET real_name = ?, nickname = ? WHERE id = ?", (real_name, nickname, player_id))
        
        if tag_uid:
            cursor.execute("INSERT OR REPLACE INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag_uid, player_id))
        else:
            cursor.execute("DELETE FROM rfid_tags WHERE player_id = ?", (player_id,))
            
        conn.commit()
        return jsonify({"success": True, "message": "Jogador atualizado com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/admin/player_history/<int:player_id>", methods=["GET"])
def admin_player_history(player_id):
    """Retorna dados cadastrais e o histórico relacional de partidas do jogador."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.id, p.real_name, p.nickname, p.is_active, t.tag_uid
        FROM players p
        LEFT JOIN rfid_tags t ON p.id = t.player_id
        WHERE p.id = ?
    """, (player_id,))
    player = cursor.fetchone()
    if not player:
        return jsonify({"success": False, "message": "Jogador não encontrado"}), 404
        
    cursor.execute("""
        SELECT m.id, ev.name as event_name, 
               p1.nickname as player1, p2.nickname as player2,
               m.score1, m.score2, w.nickname as winner, m.status
        FROM matches m
        JOIN events ev ON m.event_id = ev.id
        LEFT JOIN players p1 ON m.player1_id = p1.id
        LEFT JOIN players p2 ON m.player2_id = p2.id
        LEFT JOIN players w ON m.winner_id = w.id
        WHERE m.player1_id = ? OR m.player2_id = ?
        ORDER BY m.id DESC
    """, (player_id, player_id))
    matches = [dict(row) for row in cursor.fetchall()]
    
    return jsonify({
        "success": True,
        "player": dict(player),
        "matches": matches
    })

@app.route("/api/admin/initialize_bracket", methods=["POST"])
def admin_initialize_bracket():
    """Gera os brackets de chaveamento Single Elimination e bloqueia inscrições."""
    data = request.get_json() or {}
    event_id = data.get("event_id", 1)
    
    conn = get_db()
    motor = MotorDoTorneio(RequestDBWrapper(conn))
    
    try:
        sucesso, msg = motor.inicializar_chave_torneio(event_id)
        if sucesso:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro interno: {str(e)}"}), 500

@app.route("/api/admin/dq_player", methods=["POST"])
def admin_dq_player():
    """Desqualifica um jogador de um confronto ativo, promovendo o oponente."""
    data = request.get_json()
    if not data or "match_id" not in data or "player_id" not in data:
        return jsonify({"success": False, "message": "Parâmetros ausentes"}), 400
        
    match_id = data.get("match_id")
    player_id = data.get("player_id")
    
    conn = get_db()
    motor = MotorDoTorneio(RequestDBWrapper(conn))
    try:
        sucesso, msg = motor.desqualificar_jogador(match_id, player_id)
        if sucesso:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/admin/bind_node_station", methods=["POST"])
def admin_bind_node_station():
    """Vincula uma mesa do evento a um módulo de hardware do inventário."""
    data = request.get_json()
    if not data or "station_id" not in data or "node_mac" not in data:
        return jsonify({"success": False, "message": "Estação ou MAC ausentes"}), 400
        
    station_id = data.get("station_id")
    node_mac = data.get("node_mac").strip()
    if node_mac == "":
        node_mac = None
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE stations SET node_mac = ? WHERE id = ?", (node_mac, station_id))
        conn.commit()
        return jsonify({"success": True, "message": "Mesa vinculada ao Nó Repórter com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/admin/nodes", methods=["GET"])
def admin_get_nodes():
    """Retorna todos os nós físicos cadastrados no inventário."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT mac_address, nickname, type FROM nodes")
    rows = cursor.fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/admin/players", methods=["GET"])
def admin_get_players():
    """Retorna todos os jogadores cadastrados."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, real_name, nickname, is_active FROM players")
    rows = cursor.fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/admin/stations", methods=["GET"])
def admin_get_stations():
    """Retorna as estações do evento com seus respectivos apelidos de hardware."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.name, s.node_mac, n.nickname as node_nickname
        FROM stations s
        LEFT JOIN nodes n ON s.node_mac = n.mac_address
    """)
    rows = cursor.fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/status")
def api_status():
    """API para atualizações assíncronas do status do torneio."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, score1, score2, status FROM matches")
    matches = [dict(row) for row in cursor.fetchall()]
    return jsonify(matches)

if __name__ == "__main__":
    get_or_create_driver()
    app.run(host="0.0.0.0", port=5000, debug=True)
