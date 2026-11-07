#include <RadioLib.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define LORA_NSS   5
#define LORA_DIO0  26
#define LORA_RST   14
#define LED_STATUS 2

SX1276 radio = new Module(LORA_NSS, LORA_DIO0, LORA_RST, RADIOLIB_NC);

const int QTD_NTC = 5;

// ---------------------------------------------------------------------------
// Configuraçoes rede e API
// ---------------------------------------------------------------------------
const char *WIFI_SSID     = "SEU_WIFI";
const char *WIFI_PASSWORD = "SUA_SENHA";

const char *API_URL = "https://tcc-mastite-backend.onrender.com/leituras";
const char *API_KEY = "SUA_API_KEY";

const uint32_t HTTP_TIMEOUT_MS = 15000;

// ---------------------------------------------------------------------------

#define TAM_VACA 16   // 15 caracteres + terminador

struct LeituraPacote {
  char  vaca[TAM_VACA];
  char  membro;           // 'E', 'D' ou 'U'
  long  seq;
  float temps[QTD_NTC];   
  float rssi;
  float snr;
};

#define TAMANHO_FILA 20
QueueHandle_t filaLeituras;

bool decodificaPayload(const String &p, LeituraPacote &out, String temposStr[]) {
  if (!p.startsWith("S;")) return false;

  const int ESPERADO = 3 + QTD_NTC;   // vaca, membro, seq, 5 temps

  // Numero exato de ';' = ESPERADO (um depois do "S" + um entre campos)
  int pontoVirgulas = 0;
  for (unsigned i = 0; i < p.length(); i++) {
    if (p[i] == ';') pontoVirgulas++;
  }
  if (pontoVirgulas != ESPERADO) return false;

  String campos[ESPERADO];
  int inicio = 2;
  for (int n = 0; n < ESPERADO; n++) {
    int idx = p.indexOf(';', inicio);
    String campo = (idx == -1) ? p.substring(inicio) : p.substring(inicio, idx);
    campo.trim();
    if (campo.length() == 0) return false;
    campos[n] = campo;
    inicio = idx + 1;
  }

  // vaca_id: 1-15 chars [A-Za-z0-9_-]
  const String &vaca = campos[0];
  if (vaca.length() < 1 || vaca.length() > TAM_VACA - 1) return false;
  for (unsigned i = 0; i < vaca.length(); i++) {
    char c = vaca[i];
    bool ok = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') || c == '_' || c == '-';
    if (!ok) return false;
  }
  vaca.toCharArray(out.vaca, TAM_VACA);

  // membro: E, D ou U
  if (campos[1].length() != 1) return false;
  char m = campos[1][0];
  if (m != 'E' && m != 'D' && m != 'U') return false;
  out.membro = m;

  out.seq = campos[2].toInt();

  for (int i = 0; i < QTD_NTC; i++) {
    temposStr[i] = campos[3 + i];
  }
  return true;
}

void taskRede(void *parametro) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.println("[REDE] Conectando ao WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    vTaskDelay(pdMS_TO_TICKS(500));
    Serial.print(".");
  }
  Serial.println();
  Serial.print("[REDE] WiFi conectado. IP: ");
  Serial.println(WiFi.localIP());

  LeituraPacote pacote;

  for (;;) {
    if (xQueueReceive(filaLeituras, &pacote, portMAX_DELAY) == pdTRUE) {

      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[REDE] WiFi caiu, tentando reconectar...");
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        uint32_t inicioTentativa = millis();
        while (WiFi.status() != WL_CONNECTED && millis() - inicioTentativa < 10000) {
          vTaskDelay(pdMS_TO_TICKS(300));
        }
        if (WiFi.status() != WL_CONNECTED) {
          Serial.println("[REDE] Falha ao reconectar WiFi. Pacote descartado.");
          continue;
        }
      }

      JsonDocument doc;
      JsonArray arr = doc.to<JsonArray>();

      String vacaStr(pacote.vaca);
      String membroStr(pacote.membro);

      for (int i = 0; i < QTD_NTC; i++) {
        JsonObject item = arr.add<JsonObject>();
        item["vaca_id"] = vacaStr;
        // A API só aceita "E" ou "D"; "U" (bancada) = campo ausente,
        // e o backend grava U por conta própria.
        if (pacote.membro != 'U') {
          item["membro"] = membroStr;
        }
        item["quarto"]  = i + 1;   // indice do sensor (1 a 5)
        if (isnan(pacote.temps[i])) {
          item["temp_raw"] = nullptr;
        } else {
          item["temp_raw"] = pacote.temps[i];
        }
        item["rssi"] = pacote.rssi;
        item["snr"]  = pacote.snr;
      }

      String corpoJson;
      serializeJson(doc, corpoJson);

      WiFiClientSecure client;
      client.setInsecure();

      HTTPClient http;
      http.setTimeout(HTTP_TIMEOUT_MS);

      bool sucesso = false;
      const int MAX_TENTATIVAS = 3;

      for (int tentativa = 1; tentativa <= MAX_TENTATIVAS && !sucesso; tentativa++) {
        if (http.begin(client, API_URL)) {
          http.addHeader("Content-Type", "application/json");
          http.addHeader("X-API-Key", API_KEY);

          int codigoHttp = http.POST(corpoJson);

          if (codigoHttp == 201) {
            Serial.print("[REDE] ");
            Serial.print(pacote.vaca);
            Serial.print('/');
            Serial.print(pacote.membro);
            Serial.print(" seq=");
            Serial.print(pacote.seq);
            Serial.println(" enviado com sucesso.");
            sucesso = true;
          } else {
            Serial.print("[REDE] Tentativa ");
            Serial.print(tentativa);
            Serial.print("/");
            Serial.print(MAX_TENTATIVAS);
            Serial.print(" falhou, HTTP ");
            Serial.print(codigoHttp);
            Serial.print(": ");
            Serial.println(http.getString());
          }
          http.end();
        } else {
          Serial.println("[REDE] Falha ao iniciar conexao HTTP.");
        }

        if (!sucesso && tentativa < MAX_TENTATIVAS) {
          vTaskDelay(pdMS_TO_TICKS(3000));
        }
      }

      if (!sucesso) {
        Serial.print("[REDE] Pacote ");
        Serial.print(pacote.vaca);
        Serial.print('/');
        Serial.print(pacote.membro);
        Serial.print(" seq=");
        Serial.print(pacote.seq);
        Serial.println(" descartado apos esgotar as tentativas.");
      }
    }
  }
}

