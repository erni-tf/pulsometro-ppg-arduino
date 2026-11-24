// Pulsómetro: adquisición (M3) + detección de latidos (M5) + BPM y HRV (M6) + estado (M7).
//
// Protocolo serie (115200 baudios), una línea por mensaje:
//   S,<t_ms>,<adc>                                      señal filtrada (media de 20 ms), 100 Hz
//   B,<t_ms>,<rr_ms>,<res>,<bpm>,<rmssd>,<sdnn>,<est>   latido:
//        t_ms   instante del pico; rr_ms RR con el latido anterior (0 si no hay)
//        res    0 RR válido, 1 sin RR, 2 fuera de 300-2000 ms, 3 artefacto (> 30 % del anterior)
//        bpm    media de los últimos 8 RR válidos; rmssd, sdnn en ms, ventana de 30 RR
//               válidos (0 hasta tener 10). Con una cifra decimal.
//        est    0 sin calibrar, 1 calibrando, 2 relajado, 3 normal, 4 estrés
//   I,<texto>                                           información; estadísticas cada 5 s
// Órdenes del PC: c = calibrar (2 min en reposo), r = reiniciar detector y HRV,
//   b<hr0X10>,<rmssd0X10> = cargar una línea base guardada en el PC (perfil con nombre),
//   o = olvidar la línea base (vuelve a "sin calibrar", también tras reiniciar).
// El pulsador de D2 (a GND, pull-up interno) también inicia la calibración.
// La línea base se guarda en la EEPROM: sobrevive al reinicio que provoca abrir el puerto.
// El LED integrado (D13) se enciende 50 ms con cada latido.
#include <EEPROM.h>

#include "adquisicion.h"
#include "detector.h"
#include "estado.h"
#include "hrv.h"

const uint8_t PIN_LED = LED_BUILTIN;    // D13
const uint8_t PIN_PULSADOR = 2;         // D2
const uint8_t DIEZMADO = 5;             // 500 Hz / 5 = 100 Hz hacia el PC
const uint16_t LED_MS = 50;
const uint16_t INFORME_MS = 5000;
const uint16_t REBOTE_MS = 50;

struct LineaBase {                      // lo que se guarda en la EEPROM (dirección 0)
  uint16_t magia;
  uint16_t hr0X10;
  uint16_t rmssd0X10;
};
const uint16_t MAGIA = 0x5052;          // marca de "línea base válida"

Detector detector(PERIODO_MUESTREO_MS);
Hrv hrv;
Estado estado;
Hrv::Resultado resAnterior = Hrv::SIN_RR;
uint32_t nAhora = 0;                    // índice de la última muestra procesada
uint32_t ultimoInforme = 0;
uint32_t ledEncendido = 0;
bool ledActivo = false;
bool pulsadorAnterior = HIGH;
uint32_t cambioPulsador = 0;

void imprimeDecima(uint16_t x10) {      // 123 -> "12.3", sin coma flotante
  Serial.print(x10 / 10);
  Serial.print('.');
  Serial.print(x10 % 10);
}

void imprimeLineaBase(const __FlashStringHelper* titulo) {
  Serial.print(F("I,"));
  Serial.print(titulo);
  Serial.print(F(",hr0="));
  imprimeDecima(estado.hr0X10());
  Serial.print(F(",rmssd0="));
  imprimeDecima(estado.rmssd0X10());
  Serial.println();
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_PULSADOR, INPUT_PULLUP);
  Serial.begin(115200);
  Serial.setTimeout(50);                // para leer los números de la orden b
  Serial.println(F("I,pulso listo"));
  LineaBase lb;
  EEPROM.get(0, lb);
  if (lb.magia == MAGIA && lb.hr0X10 && lb.rmssd0X10) {
    estado.fijaLineaBase(lb.hr0X10, lb.rmssd0X10);
    imprimeLineaBase(F("linea base guardada"));
  }
  adquisicionInicia();
}

void enviaLatido(Hrv::Resultado res) {
  Serial.print(F("B,"));
  Serial.print(detector.tLatidoMs());
  Serial.print(',');
  Serial.print(detector.rrMs());
  Serial.print(',');
  Serial.print((uint8_t)res);
  Serial.print(',');
  imprimeDecima(hrv.bpmX10());
  Serial.print(',');
  imprimeDecima(hrv.rmssdX10());
  Serial.print(',');
  imprimeDecima(hrv.sdnnX10());
  Serial.print(',');
  Serial.println((uint8_t)estado.clase());
}

