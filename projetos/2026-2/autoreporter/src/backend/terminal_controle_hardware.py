#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTOREPORTER - ESTAÇÃO DE CONTROLE TERMINAL E DIAGNÓSTICO DE HARDWARE
Trabalho de Conclusão de Curso (TCC) - Engenharia de Computação PUCPR 2026

Utilitário de bancada para:
1. Conexão e detecção automática de nós via porta serial USB UART (115200 bps).
2. Varredura e descoberta de nós repórteres na sala via rádio ESP-NOW (DISCOVER broadcast).
3. Controle interativo de cores de LEDs (remoto via rádio, broadcast geral ou local).
4. Monitor contínuo de eventos RFID e telemetria de placar em tempo real.
5. Diagnóstico de integridade do hardware (versão do leitor MFRC522, canal e MAC).
"""

import os
import sys
import time
import threading
import queue

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERRO] Biblioteca 'pyserial' não encontrada. Instale com: pip install pyserial")
    sys.exit(1)

# Cores ANSI para saída no terminal
C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"
C_RED     = "\033[91m"
C_GREEN   = "\033[92m"
C_YELLOW  = "\033[93m"
C_BLUE    = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN    = "\033[96m"
C_WHITE   = "\033[97m"

def colorize(text, color):
    # Se o terminal não suportar ANSI puro no Windows, retorna texto direto
    if os.name == 'nt' and not os.environ.get('WT_SESSION') and not os.environ.get('ANSICON'):
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return text
    return f"{color}{text}{C_RESET}"

class TerminalControleHardware:
    def __init__(self):
        self.ser = None
        self.porta_com = None
        self.running = False
        self.coordinator_mac = "DESCONHECIDO"
        self.read_thread = None
        self.discovered_nodes = {}  # {mac: {'saltos': int, 'via': str, 'last_seen': float}}
        self.log_queue = queue.Queue()
        self.sniffing_mode = False
        self.diag_lines = None

    def listar_portas(self):
        portas = list(serial.tools.list_ports.comports())
        return portas

    def conectar(self, porta=None):
        portas = self.listar_portas()
        if not portas:
            print(colorize("\n[AVISO] Nenhuma porta COM detectada! Conecte o ESP32 via cabo USB.", C_RED))
            return False

        if not porta:
            # Auto-seleciona se houver apenas uma ou busca por chips comuns (CP210x, CH340, USB)
            for p in portas:
                desc = (p.description or "").upper()
                hwid = (p.hwid or "").upper()
                if any(x in desc or x in hwid for x in ["USB", "CP210", "CH340", "CH9102", "SERIAL"]):
                    porta = p.device
                    break
            if not porta and portas:
                porta = portas[0].device

        print(colorize(f"\n[CONEXÃO] Tentando abrir porta {porta} a 115200 bps...", C_CYAN))
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial()
            self.ser.port = porta
            self.ser.baudrate = 115200
            self.ser.timeout = 0.5
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            time.sleep(0.5)
            self.ser.reset_input_buffer()

            self.porta_com = porta
            self.running = True

            # Inicia thread de escuta assíncrona
            self.read_thread = threading.Thread(target=self._escuta_serial_loop, daemon=True)
            self.read_thread.start()

            # Envia PING de saudação
            self.enviar_raw("PING")
            time.sleep(0.4)

            print(colorize(f"[OK] Conectado com sucesso à porta {porta}!", C_GREEN))
            return True
        except Exception as e:
            print(colorize(f"[ERRO] Falha ao abrir porta {porta}: {e}", C_RED))
            return False

    def desconectar(self):
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        print(colorize("\n[CONEXÃO] Porta serial fechada com sucesso.", C_YELLOW))

    def enviar_raw(self, comando):
        if not self.ser or not self.ser.is_open:
            print(colorize("[ERRO] Porta serial desconectada!", C_RED))
            return False
        try:
            linha = comando.strip() + "\n"
            self.ser.write(linha.encode('utf-8'))
            self.ser.flush()
            return True
        except Exception as e:
            print(colorize(f"[ERRO DE ENVIO]: {e}", C_RED))
            return False

    def _escuta_serial_loop(self):
        buffer_str = ""
        while self.running and self.ser and self.ser.is_open:
            try:
                data = self.ser.readline()
                if data:
                    linha = data.decode('utf-8', errors='ignore').strip()
                    if linha:
                        self._processar_linha_recebida(linha)
            except Exception:
                break
            time.sleep(0.01)

    def _processar_linha_recebida(self, linha):
        # 0. Captura durante o modo diagnóstico ativo
        if self.diag_lines is not None:
            self.diag_lines.append(linha)
            if "[DIAG_END]" not in linha:
                cor_l = C_GREEN if "[OK]" in linha else (C_RED if ("FALHA" in linha or "[AVISO]" in linha) else C_CYAN)
                print(colorize(f"  {linha}", cor_l))

        # 1. Identificação do MAC do Coordenador Local
        if "MAC Físico:" in linha or "MAC:" in linha:
            partes = linha.split("MAC:") if "MAC:" in linha else linha.split("MAC Físico:")
            mac_cand = partes[-1].strip().upper()
            if len(mac_cand) >= 17:
                self.coordinator_mac = mac_cand[:17]

        # 2. Respostas de Discovery: DISCOVERED;<mac>;SALTOS:<n>;VIA:<mac>
        if linha.startswith("DISCOVERED;"):
            tokens = linha.split(";")
            if len(tokens) >= 2:
                mac = tokens[1].strip().upper()
                saltos = 1
                via = "DIRETO"
                for tok in tokens[2:]:
                    if tok.startswith("SALTOS:"):
                        try: saltos = int(tok.split(":")[-1])
                        except: pass
                    elif tok.startswith("VIA:"):
                        via = tok.split(":")[-1].strip()
                self.discovered_nodes[mac] = {
                    'saltos': saltos,
                    'via': via,
                    'last_seen': time.time()
                }
                print(colorize(f"\n[RADIO MESH] Novo nó detectado: {mac} (Saltos: {saltos}, Via: {via})", C_GREEN))

        # 3. Evento RFID: RFID;<uid>;<mac>;...
        elif linha.startswith("RFID;"):
            tokens = linha.split(";")
            uid = tokens[1] if len(tokens) > 1 else "?"
            mac = tokens[2] if len(tokens) > 2 else "?"
            origem = tokens[3] if len(tokens) > 3 else "LOCAL"
            t_str = time.strftime("%H:%M:%S")
            msg = f"\n{colorize('>>> [RFID DETECTADO]', C_BOLD + C_YELLOW)} UID: {colorize(uid, C_WHITE)} | Nó: {colorize(mac, C_CYAN)} ({origem}) às {t_str}"
            print(msg)

        # 4. Evento SCORE: SCORE;<mac>;<s1>;<s2>;...
        elif linha.startswith("SCORE;"):
            tokens = linha.split(";")
            mac = tokens[1] if len(tokens) > 1 else "?"
            s1 = tokens[2] if len(tokens) > 2 else "?"
            s2 = tokens[3] if len(tokens) > 3 else "?"
            t_str = time.strftime("%H:%M:%S")
            msg = f"\n{colorize('>>> [PLACAR RECEBIDO]', C_BOLD + C_GREEN)} Mesa {mac}: {s1} x {s2} às {t_str}"
            print(msg)

        # 5. Mensagens de Diagnóstico, Boot do Hardware e Telemetria
        elif any(k in linha for k in ["[HARDWARE]", "[AVISO]", "[ERROR]", "MFRC522", "[DIAG]", "RELATÓRIO", "[LOCAL_LED", "[LOCAL_LEDS", "[DOWNLINK", "[BARREIRA]", "PONG"]):
            if self.diag_lines is None:
                cor = C_RED if ("[AVISO]" in linha or "[ERROR]" in linha or "FALHA" in linha) else C_CYAN
                print(colorize(f"  [DISPOSITIVO USB] {linha}", cor))

        # 6. Modo Sniffer de Telemetria Geral
        elif self.sniffing_mode and self.diag_lines is None:
            print(colorize(f"  [RAW SERIAL] {linha}", C_WHITE))

    def comando_descobrir(self):
        print(colorize("\n[DISCOVER] Disparando pulsos de rádio ESP-NOW Broadcast...", C_CYAN))
        self.discovered_nodes.clear()
        self.enviar_raw("DISCOVER")
        for i in range(5):
            sys.stdout.write(f"\rAguardando respostas no ar... ({5-i}s) ")
            sys.stdout.flush()
            time.sleep(0.4)
        print("\rVarredura concluída!                         \n")

        self.exibir_tabela_nos()

    def exibir_tabela_nos(self):
        print("=" * 68)
        print(colorize(f"  NÓS REPÓRTERES IDENTIFICADOS NA MALHA ESP-NOW (Canal 1 - 2.4GHz)", C_BOLD + C_WHITE))
        print("=" * 68)
        print(f"{'#':<3} | {'Endereço MAC':<20} | {'Saltos':<8} | {'Rota (Via)':<20} | {'Status'}")
        print("-" * 68)

        # Inclui o próprio Coordenador Local na tabela
        print(f"{'0':<3} | {self.coordinator_mac:<20} | {'0 (USB)':<8} | {'LOCAL_PC':<20} | {colorize('COORDENADOR', C_MAGENTA)}")

        if not self.discovered_nodes:
            print(colorize("  (Nenhum nó remoto respondeu ainda. Pressione [1] para varrer).", C_YELLOW))
        else:
            idx = 1
            for mac, info in self.discovered_nodes.items():
                via_str = info['via']
                saltos_str = f"{info['saltos']} ({'Direto' if info['saltos']==1 else 'Relay'})"
                print(f"{idx:<3} | {mac:<20} | {saltos_str:<8} | {via_str:<20} | {colorize('ONLINE', C_GREEN)}")
                idx += 1
        print("=" * 68)

    def controlar_leds_menu(self):
        # 1. Seleção Simples de Alvo (Default = Placa Local USB ao teclar ENTER)
        lista_macs = list(self.discovered_nodes.keys())
        print("\n" + "=" * 65)
        print(colorize("  SELEÇÃO DE PLACA PARA DIAGNÓSTICO DE LEDS", C_BOLD + C_CYAN))
        print("=" * 65)
        print(f"  [{colorize('ENTER', C_BOLD + C_YELLOW)}] -> {colorize('Placa Local USB', C_GREEN)} ({self.porta_com})  <-- Padrão Imediato")
        print("  [0]     -> TODAS AS PLACAS (Broadcast Rádio ESP-NOW)")
        for i, mac in enumerate(lista_macs, 1):
            via = self.discovered_nodes[mac].get('via', 'DIRETO')
            print(f"  [{i}]     -> Nó Remoto #{i}: {mac} ({via})")
        print("  [V]     -> Voltar ao menu principal")
        print("-" * 65)

        try:
            escolha_alvo = input(f"Escolha a placa [{colorize('ENTER=Local USB', C_GREEN)}, 0=Todos, V=Voltar] > ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            return

        if escolha_alvo in ['V', 'VOLTAR', 'SAIR']:
            return

        target_mac = self.coordinator_mac
        is_local = True
        nome_alvo = f"PLACA LOCAL USB ({self.porta_com})"

        if escolha_alvo == '0':
            target_mac = "FF:FF:FF:FF:FF:FF"
            is_local = False
            nome_alvo = "TODAS AS PLACAS (BROADCAST)"
        elif escolha_alvo in ['', 'L', 'LOCAL']:
            target_mac = self.coordinator_mac
            is_local = True
            nome_alvo = f"PLACA LOCAL USB ({self.porta_com})"
        else:
            try:
                num = int(escolha_alvo)
                if 1 <= num <= len(lista_macs):
                    target_mac = lista_macs[num - 1]
                    is_local = False
                    nome_alvo = f"NÓ REMOTO #{num} ({target_mac})"
                else:
                    print(colorize("[ERRO] Opção de nó inválida!", C_RED))
                    return
            except ValueError:
                print(colorize("[ERRO] Opção inválida!", C_RED))
                return

        # Abre diretamente o console de diagnóstico em texto simples
        self._submenu_cores_placa(target_mac, is_local, nome_alvo)

    def _submenu_cores_placa(self, target_mac, is_local, nome_alvo):
        import re
        NOME_CORES = {
            '0': 'DESLIGADO',
            '1': 'VERMELHO',
            '2': 'AZUL',
            '3': 'VERDE',
            '4': 'AMARELO',
            '5': 'CIANO',
            '6': 'ROXO',
            '7': 'BRANCO'
        }
        ANSI_CORES = {
            '0': C_WHITE,
            '1': C_RED,
            '2': C_BLUE,
            '3': C_GREEN,
            '4': C_YELLOW,
            '5': C_CYAN,
            '6': C_MAGENTA,
            '7': C_BOLD + C_WHITE
        }

        l1_atual = '0'
        l2_atual = '0'

        print("\n" + "=" * 65)
        print(colorize(f"  CONSOLE DIRETO DE TESTE DE PINOS E LEDS -> {nome_alvo}", C_BOLD + C_YELLOW))
        print("=" * 65)
        print("Digite comandos em português simples:")
        print(f"  - Por LED:     {colorize('verde 1', C_GREEN)}   |   {colorize('azul 2', C_BLUE)}   |   {colorize('vermelho 1', C_RED)}   |   {colorize('apagar 1', C_WHITE)}")
        print(f"  - Em ambos:    {colorize('verde 1, azul 1', C_BOLD + C_WHITE)} (ou 'verde 1, azul 2')  |  {colorize('vermelho 1, verde 2', C_BOLD + C_WHITE)}")
        print(f"  - Tudo junto:  {colorize('vermelho', C_RED)} (ambos)   |   {colorize('apagar', C_WHITE)} (desliga tudo)")
        print(f"  - Teste Pino:  {colorize('pino 25', C_YELLOW)} (isola GPIO 25) | {colorize('pino 32', C_YELLOW)} | {colorize('pino 14', C_YELLOW)}")
        print(f"  - Para sair:   pressione {colorize('ENTER vazio', C_CYAN)} ou digite {colorize('voltar', C_CYAN)}")
        print("-" * 65)

        while True:
            c1_str = colorize(NOME_CORES.get(l1_atual, l1_atual), ANSI_CORES.get(l1_atual, C_WHITE))
            c2_str = colorize(NOME_CORES.get(l2_atual, l2_atual), ANSI_CORES.get(l2_atual, C_WHITE))
            print(f"Status no Hardware: LED 1 = [{c1_str}] | LED 2 = [{c2_str}]")

            try:
                entrada = input(colorize("Comando > ", C_BOLD + C_YELLOW)).strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not entrada or entrada.lower() in ['v', 'voltar', 'sair', 'exit', 'q']:
                break

            tipo_acao, arg1, arg2 = self._interpretar_comando_led(entrada, l1_atual, l2_atual)

            if tipo_acao == 'EXIT':
                break
            elif tipo_acao == 'PIN':
                gpio_num = arg1
                if is_local:
                    self.enviar_raw(f"PIN;{gpio_num}")
                else:
                    self.enviar_raw(f"SEND;{target_mac};PIN;{gpio_num}")
                print(colorize(f"\n>>> [TESTE DE PINO] Acionando SOMENTE a GPIO {gpio_num} (todos os outros pinos desligados).", C_BOLD + C_YELLOW))
                print("    Observe sua placa: qual cor e qual LED acendeu?\n")
            elif tipo_acao == 'LEDS':
                l1_atual = arg1
                l2_atual = arg2
                param = f"{l1_atual};{l2_atual}"
                if is_local:
                    cmd = f"LEDS;{param}"
                    self.enviar_raw(cmd)
                else:
                    cmd = f"SEND;{target_mac};LEDS;{param}"
                    self.enviar_raw(cmd)

                n1 = NOME_CORES.get(l1_atual, l1_atual)
                n2 = NOME_CORES.get(l2_atual, l2_atual)
                c1_cor = ANSI_CORES.get(l1_atual, C_WHITE)
                c2_cor = ANSI_CORES.get(l2_atual, C_WHITE)
                print(colorize(f"\n>>> [OK]", C_BOLD + C_GREEN) + f" LED 1 = {colorize(n1, c1_cor)} | LED 2 = {colorize(n2, c2_cor)}\n")
            elif tipo_acao == 'TESTE_CICLICO':
                self.executar_teste_rgb_ciclico(target_mac, is_local)
                l1_atual, l2_atual = '0', '0'
            else:
                print(colorize(f"[?] Não entendi '{entrada}'. Digite por exemplo: 'verde 1, azul 1', 'vermelho 1' ou 'pino 25'.", C_RED) + "\n")

    def _interpretar_comando_led(self, entrada, l1_atual, l2_atual):
        import re
        texto = entrada.strip().lower()

        if texto in ['v', 'voltar', 'sair', 'exit', 'q']:
            return ('EXIT', None, None)

        if texto in ['t', 'teste', 'ciclo', 'ciclico']:
            return ('TESTE_CICLICO', None, None)

        # 1. Pinos individuais GPIO: "pino 25", "gpio 25", "p 25", "p25", "pin 25", "pin;25"
        m_pino = re.search(r'(?:pino|pin|gpio|p)\s*[:;=]?\s*(\d+)', texto)
        if m_pino:
            return ('PIN', int(m_pino.group(1)), None)

        # Se digitou apenas um número de pino comum da placa
        if texto in ['4', '12', '13', '14', '15', '18', '19', '22', '23', '25', '26', '27', '32', '33']:
            return ('PIN', int(texto), None)

        # 2. Apagar tudo
        if texto in ['apagar', 'desligar', 'off', 'limpar', 'clear', '0', '00']:
            return ('LEDS', '0', '0')

        MAPA_CORES = {
            'verde': '3', 'green': '3', 'verd': '3',
            'azul': '2', 'blue': '2',
            'vermelho': '1', 'red': '1', 'verm': '1',
            'amarelo': '4', 'yellow': '4', 'amar': '4',
            'ciano': '5', 'cyan': '5',
            'roxo': '6', 'purple': '6', 'magenta': '6',
            'branco': '7', 'white': '7',
            'apagar': '0', 'desligar': '0', 'off': '0', 'desl': '0'
        }

        def extrair_cor(t):
            for nome, cod in MAPA_CORES.items():
                if nome in t:
                    return cod
            # Abreviações curtas
            if re.search(r'\b(vm|r)\b', t): return '1'
            if re.search(r'\b(az|a|b)\b', t): return '2'
            if re.search(r'\b(vd|v|g)\b', t): return '3'
            if re.search(r'\b(am|y)\b', t): return '4'
            return None

        # 3. Código numérico de 2 dígitos direto (ex: "21", "13", "10")
        if len(texto) == 2 and texto[0] in '01234567' and texto[1] in '01234567':
            return ('LEDS', texto[0], texto[1])
        if len(texto) == 1 and texto in '01234567':
            return ('LEDS', texto, texto)

        # 4. Divisão em cláusulas por vírgula, 'e', ';', '+'
        clausulas = [c.strip() for c in re.split(r'[,;+&]|\be\b', texto) if c.strip()]

        novo_l1 = l1_atual
        novo_l2 = l2_atual

        if len(clausulas) == 2:
            c0, c1 = clausulas[0], clausulas[1]
            cor0 = extrair_cor(c0)
            cor1 = extrair_cor(c1)

            if cor0 and cor1:
                # Se c0 tem '2' e c1 tem '1' (ex: "azul 2, verde 1")
                if '2' in c0 and '1' in c1:
                    novo_l1 = cor1
                    novo_l2 = cor0
                elif '1' in c0 and '2' in c1:
                    novo_l1 = cor0
                    novo_l2 = cor1
                elif '1' in c0 and '1' in c1:
                    # O usuário escreveu "Verde 1, Azul 1" querendo um em cada!
                    novo_l1 = cor0
                    novo_l2 = cor1
                elif '2' in c0 and '2' in c1:
                    novo_l1 = cor0
                    novo_l2 = cor1
                else:
                    # Ordem padrão: primeira cor no LED 1, segunda no LED 2
                    novo_l1 = cor0
                    novo_l2 = cor1
                return ('LEDS', novo_l1, novo_l2)

        elif len(clausulas) == 1:
            c = clausulas[0]
            cor = extrair_cor(c)
            if cor:
                if '1' in c:
                    novo_l1 = cor
                elif '2' in c:
                    novo_l2 = cor
                else:
                    # Sem número: aplica em ambos (ex: "verde", "vermelho")
                    novo_l1 = cor
                    novo_l2 = cor
                return ('LEDS', novo_l1, novo_l2)

        return ('UNKNOWN', None, None)

    def executar_diagnostico_hardware(self):
        print("\n" + "=" * 65)
        print(colorize("  AUTOREPORTER: DIAGNÓSTICO DE HARDWARE SPI / RFID (COMANDO DIAG)", C_BOLD + C_YELLOW))
        print("=" * 65)
        print("Solicitando relatório de registradores ao ESP32 via Serial...\n")

        self.diag_lines = []
        self.enviar_raw("DIAG")

        # Aguarda transmissão completa do ESP32 por até 2.0 segundos
        inicio = time.time()
        while time.time() - inicio < 2.0:
            if any("[DIAG_END]" in l for l in self.diag_lines):
                break
            time.sleep(0.1)

        linhas_recebidas = list(self.diag_lines)
        self.diag_lines = None

        print("\n" + "-" * 65)
        print(colorize("  PARECER TÉCNICO E DECURSO DE HARDWARE:", C_BOLD + C_WHITE))
        print("-" * 65)

        if not linhas_recebidas:
            print(colorize("[ERRO] Nenhuma resposta do ESP32!", C_RED))
            print("Verifique se o cabo USB está firme e se a porta COM correta está conectada.")
        else:
            version_reg = None
            for l in linhas_recebidas:
                if "VersionReg:" in l or "Versão MFRC522:" in l:
                    try:
                        partes = l.split("0x")
                        if len(partes) > 1:
                            hex_str = partes[1][:2].strip().upper()
                            version_reg = int(hex_str, 16)
                    except Exception:
                        pass

            if version_reg is not None:
                print(f"Código VersionReg Lido: {colorize(f'0x{version_reg:02X}', C_BOLD + C_WHITE)}")
                if version_reg in [0x91, 0x92]:
                    print(colorize("-> STATUS SPI: PERFEITO! (MFRC522 Original Operacional)", C_GREEN))
                    print("   O leitor RFID está respondendo 100% no barramento SPI.")
                elif version_reg in [0x88, 0x90, 0x12]:
                    print(colorize("-> STATUS SPI: OPERACIONAL (Clone MFRC522 Compatível)", C_GREEN))
                elif version_reg == 0x00:
                    print(colorize("-> STATUS SPI: FALHA DE CONEXÃO (0x00)!", C_BOLD + C_RED))
                    print("   Causa: As linhas de dados SPI estão presas em nível 0V ou sem continuidade.")
                    print("   PONTOS CRÍTICOS A INSPECIONAR NA PLACA 3:")
                    print("   1. SCK (GPIO 18) e SDA/SS (GPIO 15) -> Testar continuidade com multímetro.")
                    print("   2. MOSI (GPIO 23) e MISO (GPIO 19) -> Verificar se não há solda fria ou curto com GND.")
                    print("   3. Certifique-se de que nenhum fio de dados encostou no barramento GND comum.")
                elif version_reg == 0xFF:
                    print(colorize("-> STATUS SPI: FALHA DE BARRAMENTO ABERTO (0xFF)!", C_BOLD + C_RED))
                    print("   Causa: A linha MISO (GPIO 19) está flutuando em 3.3V, o chip está sem clock ou em reset.")
                    print("   PONTOS CRÍTICOS A INSPECIONAR NA PLACA 3:")
                    print("   1. RST (GPIO 4) -> Se desconectado, o RC522 fica desligado. O ESP32 deve mantê-lo em HIGH.")
                    print("   2. SCK (GPIO 18) -> Se o clock não chegar, o chip não envia dados.")
                    print("   3. MISO (GPIO 19) -> Verificar se não encostou na ilha de 3.3V.")
                else:
                    print(colorize(f"-> STATUS SPI: Resposta desconhecida (0x{version_reg:02X}).", C_YELLOW))
            else:
                print(colorize("-> O ESP32 respondeu ao comando, veja as linhas detalhadas acima.", C_YELLOW))

        print("-" * 65)
        input(colorize("Pressione [ENTER] para retornar ao menu principal...", C_YELLOW))

    def executar_teste_rgb_ciclico(self, target_mac, is_local):
        print(colorize(f"\nIniciando Teste Cíclico R-G-B em {target_mac}...", C_CYAN))
        print("(Pressione Ctrl+C a qualquer momento para parar o teste)\n")
        sequencia = [
            ("RED", C_RED),
            ("GREEN", C_GREEN),
            ("BLUE", C_BLUE),
            ("YELLOW", C_YELLOW),
            ("OFF", C_WHITE)
        ]
        try:
            for cor, ansi_cor in sequencia:
                print(f"  -> Acionando canal: {colorize(cor, ansi_cor)}")
                if is_local:
                    self.enviar_raw(f"LED;{cor}")
                else:
                    self.enviar_raw(f"SEND;{target_mac};LED;{cor}")
                time.sleep(1.5)
            print(colorize("[TESTE CONCLUÍDO] Todos os canais acionados com sucesso!", C_GREEN))
        except KeyboardInterrupt:
            print(colorize("\n[TESTE INTERROMPIDO] Finalizando.", C_YELLOW))
            if is_local:
                self.enviar_raw("LED;YELLOW")
            else:
                self.enviar_raw(f"SEND;{target_mac};LED;YELLOW")

    def modo_sniffer_rfid(self):
        print("\n" + "=" * 65)
        print(colorize("  MODO MONITOR / SNIFFER RFID EM TEMPO REAL", C_BOLD + C_YELLOW))
        print("  Aproxime qualquer cartão ou chaveiro em qualquer Nó físico.")
        print("  (Pressione ENTER para voltar ao menu principal)")
        print("=" * 65 + "\n")
        self.sniffing_mode = True
        try:
            input()
        except KeyboardInterrupt:
            pass
        self.sniffing_mode = False
        print(colorize("\n[MONITOR] Encerrado.", C_YELLOW))

    def menu_principal(self):
        while True:
            status_conn = colorize(f"CONECTADO ({self.porta_com})", C_GREEN) if (self.ser and self.ser.is_open) else colorize("DESCONECTADO", C_RED)
            print("\n" + "=" * 65)
            print(colorize("  AUTOREPORTER - CONSOLE DE CONTROLE E TESTES DE HARDWARE", C_BOLD + C_WHITE))
            print(f"  Porta Serial: {status_conn} | Coordenador Local: {colorize(self.coordinator_mac, C_CYAN)}")
            print("=" * 65)
            print("  [1] Fazer Varredura de Nós (DISCOVER / Broadcast Rádio)")
            print(f"  [2] {colorize('Painel Deliberado de LEDs (Sub-Menu Estático / Dual 1-2-3)', C_BOLD + C_CYAN)}")
            print("  [3] Teste Cíclico de Cores (Diagnóstico Rápido R-G-B)")
            print("  [4] Monitor / Sniffer RFID em Tempo Real (Leitura de Cartões)")
            print("  [5] Enviar Comando Serial Raw (Customizado)")
            print("  [6] Alternar / Reconectar Porta COM")
            print(f"  [7] {colorize('Diagnóstico de Hardware SPI e MFRC522 (Comando DIAG)', C_BOLD + C_YELLOW)}")
            print("  [0] Sair do Utilitário")
            print("=" * 65)

            try:
                opcao = input("Escolha uma opção > ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if opcao == '1':
                self.comando_descobrir()
            elif opcao == '2':
                self.controlar_leds_menu()
            elif opcao == '3':
                # Teste cíclico geral (Broadcast)
                self.executar_teste_rgb_ciclico("FF:FF:FF:FF:FF:FF", is_local=False)
            elif opcao == '4':
                self.modo_sniffer_rfid()
            elif opcao == '5':
                cmd = input("Digite o comando serial (ex: PING, DISCOVER, LEDS;2;1) > ").strip()
                if cmd:
                    self.enviar_raw(cmd)
            elif opcao == '6':
                portas = self.listar_portas()
                print("\nPortas COM disponíveis no sistema:")
                for i, p in enumerate(portas, 1):
                    print(f"  [{i}] {p.device} - {p.description}")
                p_esc = input("Selecione o número da porta > ").strip()
                try:
                    p_idx = int(p_esc) - 1
                    if 0 <= p_idx < len(portas):
                        self.conectar(portas[p_idx].device)
                except Exception:
                    print(colorize("[ERRO] Seleção inválida!", C_RED))
            elif opcao == '7':
                self.executar_diagnostico_hardware()
            elif opcao == '0':
                break
            else:
                print(colorize("[ERRO] Opção não reconhecida!", C_RED))

        self.desconectar()
        print(colorize("\n[SISTEMA] Utilitário encerrado. Até mais!\n", C_CYAN))

def main():
    app = TerminalControleHardware()
    # Tenta conexão automática na inicialização
    app.conectar()
    app.menu_principal()

if __name__ == "__main__":
    main()
