#include <Arduino.h>

#include "adquisicion.h"

namespace {
const uint8_t PIN_SENAL = A0;
const uint8_t PIN_DEBUG = 12;           // PB4
const uint16_t BUF_LEN = 256;           // head/tail de 8 bits dan la vuelta solos a 256

volatile uint16_t buf[BUF_LEN];
volatile uint8_t head = 0;
volatile uint32_t nMuestras = 0;

uint8_t tail = 0;
uint32_t nLeidas = 0;
uint32_t perdidas = 0;
}

ISR(TIMER1_COMPA_vect) {
  PORTB |= _BV(PB4);
  buf[head] = analogRead(PIN_SENAL);
  head++;
  nMuestras++;
  PORTB &= ~_BV(PB4);
}

void adquisicionInicia() {
  pinMode(PIN_DEBUG, OUTPUT);
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = _BV(WGM12) | _BV(CS11) | _BV(CS10);  // CTC, prescaler 64
  TCNT1 = 0;
  OCR1A = 499;                                    // 16 MHz / 64 / 500 = 500 Hz
  TIMSK1 = _BV(OCIE1A);
  interrupts();
}

bool adquisicionLee(uint16_t& x, uint32_t& n, bool& perdida) {
  uint8_t h;
  uint32_t total;
  noInterrupts();                       // copia atómica de las variables de la ISR
  h = head;
  total = nMuestras;
  interrupts();

  perdida = false;
  uint32_t pendientes = total - nLeidas;
  if (pendientes == 0) return false;
  if (pendientes > BUF_LEN) {           // se han sobrescrito muestras sin leer
    uint32_t p = pendientes - BUF_LEN;
    perdidas += p;
    nLeidas += p;
    tail = h;                           // las BUF_LEN más recientes siguen en el buffer
    perdida = true;
  }
  x = buf[tail];
  tail++;
  n = nLeidas;
  nLeidas++;
  return true;
}

uint32_t adquisicionTotal() {
  noInterrupts();
  uint32_t t = nMuestras;
  interrupts();
  return t;
}

uint32_t adquisicionPerdidas() { return perdidas; }
