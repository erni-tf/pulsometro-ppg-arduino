#include "detector.h"

namespace {
const uint16_t SAT_BAJO = 3;            // ADC pegado a 0 V o a 5 V: dedo entrando o saliendo
const uint16_t SAT_ALTO = 1020;
const uint16_t VENTANA_FILTRO_MS = 20;  // un periodo de red
const uint16_t PASO_PENDIENTE_MS = 20;  // pendiente = y[n] - y[n - 20 ms]
const uint16_t APRENDIZAJE_MS = 2000;   // ~2 latidos para estimar pico y valle
const uint16_t REFRACTARIO_MS = 250;    // mínimo: limita a 240 BPM
const float REFRACTARIO_FRAC = 0.6f;    // refractario = 60 % del RR medio: tapa la onda dícrota
// Máximo: la onda dícrota llega ~300 ms tras el pico sea cual sea el ritmo. Sin tope, un
// latido perdido (RR doble) alarga el refractario, tapa el latido siguiente y el detector
// se queda enganchado a la mitad del ritmo.
const uint16_t REFRACTARIO_MAX_MS = 500;
const uint16_t SUBIDA_MAX_MS = 800;     // un pico sistólico real dura ~200 ms por encima de u
const uint16_t SIN_LATIDO_MS = 3000;    // < 20 BPM: se ha perdido la señal, se reaprende
const uint16_t RR_MIN_MS = 300;         // 200 BPM
const uint16_t RR_MAX_MS = 2000;        // 30 BPM
const int16_t AMP_MIN = 220;            // 22 LSB = 0,1 V (en décimas de LSB)
const float FRACCION = 0.6f;
const float ALFA = 0.25f;
const float AMP_REL = 0.4f;             // un latido debe tener al menos el 40 % de la amplitud media
// Si pasa 1,5 RR medios sin latido (la amplitud ha bajado de golpe, p. ej. al cambiar la
// presión del dedo), la amplitud media decae hacia el valle con constante de tiempo de 1 s:
// el umbral baja hasta alcanzar los latidos pequeños sin esperar al reaprendizaje de 3 s.
const float DECAE_DESDE_RR = 1.5f;
const float TAU_DECAE_MS = 1000.0f;
const uint16_t RR_INICIAL_MS = 1000;    // RR medio supuesto hasta tener RR reales
}

Detector::Detector(uint8_t periodoMs) : periodoMs_(periodoMs) {
  nFiltro_ = VENTANA_FILTRO_MS / periodoMs;
  if (nFiltro_ < 1) nFiltro_ = 1;
  if (nFiltro_ > FILTRO_MAX) nFiltro_ = FILTRO_MAX;
  kPendiente_ = PASO_PENDIENTE_MS / periodoMs;
  if (kPendiente_ < 1) kPendiente_ = 1;
  if (kPendiente_ > HIST_MAX) kPendiente_ = HIST_MAX;
  nRr_ = posRr_ = 0;
  refractarioMs_ = REFRACTARIO_MS;
  decaeDesdeMs_ = (uint16_t)(DECAE_DESDE_RR * RR_INICIAL_MS);
  decaePorMuestra_ = periodoMs / TAU_DECAE_MS;
  reinicia(0);
}

void Detector::reinicia(uint32_t n) {
  filtroVacio_ = true;
  hayAnterior_ = false;
  tLatidoMs_ = 0;
  rr_ = 0;
  y_ = yPrev_ = 0;
  umbral_ = 0;
  entraAprendizaje(n);
}

int16_t Detector::filtra(uint16_t adc) {
  if (filtroVacio_) {                   // arranque: rellena la ventana con la primera muestra
    for (uint8_t i = 0; i < nFiltro_; i++) anillo_[i] = adc;
    suma_ = adc * nFiltro_;
    pos_ = 0;
    filtroVacio_ = false;
  }
  suma_ = suma_ - anillo_[pos_] + adc;  // media móvil con una resta y una suma por muestra
  anillo_[pos_] = adc;
  pos_ = (pos_ + 1) % nFiltro_;
  return (int16_t)((uint32_t)suma_ * 10 / nFiltro_);
}

void Detector::entraAprendizaje(uint32_t n) {
  estado_ = APRENDIZAJE;
  nInicio_ = n;
  aprMin_ = 32767;
  aprMax_ = -32768;
  dMax_ = 0;
  hayAnterior_ = false;                 // tras perder la señal el siguiente RR no sería real
}

void Detector::actualizaUmbral() {
  umbral_ = (int16_t)(valleMedio_ + FRACCION * (picoMedio_ - valleMedio_));
}

