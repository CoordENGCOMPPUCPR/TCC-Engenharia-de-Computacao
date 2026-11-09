/**
 * AUTOREPORTER - FIRMWARE UNIFICADO CIBERFÍSICO (NÓ REPÓRTER & COORDENADOR)
 * Trabalho de Conclusão de Curso (TCC) - Engenharia de Computação PUCPR 2026
 * 
 * ARQUITETURA DE PAPEL DUAL (DUAL-ROLE DESIGN):
 * Todos os módulos físicos possuem hardware rigorosamente idêntico:
 * ESP32 DevKit v1 + Leitor RFID RC522 (SPI) + LEDs de Sinalização Duplos.
 * 
 * 1. Qualquer Nó conectado via cabo USB ao computador central atua AUTOMATICAMENTE
 *    como Adaptador Coordenador (Gateway de Rádio ESP-NOW <-> Serial USB UART 115200 bps)
 *    E TAMBÉM continua operando como Nó de Mesa (com seu próprio leitor RFID e LEDs ativos!).
 * 2. Qualquer Nó alimentado via tomada na parede atua como Nó de Mesa sem fio,
 *    transmitindo eventos RFID e recebendo comandos de LED via rádio ESP-NOW 2.4GHz.
 * 
 * PINAGEM CANÔNICA HOMOLOGADA (ESP32 DEVKIT V1 - 30 PINOS):
 * - RFID RC522 (SPI):
 *     - 3.3V (VCC) -> Pino 3V3 (ESP32)
 *     - GND        -> Pino GND (ESP32)
 *     - RST        -> GPIO 4
 *     - SDA (SS)   -> GPIO 15
 *     - SCK        -> GPIO 18
 *     - MISO       -> GPIO 19
 *     - MOSI       -> GPIO 23
 *     - IRQ        -> GPIO 22 (Interrupção opcional)
 * - LED RGB 1 (Jogador 1 / Esquerdo / Inferior):
 *     - Vermelho (R) -> GPIO 25
 *     - Verde (G)    -> GPIO 33
 *     - Azul (B)     -> GPIO 32
 * - LED RGB 2 (Jogador 2 / Direito / Superior):
 *     - Vermelho (R) -> GPIO 14
 *     - Verde (G)    -> GPIO 27
 *     - Azul (B)     -> GPIO 26
 */

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_mac.h>
#include <esp_arduino_version.h>

// Definições de Hardware - Leitor RFID MFRC522 (SPI)
#define SS_PIN          15   // SPI Slave Select (SDA)
#define RST_PIN         4    // Reset
#define IRQ_PIN         22   // Interrupção Física

// Definições de Hardware - LED 1 (Jogador 1 / Esquerdo / Inferior)
#define L1_RED          25   // Canal Vermelho calibrado (GPIO 25)
#define L1_GREEN        33   // Canal Verde calibrado (GPIO 33)
#define L1_BLUE         32   // Canal Azul calibrado (GPIO 32)

// Definições de Hardware - LED 2 (Jogador 2 / Direito)
#define L2_RED_1        14   // Canal Vermelho calibrado (GPIO 14)
#define L2_RED_2        13
#define L2_GREEN_1      27   // Canal Verde calibrado (GPIO 27)
#define L2_GREEN_2      12
#define L2_BLUE         26   // Canal Azul calibrado (GPIO 26)

MFRC522 mfrc522(SS_PIN, RST_PIN);

// Interrupção Física por Hardware do Leitor RFID (GPIO 22 / pino IRQ)
volatile bool rfidInterrupcaoDisparada = false;

void IRAM_ATTR rfid_isr() {
    rfidInterrupcaoDisparada = true;
}

// Estrutura unificada de pacotes ESP-NOW Mesh (Compatível com todo o ecossistema)
typedef struct struct_message {
    char tipo[10];     // "RFID", "SCORE", "LED", "PING"
    char uid[20];      // UID do cartão OU Cor do LED ("YELLOW", "GREEN", "BLUE", "RED", "OFF")
    int score1;        // Placar 1
    int score2;        // Placar 2
    uint32_t msg_id;   // ID único da mensagem para descarte de duplicatas
    uint8_t hops;      // Contador de saltos restantes (Time-to-Live)
    char orig_mac[18]; // MAC do Nó Repórter que originou o evento
} struct_message;

// Estrutura legada de 4 campos (compatibilidade com pacotes compactos)
typedef struct legacy_message {
    char tipo[10];
    char uid[20];
    int score1;
    int score2;
} legacy_message;

struct_message myData;
struct_message incomingData;
struct_message outgoingData;

// Endereço de broadcast padrão ESP-NOW
const uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// Identificação local do nó
char meuMacStr[18];

// Histórico de mensagens processadas para descarte de duplicatas na malha
#define HISTORICO_MSG_SIZE 30
uint32_t historicoMsgId[HISTORICO_MSG_SIZE];
int indiceHistorico = 0;

bool jaProcessouMsg(uint32_t id) {
    if (id == 0) return false;
    for (int i = 0; i < HISTORICO_MSG_SIZE; i++) {
        if (historicoMsgId[i] == id) return true;
    }
    return false;
}

