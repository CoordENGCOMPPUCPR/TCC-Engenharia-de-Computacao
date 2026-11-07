#include <RadioLib.h>
#define LORA_NSS   5
#define LORA_DIO0  26
#define LORA_RST   14
#define LED_STATUS 2

SX1276 radio = new Module(LORA_NSS, LORA_DIO0, LORA_RST, RADIOLIB_NC);

const char *VACA_ID = "teste_garrafa"; // ID da vaca
const char  MEMBRO  = 'U';   // 'E', 'D' ou 'U'

const int PINOS_NTC[] = {34, 35, 36, 32, 33};
const int QTD_NTC     = 5;

const float R_FIXO    = 10000.0;
const float R0        = 10000.0;
const float BETA      = 3380.0;
const float T0_KELVIN = 298.15;
const float VCC_MV    = 3300.0;

const int OVERSAMPLING = 32;

const unsigned long INTERVALO_ENVIO_MS = 5000;

unsigned long seq = 0;
unsigned long ultimoEnvio = 0;

bool identificacaoValida() {
  size_t n = strlen(VACA_ID);
  if (n < 1 || n > 15) return false;
  for (size_t i = 0; i < n; i++) {
    char c = VACA_ID[i];
    bool ok = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') || c == '_' || c == '-';
    if (!ok) return false;
  }
  return (MEMBRO == 'E' || MEMBRO == 'D' || MEMBRO == 'U');
}

float lerTensaoMediaMv(int pino) {
  long soma = 0;
  for (int i = 0; i < OVERSAMPLING; i++) {
    soma += analogReadMilliVolts(pino);
    delayMicroseconds(100);
  }
  return (float)soma / OVERSAMPLING;
}

float tensaoParaResistencia(float v_mv) {
  if (v_mv >= VCC_MV || v_mv <= 0) return -1.0;
  return R_FIXO * v_mv / (VCC_MV - v_mv);
}

float resistenciaParaTemperaturaC(float r_ntc) {
  if (r_ntc <= 0) return NAN;
  float inv_t = (1.0 / T0_KELVIN) + (1.0 / BETA) * log(r_ntc / R0);
  return (1.0 / inv_t) - 273.15;
}

void setup() {
  pinMode(LED_STATUS, OUTPUT);
  digitalWrite(LED_STATUS, LOW);

  Serial.begin(115200);
  while (!Serial) { delay(10); }

  Serial.println("=== NO SENSOR (TX) v2 - 5x NTC + LoRa ===");

  if (!identificacaoValida()) {
    Serial.println("ERRO: VACA_ID/MEMBRO invalido (1-15 chars [A-Za-z0-9_-]; membro E/D/U). Parado.");
    while (true) { delay(1000); }
  }
  Serial.print("Identificacao: vaca=");
  Serial.print(VACA_ID);
  Serial.print(" membro=");
  Serial.println(MEMBRO);

  for (int i = 0; i < QTD_NTC; i++) {
    analogSetPinAttenuation(PINOS_NTC[i], ADC_11db);
  }

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
  radio.setOutputPower(14);

  Serial.print("TX pronto. Enviando a cada ");
  Serial.print(INTERVALO_ENVIO_MS / 1000);
  Serial.println("s. Formato: S;vaca;membro;seq;t1..t5");
}

void loop() {
  if (millis() - ultimoEnvio < INTERVALO_ENVIO_MS) return;
  ultimoEnvio = millis();

  String payload = "S;";
  payload += VACA_ID;
  payload += ';';
  payload += MEMBRO;
  payload += ';';
  payload += seq;

  for (int i = 0; i < QTD_NTC; i++) {
    float v_mv   = lerTensaoMediaMv(PINOS_NTC[i]);
    float r_ntc  = tensaoParaResistencia(v_mv);
    float temp_c = resistenciaParaTemperaturaC(r_ntc);

    payload += ';';
    if (isnan(temp_c)) {
      payload += "ERR";
    } else {
      payload += String(temp_c, 2);
    }
  }

  digitalWrite(LED_STATUS, HIGH);
  int state = radio.transmit(payload);
  digitalWrite(LED_STATUS, LOW);

  Serial.print("[TX #");
  Serial.print(seq);
  Serial.print("] ");
  Serial.print(payload);
  if (state == RADIOLIB_ERR_NONE) {
    Serial.println(" ... OK");
  } else {
    Serial.print(" ... FALHA, codigo ");
    Serial.println(state);
  }

  seq++;
}
