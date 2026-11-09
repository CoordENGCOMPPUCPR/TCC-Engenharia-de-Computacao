import threading
import time
import random
import atexit

class AdaptadorCoordenador(threading.Thread):
    """
    Classe driver de comunicação. Executa em uma thread paralela
    escutando a porta COM serial do hardware ou emulando pacotes.
    """
    def __init__(self, porta_com=None, baudrate=115200, callback_mensagem=None, mock=False):
        super().__init__()
        self.porta_com = porta_com
        self.baudrate = baudrate
        self.callback = callback_mensagem
        self.mock = mock
        self.connected = False
        self.running = False
        self.coordinator_mac = None
        self.ser = None
        self._stop_event = threading.Event()
        self.daemon = True # Encerra com a aplicação principal
        
        # Garante liberação absoluta da porta serial ao encerrar o processo Python
        atexit.register(self.parar)

    def run(self):
        self.running = True
        self._stop_event.clear()
        print(f"[SERIAL] Iniciando driver de rádio (Modo Mock={self.mock}) na porta {self.porta_com or 'AUTO'}...")
        
        if self.mock:
            self._loop_mock()
        else:
            self._loop_serial()

    def parar(self):
        """Encerra o loop e fecha imediatamente a conexão serial liberando a porta COM no SO."""
        self.running = False
        self.connected = False
        self._stop_event.set()
        if hasattr(self, 'ser') and self.ser:
            try:
                if getattr(self.ser, 'is_open', False):
                    self.ser.close()
                    print(f"[SERIAL] [OK] Porta {self.porta_com} fechada com sucesso em parar().")
            except Exception as e:
                print(f"[SERIAL ERROR ao fechar porta]: {e}")
            finally:
                self.ser = None
        
        # Se for chamada de outra thread, aguarda o encerramento do loop para liberar a porta no SO
        if threading.current_thread() != self and self.is_alive():
            try:
                self.join(timeout=1.5)
            except Exception:
                pass

    def enviar_comando_no(self, mac_destino, comando):
        """
        Envia um pacote via serial para o Adaptador Coordenador,
        que o retransmitirá via ESP-NOW para o Nó Repórter de destino.
        Formato: SEND;<mac_address>;<comando>\n
        """
        payload = f"SEND;{mac_destino};{comando}\n"
        if self.mock:
            print(f"[SERIAL - MOCK SEND] Enviando para o Nó {mac_destino}: {comando}")
        else:
            if hasattr(self, 'ser') and self.ser and getattr(self.ser, 'is_open', False):
                try:
                    self.ser.write(payload.encode('utf-8'))
                    self.ser.flush()
                    print(f"[SERIAL - SEND] {payload.strip()}")
                except Exception as ex:
                    print(f"[SERIAL - ERROR] Falha ao transmitir pela porta serial: {ex}")
            else:
                print(f"[SERIAL - WARNING] Porta serial desconectada ao tentar enviar: {payload.strip()}")

    def descobrir_nos(self):
        """
        Envia o comando de varredura broadcast (DISCOVER) para o Adaptador Coordenador USB.
        O coordenador transmitirá pulsos de rádio ESP-NOW para acordar todos os nós da sala.
        """
        if self.mock:
            print("[SERIAL - MOCK] Executando varredura broadcast simulada...")
            if self.callback:
                def _simular_respostas():
                    time.sleep(0.3)
                    self.callback("DISCOVERED;00:70:07:26:E1:70;SALTOS:1;VIA:DIRETO")
                    time.sleep(0.4)
                    self.callback("DISCOVERED;00:70:07:26:E4:50;SALTOS:2;VIA:00:70:07:26:E1:70")
                threading.Thread(target=_simular_respostas, daemon=True).start()
        else:
            if hasattr(self, 'ser') and self.ser and getattr(self.ser, 'is_open', False):
                try:
                    self.ser.write(b"DISCOVER\n")
                    self.ser.flush()
                    print("[SERIAL - DISCOVER] Comando DISCOVER enviado ao Coordenador USB!")
                except Exception as ex:
                    print(f"[SERIAL - ERROR] Falha ao enviar DISCOVER: {ex}")
            else:
                print("[SERIAL - WARNING] Porta serial desconectada ao tentar disparar DISCOVER.")

    def enviar_comando_barreira(self, ativa, mac=None):
        """
        Envia o comando de simulação de barreira de rádio para o Coordenador.
        Quando ativado, o Coordenador descarta recepção direta do nó especificado,
        exigindo que o sinal salte através de outro nó (Mesh Relay).
        """
        if ativa:
            cmd = f"BARREIRA;ON;{mac}\n" if mac else "BARREIRA;ON\n"
        else:
            cmd = "BARREIRA;OFF\n"
        if self.mock:
            print(f"[SERIAL - MOCK] Barreira de rádio: {'ATIVADA' if ativa else 'DESATIVADA'} (Nó: {mac or 'TODOS'})")
            if self.callback:
                if ativa:
                    self.callback(f"[BARREIRA];ATIVADA;{mac or 'TODOS'}")
                else:
                    self.callback("[BARREIRA];DESATIVADA")
        else:
            if hasattr(self, 'ser') and self.ser and getattr(self.ser, 'is_open', False):
                try:
                    self.ser.write(cmd.encode('utf-8'))
                    self.ser.flush()
                    print(f"[SERIAL - BARREIRA] {cmd.strip()}")
                except Exception as ex:
                    print(f"[SERIAL - ERROR] Falha ao enviar comando de barreira: {ex}")

    def _loop_serial(self):
        import serial
        import serial.tools.list_ports
        
        self.connected = False
        print(f"[SERIAL] Modo Hardware Real ativado. Aguardando conexão com Adaptador Coordenador...")

        try:
            while self.running:
                if not self.connected:
                    # 1. Detectar portas seriais disponíveis no sistema
                    puertos = [port.device for port in serial.tools.list_ports.comports()]
                    port_to_try = self.porta_com

                    # Se a porta especificada não estiver conectada ou for None, busca porta USB física
                    if not port_to_try or port_to_try not in puertos:
                        for p in serial.tools.list_ports.comports():
                            desc = (p.description or "").upper()
                            hwid = (p.hwid or "").upper()
                            if "USB" in desc or "CH9102" in desc or "CP210" in desc or "CH340" in desc or "VID:PID" in hwid or p.device == "COM7":
                                port_to_try = p.device
                                break
                        if not port_to_try and "COM7" in puertos:
                            port_to_try = "COM7"

                    if not port_to_try:
                        time.sleep(1.5)
                        continue

                    # 2. Tentar abrir a porta serial física sem prender o ESP32 em reset
                    try:
                        self.ser = serial.Serial()
                        self.ser.port = port_to_try
                        self.ser.baudrate = self.baudrate
                        self.ser.timeout = 1
                        self.ser.dtr = False
                        self.ser.rts = False
                        self.ser.open()
                        # Garante que as linhas DTR e RTS estão desativadas (evita reset no CH9102/CP210)
                        self.ser.dtr = False
                        self.ser.rts = False
                        # Aguarda brevemente o bootloader do ESP32 inicializar
                        time.sleep(1.0)
                        self.ser.reset_input_buffer()

                        self.connected = True
                        self.porta_com = port_to_try
                        print(f"[SERIAL] [OK] Conectado com sucesso ao Adaptador Coordenador na porta {port_to_try}!")
                        try:
                            self.ser.write(b"PING\n")
                            self.ser.flush()
                        except Exception:
                            pass
                        if self.callback:
                            self.callback(f"STATUS;CONNECTED;{port_to_try}")
                    except Exception as ex_open:
                        self.connected = False
                        time.sleep(1.5)
                        continue

                # 3. Leitura contínua enquanto conectado
                try:
                    raw_bytes = self.ser.readline()
                    if raw_bytes:
                        linha = raw_bytes.decode('utf-8', errors='ignore').strip()
                        if linha:
                            if "MAC:" in linha:
                                part_mac = linha.split("MAC:")[-1].strip().upper()
                                if len(part_mac) >= 17:
                                    self.coordinator_mac = part_mac[:17]
                                    print(f"[SERIAL] [COORD] Coordenador USB Físico identificado: {self.coordinator_mac}")
                                    if self.callback:
                                        self.callback(f"COORDINATOR_MAC;{self.coordinator_mac}")
                            elif "Endereço MAC Físico:" in linha:
                                part_mac = linha.split("Endereço MAC Físico:")[-1].strip().upper()
                                if len(part_mac) >= 17:
                                    self.coordinator_mac = part_mac[:17]
                                    print(f"[SERIAL] [COORD] Coordenador USB Físico identificado: {self.coordinator_mac}")
                                    if self.callback:
                                        self.callback(f"COORDINATOR_MAC;{self.coordinator_mac}")
                            if self.callback:
                                self.callback(linha)
                    time.sleep(0.005)
                except Exception as ex_read:
                    if not self.running:
                        break
                    print(f"[SERIAL - WARNING] Desconexão física na porta {self.porta_com}: {ex_read}. Tentando reconectar...")
                    self.connected = False
                    try:
                        if hasattr(self, 'ser') and self.ser:
                            self.ser.close()
                    except Exception:
                        pass
                    if self.callback:
                        self.callback(f"STATUS;DISCONNECTED;{self.porta_com}")
                    time.sleep(1.5)
        finally:
            try:
                if hasattr(self, 'ser') and self.ser and getattr(self.ser, 'is_open', False):
                    self.ser.close()
                    print(f"[SERIAL] [OK] Porta serial {self.porta_com} liberada com sucesso na finalização do loop.")
            except Exception:
                pass
            self.connected = False
            self.ser = None

    def _loop_mock(self):
        """
        Emulador de escuta serial.
        A geração automática de eventos aleatórios foi desativada para garantir
        estabilidade absoluta e evitar injeção de pacotes falsos durante a operação.
        """
        print("[SERIAL - MOCK] Modo Mock inicializado em repouso passivo (geração aleatória desativada).")
        while self.running:
            if self._stop_event.wait(timeout=1.0):
                break

if __name__ == "__main__":
    def print_msg(msg):
        print(f"Callback acionado com: {msg}")
        
    driver = AdaptadorCoordenador(callback_mensagem=print_msg, mock=True)
    driver.start()
    
    # Executa por 5 segundos para teste
    time.sleep(5)
    driver.parar()
