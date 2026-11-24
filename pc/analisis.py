"""M6/M9 - Análisis de HRV de una sesión completa (estándar de registro corto: 5 min).

Uso:  python analisis.py <sesion_latidos.csv> [figura.png] [--desde S] [--hasta S]

Lee los latidos de una sesión (lo que envía el Nano: t_ms,rr_ms,resultado,...; también
admite el formato antiguo del M5 t_ms,rr_ms,bpm, al que aplica la misma regla de artefactos
que el firmware) y calcula sobre todos los RR válidos del tramo:
  - BPM medio, RR medio, SDNN, RMSSD, pNN50
  - Poincaré: SD1 (variabilidad latido a latido, = RMSSD/sqrt(2)) y SD2 (a largo plazo)
La figura tiene el tacograma (RR frente al tiempo) y el diagrama de Poincaré.
"""
import argparse

import matplotlib.pyplot as plt
import numpy as np

RR_MIN, RR_MAX, TOLERANCIA = 300, 2000, 0.30     # las mismas reglas que firmware/pulso/hrv.cpp


def carga(fichero):
    d = np.genfromtxt(fichero, delimiter=",", names=True)
    t, rr = d["t_ms"] / 1000, d["rr_ms"]
    if "resultado" in d.dtype.names:
        return t, rr, d["resultado"].astype(int) == 0
    # Formato del M5 sin validar: se aplica la regla del firmware.
    valido = np.zeros(rr.size, bool)
    ultimo = None
    for i, x in enumerate(rr):
        if x == 0 or not RR_MIN <= x <= RR_MAX:
            continue
        if ultimo is None or abs(x - ultimo) <= TOLERANCIA * ultimo:
            valido[i], ultimo = True, x
    return t, rr, valido


def metricas(rr, contiguo):
    """rr: RR válidos; contiguo[i]: rr[i] sigue directamente a rr[i-1] (sin rechazos entre)."""
    d = np.diff(rr)[contiguo[1:]]
    x, y = rr[:-1][contiguo[1:]], rr[1:][contiguo[1:]]
    sd1 = np.std((y - x) / np.sqrt(2), ddof=1)
    sd2 = np.std((y + x) / np.sqrt(2), ddof=1)
    return {
        "N": rr.size,
        "RR medio (ms)": rr.mean(),
        "BPM medio": 60000 / rr.mean(),
        "SDNN (ms)": rr.std(ddof=1),
        "RMSSD (ms)": np.sqrt(np.mean(d ** 2)),
        "pNN50 (%)": 100 * np.mean(np.abs(d) > 50),
        "SD1 (ms)": sd1,
        "SD2 (ms)": sd2,
    }, (x, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("latidos")
    ap.add_argument("figura", nargs="?")
    ap.add_argument("--desde", type=float, default=-np.inf, help="inicio del tramo (s)")
    ap.add_argument("--hasta", type=float, default=np.inf, help="fin del tramo (s)")
    a = ap.parse_args()

    t, rr, valido = carga(a.latidos)
    tramo = (t >= a.desde) & (t <= a.hasta)
    t, rr, valido = t[tramo], rr[tramo], valido[tramo]
    # Contigüidad: un RR válido es contiguo al anterior si el latido previo también era válido.
    contiguo = np.r_[False, valido[:-1]][valido]
    m, (x, y) = metricas(rr[valido], contiguo)
    duracion = t[-1] - t[0]

    rechazados = (~valido & (rr > 0)).sum()
    print(f"Tramo {t[0]:.1f}-{t[-1]:.1f} s ({duracion:.0f} s), {rechazados} RR rechazados")
    for k, v in m.items():
        print(f"  {k:<14} {v:8.1f}" if k != "N" else f"  {k:<14} {v:8d}")
    if duracion < 240:
        print("  Aviso: el estándar de registro corto pide 5 min; con menos, SDNN se subestima.")

    if a.figura:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4), width_ratios=[2, 1])
        # La línea se corta donde hubo un RR rechazado (NaN), para no unir a través del hueco.
        cortes = np.flatnonzero(~contiguo)
        ax1.plot(np.insert(t[valido], cortes, np.nan), np.insert(rr[valido], cortes, np.nan),
                 "-", lw=1, color="tab:blue")
        ax1.plot(t[valido], rr[valido], ".", ms=4, color="tab:blue", label="RR válido")
        malos = ~valido & (rr > 0)
        ax1.plot(t[malos], rr[malos], "x", color="tab:red", ms=7, mew=2, label="rechazado")
        ax1.set_xlabel("t (s)")
        ax1.set_ylabel("RR (ms)")
        ax1.set_title("Tacograma")
        ax1.grid(alpha=0.3)
        ax1.legend(fontsize=8)
        ax2.plot(x, y, ".", ms=5)
        lim = [min(x.min(), y.min()) - 30, max(x.max(), y.max()) + 30]
        ax2.plot(lim, lim, "--", color="gray", lw=1)
        ax2.set_xlim(lim)
        ax2.set_ylim(lim)
        ax2.set_aspect("equal")
        ax2.set_xlabel("RR$_i$ (ms)")
        ax2.set_ylabel("RR$_{i+1}$ (ms)")
        ax2.set_title(f"Poincaré: SD1 {m['SD1 (ms)']:.0f} ms, SD2 {m['SD2 (ms)']:.0f} ms")
        ax2.grid(alpha=0.3)
        fig.suptitle(f"{m['BPM medio']:.1f} BPM · SDNN {m['SDNN (ms)']:.0f} ms · "
                     f"RMSSD {m['RMSSD (ms)']:.0f} ms · {duracion:.0f} s")
        fig.tight_layout()
        fig.savefig(a.figura, dpi=130)


if __name__ == "__main__":
    main()