void registrarMsgProcessada(uint32_t id) {
    if (id == 0) return;
    historicoMsgId[indiceHistorico] = id;
    indiceHistorico = (indiceHistorico + 1) % HISTORICO_MSG_SIZE;
}

// Controle de estado e debounce
String estadoAtualLed = "YELLOW";
String corRetornoAlerta = "YELLOW";
unsigned long tempoInicioAlertaTemp = 0;
unsigned long duracaoAlertaTemp = 0;
bool emAlertaTemporario = false;
unsigned long ultimoTempoLeitura = 0;
const unsigned long DEBOUNCE_RFID_MS = 1200;

// Identificação de papel operacional (Modo Coordenador ativa luz esquerda azul contínua)
bool modoCoordenador = false;

// Barreira Virtual de Rádio (Simulação de Obstáculo / Demonstração Mesh para a Banca)
bool barreiraAtiva = false;
char macBloqueadoDireto[18] = "";

// Garante registro de peer ESP-NOW antes de envio
bool ensurePeer(const uint8_t *peerMac) {
    if (esp_now_is_peer_exist(peerMac)) {
        return true;
    }
    esp_now_peer_info_t peerInfo;
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, peerMac, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    return (esp_now_add_peer(&peerInfo) == ESP_OK);
}

// Controle físico de todos os canais de LED
void clearLeds() {
    digitalWrite(L1_RED, LOW);
    digitalWrite(L1_GREEN, LOW);
    digitalWrite(L1_BLUE, LOW);

    digitalWrite(L2_RED_1, LOW);
    digitalWrite(L2_RED_2, LOW);
    digitalWrite(L2_GREEN_1, LOW);
    digitalWrite(L2_GREEN_2, LOW);
    digitalWrite(L2_BLUE, LOW);
}

// Aciona diretamente os pinos físicos do LED 1 (Esquerdo / Jogador 1)
void aplicarCorL1(int r, int g, int b) {
    digitalWrite(L1_RED,   r ? HIGH : LOW);
    digitalWrite(L1_GREEN, g ? HIGH : LOW);
    digitalWrite(L1_BLUE,  b ? HIGH : LOW);
}

// Aciona diretamente os pinos físicos do LED 2 (Direito / Jogador 2)
void aplicarCorL2(int r, int g, int b) {
    digitalWrite(L2_RED_1,   r ? HIGH : LOW);
    digitalWrite(L2_RED_2,   r ? HIGH : LOW);
    digitalWrite(L2_GREEN_1, g ? HIGH : LOW);
    digitalWrite(L2_GREEN_2, g ? HIGH : LOW);
    digitalWrite(L2_BLUE,    b ? HIGH : LOW);
}

// Decodifica nomes textuais ou códigos numéricos (0..7) para canais R, G, B
// 0=OFF, 1=VERMELHO, 2=AZUL, 3=VERDE, 4=AMARELO, 5=CIANO, 6=ROXO/MAGENTA, 7=BRANCO
void decodificarCor(String c, int &r, int &g, int &b) {
    c.trim();
    c.toUpperCase();
    r = 0; g = 0; b = 0;
    if (c == "0" || c == "OFF" || c == "DESLIGADO" || c == "APAGADO") {
        // Tudo LOW
    } else if (c == "1" || c == "RED" || c == "VERMELHO") {
        r = 1;
    } else if (c == "2" || c == "BLUE" || c == "AZUL") {
        b = 1;
    } else if (c == "3" || c == "GREEN" || c == "VERDE") {
        g = 1;
    } else if (c == "4" || c == "YELLOW" || c == "AMARELO") {
        r = 1; g = 1;
    } else if (c == "5" || c == "CYAN" || c == "CIANO") {
        g = 1; b = 1;
    } else if (c == "6" || c == "MAGENTA" || c == "PURPLE" || c == "ROXO") {
        r = 1; b = 1;
    } else if (c == "7" || c == "WHITE" || c == "BRANCO") {
        r = 1; g = 1; b = 1;
    }
}

// Controle estático independente de ambos os LEDs (permanece ativo sem expirar)
void setBothLeds(String c1, String c2) {
    emAlertaTemporario = false;
    clearLeds();
    int r1, g1, b1;
    int r2, g2, b2;
    decodificarCor(c1, r1, g1, b1);
    decodificarCor(c2, r2, g2, b2);
    aplicarCorL1(r1, g1, b1);
    aplicarCorL2(r2, g2, b2);
}