void setup() {
  pinMode(LED_STATUS, OUTPUT);
  digitalWrite(LED_STATUS, LOW);

  Serial.begin(115200);
  while (!Serial) { delay(10); }

  Serial.println("=== GATEWAY (RX) v2 - 5x NTC via LoRa + envio HTTP ===");

  Serial.print("Inicializando SX1276/RFM95W... ");
  int state = radio.begin(915.0);
  if (state != RADIOLIB_ERR_NONE) {
    Serial.print("FALHOU, codigo ");
    Serial.println(state);
    while (true) { delay(1000); }
  }
  Serial.println("sucesso!");

  radio.setSpreadingFactor(7);
  radio.setBandwidth(125.0);
  radio.setCodingRate(5);
  radio.setSyncWord(0x12);

  filaLeituras = xQueueCreate(TAMANHO_FILA, sizeof(LeituraPacote));
  xTaskCreatePinnedToCore(taskRede, "TaskRede", 8192, NULL, 1, NULL, 0);

  Serial.println("timestamp_ms;vaca;membro;seq;t1;t2;t3;t4;t5;rssi_dbm;snr_db;status");
}

void loop() {
  String payload;
  int state = radio.receive(payload);

  if (state == RADIOLIB_ERR_NONE) {
    float rssi = radio.getRSSI();
    float snr  = radio.getSNR();

    LeituraPacote pacote;
    String temposStr[QTD_NTC];

    if (decodificaPayload(payload, pacote, temposStr)) {
      digitalWrite(LED_STATUS, HIGH);

      pacote.rssi = rssi;
      pacote.snr  = snr;
      for (int i = 0; i < QTD_NTC; i++) {
        if (temposStr[i] == "ERR") {
          pacote.temps[i] = NAN;
        } else {
          pacote.temps[i] = temposStr[i].toFloat();
        }
      }

      if (xQueueSend(filaLeituras, &pacote, 0) != pdTRUE) {
        Serial.println("AVISO: fila cheia, pacote descartado.");
      }

      Serial.print(millis());
      Serial.print(';');
      Serial.print(pacote.vaca);
      Serial.print(';');
      Serial.print(pacote.membro);
      Serial.print(';');
      Serial.print(pacote.seq);
      for (int i = 0; i < QTD_NTC; i++) {
        Serial.print(';');
        Serial.print(temposStr[i]);
      }
      Serial.print(';');
      Serial.print(rssi, 1);
      Serial.print(';');
      Serial.print(snr, 1);
      Serial.println(";OK");

      digitalWrite(LED_STATUS, LOW);
    } else {
      Serial.print(millis());
      Serial.print(";;;;;;;;;");
      Serial.print(rssi, 1);
      Serial.print(';');
      Serial.print(snr, 1);
      Serial.print(";MALFORMADO:");
      Serial.println(payload);
    }

  } else if (state != RADIOLIB_ERR_RX_TIMEOUT) {
    Serial.print(millis());
    Serial.print(";;;;;;;;;;;ERR_");
    Serial.println(state);
  }
}
