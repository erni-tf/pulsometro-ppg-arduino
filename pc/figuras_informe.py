"""Figuras del informe que salen directamente de las grabaciones reales.

Uso:  python figuras_informe.py      (escribe en informe/figuras/)

1. informe_pico_pendiente.png: por qué el latido se marca en la máxima pendiente y no en el
   pico. Grabación con estrés (sesion_20261123_130304, hecha con el firmware que usaba el
   pico): RR medidos con el pico (los del Nano) y con la máxima pendiente (calculada aquí sobre
   la misma señal).
2. informe_prension.png: prueba rápida de estado (sesion_20261123_133600) con las fases
   marcadas en el visor: pulso, RMSSD y estado que mostró el Nano.
"""
import csv
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
FIG = RAIZ / "informe" / "figuras"
VREF = 4.7
AZUL, ROJO, VERDE, GRIS = "#1f5fa8", "#c0392b", "#1e8449", "#7f8c8d"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def carga(nombre):
    s = np.loadtxt(DATOS / f"{nombre}.csv", delimiter=",", skiprows=1)
    lat = list(csv.DictReader(open(DATOS / f"{nombre}_latidos.csv")))
    return s[:, 0], s[:, 1], lat


def max_pendiente(t, x, t_pico, antes_ms=350):
    """Instante de máxima pendiente (diferencia en 20 ms) antes de cada pico, con parábola."""
    d = np.zeros_like(x)
    d[2:] = x[2:] - x[:-2]                      # 20 ms a 100 Hz, centrada en t - 10 ms
    out = []
    for tp in t_pico:
        idx = np.where((t >= tp - antes_ms) & (t <= tp))[0]
        i = idx[np.argmax(d[idx])]
        a, b, c = d[i - 2], d[i], d[min(i + 2, len(d) - 1)]
        den = a - 2 * b + c
        frac = np.clip((a - c) / den, -1, 1) if den < 0 else 0   # paso 2 muestras: k/2 = 1
        out.append(t[i] + frac * 10 - 10)
    return np.array(out)


def rr_contiguos(tiempos, validos):
    rr = np.diff(tiempos)
    ok = validos[1:] & validos[:-1]
    return np.where(ok, rr, np.nan)


def rmssd(rr):
    d = np.diff(rr)
    d = d[~np.isnan(d)]
    return np.sqrt(np.mean(d ** 2))


def figura_pico_pendiente():
    t, x, lat = carga("sesion_20261123_130304")
    t0 = t[0]
    tp = np.array([int(r["t_ms"]) for r in lat], float)
    validos = np.array([r["resultado"] == "0" for r in lat])
    tf = max_pendiente(t, x, tp)
    a, b = 120_000 + t0, 150_000 + t0
    sel = (tp >= a) & (tp < b)
    rr_p = rr_contiguos(tp[sel], validos[sel])
    rr_f = rr_contiguos(tf[sel], validos[sel])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 5.0), height_ratios=[1.1, 1],
                                   layout="constrained")
    m = (t >= a + 12_000) & (t < a + 17_000)
    ts = (t[m] - t0) / 1000
    ax1.plot(ts, x[m] * VREF / 1023, color=AZUL, lw=1.2)
    for tt, col, mk, lab in ((tp, ROJO, "o", "pico"), (tf, VERDE, "s", "máxima pendiente")):
        k = (tt >= a + 12_000) & (tt < a + 17_000)
        ax1.plot((tt[k] - t0) / 1000, np.interp(tt[k], t, x) * VREF / 1023, mk, color=col,
                 ms=5, label=lab)
    ax1.set_ylabel("A0 (V)")
    ax1.set_xlabel("t (s)")
    ax1.legend(frameon=False, ncol=2, loc="upper left")
    ax1.set_title("Pulso a ~100 BPM: la onda dícrota se junta con el pico", loc="left",
                  fontsize=9)

    n = np.arange(len(rr_p))
    ax2.plot(n, rr_p, ".-", color=ROJO, lw=1, label=f"pico: RMSSD {rmssd(rr_p):.0f} ms")
    ax2.plot(n, rr_f, ".-", color=VERDE, lw=1,
             label=f"máxima pendiente: RMSSD {rmssd(rr_f):.0f} ms")
    ax2.set_xlabel("latido (120-150 s de la grabación)")
    ax2.set_ylabel("RR (ms)")
    ax2.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1))
    fig.savefig(FIG / "informe_pico_pendiente.png", dpi=200)
    print("pico/pendiente:", f"RMSSD {rmssd(rr_p):.1f} -> {rmssd(rr_f):.1f} ms")