void setCorLed(const String &cor) {
    if (cor.equalsIgnoreCase("CHECKIN1")) {
        // 1º Check-in confirmado:
        // L1 (Esquerdo): Permanece Amarelo (aguardando oponente)
        // L2 (Direito): Acende Verde puro por 2.0 segundos!
        emAlertaTemporario = true;
        tempoInicioAlertaTemp = millis();
        duracaoAlertaTemp = 2000;
        corRetornoAlerta = "YELLOW";

        clearLeds();
        aplicarCorL1(1, 1, 0); // Amarelo (R+G)
        aplicarCorL2(0, 1, 0); // Verde (G)
        return;
    }
    else if (cor.equalsIgnoreCase("CHECKIN2")) {
        // 2º Check-in confirmado (Ambos atletas na mesa):
        // L1 e L2: Acendem Verde puro por 2.0 segundos (confirmação total)!
        emAlertaTemporario = true;
        tempoInicioAlertaTemp = millis();
        duracaoAlertaTemp = 2000;
        corRetornoAlerta = "BLUE";

        clearLeds();
        aplicarCorL1(0, 1, 0); // Verde (G)
        aplicarCorL2(0, 1, 0); // Verde (G)
        return;
    }
    else if (cor.equalsIgnoreCase("RED")) {
        if (!estadoAtualLed.equalsIgnoreCase("RED")) {
            corRetornoAlerta = estadoAtualLed;
        }
        tempoInicioAlertaTemp = millis();
        duracaoAlertaTemp = 2000;
        emAlertaTemporario = true;
    } else {
        emAlertaTemporario = false;
        corRetornoAlerta = cor;
    }

    estadoAtualLed = cor;
    clearLeds();

    int r, g, b;
    decodificarCor(cor, r, g, b);
    aplicarCorL1(r, g, b);
    aplicarCorL2(r, g, b);
}

// =========================================================================
// CALLBACKS ESP-NOW (COMPATÍVEIS COM ESP32 CORE 2.x E 3.x)
// =========================================================================
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
    // Despacho no ar concluído
}

void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingDataRaw, int len) {
    const uint8_t *mac_addr = recv_info->src_addr;
#else
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    // Despacho no ar concluído
}

