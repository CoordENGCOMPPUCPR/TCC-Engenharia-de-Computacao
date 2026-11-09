import os
import sys
import time

from database.db_manager import BancoDeDados
from motor.tournament_engine import MotorDoTorneio

def visualizar_brackets_texto(db):
    """
    Renderiza na tela (usando caracteres ASCII) o chaveamento atual do torneio,
    exibindo os placares, vencedores e nomes dos jogadores de forma estruturada.
    """
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT m.id, 
               p1.nickname as p1_name, p2.nickname as p2_name,
               m.score1, m.score2, m.status, w.nickname as winner_name,
               s.name as station_name
        FROM matches m
        LEFT JOIN players p1 ON m.player1_id = p1.id
        LEFT JOIN players p2 ON m.player2_id = p2.id
        LEFT JOIN players w ON m.winner_id = w.id
        LEFT JOIN stations s ON m.station_id = s.id
    """)
    rows = cursor.fetchall()
    matches_dict = {row["id"]: row for row in rows}
    
    m1 = matches_dict.get(1)
    m2 = matches_dict.get(2)
    m3 = matches_dict.get(3)
    
    def fmt_match(m):
        if not m:
            return "Sem dados"
        p1 = m["p1_name"] if m["p1_name"] else "A definir"
        p2 = m["p2_name"] if m["p2_name"] else "A definir"
        s1 = m["score1"] if m["score1"] is not None else 0
        s2 = m["score2"] if m["score2"] is not None else 0
        status = m["status"]
        station = m["station_name"] if m["station_name"] else "Sem mesa"
        return f"{p1} ({s1}) vs {p2} ({s2}) [{status} - {station}]"
        
    print("\n" + "="*80)
    print("                     ÁRVORE DE CHAVES DO TORNEIO (ASCII)")
    print("="*80)
    print(f" [Mesa A] {fmt_match(m1)} -----\\ ")
    print("                                                 +---> [FINAL] " + fmt_match(m3))
    print(f" [Mesa B] {fmt_match(m2)} -----/ ")
    print("="*80 + "\n")

def main():
    print("="*60)
    print("           CLI DE SIMULAÇÃO - ECOSSISTEMA AUTOREPORTER")
    print("="*60)

    # 1. Instanciar e inicializar banco de dados
    user_dir = os.path.join(os.path.expanduser("~"), ".autoreporter")
    os.makedirs(user_dir, exist_ok=True)
    db_path = os.path.join(user_dir, "autoreporter.db")
    db = BancoDeDados(db_path)
    db.inicializar_banco()
    db.popular_dados_exemplo()

    # 2. Instanciar o Motor do Torneio
    motor = MotorDoTorneio(db)

    # 3. Mostrar chaveamento inicial
    visualizar_brackets_texto(db)

    print("\nComandos disponíveis:")
    print("  - ver ou status                      : Exibe brackets e status das mesas")
    print("  - checkin <tag_uid> <mac_no>          : Simula aproximação do cartão para check-in")
    print("  - report <match_id> <score1> <score2> : Simula submissão do placar via celular")
    print("  - chancela <tag_uid> <mac_no>         : Simula chancela de placar pendente com tag")
    print("  - sair                                : Encerra a simulação")

    while True:
        try:
            linha = input("\nautoreporter> ").strip()
            if not linha:
                continue
            
            partes = linha.split()
            cmd = partes[0].lower()
            
            if cmd == "sair":
                print("Encerrando...")
                break
                
            elif cmd in ("ver", "status"):
                # Mostrar status das mesas
                cursor = db.conn.cursor()
                cursor.execute("""
                    SELECT s.id, s.name, s.node_mac, m.id as match_id, m.status,
                           p1.nickname as p1_name, p2.nickname as p2_name,
                           m.player1_checked_in, m.player2_checked_in,
                           m.pending_score1, m.pending_score2
                    FROM stations s
                    LEFT JOIN matches m ON s.id = m.station_id AND m.status IN ('READY', 'PLAYING')
                    LEFT JOIN players p1 ON m.player1_id = p1.id
                    LEFT JOIN players p2 ON m.player2_id = p2.id
                """)
                mesas = cursor.fetchall()
                print("\n=== STATUS DAS ESTAÇÕES (MESAS) ===")
                for m in mesas:
                    m_id = m["match_id"]
                    if m_id:
                        p1_ci = "OK" if m["player1_checked_in"] else "Pendente"
                        p2_ci = "OK" if m["player2_checked_in"] else "Pendente"
                        pend = f" (Pendente: {m['pending_score1']}x{m['pending_score2']})" if m["pending_score1"] is not None else ""
                        print(f"- {m['name']} (Nó: {m['node_mac']}): Partida {m_id} ({m['status']}){pend}")
                        print(f"  * Jogador 1: {m['p1_name']} [{p1_ci}]")
                        print(f"  * Jogador 2: {m['p2_name']} [{p2_ci}]")
                    else:
                        print(f"- {m['name']} (Nó: {m['node_mac']}): LIVRE")
                
                visualizar_brackets_texto(db)
                
            elif cmd == "checkin":
                if len(partes) < 3:
                    print("Uso correto: checkin <tag_uid> <mac_no>")
                    continue
                tag_uid = partes[1]
                mac_no = partes[2]
                sucesso, msg = motor.registrar_checkin_rfid(tag_uid, mac_no)
                print(f"[CLI] Resultado: {msg}")
                
            elif cmd == "report":
                if len(partes) < 4:
                    print("Uso correto: report <match_id> <score1> <score2>")
                    continue
                try:
                    match_id = int(partes[1])
                    score1 = int(partes[2])
                    score2 = int(partes[3])
                except ValueError:
                    print("Parâmetros inválidos. ID e scores devem ser inteiros.")
                    continue
                sucesso, msg = motor.iniciar_reporte_placar(match_id, score1, score2)
                print(f"[CLI] Resultado: {msg}")
                
            elif cmd == "chancela":
                if len(partes) < 3:
                    print("Uso correto: chancela <tag_uid> <mac_no>")
                    continue
                tag_uid = partes[1]
                mac_no = partes[2]
                sucesso, msg = motor.confirmar_placar_rfid(tag_uid, mac_no)
                print(f"[CLI] Resultado: {msg}")
                
            else:
                print(f"Comando desconhecido: '{cmd}'")
        except KeyboardInterrupt:
            print("\nEncerrando...")
            break
        except Exception as e:
            print(f"Erro ao processar comando: {e}")

    db.fechar()
    print("Ecossistema encerrado com sucesso.")

if __name__ == "__main__":
    main()