bool Detector::procesa(uint16_t adc, uint32_t n) {
  bool arranque = filtroVacio_;
  y_ = filtra(adc);
  bool latido = false;

  // Historial de las últimas k muestras: hist_[posH_] es la de hace k muestras.
  if (arranque) {
    for (uint8_t i = 0; i < kPendiente_; i++) {
      hist_[i] = y_;
      histD_[i] = 0;
    }
    posH_ = 0;
  }
  int16_t d = y_ - hist_[posH_];        // pendiente en 20 ms, centrada en n - k/2
  int16_t dHaceK = histD_[posH_];
  hist_[posH_] = y_;
  histD_[posH_] = d;
  posH_ = (posH_ + 1) % kPendiente_;

  if (adc <= SAT_BAJO || adc >= SAT_ALTO) {
    entraAprendizaje(n);                // el aprendizaje acaba 2 s después de la última saturación
    yPrev_ = y_;
    return false;
  }

  switch (estado_) {
    case APRENDIZAJE:
      if (y_ < aprMin_) aprMin_ = y_;
      if (y_ > aprMax_) aprMax_ = y_;
      if (ms(n - nInicio_) >= APRENDIZAJE_MS) {
        if (aprMax_ - aprMin_ >= AMP_MIN) {
          picoMedio_ = aprMax_;
          valleMedio_ = aprMin_;
          actualizaUmbral();
          valle_ = y_;
          nActividad_ = n;
          estado_ = ESPERA;
        } else {
          entraAprendizaje(n);          // sin pulso (no hay dedo): sigue aprendiendo
        }
      }
      break;

    case ESPERA:
      if (y_ < valle_) nuevoValle();
      siguePendiente(d, dHaceK, n);
      if (ms(n - nActividad_) > decaeDesdeMs_ && picoMedio_ - valleMedio_ > AMP_MIN) {
        picoMedio_ -= decaePorMuestra_ * (picoMedio_ - valleMedio_);
        actualizaUmbral();
      }
      if (y_ > umbral_ && yPrev_ <= umbral_) {   // cruce de subida, no basta con estar encima
        estado_ = SUBIDA;
        nInicio_ = n;
        yMax_ = y_;
        nMax_ = n;
      }
      break;

    case SUBIDA:
      siguePendiente(d, dHaceK, n);
      if (y_ > yMax_) {
        yMax_ = y_;
        nMax_ = n;
      }
      if (y_ < umbral_) {
        latido = confirmaPico();
        if (latido) {
          nActividad_ = nMax_;
          nuevoValle();
          estado_ = REFRACTARIO;
        } else {
          estado_ = ESPERA;             // pico descartado: se sigue esperando el latido
        }
      } else if (ms(n - nInicio_) > SUBIDA_MAX_MS) {
        entraAprendizaje(n);            // la línea base ha subido: el umbral ya no vale
      }
      break;

    case REFRACTARIO:
      if (y_ < valle_) nuevoValle();
      siguePendiente(d, dHaceK, n);
      if (ms(n - nMax_) >= refractarioMs_) estado_ = ESPERA;
      break;
  }

  if ((estado_ == ESPERA || estado_ == REFRACTARIO) && ms(n - nActividad_) > SIN_LATIDO_MS) {
    entraAprendizaje(n);
  }

  yPrev_ = y_;
  return latido;
}

void Detector::nuevoValle() {
  // La subida de un latido empieza en el último valle: lo anterior (p. ej. la onda dícrota
  // del latido previo) no cuenta para la máxima pendiente.
  valle_ = y_;
  dMax_ = 0;
}

void Detector::siguePendiente(int16_t d, int16_t dHaceK, uint32_t n) {
  if (d > dMax_) {
    dMax_ = d;
    dAntes_ = dHaceK;
    nPendiente_ = n;
    tieneDespues_ = false;
  } else if (!tieneDespues_ && n - nPendiente_ == kPendiente_) {
    dDespues_ = d;
    tieneDespues_ = true;
  }
}

bool Detector::confirmaPico() {
  // Instante = máxima pendiente, refinado con una parábola sobre la pendiente en esa muestra y
  // las situadas k muestras antes y después: delta = k/2 (a - c) / (a - 2b + c), en muestras. La pendiente y[n] - y[n-k] está centrada en
  // n - k/2: se resta para que la marca caiga sobre la señal filtrada.
  if (dMax_ <= 0) return false;         // sin frente de subida no hay latido
  float frac = 0;
  if (tieneDespues_) {
    float a = dAntes_, b = dMax_, c = dDespues_;
    float den = a - 2 * b + c;
    float lim = 0.5f * kPendiente_;
    if (den < 0) frac = lim * (a - c) / den;
    if (frac > lim) frac = lim;
    if (frac < -lim) frac = -lim;
  }
  frac -= 0.5f * kPendiente_;
  uint32_t nLatido = nPendiente_;

  int16_t amp = yMax_ - valle_;
  if (amp < AMP_MIN) return false;      // ruido por encima del umbral, no es un latido
  if (amp < AMP_REL * (picoMedio_ - valleMedio_)) return false;   // onda dícrota o rizado

  float rrf = 0;
  if (hayAnterior_) {
    rrf = ((float)(nLatido - nAnterior_) + frac - fracAnterior_) * periodoMs_;
    if (rrf < RR_MIN_MS) return false;  // pico espurio demasiado cerca del anterior
  }

  // Latido aceptado: adapta pico y valle medios.
  picoMedio_ += ALFA * (yMax_ - picoMedio_);
  valleMedio_ += ALFA * (valle_ - valleMedio_);
  actualizaUmbral();

  rr_ = 0;
  if (hayAnterior_ && rrf <= RR_MAX_MS) {
    rr_ = (uint16_t)(rrf + 0.5f);
    rrs_[posRr_] = rr_;
    posRr_ = (posRr_ + 1) % RR_MEDIA;
    if (nRr_ < RR_MEDIA) nRr_++;
    uint32_t suma = 0;
    for (uint8_t i = 0; i < nRr_; i++) suma += rrs_[i];
    uint16_t r = (uint16_t)(REFRACTARIO_FRAC * suma / nRr_);
    refractarioMs_ = r < REFRACTARIO_MS ? REFRACTARIO_MS : r > REFRACTARIO_MAX_MS ? REFRACTARIO_MAX_MS : r;
    decaeDesdeMs_ = (uint16_t)(DECAE_DESDE_RR * suma / nRr_);
  }

  hayAnterior_ = true;
  nAnterior_ = nLatido;
  fracAnterior_ = frac;
  tLatidoMs_ = (uint32_t)(((float)nLatido + frac) * periodoMs_ + 0.5f);
  return true;
}