void OnDataRecv(const uint8_t *mac_addr, const uint8_t *incomingDataRaw, int len) {
#endif
    if (len < (int)sizeof(legacy_message)) {
        return;
    }

    char macStr[18];
    snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac_addr[0], mac_addr[1], mac_addr[2], mac_addr[3], mac_addr[4], mac_addr[5]);

    if (len >= (int)sizeof(struct_message)) {
        memcpy(&incomingData, incomingDataRaw, sizeof(incomingData));
        // Descarte de pacotes já processados (evita tempestade de broadcast / loops)
        if (incomingData.msg_id != 0 && jaProcessouMsg(incomingData.msg_id)) {
            return;
        }
    } else {
        // Pacote em formato legado
        legacy_message leg;
        memcpy(&leg, incomingDataRaw, sizeof(leg));
        memset(&incomingData, 0, sizeof(incomingData));
        strncpy(incomingData.tipo, leg.tipo, sizeof(incomingData.tipo) - 1);
        strncpy(incomingData.uid, leg.uid, sizeof(incomingData.uid) - 1);
        incomingData.score1 = leg.score1;
        incomingData.score2 = leg.score2;
        incomingData.hops = 1;
        strncpy(incomingData.orig_mac, macStr, sizeof(incomingData.orig_mac) - 1);
    }

    // MAC de origem efetivo do evento
    const char *origemFinal = (strlen(incomingData.orig_mac) > 0) ? incomingData.orig_mac : macStr;

    // Cálculo de Saltos e Identificação de Rota Mesh
    bool isDireto = (strcmp(macStr, origemFinal) == 0);
    int saltos = isDireto ? 1 : 2;
    const char *viaStr = isDireto ? "DIRETO" : macStr;

    // Se a Barreira Virtual estiver ativa, descarta recepção direta do nó bloqueado
    if (barreiraAtiva && isDireto) {
        if (strlen(macBloqueadoDireto) == 0 || strcmp(origemFinal, macBloqueadoDireto) == 0) {
            Serial.printf("[BARREIRA_DROP];%s;DIRETO_BLOQUEADO\n", origemFinal);
            return; // Descarte intencional para forçar passagem pelo repetidor Mesh!
        }
    }

    // Registra ID da mensagem após passar pelo filtro da barreira
    if (incomingData.msg_id != 0) {
        registrarMsgProcessada(incomingData.msg_id);
    }

    // =========================================================================
    // PAPEL DE COORDENADOR: Envia para a Serial do PC se estiver conectado!
    // =========================================================================
    if (strcmp(incomingData.tipo, "RFID") == 0) {
        // Formato enriquecido: RFID;<uid>;<orig_mac>;REMOTE;SALTOS:<n>;VIA:<mac>
        Serial.printf("RFID;%s;%s;REMOTE;SALTOS:%d;VIA:%s\n", incomingData.uid, origemFinal, saltos, viaStr);
    } 
    else if (strcmp(incomingData.tipo, "SCORE") == 0) {
        // Formato enriquecido: SCORE;<orig_mac>;<s1>;<s2>;SALTOS:<n>;VIA:<mac>
        Serial.printf("SCORE;%s;%d;%d;SALTOS:%d;VIA:%s\n", origemFinal, incomingData.score1, incomingData.score2, saltos, viaStr);
    }
    else if (strcmp(incomingData.tipo, "PING") == 0) {
        Serial.printf("PING;%s;SALTOS:%d;VIA:%s\n", origemFinal, saltos, viaStr);
    }
    else if (strcmp(incomingData.tipo, "LED") == 0) {
        // Downlink de controle de LED
        if (strcmp(incomingData.orig_mac, meuMacStr) == 0 || 
            strcmp(incomingData.orig_mac, "FF:FF:FF:FF:FF:FF") == 0 ||
            strcmp(incomingData.orig_mac, "BROADCAST") == 0 ||
            strlen(incomingData.orig_mac) == 0) {
            String corDesejada = String(incomingData.uid);
            corDesejada.trim();
            setCorLed(corDesejada);
        }
    }
    else if (strcmp(incomingData.tipo, "LEDS") == 0) {
        // Downlink de controle independente de ambos os LEDs
        if (strcmp(incomingData.orig_mac, meuMacStr) == 0 || 
            strcmp(incomingData.orig_mac, "FF:FF:FF:FF:FF:FF") == 0 ||
            strcmp(incomingData.orig_mac, "BROADCAST") == 0 ||
            strlen(incomingData.orig_mac) == 0) {
            String param = String(incomingData.uid);
            param.trim();
            String c1 = "", c2 = "";
            int semi = param.indexOf(';');
            if (semi != -1) {
                c1 = param.substring(0, semi);
                c2 = param.substring(semi + 1);
            } else if (param.length() == 2 && isDigit(param[0]) && isDigit(param[1])) {
                c1 = String(param[0]);
                c2 = String(param[1]);
            } else {
                c1 = param;
                c2 = param;
            }
            setBothLeds(c1, c2);
        }
    }
    else if (strcmp(incomingData.tipo, "PIN") == 0) {
        // Controle direto de pino GPIO para diagnóstico e calibração de bancada
        if (strcmp(incomingData.orig_mac, meuMacStr) == 0 || 
            strcmp(incomingData.orig_mac, "FF:FF:FF:FF:FF:FF") == 0 ||
            strcmp(incomingData.orig_mac, "BROADCAST") == 0 ||
            strlen(incomingData.orig_mac) == 0) {
            String param = String(incomingData.uid);
            param.trim();
            if (param.equalsIgnoreCase("CLEAR") || param.equalsIgnoreCase("OFF") || param.equalsIgnoreCase("0")) {
                clearLeds();
            } else {
                int semi = param.indexOf(';');
                if (semi != -1) {
                    int pino = param.substring(0, semi).toInt();
                    int val = param.substring(semi + 1).toInt();
                    pinMode(pino, OUTPUT);
                    digitalWrite(pino, val ? HIGH : LOW);
                } else {
                    int pino = param.toInt();
                    clearLeds();
                    pinMode(pino, OUTPUT);
                    digitalWrite(pino, HIGH);
                }
            }
        }
    }
    else if (strcmp(incomingData.tipo, "DISCOVER") == 0) {
        // Interrogação de Varredura Broadcast: Se este nó não for o coordenador emissor, responde!
        if (strcmp(origemFinal, meuMacStr) != 0) {
            // Pisca LEDs em Azul puro brevemente como feedback visual de presença
            digitalWrite(L1_RED, LOW);
            digitalWrite(L1_GREEN, LOW);
            digitalWrite(L1_BLUE, HIGH);
            digitalWrite(L2_RED_1, LOW);
            digitalWrite(L2_RED_2, LOW);
            digitalWrite(L2_GREEN_1, LOW);
            digitalWrite(L2_GREEN_2, LOW);
            digitalWrite(L2_BLUE, HIGH);

            emAlertaTemporario = true;
            tempoInicioAlertaTemp = millis();
            duracaoAlertaTemp = 250;
            corRetornoAlerta = estadoAtualLed;

            // Jitter aleatório para evitar colisão no ar (CSMA)
            delay(random(15, 60));

            struct_message reply;
            memset(&reply, 0, sizeof(reply));
            strncpy(reply.tipo, "NODE_HERE", sizeof(reply.tipo) - 1);
            strncpy(reply.orig_mac, meuMacStr, sizeof(reply.orig_mac) - 1);
            reply.msg_id = (uint32_t)esp_random();
            reply.hops = 2;

            ensurePeer(broadcastAddress);
            esp_now_send(broadcastAddress, (uint8_t *)&reply, sizeof(reply));
            delay(25);
            reply.msg_id = (uint32_t)esp_random();
            esp_now_send(broadcastAddress, (uint8_t *)&reply, sizeof(reply));
        }
    }
    else if (strcmp(incomingData.tipo, "NODE_HERE") == 0) {
        // Presença de Nó detectada via rádio: O Coordenador repassa para a Serial do PC
        Serial.printf("DISCOVERED;%s;SALTOS:%d;VIA:%s\n", origemFinal, saltos, viaStr);
    }

    // =========================================================================
    // LÓGICA DE REPETIDOR MESH (MULTI-HOP RELAY)
    // Se o pacote tem saltos restantes e não foi gerado por este nó:
    // =========================================================================
    if (incomingData.hops > 1 && strcmp(incomingData.orig_mac, meuMacStr) != 0) {
        incomingData.hops--;
        // Retransmite em broadcast para alcançar o Coordenador ou próximo nó
        esp_now_send(broadcastAddress, (uint8_t *)&incomingData, sizeof(incomingData));
    }
}

