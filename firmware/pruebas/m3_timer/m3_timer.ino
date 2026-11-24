// M3 - Prueba de adquisición a 500 Hz con interrupción del Timer1.
//
// - La ISR lee A0 cada 2 ms exactos y guarda la muestra en un buffer circular.
// - loop() vacía el buffer y envía 1 de cada 5 muestras (100 Hz) por serie: S,<t_ms>,<adc>
// - Cada 5 s envía estadísticas: I,muestras=<n>,perdidas=<n>
// - D12 está a nivel alto mientras se ejecuta la ISR: con el osciloscopio se ve
//   el periodo de muestreo (2,000 ms) y la duración de la ISR (~110 us).
//
// Prueba sin sensor: potenciómetro de 10 kOhm entre 5V y GND con el cursor en A0.

const uint8_t PIN_SENAL = A0;
const uint8_t PIN_DEBUG = 12;          // PB4 en el ATmega328P
const uint16_t BUF_LEN = 256;          // head/tail de 8 bits dan la vuelta solos a 256
const uint8_t DIEZMADO = 5;            // 500 Hz / 5 = 100 Hz hacia el PC
const uint16_t PERIODO_MS = 2;         // 1 / 500 Hz

volatile uint16_t buf[BUF_LEN];
volatile uint8_t head = 0;
volatile uint32_t nMuestras = 0;       // muestras adquiridas por la ISR

uint8_t tail = 0;
uint32_t nLeidas = 0;                  // muestras procesadas en loop()
uint32_t perdidas = 0;
uint32_t ultimoInforme = 0;

ISR(TIMER1_COMPA_vect) {
  PORTB |= _BV(PB4);                   // D12 alto (más rápido que digitalWrite)
  buf[head] = analogRead(PIN_SENAL);
  head++;
  nMuestras++;
  PORTB &= ~_BV(PB4);                  // D12 bajo
}

void setupTimer1() {
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = _BV(WGM12) | _BV(CS11) | _BV(CS10);  // modo CTC, prescaler 64
  TCNT1 = 0;
  OCR1A = 499;                                    // 16 MHz / 64 / (499 + 1) = 500 Hz
  TIMSK1 = _BV(OCIE1A);                           // interrupción por comparación A
  interrupts();
}

void setup() {
  pinMode(PIN_DEBUG, OUTPUT);
  Serial.begin(115200);
  Serial.println(F("I,M3 adquisicion 500 Hz lista"));
  setupTimer1();
}

void loop() {
  uint8_t h;
  uint32_t n;
  noInterrupts();                      // copia atómica de las variables de la ISR
  h = head;
  n = nMuestras;
  interrupts();

  // Si loop() se ha retrasado más de lo que cabe en el buffer, se han sobrescrito muestras.
  uint32_t pendientes = n - nLeidas;
  if (pendientes > BUF_LEN) {
    uint32_t p = pendientes - BUF_LEN;
    perdidas += p;
    nLeidas += p;
    tail = h;                          // las BUF_LEN más recientes siguen en el buffer
  }

  while (nLeidas < n) {
    uint16_t x = buf[tail];
    tail++;
    nLeidas++;
    if (nLeidas % DIEZMADO == 0) {
      Serial.print('S');
      Serial.print(',');
      Serial.print(nLeidas * PERIODO_MS);  // tiempo exacto según el contador de muestras
      Serial.print(',');
      Serial.println(x);
    }
  }

  uint32_t ahora = millis();
  if (ahora - ultimoInforme >= 5000) {
    ultimoInforme = ahora;
    Serial.print(F("I,muestras="));
    Serial.print(n);
    Serial.print(F(",perdidas="));
    Serial.println(perdidas);
  }
}
