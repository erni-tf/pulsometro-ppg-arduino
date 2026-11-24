// M5 - Detector de latidos.
//
// Recibe las muestras crudas del ADC (0-1023) a periodo fijo y, por cada muestra:
//   1. Media móvil de 20 ms (10 muestras a 500 Hz): ceros en 50 Hz y sus múltiplos.
//   2. Umbral adaptativo: u = valle + 0,6 (pico - valle), con pico y valle promediados
//      latido a latido (media exponencial, alfa = 0,25).
//   3. Máquina de estados APRENDIZAJE -> ESPERA -> SUBIDA -> REFRACTARIO -> ESPERA.
//      Refractario adaptativo (60 % del RR medio, entre 250 y 500 ms) y amplitud mínima
//      relativa (40 %) para no contar la onda dícrota. Si pasa 1,5 RR medios sin latido,
//      la amplitud media decae (tau = 1 s) para seguir una bajada brusca de amplitud.
//   4. Instante del latido: punto de máxima pendiente del frente de subida, con la pendiente
//      medida en 20 ms y refinado con interpolación parabólica (puntos a +-20 ms; con
//      vecinos inmediatos el máximo es casi plano y el ruido lo mueve +-10 ms). El pico no sirve: a ritmo
//      alto la onda dícrota se junta con él, la cima se achata y su instante "baila"
//      (en una grabación con estrés, a ~100 BPM, el RMSSD con el pico salía 67 ms y con la
//      pendiente 37 ms; en reposo ambos coinciden).
//   5. RR entre latidos consecutivos. El BPM y la HRV, con los RR ya validados, los calcula
//      el módulo hrv (M6).
//
// Es C++ sin dependencias de Arduino: el mismo código se compila en el PC
// (pc/test_detector.cpp) para probarlo con grabaciones y señales sintéticas.
#pragma once
#include <stdint.h>

class Detector {
public:
  enum Estado : uint8_t { APRENDIZAJE, ESPERA, SUBIDA, REFRACTARIO };

  // periodoMs: periodo de muestreo (2 en el Nano a 500 Hz, 10 con las grabaciones a 100 Hz).
  explicit Detector(uint8_t periodoMs);

  // n: índice de la muestra (tiempo = n * periodoMs). Si se pierden muestras, n salta y
  // conviene llamar antes a reinicia(). Devuelve true si se confirma un latido.
  bool procesa(uint16_t adc, uint32_t n);
  void reinicia(uint32_t n);

  // Último latido confirmado.
  uint32_t tLatidoMs() const { return tLatidoMs_; }
  uint16_t rrMs() const { return rr_; }          // 0 si no hay RR válido (primer latido)
  // Estado interno, para depurar y para el visor.
  Estado estado() const { return estado_; }
  int16_t filtrada() const { return y_; }        // en décimas de LSB
  int16_t umbral() const { return umbral_; }     // en décimas de LSB

private:
  static const uint8_t FILTRO_MAX = 10;
  static const uint8_t RR_MEDIA = 8;
  static const uint8_t HIST_MAX = 10;   // 20 ms a 500 Hz

  int16_t filtra(uint16_t adc);
  void entraAprendizaje(uint32_t n);
  bool confirmaPico();
  void nuevoValle();
  void siguePendiente(int16_t d, int16_t dHaceK, uint32_t n);
  void actualizaUmbral();
  uint32_t ms(uint32_t muestras) const { return muestras * periodoMs_; }

  uint8_t periodoMs_;

  // Media móvil.
  uint8_t nFiltro_;
  uint16_t anillo_[FILTRO_MAX];
  uint8_t pos_;
  uint16_t suma_;
  bool filtroVacio_;

  // Historial corto de la señal (para la pendiente en 20 ms) y de la pendiente (para la
  // parábola con puntos a +-20 ms de la máxima).
  uint8_t kPendiente_;
  int16_t hist_[HIST_MAX];
  int16_t histD_[HIST_MAX];
  uint8_t posH_;

  // Máquina de estados.
  Estado estado_;
  uint32_t nInicio_;        // inicio del aprendizaje o de la subida
  uint32_t nActividad_;     // último latido (o fin del aprendizaje), para el tiempo sin latido
  int16_t aprMin_, aprMax_;
  float picoMedio_, valleMedio_;
  int16_t umbral_;
  int16_t valle_;           // mínimo desde el último pico
  int16_t y_, yPrev_;

  // Pico en curso: muestra máxima (amplitud y refractario).
  int16_t yMax_;
  uint32_t nMax_;

  // Máxima pendiente desde el último valle y sus vecinas, para la parábola.
  int16_t dMax_, dAntes_, dDespues_;
  bool tieneDespues_;
  uint32_t nPendiente_;

  // Latido anterior, guardado como muestra entera + fracción para no perder precisión.
  bool hayAnterior_;
  uint32_t nAnterior_;
  float fracAnterior_;

  // Resultados.
  uint32_t tLatidoMs_;
  uint16_t rr_;
  uint16_t rrs_[RR_MEDIA];   // últimos RR, solo para el refractario adaptativo
  uint8_t nRr_, posRr_;
  uint16_t refractarioMs_;   // 60 % del RR medio, entre 250 y 500 ms
  uint16_t decaeDesdeMs_;    // 1,5 RR medios: sin latido desde entonces, el umbral decae
  float decaePorMuestra_;    // periodo / constante de tiempo del decaimiento
};