// Trata comandos recebidos pela porta Serial USB (vindos do software do PC)
void processarComandoSerial(const String &cmdRaw) {
    String cmd = cmdRaw;
    cmd.trim();
    if (cmd.length() == 0) return;

    // Ativação automática do Modo Coordenador ao receber comandos do computador
    if (!modoCoordenador) {
        modoCoordenador = true;
        setCorLed(estadoAtualLed);
    }

    // 0. Diagnóstico detalhado de hardware, registradores e barramento SPI
    if (cmd.equalsIgnoreCase("DIAG") || cmd.equalsIgnoreCase("STATUS")) {
        Serial.println("\n=======================================================");
        Serial.println("  RELATÓRIO DE DIAGNÓSTICO DO HARDWARE FÍSICO");
        Serial.println("=======================================================");
        Serial.printf("[DIAG] Endereço MAC Físico: %s\n", meuMacStr);
        Serial.printf("[DIAG] Modo Operacional: %s\n", modoCoordenador ? "COORDENADOR USB (Gateway)" : "NÓ DE MESA");

        // Lê registrador de versão do MFRC522 via SPI
        byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
        Serial.printf("[DIAG] Registrador VersionReg: 0x%02X ", v);
        if (v == 0x92) {
            Serial.println("-> [OK]: MFRC522 Versão 2.0 Oficial!");
        } else if (v == 0x91) {
            Serial.println("-> [OK]: MFRC522 Versão 1.0 Oficial!");
        } else if (v == 0x88 || v == 0x90 || v == 0x12) {
            Serial.println("-> [OK]: MFRC522 Clone Compatível operacional.");
        } else if (v == 0x00) {
            Serial.println("-> [FALHA 0x00]: SPI não responde! Pinos MISO/MOSI/SCK/SDA desconectados ou em curto com GND.");
        } else if (v == 0xFF) {
            Serial.println("-> [FALHA 0xFF]: Barramento aberto! Linha MISO flutuando em 3.3V ou chip sem clock.");
        } else {
            Serial.printf("-> [AVISO]: Código 0x%02X desconhecido\n", v);
        }

        // Diagnóstico do pino de interrupção IRQ (GPIO 22)
        int irqNivel = digitalRead(IRQ_PIN);
        Serial.printf("[DIAG] Pino IRQ (GPIO 22): Nível %d (%s)\n", irqNivel, irqNivel ? "ALTO (Repouso normal)" : "BAIXO (Disparado/Curto)");
        Serial.printf("[DIAG] Barramento SPI: SDA=15, SCK=18, MOSI=23, MISO=19, RST=4, IRQ=22\n");
        Serial.println("[DIAG_END]");
        Serial.println("=======================================================\n");
        return;
    }

    // 1. Handshake de presença do Coordenador
    if (cmd.equalsIgnoreCase("PING")) {
        Serial.printf("PONG;COORDINATOR;ONLINE;MAC:%s\n", meuMacStr);
        return;
    }

    // Handshake direto de LED único local via Serial: LED;<COR>
    if (cmd.startsWith("LED;")) {
        String cor = cmd.substring(4);
        cor.trim();
        setCorLed(cor);
        Serial.printf("[LOCAL_LED];%s\n", cor.c_str());
        return;
    }

    // Handshake direto de LED duplo independente via Serial: LEDS;<C1>;<C2> ou LEDS;<DIGITOS>
    // Exemplos: LEDS;2;1 | LEDS;21 | LEDS;13 | LEDS;RED;BLUE
    if (cmd.startsWith("LEDS;")) {
        String param = cmd.substring(5);
        param.trim();
        String c1 = "", c2 = "";
        int semi = param.indexOf(';');
        if (semi != -1) {
            c1 = param.substring(0, semi);
            c2 = param.substring(semi + 1);
        } else if (param.length() == 2 && isDigit(param[0]) && isDigit(param[1])) {
            c1 = String(param[0]);
            c2 = String(param[1]);
        } else {
            c1 = param;
            c2 = param;
        }
        setBothLeds(c1, c2);
        Serial.printf("[LOCAL_LEDS];L1=%s;L2=%s\n", c1.c_str(), c2.c_str());
        return;
    }

    // Controle direto de pino GPIO individual para calibração e diagnóstico de bancada:
    // Exemplos: PIN;25 (liga apenas GPIO 25 e apaga o resto) | PIN;25;1 | PIN;25;0 | PIN;CLEAR
    if (cmd.startsWith("PIN;")) {
        String param = cmd.substring(4);
        param.trim();
        if (param.equalsIgnoreCase("CLEAR") || param.equalsIgnoreCase("OFF") || param.equalsIgnoreCase("0")) {
            clearLeds();
            Serial.println("[PIN_OK];ALL_OFF");
            return;
        }
        int semi = param.indexOf(';');
        if (semi != -1) {
            int pino = param.substring(0, semi).toInt();
            int val = param.substring(semi + 1).toInt();
            pinMode(pino, OUTPUT);
            digitalWrite(pino, val ? HIGH : LOW);
            Serial.printf("[PIN_OK];GPIO_%d=%d\n", pino, val);
            return;
        } else {
            int pino = param.toInt();
            clearLeds();
            pinMode(pino, OUTPUT);
            digitalWrite(pino, HIGH);
            Serial.printf("[PIN_OK];ONLY_GPIO_%d=1\n", pino);
            return;
        }
    }

    // 2. Varredura e Mapeamento Ativo de Nós Repórteres (Broadcast Discovery)
    if (cmd.equalsIgnoreCase("DISCOVER") || cmd.equalsIgnoreCase("SCAN")) {
        Serial.printf("DISCOVER_START;%s\n", meuMacStr);

        memset(&outgoingData, 0, sizeof(outgoingData));
        strncpy(outgoingData.tipo, "DISCOVER", sizeof(outgoingData.tipo) - 1);
        strncpy(outgoingData.orig_mac, meuMacStr, sizeof(outgoingData.orig_mac) - 1);
        outgoingData.hops = 2;

        ensurePeer(broadcastAddress);
        for (int p = 0; p < 3; p++) {
            outgoingData.msg_id = (uint32_t)esp_random();
            esp_now_send(broadcastAddress, (uint8_t *)&outgoingData, sizeof(outgoingData));
            delay(40);
        }
        return;
    }

    // 3. Barreira Virtual de Rádio (Modo Demonstração Mesh para TCC)
    if (cmd.startsWith("BARREIRA;")) {
        if (cmd.indexOf("ON") != -1) {
            barreiraAtiva = true;
            int lastSemi = cmd.lastIndexOf(';');
            if (lastSemi != -1 && lastSemi > 9) {
                String bMac = cmd.substring(lastSemi + 1);
                bMac.trim();
                bMac.toUpperCase();
                strncpy(macBloqueadoDireto, bMac.c_str(), sizeof(macBloqueadoDireto) - 1);
            } else {
                macBloqueadoDireto[0] = '\0';
            }
            Serial.printf("[BARREIRA];ATIVADA;%s\n", macBloqueadoDireto);
        } else {
            barreiraAtiva = false;
            macBloqueadoDireto[0] = '\0';
            Serial.println("[BARREIRA];DESATIVADA");
        }
        return;
    }

    // 4. Downlink para nós de mesa: SEND;<target_mac>;<comando>;<param>
    // Exemplo: SEND;00:70:07:26:E1:70;LED;YELLOW
    // Exemplo: SEND;FF:FF:FF:FF:FF:FF;LEDS;2;1
    // Exemplo: SEND;FF:FF:FF:FF:FF:FF;PIN;25
    if (cmd.startsWith("SEND;")) {
        int firstSemi = cmd.indexOf(';');
        int secondSemi = cmd.indexOf(';', firstSemi + 1);
        int thirdSemi = cmd.indexOf(';', secondSemi + 1);

        if (secondSemi != -1) {
            String targetMacStr = cmd.substring(firstSemi + 1, secondSemi);
            targetMacStr.trim();
            targetMacStr.toUpperCase();

            String subCmd = (thirdSemi != -1) ? cmd.substring(secondSemi + 1, thirdSemi) : cmd.substring(secondSemi + 1);
            subCmd.trim();

            String param = (thirdSemi != -1) ? cmd.substring(thirdSemi + 1) : "";
            param.trim();

            // Se o comando for para este próprio nó (ou broadcast geral), aplica localmente!
            if (targetMacStr.equalsIgnoreCase(meuMacStr) || 
                targetMacStr.equalsIgnoreCase("FF:FF:FF:FF:FF:FF") || 
                targetMacStr.equalsIgnoreCase("BROADCAST")) {
                if (subCmd.equalsIgnoreCase("LED")) {
                    setCorLed(param);
                } else if (subCmd.equalsIgnoreCase("LEDS")) {
                    String c1 = "", c2 = "";
                    int semi = param.indexOf(';');
                    if (semi != -1) {
                        c1 = param.substring(0, semi);
                        c2 = param.substring(semi + 1);
                    } else if (param.length() == 2 && isDigit(param[0]) && isDigit(param[1])) {
                        c1 = String(param[0]);
                        c2 = String(param[1]);
                    } else {
                        c1 = param;
                        c2 = param;
                    }
                    setBothLeds(c1, c2);
                } else if (subCmd.equalsIgnoreCase("PIN")) {
                    if (param.equalsIgnoreCase("CLEAR") || param.equalsIgnoreCase("OFF") || param.equalsIgnoreCase("0")) {
                        clearLeds();
                    } else {
                        int semi = param.indexOf(';');
                        if (semi != -1) {
                            int pino = param.substring(0, semi).toInt();
                            int val = param.substring(semi + 1).toInt();
                            pinMode(pino, OUTPUT);
                            digitalWrite(pino, val ? HIGH : LOW);
                        } else {
                            int pino = param.toInt();
                            clearLeds();
                            pinMode(pino, OUTPUT);
                            digitalWrite(pino, HIGH);
                        }
                    }
                }
            }

            // Despacha também pelo rádio ESP-NOW na malha para alcançar mesas remotas
            memset(&outgoingData, 0, sizeof(outgoingData));
            strncpy(outgoingData.tipo, subCmd.c_str(), sizeof(outgoingData.tipo) - 1);
            strncpy(outgoingData.uid, param.c_str(), sizeof(outgoingData.uid) - 1);
            outgoingData.msg_id = (uint32_t)esp_random();
            outgoingData.hops = 3;
            strncpy(outgoingData.orig_mac, targetMacStr.c_str(), sizeof(outgoingData.orig_mac) - 1);

            registrarMsgProcessada(outgoingData.msg_id);
            esp_err_t res = esp_now_send(broadcastAddress, (uint8_t *)&outgoingData, sizeof(outgoingData));
            if (res == ESP_OK) {
                Serial.printf("[DOWNLINK_OK];%s;%s;%s\n", targetMacStr.c_str(), subCmd.c_str(), param.c_str());
            } else {
                Serial.printf("[DOWNLINK_FAIL];%s\n", targetMacStr.c_str());
            }
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(400);

    // Inicialização dos pinos de LEDs RGB como saída
    pinMode(L1_RED, OUTPUT);
    pinMode(L1_GREEN, OUTPUT);
    pinMode(L1_BLUE, OUTPUT);

    pinMode(L2_RED_1, OUTPUT);
    pinMode(L2_RED_2, OUTPUT);
    pinMode(L2_GREEN_1, OUTPUT);
    pinMode(L2_GREEN_2, OUTPUT);
    pinMode(L2_BLUE, OUTPUT);

    // Estado inicial: LEDs em AMARELO brilhante (Aguardando Atletas / Pronto)
    setCorLed("YELLOW");

    // Configuração Wi-Fi em modo Station para rádio ESP-NOW
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(40);

    // Fixa o canal do rádio Wi-Fi no canal 1 (interoperabilidade determinística no salão)
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);

    // Leitura garantida do endereço MAC físico diretamente dos registradores eFuse do chip
    uint8_t baseMac[6];
    esp_err_t errMac = esp_read_mac(baseMac, ESP_MAC_WIFI_STA);
    if (errMac != ESP_OK || (baseMac[0] == 0 && baseMac[1] == 0 && baseMac[2] == 0 && baseMac[3] == 0 && baseMac[4] == 0 && baseMac[5] == 0)) {
        esp_efuse_mac_get_default(baseMac);
    }
    snprintf(meuMacStr, sizeof(meuMacStr), "%02X:%02X:%02X:%02X:%02X:%02X",
             baseMac[0], baseMac[1], baseMac[2], baseMac[3], baseMac[4], baseMac[5]);

    // Fallback adicional via API WiFi do Arduino caso o buffer retorne zerado
    if (strcmp(meuMacStr, "00:00:00:00:00:00") == 0 || strlen(meuMacStr) < 17) {
        String mac = WiFi.macAddress();
        if (mac.length() >= 17 && mac != "00:00:00:00:00:00") {
            strncpy(meuMacStr, mac.c_str(), sizeof(meuMacStr) - 1);
        }
    }

    Serial.println("\n=======================================================");
    Serial.println("  AUTOREPORTER: FIRMWARE UNIFICADO (NÓ & COORDENADOR) ");
    Serial.println("=======================================================");
    Serial.printf("[HARDWARE] Endereço MAC Físico: %s\n", meuMacStr);

    // Configuração do pino físico de interrupção IRQ (GPIO 22)
    pinMode(IRQ_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(IRQ_PIN), rfid_isr, FALLING);

    // Barramento SPI do leitor RFID MFRC522 (Pinos canônicos)
    SPI.begin(18, 19, 23, SS_PIN); // SCK=18, MISO=19, MOSI=23, SS=15
    delay(40);
    mfrc522.PCD_Init();
    delay(40);

    // Configura o chip MFRC522 para disparar sinal no pino IRQ ao detectar presença
    mfrc522.PCD_WriteRegister(mfrc522.ComIEnReg, 0xA0); // 0x80 (IRqInv) | 0x20 (RxIEn)
    mfrc522.PCD_WriteRegister(mfrc522.DivIEnReg, 0x00);
    mfrc522.PCD_WriteRegister(mfrc522.ComIrqReg, 0x7F); // Limpa interrupções pendentes

    // Ganho máximo da antena (48 dB) para leitura estável de cartões e chaveiros
    mfrc522.PCD_SetAntennaGain(MFRC522::RxGain_max);
    mfrc522.PCD_AntennaOn();

    byte v = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
    Serial.printf("[HARDWARE] Versão MFRC522: 0x%02X\n", v);
    if (v == 0x00 || v == 0xFF) {
        Serial.println("[AVISO] Leitor RFID não detectado! Verifique a fiação SPI.");
    } else {
        Serial.println("[HARDWARE] Leitor RFID MFRC522 operacional.");
    }

    // Inicialização do rádio ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("[ERROR] Falha ao inicializar ESP-NOW.");
        setCorLed("RED");
        return;
    }

    esp_now_register_send_cb(OnDataSent);
    esp_now_register_recv_cb(OnDataRecv);

    ensurePeer(broadcastAddress);

    // Anúncio autônomo de boot para a rede de rádio (Informa presença ao Coordenador)
    memset(&outgoingData, 0, sizeof(outgoingData));
    strncpy(outgoingData.tipo, "NODE_HERE", sizeof(outgoingData.tipo) - 1);
    strncpy(outgoingData.orig_mac, meuMacStr, sizeof(outgoingData.orig_mac) - 1);
    outgoingData.msg_id = (uint32_t)esp_random();
    outgoingData.hops = 2;
    esp_now_send(broadcastAddress, (uint8_t *)&outgoingData, sizeof(outgoingData));

    Serial.println("[SISTEMA] Inicialização concluída. Operando em modo DUAL (USB Gateway + Mesa).");
}

