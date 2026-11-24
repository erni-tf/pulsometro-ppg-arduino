// Banco de pruebas de M5 (detector) y M6 (hrv) en el PC, con el mismo código que el Nano.
//
// Compilar:  g++ -O2 -Wall -Wextra -I../firmware/pulso -o test_detector test_detector.cpp
//             ../firmware/pulso/detector.cpp ../firmware/pulso/hrv.cpp   (en una línea)
// Uso:       ./test_detector <grabacion.csv> [periodo_ms=10] [latidos.csv] [traza.csv] [calibra]
//
// Lee un CSV t_ms,adc y pasa cada muestra al detector, y cada RR al módulo hrv.
//   latidos.csv: t_ms,rr_ms,resultado,bpm,rmssd,sdnn,estado   (resultado: 0 válido, 1 sin RR,
//                2 fuera de rango, 3 artefacto; estado: 0 sin calibrar, 1 calibrando,
//                2 relajado, 3 normal, 4 estrés), los mismos valores que enviaría el Nano.
//   calibra:     empieza la calibración del M7 con el primer latido (cualquier texto vale;
//                usar "-" en latidos.csv/traza.csv para no escribirlos).
//   traza.csv:   t_ms,y,umbral,estado del detector, para depurar.
// Al final imprime un resumen y los últimos RMSSD/SDNN de la ventana de 30 latidos.
#include <cstdio>
#include <cstdlib>

#include <cstring>

#include "detector.h"
#include "estado.h"
#include "hrv.h"

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr, "uso: %s grabacion.csv [periodo_ms] [latidos.csv] [traza.csv]\n", argv[0]);
    return 1;
  }
  int periodo = argc > 2 ? std::atoi(argv[2]) : 10;
  FILE* f = std::fopen(argv[1], "r");
  if (!f) { std::perror(argv[1]); return 1; }
  FILE* out = argc > 3 && std::strcmp(argv[3], "-") ? std::fopen(argv[3], "w") : nullptr;
  if (out) std::fprintf(out, "t_ms,rr_ms,resultado,bpm,rmssd,sdnn,estado\n");
  FILE* traza = argc > 4 && std::strcmp(argv[4], "-") ? std::fopen(argv[4], "w") : nullptr;
  bool calibra = argc > 5;
  if (traza) std::fprintf(traza, "t_ms,y,umbral,estado\n");

  Detector det(periodo);
  Hrv hrv;
  Estado estado;
  Hrv::Resultado anterior = Hrv::SIN_RR;
  char linea[128];
  std::fgets(linea, sizeof linea, f);           // cabecera
  int latidos = 0, cuenta[4] = {0, 0, 0, 0};
  long tAnterior = -1;
  while (std::fgets(linea, sizeof linea, f)) {
    long t;
    int adc;
    if (std::sscanf(linea, "%ld,%d", &t, &adc) != 2) continue;
    if (tAnterior >= 0 && t - tAnterior != periodo) det.reinicia(t / periodo);
    tAnterior = t;
    bool hay = det.procesa(adc, t / periodo);
    if (traza) std::fprintf(traza, "%ld,%.1f,%.1f,%d\n", t, det.filtrada() / 10.0, det.umbral() / 10.0, det.estado());
    if (!hay) continue;
    latidos++;
    Hrv::Resultado r = hrv.nuevoRR(det.rrMs());
    cuenta[r]++;
    if (calibra && latidos == 1) estado.iniciaCalibracion(det.tLatidoMs());
    if (estado.nuevoLatido(det.tLatidoMs(), det.rrMs(), r == Hrv::VALIDO,
                           r == Hrv::VALIDO && anterior == Hrv::VALIDO, hrv.bpmX10(),
                           hrv.rmssdX10(), hrv.n())) {
      std::printf("# calibrado en t=%.1f s: HR0=%.1f BPM RMSSD0=%.1f ms\n", det.tLatidoMs() / 1000.0,
                  estado.hr0X10() / 10.0, estado.rmssd0X10() / 10.0);
    }
    anterior = r;
    if (out) {
      std::fprintf(out, "%u,%u,%d,%.1f,%.1f,%.1f,%d\n", det.tLatidoMs(), det.rrMs(), r,
                   hrv.bpmX10() / 10.0, hrv.rmssdX10() / 10.0, hrv.sdnnX10() / 10.0,
                   estado.clase());
    }
  }
  std::fclose(f);
  if (out) std::fclose(out);
  if (traza) std::fclose(traza);

  std::printf("# latidos=%d validos=%d sin_rr=%d fuera_rango=%d artefactos=%d | "
              "ultima ventana: n=%u bpm=%.1f rmssd=%.1f ms sdnn=%.1f ms\n",
              latidos, cuenta[0], cuenta[1], cuenta[2], cuenta[3], hrv.n(), hrv.bpmX10() / 10.0,
              hrv.rmssdX10() / 10.0, hrv.sdnnX10() / 10.0);
  return 0;
}
