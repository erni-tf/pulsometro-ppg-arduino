#include "hrv.h"

#include <math.h>

namespace {
const uint16_t RR_MIN_MS = 300;
const uint16_t RR_MAX_MS = 2000;
const uint8_t TOLERANCIA_PCT = 30;  // cambio real máximo medido latido a latido: 25,5 %
}

void Hrv::reinicia() {
  pos_ = n_ = 0;
  ultimoValido_ = false;
  rechazos_ = 0;
  candidato_ = 0;
  bpmX10_ = rmssdX10_ = sdnnX10_ = 0;
}

Hrv::Resultado Hrv::nuevoRR(uint16_t rr) {
  if (rr == 0) {
    ultimoValido_ = false;
    candidato_ = 0;
    return SIN_RR;
  }
  if (rr < RR_MIN_MS || rr > RR_MAX_MS) {
    ultimoValido_ = false;
    candidato_ = 0;
    return FUERA_RANGO;
  }
  if (n_ == 0) {                        // sin referencia: hace falta que dos RR coincidan
    uint16_t c = candidato_;
    candidato_ = rr;
    ultimoValido_ = false;
    if (!c) return SIN_RR;              // primer RR: aún no hay con qué compararlo
    if (!parecidos(rr, c)) return ARTEFACTO;
  } else if (!parecidos(rr, rr_[(pos_ + VENTANA - 1) % VENTANA])) {   // vs último válido
    ultimoValido_ = false;
    if (++rechazos_ >= RECHAZOS_MAX) {
      reinicia();
      candidato_ = rr;
    }
    return ARTEFACTO;
  }

  rechazos_ = 0;
  rr_[pos_] = rr;
  contiguo_[pos_] = ultimoValido_;
  pos_ = (pos_ + 1) % VENTANA;
  if (n_ < VENTANA) n_++;
  ultimoValido_ = true;
  calcula();
  return VALIDO;
}

bool Hrv::parecidos(uint16_t rr, uint16_t ref) {
  uint16_t dif = rr > ref ? rr - ref : ref - rr;
  return (uint32_t)dif * 100 <= (uint32_t)ref * TOLERANCIA_PCT;
}

void Hrv::calcula() {
  // BPM con los últimos N_BPM RR.
  uint8_t m = n_ < N_BPM ? n_ : N_BPM;
  uint32_t suma = 0;
  for (uint8_t i = 0; i < m; i++) suma += rr_[(pos_ + VENTANA - 1 - i) % VENTANA];
  bpmX10_ = (uint16_t)((600000UL * m + suma / 2) / suma);

  if (n_ < N_MIN) {
    rmssdX10_ = sdnnX10_ = 0;
    return;
  }

  // Recorre la ventana del más antiguo al más reciente.
  uint8_t inicio = (pos_ + VENTANA - n_) % VENTANA;
  uint32_t s1 = 0, s2 = 0, d2 = 0;
  uint8_t nd = 0;
  for (uint8_t k = 0; k < n_; k++) {
    uint8_t i = (inicio + k) % VENTANA;
    uint32_t x = rr_[i];
    s1 += x;
    s2 += x * x;
    if (k > 0 && contiguo_[i]) {        // el primero de la ventana no tiene anterior dentro
      uint8_t ia = (i + VENTANA - 1) % VENTANA;
      int32_t d = (int32_t)rr_[i] - (int32_t)rr_[ia];
      d2 += (uint32_t)(d * d);
      nd++;
    }
  }
  // Varianza exacta en enteros: (N sum x^2 - (sum x)^2) / (N (N - 1)).
  uint32_t num = n_ * s2 - s1 * s1;
  float var = (float)num / ((uint32_t)n_ * (n_ - 1));
  sdnnX10_ = (uint16_t)(10 * sqrtf(var) + 0.5f);
  // RMSSD = sqrt(media de las diferencias al cuadrado). El plan escribe 1/(N-1) con N RR,
  // que es lo mismo: N - 1 diferencias.
  rmssdX10_ = nd ? (uint16_t)(10 * sqrtf((float)d2 / nd) + 0.5f) : 0;
}