void loop() {
    // -------------------------------------------------------------------------
    // 0. Restauração Automática de Alertas Temporários (CHECKIN1, CHECKIN2, RED)
    // -------------------------------------------------------------------------
    if (emAlertaTemporario && (millis() - tempoInicioAlertaTemp >= duracaoAlertaTemp)) {
        emAlertaTemporario = false;
        setCorLed(corRetornoAlerta.length() > 0 ? corRetornoAlerta : "YELLOW");
    }


    // -------------------------------------------------------------------------
    // 1. Escuta Serial USB UART (Comandos do software do PC quando conectado)
    // -------------------------------------------------------------------------
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        processarComandoSerial(cmd);
    }

    // -------------------------------------------------------------------------
    // 2. Sensoriamento Físico de Cartão RFID (Interrupção por Hardware via IRQ)
    // -------------------------------------------------------------------------
    // Verifica primeiro o disparo da interrupção física na GPIO 22 (Zero Polling desnecessário)
    // Mantém fallback de segurança com PICC_IsNewCardPresent para tolerância a falhas
    if (!rfidInterrupcaoDisparada && !mfrc522.PICC_IsNewCardPresent()) {
        delay(15);
        return;
    }
    rfidInterrupcaoDisparada = false;
    mfrc522.PCD_WriteRegister(mfrc522.ComIrqReg, 0x7F); // Limpa flag de interrupção no MFRC522

    if (!mfrc522.PICC_ReadCardSerial()) {
        delay(15);
        return;
    }

    unsigned long agora = millis();
    if (agora - ultimoTempoLeitura < DEBOUNCE_RFID_MS) {
        mfrc522.PICC_HaltA();
        mfrc522.PCD_StopCrypto1();
        return;
    }
    ultimoTempoLeitura = agora;

    // Extrai o UID em formato Hexadecimal maiúsculo
    String uidStr = "";
    for (byte i = 0; i < mfrc522.uid.size; i++) {
        if (mfrc522.uid.uidByte[i] < 0x10) uidStr += "0";
        uidStr += String(mfrc522.uid.uidByte[i], HEX);
    }
    uidStr.toUpperCase();

    // -------------------------------------------------------------------------
    // 3. Feedback Visual Imediato de Leitura (Pulso puro em Azul sem mistura)
    // -------------------------------------------------------------------------
    digitalWrite(L2_RED_1, LOW);
    digitalWrite(L2_RED_2, LOW);
    digitalWrite(L2_GREEN_1, LOW);
    digitalWrite(L2_GREEN_2, LOW);
    digitalWrite(L2_BLUE, HIGH);

    // -------------------------------------------------------------------------
    // 4. Despacho Serial Local (Se estiver conectado na USB do computador)
    // -------------------------------------------------------------------------
    Serial.printf("RFID;%s;%s;LOCAL;SALTOS:0;VIA:LOCAL\n", uidStr.c_str(), meuMacStr);

    // -------------------------------------------------------------------------
    // 5. Despacho de Rádio ESP-NOW (Para Coordenador remoto ou nós na malha)
    // -------------------------------------------------------------------------
    memset(&myData, 0, sizeof(myData));
    strcpy(myData.tipo, "RFID");
    strncpy(myData.uid, uidStr.c_str(), sizeof(myData.uid) - 1);
    strncpy(myData.orig_mac, meuMacStr, sizeof(myData.orig_mac) - 1);
    myData.msg_id = (uint32_t)esp_random();
    myData.hops = 3;

    registrarMsgProcessada(myData.msg_id);
    esp_err_t resTx = esp_now_send(broadcastAddress, (uint8_t *)&myData, sizeof(myData));
    if (resTx != ESP_OK) {
        ensurePeer(broadcastAddress);
        esp_now_send(broadcastAddress, (uint8_t *)&myData, sizeof(myData));
    }

    delay(150);
    setCorLed(estadoAtualLed);

    // Finaliza transação com o cartão
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
}
