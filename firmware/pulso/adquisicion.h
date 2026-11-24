// M3 - Adquisición a 500 Hz con el Timer1 (modo CTC) y buffer circular.
//
// La ISR lee A0 cada 2 ms exactos. loop() saca las muestras con adquisicionLee().
// D12 (PB4) está a nivel alto durante la ISR, para medir el muestreo con el osciloscopio.
#pragma once
#include <stdint.h>

const uint8_t PERIODO_MUESTREO_MS = 2;

void adquisicionInicia();

// Saca la siguiente muestra pendiente. n es su índice (tiempo = n * 2 ms).
// Devuelve false si no hay muestras. Si loop() se retrasó más de lo que cabe en el buffer,
// las más antiguas se han perdido: perdida = true y n salta.
bool adquisicionLee(uint16_t& x, uint32_t& n, bool& perdida);

uint32_t adquisicionTotal();     // muestras adquiridas por la ISR
uint32_t adquisicionPerdidas();  // muestras sobrescritas antes de leerlas
