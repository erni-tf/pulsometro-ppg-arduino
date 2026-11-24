"""Señal de pulso sintética con RR conocidos, para validar el detector (M5) y la HRV (M6).

Uso:  python sintetica.py <salida.csv> <rr_verdad.csv> <caso> [periodo_ms=2]
      caso: un número (BPM constante),
            "arritmia" (RR = 800 + 60 sin(2 pi n / 5) ms),
            "alterna"  (RR alternando 800 y 900 ms: RMSSD = 100 ms, SDNN = 50,9 ms con 30 RR),
            "perdidos" (arritmia con 3 latidos muy débiles, que el detector debe perder)
            "protocolo" (M7, 420 s: reposo 0-150 s con RR 850 +- 50 ms, estrés 150-270 s con
                         RR 650 +- 8 ms, relajación 270-420 s con RR 950 +- 90 ms; rampas de 15 s)

Cada latido es una onda sistólica (gaussiana) más una onda dícrota más pequeña, como en
las grabaciones reales. Se añade ruido de red de 50 Hz, ruido blanco y la cuantificación
del ADC. El CSV tiene el mismo formato que las grabaciones (t_ms,adc).
"""
import sys

import numpy as np

PICO_S = 0.15        # retardo del pico sistólico desde el inicio del latido
DICROTA_S = 0.30     # la onda dícrota llega 300 ms después del pico
AMP = 320            # LSB, ~1,5 V p-p como con G = 68
DURACION_S = 120
# Protocolo M7: (inicio_s, RR medio, amplitud de la oscilación respiratoria) por fase.
FASES = [(0, 850, 50), (150, 650, 8), (270, 950, 90)]
RAMPA_S = 15


def rr_protocolo():
    rr, t = [], 1.0
    while t < 420:
        medio, amp = FASES[0][1:]
        for (t0, m, a), (_, m_ant, a_ant) in zip(FASES[1:], FASES[:-1]):
            if t >= t0:
                f = min(1.0, (t - t0) / RAMPA_S)
                medio, amp = m_ant + f * (m - m_ant), a_ant + f * (a - a_ant)
        rr.append(medio + amp * np.sin(2 * np.pi * len(rr) / 5))
        t += rr[-1] / 1000
    return np.array(rr)


def rr_secuencia(caso, n):
    if caso == "protocolo":
        return rr_protocolo()
    if caso in ("arritmia", "perdidos"):
        return 800 + 60 * np.sin(2 * np.pi * np.arange(n) / 5)
    if caso == "alterna":
        return np.where(np.arange(n) % 2, 900.0, 800.0)
    return np.full(n, 60000 / float(caso))


def main():
    salida, verdad, caso = sys.argv[1], sys.argv[2], sys.argv[3]
    periodo = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    rng = np.random.default_rng(1)
    duracion = 420 if caso == "protocolo" else DURACION_S
    t = np.arange(periodo, duracion * 1000 + 1, periodo) / 1000
    rr = rr_secuencia(caso, 400)
    inicios = np.cumsum(np.r_[1000, rr]) / 1000
    inicios = inicios[inicios < duracion]
    amp = np.ones(inicios.size)
    if caso == "perdidos":
        amp[[40, 80, 120]] = 0.15
    x = np.zeros_like(t)
    for t0, a in zip(inicios, amp):
        tp = t0 + PICO_S
        x += a * np.exp(-0.5 * ((t - tp) / 0.06) ** 2)
        x += a * 0.35 * np.exp(-0.5 * ((t - tp - DICROTA_S) / 0.07) ** 2)
    x = 400 + AMP * x
    x += 15 * np.sin(2 * np.pi * 50 * t + 0.3) + rng.normal(0, 2, t.size)
    adc = np.clip(np.round(x), 0, 1023).astype(int)
    np.savetxt(salida, np.c_[np.round(t * 1000).astype(int), adc], fmt="%d", delimiter=",",
               header="t_ms,adc", comments="")
    np.savetxt(verdad, np.diff(inicios) * 1000, fmt="%.3f", header="rr_ms", comments="")


if __name__ == "__main__":
    main()