def figura_prension():
    nombre = "sesion_20261123_133600"
    _, _, lat = carga(nombre)
    marcas = [int(r["t_ms"]) for r in csv.DictReader(open(DATOS / f"{nombre}_marcas.csv"))]
    t = np.array([int(r["t_ms"]) for r in lat]) / 1000
    bpm = np.array([float(r["bpm"]) for r in lat])
    bpm[bpm == 0] = np.nan                        # sin RR válidos todavía
    rms = np.array([float(r["rmssd"]) for r in lat])
    est = np.array([int(r["estado"]) for r in lat])
    t_ini = marcas[1] / 1000 - 10                 # desde poco antes del reposo
    k = t >= t_ini
    t, bpm, rms, est = t[k] - t_ini, bpm[k], rms[k], est[k]
    fases = [(m / 1000 - t_ini, n) for m, n in
             zip(marcas[1:], ("reposo", "prensión\n(mano libre)", "respiración\nlenta"))]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(7.2, 5.2), sharex=True,
                                        height_ratios=[2, 1.4, 0.55], layout="constrained")
    ax1.plot(t, bpm, color=AZUL, lw=1.4)
    ax1.axhline(82.8, color=GRIS, ls=":", lw=1)
    ax1.text(t[-1], 82.8 + 0.8, "HR$_0$", color=GRIS, ha="right", va="bottom")
    ax1.axhline(82.8 + 15, color=ROJO, ls=":", lw=1)
    ax1.text(t[-1], 82.8 + 15.8, "HR$_0$ + 15", color=ROJO, ha="right", va="bottom")
    ax1.set_ylabel("pulso (BPM, 8 RR)")
    ax2.plot(t, np.where(rms > 0, rms, np.nan), color=AZUL, lw=1.4)
    ax2.axhline(25.0, color=GRIS, ls=":", lw=1)
    ax2.text(t[-1], 25.8, "RMSSD$_0$", color=GRIS, ha="right", va="bottom")
    ax2.set_ylabel("RMSSD (ms)")
    colores = {2: VERDE, 3: AZUL, 4: ROJO}
    nombres = {2: "relajado", 3: "normal", 4: "estrés"}
    for i in range(len(t) - 1):
        if est[i] in colores:
            ax3.axvspan(t[i], t[i + 1], color=colores[est[i]], lw=0)
    ax3.set_yticks([])
    ax3.set_ylabel("estado", rotation=0, ha="right", va="center")
    ax3.spines["left"].set_visible(False)
    for e, c in colores.items():
        ax3.plot([], [], "s", color=c, label=nombres[e])
    ax3.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.9))
    for ax in (ax1, ax2, ax3):
        for x0, _ in fases:
            ax.axvline(x0, color="k", lw=0.8, alpha=0.5)
    for x0, n in fases:                            # encima del eje: no tapa la curva
        ax1.text(x0 + 1, 1.02, n.replace("\n", " "), transform=ax1.get_xaxis_transform(),
                 va="bottom", fontsize=8)
    ax3.set_xlabel("t (s)")
    fig.savefig(FIG / "informe_prension.png", dpi=200)
    print("prensión: fases en", [round(x0, 1) for x0, _ in fases])


if __name__ == "__main__":
    figura_pico_pendiente()
    figura_prension()
