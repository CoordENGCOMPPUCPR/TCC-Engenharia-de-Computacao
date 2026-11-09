import sys, os
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from database.db_manager import BancoDeDados
from motor.tournament_engine import MotorDoTorneio
from gateway.serial_driver import AdaptadorCoordenador

try:
    import qrcode
    from PIL import Image, ImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False

# =============================================================================
# IDENTIDADE VISUAL TRYHARD ARENA (Central de Comando E-Sports / FGC)
# =============================================================================
THEME_TRYHARD = {
    "bg_main": "#0B0E14",         # Arena Void (fundo principal da janela)
    "bg_card": "#141922",         # Hex Slate (containers e cards)
    "bg_card_alt": "#1A222F",     # Variação sutil para cards internos/hover
    "border": "#222C3A",          # Borda de cards e divisores
    "border_focus": "#2DB5F6",    # Borda ciano ativa
    "primary": "#2DB5F6",         # TryHard Cyan (destaques e ações)
    "primary_hover": "#1BA0DF",   # Hover do Ciano
    "primary_text": "#0B0E14",    # Texto sobre primário (preto/contraste)
    "rage_red": "#E84125",        # Rage Red (conflito, ação ativa, em jogo, score)
    "rage_red_hover": "#CF341A",  # Hover do vermelho
    "status_waiting": "#F59E0B",  # Amber (convocado, aguardando confirmação)
    "status_success": "#10B981",  # Emerald Green (PoPL, sucesso, finalizada)
    "text_main": "#F8FAFC",       # Textos principais
    "text_muted": "#8A99AD",      # Textos secundários / telemetria
    "terminal_bg": "#07090D",     # Fundo preto terminal profundo
}

def listar_portas_com():
    """Detecta portas seriais disponíveis no sistema com fallbacks."""
    try:
        import serial.tools.list_ports
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            ports = ["COM7", "COM3", "COM5"]
        return ports
    except Exception:
        return ["COM7", "COM3", "COM5"]