void guardaLineaBase() {
  LineaBase lb = {MAGIA, estado.hr0X10(), estado.rmssd0X10()};
  EEPROM.put(0, lb);                    // ~3,3 ms por byte: solo al cambiar la línea base
}

void calibra() {
  estado.iniciaCalibracion(nAhora * PERIODO_MUESTREO_MS);
  Serial.print(F("I,calibrando,"));
  Serial.println(Estado::CALIBRACION_MS / 1000);
}

void latido() {
  Hrv::Resultado res = hrv.nuevoRR(detector.rrMs());
  bool valido = res == Hrv::VALIDO;
  if (estado.nuevoLatido(detector.tLatidoMs(), detector.rrMs(), valido,
                         valido && resAnterior == Hrv::VALIDO, hrv.bpmX10(), hrv.rmssdX10(),
                         hrv.n())) {
    guardaLineaBase();
    imprimeLineaBase(F("calibrado"));
  }
  resAnterior = res;
  enviaLatido(res);
  digitalWrite(PIN_LED, HIGH);
  ledEncendido = millis();
  ledActivo = true;
}

void atiendeOrdenes(uint32_t ahora) {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'c') {
      calibra();
    } else if (c == 'r') {
      detector.reinicia(nAhora + 1);
      hrv.reinicia();
      resAnterior = Hrv::SIN_RR;
      Serial.println(F("I,reiniciado"));
    } else if (c == 'b') {
      long hr = Serial.parseInt();      // los dígitos ya han llegado: no espera
      long rm = Serial.parseInt();
      if (hr >= 300 && hr <= 2000 && rm > 0 && rm <= 3000) {   // 30-200 BPM, 0-300 ms
        estado.fijaLineaBase((uint16_t)hr, (uint16_t)rm);
        guardaLineaBase();
        imprimeLineaBase(F("linea base cargada"));
      } else {
        Serial.println(F("I,linea base no valida"));
      }
    } else if (c == 'o') {               // olvidar la línea base (también en la EEPROM)
      estado.olvidaLineaBase();
      guardaLineaBase();                  // con ceros: al arrancar no se carga
      Serial.println(F("I,linea base borrada"));
    }
  }
  // Pulsador con antirrebote: cuenta el flanco de bajada si el nivel se mantiene 50 ms.
  bool nivel = digitalRead(PIN_PULSADOR);
  if (nivel != pulsadorAnterior && ahora - cambioPulsador >= REBOTE_MS) {
    cambioPulsador = ahora;
    pulsadorAnterior = nivel;
    if (nivel == LOW) calibra();
  }
}

void loop() {
  uint16_t x;
  uint32_t n;
  bool perdida;
  while (adquisicionLee(x, n, perdida)) {
    nAhora = n;
    if (perdida) {                      // con huecos el RR no sería fiable
      detector.reinicia(n);
      resAnterior = Hrv::SIN_RR;
    }
    if (detector.procesa(x, n)) latido();
    if (n % DIEZMADO == 0) {
      Serial.print(F("S,"));
      Serial.print(n * PERIODO_MUESTREO_MS);
      Serial.print(',');
      Serial.println((detector.filtrada() + 5) / 10);   // décimas de LSB -> LSB redondeado
    }
  }

  uint32_t ahora = millis();
  atiendeOrdenes(ahora);
  if (ledActivo && ahora - ledEncendido >= LED_MS) {
    digitalWrite(PIN_LED, LOW);
    ledActivo = false;
  }
  if (ahora - ultimoInforme >= INFORME_MS) {
    ultimoInforme = ahora;
    if (estado.clase() == Estado::CALIBRANDO) {
      Serial.print(F("I,calibrando,"));
      Serial.println(estado.restanteS(nAhora * PERIODO_MUESTREO_MS));
    } else {
      Serial.print(F("I,muestras="));
      Serial.print(adquisicionTotal());
      Serial.print(F(",perdidas="));
      Serial.println(adquisicionPerdidas());
    }
  }
}
