// M6 - BPM y variabilidad de la frecuencia cardiaca (HRV) a partir de los RR del detector.
//
//   1. Rechazo de artefactos: un RR fuera de 300-2000 ms, o que se aleje más de un 30 % del
//      último RR válido, se descarta. Con un solo RR erróneo (un latido perdido da un RR
//      doble, +100 %; uno de más lo parte, -50 %) el RMSSD se dispara. El plan proponía un
//      20 %, pero en las grabaciones reales la arritmia respiratoria llega a cambiar el RR
//      un 25,5 % de un latido al siguiente. Comparar con la mediana de los últimos 5 es
//      peor: cuando el ritmo sube o baja varios latidos seguidos se separa hasta un 42 %.
//      Sin RR válidos previos (al arrancar o tras reiniciar) no hay referencia: el primer RR
//      solo se acepta si coincide (+-30 %) con el anterior. Así un primer RR erróneo (p. ej.
//      un latido perdido) no se convierte en referencia y no hace rechazar los buenos.
//      Si aun así se rechazan 5 seguidos, la referencia estaba mal (el ritmo ha cambiado de
//      verdad): se reinicia todo y el último RR pasa a ser el candidato.
//   2. Ventana deslizante con los últimos 30 RR válidos (~30 s):
//        SDNN  = sqrt( sum (RR_i - media)^2 / (N - 1) )
//        RMSSD = sqrt( sum (RR_i+1 - RR_i)^2 / (M - 1) ), M - 1 diferencias entre RR contiguos
//      Solo cuentan las diferencias entre RR seguidos de verdad: si entre dos RR válidos
//      hubo uno rechazado, esa diferencia no se usa.
//   3. BPM = 60000 / media de los últimos 8 RR válidos.
//
// Aritmética entera exacta (uint32_t) hasta la raíz final: con N <= 30 y RR <= 2000 ms,
// N * sum(RR^2) <= 3,6e9 < 2^32.
//
// Sin dependencias de Arduino: también se compila en el PC (pc/test_detector.cpp).
#pragma once
#include <stdint.h>

class Hrv {
public:
  enum Resultado : uint8_t { VALIDO, SIN_RR, FUERA_RANGO, ARTEFACTO };

  Hrv() { reinicia(); }
  void reinicia();

  // rr = 0 significa "latido sin RR" (el primero tras perder la señal): rompe la
  // contigüidad para el RMSSD.
  Resultado nuevoRR(uint16_t rr);

  uint16_t bpmX10() const { return bpmX10_; }     // 0 hasta tener un RR válido
  uint16_t rmssdX10() const { return rmssdX10_; } // 0 hasta tener N_MIN RR válidos
  uint16_t sdnnX10() const { return sdnnX10_; }
  uint8_t n() const { return n_; }                // RR válidos en la ventana

  static const uint8_t VENTANA = 30;
  static const uint8_t N_MIN = 10;

private:
  static const uint8_t N_BPM = 8;
  static const uint8_t RECHAZOS_MAX = 5;

  void calcula();
  static bool parecidos(uint16_t rr, uint16_t ref);   // |rr - ref| <= 30 % de ref

  uint16_t rr_[VENTANA];     // ventana circular de RR válidos
  bool contiguo_[VENTANA];   // el RR anterior en la ventana es el latido inmediatamente previo
  uint8_t pos_, n_;
  bool ultimoValido_;        // el último RR recibido fue válido
  uint8_t rechazos_;
  uint16_t candidato_;       // sin RR válidos: último RR recibido, para confirmar el primero

  uint16_t bpmX10_, rmssdX10_, sdnnX10_;
};