def obter_ip_local():
    """Detecta dinamicamente o endereço IPv4 ativo do computador na rede local / Wi-Fi / Hotspot."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip

class AutoreporterGUIApp:
    def obter_ip_local(self):
        return obter_ip_local()

    def __init__(self, root):
        self.root = root
        self.root.title("Autoreporter v1.1 - Sistema Ciberfísico de Torneios (PoC PUCPR 2026)")
        self.root.geometry("1100x720")
        self.root.minsize(950, 620)
        self.root.configure(bg=THEME_TRYHARD["bg_main"])

        # 1. Conectar Camadas de Backend
        user_dir = os.path.join(os.path.expanduser("~"), ".autoreporter")
        os.makedirs(user_dir, exist_ok=True)
        db_path = os.path.join(user_dir, "autoreporter.db")
        self.db = BancoDeDados(db_path)
        self.db.inicializar_banco()
        self.db.popular_dados_exemplo()

        # Driver Serial: Prioriza portas físicas reais (COM7, CH9102, CP210, etc.) com auto-reconexão
        import serial.tools.list_ports
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        target_port = "COM7" if "COM7" in available_ports else None
        if not target_port:
            for p in serial.tools.list_ports.comports():
                desc = (p.description or "").upper()
                if "CH9102" in desc or "CP210" in desc or "CH340" in desc or "USB" in desc:
                    target_port = p.device
                    break
        if not target_port:
            target_port = "COM7"

        self.driver_serial = AdaptadorCoordenador(
            porta_com=target_port, 
            baudrate=115200, 
            callback_mensagem=self.on_mensagem_serial_recebida, 
            mock=False
        )
        self.driver_serial.start()
        
        self.motor = MotorDoTorneio(self.db, driver_serial=self.driver_serial)

        # Flags de Estado
        self.servidor_rodando = False
        cursor_ev = self.db.conn.cursor()
        cursor_ev.execute("SELECT id FROM events ORDER BY id DESC LIMIT 1")
        row_ev = cursor_ev.fetchone()
        self.evento_selecionado_id = row_ev["id"] if row_ev else None
        self.modulo_atual = 1           # 1: Eventos, 2: Jogadores, 3: Hardware
        self.map_torneios_global = {}   # Mapeamento {desc: event_id}
        self.node_telemetry = {}        # Rastreamento de telemetria em tempo real por MAC
        self.active_new_node_callback = None  # Callback para pareamento dinâmico de novos nós
        self.active_rfid_capture_callback = None  # Callback para captura de tags RFID
        self.ultima_tag_lida = None
        self.ultimo_no_mac = None
        self.ultimo_timestamp_rfid = None
        self.lbl_scanner_tag = None
        self.coordenador_usb_mac = "00:70:07:26:E1:70"
        self.bracket_zoom = 1.0         # Fator de escala do chaveamento interativo (0.5x a 2.0x)
        self.barreira_mesh_ativa = False
        self.barreira_mac_bloqueado = None
        self.ultima_rota_mesh = {
            "origem": None,
            "via": "DIRETO",
            "saltos": 1,
            "timestamp": None,
            "tipo": None
        }
        self.lbl_rota_mesh_status = None
        self.btn_toggle_barreira = None

        # Construção da Interface
        self.setup_ui()

        # Encerramento Gracioso Vinculado ao Botão Fechar da Janela [X]
        self.root.protocol("WM_DELETE_WINDOW", self.fechar_aplicacao_gracioso)

    def atualizar_telemetria_no(self, mac_address, tipo, payload):
        """Atualiza a telemetria do nó em memória com timestamp, status e histórico."""
        mac_clean = str(mac_address).strip().upper()
        if not mac_clean:
            return
        now = time.time()
        time_str = time.strftime("%H:%M:%S")
        entry = self.node_telemetry.get(mac_clean, {
            "mac_address": mac_clean,
            "first_seen": time_str,
            "history": []
        })
        entry["last_seen"] = now
        entry["last_seen_str"] = time_str
        entry["last_type"] = tipo
        entry["last_payload"] = payload
        entry["status"] = "ONLINE"
        
        log_msg = f"[{time_str}] [{tipo}] {payload}"
        entry["history"].insert(0, log_msg)
        if len(entry["history"]) > 30:
            entry["history"].pop()
            
        self.node_telemetry[mac_clean] = entry

        # Auto-registro do nó no inventário do banco caso seja um hardware novo com MAC válido
        import re
        if re.match(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", mac_clean):
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO nodes (mac_address, nickname, type) VALUES (?, ?, 'REPORTER')", 
                               (mac_clean, f"Nó {mac_clean[-5:]}"))
                self.db.conn.commit()
            except Exception:
                pass

    def setup_ui(self):
        # Container Principal
        if HAS_CTK:
            self.main_container = ctk.CTkFrame(self.root, fg_color=THEME_TRYHARD["bg_main"], corner_radius=0)
        else:
            self.main_container = tk.Frame(self.root, bg=THEME_TRYHARD["bg_main"])
        self.main_container.pack(fill="both", expand=True)

        # ---------------------------------------------------------------------
        # 1. HEADER GLOBAL DE TOPO (Fixado no topo)
        # ---------------------------------------------------------------------
        self.create_header()

        # ---------------------------------------------------------------------
        # 2. BARRA DE NAVEGAÇÃO INFERIOR (Fixada no rodapé em primeiro lugar)
        # ---------------------------------------------------------------------
        self.create_navbar()

        # ---------------------------------------------------------------------
        # 3. CONTEÚDO CENTRAL (Preenche todo o espaço intermediário restante)
        # ---------------------------------------------------------------------
        if HAS_CTK:
            self.content_area = ctk.CTkFrame(self.main_container, fg_color=THEME_TRYHARD["bg_main"], corner_radius=0)
        else:
            self.content_area = tk.Frame(self.main_container, bg=THEME_TRYHARD["bg_main"])
        self.content_area.pack(fill="both", expand=True, padx=10, pady=5)

        # Atualiza a lista de torneios no dropdown global do topo
        self.atualizar_combo_torneios_global()

        # Abrir Módulo 1 por Padrão
        self.show_modulo_eventos()

    def create_header(self):
        if HAS_CTK:
            header_frame = ctk.CTkFrame(self.main_container, height=52, fg_color=THEME_TRYHARD["bg_card"], corner_radius=0)
            header_frame.pack(fill="x", side="top", padx=0, pady=0)

            # Borda inferior fina divisória
            header_border = ctk.CTkFrame(self.main_container, height=1, fg_color=THEME_TRYHARD["border"], corner_radius=0)
            header_border.pack(fill="x", side="top", padx=0, pady=0)

            # Logotipo: Badge temático TryHard ⬡💢 antes de AUTOREPORTER v1.1 em Ciano Neon
            lbl_title = ctk.CTkLabel(
                header_frame,
                text="⬡💢 AUTOREPORTER v1.1",
                font=("Helvetica", 16, "bold"),
                text_color=THEME_TRYHARD["primary"]
            )
            lbl_title.pack(side="left", padx=15, pady=10)

            lbl_poc = ctk.CTkLabel(
                header_frame,
                text="[ PoC PUCPR 2026 ]",
                font=("Helvetica", 11),
                text_color=THEME_TRYHARD["text_muted"]
            )
            lbl_poc.pack(side="left", padx=0, pady=10)

            # Seletor Global de Torneio em Foco
            frame_foco = ctk.CTkFrame(header_frame, fg_color="transparent")
            frame_foco.pack(side="left", padx=(25, 10), pady=10)

            lbl_foco = ctk.CTkLabel(
                frame_foco,
                text="🏆 Torneio em Foco:",
                font=("Helvetica", 11, "bold"),
                text_color=THEME_TRYHARD["text_main"]
            )
            lbl_foco.pack(side="left", padx=(0, 6))

            self.combo_torneio_global = ctk.CTkComboBox(
                frame_foco,
                values=["Carregando..."],
                width=260,
                height=28,
                fg_color=THEME_TRYHARD["bg_card"],
                text_color=THEME_TRYHARD["text_main"],
                border_color=THEME_TRYHARD["primary"],
                border_width=1,
                button_color=THEME_TRYHARD["border"],
                button_hover_color=THEME_TRYHARD["primary"],
                dropdown_fg_color=THEME_TRYHARD["bg_card"],
                dropdown_text_color=THEME_TRYHARD["text_main"],
                dropdown_hover_color=THEME_TRYHARD["bg_card_alt"],
                command=self.on_mudar_torneio_foco_global
            )
            self.combo_torneio_global.pack(side="left")

            # Badges de Status Globais (Direita)
            self.lbl_status_com = ctk.CTkLabel(
                header_frame,
                text="COM: Pronto",
                font=("Helvetica", 11, "bold"),
                text_color=THEME_TRYHARD["status_success"]
            )
            self.lbl_status_com.pack(side="right", padx=15)

            self.lbl_status_server = ctk.CTkLabel(
                header_frame,
                text="Servidor: OFF",
                font=("Helvetica", 11, "bold"),
                text_color=THEME_TRYHARD["rage_red"]
            )
            self.lbl_status_server.pack(side="right", padx=10)

            self.btn_toggle_server = ctk.CTkButton(
                header_frame,
                text="Ligar Servidor Web",
                width=130,
                height=28,
                command=self.toggle_servidor_web,
                fg_color=THEME_TRYHARD["border"],
                hover_color=THEME_TRYHARD["primary_hover"],
                text_color=THEME_TRYHARD["text_main"]
            )
            self.btn_toggle_server.pack(side="right", padx=10)

            lbl_db = ctk.CTkLabel(
                header_frame,
                text="BD: OK",
                font=("Helvetica", 11, "bold"),
                text_color=THEME_TRYHARD["status_success"]
            )
            lbl_db.pack(side="right", padx=10)

    def atualizar_combo_torneios_global(self):
        """Atualiza dinamicamente as opções do seletor global de Torneio em Foco no Header."""
        if not hasattr(self, "combo_torneio_global") or not self.combo_torneio_global:
            return

        eventos = self.db.obter_todos_eventos("", "Todos")
        self.map_torneios_global = {}
        opcoes = []
        selected_desc = None

        for ev in eventos:
            desc = f"#{ev['id']} - {ev['name']}"
            self.map_torneios_global[desc] = ev["id"]
            opcoes.append(desc)
            if self.evento_selecionado_id == ev["id"]:
                selected_desc = desc

        if not opcoes:
            opcoes = ["Nenhum Torneio Cadastrado"]
            self.combo_torneio_global.configure(values=opcoes)
            self.combo_torneio_global.set(opcoes[0])
            self.evento_selecionado_id = None
        else:
            self.combo_torneio_global.configure(values=opcoes)
            if selected_desc:
                self.combo_torneio_global.set(selected_desc)
            else:
                self.combo_torneio_global.set(opcoes[0])
                self.evento_selecionado_id = self.map_torneios_global[opcoes[0]]

    def on_mudar_torneio_foco_global(self, escolha_texto):
        """Disparado quando o operador seleciona outro Torneio em Foco no Header."""
        novo_id = self.map_torneios_global.get(escolha_texto)
        if novo_id and novo_id != self.evento_selecionado_id:
            self.evento_selecionado_id = novo_id
            self.refresh_aba_atual_apos_troca_foco()

    def refresh_aba_atual_apos_troca_foco(self):
        """Recarrega a tela ativa no momento para sincronizar o novo torneio em foco."""
        mod = getattr(self, "modulo_atual", 1)
        if mod == 1:
            ev = self.db.obter_evento(self.evento_selecionado_id)
            self.show_modulo_eventos()
            if ev:
                if ev["status"] == "DRAFT":
                    self.event_tab_frame.set("✏️ Edição / Preparação")
                else:
                    self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")
        elif mod == 3:
            self.show_modulo_hardware()
        else:
            header_frame = tk.Frame(self.main_container, bg="#1E1E1E", height=50)
            header_frame.pack(fill="x", side="top")
            lbl = tk.Label(header_frame, text="AUTOREPORTER - PoC PUCPR 2026", fg="white", bg="#1E1E1E", font=("Helvetica", 14, "bold"))
            lbl.pack(side="left", padx=15, pady=10)

    def create_navbar(self):
        if HAS_CTK:
            # Borda superior fina na barra de navegação
            nav_border = ctk.CTkFrame(self.main_container, height=1, fg_color=THEME_TRYHARD["border"], corner_radius=0)
            nav_border.pack(fill="x", side="bottom", padx=0, pady=0)

            nav_frame = ctk.CTkFrame(self.main_container, height=55, fg_color=THEME_TRYHARD["bg_card"], corner_radius=0)
            nav_frame.pack(fill="x", side="bottom", padx=0, pady=0)

            self.btn_nav_mod1 = ctk.CTkButton(
                nav_frame,
                text="🏆 1. Eventos & Torneios",
                font=("Helvetica", 13, "bold"),
                height=40,
                command=self.show_modulo_eventos
            )
            self.btn_nav_mod1.pack(side="left", expand=True, fill="x", padx=5, pady=8)

            self.btn_nav_mod2 = ctk.CTkButton(
                nav_frame,
                text="👤 2. Jogadores",
                font=("Helvetica", 13, "bold"),
                height=40,
                command=self.show_modulo_jogadores
            )
            self.btn_nav_mod2.pack(side="left", expand=True, fill="x", padx=5, pady=8)

            self.btn_nav_mod3 = ctk.CTkButton(
                nav_frame,
                text="📡 3. Hardware & Servidor",
                font=("Helvetica", 13, "bold"),
                height=40,
                command=self.show_modulo_hardware
            )
            self.btn_nav_mod3.pack(side="left", expand=True, fill="x", padx=5, pady=8)

            self.btn_nav_mod4 = ctk.CTkButton(
                nav_frame,
                text="🚪 4. Sair",
                font=("Helvetica", 13, "bold"),
                height=40,
                fg_color=THEME_TRYHARD["bg_card"],
                hover_color=THEME_TRYHARD["rage_red"],
                border_width=1,
                border_color=THEME_TRYHARD["rage_red"],
                text_color=THEME_TRYHARD["rage_red"],
                command=self.confirmar_sair
            )
            self.btn_nav_mod4.pack(side="left", expand=True, fill="x", padx=5, pady=8)

            self.update_navbar_active_state(self.modulo_atual)

    def update_navbar_active_state(self, modulo_num):
        """Destaca o botão do módulo ativo no padrão TryHard Arena."""
        if not HAS_CTK:
            return
        btn_map = {
            1: getattr(self, "btn_nav_mod1", None),
            2: getattr(self, "btn_nav_mod2", None),
            3: getattr(self, "btn_nav_mod3", None)
        }
        for m_num, btn in btn_map.items():
            if not btn:
                continue
            if m_num == modulo_num:
                btn.configure(
                    fg_color=THEME_TRYHARD["primary"],
                    hover_color=THEME_TRYHARD["primary_hover"],
                    text_color=THEME_TRYHARD["primary_text"],
                    border_width=0
                )
            else:
                btn.configure(
                    fg_color=THEME_TRYHARD["bg_card"],
                    hover_color=THEME_TRYHARD["bg_card_alt"],
                    text_color=THEME_TRYHARD["text_muted"],
                    border_width=1,
                    border_color=THEME_TRYHARD["border"]
                )

    def clear_content_area(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

    # -------------------------------------------------------------------------
    # MÓDULO 1: EVENTOS & TORNEIOS
    # -------------------------------------------------------------------------
    def show_modulo_eventos(self):
        self.clear_content_area()
        self.modulo_atual = 1
        self.update_navbar_active_state(1)

        if HAS_CTK:
            title = ctk.CTkLabel(self.content_area, text="🏆 Módulo 1: Eventos & Torneios", font=("Helvetica", 18, "bold"))
            title.pack(anchor="w", padx=15, pady=10)

            # Sub-Abas de Eventos
            self.event_tab_frame = ctk.CTkTabview(
                self.content_area,
                fg_color=THEME_TRYHARD["bg_card"],
                segmented_button_fg_color=THEME_TRYHARD["bg_main"],
                segmented_button_selected_color=THEME_TRYHARD["primary"],
                segmented_button_selected_hover_color=THEME_TRYHARD["primary_hover"],
                segmented_button_unselected_color=THEME_TRYHARD["bg_card"],
                segmented_button_unselected_hover_color=THEME_TRYHARD["bg_card_alt"],
                text_color=THEME_TRYHARD["text_main"]
            )
            self.event_tab_frame.pack(fill="both", expand=True, padx=10, pady=5)

            tab_lista = self.event_tab_frame.add("📋 Lista de Eventos")
            tab_prep = self.event_tab_frame.add("✏️ Edição / Preparação")
            tab_brackets = self.event_tab_frame.add("🌲 Árvore de Brackets Interativa")
            self.tab_brackets_frame = tab_brackets

            # Contribuição 1: Lista de Eventos
            self.setup_tab_lista_eventos(tab_lista)

            # Contribuição 2: Preparação (Draft)
            self.setup_tab_preparacao_evento(tab_prep)

            # Contribuição 3: Árvore de Brackets
            self.setup_tab_brackets(tab_brackets)

    def atualizar_view_brackets(self):
        """Atualiza a renderização dos brackets de forma thread-safe se estiver no módulo de eventos."""
        def _refresh():
            try:
                if getattr(self, "modulo_atual", None) == 1 and hasattr(self, "tab_brackets_frame"):
                    self.setup_tab_brackets(self.tab_brackets_frame)
            except Exception as e:
                print(f"[GUI BRACKETS REFRESH ERROR] {e}")
        if hasattr(self, "root") and self.root:
            self.root.after(0, _refresh)

    def setup_tab_lista_eventos(self, parent):
        if not HAS_CTK:
            return

        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=10)

        entry_search = ctk.CTkEntry(top_bar, placeholder_text="Buscar evento por nome...", width=200)
        entry_search.pack(side="left", padx=2)

        # Dropdown para filtro de status
        combo_filter = ctk.CTkComboBox(top_bar, values=["Todos", "DRAFT", "IN_PROGRESS", "FINISHED"], width=130)
        combo_filter.set("Todos")
        combo_filter.pack(side="left", padx=2)

        btn_search = ctk.CTkButton(top_bar, text="🔍 Buscar", width=80,
                                   command=lambda: self.refresh_lista_eventos(scroll_frame, entry_search.get(), combo_filter.get()))
        btn_search.pack(side="left", padx=2)

        btn_novo = ctk.CTkButton(top_bar, text="+ Criar Novo Evento", fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 12, "bold"), command=self.modal_novo_evento)
        btn_novo.pack(side="right", padx=2)

        # Tabela de Eventos (Scrollable)
        scroll_frame = ctk.CTkScrollableFrame(parent, label_text="Campeonatos Cadastrados (Duplo clique para abrir)")
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Renderização inicial
        self.refresh_lista_eventos(scroll_frame, "", "Todos")

    def bind_double_click(self, widget, callback):
        """Propaga o evento de duplo clique de forma recursiva e robusta por todos os filhos."""
        if isinstance(widget, ctk.CTkButton):
            return
        widget.bind("<Double-Button-1>", callback)
        for attr in ["_canvas", "_label", "_entry"]:
            sub_w = getattr(widget, attr, None)
            if sub_w and hasattr(sub_w, "bind"):
                sub_w.bind("<Double-Button-1>", callback)
        for child in widget.winfo_children():
            self.bind_double_click(child, callback)

    def refresh_lista_eventos(self, scroll_frame, query="", status_filter="Todos"):
        for widget in scroll_frame.winfo_children():
            widget.destroy()

        eventos = self.db.obter_todos_eventos(query, status_filter)

        if not eventos:
            lbl_empty = ctk.CTkLabel(scroll_frame, text="Nenhum evento encontrado.", font=("Helvetica", 11))
            lbl_empty.pack(padx=20, pady=20)
            return

        for ev in eventos:
            is_active = (ev['id'] == self.evento_selecionado_id)
            row_bg = THEME_TRYHARD["bg_card_alt"] if is_active else THEME_TRYHARD["bg_card"]
            row_b_col = THEME_TRYHARD["primary"] if is_active else THEME_TRYHARD["border"]
            row_b_w = 2 if is_active else 1

            row = ctk.CTkFrame(scroll_frame, fg_color=row_bg, border_width=row_b_w, border_color=row_b_col, height=45)
            row.pack(fill="x", padx=5, pady=4)

            status_map = {
                "DRAFT": ("● Rascunho", THEME_TRYHARD["status_waiting"]),
                "IN_PROGRESS": ("💢 Em Andamento", THEME_TRYHARD["rage_red"]),
                "FINISHED": ("● Finalizado", THEME_TRYHARD["status_success"])
            }
            st_text, st_color = status_map.get(ev['status'], ("● Rascunho", "#D97706"))

            lbl_name = ctk.CTkLabel(row, text=f"ID {ev['id']} - {ev['name']}", font=("Helvetica", 13, "bold"))
            lbl_name.pack(side="left", padx=15, pady=10)

            lbl_date = ctk.CTkLabel(row, text=f"Data: {ev['date']}", font=("Helvetica", 11), text_color="#AAAAAA")
            lbl_date.pack(side="left", padx=15, pady=10)

            lbl_st = ctk.CTkLabel(row, text=st_text, font=("Helvetica", 11, "bold"), text_color=st_color)
            lbl_st.pack(side="left", padx=15, pady=10)

            # Vincula duplo clique em toda a linha para selecionar silenciosamente
            self.bind_double_click(row, lambda e, e_id=ev['id']: self.selecionar_evento(e_id))

            def deletar_ev(e_id=ev['id'], e_name=ev['name']):
                if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza de que deseja excluir permanentemente o torneio '{e_name}' (ID {e_id}) e todas as suas partidas?"):
                    self.db.excluir_evento(e_id)
                    if self.evento_selecionado_id == e_id:
                        self.evento_selecionado_id = None
                    self.atualizar_combo_torneios_global()
                    messagebox.showinfo("Sucesso", "Torneio excluído com sucesso!")
                    self.refresh_lista_eventos(scroll_frame, query, status_filter)

            btn_del = ctk.CTkButton(row, text="🗑️", width=35, height=28, fg_color=THEME_TRYHARD["rage_red"], hover_color=THEME_TRYHARD["rage_red_hover"],
                                    command=deletar_ev)
            btn_del.pack(side="right", padx=15, pady=5)

    def obter_opcoes_hardware_dropdown(self):
        """
        Retorna (lista_labels, mapa_label_para_mac) para ser usado em dropdowns de seleção de hardware.
        Lista todos os nós cadastrados no banco de dados e adiciona a opção de modo manual.
        """
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT mac_address, nickname, type FROM nodes ORDER BY type DESC, nickname ASC, mac_address ASC")
        nos = cursor.fetchall()

        opcoes = ["⚠️ Sem Hardware (Modo Manual)"]
        mapa = {"⚠️ Sem Hardware (Modo Manual)": None}

        for n in nos:
            mac = n["mac_address"]
            nick = n["nickname"] or f"Nó {mac[-5:]}"
            t_icon = "🎮" if n["type"] == "REPORTER" else "🔌"
            label = f"{t_icon} {nick} [{mac}]"
            opcoes.append(label)
            mapa[label] = mac

        return opcoes, mapa

    def obter_label_para_mac(self, node_mac, opcoes_mapa):
        """Mapeia um endereço MAC para o respectivo label exibido nos Dropdowns."""
        if not node_mac:
            return "⚠️ Sem Hardware (Modo Manual)"
        mac_clean = str(node_mac).strip().upper()
        for label, mac in opcoes_mapa.items():
            if mac and mac.upper() == mac_clean:
                return label
        return f"📡 Nó [{mac_clean}]"

    def setup_tab_preparacao_evento(self, parent):
        if not HAS_CTK:
            return

        for widget in parent.winfo_children():
            widget.destroy()

        if not getattr(self, "evento_selecionado_id", None):
            lbl_err = ctk.CTkLabel(parent, text="⚠️ Nenhum campeonato selecionado.\nPor favor, vá para a aba 'Lista de Eventos' e selecione um torneio ativo.", font=("Helvetica", 14, "bold"), text_color="#FF4444")
            lbl_err.pack(expand=True)
            return

        ev = self.db.obter_evento(self.evento_selecionado_id)
        if not ev:
            return

        # Cabeçalho da Preparação
        header_prep = ctk.CTkFrame(parent, fg_color="transparent")
        header_prep.pack(fill="x", padx=10, pady=5)

        lbl_title = ctk.CTkLabel(header_prep, text=f"✏️ Preparação de Campeonato: {ev['name']}", font=("Helvetica", 15, "bold"))
        lbl_title.pack(side="left", padx=5)

        st_map = {
            "DRAFT": ("Rascunho", "#D97706"),
            "IN_PROGRESS": ("Em Andamento", "#00FF88"),
            "FINISHED": ("Finalizado", "#3B82F6")
        }
        st_txt, st_col = st_map.get(ev["status"], ("Rascunho", "#D97706"))
        lbl_status = ctk.CTkLabel(header_prep, text=f" Status: {st_txt} ", fg_color=st_col, font=("Helvetica", 11, "bold"), corner_radius=6)
        lbl_status.pack(side="left", padx=15)

        if ev["status"] != "DRAFT":
            lbl_info = ctk.CTkLabel(parent, text="Este campeonato já foi INICIADO ou FINALIZADO.\nAs configurações de participantes e chaves estão congeladas.\n\nAcesse a aba 'Árvore de Brackets Interativa' para gerenciar e visualizar as partidas.", font=("Helvetica", 13, "bold"), text_color="#AAAAAA")
            lbl_info.pack(expand=True, pady=40)
            return

        # Grid principal da Preparação (Duas Colunas)
        grid_frame = ctk.CTkFrame(parent, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Coluna Esquerda: Cadastro e Inscrição de Atletas (60%)
        col_left = ctk.CTkFrame(grid_frame, fg_color="#1E1E1E")
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=0)

        lbl_parts_title = ctk.CTkLabel(col_left, text="Selecione os competidores inscritos para esta chave:", font=("Helvetica", 12, "bold"))
        lbl_parts_title.pack(anchor="w", padx=15, pady=(10, 2))

        # Barra de Busca Dinâmica de Atletas
        search_prep_frame = ctk.CTkFrame(col_left, fg_color="transparent")
        search_prep_frame.pack(fill="x", padx=10, pady=(2, 5))

        entry_search_prep = ctk.CTkEntry(search_prep_frame, placeholder_text="🔍 Buscar atleta por apelido ou nome real...", height=32)
        entry_search_prep.pack(fill="x", expand=True)

        scroll_parts = ctk.CTkScrollableFrame(col_left, label_text="Competidores Disponíveis no Banco")
        scroll_parts.pack(fill="both", expand=True, padx=10, pady=5)

        # Buscar todos os jogadores e os inscritos nesse evento
        todos_jogadores = self.db.buscar_jogadores(query="", incluir_inativos=False)
        participantes_atuais = self.db.obter_participantes_evento(self.evento_selecionado_id)
        inscritos_ids = {p["id"] for p in participantes_atuais}

        self.athlete_checkboxes = {}
        row_frames_prep = {}

        for player in todos_jogadores:
            row_p = ctk.CTkFrame(scroll_parts, fg_color="#242424", height=40)
            row_p.pack(fill="x", padx=5, pady=3)

            p_id = player["id"]
            checked = p_id in inscritos_ids
            has_tag = player["tag_uid"] is not None and len(player["tag_uid"].strip()) > 0

            chk = ctk.CTkCheckBox(row_p, text=f"{player['nickname']}", font=("Helvetica", 12))
            if checked:
                chk.select()
            chk.pack(side="left", padx=10, pady=8)
            self.athlete_checkboxes[p_id] = (chk, has_tag)
            row_frames_prep[p_id] = (row_p, player["nickname"], player["real_name"])

            if has_tag:
                lbl_tag = ctk.CTkLabel(row_p, text=f"🏷️ {player['tag_uid']}", font=("Helvetica", 10), text_color="#00FF88")
                lbl_tag.pack(side="right", padx=10)
            else:
                warning_frame = ctk.CTkFrame(row_p, fg_color="transparent")
                warning_frame.pack(side="right", padx=5)

                lbl_warn = ctk.CTkLabel(warning_frame, text="⚠️ Sem Tag", font=("Helvetica", 10, "bold"), text_color="#FF9900")
                lbl_warn.pack(side="left", padx=5)

                btn_bind = ctk.CTkButton(warning_frame, text="Vincular", width=60, height=22, fg_color="#D97706", hover_color="#B45309",
                                         command=lambda p_id=p_id, nick=player["nickname"]: self.modal_vincular_rfid_onthefly(p_id, nick))
                btn_bind.pack(side="left", padx=2)

        def filter_prep_list(event=None):
            q = entry_search_prep.get().strip().lower()
            for p_id, (r_frame, nick, real) in row_frames_prep.items():
                if not q or q in nick.lower() or q in real.lower():
                    r_frame.pack(fill="x", padx=5, pady=3)
                else:
                    r_frame.pack_forget()

        entry_search_prep.bind("<KeyRelease>", filter_prep_list)

        # Coluna Direita: Mesas e Controle de Start (40%)
        col_right = ctk.CTkFrame(grid_frame, fg_color="#1E1E1E", width=380)
        col_right.pack(side="right", fill="both", expand=False, padx=(5, 0), pady=0)

        header_mesas_frame = ctk.CTkFrame(col_right, fg_color="transparent")
        header_mesas_frame.pack(fill="x", padx=15, pady=(10, 5))

        lbl_mesas_title = ctk.CTkLabel(header_mesas_frame, text="Estações / Mesas:", font=("Helvetica", 12, "bold"))
        lbl_mesas_title.pack(side="left")

        def modal_adicionar_mesa_prep():
            top_m = ctk.CTkToplevel(self.root)
            top_m.title("Adicionar Mesa ao Torneio")
            top_m.geometry("450x260")
            top_m.transient(self.root)
            top_m.lift()
            top_m.focus_set()

            lbl_t = ctk.CTkLabel(top_m, text="Cadastrar Nova Mesa no Torneio", font=("Helvetica", 13, "bold"))
            lbl_t.pack(pady=12)

            cursor_cnt = self.db.conn.cursor()
            cursor_cnt.execute("SELECT COUNT(*) as cnt FROM stations WHERE event_id = ?", (self.evento_selecionado_id,))
            next_num = cursor_cnt.fetchone()["cnt"] + 1

            e_name = ctk.CTkEntry(top_m, placeholder_text=f"Mesa {next_num}", width=340)
            e_name.insert(0, f"Mesa {next_num}")
            e_name.pack(pady=6)

            hw_opts, hw_map = self.obter_opcoes_hardware_dropdown()
            combo_hw = ctk.CTkComboBox(top_m, values=hw_opts, width=340)
            combo_hw.set(hw_opts[1] if len(hw_opts) > 1 else hw_opts[0])
            combo_hw.pack(pady=6)

            def salvar_m():
                name_val = e_name.get().strip()
                if not name_val:
                    messagebox.showerror("Erro", "Nome da mesa é obrigatório.")
                    return
                mac_val = hw_map.get(combo_hw.get())
                self.db.cadastrar_estacao(self.evento_selecionado_id, name_val, mac_val)
                top_m.destroy()
                self.setup_tab_preparacao_evento(parent)

            btn_s = ctk.CTkButton(top_m, text="💾 Salvar Mesa", fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], command=salvar_m)
            btn_s.pack(pady=15)

        btn_add_st = ctk.CTkButton(header_mesas_frame, text="+ Nova Mesa", width=95, height=24, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 11, "bold"), command=modal_adicionar_mesa_prep)
        btn_add_st.pack(side="right")

        scroll_mesas = ctk.CTkScrollableFrame(col_right, label_text="Mesas de Jogo & Hardware ESP-NOW")
        scroll_mesas.pack(fill="both", expand=True, padx=10, pady=5)

        hw_opts_prep, hw_map_prep = self.obter_opcoes_hardware_dropdown()

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, name, node_mac FROM stations WHERE event_id = ? ORDER BY id ASC", (self.evento_selecionado_id,))
        mesas = cursor.fetchall()

        if not mesas:
            lbl_no_mesas = ctk.CTkLabel(scroll_mesas, text="Nenhuma mesa cadastrada para este torneio.\nClique em '+ Nova Mesa' acima.", font=("Helvetica", 11), text_color="#AAAAAA")
            lbl_no_mesas.pack(padx=10, pady=20)
        else:
            for st in mesas:
                st_id = st["id"]
                st_frame = ctk.CTkFrame(scroll_mesas, fg_color="#242424", height=42)
                st_frame.pack(fill="x", padx=5, pady=3)

                lbl_st = ctk.CTkLabel(st_frame, text=f"🪑 {st['name']}", font=("Helvetica", 11, "bold"))
                lbl_st.pack(side="left", padx=8, pady=8)

                # Dropdown de seleção de hardware direto na mesa
                combo_st_node = ctk.CTkComboBox(st_frame, values=hw_opts_prep, width=175, height=24, font=("Helvetica", 10))
                combo_st_node.set(self.obter_label_para_mac(st["node_mac"], hw_map_prep))

                def on_st_node_change(choice, sid=st_id):
                    mac_sel = hw_map_prep.get(choice)
                    if mac_sel:
                        self.db.vincular_no_estacao(sid, mac_sel)
                    else:
                        self.db.desvincular_no_estacao(sid)

                combo_st_node.configure(command=on_st_node_change)
                combo_st_node.pack(side="left", padx=5)

                def remover_st(sid=st_id, sname=st["name"]):
                    if messagebox.askyesno("Remover Mesa", f"Deseja remover a estação '{sname}' deste torneio?"):
                        self.db.excluir_estacao(sid)
                        self.setup_tab_preparacao_evento(parent)

                btn_del_st = ctk.CTkButton(st_frame, text="❌", width=26, height=24, fg_color="#881337", hover_color="#4C0519", command=remover_st)
                btn_del_st.pack(side="right", padx=5)

        action_card = ctk.CTkFrame(col_right, fg_color="#242424", border_width=1, border_color="#374151")
        action_card.pack(fill="x", padx=10, pady=10)

        lbl_act = ctk.CTkLabel(action_card, text="Iniciar Campeonato Ciberfísico", font=("Helvetica", 12, "bold"))
        lbl_act.pack(padx=10, pady=(10, 5))

        btn_start = ctk.CTkButton(action_card, text="🚀 Gerar Chaves & Dar Start", fg_color="#10B981", hover_color="#059669", font=("Helvetica", 13, "bold"),
                                  height=40, command=self.iniciar_torneio_acao)
        btn_start.pack(fill="x", padx=15, pady=(5, 15))

    def iniciar_torneio_acao(self):
        player_ids = []
        lacking_rfid = []

        for p_id, (chk, has_tag) in self.athlete_checkboxes.items():
            if chk.get() == 1:
                player_ids.append(p_id)
                if not has_tag:
                    # Consulta se o jogador obteve tag recentemente antes de bloquear
                    cursor = self.db.conn.cursor()
                    cursor.execute("SELECT tag_uid FROM rfid_tags WHERE player_id = ?", (p_id,))
                    row = cursor.fetchone()
                    if not row or not row["tag_uid"]:
                        lacking_rfid.append(p_id)

        if len(player_ids) < 2:
            messagebox.showerror("Erro de Iniciação", "É necessário inscrever no mínimo 2 jogadores para gerar o chaveamento do campeonato.")
            return

        # Se tudo estiver correto, atualiza os inscritos e dá o Start no Motor
        self.db.atualizar_participantes_evento(self.evento_selecionado_id, player_ids)
        
        # Inicializa a Chave via Engine
        sucesso, msg = self.motor.inicializar_chave_torneio(self.evento_selecionado_id)
        if sucesso:
            messagebox.showinfo("Sucesso", "Campeonato Iniciado com Sucesso! Chaves e rodadas preliminares geradas no SQLite.\n\nVocê será redirecionado para a árvore de brackets.")
            self.show_modulo_eventos()
            self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")
        else:
            messagebox.showerror("Erro no Motor", f"O motor de chaveamento falhou ao gerar chaves:\n\n{msg}")

    def modal_vincular_rfid_onthefly(self, player_id, nickname):
        # Preserva os marcadores de seleção atuais antes de abrir o modal
        if hasattr(self, "athlete_checkboxes") and self.athlete_checkboxes:
            current_checked = [p_id for p_id, (chk, has_tag) in self.athlete_checkboxes.items() if chk.get() == 1]
            self.db.atualizar_participantes_evento(self.evento_selecionado_id, current_checked)

        top = ctk.CTkToplevel(self.root)
        top.title("Vincular RFID On-The-Fly")
        top.geometry("450x260")
        top.transient(self.root)
        top.lift()
        top.focus_set()

        def fechar_vinc():
            self.active_rfid_capture_callback = None
            top.destroy()
        top.protocol("WM_DELETE_WINDOW", fechar_vinc)

        lbl = ctk.CTkLabel(top, text=f"Vincular Tag RFID para {nickname}", font=("Helvetica", 15, "bold"))
        lbl.pack(padx=20, pady=15)

        card_scan = ctk.CTkFrame(top, fg_color="#1E1E1E", border_width=1, border_color="#333333")
        card_scan.pack(fill="x", padx=20, pady=10)

        lbl_status = ctk.CTkLabel(card_scan, text="📡 ESCUTA ATIVA: Aproxime o cartão físico de qualquer Nó Repórter...", font=("Helvetica", 11, "bold"), text_color="#3B82F6")
        lbl_status.pack(padx=10, pady=(10, 6))

        entry_tag = ctk.CTkEntry(card_scan, placeholder_text="UID Hexadecimal da Tag", width=340)
        entry_tag.pack(padx=15, pady=(0, 12))

        def update_rfid_onthefly(tag_uid, mac_no):
            entry_tag.delete(0, "end")
            entry_tag.insert(0, tag_uid)
            lbl_status.configure(text=f"✅ TAG DETECTADA: {tag_uid} (Nó {mac_no})", text_color="#00FF88")

        self.active_rfid_capture_callback = update_rfid_onthefly

        def salvar():
            tag = entry_tag.get().strip().upper()
            if not tag:
                messagebox.showerror("Erro de Validação", "Preencha a UID da tag antes de salvar.")
                return
            self.active_rfid_capture_callback = None
            
            # Deletar qualquer vinculo anterior da tag para evitar colisões
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM rfid_tags WHERE tag_uid = ? OR player_id = ?", (tag, player_id))
            cursor.execute("INSERT INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag, player_id))
            self.db.conn.commit()

            messagebox.showinfo("Sucesso", f"Tag RFID '{tag}' vinculada com sucesso a '{nickname}'!")
            top.destroy()
            self.show_modulo_eventos()
            self.event_tab_frame.set("✏️ Edição / Preparação")

        btn_save = ctk.CTkButton(top, text="💾 Salvar Vínculo", fg_color="#10B981", command=salvar, width=180)
        btn_save.pack(padx=20, pady=15)

    def alterar_zoom_bracket(self, delta, parent_tab):
        """Altera o fator de escala de zoom do chaveamento interativo."""
        current = getattr(self, "bracket_zoom", 1.0)
        novo = round(current + delta, 1)
        if 0.5 <= novo <= 2.0:
            self.bracket_zoom = novo
            self.setup_tab_brackets(parent_tab)

    def reset_zoom_bracket(self, parent_tab):
        """Redefine o zoom do chaveamento para 100% (1.0)."""
        self.bracket_zoom = 1.0
        self.setup_tab_brackets(parent_tab)

    def setup_tab_brackets(self, parent):
        if not HAS_CTK:
            return

        for widget in parent.winfo_children():
            widget.destroy()

        if not getattr(self, "evento_selecionado_id", None):
            lbl_err = ctk.CTkLabel(parent, text="⚠️ Nenhum campeonato ativo.\nSelecione um torneio na aba 'Lista de Eventos'.", font=("Helvetica", 13), text_color=THEME_TRYHARD["text_muted"])
            lbl_err.pack(expand=True)
            return

        top_controls = ctk.CTkFrame(parent, fg_color="transparent")
        top_controls.pack(fill="x", padx=10, pady=5)

        # Buscar detalhes do evento selecionado
        ev = self.db.obter_evento(self.evento_selecionado_id) if getattr(self, "evento_selecionado_id", None) else None
        ev_name = ev["name"] if ev else "Nenhum Torneio Selecionado"

        lbl_ev = ctk.CTkLabel(top_controls, text=f"Torneio Ativo: {ev_name}", font=("Helvetica", 13, "bold"), text_color=THEME_TRYHARD["text_main"])
        lbl_ev.pack(side="left", padx=5)

        # Botões de Ação na Direita
        btn_refresh = ctk.CTkButton(top_controls, text="🔄 Atualizar Chave", width=120, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=lambda: self.setup_tab_brackets(parent))
        btn_refresh.pack(side="right", padx=5)

        btn_mesas = ctk.CTkButton(top_controls, text="🎛️ Estações", width=110, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=self.acao_clicar_gerenciar_estacoes)
        btn_mesas.bind("<Button-1>", lambda e: setattr(self, "_last_btn_press_event", e))
        btn_mesas.pack(side="right", padx=5)

        btn_tags = ctk.CTkButton(top_controls, text="🏷️ Tags RFID", width=110, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=self.modal_gerenciar_tags_torneio)
        btn_tags.pack(side="right", padx=5)

        # Controles de Zoom (Ctrl + Scroll ou Botões de Interface)
        frame_zoom = ctk.CTkFrame(top_controls, fg_color=THEME_TRYHARD["bg_card"], border_width=1, border_color=THEME_TRYHARD["border"], corner_radius=0)
        frame_zoom.pack(side="right", padx=10)

        btn_z_out = ctk.CTkButton(frame_zoom, text="➖", width=28, height=28, corner_radius=0, fg_color="transparent", hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=lambda: self.alterar_zoom_bracket(-0.1, parent))
        btn_z_out.pack(side="left", padx=1)

        lbl_zoom_val = ctk.CTkLabel(frame_zoom, text=f"{int(self.bracket_zoom * 100)}%", width=46, font=("Helvetica", 11, "bold"), text_color=THEME_TRYHARD["primary"])
        lbl_zoom_val.pack(side="left", padx=2)

        btn_z_in = ctk.CTkButton(frame_zoom, text="➕", width=28, height=28, corner_radius=0, fg_color="transparent", hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=lambda: self.alterar_zoom_bracket(0.1, parent))
        btn_z_in.pack(side="left", padx=1)

        btn_z_reset = ctk.CTkButton(frame_zoom, text="100%", width=44, height=28, corner_radius=0, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["text_main"], command=lambda: self.reset_zoom_bracket(parent))
        btn_z_reset.pack(side="left", padx=2)

        # Container principal com Canvas e Scrollbars para renderização dos Brackets
        canvas_container = ctk.CTkFrame(parent, fg_color="transparent")
        canvas_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Scrollbars do Canvas
        scrollbar_y = ctk.CTkScrollbar(canvas_container, orientation="vertical")
        scrollbar_y.pack(side="right", fill="y")

        scrollbar_x = ctk.CTkScrollbar(parent, orientation="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")

        canvas = tk.Canvas(canvas_container, bg=THEME_TRYHARD["bg_main"], highlightthickness=0,
                           xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)
        canvas.pack(side="left", fill="both", expand=True)

        scrollbar_y.configure(command=canvas.yview)
        scrollbar_x.configure(command=canvas.xview)

        # Handlers de Rolagem e Zoom com Ctrl + Scroll
        def _on_mousewheel(event):
            # Se a tecla Ctrl estiver pressionada (state & 0x0004 no Windows)
            if event.state & 0x0004:
                if event.delta > 0:
                    self.alterar_zoom_bracket(0.1, parent)
                else:
                    self.alterar_zoom_bracket(-0.1, parent)
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_ctrl_mousewheel(event):
            if event.delta > 0:
                self.alterar_zoom_bracket(0.1, parent)
            else:
                self.alterar_zoom_bracket(-0.1, parent)

        def _on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_scroll(w):
            w.bind("<MouseWheel>", _on_mousewheel)
            w.bind("<Control-MouseWheel>", _on_ctrl_mousewheel)
            w.bind("<Shift-MouseWheel>", _on_shift_mousewheel)
            for child in w.winfo_children():
                bind_scroll(child)

        bind_scroll(canvas)

        # Buscar todas as partidas com detalhes dos jogadores, vencedor e mesa alocada
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT m.id, m.round_number, p1.nickname as p1_name, p2.nickname as p2_name,
                   p1.id as p1_id, p2.id as p2_id,
                   m.score1, m.score2, m.status, w.nickname as winner_name, 
                   m.winner_id, s.name as station_name, m.player1_checked_in, m.player2_checked_in,
                   m.next_match_id, m.next_match_slot
            FROM matches m
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            LEFT JOIN players w ON m.winner_id = w.id
            LEFT JOIN stations s ON m.station_id = s.id
            WHERE m.event_id = ?
            ORDER BY m.round_number ASC, m.id ASC
        """, (self.evento_selecionado_id,))
        matches = cursor.fetchall()

        if not matches:
            lbl_empty = ctk.CTkLabel(canvas, text="Nenhuma partida gerada para este torneio ainda.\nUse a aba 'Edição / Preparação' para inscrever competidores e iniciar.", font=("Helvetica", 12), text_color=THEME_TRYHARD["text_muted"])
            lbl_empty.pack(padx=20, pady=40)
            return

        # -------------------------------------------------------------
        # 1. Atribuição de Letras / Identificadores às Partidas (A, B, C...)
        # -------------------------------------------------------------
        def get_match_letter(idx):
            res = ""
            while True:
                res = chr(65 + (idx % 26)) + res
                idx = (idx // 26) - 1
                if idx < 0:
                    break
            return res

        match_letters = {}
        sorted_matches = sorted(matches, key=lambda x: (x["round_number"], x["id"]))
        for idx, m in enumerate(sorted_matches):
            match_letters[m["id"]] = get_match_letter(idx)

        feeders = {}
        for m in matches:
            m_id = m["id"]
            next_id = m["next_match_id"]
            slot = m["next_match_slot"]
            if next_id and slot:
                if next_id not in feeders:
                    feeders[next_id] = {}
                feeders[next_id][slot] = match_letters.get(m_id, "?")

        # -------------------------------------------------------------
        # 2. Escalonamento e Cálculo de Posições (Suporte a Zoom Dinâmico)
        # -------------------------------------------------------------
        zoom = getattr(self, "bracket_zoom", 1.0)
        col_width = int(360 * zoom)
        card_width = int(290 * zoom)
        card_height = int(106 * zoom)
        x_start = int(50 * zoom)
        badge_width = int(46 * zoom)
        row_gap = int(175 * zoom)

        font_name_size = max(8, int(11 * zoom))
        font_score_size = max(8, int(12 * zoom))
        font_badge_size = max(8, int(11 * zoom))
        font_vs_size = max(7, int(8 * zoom))

        match_y = {}
        max_round = max(m["round_number"] for m in matches)

        # Round 1
        round_1_matches = sorted([m for m in matches if m["round_number"] == 1], key=lambda x: x["id"])
        for idx, m in enumerate(round_1_matches):
            match_y[m["id"]] = int(50 * zoom) + idx * row_gap

        # Rodadas subsequentes
        for r in range(2, max_round + 1):
            round_r_matches = [m for m in matches if m["round_number"] == r]
            for m in round_r_matches:
                m_id = m["id"]
                filhos = [f for f in matches if f["next_match_id"] == m_id]
                if filhos:
                    filhos_y = [match_y[f["id"]] for f in filhos if f["id"] in match_y]
                    if filhos_y:
                        match_y[m_id] = sum(filhos_y) / len(filhos_y)
                    else:
                        match_y[m_id] = int(100 * zoom)
                else:
                    match_y[m_id] = int(100 * zoom)

        # -------------------------------------------------------------
        # 3. Desenhar linhas conectoras atrás dos cards
        # -------------------------------------------------------------
        line_w = max(1, int(2 * zoom))
        for m in matches:
            m_id = m["id"]
            next_id = m["next_match_id"]
            if next_id and m_id in match_y and next_id in match_y:
                mx = x_start + (m["round_number"] - 1) * col_width
                my = match_y[m_id]
                
                parent_match = [p for p in matches if p["id"] == next_id][0]
                px = x_start + (parent_match["round_number"] - 1) * col_width
                py = match_y[next_id]

                start_x = mx + card_width
                start_y = my + card_height / 2
                end_x = px
                end_y = py + card_height / 2

                mid_x = (start_x + end_x) / 2
                canvas.create_line(start_x, start_y, mid_x, start_y, fill=THEME_TRYHARD["border"], width=line_w)
                canvas.create_line(mid_x, start_y, mid_x, end_y, fill=THEME_TRYHARD["border"], width=line_w)
                canvas.create_line(mid_x, end_y, end_x, end_y, fill=THEME_TRYHARD["border"], width=line_w)

        # -------------------------------------------------------------
        # 4. Renderizar Cards Angulares TryHard Arena (Sem corte de texto)
        # -------------------------------------------------------------
        for m in matches:
            m_id = m["id"]
            r_num = m["round_number"]
            mx = x_start + (r_num - 1) * col_width
            my = match_y[m_id]

            status = m["status"]
            letter = match_letters.get(m_id, "?")
            p1_checked = m["player1_checked_in"]
            p2_checked = m["player2_checked_in"]

            # Estilos dos cards com a paleta oficial TryHard Arena
            card_style = {
                "WAITING": (THEME_TRYHARD["bg_card"], THEME_TRYHARD["border"], THEME_TRYHARD["text_muted"]),
                "READY": ("#2B2313", THEME_TRYHARD["status_waiting"], THEME_TRYHARD["status_waiting"]),
                "PLAYING": ("#2D120E", THEME_TRYHARD["rage_red"], THEME_TRYHARD["rage_red"]),
                "FINISHED": ("#0F281E", THEME_TRYHARD["status_success"], THEME_TRYHARD["status_success"])
            }
            bg_col, border_col, text_col = card_style.get(status, (THEME_TRYHARD["bg_card"], THEME_TRYHARD["border"], THEME_TRYHARD["text_muted"]))

            if m["p1_name"]:
                p1_name = m["p1_name"]
            elif m_id in feeders and 1 in feeders[m_id]:
                p1_name = f"Ganhador de {feeders[m_id][1]}"
            else:
                p1_name = "BYE"

            if m["p2_name"]:
                p2_name = m["p2_name"]
            elif m_id in feeders and 2 in feeders[m_id]:
                p2_name = f"Ganhador de {feeders[m_id][2]}"
            else:
                p2_name = "BYE"

            s1 = m["score1"] if m["score1"] is not None else 0
            s2 = m["score2"] if m["score2"] is not None else 0

            # Formatação Jogador 1
            p1_display = p1_name
            p1_color = THEME_TRYHARD["text_main"] if m["p1_name"] else THEME_TRYHARD["text_muted"]
            if status == "FINISHED":
                if m["winner_id"] == m["p1_id"] and m["p1_id"] is not None:
                    p1_display = f"🏆 {p1_name}"
                    p1_color = THEME_TRYHARD["status_success"]
                else:
                    p1_color = THEME_TRYHARD["text_muted"]
            elif status == "READY" and p1_checked:
                p1_display = f"✓ {p1_name}"
                p1_color = THEME_TRYHARD["status_success"]

            # Formatação Jogador 2
            p2_display = p2_name
            p2_color = THEME_TRYHARD["text_main"] if m["p2_name"] else THEME_TRYHARD["text_muted"]
            if status == "FINISHED":
                if m["winner_id"] == m["p2_id"] and m["p2_id"] is not None:
                    p2_display = f"🏆 {p2_name}"
                    p2_color = THEME_TRYHARD["status_success"]
                else:
                    p2_color = THEME_TRYHARD["text_muted"]
            elif status == "READY" and p2_checked:
                p2_display = f"✓ {p2_name}"
                p2_color = THEME_TRYHARD["status_success"]

            # Container Principal: Ângulos Retos (corner_radius=0) para Estética Angular FGC
            m_card = ctk.CTkFrame(
                canvas,
                fg_color=THEME_TRYHARD["bg_card"],
                border_width=2 if status in ("PLAYING", "READY") else 1,
                border_color=border_col,
                corner_radius=0, # Ângulos técnicos de e-sports
                width=card_width,
                height=card_height
            )
            m_card.pack_propagate(False)

            # Bloco Lateral Esquerdo (Letra + Ícone de Estado) com cantos retos
            badge_frame = ctk.CTkFrame(
                m_card,
                fg_color=bg_col,
                width=badge_width,
                height=card_height,
                corner_radius=0
            )
            badge_frame.pack(side="left", fill="y")
            badge_frame.pack_propagate(False)

            if status == "PLAYING":
                badge_text = f"💢\n{letter}"
            elif status == "READY":
                badge_text = f"⚠️\n{letter}"
            elif status == "FINISHED":
                badge_text = f"✓\n{letter}"
            else:
                badge_text = letter

            lbl_badge = ctk.CTkLabel(
                badge_frame,
                text=badge_text,
                font=("Helvetica", font_badge_size, "bold"),
                text_color=text_col,
                height=1
            )
            lbl_badge.place(relx=0.5, rely=0.5, anchor="center")

            # Bloco Direito: Distribuição vertical balanceada sem compressão de texto
            right_frame = ctk.CTkFrame(m_card, fg_color="transparent")
            right_frame.pack(side="left", fill="both", expand=True, padx=int(8 * zoom), pady=int(4 * zoom))

            # Subdivisão Superior (Jogador 1)
            p1_row = ctk.CTkFrame(right_frame, fg_color="transparent")
            p1_row.pack(side="top", fill="x", expand=True)

            p1_lbl = ctk.CTkLabel(
                p1_row,
                text=p1_display,
                font=("Helvetica", font_name_size, "bold" if "🏆" in p1_display or "✓" in p1_display else "normal"),
                text_color=p1_color,
                height=1
            )
            p1_lbl.pack(side="left", anchor="w")

            if m["p1_name"]:
                s1_lbl = ctk.CTkLabel(
                    p1_row,
                    text=str(s1),
                    font=("Helvetica", font_score_size, "bold"),
                    text_color=THEME_TRYHARD["text_main"],
                    height=1
                )
                s1_lbl.pack(side="right", anchor="e", padx=(0, int(4 * zoom)))

            # Divisória Central com Rage VS (💢 VS) de altura controlada
            divider_frame = ctk.CTkFrame(right_frame, fg_color="transparent", height=int(14 * zoom))
            divider_frame.pack(side="top", fill="x", pady=int(2 * zoom))
            divider_frame.pack_propagate(False)

            line_l = ctk.CTkFrame(divider_frame, fg_color=THEME_TRYHARD["border"], height=1)
            line_l.pack(side="left", fill="x", expand=True, pady=int(6 * zoom))

            vs_col = THEME_TRYHARD["rage_red"] if status == "PLAYING" else (THEME_TRYHARD["status_waiting"] if status == "READY" else THEME_TRYHARD["text_muted"])
            lbl_vs = ctk.CTkLabel(
                divider_frame,
                text="💢 VS",
                font=("Helvetica", font_vs_size, "bold"),
                text_color=vs_col,
                height=1
            )
            lbl_vs.pack(side="left", padx=int(4 * zoom))

            line_r = ctk.CTkFrame(divider_frame, fg_color=THEME_TRYHARD["border"], height=1)
            line_r.pack(side="right", fill="x", expand=True, pady=int(6 * zoom))

            # Subdivisão Inferior (Jogador 2)
            p2_row = ctk.CTkFrame(right_frame, fg_color="transparent")
            p2_row.pack(side="top", fill="x", expand=True)

            p2_lbl = ctk.CTkLabel(
                p2_row,
                text=p2_display,
                font=("Helvetica", font_name_size, "bold" if "🏆" in p2_display or "✓" in p2_display else "normal"),
                text_color=p2_color,
                height=1
            )
            p2_lbl.pack(side="left", anchor="w")

            if m["p2_name"]:
                s2_lbl = ctk.CTkLabel(
                    p2_row,
                    text=str(s2),
                    font=("Helvetica", font_score_size, "bold"),
                    text_color=THEME_TRYHARD["text_main"],
                    height=1
                )
                s2_lbl.pack(side="right", anchor="e", padx=(0, int(4 * zoom)))

            # Adicionar janela no Canvas
            canvas.create_window(mx, my, window=m_card, anchor="nw", width=card_width, height=card_height)

            # Vincular evento de duplo clique e scroll no card
            def on_card_double_click(e, m_id=m['id']):
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT status, player1_id, player2_id FROM matches WHERE id = ?", (m_id,))
                m_row = cursor.fetchone()
                if not m_row:
                    return
                if m_row["status"] == "WAITING" and (m_row["player1_id"] is None or m_row["player2_id"] is None):
                    messagebox.showwarning(
                        "Partida Não Iniciável", 
                        "Esta partida ainda não pode ser iniciada ou gerida pois aguarda a definição dos competidores das rodadas anteriores."
                    )
                    return
                self.modal_contexto_partida(m_id)

            self.bind_double_click(m_card, on_card_double_click)
            bind_scroll(m_card)

        # Configurar limites de rolagem do Canvas com margens dinâmicas
        max_x = x_start + max_round * col_width + int(120 * zoom)
        max_y = max(match_y.values()) + card_height + int(120 * zoom)
        canvas.configure(scrollregion=(0, 0, max_x, max_y))

    # -------------------------------------------------------------------------
    # MÓDULO 2: JOGADORES
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # MÓDULO 2: JOGADORES (PLAYER MANAGEMENT)
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # MÓDULO 2: JOGADORES (LAYOUT MASTER-DETAIL)
    # -------------------------------------------------------------------------
    def show_modulo_jogadores(self, filter_text="", selected_id=None):
        self.clear_content_area()
        self.modulo_atual = 2
        self.update_navbar_active_state(2)
        if not HAS_CTK:
            return

        title = ctk.CTkLabel(self.content_area, text="👤 Módulo 2: Gestão de Atletas & Tags RFID", font=("Helvetica", 18, "bold"))
        title.pack(anchor="w", padx=15, pady=(10, 4))

        # Banner de Scanner RFID em Tempo Real
        scanner_bar = ctk.CTkFrame(self.content_area, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"], corner_radius=6)
        scanner_bar.pack(fill="x", padx=15, pady=(0, 6))

        lbl_sc_title = ctk.CTkLabel(scanner_bar, text="📡 SCANNER RFID ATIVO:", font=("Helvetica", 11, "bold"), text_color=THEME_TRYHARD["primary"])
        lbl_sc_title.pack(side="left", padx=(12, 5), pady=6)

        txt_sc = "Aproxime qualquer cartão físico em qualquer Nó Repórter para capturar sua UID..."
        cor_sc = "#A5F3FC"
        if getattr(self, "ultima_tag_lida", None):
            txt_sc = f"Última Tag: {self.ultima_tag_lida} (Nó: {self.ultimo_no_mac or '?'}) às {self.ultimo_timestamp_rfid or ''}"
            cor_sc = THEME_TRYHARD["status_success"]

        self.lbl_scanner_tag = ctk.CTkLabel(scanner_bar, text=txt_sc, font=("Helvetica", 11, "bold"), text_color=cor_sc)
        self.lbl_scanner_tag.pack(side="left", padx=5, pady=6)

        def criar_com_ultima_tag():
            if getattr(self, "ultima_tag_lida", None):
                if hasattr(self, "selecionar_atleta_fn"):
                    self.selecionar_atleta_fn("NEW")
                else:
                    self.show_modulo_jogadores(selected_id="NEW")
                if hasattr(self, "entry_tag_novo") and self.entry_tag_novo:
                    self.entry_tag_novo.delete(0, "end")
                    self.entry_tag_novo.insert(0, self.ultima_tag_lida)
            else:
                messagebox.showinfo("Scanner RFID", "Nenhuma tag foi lida recentemente. Aproxime uma tag de qualquer nó primeiro.")

        btn_use_tag = ctk.CTkButton(scanner_bar, text="➕ Novo Atleta c/ esta Tag", width=190, height=26, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["text_main"], font=("Helvetica", 11, "bold"), command=criar_com_ultima_tag)
        btn_use_tag.pack(side="right", padx=(5, 12), pady=6)

        def limpar_tags_dialog():
            if messagebox.askyesno("Limpar Tags do Banco", "Deseja remover todas as tags RFID registradas (artificiais e de teste)?\n\nOs atletas continuarão existindo normalmente, mas suas tags serão limpas para você aproximar e cadastrar os crachás físicos reais do zero."):
                self.db.limpar_tags_rfid(apenas_artificiais=False)
                messagebox.showinfo("Tags Limpas", "Todas as tags RFID foram removidas do banco de dados!\nAgora você pode aproximar suas tags físicas reais para vinculá-las.")
                self.show_modulo_jogadores()

        btn_clean = ctk.CTkButton(scanner_bar, text="🧹 Limpar Todas as Tags", width=160, height=26, fg_color="#374151", hover_color=THEME_TRYHARD["rage_red"], text_color="#FFFFFF", font=("Helvetica", 11, "bold"), command=limpar_tags_dialog)
        btn_clean.pack(side="right", padx=5, pady=6)

        # Container Principal Duplo (Master / Detail)
        panes_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        panes_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # PAINEL ESQUERDO (MASTER: 38% da largura)
        master_panel = ctk.CTkFrame(panes_frame, fg_color=THEME_TRYHARD["bg_card"], width=380)
        master_panel.pack(side="left", fill="both", expand=False, padx=(0, 5), pady=0)

        top_bar = ctk.CTkFrame(master_panel, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=10)

        self.entry_search_player = ctk.CTkEntry(top_bar, placeholder_text="Buscar por Nome, Nickname, Tag...", width=200)
        if filter_text:
            self.entry_search_player.insert(0, filter_text)
        self.entry_search_player.pack(side="left", padx=2)
        self.entry_search_player.bind("<Return>", lambda e: self.show_modulo_jogadores(self.entry_search_player.get(), selected_id))

        btn_search = ctk.CTkButton(top_bar, text="🔍", width=40,
                                   command=lambda: self.show_modulo_jogadores(self.entry_search_player.get(), selected_id))
        btn_search.pack(side="left", padx=2)

        scroll_players = ctk.CTkScrollableFrame(master_panel, label_text="Lista de Atletas")
        scroll_players.pack(fill="both", expand=True, padx=5, pady=5)

        players = self.db.buscar_jogadores(query=filter_text, incluir_inativos=True)

        if not players:
            lbl_empty = ctk.CTkLabel(scroll_players, text="Nenhum jogador encontrado.", font=("Helvetica", 11))
            lbl_empty.pack(padx=10, pady=20)
            selected_id = None
        elif selected_id is None and players:
            selected_id = players[0]['id']

        # PAINEL DIREITO (DETAIL: 62% da largura)
        detail_panel = ctk.CTkFrame(panes_frame, fg_color=THEME_TRYHARD["bg_card"])
        detail_panel.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=0)
        self.player_detail_panel = detail_panel
        self.player_rows = {}
        self.current_selected_player_id = selected_id

        def selecionar_atleta(target_id):
            if self.current_selected_player_id == target_id:
                return
            prev_id = self.current_selected_player_id
            self.current_selected_player_id = target_id

            # Desmarca botão anterior
            if prev_id in self.player_rows:
                prev_btn, prev_p = self.player_rows[prev_id]
                prev_btn.configure(
                    fg_color=THEME_TRYHARD["bg_card"] if prev_p['is_active'] else THEME_TRYHARD["bg_main"],
                    text_color=THEME_TRYHARD["text_main"] if prev_p['is_active'] else THEME_TRYHARD["text_muted"],
                    border_width=1,
                    border_color=THEME_TRYHARD["border"],
                    hover_color=THEME_TRYHARD["bg_card_alt"],
                    font=("Helvetica", 12, "normal")
                )

            # Destaca novo botão
            if target_id in self.player_rows:
                new_btn, new_p = self.player_rows[target_id]
                new_btn.configure(
                    fg_color=THEME_TRYHARD["primary"],
                    text_color=THEME_TRYHARD["primary_text"],
                    border_width=0,
                    hover_color=THEME_TRYHARD["primary_hover"],
                    font=("Helvetica", 12, "bold")
                )

            # Atualiza apenas o painel direito sem tocar na lista ou no restante da janela
            for w in self.player_detail_panel.winfo_children():
                w.destroy()

            if target_id == "NEW":
                self.render_form_novo_jogador(self.player_detail_panel)
            elif target_id:
                self.render_detalhes_jogador_painel(self.player_detail_panel, target_id)
            else:
                lbl_select = ctk.CTkLabel(self.player_detail_panel, text="Selecione um atleta na lista ao lado para visualizar seu perfil e histórico.", font=("Helvetica", 12), text_color="#888888")
                lbl_select.pack(expand=True)

        self.selecionar_atleta_fn = selecionar_atleta

        btn_new = ctk.CTkButton(top_bar, text="+ Atleta", width=80, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 12, "bold"), command=lambda: selecionar_atleta("NEW"))
        btn_new.pack(side="right", padx=2)

        for p in players:
            is_selected = (p['id'] == selected_id)
            row_color = THEME_TRYHARD["primary"] if is_selected else (THEME_TRYHARD["bg_card"] if p['is_active'] else THEME_TRYHARD["bg_main"])
            row_txt_color = THEME_TRYHARD["primary_text"] if is_selected else (THEME_TRYHARD["text_main"] if p['is_active'] else THEME_TRYHARD["text_muted"])
            row_border_w = 0 if is_selected else 1
            row_border_c = THEME_TRYHARD["border"]
            
            btn_row = ctk.CTkButton(
                scroll_players,
                text=f"#{p['id']} {p['nickname']}\nTag: {p['tag_uid'] or 'Sem Tag'}",
                font=("Helvetica", 12, "bold" if is_selected else "normal"),
                anchor="w",
                fg_color=row_color,
                text_color=row_txt_color,
                border_width=row_border_w,
                border_color=row_border_c,
                hover_color=THEME_TRYHARD["primary_hover"] if is_selected else THEME_TRYHARD["bg_card_alt"],
                height=45,
                command=lambda p_id=p['id']: selecionar_atleta(p_id)
            )
            btn_row.pack(fill="x", padx=3, pady=3)
            self.player_rows[p['id']] = (btn_row, p)

        if selected_id == "NEW":
            self.render_form_novo_jogador(detail_panel)
        elif selected_id:
            self.render_detalhes_jogador_painel(detail_panel, selected_id)
        else:
            lbl_select = ctk.CTkLabel(detail_panel, text="Selecione um atleta na lista ao lado para visualizar seu perfil e histórico.", font=("Helvetica", 12), text_color="#888888")
            lbl_select.pack(expand=True)

    def render_detalhes_jogador_painel(self, parent_frame, player_id):
        if player_id == "NEW":
            self.render_form_novo_jogador(parent_frame)
            return

        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT p.id, p.real_name, p.nickname, p.is_active, r.tag_uid
            FROM players p
            LEFT JOIN rfid_tags r ON p.id = r.player_id
            WHERE p.id = ?
        """, (player_id,))
        p = cursor.fetchone()

        if not p:
            return

        # Header do Card de Detalhes do Atleta
        header_card = ctk.CTkFrame(parent_frame, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        header_card.pack(fill="x", padx=15, pady=15)

        lbl_nick = ctk.CTkLabel(header_card, text=f"{p['nickname']}", font=("Helvetica", 22, "bold"), text_color=THEME_TRYHARD["text_main"])
        lbl_nick.pack(anchor="w", padx=15, pady=(10, 2))

        lbl_name = ctk.CTkLabel(header_card, text=f"Nome Real: {p['real_name']}  |  ID #{p['id']}", font=("Helvetica", 12), text_color=THEME_TRYHARD["text_muted"])
        lbl_name.pack(anchor="w", padx=15, pady=(0, 10))

        badges_row = ctk.CTkFrame(header_card, fg_color="transparent")
        badges_row.pack(fill="x", padx=15, pady=(0, 10))

        tag_txt = f"🏷️ RFID: {p['tag_uid']}" if p['tag_uid'] else "⚠️ Sem Tag RFID Vinculada"
        tag_bg = THEME_TRYHARD["primary"] if p['tag_uid'] else THEME_TRYHARD["status_waiting"]
        lbl_tag = ctk.CTkLabel(badges_row, text=f"  {tag_txt}  ", fg_color=tag_bg, font=("Helvetica", 11, "bold"), corner_radius=6)
        lbl_tag.pack(side="left", padx=(0, 10))

        st_txt = "● Ativo" if p['is_active'] else "● Inativo (Soft Delete)"
        st_color = THEME_TRYHARD["status_success"] if p['is_active'] else THEME_TRYHARD["rage_red"]
        lbl_st = ctk.CTkLabel(badges_row, text=st_txt, font=("Helvetica", 11, "bold"), text_color=st_color)
        lbl_st.pack(side="left")

        # Canto Superior Direito: Ações de Edição e Soft Delete
        actions_bar = ctk.CTkFrame(header_card, fg_color="transparent")
        actions_bar.pack(anchor="e", padx=15, pady=(0, 10))

        def vincular_ultima_tag_direto():
            tag_atual = getattr(self, "ultima_tag_lida", None)
            if not tag_atual:
                messagebox.showwarning("Nenhuma Tag Lida", "Aproxime um cartão RFID de qualquer nó repórter primeiro.")
                return
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM rfid_tags WHERE tag_uid = ? OR player_id = ?", (tag_atual, p['id']))
            cursor.execute("INSERT INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (tag_atual, p['id']))
            self.db.conn.commit()
            messagebox.showinfo("Tag Vinculada", f"Tag RFID '{tag_atual}' vinculada com sucesso ao atleta '{p['nickname']}'!")
            if hasattr(self, "player_rows") and p['id'] in self.player_rows:
                b_widget, p_info = self.player_rows[p['id']]
                p_info['tag_uid'] = tag_atual
                b_widget.configure(text=f"#{p['id']} {p['nickname']}\nTag: {tag_atual}")
            for w in parent_frame.winfo_children():
                w.destroy()
            self.render_detalhes_jogador_painel(parent_frame, p['id'])

        last_tag_txt = f"🏷️ Vincular Tag [{self.ultima_tag_lida}]" if getattr(self, "ultima_tag_lida", None) else "🏷️ Vincular Última Tag"
        btn_quick_tag = ctk.CTkButton(actions_bar, text=last_tag_txt, width=175, fg_color="#059669", hover_color="#047857", text_color="#FFFFFF", font=("Helvetica", 11, "bold"), command=vincular_ultima_tag_direto)
        btn_quick_tag.pack(side="left", padx=5)

        btn_edit = ctk.CTkButton(actions_bar, text="✏️ Editar Perfil & Tag", width=140, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 12, "bold"),
                                 command=lambda: self.modal_editar_jogador(p['id'], p['real_name'], p['nickname'], p['tag_uid']))
        btn_edit.pack(side="left", padx=5)

        if p['is_active']:
            btn_del = ctk.CTkButton(actions_bar, text="🗑️ Desativar", width=110, fg_color=THEME_TRYHARD["rage_red"], hover_color=THEME_TRYHARD["rage_red_hover"], font=("Helvetica", 12, "bold"),
                                    command=lambda: self.toggle_status_jogador(p['id'], 0))
            btn_del.pack(side="left", padx=5)
        else:
            btn_react = ctk.CTkButton(actions_bar, text="🟢 Reativar", width=110, fg_color=THEME_TRYHARD["status_success"], hover_color="#0D9467", font=("Helvetica", 12, "bold"),
                                      command=lambda: self.toggle_status_jogador(p['id'], 1))
            btn_react.pack(side="left", padx=5)

        # Link de Acesso Mobile (ID ou UID)
        mobile_ident = p['tag_uid'] if p['tag_uid'] else str(p['id'])
        local_ip_atual = self.obter_ip_local()
        mobile_url = f"http://{local_ip_atual}:5000/player/{mobile_ident}"
        
        row_link = ctk.CTkFrame(header_card, fg_color="#121820", corner_radius=6)
        row_link.pack(fill="x", padx=15, pady=(0, 12))
        
        lbl_link_title = ctk.CTkLabel(row_link, text="📱 Link Mobile:", font=("Helvetica", 11, "bold"), text_color=THEME_TRYHARD["primary"])
        lbl_link_title.pack(side="left", padx=(10, 5), pady=6)
        
        lbl_link_val = ctk.CTkLabel(row_link, text=mobile_url, font=("Helvetica", 11, "bold"), text_color="#A5F3FC")
        lbl_link_val.pack(side="left", padx=5, pady=6)
        
        def copiar_link_mobile():
            self.root.clipboard_clear()
            self.root.clipboard_append(mobile_url)
            messagebox.showinfo("Link Copiado", f"Link copiado para a área de transferência:\n{mobile_url}")

        btn_copy = ctk.CTkButton(
            row_link, 
            text="📋 Copiar Link", 
            width=95, 
            height=24, 
            fg_color=THEME_TRYHARD["border"], 
            hover_color=THEME_TRYHARD["primary_hover"], 
            text_color=THEME_TRYHARD["text_main"], 
            font=("Helvetica", 10, "bold"), 
            command=copiar_link_mobile
        )
        btn_copy.pack(side="right", padx=(4, 10), pady=6)

        btn_qr = ctk.CTkButton(
            row_link, 
            text="Gerar QR Code", 
            width=105, 
            height=24, 
            fg_color=THEME_TRYHARD["primary"], 
            hover_color=THEME_TRYHARD["primary_hover"], 
            text_color=THEME_TRYHARD["primary_text"], 
            font=("Helvetica", 10, "bold"), 
            command=lambda: self.modal_qrcode_jogador(p['nickname'], mobile_url)
        )
        btn_qr.pack(side="right", padx=(4, 4), pady=6)

        # Histórico Cruzado de Partidas (Domina o Restante do Painel)
        lbl_hist_title = ctk.CTkLabel(parent_frame, text="📜 Histórico Cruzado de Partidas em Torneios", font=("Helvetica", 14, "bold"))
        lbl_hist_title.pack(anchor="w", padx=15, pady=(10, 5))

        scroll_hist = ctk.CTkScrollableFrame(parent_frame, label_text="Trajetória do Atleta")
        scroll_hist.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        historico = self.db.obter_historico_partidas_jogador(player_id)

        if not historico:
            lbl_empty = ctk.CTkLabel(scroll_hist, text="Nenhuma partida encontrada no histórico deste atleta.", font=("Helvetica", 12), text_color="#888888")
            lbl_empty.pack(padx=20, pady=20)
            return

        for h in historico:
            row = ctk.CTkFrame(scroll_hist, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
            row.pack(fill="x", padx=5, pady=4)

            p1 = h['p1_nick'] or "A Definir"
            p2 = h['p2_nick'] or "A Definir"
            s1 = h['score1'] if h['score1'] is not None else 0
            s2 = h['score2'] if h['score2'] is not None else 0
            ev_name = h['event_name']
            ev_date = h['event_date']
            winner_id = h['winner_id']

            if winner_id == player_id:
                res_txt = "🏆 VITÓRIA"
                res_color = THEME_TRYHARD["status_success"]
            elif winner_id is not None:
                res_txt = "❌ DERROTA"
                res_color = THEME_TRYHARD["rage_red"]
            else:
                res_txt = "⏳ EM ANDAMENTO"
                res_color = THEME_TRYHARD["primary"]

            lbl_title = ctk.CTkLabel(row, text=f"{ev_name} ({ev_date}) - Partida #{h['match_id']}", font=("Helvetica", 11, "bold"), text_color="#888888")
            lbl_title.pack(anchor="w", padx=10, pady=(4, 0))

            lbl_detail = ctk.CTkLabel(row, text=f"  {p1} ({s1})  vs  {p2} ({s2})", font=("Helvetica", 13, "bold"))
            lbl_res = ctk.CTkLabel(row, text=res_txt, font=("Helvetica", 11, "bold"), text_color=res_color)
            lbl_res.pack(anchor="e", padx=10, pady=(0, 4))

    def render_form_novo_jogador(self, parent_frame):
        lbl_title = ctk.CTkLabel(parent_frame, text="✨ Cadastrar Novo Atleta", font=("Helvetica", 18, "bold"))
        lbl_title.pack(anchor="w", padx=20, pady=(15, 5))

        lbl_desc = ctk.CTkLabel(parent_frame, text="Preencha os dados do atleta e aproxime o cartão RFID para vincular o identificador único ciberfísico.", font=("Helvetica", 11), text_color="#AAAAAA", justify="left")
        lbl_desc.pack(anchor="w", padx=20, pady=(0, 15))

        form_card = ctk.CTkFrame(parent_frame, fg_color=THEME_TRYHARD["bg_card"], border_width=1, border_color=THEME_TRYHARD["border"])
        form_card.pack(fill="x", padx=20, pady=5)

        lbl_name = ctk.CTkLabel(form_card, text="Nome Completo:", font=("Helvetica", 12, "bold"))
        lbl_name.pack(anchor="w", padx=15, pady=(12, 2))
        entry_name = ctk.CTkEntry(form_card, placeholder_text="Ex: Alice Silva", width=420)
        entry_name.pack(anchor="w", padx=15, pady=(0, 10))

        lbl_nick = ctk.CTkLabel(form_card, text="Gamer Tag / Nickname (Nome em jogo):", font=("Helvetica", 12, "bold"))
        lbl_nick.pack(anchor="w", padx=15, pady=(5, 2))
        entry_nick = ctk.CTkEntry(form_card, placeholder_text="Ex: Alice_TCG", width=420)
        entry_nick.pack(anchor="w", padx=15, pady=(0, 12))

        # CARD DE VÍNCULO DE TAG RFID EM TEMPO REAL
        card_rfid = ctk.CTkFrame(form_card, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        card_rfid.pack(fill="x", padx=15, pady=10)

        lbl_rfid_st = ctk.CTkLabel(card_rfid, text="📡 ESCUTA RFID EM TEMPO REAL", font=("Helvetica", 11, "bold"), text_color=THEME_TRYHARD["primary"])
        lbl_rfid_st.pack(anchor="w", padx=12, pady=(10, 2))

        lbl_status_rfid = ctk.CTkLabel(card_rfid, text="● Aproxime o cartão RFID físico em qualquer Nó Repórter ativo...", font=("Helvetica", 11), text_color="#D97706")
        lbl_status_rfid.pack(anchor="w", padx=12, pady=(0, 8))

        row_tag = ctk.CTkFrame(card_rfid, fg_color="transparent")
        row_tag.pack(fill="x", padx=12, pady=(0, 10))

        entry_tag = ctk.CTkEntry(row_tag, placeholder_text="UID da Tag RFID (Opcional - deixe vazio se não tiver cartão)", width=360)
        entry_tag.pack(side="left", padx=(0, 8))
        self.entry_tag_novo = entry_tag

        def limpar_campo_tag():
            entry_tag.delete(0, "end")
            lbl_status_rfid.configure(text="● Campo de tag limpo. Aproxime outro cartão se desejar.", text_color="#D97706")

        btn_limpar = ctk.CTkButton(row_tag, text="✕ Limpar Tag", width=110, fg_color="#374151", command=limpar_campo_tag)
        btn_limpar.pack(side="left", padx=(0, 6))

        def preencher_com_ultima():
            if getattr(self, "ultima_tag_lida", None):
                entry_tag.delete(0, "end")
                entry_tag.insert(0, self.ultima_tag_lida)
                lbl_status_rfid.configure(text=f"✅ TAG PREENCHIDA: {self.ultima_tag_lida}", text_color="#00FF88")
            else:
                messagebox.showinfo("RFID", "Nenhuma tag foi lida recentemente. Aproxime uma tag de qualquer nó primeiro.")

        btn_last_tag = ctk.CTkButton(row_tag, text="🏷️ Usar Última Lida", width=140, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], command=preencher_com_ultima)
        btn_last_tag.pack(side="left")

        def update_rfid_ui(tag_uid, mac_no):
            entry_tag.delete(0, "end")
            entry_tag.insert(0, tag_uid)
            lbl_status_rfid.configure(text=f"✅ TAG CAPTURADA COM SUCESSO: {tag_uid} (Nó {mac_no})", text_color="#00FF88")

        self.active_rfid_capture_callback = update_rfid_ui

        actions_row = ctk.CTkFrame(parent_frame, fg_color="transparent")
        actions_row.pack(fill="x", padx=20, pady=15)

        def salvar_atleta():
            name = entry_name.get().strip()
            nick = entry_nick.get().strip()
            tag = entry_tag.get().strip().upper()
            if not name or not nick:
                messagebox.showerror("Erro de Validação", "Preencha o Nome Completo e o Nickname do atleta.")
                return
            
            self.active_rfid_capture_callback = None
            new_id = self.db.cadastrar_jogador(name, nick, tag if tag else None)
            messagebox.showinfo("Atleta Cadastrado", f"O atleta '{nick}' foi cadastrado com sucesso!")
            self.show_modulo_jogadores(selected_id=new_id)

        btn_save = ctk.CTkButton(actions_row, text="💾 Salvar e Finalizar Cadastro", fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 13, "bold"),
                                 height=40, width=240, command=salvar_atleta)
        btn_save.pack(side="left")

        def cancelar_cadastro():
            self.active_rfid_capture_callback = None
            if hasattr(self, "selecionar_atleta_fn") and hasattr(self, "player_rows") and self.player_rows:
                primeiro_id = list(self.player_rows.keys())[0]
                self.current_selected_player_id = None
                self.selecionar_atleta_fn(primeiro_id)
            else:
                self.show_modulo_jogadores()

        btn_cancel = ctk.CTkButton(actions_row, text="Cancelar", fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_muted"], height=40, width=100,
                                   command=cancelar_cadastro)
        btn_cancel.pack(side="left", padx=10)

    # -------------------------------------------------------------------------
    # MODAIS E FORMULÁRIOS DE JOGADORES (COM CAPTURA RFID REAL-TIME)
    # -------------------------------------------------------------------------
    def modal_novo_jogador(self):
        self.show_modulo_jogadores(selected_id="NEW")

    def modal_editar_jogador(self, player_id, current_real_name, current_nickname, current_tag_uid):
        if not HAS_CTK:
            return
        top = ctk.CTkToplevel(self.root)
        top.title(f"Editar Jogador #{player_id}")
        top.geometry("590x460")
        top.minsize(580, 450)
        top.transient(self.root)
        top.lift()
        top.focus_set()

        def fechar_modal_edit():
            self.active_rfid_capture_callback = None
            top.destroy()
        top.protocol("WM_DELETE_WINDOW", fechar_modal_edit)

        lbl = ctk.CTkLabel(top, text=f"Editar Perfil do Jogador #{player_id}", font=("Helvetica", 16, "bold"))
        lbl.pack(padx=20, pady=15)

        entry_name = ctk.CTkEntry(top, placeholder_text="Nome Completo", width=460)
        entry_name.insert(0, current_real_name or "")
        entry_name.pack(padx=20, pady=8)

        entry_nick = ctk.CTkEntry(top, placeholder_text="Gamer Tag / Nickname", width=460)
        entry_nick.insert(0, current_nickname or "")
        entry_nick.pack(padx=20, pady=8)

        # CARD DE LEITURA DE TAG RFID EM TEMPO REAL
        card_rfid = ctk.CTkFrame(top, fg_color="#1E1E1E", border_width=1, border_color="#333333")
        card_rfid.pack(fill="x", padx=20, pady=10)

        lbl_rfid_st = ctk.CTkLabel(card_rfid, text="📡 LEITURA DE TAG RFID EM TEMPO REAL", font=("Helvetica", 11, "bold"), text_color="#3B82F6")
        lbl_rfid_st.pack(anchor="w", padx=10, pady=(8, 2))

        lbl_rfid_desc = ctk.CTkLabel(card_rfid, text="Aproxime o cartão RFID no leitor de qualquer Nó Repórter para atualizar a UID:", font=("Helvetica", 10), text_color="#AAAAAA", justify="left")
        lbl_rfid_desc.pack(anchor="w", padx=10, pady=(0, 6))

        frame_tag_input = ctk.CTkFrame(card_rfid, fg_color="transparent")
        frame_tag_input.pack(fill="x", padx=10, pady=(0, 8))

        entry_tag = ctk.CTkEntry(frame_tag_input, placeholder_text="UID Hexadecimal (ou vazio)", width=220)
        entry_tag.insert(0, current_tag_uid or "")
        entry_tag.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def desvincular_tag():
            entry_tag.delete(0, "end")
            lbl_rfid_st.configure(text="● Tag desvinculada. Salve para confirmar.", text_color="#F59E0B")

        def preencher_com_ultima_edit():
            if getattr(self, "ultima_tag_lida", None):
                entry_tag.delete(0, "end")
                entry_tag.insert(0, self.ultima_tag_lida)
                lbl_rfid_st.configure(text=f"✅ TAG PREENCHIDA: {self.ultima_tag_lida}", text_color="#00FF88")
            else:
                messagebox.showinfo("RFID", "Nenhuma tag foi lida recentemente. Aproxime uma tag de qualquer nó primeiro.")

        btn_last_tag_edit = ctk.CTkButton(frame_tag_input, text="🏷️ Usar Última Lida", width=140, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], command=preencher_com_ultima_edit)
        btn_last_tag_edit.pack(side="left", padx=(0, 6))

        btn_desv = ctk.CTkButton(frame_tag_input, text="✕ Desvincular", width=110, fg_color="#374151", hover_color=THEME_TRYHARD["rage_red"], command=desvincular_tag)
        btn_desv.pack(side="left")

        def update_rfid_edit(tag_uid, mac_no):
            entry_tag.delete(0, "end")
            entry_tag.insert(0, tag_uid)
            lbl_rfid_st.configure(text=f"✅ NOVA TAG DETECTADA: {tag_uid} (Nó {mac_no})", text_color="#00FF88")

        self.active_rfid_capture_callback = update_rfid_edit

        def salvar():
            name = entry_name.get().strip()
            nick = entry_nick.get().strip()
            tag = entry_tag.get().strip().upper()
            if not name or not nick:
                messagebox.showerror("Erro de Validação", "Preencha o Nome Completo e o Nickname do jogador.")
                return
            self.active_rfid_capture_callback = None
            self.db.atualizar_jogador(player_id, name, nick, tag if tag else "")
            messagebox.showinfo("Sucesso", f"Cadastro de '{nick}' atualizado com sucesso!")
            top.destroy()
            self.show_modulo_jogadores(selected_id=player_id)

        btn_save = ctk.CTkButton(top, text="💾 Salvar Alterações", fg_color="#1F6AA5", command=salvar, width=220, height=36)
        btn_save.pack(padx=20, pady=15)

    def toggle_status_jogador(self, player_id, novo_status):
        if novo_status == 0:
            if messagebox.askyesno("Confirmar Inativação (Soft Delete)", "Deseja desativar este jogador?\n\nO registro e o histórico de campeonatos passados serão MANTIDOS intactos no banco de dados, mas ele não aparecerá em novos torneios."):
                self.db.desativar_jogador(player_id)
                self.show_modulo_jogadores(selected_id=player_id)
        else:
            self.db.reativar_jogador(player_id)
            self.show_modulo_jogadores(selected_id=player_id)

    def toggle_modo_mock(self):
        novo_mock = not self.driver_serial.mock
        self.driver_serial.mock = novo_mock
        status_txt = "COM: MOCK (OK)" if novo_mock else "COM: REAL (COM5)"
        self.lbl_status_com.configure(text=status_txt)

    def selecionar_evento(self, evento_id, mostrar_popup=False):
        self.evento_selecionado_id = evento_id
        self.atualizar_combo_torneios_global()
        ev = self.db.obter_evento(evento_id)
        if ev:
            if mostrar_popup:
                messagebox.showinfo("Sucesso", f"Torneio '{ev['name']}' (#ID {evento_id}) selecionado!")
            self.show_modulo_eventos()
            if ev["status"] == "DRAFT":
                self.event_tab_frame.set("✏️ Edição / Preparação")
            else:
                self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")

    def modal_novo_evento(self):
        # Criação do Assistente de 3 Passos (CTkToplevel)
        top = ctk.CTkToplevel(self.root)
        top.title("Assistente de Criação de Campeonato")
        top.geometry("660x690")
        top.minsize(640, 670)
        top.transient(self.root)
        top.lift()
        top.focus_set()

        # Estado do Wizard
        self.wizard_state = {
            "name": "",
            "date": time.strftime("%Y-%m-%d"),
            "mesas_mode": "manual", # "clone" ou "manual"
            "clone_from_event_id": None,
            "manual_mesas": [], # lista de dicts: {"name": "...", "node_mac": "..."}
            "selected_players": [] # lista de IDs
        }

        # Frame inferior de navegação (ancorado PRIMEIRO na base para nunca ser esmagado ou cortado)
        nav_frame = ctk.CTkFrame(top, fg_color="transparent")
        nav_frame.pack(fill="x", side="bottom", padx=20, pady=(10, 15))

        # Frame de conteúdo (expande no espaço restante superior)
        content_frame = ctk.CTkFrame(top, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=(10, 5))

        def clear_content():
            for w in content_frame.winfo_children():
                w.destroy()
            for w in nav_frame.winfo_children():
                w.destroy()

        def ir_para_passo_1():
            clear_content()

            # Título
            lbl_title = ctk.CTkLabel(content_frame, text="Passo 1: Identidade do Torneio", font=("Helvetica", 16, "bold"))
            lbl_title.pack(anchor="w", pady=(10, 15))

            lbl_name = ctk.CTkLabel(content_frame, text="Nome do Torneio:", font=("Helvetica", 12))
            lbl_name.pack(anchor="w", pady=2)
            entry_name = ctk.CTkEntry(content_frame, width=540, placeholder_text="Ex: PUCPR Open 2026 TCG")
            entry_name.pack(anchor="w", pady=5)
            entry_name.insert(0, self.wizard_state["name"])

            lbl_date = ctk.CTkLabel(content_frame, text="Data do Torneio (AAAA-MM-DD):", font=("Helvetica", 12))
            lbl_date.pack(anchor="w", pady=2)
            entry_date = ctk.CTkEntry(content_frame, width=540, placeholder_text="Ex: 2026-07-24")
            entry_date.pack(anchor="w", pady=5)
            entry_date.insert(0, self.wizard_state["date"])

            # Nav
            btn_cancel = ctk.CTkButton(nav_frame, text="Cancelar", fg_color="#374151", command=top.destroy)
            btn_cancel.pack(side="left", padx=5)

            def avancar():
                name = entry_name.get().strip()
                date = entry_date.get().strip()
                if not name or not date:
                    messagebox.showerror("Erro de Validação", "Preencha o Nome e a Data do torneio.")
                    return
                self.wizard_state["name"] = name
                self.wizard_state["date"] = date
                ir_para_passo_2()

            btn_next = ctk.CTkButton(nav_frame, text="Avançar ➡️", fg_color="#1F6AA5", command=avancar)
            btn_next.pack(side="right", padx=5)

        def ir_para_passo_2():
            clear_content()

            lbl_title = ctk.CTkLabel(content_frame, text="Passo 2: Configuração de Mesas / Estações", font=("Helvetica", 16, "bold"))
            lbl_title.pack(anchor="w", pady=(10, 15))

            # Segmented Button para escolher modo
            mode_var = ctk.StringVar(value="Manualmente" if self.wizard_state["mesas_mode"] == "manual" else "Clonar de Torneio Anterior")
            
            mode_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            mode_frame.pack(fill="x", pady=5)

            lbl_choice = ctk.CTkLabel(mode_frame, text="Escolha a origem das mesas:", font=("Helvetica", 12))
            lbl_choice.pack(anchor="w", pady=2)

            sub_container = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", border_width=1, border_color="#333333")
            sub_container.pack(fill="both", expand=True, pady=10)

            def refresh_sub_container(mode_val):
                for w in sub_container.winfo_children():
                    w.destroy()

                if mode_val == "Clonar de Torneio Anterior":
                    self.wizard_state["mesas_mode"] = "clone"
                    lbl_clone = ctk.CTkLabel(sub_container, text="Selecione o torneio de origem para clonar as mesas:", font=("Helvetica", 12))
                    lbl_clone.pack(anchor="w", padx=15, pady=(15, 5))

                    # Buscar torneios anteriores
                    cursor = self.db.conn.cursor()
                    cursor.execute("SELECT id, name, date FROM events ORDER BY id DESC")
                    eventos_anteriores = cursor.fetchall()
                    ev_map = {f"#{ev['id']} - {ev['name']} ({ev['date']})": ev['id'] for ev in eventos_anteriores}
                    ev_names = list(ev_map.keys())

                    combo_ev = ctk.CTkComboBox(sub_container, values=ev_names, width=400)
                    combo_ev.pack(anchor="w", padx=15, pady=10)
                    if ev_names:
                        combo_ev.set(ev_names[0])
                        self.wizard_state["clone_from_event_id"] = ev_map[ev_names[0]]

                    def on_ev_changed(val):
                        self.wizard_state["clone_from_event_id"] = ev_map[val]

                    combo_ev.configure(command=on_ev_changed)

                else:
                    self.wizard_state["mesas_mode"] = "manual"
                    lbl_man = ctk.CTkLabel(sub_container, text="Selecione ou configure as mesas de jogo físicas do torneio:", font=("Helvetica", 12, "bold"))
                    lbl_man.pack(anchor="w", padx=15, pady=(15, 5))

                    mesa_list_scroll = ctk.CTkScrollableFrame(sub_container, height=220, label_text="Mesas de Jogo & Hardware ESP-NOW")
                    mesa_list_scroll.pack(fill="both", expand=True, padx=15, pady=5)

                    rows_list = []
                    hw_opts_wiz, hw_map_wiz = self.obter_opcoes_hardware_dropdown()

                    def add_mesa_row(name="", mac=None):
                        r_frame = ctk.CTkFrame(mesa_list_scroll, fg_color="#242424", height=38)
                        r_frame.pack(fill="x", padx=5, pady=3)

                        e_name = ctk.CTkEntry(r_frame, placeholder_text="Nome (ex: Mesa 1)", width=120)
                        e_name.pack(side="left", padx=5, pady=5)
                        e_name.insert(0, name)

                        combo_hw = ctk.CTkComboBox(r_frame, values=hw_opts_wiz, width=280)
                        combo_hw.set(self.obter_label_para_mac(mac, hw_map_wiz))
                        combo_hw.pack(side="left", padx=5, pady=5)

                        def remover_linha():
                            rows_list.remove((e_name, combo_hw, r_frame))
                            r_frame.destroy()

                        btn_rem = ctk.CTkButton(r_frame, text="❌", width=30, fg_color="#881337", hover_color="#4c0519", command=remover_linha)
                        btn_rem.pack(side="right", padx=5, pady=5)

                        rows_list.append((e_name, combo_hw, r_frame))

                    # Se já havia mesas no estado manual do wizard, restaura:
                    if self.wizard_state["manual_mesas"]:
                        for m in self.wizard_state["manual_mesas"]:
                            add_mesa_row(m["name"], m["node_mac"])
                    else:
                        # Prioridade para carregar mesas padrão:
                        # 1. Mesas do evento atualmente selecionado
                        cursor = self.db.conn.cursor()
                        cur_ev_id = getattr(self, "evento_selecionado_id", None)
                        st_existentes = []
                        if cur_ev_id:
                            cursor.execute("SELECT name, node_mac FROM stations WHERE event_id = ? ORDER BY id ASC", (cur_ev_id,))
                            st_existentes = cursor.fetchall()
                        
                        # 2. Se não houver evento em foco com mesas, busca do torneio mais recente
                        if not st_existentes:
                            cursor.execute("""
                                SELECT name, node_mac FROM stations 
                                WHERE event_id = (SELECT id FROM events ORDER BY id DESC LIMIT 1)
                                ORDER BY id ASC
                            """)
                            st_existentes = cursor.fetchall()

                        if st_existentes:
                            for st in st_existentes:
                                add_mesa_row(st["name"], st["node_mac"])
                        else:
                            # 3. Caso não haja mesas em torneios recentes, monta pelas estações/nós físicos do inventário
                            cursor.execute("SELECT mac_address, nickname FROM nodes WHERE type = 'REPORTER' ORDER BY nickname ASC")
                            rep_nodes = cursor.fetchall()
                            if rep_nodes:
                                for idx, n in enumerate(rep_nodes):
                                    add_mesa_row(n["nickname"] or f"Mesa {idx+1}", n["mac_address"])
                            else:
                                add_mesa_row("Mesa 1", None)
                                add_mesa_row("Mesa 2", None)

                    # Salvar dados atuais temporários
                    def capturar_dados_manual():
                        temp_mesas = []
                        for en, cb_hw, _ in rows_list:
                            name_val = en.get().strip()
                            hw_label = cb_hw.get()
                            mac_val = hw_map_wiz.get(hw_label)
                            if name_val:
                                temp_mesas.append({"name": name_val, "node_mac": mac_val})
                        self.wizard_state["manual_mesas"] = temp_mesas

                    # Adiciona hook no avanço
                    self.capturar_dados_manual_hook = capturar_dados_manual

                    # Barra de Seleção e Adição de Mesas Pré-Cadastradas no Banco
                    frame_add_existente = ctk.CTkFrame(sub_container, fg_color="#18181B", border_width=1, border_color="#27272A")
                    frame_add_existente.pack(fill="x", padx=15, pady=(5, 6))

                    # Consulta mesas existentes válidas (do torneio em foco, mais recente ou templates)
                    cursor = self.db.conn.cursor()
                    cur_ev_id = getattr(self, "evento_selecionado_id", None)
                    if cur_ev_id:
                        cursor.execute("""
                            SELECT name, 
                                   MAX(CASE WHEN node_mac IS NOT NULL AND TRIM(node_mac) != '' THEN node_mac ELSE NULL END) as node_mac
                            FROM stations
                            WHERE event_id = ? OR event_id IS NULL
                            GROUP BY name
                            ORDER BY id ASC
                        """, (cur_ev_id,))
                    else:
                        cursor.execute("""
                            SELECT name, 
                                   MAX(CASE WHEN node_mac IS NOT NULL AND TRIM(node_mac) != '' THEN node_mac ELSE NULL END) as node_mac
                            FROM stations
                            WHERE event_id = (SELECT id FROM events ORDER BY id DESC LIMIT 1)
                            GROUP BY name
                            ORDER BY id ASC
                        """)
                    st_conhecidas = cursor.fetchall()
                    map_existentes = {}
                    for st in st_conhecidas:
                        hw_lbl = self.obter_label_para_mac(st["node_mac"], hw_map_wiz)
                        display_text = f"{st['name']} ({hw_lbl})"
                        map_existentes[display_text] = (st["name"], st["node_mac"])

                    opts_existentes = list(map_existentes.keys())
                    if not opts_existentes:
                        opts_existentes = ["Nenhuma mesa pré-cadastrada no banco"]
                        map_existentes["Nenhuma mesa pré-cadastrada no banco"] = (None, None)

                    lbl_combo_ex = ctk.CTkLabel(frame_add_existente, text="Mesa Existente:", font=("Helvetica", 11, "bold"), text_color="#D1D5DB")
                    lbl_combo_ex.pack(side="left", padx=(10, 5), pady=6)

                    combo_existente = ctk.CTkComboBox(frame_add_existente, values=opts_existentes, width=280)
                    combo_existente.set(opts_existentes[0])
                    combo_existente.pack(side="left", padx=5, pady=6)

                    def adicionar_mesa_selecionada():
                        sel = combo_existente.get()
                        st_dados = map_existentes.get(sel)
                        if not st_dados or not st_dados[0]:
                            messagebox.showwarning("Aviso", "Selecione uma mesa válida para adicionar.")
                            return
                        st_nome, st_mac = st_dados
                        # Verifica se já está na lista atual
                        nomes_atuais = [en.get().strip().lower() for en, _, _ in rows_list]
                        if st_nome.lower() in nomes_atuais:
                            messagebox.showinfo("Aviso", f"A mesa '{st_nome}' já está incluída na lista abaixo.")
                            return
                        add_mesa_row(st_nome, st_mac)

                    btn_add_sel = ctk.CTkButton(frame_add_existente, text="➕ Adicionar Selecionada", width=160, fg_color="#0284C7", hover_color="#0369A1", text_color="#FFFFFF", font=("Helvetica", 11, "bold"), command=adicionar_mesa_selecionada)
                    btn_add_sel.pack(side="left", padx=(5, 10), pady=6)

                    row_actions_wiz = ctk.CTkFrame(sub_container, fg_color="transparent")
                    row_actions_wiz.pack(fill="x", padx=15, pady=(4, 10))

                    btn_add_mesa = ctk.CTkButton(row_actions_wiz, text="+ Nova Mesa em Branco", fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 11, "bold"), command=lambda: add_mesa_row(f"Mesa {len(rows_list)+1}", None))
                    btn_add_mesa.pack(side="left", padx=(0, 10))

                    def abrir_mapeamento_do_wizard():
                        capturar_dados_manual()
                        def on_map_closed():
                            refresh_sub_container("Manualmente")
                        self.modal_mapear_nos_reporteres(on_close_callback=on_map_closed)

                    btn_map_nodes_wiz = ctk.CTkButton(row_actions_wiz, text="📡 Mapear Nós Repórteres", fg_color="#374151", hover_color="#4B5563", text_color="#FFFFFF", font=("Helvetica", 11, "bold"), command=abrir_mapeamento_do_wizard)
                    btn_map_nodes_wiz.pack(side="left")

            # Segmented Button
            seg_btn = ctk.CTkSegmentedButton(mode_frame, values=["Manualmente", "Clonar de Torneio Anterior"],
                                             command=refresh_sub_container)
            seg_btn.pack(anchor="w", pady=5)
            seg_btn.set(mode_var.get())
            refresh_sub_container(mode_var.get())

            # Nav
            btn_prev = ctk.CTkButton(nav_frame, text="⬅️ Voltar", fg_color="#374151", command=ir_para_passo_1)
            btn_prev.pack(side="left", padx=5)

            def avancar_passo_2():
                if self.wizard_state["mesas_mode"] == "manual":
                    if hasattr(self, "capturar_dados_manual_hook"):
                        self.capturar_dados_manual_hook()
                    if not self.wizard_state["manual_mesas"]:
                        messagebox.showerror("Erro de Validação", "Adicione pelo menos 1 mesa física de jogo.")
                        return
                else:
                    if not self.wizard_state["clone_from_event_id"]:
                        messagebox.showerror("Erro", "Selecione um torneio de origem para clonar as mesas.")
                        return
                ir_para_passo_3()

            btn_next = ctk.CTkButton(nav_frame, text="Avançar ➡️", fg_color="#1F6AA5", command=avancar_passo_2)
            btn_next.pack(side="right", padx=5)

        def ir_para_passo_3():
            clear_content()

            lbl_title = ctk.CTkLabel(content_frame, text="Passo 3: Seleção e Cadastro de Jogadores", font=("Helvetica", 16, "bold"))
            lbl_title.pack(anchor="w", pady=(10, 2))

            lbl_desc = ctk.CTkLabel(content_frame, text="Selecione os competidores cadastrados no banco para esta chave.\nUse a busca rápida para encontrar atletas em listas grandes.", font=("Helvetica", 11), text_color="#AAAAAA", justify="left")
            lbl_desc.pack(anchor="w", pady=2)

            # Barra de Busca Dinâmica de Atletas no Wizard
            search_wiz_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            search_wiz_frame.pack(fill="x", pady=(5, 0))

            entry_search_wiz = ctk.CTkEntry(search_wiz_frame, placeholder_text="🔍 Buscar atleta por apelido ou nome real...", height=32)
            entry_search_wiz.pack(fill="x", expand=True)

            scroll_players = ctk.CTkScrollableFrame(content_frame, height=250, label_text="Competidores no Banco")
            scroll_players.pack(fill="both", expand=True, pady=5)

            # Buscar todos os jogadores
            jogadores_banco = self.db.buscar_jogadores(query="", incluir_inativos=False)
            chk_map = {}
            row_frames_wiz = {}

            # Função de vínculo rápido dentro do Wizard
            def vincular_rfid_wizard(player_id, nickname):
                # Preservar seleções atuais dos checkboxes antes de recarregar a tela
                self.wizard_state["selected_players"] = [p_id for p_id, (chk, has_tag) in chk_map.items() if chk.get() == 1]

                top_v = ctk.CTkToplevel(top)
                top_v.title("Vincular RFID Rápido")
                top_v.geometry("400x200")
                top_v.transient(top)
                top_v.lift()
                top_v.focus_set()

                lbl_v = ctk.CTkLabel(top_v, text=f"Vincular Tag RFID para {nickname}", font=("Helvetica", 13, "bold"))
                lbl_v.pack(pady=15)

                entry_v = ctk.CTkEntry(top_v, placeholder_text="UID Tag Hexadecimal", width=220)
                entry_v.pack(pady=5)

                def fechar_v():
                    self.active_rfid_capture_callback = None
                    top_v.destroy()
                top_v.protocol("WM_DELETE_WINDOW", fechar_v)

                def update_cb(tag_uid, mac):
                    entry_v.delete(0, "end")
                    entry_v.insert(0, tag_uid)

                self.active_rfid_capture_callback = update_cb

                def salvar_v():
                    uid = entry_v.get().strip().upper()
                    if not uid:
                        return
                    self.active_rfid_capture_callback = None
                    cursor = self.db.conn.cursor()
                    cursor.execute("DELETE FROM rfid_tags WHERE tag_uid = ? OR player_id = ?", (uid, player_id))
                    cursor.execute("INSERT INTO rfid_tags (tag_uid, player_id) VALUES (?, ?)", (uid, player_id))
                    self.db.conn.commit()
                    messagebox.showinfo("Sucesso", f"Tag RFID '{uid}' vinculada com sucesso!")
                    top_v.destroy()
                    ir_para_passo_3()

                btn_v_save = ctk.CTkButton(top_v, text="Salvar Tag", fg_color="#10B981", command=salvar_v)
                btn_v_save.pack(pady=10)

            # Função para criar um novo jogador do zero no meio do Wizard
            def cadastrar_novo_jogador_wizard():
                # Preservar seleções atuais dos checkboxes
                self.wizard_state["selected_players"] = [p_id for p_id, (chk, has_tag) in chk_map.items() if chk.get() == 1]

                top_new = ctk.CTkToplevel(top)
                top_new.title("Cadastrar Novo Atleta")
                top_new.geometry("450x300")
                top_new.transient(top)
                top_new.lift()
                top_new.focus_set()

                def fechar_new():
                    self.active_rfid_capture_callback = None
                    top_new.destroy()
                top_new.protocol("WM_DELETE_WINDOW", fechar_new)

                lbl_n = ctk.CTkLabel(top_new, text="Cadastrar Novo Atleta no Banco", font=("Helvetica", 14, "bold"))
                lbl_n.pack(pady=15)

                e_nick = ctk.CTkEntry(top_new, placeholder_text="Nickname do Atleta", width=350)
                e_nick.pack(pady=5)

                e_name = ctk.CTkEntry(top_new, placeholder_text="Nome Real do Atleta", width=350)
                e_name.pack(pady=5)

                e_tag = ctk.CTkEntry(top_new, placeholder_text="UID RFID Tag (Opcional - aproxime o cartão do leitor)", width=350)
                e_tag.pack(pady=5)

                def update_new_cb(tag_uid, mac):
                    e_tag.delete(0, "end")
                    e_tag.insert(0, tag_uid)

                self.active_rfid_capture_callback = update_new_cb

                def salvar_novo():
                    nick = e_nick.get().strip()
                    real = e_name.get().strip()
                    tag = e_tag.get().strip().upper()
                    if not nick or not real:
                        messagebox.showerror("Erro", "Apelido e Nome Real são obrigatórios.")
                        return
                    self.active_rfid_capture_callback = None
                    p_id = self.db.cadastrar_jogador(real, nick, tag if tag else None)
                    messagebox.showinfo("Sucesso", f"Jogador '{nick}' cadastrado no banco com ID {p_id}!")
                    self.wizard_state["selected_players"].append(p_id)
                    top_new.destroy()
                    ir_para_passo_3()

                btn_n_save = ctk.CTkButton(top_new, text="💾 Gravar Atleta", fg_color="#10B981", command=salvar_novo)
                btn_n_save.pack(pady=15)

            for p in jogadores_banco:
                p_frame = ctk.CTkFrame(scroll_players, fg_color="#242424", height=38)
                p_frame.pack(fill="x", padx=5, pady=3)

                p_id = p["id"]
                has_tag = p["tag_uid"] is not None and len(p["tag_uid"].strip()) > 0
                checked = p_id in self.wizard_state["selected_players"]

                chk = ctk.CTkCheckBox(p_frame, text=f"{p['nickname']}", font=("Helvetica", 12))
                if checked:
                    chk.select()
                chk.pack(side="left", padx=10, pady=8)
                chk_map[p_id] = (chk, has_tag)
                row_frames_wiz[p_id] = (p_frame, p["nickname"], p["real_name"])

                if has_tag:
                    lbl_tag = ctk.CTkLabel(p_frame, text=f"🏷️ {p['tag_uid']}", font=("Helvetica", 10), text_color="#00FF88")
                    lbl_tag.pack(side="right", padx=10)
                else:
                    w_frame = ctk.CTkFrame(p_frame, fg_color="transparent")
                    w_frame.pack(side="right", padx=5)

                    lbl_warn = ctk.CTkLabel(w_frame, text="⚠️ Sem Tag", font=("Helvetica", 10, "bold"), text_color="#FF9900")
                    lbl_warn.pack(side="left", padx=5)

                    btn_v = ctk.CTkButton(w_frame, text="Vincular", width=60, height=22, fg_color="#D97706", hover_color="#B45309",
                                         command=lambda p_id=p_id, nick=p["nickname"]: vincular_rfid_wizard(p_id, nick))
                    btn_v.pack(side="left", padx=2)

            def filter_wiz_list(event=None):
                q = entry_search_wiz.get().strip().lower()
                for p_id, (r_frame, nick, real) in row_frames_wiz.items():
                    if not q or q in nick.lower() or q in real.lower():
                        r_frame.pack(fill="x", padx=5, pady=3)
                    else:
                        r_frame.pack_forget()

            entry_search_wiz.bind("<KeyRelease>", filter_wiz_list)

            btn_new_player = ctk.CTkButton(content_frame, text="+ Cadastrar Novo Jogador", fg_color="#374151", command=cadastrar_novo_jogador_wizard)
            btn_new_player.pack(anchor="w", pady=5)

            # Nav
            btn_prev = ctk.CTkButton(nav_frame, text="⬅️ Voltar", fg_color="#374151", command=ir_para_passo_2)
            btn_prev.pack(side="left", padx=5)

            def finalizar_wizard():
                # Salvar a seleção atual de jogadores no estado do wizard
                players_list = []
                missing_tags = []
                for p_id, (chk, has_tag) in chk_map.items():
                    if chk.get() == 1:
                        players_list.append(p_id)
                        if not has_tag:
                            cursor = self.db.conn.cursor()
                            cursor.execute("SELECT tag_uid FROM rfid_tags WHERE player_id = ?", (p_id,))
                            row = cursor.fetchone()
                            if not row or not row["tag_uid"]:
                                missing_tags.append(p_id)

                self.wizard_state["selected_players"] = players_list

                if len(players_list) < 2:
                    messagebox.showerror("Erro de Validação", "Selecione pelo menos 2 competidores para o torneio.")
                    return

                # Salvar efetivamente no banco
                new_id = self.db.cadastrar_evento(self.wizard_state["name"], self.wizard_state["date"], "DRAFT")

                # Salvar as mesas
                cursor = self.db.conn.cursor()
                if self.wizard_state["mesas_mode"] == "clone":
                    origin_id = self.wizard_state["clone_from_event_id"]
                    cursor.execute("SELECT name, node_mac FROM stations WHERE event_id = ?", (origin_id,))
                    stations_cloned = cursor.fetchall()
                    for st in stations_cloned:
                        # Criar os nós correspondentes se não existirem
                        if st["node_mac"]:
                            cursor.execute("UPDATE stations SET node_mac = NULL WHERE UPPER(node_mac) = UPPER(?)", (st["node_mac"],))
                            cursor.execute("INSERT OR IGNORE INTO nodes (mac_address, nickname, type) VALUES (?, ?, 'REPORTER')", (st["node_mac"], st["name"]))
                        cursor.execute("INSERT INTO stations (event_id, name, node_mac) VALUES (?, ?, ?)", (new_id, st["name"], st["node_mac"]))
                else:
                    for st in self.wizard_state["manual_mesas"]:
                        if st["node_mac"]:
                            cursor.execute("UPDATE stations SET node_mac = NULL WHERE UPPER(node_mac) = UPPER(?)", (st["node_mac"],))
                            cursor.execute("INSERT OR IGNORE INTO nodes (mac_address, nickname, type) VALUES (?, ?, 'REPORTER')", (st["node_mac"], st["name"]))
                        cursor.execute("INSERT INTO stations (event_id, name, node_mac) VALUES (?, ?, ?)", (new_id, st["name"], st["node_mac"]))
                self.db.conn.commit()

                # Salvar os jogadores
                self.db.atualizar_participantes_evento(new_id, players_list)

                messagebox.showinfo("Sucesso", f"Rascunho do torneio '{self.wizard_state['name']}' (#ID {new_id}) criado com sucesso!")
                top.destroy()
                self.selecionar_evento(new_id)

            btn_finish = ctk.CTkButton(nav_frame, text="💾 Criar Rascunho", fg_color="#10B981", hover_color="#059669", command=finalizar_wizard)
            btn_finish.pack(side="right", padx=5)

        # Inicia no Passo 1
        ir_para_passo_1()



    def modal_contexto_partida(self, match_id):
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT m.id, m.event_id, m.player1_id, m.player2_id,
                   p1.nickname as p1_name, p2.nickname as p2_name,
                   p1.id as p1_id, p2.id as p2_id,
                   m.score1, m.score2, m.status, s.id as station_id, s.name as station_name,
                   s.node_mac, m.player1_checked_in, m.player2_checked_in
            FROM matches m
            LEFT JOIN players p1 ON m.player1_id = p1.id
            LEFT JOIN players p2 ON m.player2_id = p2.id
            LEFT JOIN stations s ON m.station_id = s.id
            WHERE m.id = ?
        """, (match_id,))
        m = cursor.fetchone()
        if not m:
            messagebox.showerror("Erro", f"Partida #{match_id} não encontrada no banco.")
            return

        top = ctk.CTkToplevel(self.root)
        top.title(f"Controle da Partida #{match_id}")
        top.geometry("540x660")
        top.minsize(520, 620)
        top.transient(self.root)
        top.lift()
        top.focus_set()

        p1_name = m["p1_name"] or "A Definir"
        p2_name = m["p2_name"] or "A Definir"
        status = m["status"]
        station_name = m["station_name"] or "Nenhuma mesa alocada"
        node_mac = m["node_mac"] or "Sem MAC"

        top.configure(fg_color=THEME_TRYHARD["bg_main"])

        lbl_head = ctk.CTkLabel(top, text=f"Partida #{match_id}", font=("Helvetica", 16, "bold"), text_color=THEME_TRYHARD["text_main"])
        lbl_head.pack(padx=20, pady=(15, 5))

        lbl_vs = ctk.CTkLabel(top, text=f"{p1_name}   💢 VS   {p2_name}", font=("Helvetica", 14, "bold"), text_color=THEME_TRYHARD["primary"])
        lbl_vs.pack(padx=20, pady=5)

        # Status da Partida com Badge / Símbolo do Rage
        if status == "PLAYING":
            status_display = "💢 Em Andamento"
            status_color = THEME_TRYHARD["rage_red"]
        elif status == "READY":
            status_display = "⚠️ Aguardando Confirmação Presencial"
            status_color = THEME_TRYHARD["status_waiting"]
        elif status == "FINISHED":
            status_display = "✓ Finalizado"
            status_color = THEME_TRYHARD["status_success"]
        else:
            status_display = "Aguardando"
            status_color = THEME_TRYHARD["text_muted"]

        lbl_info = ctk.CTkLabel(top, text=f"Status da Partida: {status_display}\nMesa Física: {station_name} ({node_mac})", font=("Helvetica", 11, "bold"), text_color=status_color)
        lbl_info.pack(padx=20, pady=5)

        # Status do Check-In RFID dos Jogadores
        p1_st = "Confirmado ✓" if m["player1_checked_in"] else "Pendente (Aguardando PoPL)"
        p2_st = "Confirmado ✓" if m["player2_checked_in"] else "Pendente (Aguardando PoPL)"
        p1_st_col = THEME_TRYHARD["status_success"] if m["player1_checked_in"] else THEME_TRYHARD["status_waiting"]
        p2_st_col = THEME_TRYHARD["status_success"] if m["player2_checked_in"] else THEME_TRYHARD["status_waiting"]

        lbl_status_p1 = ctk.CTkLabel(top, text=f"Check-In {p1_name}: {p1_st}", font=("Helvetica", 11, "bold"), text_color=p1_st_col)
        lbl_status_p1.pack(padx=20, pady=2)
        lbl_status_p2 = ctk.CTkLabel(top, text=f"Check-In {p2_name}: {p2_st}", font=("Helvetica", 11, "bold"), text_color=p2_st_col)
        lbl_status_p2.pack(padx=20, pady=2)

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # SEÇÃO 1: Chamar Partida / Realocar Mesa
        # -------------------------------------------------------------
        p1_val = m["player1_id"]
        p2_val = m["player2_id"]
        is_finished = (m["status"] == "FINISHED")

        # Verifica se é um BYE verdadeiro (folha já resolvida sem adversário ou atleta nomeado 'BYE')
        is_bye = (is_finished and (p1_val is None or p2_val is None)) or \
                 (m["p1_name"] and "BYE" in str(m["p1_name"]).upper()) or \
                 (m["p2_name"] and "BYE" in str(m["p2_name"]).upper())

        # Verifica se é uma partida futura que aguarda definição das partidas anteriores
        is_waiting_opponents = (not is_bye and not is_finished and (p1_val is None or p2_val is None))

        # -------------------------------------------------------------
        # SEÇÃO 1: Chamar Partida / Realocar Mesa
        # -------------------------------------------------------------
        frame_call = ctk.CTkFrame(top, fg_color="#1E1E1E", border_width=1, border_color="#333333")
        frame_call.pack(fill="x", padx=20, pady=10)

        lbl_sec1 = ctk.CTkLabel(frame_call, text="📣 Chamada & Localidade Física (ESP-NOW)", font=("Helvetica", 11, "bold"))
        lbl_sec1.pack(anchor="w", padx=15, pady=(8, 2))

        # Obter opções de mesas livres do torneio (filtra mesas ocupadas por outras partidas ativas)
        stations_list = self.db.obter_estacoes_disponiveis(m["event_id"], match_id)
        st_options = {s["name"]: s["id"] for s in stations_list}
        st_names = list(st_options.keys())
        if not st_names:
            st_names = ["⚠️ Nenhuma Mesa Livre no Momento"]
            st_options["⚠️ Nenhuma Mesa Livre no Momento"] = None

        combo_stations = None

        if is_bye:
            lbl_bye_info = ctk.CTkLabel(
                frame_call, 
                text="ℹ️ Avanço Automático por BYE (Sem Adversário)\nEsta partida não requer mesa física, check-in ou reporte de placar.",
                font=("Helvetica", 11, "bold"), 
                text_color="#38BDF8", 
                justify="left"
            )
            lbl_bye_info.pack(padx=15, pady=(5, 12), anchor="w")
        elif is_waiting_opponents:
            lbl_wait_info = ctk.CTkLabel(
                frame_call,
                text="⏳ Aguardando Conclusão de Partidas Anteriores\nEsta partida será liberada para chamada assim que os vencedores das rodadas anteriores forem definidos.",
                font=("Helvetica", 11, "bold"),
                text_color="#F59E0B",
                justify="left"
            )
            lbl_wait_info.pack(padx=15, pady=(5, 12), anchor="w")
        elif is_finished:
            row_fin = ctk.CTkFrame(frame_call, fg_color="transparent")
            row_fin.pack(fill="x", padx=15, pady=(5, 10))
            lbl_fin_info = ctk.CTkLabel(
                row_fin, 
                text="✓ Partida já finalizada e consolidada.", 
                font=("Helvetica", 11, "bold"), 
                text_color=THEME_TRYHARD["status_success"]
            )
            lbl_fin_info.pack(side="left")

            if m["station_id"]:
                def liberar_mesa_fin():
                    cursor.execute("UPDATE matches SET station_id = NULL WHERE id = ?", (match_id,))
                    self.db.conn.commit()
                    messagebox.showinfo("Sucesso", "Vínculo de mesa liberado com sucesso.")
                    top.destroy()
                    self.show_modulo_eventos()
                    self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")

                btn_liberar = ctk.CTkButton(row_fin, text="Liberar Mesa", width=110, fg_color="#4B5563", hover_color="#374151", command=liberar_mesa_fin)
                btn_liberar.pack(side="right")
        else:
            row_actions_call = ctk.CTkFrame(frame_call, fg_color="transparent")
            row_actions_call.pack(fill="x", padx=15, pady=(2, 10))

            combo_stations = ctk.CTkComboBox(row_actions_call, values=st_names, width=220)
            if m["station_name"] and m["station_name"] in st_options:
                combo_stations.set(m["station_name"])
            else:
                combo_stations.set(st_names[0])
            combo_stations.pack(side="left")

            def chamar_partida():
                selected_st_name = combo_stations.get()
                if not selected_st_name or selected_st_name in ("Nenhuma Mesa Cadastrada", "⚠️ Nenhuma Mesa Livre no Momento"):
                    messagebox.showerror(
                        "Mesa Indisponível",
                        "Não há mesas livres disponíveis no momento para chamar esta partida.\n"
                        "Aguarde a finalização de uma partida em andamento ou libere uma mesa."
                    )
                    return
                st_id = st_options.get(selected_st_name)
                if not st_id:
                    messagebox.showerror("Erro", "Mesa selecionada inválida.")
                    return

                # Validação defensiva direta no banco para prevenir alocação de mesa já ocupada
                cursor.execute("""
                    SELECT id, status FROM matches 
                    WHERE station_id = ? AND status IN ('READY', 'PLAYING') AND id != ?
                """, (st_id, match_id))
                conflito = cursor.fetchone()
                if conflito:
                    messagebox.showerror(
                        "Mesa Ocupada",
                        f"A mesa '{selected_st_name}' já está ocupada pela partida #{conflito['id']} (Status: {conflito['status']}).\n"
                        "Escolha outra mesa livre ou aguarde a finalização da partida ativa."
                    )
                    return
                
                # Atualiza no banco: status READY e mesa associada
                cursor.execute("UPDATE matches SET station_id = ?, status = 'READY' WHERE id = ?", (st_id, match_id))
                self.db.conn.commit()

                # Envia comando serial Downlink de LED Amarelo para a mesa
                cursor.execute("SELECT node_mac FROM stations WHERE id = ?", (st_id,))
                st_row = cursor.fetchone()
                if st_row and st_row["node_mac"]:
                    self.driver_serial.enviar_comando_no(st_row["node_mac"], "LED;YELLOW")
                    messagebox.showinfo("Sucesso", f"Partida chamada na {selected_st_name}! Comando de LED Yellow enviado via serial.")
                else:
                    messagebox.showinfo("Sucesso", f"Partida associada à {selected_st_name}, mas a mesa não possui nó MAC configurado.")
                top.destroy()
                self.show_modulo_eventos()
                self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")

            btn_call = ctk.CTkButton(row_actions_call, text="Chamar Mesa", fg_color="#D97706", hover_color="#B45309", width=120, command=chamar_partida)
            btn_call.pack(side="right")

            if m["station_id"]:
                def liberar_mesa_ativa():
                    cursor.execute("UPDATE matches SET station_id = NULL WHERE id = ?", (match_id,))
                    self.db.conn.commit()
                    messagebox.showinfo("Sucesso", "Mesa desvinculada desta partida.")
                    top.destroy()
                    self.show_modulo_eventos()
                    self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")

                btn_unassign = ctk.CTkButton(row_actions_call, text="Desvincular Mesa", fg_color="#4B5563", hover_color="#374151", width=120, command=liberar_mesa_ativa)
                btn_unassign.pack(side="right", padx=10)

        # -------------------------------------------------------------
        # SEÇÃO 2: Registro de Placar Administrativo (Forçado)
        # -------------------------------------------------------------
        if not is_bye and not is_waiting_opponents:
            frame_score = ctk.CTkFrame(top, fg_color="#1E1E1E", border_width=1, border_color="#333333")
            frame_score.pack(fill="x", padx=20, pady=10)

            lbl_sec2 = ctk.CTkLabel(frame_score, text="🏆 Resultado Administrativo (Sobrescrever Físico)", font=("Helvetica", 11, "bold"))
            lbl_sec2.pack(anchor="w", padx=15, pady=(8, 2))

            lbl_bo3_hint = ctk.CTkLabel(frame_score, text="* Formato: Melhor de 3 (Bo3). 2 vitórias (ex: 2x0, 2x1) finalizam a partida.\n  Placares parciais (ex: 1x0, 1x1) mantêm a partida em andamento.", font=("Helvetica", 9), text_color="#AAAAAA", justify="left")
            lbl_bo3_hint.pack(anchor="w", padx=15, pady=(0, 4))

            score_fields = ctk.CTkFrame(frame_score, fg_color="transparent")
            score_fields.pack(fill="x", padx=15, pady=2)

            lbl_s1 = ctk.CTkLabel(score_fields, text=f"{p1_name}:")
            lbl_s1.pack(side="left", padx=5)

            entry_s1 = ctk.CTkEntry(score_fields, width=50, placeholder_text="0")
            entry_s1.pack(side="left", padx=5)
            entry_s1.insert(0, str(m["score1"] or 0))

            lbl_s2 = ctk.CTkLabel(score_fields, text=f"  vs  {p2_name}:")
            lbl_s2.pack(side="left", padx=5)

            entry_s2 = ctk.CTkEntry(score_fields, width=50, placeholder_text="0")
            entry_s2.pack(side="left", padx=5)
            entry_s2.insert(0, str(m["score2"] or 0))

            def forcar_placar():
                try:
                    s1_val = int(entry_s1.get().strip())
                    s2_val = int(entry_s2.get().strip())
                except ValueError:
                    messagebox.showerror("Erro de Validação", "Insira valores inteiros válidos para o placar.")
                    return
                
                # Garantir que há uma estação vinculada para o motor (ou associa a que está selecionada no combo)
                curr_station_id = m["station_id"]
                if not curr_station_id:
                    if combo_stations and combo_stations.get() in st_options:
                        curr_station_id = st_options[combo_stations.get()]
                    else:
                        cursor.execute("SELECT id FROM stations WHERE event_id = ? LIMIT 1", (m["event_id"],))
                        st_fallback = cursor.fetchone()
                        if st_fallback:
                            curr_station_id = st_fallback["id"]

                    if curr_station_id:
                        cursor.execute("UPDATE matches SET station_id = ? WHERE id = ?", (curr_station_id, match_id))
                        self.db.conn.commit()
                    else:
                        messagebox.showerror("Erro", "Cadastre ou associe uma mesa no evento antes de consolidar o placar.")
                        return

                # Força o status para PLAYING na partida para o motor processar
                cursor.execute("UPDATE matches SET status = 'PLAYING' WHERE id = ?", (match_id,))
                self.db.conn.commit()

                # Chama o método de consolidação e promoção da Engine
                sucesso = self.motor.reportar_placar_ciberfisico(curr_station_id, s1_val, s2_val)
                if sucesso:
                    # Envia comando de LED verde para sinalizar conclusão física no nó
                    cursor.execute("SELECT node_mac FROM stations WHERE id = ?", (curr_station_id,))
                    mac_row = cursor.fetchone()
                    if mac_row and mac_row["node_mac"]:
                        self.driver_serial.enviar_comando_no(mac_row["node_mac"], "LED;GREEN")
                    messagebox.showinfo("Sucesso", f"Placar de {s1_val}x{s2_val} consolidado administrativamente!")
                else:
                    messagebox.showerror("Erro", "O motor de torneio falhou em processar o reporte do placar.")
                
                top.destroy()
                self.show_modulo_eventos()
                self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")

            btn_score = ctk.CTkButton(frame_score, text="Salvar Resultado", fg_color="#10B981", hover_color="#059669", width=120, command=forcar_placar)
            btn_score.pack(anchor="e", padx=15, pady=(2, 10))

        # -------------------------------------------------------------
        # SEÇÃO 3: Desqualificação / W.O.
        # -------------------------------------------------------------
        if not is_bye and not is_waiting_opponents:
            frame_wo = ctk.CTkFrame(top, fg_color="#1E1E1E", border_width=1, border_color="#333333")
            frame_wo.pack(fill="x", padx=20, pady=10)

            lbl_sec3 = ctk.CTkLabel(frame_wo, text="⚠️ W.O. ou Desqualificação Direta (DQ)", font=("Helvetica", 11, "bold"))
            lbl_sec3.pack(anchor="w", padx=15, pady=(8, 5))

            def aplicar_dq(player_id, name):
                if not player_id:
                    messagebox.showerror("Erro", "Oponente indefinido para aplicar desqualificação.")
                    return
                if messagebox.askyesno("Confirmar DQ", f"Tem certeza que deseja desqualificar '{name}'?\nO oponente será promovido automaticamente."):
                    sucesso, msg = self.motor.desqualificar_jogador(match_id, player_id)
                    if sucesso:
                        # Envia comando de LED verde para liberar mesa física
                        if m["station_id"]:
                            cursor.execute("SELECT node_mac FROM stations WHERE id = ?", (m["station_id"],))
                            mac_row = cursor.fetchone()
                            if mac_row and mac_row["node_mac"]:
                                self.driver_serial.enviar_comando_no(mac_row["node_mac"], "LED;GREEN")
                        messagebox.showinfo("Sucesso", f"Jogador '{name}' desqualificado com sucesso!")
                    else:
                        messagebox.showerror("Erro", f"Falha na desqualificação:\n\n{msg}")
                    top.destroy()
                    self.show_modulo_eventos()
                    self.event_tab_frame.set("🌲 Árvore de Brackets Interativa")

            btn_dq1 = ctk.CTkButton(frame_wo, text=f"❌ DQ {p1_name}", fg_color="#881337", hover_color="#4c0519", width=180,
                                   command=lambda: aplicar_dq(m["p1_id"], p1_name))
            btn_dq1.pack(side="left", padx=15, pady=10)

            btn_dq2 = ctk.CTkButton(frame_wo, text=f"❌ DQ {p2_name}", fg_color="#881337", hover_color="#4c0519", width=180,
                                   command=lambda: aplicar_dq(m["p2_id"], p2_name))
            btn_dq2.pack(side="right", padx=15, pady=10)

    def modal_gerenciar_tags_torneio(self):
        if not getattr(self, "evento_selecionado_id", None):
            messagebox.showerror("Erro", "Nenhum torneio selecionado.")
            return

        top = ctk.CTkToplevel(self.root)
        top.title("Gerenciador de Tags RFID do Torneio")
        top.geometry("550x500")
        top.transient(self.root)
        top.lift()
        top.focus_set()

        lbl_t = ctk.CTkLabel(top, text="🏷️ Tags RFID dos Competidores Inscritos", font=("Helvetica", 16, "bold"))
        lbl_t.pack(padx=20, pady=15)

        scroll = ctk.CTkScrollableFrame(top, label_text="Atletas do Torneio")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT p.id, p.real_name, p.nickname, r.tag_uid, ep.checked_in
            FROM event_players ep
            JOIN players p ON ep.player_id = p.id
            LEFT JOIN rfid_tags r ON p.id = r.player_id
            WHERE ep.event_id = ?
            ORDER BY p.nickname ASC
        """, (self.evento_selecionado_id,))
        players = cursor.fetchall()

        if not players:
            lbl_empty = ctk.CTkLabel(scroll, text="Nenhum competidor inscrito neste torneio.")
            lbl_empty.pack(pady=20)
        else:
            for p in players:
                p_id = p["id"]
                nick = p["nickname"]
                real = p["real_name"]
                tag = p["tag_uid"] or "Sem Tag"
                checked = p["checked_in"]

                r_frame = ctk.CTkFrame(scroll, fg_color="#242424", height=42)
                r_frame.pack(fill="x", padx=5, pady=3)

                st_txt = "✓ Checked-in" if checked else "Pendente"
                st_color = "#00FF88" if checked else "#FF9900"

                lbl_info = ctk.CTkLabel(r_frame, text=f"#{p_id} {nick}  |  Tag: {tag}", font=("Helvetica", 11, "bold"))
                lbl_info.pack(side="left", padx=10)

                lbl_chk = ctk.CTkLabel(r_frame, text=st_txt, font=("Helvetica", 10), text_color=st_color)
                lbl_chk.pack(side="left", padx=10)

                def simular_tag_atleta(pid=p_id, nickname=nick, real_name=real):
                    import uuid
                    new_tag = f"SIM-{uuid.uuid4().hex[:6].upper()}"
                    self.db.cadastrar_jogador(real_name, nickname, new_tag)
                    messagebox.showinfo("Nova Tag Gerada", f"Tag '{new_tag}' atribuída ao atleta {nickname}!")
                    top.destroy()
                    self.modal_gerenciar_tags_torneio()

                btn_sim = ctk.CTkButton(r_frame, text="📲 Simular", width=85, height=26, fg_color="#374151", command=simular_tag_atleta)
                btn_sim.pack(side="right", padx=5)

                btn_edit = ctk.CTkButton(r_frame, text="✏️ Vincular", width=80, height=26, fg_color="#2563EB", command=lambda pid=p_id, n=nick: self.modal_vincular_rfid_onthefly(pid, n))
                btn_edit.pack(side="right", padx=5)

    def acao_clicar_gerenciar_estacoes(self, event=None):
        """
        Abre o modal de Gerenciamento de Estações normalmente.
        Atalho Oculto de Manutenção (Ctrl + Shift + Clique):
        Dispara a Auditoria e Sanitização de Integridade do Banco de Dados em vez de abrir o modal.
        """
        ctrl_pressed = False
        shift_pressed = False

        # 1. Verificação nativa no Windows via GetKeyState (ctypes)
        try:
            import ctypes
            ctrl_pressed = bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
            shift_pressed = bool(ctypes.windll.user32.GetKeyState(0x10) & 0x8000)
        except Exception:
            pass

        # 2. Verificação complementar via event.state do Tkinter (Ctrl=0x4, Shift=0x1)
        if event and hasattr(event, "state"):
            if (event.state & 0x0004) and (event.state & 0x0001):
                ctrl_pressed = True
                shift_pressed = True

        # 3. Fallback no estado registrado no mouse_press recente
        last_ev = getattr(self, "_last_btn_press_event", None)
        if last_ev and hasattr(last_ev, "state"):
            if (last_ev.state & 0x0004) and (last_ev.state & 0x0001):
                ctrl_pressed = True
                shift_pressed = True

        if ctrl_pressed and shift_pressed:
            print("[SISTEMA] 🛡️ Atalho de Manutenção acionado (Ctrl + Shift + Clique): Disparando Auditoria de Integridade do Banco de Dados!")
            self.acao_auditar_integridade_banco()
        else:
            self.modal_gerenciar_mesas_torneio()

    def modal_gerenciar_mesas_torneio(self, aba_inicial="mesas", on_close_callback=None):
        """
        Janela Unificada de Gestão Ciberfísica:
        - Aba 1: 🪑 Estações - Master/Detail, criação de mesas, vínculo de hardware e status.
        - Aba 2: 📡 Nós Repórteres & Varredura - Disparo ativo de broadcast ESP-NOW,
                 descoberta em tempo real, telemetria, teste de LEDs e atribuição direta a mesas.
        """
        ev_id = getattr(self, "evento_selecionado_id", None)
        ev = self.db.obter_evento(ev_id) if ev_id else None
        ev_name = ev["name"] if ev else "Geral (Sem Torneio Ativo)"

        top = ctk.CTkToplevel(self.root)
        top.title("🎛️ Gestão de Estações & Varredura de Nós ESP-NOW")
        top.geometry("1020x720")
        top.minsize(940, 620)
        top.transient(self.root)
        top.lift()
        top.focus_set()

        # Header do Modal
        header_frame = ctk.CTkFrame(top, fg_color=THEME_TRYHARD["bg_card"], height=52, corner_radius=0)
        header_frame.pack(fill="x")

        lbl_header_title = ctk.CTkLabel(
            header_frame, 
            text=f"🎛️ Gestão Ciberfísica: Estações & Nós Repórteres | Torneio: {ev_name}", 
            font=("Helvetica", 14, "bold"),
            text_color="#FFFFFF"
        )
        lbl_header_title.pack(side="left", padx=16, pady=12)

        # Abas Principais
        tabview = ctk.CTkTabview(
            top, 
            fg_color=THEME_TRYHARD["bg_card"], 
            segmented_button_fg_color=THEME_TRYHARD["bg_main"], 
            segmented_button_selected_color=THEME_TRYHARD["primary"], 
            segmented_button_selected_hover_color=THEME_TRYHARD["primary_hover"], 
            segmented_button_unselected_color=THEME_TRYHARD["bg_card"], 
            segmented_button_unselected_hover_color=THEME_TRYHARD["bg_card_alt"], 
            text_color=THEME_TRYHARD["text_main"]
        )
        tabview.pack(fill="both", expand=True, padx=12, pady=(5, 10))

        tab_mesas = tabview.add("🪑 Estações")
        tab_nos = tabview.add("📡 Nós Repórteres & Varredura")

        # =====================================================================
        # ABA 1: ESTAÇÕES
        # =====================================================================
        selected_station_id = [None]

        top_mesas_bar = ctk.CTkFrame(tab_mesas, fg_color="transparent")
        top_mesas_bar.pack(fill="x", padx=10, pady=(5, 10))

        lbl_mesas_sub = ctk.CTkLabel(
            top_mesas_bar, 
            text="Mesas configuradas para realização de partidas e chancelas de placares", 
            font=("Helvetica", 12),
            text_color="#9CA3AF"
        )
        lbl_mesas_sub.pack(side="left")

        split_mesas = ctk.CTkFrame(tab_mesas, fg_color="transparent")
        split_mesas.pack(fill="both", expand=True, padx=5, pady=5)

        left_mesas_frame = ctk.CTkFrame(split_mesas, fg_color=THEME_TRYHARD["bg_card"], width=360)
        left_mesas_frame.pack(side="left", fill="both", padx=(0, 6))
        left_mesas_frame.pack_propagate(False)

        scroll_mesas = ctk.CTkScrollableFrame(left_mesas_frame, label_text="Lista de Estações")
        scroll_mesas.pack(fill="both", expand=True, padx=6, pady=6)

        detail_mesas_frame = ctk.CTkScrollableFrame(split_mesas, label_text="Detalhes da Estação Selecionada")
        detail_mesas_frame.pack(side="left", fill="both", expand=True, padx=(6, 0))

        def refresh_mesas(manter_selecao=True):
            for w in scroll_mesas.winfo_children():
                w.destroy()

            cursor = self.db.conn.cursor()
            cur_ev_id = getattr(self, "evento_selecionado_id", None)
            if cur_ev_id:
                cursor.execute("SELECT id, name, node_mac FROM stations WHERE event_id = ? OR event_id IS NULL ORDER BY id ASC", (cur_ev_id,))
            else:
                cursor.execute("SELECT id, name, node_mac FROM stations ORDER BY id ASC")
            stations = cursor.fetchall()

            if not stations:
                lbl_vazio = ctk.CTkLabel(scroll_mesas, text="Nenhuma estação cadastrada.\nClique em '+ Nova Estação' acima.", font=("Helvetica", 11), text_color="#6B7280")
                lbl_vazio.pack(pady=30)
                render_detalhe_mesa(None)
                return

            if not manter_selecao or selected_station_id[0] not in [s["id"] for s in stations]:
                selected_station_id[0] = stations[0]["id"]

            for st in stations:
                sid = st["id"]
                sname = st["name"]
                smac = st["node_mac"]
                det = self.db.obter_detalhes_estacao(sid)

                partida = det.get("partida_ativa") if det else None
                if partida:
                    if partida.get("score_conflict"):
                        st_status = f"🚨 DIVERGÊNCIA (#{partida['id']})"
                        st_color = THEME_TRYHARD["rage_red"]
                        b_color = THEME_TRYHARD["rage_red"]
                    elif partida.get("pending_score1") is not None:
                        st_status = "🟡 Chancela Pendente"
                        st_color = THEME_TRYHARD["status_waiting"]
                        b_color = THEME_TRYHARD["status_waiting"]
                    elif partida.get("status") == "PLAYING":
                        st_status = f"💢 Em Jogo (#{partida['id']})"
                        st_color = THEME_TRYHARD["rage_red"]
                        b_color = THEME_TRYHARD["rage_red"]
                    else:
                        st_status = f"⚠️ Convocada (#{partida['id']})"
                        st_color = THEME_TRYHARD["status_waiting"]
                        b_color = THEME_TRYHARD["status_waiting"]
                else:
                    st_status = "🟢 Livre"
                    st_color = THEME_TRYHARD["status_success"]
                    b_color = THEME_TRYHARD["border"]

                if smac:
                    telem = self.node_telemetry.get(smac, {})
                    is_online = (time.time() - telem.get("last_seen", 0)) < 60
                    hw_txt = f"📡 {det.get('node_nickname') or smac[-5:]} {'(🟢)' if is_online else '(⚪)'}"
                    hw_color = THEME_TRYHARD["primary"]
                else:
                    hw_txt = "⚠️ Sem Nó (Manual)"
                    hw_color = THEME_TRYHARD["text_muted"]

                is_sel = (sid == selected_station_id[0])
                card_bg = THEME_TRYHARD["bg_card_alt"] if is_sel else THEME_TRYHARD["bg_card"]
                if is_sel:
                    b_color = THEME_TRYHARD["primary"]

                card = ctk.CTkFrame(scroll_mesas, fg_color=card_bg, border_width=2, border_color=b_color, corner_radius=6)
                card.pack(fill="x", padx=3, pady=3)

                c_inner = ctk.CTkFrame(card, fg_color="transparent")
                c_inner.pack(fill="x", padx=10, pady=8)

                lbl_n = ctk.CTkLabel(c_inner, text=sname, font=("Helvetica", 12, "bold"), text_color="#FFFFFF")
                lbl_n.pack(anchor="w")

                row_st = ctk.CTkFrame(c_inner, fg_color="transparent")
                row_st.pack(fill="x", pady=(2, 0))

                lbl_stat = ctk.CTkLabel(row_st, text=st_status, font=("Helvetica", 10, "bold"), text_color=st_color)
                lbl_stat.pack(side="left")

                lbl_hw = ctk.CTkLabel(row_st, text=hw_txt, font=("Helvetica", 10), text_color=hw_color)
                lbl_hw.pack(side="right")

                def make_click(station_id=sid):
                    selected_station_id[0] = station_id
                    refresh_mesas(manter_selecao=True)

                card.bind("<Button-1>", lambda e, s=sid: make_click(s))
                c_inner.bind("<Button-1>", lambda e, s=sid: make_click(s))
                lbl_n.bind("<Button-1>", lambda e, s=sid: make_click(s))
                lbl_stat.bind("<Button-1>", lambda e, s=sid: make_click(s))
                lbl_hw.bind("<Button-1>", lambda e, s=sid: make_click(s))

            render_detalhe_mesa(selected_station_id[0])

        def render_detalhe_mesa(station_id):
            for w in detail_mesas_frame.winfo_children():
                w.destroy()

            if not station_id:
                lbl_sel = ctk.CTkLabel(detail_mesas_frame, text="Selecione uma estação à esquerda para inspecionar os detalhes.", font=("Helvetica", 12), text_color="#6B7280")
                lbl_sel.pack(pady=40)
                return

            det = self.db.obter_detalhes_estacao(station_id)
            if not det:
                return

            top_det = ctk.CTkFrame(detail_mesas_frame, fg_color="transparent")
            top_det.pack(fill="x", padx=10, pady=5)

            lbl_t = ctk.CTkLabel(top_det, text=f"🪑 {det['name']}", font=("Helvetica", 16, "bold"), text_color="#FFFFFF")
            lbl_t.pack(side="left")

            lbl_id_badge = ctk.CTkLabel(top_det, text=f"ID #{det['id']}", font=("Helvetica", 11), text_color="#6B7280")
            lbl_id_badge.pack(side="left", padx=10)

            def modal_renomear_mesa():
                top_ren = ctk.CTkToplevel(top)
                top_ren.title("Renomear Estação")
                top_ren.geometry("420x220")
                top_ren.transient(top)
                top_ren.lift()
                top_ren.focus_set()

                lbl_ren_title = ctk.CTkLabel(top_ren, text=f"Renomear Estação: {det['name']}", font=("Helvetica", 13, "bold"))
                lbl_ren_title.pack(pady=(15, 10))

                entry_novo_nome = ctk.CTkEntry(top_ren, placeholder_text="Novo Nome da Estação", width=320)
                entry_novo_nome.insert(0, det['name'])
                entry_novo_nome.pack(pady=5)
                entry_novo_nome.focus_set()

                chk_global = ctk.CTkCheckBox(top_ren, text="Renomear globalmente (em todos os torneios)", font=("Helvetica", 11))
                chk_global.pack(pady=10)

                def salvar_renomeacao():
                    novo_n = entry_novo_nome.get().strip()
                    if not novo_n:
                        messagebox.showwarning("Aviso", "O nome da estação não pode ser vazio.")
                        return
                    sucesso = self.db.renomear_estacao(station_id, novo_n, renomear_global=bool(chk_global.get()))
                    if sucesso:
                        messagebox.showinfo("Sucesso", f"Estação renomeada para '{novo_n}' com sucesso!")
                        top_ren.destroy()
                        refresh_mesas(manter_selecao=True)
                    else:
                        messagebox.showerror("Erro", "Não foi possível renomear a estação.")

                row_b = ctk.CTkFrame(top_ren, fg_color="transparent")
                row_b.pack(pady=10)

                btn_salvar = ctk.CTkButton(row_b, text="💾 Salvar", width=100, fg_color="#10B981", hover_color="#059669", command=salvar_renomeacao)
                btn_salvar.pack(side="left", padx=5)

                btn_canc = ctk.CTkButton(row_b, text="Cancelar", width=80, fg_color="#374151", hover_color="#4B5563", command=top_ren.destroy)
                btn_canc.pack(side="left", padx=5)

            btn_ren = ctk.CTkButton(top_det, text="✏️ Renomear", width=95, height=24, fg_color="#374151", hover_color="#4B5563", text_color="#E5E7EB", font=("Helvetica", 11, "bold"), command=modal_renomear_mesa)
            btn_ren.pack(side="right", padx=5)

            # CARD 1: NÓ VINCULADO
            card_hw = ctk.CTkFrame(detail_mesas_frame, fg_color="#242424", border_width=1, border_color="#374151", corner_radius=8)
            card_hw.pack(fill="x", padx=10, pady=6)

            lbl_hw_title = ctk.CTkLabel(card_hw, text="📡 Nó Repórter Vinculado", font=("Helvetica", 12, "bold"), text_color="#93C5FD")
            lbl_hw_title.pack(anchor="w", padx=12, pady=(10, 4))

            node_mac = det.get("node_mac")
            if node_mac:
                telem = self.node_telemetry.get(node_mac, {})
                now = time.time()
                is_online = (now - telem.get("last_seen", 0)) < 60
                status_conn = "🟢 Online (Conectado)" if is_online else "⚪ Offline (Sem telemetria recente)"
                status_color = "#10B981" if is_online else "#9CA3AF"

                info_node = f"Apelido: {det.get('node_nickname') or 'Sem Apelido'}  |  MAC: {node_mac}"
                lbl_node_info = ctk.CTkLabel(card_hw, text=info_node, font=("Helvetica", 12), text_color="#E5E7EB")
                lbl_node_info.pack(anchor="w", padx=12, pady=2)

                lbl_conn = ctk.CTkLabel(card_hw, text=f"Status: {status_conn}", font=("Helvetica", 11, "bold"), text_color=status_color)
                lbl_conn.pack(anchor="w", padx=12, pady=(0, 8))

                row_hw_btns = ctk.CTkFrame(card_hw, fg_color="transparent")
                row_hw_btns.pack(fill="x", padx=12, pady=(0, 10))

                def trocar_no():
                    modal_selecionar_no_para_mesa(station_id, det["name"])

                btn_swap = ctk.CTkButton(row_hw_btns, text="🔄 Trocar Nó", width=100, height=28, fg_color="#2563EB", hover_color="#1D4ED8", command=trocar_no)
                btn_swap.pack(side="left", padx=(0, 8))

                def testar_led_mesa():
                    self.enviar_downlink_led(node_mac, "GREEN")
                    btn_led.configure(text="🟢 Testando...", fg_color="#10B981")
                    self.root.after(1500, lambda: [
                        btn_led.configure(text="💡 Testar LED", fg_color="#0284C7"),
                        self.enviar_downlink_led(node_mac, "YELLOW")
                    ])

                btn_led = ctk.CTkButton(row_hw_btns, text="💡 Testar LED", width=100, height=28, fg_color="#0284C7", hover_color="#0369A1", command=testar_led_mesa)
                btn_led.pack(side="left", padx=(0, 8))

                def desvincular_no():
                    if messagebox.askyesno("Desvincular Hardware", f"Deseja desvincular o Nó '{node_mac}' da estação '{det['name']}'?\nA estação passará a operar em modo manual."):
                        self.db.desvincular_no_estacao(station_id)
                        messagebox.showinfo("Sucesso", "Nó desvinculado. Estação em modo manual.")
                        refresh_mesas(manter_selecao=True)
                        refresh_nos_tab()

                btn_unbind = ctk.CTkButton(row_hw_btns, text="🔌 Desvincular", width=100, height=28, fg_color="#4B5563", hover_color="#374151", command=desvincular_no)
                btn_unbind.pack(side="left")
            else:
                lbl_no_hw = ctk.CTkLabel(
                    card_hw, 
                    text="⚠️ Nenhum Nó Repórter vinculado a esta estação.\nEla opera normalmente no modo manual/analógico (resultados lançados pelo organizador).", 
                    font=("Helvetica", 11),
                    text_color="#9CA3AF",
                    justify="left"
                )
                lbl_no_hw.pack(anchor="w", padx=12, pady=(2, 8))

                row_vinc = ctk.CTkFrame(card_hw, fg_color="transparent")
                row_vinc.pack(fill="x", padx=12, pady=(0, 10))

                btn_vinc = ctk.CTkButton(row_vinc, text="📡 Vincular Nó do Inventário", width=180, height=28, fg_color="#10B981", hover_color="#059669", command=lambda: modal_selecionar_no_para_mesa(station_id, det["name"]))
                btn_vinc.pack(side="left", padx=(0, 8))

            # CARD 2: PARTIDA ATIVA
            card_match = ctk.CTkFrame(detail_mesas_frame, fg_color="#242424", border_width=1, border_color="#374151", corner_radius=8)
            card_match.pack(fill="x", padx=10, pady=6)

            lbl_match_title = ctk.CTkLabel(card_match, text="⚔️ Partida Ativa na Estação", font=("Helvetica", 12, "bold"), text_color="#FCD34D")
            lbl_match_title.pack(anchor="w", padx=12, pady=(10, 4))

            partida = det.get("partida_ativa")
            if partida:
                p1 = partida.get("p1_nick") or partida.get("p1_real") or "TBD"
                p2 = partida.get("p2_nick") or partida.get("p2_real") or "TBD"
                chk1 = "✅ Confirmado" if partida.get("player1_checked_in") else "⏳ Pendente"
                chk2 = "✅ Confirmado" if partida.get("player2_checked_in") else "⏳ Pendente"
                chk1_col = "#10B981" if partida.get("player1_checked_in") else "#F59E0B"
                chk2_col = "#10B981" if partida.get("player2_checked_in") else "#F59E0B"

                lbl_m_info = ctk.CTkLabel(card_match, text=f"Confronto #{partida['id']} (Rodada {partida.get('round_number', 1)}) — Status: {partida.get('status')}", font=("Helvetica", 11, "bold"), text_color="#E5E7EB")
                lbl_m_info.pack(anchor="w", padx=12, pady=2)

                lbl_p1 = ctk.CTkLabel(card_match, text=f"• Jogador 1: {p1} | Check-in: {chk1}", font=("Helvetica", 11), text_color=chk1_col)
                lbl_p1.pack(anchor="w", padx=18, pady=1)

                lbl_p2 = ctk.CTkLabel(card_match, text=f"• Jogador 2: {p2} | Check-in: {chk2}", font=("Helvetica", 11), text_color=chk2_col)
                lbl_p2.pack(anchor="w", padx=18, pady=1)

                if partida.get("score_conflict"):
                    lbl_sc = ctk.CTkLabel(
                        card_match, 
                        text=f"🚨 DIVERGÊNCIA DE PLACAR REPORTADA! (Chame os competidores para arbitrar)",
                        font=("Helvetica", 11, "bold"),
                        text_color=THEME_TRYHARD["rage_red"]
                    )
                    lbl_sc.pack(anchor="w", padx=12, pady=(4, 8))
                elif partida.get("pending_score1") is not None:
                    lbl_sc = ctk.CTkLabel(
                        card_match, 
                        text=f"⚠️ Placar Reportado: {partida['pending_score1']} x {partida['pending_score2']} (Aguardando chancela física RFID na mesa)",
                        font=("Helvetica", 11, "bold"),
                        text_color="#F59E0B"
                    )
                    lbl_sc.pack(anchor="w", padx=12, pady=(4, 8))
                else:
                    lbl_sc = ctk.CTkLabel(card_match, text=f"Placar Atual: {partida.get('score1', 0)} x {partida.get('score2', 0)}", font=("Helvetica", 11), text_color="#9CA3AF")
                    lbl_sc.pack(anchor="w", padx=12, pady=(2, 8))
            else:
                lbl_free = ctk.CTkLabel(card_match, text="🟢 Estação livre. Nenhuma partida em andamento no momento.", font=("Helvetica", 11), text_color="#10B981")
                lbl_free.pack(anchor="w", padx=12, pady=(4, 10))

            # CARD 3: AÇÕES DA ESTAÇÃO
            btn_del_mesa = ctk.CTkButton(
                detail_mesas_frame,
                text="❌ Excluir Estação",
                fg_color="#881337",
                hover_color="#4C0519",
                height=30,
                command=lambda: excluir_mesa_acao(station_id, det["name"])
            )
            btn_del_mesa.pack(anchor="w", padx=10, pady=(12, 10))

        def excluir_mesa_acao(station_id, station_name):
            if not messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir a estação '{station_name}'?\nPartidas associadas ficarão sem estação alocada."):
                return
            
            expurgar = messagebox.askyesno(
                "Expurgar Nome Definitivamente?",
                f"Deseja remover o nome '{station_name}' também do histórico e de templates futuros?\n\n(Recomendado 'Sim' se for uma mesa errada ou temporária, para não reaparecer no assistente de novos torneios)."
            )
            self.db.excluir_estacao(station_id, expurgar_global=expurgar)
            selected_station_id[0] = None
            messagebox.showinfo("Sucesso", f"Estação '{station_name}' removida com sucesso!")
            refresh_mesas(manter_selecao=False)
            refresh_nos_tab()

        def modal_selecionar_no_para_mesa(station_id, station_name):
            top_sel = ctk.CTkToplevel(top)
            top_sel.title("Vincular Nó Repórter à Estação")
            top_sel.geometry("460x280")
            top_sel.transient(top)
            top_sel.lift()
            top_sel.focus_set()

            lbl_i = ctk.CTkLabel(top_sel, text=f"Selecionar Nó para: {station_name}", font=("Helvetica", 13, "bold"))
            lbl_i.pack(pady=12)

            nos = self.db.listar_nos_inventario()
            opcoes_map = {}
            for n in nos:
                mac = n["mac_address"]
                nick = n["nickname"] or mac
                st_atual = n["station_name"]
                desc = f"{nick} ({mac})" + (f" [Em: {st_atual}]" if st_atual else " [Livre]")
                opcoes_map[desc] = mac

            if not opcoes_map:
                lbl_sem = ctk.CTkLabel(top_sel, text="Nenhum nó repórter cadastrado no inventário.\nFaça a varredura na aba '📡 Nós Repórteres'.", text_color="#F59E0B")
                lbl_sem.pack(pady=15)
                return

            combo_nos = ctk.CTkComboBox(top_sel, values=list(opcoes_map.keys()), width=400)
            combo_nos.set(list(opcoes_map.keys())[0])
            combo_nos.pack(pady=10)

            def confirmar_vinculo():
                sel_txt = combo_nos.get()
                mac_sel = opcoes_map.get(sel_txt)
                if mac_sel:
                    self.db.vincular_no_estacao(station_id, mac_sel)
                    messagebox.showinfo("Sucesso", f"Nó vinculado à estação '{station_name}' com sucesso!")
                    top_sel.destroy()
                    refresh_mesas(manter_selecao=True)
                    refresh_nos_tab()

            btn_cf = ctk.CTkButton(top_sel, text="💾 Confirmar Vínculo", fg_color="#10B981", hover_color="#059669", command=confirmar_vinculo)
            btn_cf.pack(pady=15)

        def modal_nova_mesa():
            top_add = ctk.CTkToplevel(top)
            top_add.title("Cadastrar Nova Estação")
            top_add.geometry("450x290")
            top_add.transient(top)
            top_add.lift()
            top_add.focus_set()

            lbl_a = ctk.CTkLabel(top_add, text="Cadastrar Nova Estação de Jogo", font=("Helvetica", 13, "bold"))
            lbl_a.pack(pady=12)

            cursor = self.db.conn.cursor()
            cur_ev = getattr(self, "evento_selecionado_id", None)
            if cur_ev:
                cursor.execute("SELECT COUNT(*) as cnt FROM stations WHERE event_id = ?", (cur_ev,))
            else:
                cursor.execute("SELECT COUNT(*) as cnt FROM stations")
            cnt = cursor.fetchone()["cnt"] + 1

            e_name = ctk.CTkEntry(top_add, placeholder_text=f"Nome da Estação (ex: Mesa {cnt})", width=350)
            e_name.insert(0, f"Mesa {cnt}")
            e_name.pack(pady=6)

            lbl_opt = ctk.CTkLabel(top_add, text="Associar Nó Repórter (Opcional):", font=("Helvetica", 11), text_color="#9CA3AF")
            lbl_opt.pack(anchor="w", padx=50, pady=(6, 2))

            nos_livres = [n for n in self.db.listar_nos_inventario() if not n["station_id"]]
            no_opts = {"⚠️ Sem Nó (Modo Manual)": None}
            for n in nos_livres:
                desc = f"{n['nickname'] or n['mac_address']} ({n['mac_address']})"
                no_opts[desc] = n["mac_address"]

            combo_no_init = ctk.CTkComboBox(top_add, values=list(no_opts.keys()), width=350)
            combo_no_init.set("⚠️ Sem Nó (Modo Manual)")
            combo_no_init.pack(pady=4)

            def salvar_nova_m():
                nome = e_name.get().strip()
                if not nome:
                    messagebox.showerror("Erro", "Nome da estação é obrigatório.")
                    return
                sel_no_desc = combo_no_init.get()
                mac_escolhido = no_opts.get(sel_no_desc)
                new_id = self.db.cadastrar_estacao(cur_ev, nome, mac_escolhido)
                messagebox.showinfo("Sucesso", f"Estação '{nome}' cadastrada com sucesso!")
                top_add.destroy()
                selected_station_id[0] = new_id
                refresh_mesas(manter_selecao=True)
                refresh_nos_tab()

            btn_save = ctk.CTkButton(top_add, text="💾 Salvar Estação", fg_color="#10B981", hover_color="#059669", command=salvar_nova_m, width=200)
            btn_save.pack(pady=15)

        btn_add_mesa = ctk.CTkButton(top_mesas_bar, text="+ Nova Estação", fg_color="#10B981", hover_color="#059669", font=("Helvetica", 11, "bold"), command=modal_nova_mesa)
        btn_add_mesa.pack(side="right", padx=5)

        # =====================================================================
        # ABA 2: NÓS REPÓRTERES & VARREDURA
        # =====================================================================
        action_bar_tab2 = ctk.CTkFrame(tab_nos, fg_color="#1E1E1E", border_width=1, border_color="#333333")
        action_bar_tab2.pack(fill="x", padx=10, pady=(5, 10))

        lbl_status_scan = ctk.CTkLabel(action_bar_tab2, text="Pronto para varredura. Clique em 'Iniciar Varredura de Nós'.", font=("Helvetica", 11, "bold"), text_color="#38BDF8")
        lbl_status_scan.pack(side="left", padx=15, pady=10)

        def disparar_varredura_integrada():
            btn_scan_nos.configure(state="disabled", text="🔍 Varrendo Sala...")
            lbl_status_scan.configure(text="📡 Transmitindo pulsos broadcast ESP-NOW... Aguardando respostas dos nós...", text_color="#F59E0B")

            # O nó conectado diretamente na USB do PC é sempre ativo na bancada
            coord_mac = getattr(self.driver_serial, "coordinator_mac", None) or getattr(self, "coordenador_usb_mac", None)
            if coord_mac:
                if not hasattr(self, "nos_descobertos_recentes"):
                    self.nos_descobertos_recentes = {}
                self.nos_descobertos_recentes[coord_mac] = time.time()
                try:
                    cursor = self.db.conn.cursor()
                    cursor.execute("SELECT mac_address FROM nodes WHERE mac_address = ?", (coord_mac,))
                    if not cursor.fetchone():
                        self.db.cadastrar_ou_atualizar_no(coord_mac, f"Nó Coordenador USB ({coord_mac[-5:]})", "REPORTER")
                except Exception:
                    pass

            def _thread_scan():
                self.driver_serial.descobrir_nos()
                time.sleep(1.0)
                self.driver_serial.descobrir_nos()
                time.sleep(0.8)
                self.root.after(0, _scan_finalizado)

            def _scan_finalizado():
                btn_scan_nos.configure(state="normal", text="📡 Iniciar Varredura de Nós")
                recentes = getattr(self, "nos_descobertos_recentes", {})
                agora = time.time()
                qtd_recentes = sum(1 for ts in recentes.values() if (agora - ts) < 45)
                lbl_status_scan.configure(text=f"✅ Varredura concluída! {qtd_recentes} nó(s) ativos detectados na bancada.", text_color="#10B981")
                refresh_nos_tab(incremental=True)
                refresh_mesas(manter_selecao=True)

            threading.Thread(target=_thread_scan, daemon=True).start()

        btn_scan_nos = ctk.CTkButton(
            action_bar_tab2, 
            text="📡 Iniciar Varredura de Nós", 
            fg_color=THEME_TRYHARD["primary"], 
            hover_color=THEME_TRYHARD["primary_hover"], 
            text_color=THEME_TRYHARD["primary_text"], 
            font=("Helvetica", 12, "bold"), 
            command=disparar_varredura_integrada
        )
        btn_scan_nos.pack(side="right", padx=10, pady=10)

        scroll_nos_tab = ctk.CTkScrollableFrame(tab_nos, label_text="Nós Identificados & Vínculo com Estações")
        scroll_nos_tab.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        nos_ui_rows = {}
        lbl_vazio_ref = [None]

        def refresh_nos_tab(incremental=False):
            nos = self.db.listar_nos_inventario()
            recentes = getattr(self, "nos_descobertos_recentes", {})

            cursor = self.db.conn.cursor()
            cur_ev = getattr(self, "evento_selecionado_id", None)
            if cur_ev:
                cursor.execute("SELECT id, name FROM stations WHERE event_id = ? OR event_id IS NULL ORDER BY id ASC", (cur_ev,))
            else:
                cursor.execute("SELECT id, name FROM stations ORDER BY id ASC")
            estacoes = cursor.fetchall()
            st_map = {"[Livre / Sem Mesa]": None}
            for s in estacoes:
                st_map[f"🪑 {s['name']} (ID #{s['id']})"] = s["id"]
            st_opcoes = list(st_map.keys())

            if not nos:
                for mac, rdata in list(nos_ui_rows.items()):
                    rdata["row"].destroy()
                nos_ui_rows.clear()
                if not lbl_vazio_ref[0] or not lbl_vazio_ref[0].winfo_exists():
                    lbl_vazio_ref[0] = ctk.CTkLabel(
                        scroll_nos_tab, 
                        text="Nenhum nó físico cadastrado ainda.\nLigue os nós repórteres na alimentação e clique em 'Iniciar Varredura de Nós' acima.", 
                        font=("Helvetica", 12), 
                        text_color="#9CA3AF"
                    )
                    lbl_vazio_ref[0].pack(pady=30)
                return

            if lbl_vazio_ref[0] and lbl_vazio_ref[0].winfo_exists():
                lbl_vazio_ref[0].destroy()
                lbl_vazio_ref[0] = None

            agora = time.time()
            macs_no_banco = {n["mac_address"]: n for n in nos}

            # Remove nós excluídos
            for mac in list(nos_ui_rows.keys()):
                if mac not in macs_no_banco:
                    try:
                        nos_ui_rows[mac]["row"].destroy()
                    except Exception:
                        pass
                    del nos_ui_rows[mac]

            # Atualiza nós existentes de forma cirúrgica ou anexa novos nós
            for n in nos:
                mac = n["mac_address"]
                nick = n["nickname"] or f"Nó {mac[-5:]}"
                st_id_atual = n["station_id"]

                foi_visto_recente = (agora - recentes.get(mac, 0)) < 45
                status_icon = "🟢" if foi_visto_recente else "🔵"
                status_txt = "Detectado Agora" if foi_visto_recente else "Cadastrado"
                status_color = "#10B981" if foi_visto_recente else "#60A5FA"

                if mac in nos_ui_rows:
                    rdata = nos_ui_rows[mac]
                    try:
                        rdata["lbl_st"].configure(text=f"{status_icon} {status_txt}", text_color=status_color)
                        rdata["cb"].configure(values=st_opcoes)
                        if not incremental:
                            focused = False
                            try:
                                focused = (scroll_nos_tab.focus_get() == rdata["entry"])
                            except Exception:
                                pass
                            if not focused and rdata["entry"].get() != nick:
                                rdata["entry"].delete(0, "end")
                                rdata["entry"].insert(0, nick)
                    except Exception:
                        pass
                else:
                    row = ctk.CTkFrame(scroll_nos_tab, fg_color="#242424", border_width=1, border_color="#374151", corner_radius=6)
                    row.pack(fill="x", padx=5, pady=4)

                    lbl_st_ind = ctk.CTkLabel(row, text=f"{status_icon} {status_txt}", font=("Helvetica", 10, "bold"), text_color=status_color, width=115)
                    lbl_st_ind.pack(side="left", padx=8, pady=8)

                    e_nick = ctk.CTkEntry(row, width=150, height=28)
                    e_nick.insert(0, nick)
                    e_nick.pack(side="left", padx=5, pady=8)

                    lbl_mac = ctk.CTkLabel(row, text=mac, font=("Consolas", 11), text_color="#9CA3AF", width=145)
                    lbl_mac.pack(side="left", padx=5, pady=8)

                    cb_st = ctk.CTkComboBox(row, values=st_opcoes, width=180, height=28)
                    cur_label = "[Livre / Sem Mesa]"
                    if st_id_atual:
                        for k, v in st_map.items():
                            if v == st_id_atual:
                                cur_label = k
                                break
                    cb_st.set(cur_label)
                    cb_st.pack(side="left", padx=5, pady=8)

                    def salvar_alteracoes(mac_addr=mac, entry_widget=e_nick, combo_widget=cb_st):
                        novo_nick = entry_widget.get().strip()
                        nova_st_label = combo_widget.get()
                        nova_st_id = st_map.get(nova_st_label)

                        self.db.cadastrar_ou_atualizar_no(mac_addr, novo_nick)
                        if nova_st_id is not None:
                            self.db.vincular_no_estacao(nova_st_id, mac_addr)
                        else:
                            cursor_del = self.db.conn.cursor()
                            cursor_del.execute("UPDATE stations SET node_mac = NULL WHERE node_mac = ?", (mac_addr,))
                            self.db.conn.commit()

                        messagebox.showinfo("Sucesso", f"Nó [{mac_addr}] atualizado com sucesso!")
                        refresh_nos_tab(incremental=False)
                        refresh_mesas(manter_selecao=True)

                    btn_salvar = ctk.CTkButton(row, text="💾 Salvar", width=65, height=28, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], command=salvar_alteracoes)
                    btn_salvar.pack(side="left", padx=4, pady=8)

                    def testar_led_no(mac_addr=mac, b_widget=None):
                        self.enviar_downlink_led(mac_addr, "GREEN")
                        if b_widget:
                            b_widget.configure(text="🟢 OK!", fg_color="#10B981")
                            self.root.after(1500, lambda: [
                                b_widget.configure(text="💡 LED", fg_color="#0284C7"),
                                self.enviar_downlink_led(mac_addr, "YELLOW")
                            ])

                    btn_test = ctk.CTkButton(row, text="💡 LED", width=50, height=28, fg_color="#0284C7", hover_color="#0369A1")
                    btn_test.configure(command=lambda m=mac, b=btn_test: testar_led_no(m, b))
                    btn_test.pack(side="left", padx=4, pady=8)

                    def excluir_no(mac_addr=mac):
                        if messagebox.askyesno("Remover Nó", f"Deseja remover o nó [{mac_addr}] do inventário?"):
                            self.db.remover_no(mac_addr)
                            refresh_nos_tab(incremental=False)
                            refresh_mesas(manter_selecao=True)

                    btn_del = ctk.CTkButton(row, text="🗑️", width=32, height=28, fg_color="#881337", hover_color="#4C0519", command=excluir_no)
                    btn_del.pack(side="left", padx=4, pady=8)

                    nos_ui_rows[mac] = {
                        "row": row,
                        "lbl_st": lbl_st_ind,
                        "entry": e_nick,
                        "cb": cb_st
                    }

        def on_novo_no_descoberto(mac):
            self.root.after(0, lambda: (refresh_nos_tab(incremental=True), refresh_mesas(manter_selecao=True)))

        self.active_discover_callback = on_novo_no_descoberto

        def fechar():
            self.active_discover_callback = None
            top.destroy()
            if on_close_callback and callable(on_close_callback):
                on_close_callback()

        top.protocol("WM_DELETE_WINDOW", fechar)

        # Seleciona aba inicial conforme argumento
        if str(aba_inicial).lower() in ("nos", "scan", "broadcast"):
            tabview.set("📡 Nós Repórteres & Varredura")
        else:
            tabview.set("🪑 Estações")

        # Inicializa ambas as abas
        refresh_mesas(manter_selecao=False)
        refresh_nos_tab()

    def modal_mapear_nos_reporteres(self, on_close_callback=None):
        """Atalho direto para a aba de Varredura e Nós na janela unificada."""
        self.modal_gerenciar_mesas_torneio(aba_inicial="nos", on_close_callback=on_close_callback)

    def enviar_downlink_led(self, mac_destino, cor="GREEN"):
        """
        Envia downlink serial/ESP-NOW para acionar a cor dos LEDs de um nó específico ou broadcast.
        Cores suportadas pelo hardware protótipo: 'YELLOW' (Convocada/Aguardando), 'GREEN' (Ativo/Confirmado), 'RED' (Alerta), 'OFF'.
        (O canal Azul não é fisicamente roteado no hardware protótipo).
        """
        alvo = mac_destino if mac_destino and str(mac_destino).strip() else "BROADCAST"
        if hasattr(self, "driver_serial") and self.driver_serial:
            self.driver_serial.enviar_comando_no(alvo, f"LED;{cor}")
            print(f"[GUI] 💡 Downlink LED enviado para [{alvo}] -> Cor: {cor}")
            self.atualizar_telemetria_no(alvo, "LED_CMD", f"Cor: {cor}")

    # -------------------------------------------------------------------------
    # CALLBACK UNIFICADO DE TELEMETRIA E ESCUTA SERIAL
    # -------------------------------------------------------------------------
    def on_mensagem_serial_recebida(self, *args, **kwargs):
        """
        Trata mensagens de rádio/serial recebidas e atualiza a telemetria, a GUI e o motor de torneio.
        Aceita tanto uma string bruta ('RFID;tag;mac' ou 'SCORE;mac;s1;s2') quanto parâmetros decompostos.
        """
        if not args:
            return

        timestamp = time.strftime("%H:%M:%S")

        if len(args) == 1 and isinstance(args[0], str):
            raw_msg = args[0].strip()
            partes = [p.strip() for p in raw_msg.split(";")]
            tipo = partes[0].upper() if partes else ""
            conteudo = partes[1:]
        else:
            tipo = str(args[0]).upper()
            conteudo = [str(a) for a in args[1:]]
            raw_msg = f"{tipo};" + ";".join(conteudo)

        log_line = f"[{timestamp}] [{tipo}] " + " | ".join(conteudo)
        print(f"[GUI SERIAL] {log_line}")

        # Atualização thread-safe do terminal de telemetria
        tag_tipo = "system"
        if tipo == "RFID":
            tag_tipo = "rfid"
        elif tipo == "SCORE":
            tag_tipo = "score"
        elif tipo in ("DOWNLINK", "OK", "ACK", "STATUS", "DISCOVERED", "NODE_HERE"):
            tag_tipo = "downlink"
        elif "ERR" in tipo or "WARN" in tipo:
            tag_tipo = "alert"

        def _log_ui(l=log_line, t=tag_tipo):
            try:
                if hasattr(self, "txt_telemetria") and self.txt_telemetria and getattr(self, "telemetria_ativa", True):
                    self.txt_telemetria.configure(state="normal")
                    self.txt_telemetria.insert("end", l + "\n", t)
                    self.txt_telemetria.see("end")
                    self.txt_telemetria.configure(state="disabled")
            except Exception:
                pass
        self.root.after(0, _log_ui)

        # 1. Tratamento de Conexão Serial
        if tipo == "STATUS" and len(conteudo) >= 2:
            st_action, st_port = conteudo[0].upper(), conteudo[1]
            if st_action == "CONNECTED":
                self.root.after(0, lambda: self.lbl_status_com.configure(text=f"COM: {st_port} (OK)", text_color=THEME_TRYHARD["status_success"]))
            elif st_action == "DISCONNECTED":
                self.root.after(0, lambda: self.lbl_status_com.configure(text="COM: DESCONECTADA", text_color=THEME_TRYHARD["rage_red"]))
            return

        # 2. Identificação do Adaptador Coordenador USB
        if tipo == "COORDINATOR_MAC" and len(conteudo) >= 1:
            coord_mac = conteudo[0].strip().upper()
            self.coordenador_usb_mac = coord_mac
            if not hasattr(self, "nos_descobertos_recentes"):
                self.nos_descobertos_recentes = {}
            self.nos_descobertos_recentes[coord_mac] = time.time()
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT mac_address FROM nodes WHERE mac_address = ?", (coord_mac,))
                if not cursor.fetchone():
                    self.db.cadastrar_ou_atualizar_no(coord_mac, f"Nó Coordenador USB ({coord_mac[-5:]})", "REPORTER")
            except Exception:
                pass
            self.atualizar_telemetria_no(coord_mac, "COORDINATOR", "Adaptador Coordenador USB Online")
            if getattr(self, "active_discover_callback", None) and callable(self.active_discover_callback):
                cb = self.active_discover_callback
                self.root.after(0, lambda m=coord_mac: cb(m))
            return

        if "MAC:" in raw_msg:
            try:
                part_mac = raw_msg.split("MAC:")[-1].strip().upper()
                if len(part_mac) >= 17:
                    coord_mac = part_mac[:17]
                    self.coordenador_usb_mac = coord_mac
                    if not hasattr(self, "nos_descobertos_recentes"):
                        self.nos_descobertos_recentes = {}
                    self.nos_descobertos_recentes[coord_mac] = time.time()
                    cursor = self.db.conn.cursor()
                    cursor.execute("SELECT mac_address FROM nodes WHERE mac_address = ?", (coord_mac,))
                    if not cursor.fetchone():
                        self.db.cadastrar_ou_atualizar_no(coord_mac, f"Nó Coordenador USB ({coord_mac[-5:]})", "REPORTER")
                    self.atualizar_telemetria_no(coord_mac, "COORDINATOR", "Adaptador Coordenador USB Online")
            except Exception:
                pass

        # 3. Descoberta de Nós Repórteres (Broadcast / Scan)
        if tipo == "DISCOVER_START":
            c_mac = getattr(self.driver_serial, "coordinator_mac", None) or getattr(self, "coordenador_usb_mac", None)
            if c_mac:
                self.atualizar_telemetria_no(c_mac, "SCAN", "Varredura Broadcast Disparada...")
            return

        # Extração de Rota Mesh e Saltos (HOPS/SALTOS e VIA)
        saltos_info = 1
        via_info = "DIRETO"
        for p in conteudo:
            p_up = p.upper()
            if p_up.startswith("SALTOS:") or p_up.startswith("HOPS:"):
                try:
                    saltos_info = int(p.split(":", 1)[1].strip())
                except Exception:
                    pass
            elif p_up.startswith("VIA:"):
                via_info = p.split(":", 1)[1].strip().upper()

        if "BARREIRA_DROP" in tipo:
            _log_ui(f"[{timestamp}] ⛔ [BARREIRA HARDWARE] Pacote direto de {conteudo[0]} descartado no Coordenador!", "alert")
            return
        elif "BARREIRA_PASS" in tipo or "[BARREIRA]" in tipo:
            _log_ui(f"[{timestamp}] 🛡️ [BARREIRA HARDWARE] {' | '.join(conteudo)}", "downlink")
            return

        if tipo in ("DISCOVERED", "NODE_HERE") and len(conteudo) >= 1:
            mac_no = conteudo[0].strip().upper()
            if not hasattr(self, "nos_descobertos_recentes"):
                self.nos_descobertos_recentes = {}
            self.nos_descobertos_recentes[mac_no] = time.time()

            try:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT mac_address FROM nodes WHERE mac_address = ?", (mac_no,))
                if not cursor.fetchone():
                    self.db.cadastrar_ou_atualizar_no(mac_no, f"Nó Repórter ({mac_no[-5:]})", "REPORTER")
            except Exception as ex_db:
                print(f"[GUI ERROR] Erro ao cadastrar nó descoberto: {ex_db}")

            self.atualizar_telemetria_no(mac_no, "DISCOVERED", f"Nó Ativo ({saltos_info} salto(s) | Via: {via_info})")
            self.ultima_rota_mesh = {
                "origem": mac_no,
                "via": via_info,
                "saltos": saltos_info,
                "timestamp": timestamp,
                "tipo": tipo
            }
            self._atualizar_badge_rota_mesh_ui(mac_no, via_info, saltos_info)

            if getattr(self, "active_discover_callback", None) and callable(self.active_discover_callback):
                try:
                    cb = self.active_discover_callback
                    self.root.after(0, lambda m=mac_no: cb(m))
                except Exception as ex:
                    print(f"[GUI ERROR] Falha no callback de descoberta: {ex}")
            return

        if tipo == "RFID" and len(conteudo) >= 2:
            tag_uid = conteudo[0].strip().upper()
            node_mac_arg = conteudo[1].strip().upper()
            origem = conteudo[2].strip().upper() if len(conteudo) >= 3 else ""
            coord_mac = getattr(self.driver_serial, "coordinator_mac", None) or self.coordenador_usb_mac
            if origem == "LOCAL":
                is_coordinator = True
                via_info = "LOCAL"
                saltos_info = 0
            elif origem == "REMOTE":
                is_coordinator = False
            else:
                is_coordinator = bool(coord_mac and node_mac_arg == coord_mac.upper())
                if is_coordinator:
                    via_info = "LOCAL"
                    saltos_info = 0

            self.ultima_tag_lida = tag_uid
            self.ultimo_no_mac = node_mac_arg
            self.ultimo_timestamp_rfid = timestamp
            if not hasattr(self, "nos_descobertos_recentes"):
                self.nos_descobertos_recentes = {}
            self.nos_descobertos_recentes[node_mac_arg] = time.time()

            # Auto-registro do nó no inventário
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT mac_address FROM nodes WHERE mac_address = ?", (node_mac_arg,))
                if not cursor.fetchone():
                    self.db.cadastrar_ou_atualizar_no(node_mac_arg, f"Nó Repórter ({node_mac_arg[-5:]})", "REPORTER")
            except Exception:
                pass

            self.atualizar_telemetria_no(node_mac_arg, "RFID", f"Tag: {tag_uid} | {saltos_info} salto(s) | Via: {via_info}")
            self.ultima_rota_mesh = {
                "origem": node_mac_arg,
                "via": via_info,
                "saltos": saltos_info,
                "timestamp": timestamp,
                "tipo": "RFID"
            }
            self._atualizar_badge_rota_mesh_ui(node_mac_arg, via_info, saltos_info)

            # Filtro da Barreira Virtual de Rádio
            if getattr(self, "barreira_mesh_ativa", False):
                bloqueado_mac = getattr(self, "barreira_mac_bloqueado", None)
                is_bloqueado = (bloqueado_mac is None or node_mac_arg == bloqueado_mac.upper())
                if via_info in ("DIRETO", "LOCAL") and is_bloqueado:
                    msg_b = f"[{timestamp}] ⛔ [BARREIRA ATIVA] Tag {tag_uid} do Nó {node_mac_arg[-5:]} bloqueada na rota direta! Aguardando salto repetidor..."
                    _log_ui(msg_b, "alert")
                    print(f"[BARREIRA] {msg_b}")
                    return # BLOQUEADO!
                elif via_info not in ("DIRETO", "LOCAL") and is_bloqueado:
                    msg_b = f"[{timestamp}] 🛡️ [BARREIRA SUPERADA!] Tag {tag_uid} do Nó {node_mac_arg[-5:]} aceita via Repetidor {via_info[-5:]} ({saltos_info} saltos)!"
                    _log_ui(msg_b, "downlink")
                    print(f"[BARREIRA] {msg_b}")

            if via_info not in ("DIRETO", "LOCAL") and not getattr(self, "barreira_mesh_ativa", False):
                _log_ui(f"[{timestamp}] 🔀 [ROTA MESH] Nó {node_mac_arg[-5:]} ➔ Repetidor {via_info[-5:]} ➔ Coordenador USB ({saltos_info} saltos)", "downlink")


            self.root.after(0, lambda: self._on_rfid_recebido_thread_safe(tag_uid, node_mac_arg, is_coordinator))
            return

        elif tipo == "SCORE" and len(conteudo) >= 3:
            try:
                node_mac_arg, s1, s2 = conteudo[0].strip().upper(), int(conteudo[1]), int(conteudo[2])
                if not hasattr(self, "nos_descobertos_recentes"):
                    self.nos_descobertos_recentes = {}
                self.nos_descobertos_recentes[node_mac_arg] = time.time()

                self.ultima_rota_mesh = {
                    "origem": node_mac_arg,
                    "via": via_info,
                    "saltos": saltos_info,
                    "timestamp": timestamp,
                    "tipo": "SCORE"
                }
                self._atualizar_badge_rota_mesh_ui(node_mac_arg, via_info, saltos_info)

                # Filtro da Barreira Virtual de Rádio
                if getattr(self, "barreira_mesh_ativa", False):
                    bloqueado_mac = getattr(self, "barreira_mac_bloqueado", None)
                    is_bloqueado = (bloqueado_mac is None or node_mac_arg == bloqueado_mac.upper())
                    if via_info in ("DIRETO", "LOCAL") and is_bloqueado:
                        msg_b = f"[{timestamp}] ⛔ [BARREIRA ATIVA] Placar do Nó {node_mac_arg[-5:]} descartado na rota direta! Aguardando salto repetidor..."
                        _log_ui(msg_b, "alert")
                        print(f"[BARREIRA] {msg_b}")
                        return
                    elif via_info not in ("DIRETO", "LOCAL") and is_bloqueado:
                        msg_b = f"[{timestamp}] 🛡️ [BARREIRA SUPERADA!] Placar do Nó {node_mac_arg[-5:]} aceito via Repetidor {via_info[-5:]} ({saltos_info} saltos)!"
                        _log_ui(msg_b, "downlink")
                        print(f"[BARREIRA] {msg_b}")

                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT m.id FROM matches m
                    JOIN stations s ON m.station_id = s.id
                    WHERE s.node_mac = ? AND m.status IN ('READY', 'PLAYING')
                """, (node_mac_arg,))
                m_row = cursor.fetchone()
                if m_row:
                    self.motor.iniciar_reporte_placar(m_row["id"], s1, s2)
            except Exception as ex:
                print(f"[GUI ERROR] Falha ao processar SCORE: {ex}")

    def _atualizar_badge_rota_mesh_ui(self, origem, via, saltos):
        """Atualiza o badge de rota Mesh na interface caso o widget esteja visível."""
        try:
            if hasattr(self, "lbl_rota_mesh_status") and self.lbl_rota_mesh_status and self.lbl_rota_mesh_status.winfo_exists():
                if via in ("DIRETO", "LOCAL"):
                    txt = f"⚡ DIRETO (1 salto): Nó {origem[-5:]} ➔ Coordenador USB"
                    cor = "#38BDF8"
                else:
                    txt = f"🔀 MULTI-HOP (2 saltos): Nó {origem[-5:]} ➔ Repetidor {via[-5:]} ➔ Coordenador"
                    cor = "#A855F7"
                self.root.after(0, lambda: self.lbl_rota_mesh_status.configure(text=txt, text_color=cor))
        except Exception:
            pass

    def _on_rfid_recebido_thread_safe(self, tag_uid, node_mac, is_coordinator=False):
        """Processa a leitura de uma tag RFID diretamente na thread principal do Tkinter."""
        # 1. Feedback auditivo suave
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass

        # 2. Se houver formulário ativo aguardando leitura de tag (Cadastro de Atleta ou Edição):
        cb = getattr(self, "active_rfid_capture_callback", None)
        if cb and callable(cb):
            try:
                cb(tag_uid, node_mac)
            except Exception as ex:
                print(f"[GUI ERROR] Falha no callback de captura RFID: {ex}")
            return

        # 3. Atualizar Banner do Scanner em Módulo 2
        if hasattr(self, "lbl_scanner_tag") and self.lbl_scanner_tag:
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT p.id, p.nickname, p.real_name 
                    FROM rfid_tags r 
                    JOIN players p ON r.player_id = p.id 
                    WHERE UPPER(r.tag_uid) = ?
                """, (tag_uid,))
                owner = cursor.fetchone()
                if owner:
                    txt = f"Última Tag: {tag_uid} (Nó {node_mac[-5:]}) • Atleta: #{owner['id']} {owner['nickname']}"
                    cor = THEME_TRYHARD["status_success"]
                else:
                    txt = f"Última Tag: {tag_uid} (Nó {node_mac[-5:]}) • ⚠️ TAG NOVA / NÃO VINCULADA"
                    cor = THEME_TRYHARD["status_waiting"]
                self.lbl_scanner_tag.configure(text=txt, text_color=cor)
            except Exception as ex:
                print(f"[GUI SCANNER] {ex}")

        # 4. Tratar lógica ciberfísica de torneio nas mesas (Check-in PoPL ou Chancela de Placar na mesa designada)
        try:
            sucesso, msg = self.motor.confirmar_placar_rfid(tag_uid, node_mac)
            if not sucesso:
                sucesso_chk, msg_chk = self.motor.registrar_checkin_rfid(tag_uid, node_mac)
                if sucesso_chk:
                    self.atualizar_view_brackets()
                    print(f"[GUI RFID CHECKIN] {msg_chk}")
                else:
                    print(f"[GUI RFID] Placar: {msg} | Check-in: {msg_chk}")
            else:
                self.atualizar_view_brackets()
                print(f"[GUI RFID PLACAR CONFIRMADO] {msg}")
        except Exception as ex:
            print(f"[GUI MOTOR RFID ERROR] {ex}")

    def toggle_servidor_web(self):
        """Liga ou desliga o servidor Flask local em uma thread paralela."""
        if self.servidor_rodando:
            self.servidor_rodando = False
            if HAS_CTK:
                self.lbl_status_server.configure(text="Servidor: OFF", text_color=THEME_TRYHARD["rage_red"])
                self.btn_toggle_server.configure(text="Ligar Servidor Web", fg_color=THEME_TRYHARD["border"])
            messagebox.showinfo("Servidor Web", "Servidor Web local foi desativado.")
        else:
            self.servidor_rodando = True

            def run_flask():
                try:
                    import web.app as web_module
                    web_module.driver = self.driver_serial
                    web_module.app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
                except Exception as ex:
                    print(f"[FLASK SERVER ERROR] {ex}")

            t = threading.Thread(target=run_flask, daemon=True)
            t.start()

            if HAS_CTK:
                self.lbl_status_server.configure(text="Servidor: ON (5000)", text_color=THEME_TRYHARD["status_success"])
                self.btn_toggle_server.configure(text="Desligar Servidor", fg_color=THEME_TRYHARD["rage_red"])
            local_ip = self.obter_ip_local()
            messagebox.showinfo(
                "Servidor Web Ativo", 
                f"✅ Servidor Web local iniciado com sucesso!\n\n"
                f"• No Computador: http://localhost:5000\n"
                f"• Nos Celulares (Wi-Fi/Hotspot): http://{local_ip}:5000\n\n"
                f"Dica de Rede: Se o celular conectado no seu Hotspot 5G não abrir a página, "
                f"execute como Administrador o arquivo 'liberar_firewall_porta_5000.bat' para permitir a porta 5000 no Firewall do Windows."
            )

    # -------------------------------------------------------------------------
    # MÓDULO 3: HARDWARE & SERVIDOR (CONSOLE CIBERFÍSICO)
    # -------------------------------------------------------------------------
    def show_modulo_hardware(self):
        self.clear_content_area()
        self.modulo_atual = 3
        self.update_navbar_active_state(3)

        if not HAS_CTK:
            return

        title = ctk.CTkLabel(self.content_area, text="📡 Módulo 3: Hardware & Servidor (Console Ciberfísico)", font=("Helvetica", 18, "bold"))
        title.pack(anchor="w", padx=15, pady=10)

        main_grid = ctk.CTkFrame(self.content_area, fg_color="transparent")
        main_grid.pack(fill="both", expand=True, padx=10, pady=5)

        # Coluna 1: Controle Serial, Mesh, Web & Integrações (com rolagem vertical suave)
        col_left = ctk.CTkScrollableFrame(main_grid, fg_color=THEME_TRYHARD["bg_card"], width=435)
        col_left.pack(side="left", fill="both", expand=False, padx=(0, 5))

        # CARD 1: Escuta Serial USB UART
        card_serial = ctk.CTkFrame(col_left, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        card_serial.pack(fill="x", padx=10, pady=10)

        lbl_s_title = ctk.CTkLabel(card_serial, text="⚙️ Escuta Serial (USB UART)", font=("Helvetica", 13, "bold"))
        lbl_s_title.pack(anchor="w", padx=15, pady=(10, 5))

        ports = listar_portas_com()

        row_port = ctk.CTkFrame(card_serial, fg_color="transparent")
        row_port.pack(fill="x", padx=15, pady=5)

        lbl_p = ctk.CTkLabel(row_port, text="Porta COM:", font=("Helvetica", 11, "bold"))
        lbl_p.pack(side="left", padx=5)

        combo_com = ctk.CTkComboBox(row_port, values=ports, width=130)
        combo_com.set(self.driver_serial.porta_com or (ports[0] if ports else "COM7"))
        combo_com.pack(side="left", padx=5)

        def reconectar_serial():
            p_sel = combo_com.get().strip()
            self.driver_serial.parar()
            self.driver_serial = AdaptadorCoordenador(
                porta_com=p_sel,
                baudrate=115200,
                callback_mensagem=self.on_mensagem_serial_recebida,
                mock=False
            )
            self.driver_serial.start()
            self.motor.driver_serial = self.driver_serial
            try:
                import web.app as web_module
                web_module.driver = self.driver_serial
            except Exception:
                pass
            st_text = f"COM: {p_sel} (Ativo)"
            msg_body = f"Escuta serial conectada com sucesso na porta {p_sel}!"
            self.lbl_status_com.configure(text=st_text, text_color="#00FF88")
            lbl_status_ser.configure(text=f"Status: CONECTADO em {p_sel}", text_color="#00FF88")
            messagebox.showinfo("Serial Reconectada", msg_body)

        def desconectar_serial():
            p_sel = combo_com.get().strip()
            self.driver_serial.parar()
            self.lbl_status_com.configure(text="COM: Liberada", text_color="#F59E0B")
            lbl_status_ser.configure(text=f"Status: LIBERADA / DESCONECTADA ({p_sel})", text_color="#F59E0B")
            messagebox.showinfo(
                "Porta Serial Liberada",
                f"A porta {p_sel} foi desconectada e liberada com sucesso pelo Autoreporter!\n\n"
                f"Você já pode compilar ou gravar sketches pelo Arduino IDE sem erros de porta ocupada.\n\n"
                f"Quando terminar o upload no Arduino, clique no botão 'Conectar'."
            )

        btn_rec = ctk.CTkButton(
            row_port,
            text="Conectar",
            width=85,
            command=reconectar_serial,
            fg_color=THEME_TRYHARD["primary"],
            hover_color=THEME_TRYHARD["primary_hover"],
            text_color=THEME_TRYHARD["primary_text"],
            font=("Helvetica", 11, "bold")
        )
        btn_rec.pack(side="left", padx=5)

        btn_pause = ctk.CTkButton(
            row_port,
            text="🔌 Liberar",
            width=80,
            command=desconectar_serial,
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            font=("Helvetica", 11, "bold")
        )
        btn_pause.pack(side="left", padx=5)

        lbl_status_ser = ctk.CTkLabel(card_serial, text=f"Status: CONECTADO em {combo_com.get()}", font=("Helvetica", 11), text_color="#00FF88")
        lbl_status_ser.pack(anchor="w", padx=15, pady=(0, 10))

        # CARD 1.5: Topologia de Rede Mesh & Barreira Virtual (TCC)
        card_mesh = ctk.CTkFrame(col_left, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        card_mesh.pack(fill="x", padx=10, pady=(0, 10))

        lbl_m_title = ctk.CTkLabel(card_mesh, text="🛰️ Rede Mesh & Demonstração TCC", font=("Helvetica", 13, "bold"))
        lbl_m_title.pack(anchor="w", padx=15, pady=(10, 4))

        frame_rota = ctk.CTkFrame(card_mesh, fg_color="#18181B", corner_radius=6, border_width=1, border_color="#27272A")
        frame_rota.pack(fill="x", padx=15, pady=(0, 8))

        lbl_r_title = ctk.CTkLabel(frame_rota, text="📍 Última Rota Detectada:", font=("Helvetica", 10, "bold"), text_color="#A1A1AA")
        lbl_r_title.pack(anchor="w", padx=10, pady=(6, 2))

        rota_txt = "Aguardando primeiro evento RFID/Score..."
        rota_cor = "#9CA3AF"
        if getattr(self, "ultima_rota_mesh", None) and self.ultima_rota_mesh.get("origem"):
            r = self.ultima_rota_mesh
            if r["via"] in ("DIRETO", "LOCAL"):
                rota_txt = f"⚡ DIRETO (1 salto): Nó {r['origem'][-5:]} ➔ Coordenador USB"
                rota_cor = "#38BDF8"
            else:
                rota_txt = f"🔀 MULTI-HOP (2 saltos): Nó {r['origem'][-5:]} ➔ Repetidor {r['via'][-5:]} ➔ Coordenador"
                rota_cor = "#A855F7"

        self.lbl_rota_mesh_status = ctk.CTkLabel(frame_rota, text=rota_txt, font=("Consolas", 11, "bold"), text_color=rota_cor)
        self.lbl_rota_mesh_status.pack(anchor="w", padx=10, pady=(0, 8))

        # Barreira Virtual de Rádio
        lbl_barr_title = ctk.CTkLabel(card_mesh, text="🛡️ Barreira Virtual de Rádio (Simulação de Obstáculo):", font=("Helvetica", 11, "bold"), text_color=THEME_TRYHARD["text_main"])
        lbl_barr_title.pack(anchor="w", padx=15, pady=(4, 2))

        lbl_barr_desc = ctk.CTkLabel(
            card_mesh, 
            text="Simula distância física na bancada: o Coordenador descarta recepção direta (1 salto) e só aceita o sinal se outro nó atuar como Repetidor Mesh (LED Roxo).", 
            font=("Helvetica", 10), 
            text_color="#9CA3AF", 
            wraplength=380, 
            justify="left"
        )
        lbl_barr_desc.pack(anchor="w", padx=15, pady=(0, 8))

        row_barr_ctrl = ctk.CTkFrame(card_mesh, fg_color="transparent")
        row_barr_ctrl.pack(fill="x", padx=15, pady=(0, 12))

        lbl_alvo = ctk.CTkLabel(row_barr_ctrl, text="Alvo:", font=("Helvetica", 11, "bold"))
        lbl_alvo.pack(side="left", padx=(0, 6))

        nos_inventario = self.db.listar_nos_inventario()
        map_nos_barr = {"Todos os Nós": None}
        for n in nos_inventario:
            nick = n["nickname"] or f"Nó {n['mac_address'][-5:]}"
            map_nos_barr[f"{nick} ({n['mac_address'][-5:]})"] = n["mac_address"]
        opts_barr = list(map_nos_barr.keys())

        combo_alvo_barr = ctk.CTkComboBox(row_barr_ctrl, values=opts_barr, width=175, height=28)
        combo_alvo_barr.set(opts_barr[0] if opts_barr else "Todos os Nós")
        combo_alvo_barr.pack(side="left", padx=(0, 8))

        def toggle_barreira():
            self.barreira_mesh_ativa = not self.barreira_mesh_ativa
            sel_label = combo_alvo_barr.get()
            target_mac = map_nos_barr.get(sel_label)
            self.barreira_mac_bloqueado = target_mac

            if hasattr(self, "driver_serial") and self.driver_serial:
                self.driver_serial.enviar_comando_barreira(self.barreira_mesh_ativa, target_mac)

            if self.barreira_mesh_ativa:
                btn_barr.configure(text="🔴 Barreira Ativa", fg_color="#DC2626", hover_color="#B91C1C", text_color="#FFFFFF")
                alvo_str = f"Nó {target_mac[-5:]}" if target_mac else "Todos os nós"
                msg_txt = f"🛡️ Barreira de rádio ATIVADA para {alvo_str}!\n\nRecepção direta bloqueada. Apenas pacotes relayados pela malha Mesh (repetidor) serão aceitos pelo Coordenador."
            else:
                btn_barr.configure(text="🛡️ Ativar Barreira", fg_color="#374151", hover_color="#4B5563", text_color="#FFFFFF")
                msg_txt = "🟢 Barreira de rádio DESATIVADA.\n\nComunicação direta restaurada normalmente."

            self.on_mensagem_serial_recebida("SISTEMA", msg_txt.replace("\n\n", " | "))
            messagebox.showinfo("Barreira Virtual de Rádio", msg_txt)

        btn_barr_text = "🔴 Barreira Ativa" if self.barreira_mesh_ativa else "🛡️ Ativar Barreira"
        btn_barr_color = "#DC2626" if self.barreira_mesh_ativa else "#374151"
        btn_barr = ctk.CTkButton(row_barr_ctrl, text=btn_barr_text, width=125, height=28, fg_color=btn_barr_color, hover_color="#4B5563", font=("Helvetica", 11, "bold"), command=toggle_barreira)
        btn_barr.pack(side="left")
        self.btn_toggle_barreira = btn_barr

        # CARD 1.8: Servidor Web Local & Intranet dos Competidores
        card_web = ctk.CTkFrame(col_left, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        card_web.pack(fill="x", padx=10, pady=(0, 10))

        lbl_w_title = ctk.CTkLabel(card_web, text="🌐 Servidor Web & Intranet Mobile", font=("Helvetica", 13, "bold"))
        lbl_w_title.pack(anchor="w", padx=15, pady=(10, 4))

        local_ip_m3 = self.obter_ip_local()
        web_url_m3 = f"http://{local_ip_m3}:5000"

        lbl_w_ip = ctk.CTkLabel(card_web, text=f"URL Wi-Fi: {web_url_m3}", font=("Consolas", 12, "bold"), text_color="#38BDF8")
        lbl_w_ip.pack(anchor="w", padx=15, pady=(0, 6))

        row_web_actions = ctk.CTkFrame(card_web, fg_color="transparent")
        row_web_actions.pack(fill="x", padx=15, pady=(0, 10))

        def copiar_url_web_m3():
            self.root.clipboard_clear()
            self.root.clipboard_append(web_url_m3)
            messagebox.showinfo("URL Copiada", f"URL copiada para a área de transferência:\n{web_url_m3}")

        btn_copy_w = ctk.CTkButton(row_web_actions, text="📋 Copiar URL", width=100, height=26, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["text_main"], font=("Helvetica", 11, "bold"), command=copiar_url_web_m3)
        btn_copy_w.pack(side="left", padx=(0, 6))

        def executar_liberacao_firewall():
            bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "liberar_firewall_porta_5000.bat")
            if not os.path.exists(bat_path):
                bat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "liberar_firewall_porta_5000.bat")
            if not os.path.exists(bat_path):
                bat_path = os.path.join(os.getcwd(), "liberar_firewall_porta_5000.bat")
            try:
                import subprocess
                subprocess.Popen(["cmd.exe", "/c", bat_path], shell=True)
            except Exception as ex:
                messagebox.showerror("Firewall", f"Erro ao executar script de firewall: {ex}")

        btn_firewall = ctk.CTkButton(row_web_actions, text="🛡️ Liberar Porta 5000", width=155, height=26, fg_color="#374151", hover_color="#0284C7", text_color="#FFFFFF", font=("Helvetica", 11, "bold"), command=executar_liberacao_firewall)
        btn_firewall.pack(side="left")

        # CARD 2: Ferramentas de Exportação e Importação de Dados
        card_tools = ctk.CTkFrame(col_left, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        card_tools.pack(fill="x", padx=10, pady=10)

        lbl_t_title = ctk.CTkLabel(card_tools, text="📦 Integração Externa & Arquivos", font=("Helvetica", 13, "bold"))
        lbl_t_title.pack(anchor="w", padx=15, pady=(10, 5))

        btn_exp = ctk.CTkButton(card_tools, text="📊 Exportar Relatório (CSV / JSON)", fg_color=THEME_TRYHARD["status_success"], hover_color="#0D9467", text_color="#FFFFFF", font=("Helvetica", 12, "bold"),
                                command=self.modal_exportar_torneio, height=36)
        btn_exp.pack(fill="x", padx=15, pady=6)

        btn_imp = ctk.CTkButton(card_tools, text="📥 Importar Atletas em Lote (Start.gg/CSV)", fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 12, "bold"),
                                command=self.modal_importar_participantes, height=36)
        btn_imp.pack(fill="x", padx=15, pady=(6, 15))

        # Coluna 2: Monitor de Estações & Feed de Telemetria (60% largura)
        col_right = ctk.CTkFrame(main_grid, fg_color=THEME_TRYHARD["bg_card"])
        col_right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Sub-Aba / Painel Superior: Monitor de Estações e LEDs RGB
        card_stations = ctk.CTkFrame(col_right, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"], height=220)
        card_stations.pack(fill="x", padx=10, pady=(10, 5))

        top_st_bar = ctk.CTkFrame(card_stations, fg_color="transparent")
        top_st_bar.pack(fill="x", padx=15, pady=8)

        ev_ativo = self.db.obter_evento(self.evento_selecionado_id) if getattr(self, "evento_selecionado_id", None) else None
        ev_nome_ativo = ev_ativo["name"] if ev_ativo else "Nenhum Torneio Selecionado"
        
        st_title_box = ctk.CTkFrame(top_st_bar, fg_color="transparent")
        st_title_box.pack(side="left", fill="y")

        lbl_st_head = ctk.CTkLabel(st_title_box, text="🎛️ Monitor de Estações", font=("Helvetica", 13, "bold"), text_color="#FFFFFF")
        lbl_st_head.pack(side="left")

        lbl_st_ev = ctk.CTkLabel(st_title_box, text=f"  •  {ev_nome_ativo}", font=("Helvetica", 11), text_color="#9CA3AF")
        lbl_st_ev.pack(side="left")

        btn_add_mesa_m3 = ctk.CTkButton(top_st_bar, text="🎛️ Gerenciar Estações", width=170, height=24, fg_color=THEME_TRYHARD["primary"], hover_color=THEME_TRYHARD["primary_hover"], text_color=THEME_TRYHARD["primary_text"], font=("Helvetica", 11, "bold"), command=self.acao_clicar_gerenciar_estacoes)
        btn_add_mesa_m3.bind("<Button-1>", lambda e: setattr(self, "_last_btn_press_event", e))
        btn_add_mesa_m3.pack(side="right")

        btn_map_m3 = ctk.CTkButton(top_st_bar, text="📡 Mapear Nós Repórteres", width=190, height=24, fg_color="#0284C7", hover_color="#0369A1", text_color="#FFFFFF", font=("Helvetica", 11, "bold"), command=lambda: self.modal_mapear_nos_reporteres(on_close_callback=self.show_modulo_hardware))
        btn_map_m3.pack(side="right", padx=(0, 8))

        scroll_st_m3 = ctk.CTkScrollableFrame(card_stations, height=140, label_text="Estações Ativas no Torneio")
        scroll_st_m3.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cursor = self.db.conn.cursor()
        if getattr(self, "evento_selecionado_id", None):
            cursor.execute("SELECT id, name, node_mac FROM stations WHERE event_id = ? ORDER BY id ASC", (self.evento_selecionado_id,))
        else:
            cursor.execute("SELECT id, name, node_mac FROM stations ORDER BY id ASC")
        mesas_all = cursor.fetchall()
        hw_opts_m3, hw_map_m3 = self.obter_opcoes_hardware_dropdown()

        if not mesas_all:
            lbl_empty_m3 = ctk.CTkLabel(scroll_st_m3, text="Nenhuma estação cadastrada. Clique em '🎛️ Gerenciar Estações'.", font=("Helvetica", 11), text_color="#888888")
            lbl_empty_m3.pack(pady=15)
        else:
            for st in mesas_all:
                st_id = st["id"]
                st_name = st["name"]
                st_mac = st["node_mac"] or "Sem MAC"

                cursor.execute("""
                    SELECT id, status, pending_score1, score_conflict
                    FROM matches WHERE station_id = ? AND status IN ('READY', 'PLAYING')
                """, (st_id,))
                active = cursor.fetchone()

                if active:
                    if active["score_conflict"]:
                        border_color, led_color, led_text = THEME_TRYHARD["rage_red"], THEME_TRYHARD["rage_red"], "🚨 DIVERGÊNCIA DE PLACAR!"
                    elif active["pending_score1"] is not None:
                        border_color, led_color, led_text = THEME_TRYHARD["status_waiting"], THEME_TRYHARD["status_waiting"], "🟡 Chancela Pendente (RFID)"
                    elif active["status"] == "PLAYING":
                        border_color, led_color, led_text = THEME_TRYHARD["rage_red"], THEME_TRYHARD["rage_red"], "💢 Em Jogo"
                    else:
                        border_color, led_color, led_text = THEME_TRYHARD["status_waiting"], THEME_TRYHARD["status_waiting"], "⚠️ Convocada (Aguardando RFID)"
                else:
                    border_color, led_color, led_text = THEME_TRYHARD["border"], THEME_TRYHARD["status_success"], "🟢 Livre"

                row_st = ctk.CTkFrame(scroll_st_m3, fg_color=THEME_TRYHARD["bg_card"], border_width=2, border_color=border_color, height=36, corner_radius=6)
                row_st.pack(fill="x", padx=5, pady=2)

                lbl_st_info = ctk.CTkLabel(row_st, text=f"🪑 {st_name}", font=("Helvetica", 11, "bold"))
                lbl_st_info.pack(side="left", padx=10)

                lbl_led = ctk.CTkLabel(row_st, text=led_text, font=("Helvetica", 10, "bold"), text_color=led_color)
                lbl_led.pack(side="right", padx=10)

                combo_node_m3 = ctk.CTkComboBox(row_st, values=hw_opts_m3, width=195, height=24, font=("Helvetica", 10))
                combo_node_m3.set(self.obter_label_para_mac(st["node_mac"], hw_map_m3))

                def on_m3_node_change(choice, sid=st_id):
                    mac_choice = hw_map_m3.get(choice)
                    if mac_choice:
                        self.db.vincular_no_estacao(sid, mac_choice)
                    else:
                        self.db.desvincular_no_estacao(sid)
                    self.show_modulo_hardware()

                combo_node_m3.configure(command=on_m3_node_change)
                combo_node_m3.pack(side="right", padx=6)

        # Sub-Aba / Painel Inferior: Feed de Telemetria de Rádio (Console Serial)
        card_log = ctk.CTkFrame(col_right, fg_color=THEME_TRYHARD["bg_main"], border_width=1, border_color=THEME_TRYHARD["border"])
        card_log.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        log_head = ctk.CTkFrame(card_log, fg_color="transparent")
        log_head.pack(fill="x", padx=15, pady=8)

        lbl_log_head = ctk.CTkLabel(log_head, text="💻 Feed de Telemetria de Rádio (Serial USB UART)", font=("Helvetica", 13, "bold"))
        lbl_log_head.pack(side="left")

        def limpar_console():
            if hasattr(self, "txt_telemetria"):
                self.txt_telemetria.configure(state="normal")
                self.txt_telemetria.delete("1.0", "end")
                self.txt_telemetria.configure(state="disabled")

        btn_clear = ctk.CTkButton(log_head, text="🧹 Limpar", width=70, height=24, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=limpar_console)
        btn_clear.pack(side="right", padx=5)

        self.telemetria_ativa = True

        def toggle_pause():
            self.telemetria_ativa = not self.telemetria_ativa
            btn_pause.configure(text="▶️ Retomar" if not self.telemetria_ativa else "⏸️ Pausar")

        btn_pause = ctk.CTkButton(log_head, text="⏸️ Pausar", width=75, height=24, fg_color=THEME_TRYHARD["border"], hover_color=THEME_TRYHARD["bg_card_alt"], text_color=THEME_TRYHARD["text_main"], command=toggle_pause)
        btn_pause.pack(side="right", padx=2)

        self.txt_telemetria = ctk.CTkTextbox(
            card_log, 
            font=("Consolas", 11), 
            fg_color=THEME_TRYHARD["terminal_bg"], 
            text_color=THEME_TRYHARD["text_main"],
            border_width=1,
            border_color=THEME_TRYHARD["border"]
        )
        self.txt_telemetria.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_telemetria.configure(state="disabled")

        # Configuração das Tags de Colorização de Telemetria TryHard Arena
        self.txt_telemetria.tag_config("rfid", foreground=THEME_TRYHARD["primary"])
        self.txt_telemetria.tag_config("score", foreground=THEME_TRYHARD["rage_red"])
        self.txt_telemetria.tag_config("downlink", foreground=THEME_TRYHARD["status_success"])
        self.txt_telemetria.tag_config("alert", foreground=THEME_TRYHARD["status_waiting"])
        self.txt_telemetria.tag_config("system", foreground=THEME_TRYHARD["text_muted"])
        self.txt_telemetria.tag_config("mesh_relay", foreground="#C084FC")
        self.txt_telemetria.tag_config("barrier", foreground="#EF4444")
        self.txt_telemetria.tag_config("barrier_ok", foreground="#10B981")

        self.txt_telemetria.configure(state="normal")
        self.txt_telemetria.insert("end", "[SISTEMA] Console de Telemetria de Rádio Inicializado.\n", "system")
        self.txt_telemetria.insert("end", f"[SISTEMA] Conectado na porta: {combo_com.get()}\n", "system")
        self.txt_telemetria.insert("end", "[SISTEMA] Aguardando mensagens 'RFID', 'SCORE' e Downlinks...\n\n", "system")
        self.txt_telemetria.configure(state="disabled")

    def modal_qrcode_jogador(self, player_name, mobile_url):
        """
        Exibe janela modal com QR Code dinâmico apontando diretamente para o link mobile
        do competidor selecionado (Ex: http://<IP>:5000/player/<ident>), permitindo
        que a banca avaliadora escaneie com a câmera do celular para abrir o Web App do atleta.
        """
        top = ctk.CTkToplevel(self.root)
        top.title(f"📱 QR Code Mobile - {player_name}")
        top.geometry("420x510")
        top.minsize(380, 470)
        top.configure(fg_color=THEME_TRYHARD["bg_main"])
        top.transient(self.root)
        top.lift()
        top.focus_set()

        # Cabeçalho
        lbl_head = ctk.CTkLabel(
            top,
            text=f"📱 Acesso Mobile: {player_name}",
            font=("Helvetica", 16, "bold"),
            text_color=THEME_TRYHARD["primary"]
        )
        lbl_head.pack(padx=20, pady=(15, 2))

        lbl_sub = ctk.CTkLabel(
            top,
            text="Aponte a câmera do celular para abrir a área do competidor",
            font=("Helvetica", 11),
            text_color=THEME_TRYHARD["text_muted"]
        )
        lbl_sub.pack(padx=20, pady=(0, 10))

        # Banner de Estado do Servidor
        frame_server_info = ctk.CTkFrame(top, fg_color=THEME_TRYHARD["bg_card"], corner_radius=8, border_width=1, border_color=THEME_TRYHARD["border"])
        frame_server_info.pack(fill="x", padx=25, pady=(0, 10))

        lbl_srv_status = ctk.CTkLabel(
            frame_server_info,
            text="🟢 Servidor Web Ativo na porta 5000" if self.servidor_rodando else "⚠️ Servidor Web Desligado",
            font=("Helvetica", 11, "bold"),
            text_color=THEME_TRYHARD["status_success"] if self.servidor_rodando else THEME_TRYHARD["status_waiting"]
        )
        lbl_srv_status.pack(side="left", padx=12, pady=8)

        def ligar_servidor_pelo_modal():
            if not self.servidor_rodando:
                self.toggle_servidor_web()
                lbl_srv_status.configure(text="🟢 Servidor Web Ativo na porta 5000", text_color=THEME_TRYHARD["status_success"])
                btn_ligar_srv.pack_forget()

        btn_ligar_srv = ctk.CTkButton(
            frame_server_info,
            text="▶️ Ligar Agora",
            width=100,
            height=24,
            fg_color=THEME_TRYHARD["primary"],
            hover_color=THEME_TRYHARD["primary_hover"],
            text_color=THEME_TRYHARD["primary_text"],
            font=("Helvetica", 10, "bold"),
            command=ligar_servidor_pelo_modal
        )
        if not self.servidor_rodando:
            btn_ligar_srv.pack(side="right", padx=10, pady=6)

        # Moldura branca de alto contraste para o QR Code (essencial para leitura óptica rápida por câmera)
        qr_badge = ctk.CTkFrame(top, fg_color="#FFFFFF", corner_radius=12, width=250, height=250)
        qr_badge.pack(pady=5)
        qr_badge.pack_propagate(False)

        lbl_qr_display = ctk.CTkLabel(qr_badge, text="", fg_color="#FFFFFF")
        lbl_qr_display.place(relx=0.5, rely=0.5, anchor="center")

        entry_url = ctk.CTkEntry(top, width=380, height=30, justify="center", font=("Consolas", 11, "bold"))
        entry_url.pack(pady=(8, 10))
        entry_url.insert(0, mobile_url)
        entry_url.configure(state="readonly")

        try:
            import qrcode
            from PIL import Image
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2
            )
            qr.add_data(mobile_url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")
            pil_img = pil_img.resize((220, 220), Image.Resampling.NEAREST)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(220, 220))
            lbl_qr_display.configure(image=ctk_img)
            lbl_qr_display.image = ctk_img
        except Exception as ex:
            lbl_qr_display.configure(text=f"Erro ao gerar QR Code:\n{ex}", text_color="#000000", font=("Helvetica", 10))

        # Instrução da Banca
        lbl_hint = ctk.CTkLabel(
            top,
            text="💡 O smartphone deve estar conectado no mesmo Wi-Fi deste computador.",
            font=("Helvetica", 10),
            text_color=THEME_TRYHARD["text_muted"],
            justify="center"
        )
        lbl_hint.pack(padx=20, pady=(6, 12))

        btn_fechar = ctk.CTkButton(
            top,
            text="Fechar",
            width=120,
            height=28,
            fg_color="#27272A",
            hover_color="#3F3F46",
            command=top.destroy
        )
        btn_fechar.pack(pady=(0, 15))

    def modal_qrcode_mobile(self):
        """Fallback para compatibilidade retroativa."""
        local_ip = self.obter_ip_local()
        self.modal_qrcode_jogador("Entrada Geral", f"http://{local_ip}:5000/")

    # -------------------------------------------------------------------------
    # MODAIS DE EXPORTAÇÃO E IMPORTAÇÃO
    # -------------------------------------------------------------------------
    def modal_exportar_torneio(self):
        if not getattr(self, "evento_selecionado_id", None):
            messagebox.showerror("Erro de Exportação", "Selecione um campeonato na aba 'Lista de Eventos' antes de exportar.")
            return

        ev = self.db.obter_evento(self.evento_selecionado_id)
        ev_name = ev["name"] if ev else f"Evento_{self.evento_selecionado_id}"

        top = ctk.CTkToplevel(self.root)
        top.title("Exportar Relatório do Torneio")
        top.geometry("450x240")
        top.transient(self.root)
        top.lift()
        top.focus_set()

        lbl_t = ctk.CTkLabel(top, text=f"📊 Exportar Dados de '{ev_name}'", font=("Helvetica", 15, "bold"))
        lbl_t.pack(pady=15)

        lbl_desc = ctk.CTkLabel(top, text="Escolha o formato de arquivo desejado para salvar a classificação e histórico de partidas:", font=("Helvetica", 11), wraplength=400)
        lbl_desc.pack(pady=5)

        row_btns = ctk.CTkFrame(top, fg_color="transparent")
        row_btns.pack(pady=20)

        def exp_csv():
            fpath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV File", "*.csv")], initialfile=f"{ev_name}_relatorio.csv")
            if fpath:
                ok, msg = self.db.exportar_evento_csv(self.evento_selecionado_id, fpath)
                if ok:
                    messagebox.showinfo("Sucesso", msg)
                    top.destroy()
                else:
                    messagebox.showerror("Erro", msg)

        def exp_json():
            fpath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON File", "*.json")], initialfile=f"{ev_name}_relatorio.json")
            if fpath:
                ok, msg = self.db.exportar_evento_json(self.evento_selecionado_id, fpath)
                if ok:
                    messagebox.showinfo("Sucesso", msg)
                    top.destroy()
                else:
                    messagebox.showerror("Erro", msg)

        btn_csv = ctk.CTkButton(row_btns, text="📄 Exportar CSV", fg_color="#059669", hover_color="#047857", command=exp_csv, width=150, height=36)
        btn_csv.pack(side="left", padx=10)

        btn_json = ctk.CTkButton(row_btns, text="📦 Exportar JSON", fg_color="#2563EB", hover_color="#1D4ED8", command=exp_json, width=150, height=36)
        btn_json.pack(side="left", padx=10)

    def modal_importar_participantes(self):
        top = ctk.CTkToplevel(self.root)
        top.title("Importar Atletas em Lote (Start.gg / CSV)")
        top.geometry("550x420")
        top.transient(self.root)
        top.lift()
        top.focus_set()

        lbl_t = ctk.CTkLabel(top, text="📥 Importação de Atletas em Lote", font=("Helvetica", 15, "bold"))
        lbl_t.pack(pady=15)

        lbl_desc = ctk.CTkLabel(top, text="Cole o texto CSV/JSON ou selecione um arquivo contendo a lista de participantes.\nFormato CSV aceito: nickname;real_name;tag_uid", font=("Helvetica", 11), wraplength=500)
        lbl_desc.pack(pady=5)

        txt_input = ctk.CTkTextbox(top, height=180, font=("Courier", 11))
        txt_input.pack(fill="x", padx=20, pady=10)
        txt_input.insert("end", "# Exemplo CSV:\nAlice;Alice Silva;A1B2C3D4\nBob;Bob Santos;E5F6G7H8\nCharlie;Charlie Souza;\n")

        row_b = ctk.CTkFrame(top, fg_color="transparent")
        row_b.pack(pady=10)

        def carregar_arquivo():
            fpath = filedialog.askopenfilename(filetypes=[("Arquivos Texto/CSV/JSON", "*.csv *.json *.txt")])
            if fpath:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        conteudo = f.read()
                    txt_input.delete("1.0", "end")
                    txt_input.insert("1.0", conteudo)
                    messagebox.showinfo("Arquivo Carregado", f"Conteúdo de '{fpath}' carregado na caixa de texto!")
                except Exception as ex:
                    messagebox.showerror("Erro ao Abrir", f"Falha ao ler arquivo: {ex}")

        def processar_importacao():
            texto = txt_input.get("1.0", "end").strip()
            if not texto:
                messagebox.showerror("Erro", "Forneça o conteúdo em texto antes de importar.")
                return

            lista_parsed = []
            try:
                import json
                dados_json = json.loads(texto)
                if isinstance(dados_json, list):
                    lista_parsed = dados_json
                elif isinstance(dados_json, dict) and "participantes" in dados_json:
                    lista_parsed = dados_json["participantes"]
            except Exception:
                import csv
                linhas = [l for l in texto.splitlines() if l.strip() and not l.strip().startswith("#")]
                if linhas:
                    primeira = linhas[0]
                    delim = ";" if ";" in primeira else ","
                    reader = csv.reader(linhas, delimiter=delim)
                    rows = list(reader)

                    if rows:
                        header = [c.strip().lower() for c in rows[0]]
                        has_header = any(h in ("gamertag", "gamer tag", "nickname", "nick", "player", "atleta") for h in header)

                        nick_idx = 0
                        real_idx = 1
                        tag_idx = 2 if not has_header else None

                        start_row = 0
                        if has_header:
                            start_row = 1
                            for idx, col in enumerate(header):
                                if col in ("gamertag", "gamer tag", "nickname", "nick", "player"):
                                    nick_idx = idx
                                elif col in ("real_name", "realname", "name", "nome", "first name"):
                                    real_idx = idx
                                elif col in ("tag_uid", "rfid", "tag", "rfid_tag"):
                                    tag_idx = idx

                        for r in rows[start_row:]:
                            if not r:
                                continue
                            nick = r[nick_idx].strip() if len(r) > nick_idx else ""
                            real = r[real_idx].strip() if len(r) > real_idx else nick
                            if has_header and "last name" in header:
                                last_idx = header.index("last name")
                                if len(r) > last_idx and r[last_idx].strip():
                                    real = f"{real} {r[last_idx].strip()}".strip()
                            tag = r[tag_idx].strip() if tag_idx is not None and len(r) > tag_idx else ""
                            if nick and nick.lower() not in ("gamertag", "gamer tag", "nickname", "player"):
                                lista_parsed.append({"nickname": nick, "real_name": real, "tag_uid": tag})

            if not lista_parsed:
                messagebox.showerror("Erro de Formatação", "Nenhum atleta válido foi extraído da entrada.")
                return

            ins, atu = self.db.importar_participantes_lote(lista_parsed)
            messagebox.showinfo("Importação Concluída", f"Processamento concluído com sucesso!\n\n✨ Novos Atletas Cadastrados: {ins}\n🔄 Atletas Atualizados: {atu}")
            top.destroy()
            if hasattr(self, "show_modulo_jogadores"):
                self.show_modulo_jogadores()

        btn_file = ctk.CTkButton(row_b, text="📂 Abrir Arquivo", fg_color="#374151", command=carregar_arquivo, width=140)
        btn_file.pack(side="left", padx=10)

        btn_proc = ctk.CTkButton(row_b, text="🚀 Processar Importação", fg_color="#10B981", hover_color="#059669", command=processar_importacao, width=180)
        btn_proc.pack(side="left", padx=10)

    def fechar_aplicacao_gracioso(self):
        """
        Encerramento Gracioso Mestre:
        1. Desliga o driver serial e libera instantaneamente qualquer porta COM conectada no SO.
        2. Fecha a conexão com o banco SQLite.
        3. Destrói a interface gráfica Tkinter.
        4. Encerra terminantemente o processo Python com os._exit(0) para evitar processos zumbis em segundo plano.
        """
        try:
            if hasattr(self, 'driver_serial') and self.driver_serial:
                self.driver_serial.parar()
        except Exception as e:
            print(f"[SHUTDOWN] Erro ao fechar driver serial: {e}")

        try:
            if hasattr(self, 'db') and self.db:
                self.db.fechar()
        except Exception as e:
            print(f"[SHUTDOWN] Erro ao fechar banco: {e}")

        try:
            self.servidor_rodando = False
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

        # Garante liberação instantânea de todos os descritores e threads no Windows
        os._exit(0)

    def confirmar_sair(self):
        if messagebox.askokcancel("Sair do Autoreporter", "Deseja encerrar o aplicativo e liberar todas as portas seriais?"):
            self.fechar_aplicacao_gracioso()

    def acao_auditar_integridade_banco(self):
        """Dispara a rotina mestre de limpeza de dados órfãos e integridade referencial."""
        rel = self.db.sanitizar_e_limpar_dados_orfaos()
        total_corrigido = sum(rel.values())
        msg = (
            f"Varredura de Integridade Concluída!\n\n"
            f"• Jogadores duplicados removidos: {rel['jogadores_duplicados_removidos']}\n"
            f"• Tags RFID órfãs removidas: {rel['tags_orfas_removidas']}\n"
            f"• MACs de nós duplicados desvinculados: {rel['macs_duplicados_desvinculados']}\n"
            f"• Mesas órfãs removidas: {rel['estacoes_orfas_removidas']}\n"
            f"• Inscrições órfãs removidas: {rel['inscricoes_orfas_removidas']}\n"
            f"• Partidas órfãs removidas: {rel['partidas_orfas_removidas']}\n"
            f"• Referências de partidas corrigidas: {rel['referencias_partidas_corrigidas']}\n\n"
        )
        if total_corrigido == 0:
            msg += "✅ O banco de dados está 100% íntegro e sem dados órfãos!"
        else:
            msg += f"🧹 {total_corrigido} inconsistência(s) corrigida(s) com sucesso!"
        messagebox.showinfo("Integridade Referencial", msg)
        self.show_modulo_hardware()

def main():
    import signal
    app_holder = []

    def sig_handler(sig, frame):
        if app_holder:
            app_holder[0].fechar_aplicacao_gracioso()
        else:
            os._exit(0)

    try:
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
    except Exception:
        pass

    try:
        if HAS_CTK:
            root = ctk.CTk()
        else:
            root = tk.Tk()
        app = AutoreporterGUIApp(root)
        app_holder.append(app)
        root.mainloop()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open("crash.log", "w", encoding="utf-8") as f:
                f.write(err_msg)
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("Erro de Inicialização - Autoreporter", f"Ocorreu um erro ao iniciar a aplicação:\n\n{e}\n\nDetalhes gravados em crash.log")
        except Exception:
            pass
    finally:
        if app_holder:
            app_holder[0].fechar_aplicacao_gracioso()
        else:
            os._exit(0)

if __name__ == "__main__":
    main()
