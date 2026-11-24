// M7 - Indicador de estado {relajado, normal, estrés} respecto a una línea base personal.
//
// La HRV varía mucho entre personas, así que no se usan umbrales absolutos:
//   1. Calibración: 2 min en reposo (y al menos 60 RR válidos). Línea base HR0 (BPM medio)
//      y RMSSD0 (con todas las diferencias entre RR contiguos del periodo).
//   2. Clasificación por latido, con el BPM (8 RR) y el RMSSD (30 RR) del módulo hrv:
//        relajado: RMSSD >= 1,15 RMSSD0 y HR <= HR0 + 5
//        estrés:   (HR >= HR0 + 10 y RMSSD <= 1,15 RMSSD0) o HR >= HR0 + 15
//                  o RMSSD <= 0,50 RMSSD0
//      El plan pedía además RMSSD <= 0,70 RMSSD0 junto al HR alto, pero en las pruebas
//      reales con cálculo mental el pulso subió 12-18 BPM y el RMSSD no bajó (25-32 ms
//      con RMSSD0 = 25): el marcador fiable en ese caso es el HR.
//        normal:   en otro caso
//   3. Histéresis: el estado mostrado solo cambia si el nuevo se mantiene 10 latidos seguidos.
//
// Es un indicador orientativo, no una medida clínica.
// Sin dependencias de Arduino: también se compila en el PC (pc/test_detector.cpp).
#pragma once
#include <stdint.h>

class Estado {
public:
  enum Clase : uint8_t { SIN_CALIBRAR, CALIBRANDO, RELAJADO, NORMAL, ESTRES };

  Estado() : mostrado_(SIN_CALIBRAR), hr0X10_(0), rmssd0X10_(0) {}

  void iniciaCalibracion(uint32_t tMs);
  void fijaLineaBase(uint16_t hr0X10, uint16_t rmssd0X10);   // p. ej. leída de la EEPROM
  void olvidaLineaBase();                                     // vuelve a "sin calibrar"

  // Tras cada latido. valido: el módulo hrv aceptó este RR. contiguo: el latido anterior
  // también fue válido (la diferencia entre ambos vale para el RMSSD). bpmX10, rmssdX10 y
  // nHrv son los valores actuales del módulo hrv. Devuelve true si acaba la calibración.
  bool nuevoLatido(uint32_t tMs, uint16_t rr, bool valido, bool contiguo,
                   uint16_t bpmX10, uint16_t rmssdX10, uint8_t nHrv);

  Clase clase() const { return mostrado_; }
  uint16_t hr0X10() const { return hr0X10_; }
  uint16_t rmssd0X10() const { return rmssd0X10_; }
  uint16_t restanteS(uint32_t tMs) const;   // segundos de calibración que faltan

  static const uint32_t CALIBRACION_MS = 120000;
  static const uint16_t RR_CALIBRACION = 60;

private:
  Clase clasifica(uint16_t bpmX10, uint16_t rmssdX10) const;

  Clase mostrado_, candidata_;
  uint8_t cuenta_;
  uint16_t hr0X10_, rmssd0X10_;

  // Acumuladores de la calibración.
  uint32_t tInicio_;
  uint16_t nCal_, nDif_;
  uint32_t sumaRr_, sumaDif2_;
  uint16_t rrAnterior_;
};
