#include "estado.h"

#include <math.h>

namespace {
const uint8_t HISTERESIS_LATIDOS = 10;
const uint8_t N_HRV_MIN = 10;          // el módulo hrv publica RMSSD a partir de 10 RR
}

void Estado::iniciaCalibracion(uint32_t tMs) {
  mostrado_ = CALIBRANDO;
  tInicio_ = tMs;
  nCal_ = nDif_ = 0;
  sumaRr_ = sumaDif2_ = 0;
  rrAnterior_ = 0;
}

void Estado::fijaLineaBase(uint16_t hr0X10, uint16_t rmssd0X10) {
  hr0X10_ = hr0X10;
  rmssd0X10_ = rmssd0X10;
  mostrado_ = candidata_ = NORMAL;
  cuenta_ = 0;
}

void Estado::olvidaLineaBase() {
  hr0X10_ = rmssd0X10_ = 0;
  mostrado_ = SIN_CALIBRAR;
  cuenta_ = 0;
}

uint16_t Estado::restanteS(uint32_t tMs) const {
  if (mostrado_ != CALIBRANDO) return 0;
  uint32_t pasado = tMs - tInicio_;
  return pasado >= CALIBRACION_MS ? 0 : (uint16_t)((CALIBRACION_MS - pasado + 999) / 1000);
}

Estado::Clase Estado::clasifica(uint16_t bpmX10, uint16_t rmssdX10) const {
  // Todo en décimas y en enteros: RMSSD >= 1,15 RMSSD0  <=>  100 RMSSD >= 115 RMSSD0.
  uint32_t r = 100UL * rmssdX10, r0 = rmssd0X10_;
  if (r <= 50 * r0) return ESTRES;
  if (bpmX10 >= hr0X10_ + 150) return ESTRES;
  if (bpmX10 >= hr0X10_ + 100 && r <= 115 * r0) return ESTRES;
  if (r >= 115 * r0 && bpmX10 <= hr0X10_ + 50) return RELAJADO;
  return NORMAL;
}

bool Estado::nuevoLatido(uint32_t tMs, uint16_t rr, bool valido, bool contiguo,
                         uint16_t bpmX10, uint16_t rmssdX10, uint8_t nHrv) {
  if (mostrado_ == SIN_CALIBRAR) return false;

  if (mostrado_ == CALIBRANDO) {
    if (valido) {
      nCal_++;
      sumaRr_ += rr;
      if (contiguo && rrAnterior_) {
        int32_t d = (int32_t)rr - (int32_t)rrAnterior_;
        sumaDif2_ += (uint32_t)(d * d);
        nDif_++;
      }
      rrAnterior_ = rr;
    } else {
      rrAnterior_ = 0;
    }
    if (tMs - tInicio_ >= CALIBRACION_MS && nCal_ >= RR_CALIBRACION && nDif_ > 0) {
      fijaLineaBase((uint16_t)((600000UL * nCal_ + sumaRr_ / 2) / sumaRr_),
                    (uint16_t)(10 * sqrtf((float)sumaDif2_ / nDif_) + 0.5f));
      return true;
    }
    return false;
  }

  if (nHrv < N_HRV_MIN || rmssd0X10_ == 0) return false;
  Clase c = clasifica(bpmX10, rmssdX10);
  if (c == mostrado_) {
    cuenta_ = 0;
  } else if (c == candidata_) {
    if (++cuenta_ >= HISTERESIS_LATIDOS) {
      mostrado_ = c;
      cuenta_ = 0;
    }
  } else {
    candidata_ = c;
    cuenta_ = 1;
  }
  return false;
}
