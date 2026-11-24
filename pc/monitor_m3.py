"""M3/M5 - Monitor: gráfica en vivo de A0, latidos y comprobación de continuidad.

Uso:  python monitor_m3.py [puerto] [fichero.csv]   (puerto por defecto /dev/ttyUSB0)

Si se indica un fichero CSV, se guardan en él todas las muestras (t_ms, adc) y, si el
firmware envía latidos (líneas B,...), también en <fichero>_latidos.csv (t_ms, rr_ms, bpm).
El eje vertical se autoescala para que se vean variaciones de pocos mV.

Muestra los últimos 5 s de señal (en voltios) y, en la consola, avisa si falta alguna
muestra (salto de tiempo distinto de 10 ms) y repite las líneas I,... del Arduino.
"""
import sys
import threading
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial

PUERTO = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
CSV = sys.argv[2] if len(sys.argv) > 2 else None
BAUDIOS = 115200
PASO_MS = 10            # 100 Hz tras el diezmado
VENTANA = 500           # 5 s a 100 Hz
VREF = 5.0
MIN_RANGO_V = 0.05      # rango vertical mínimo de la autoescala

t = deque(maxlen=VENTANA)
v = deque(maxlen=VENTANA)
latidos = deque(maxlen=20)     # instantes (s) de los últimos latidos
cerrojo = threading.Lock()
estado = {"saltos": 0, "ultimo_t": None, "bpm": None, "rr": None}


def lector(puerto, csv=None, csv_latidos=None):
    while True:
        linea = puerto.readline().decode("ascii", errors="replace").strip()
        if not linea:
            continue
        partes = linea.split(",")
        if partes[0] == "S" and len(partes) == 3:
            try:
                tms, adc = int(partes[1]), int(partes[2])
            except ValueError:
                continue
            ult = estado["ultimo_t"]
            if ult is not None and tms - ult != PASO_MS:
                estado["saltos"] += 1
                print(f"Salto de tiempo: {ult} -> {tms} ms")
            estado["ultimo_t"] = tms
            if csv:
                csv.write(f"{tms},{adc}\n")
            with cerrojo:
                t.append(tms / 1000)
                v.append(adc * VREF / 1023)
        elif partes[0] == "B" and len(partes) == 4:
            try:
                tms, rr, bpm = int(partes[1]), int(partes[2]), float(partes[3])
            except ValueError:
                continue
            print(f"Latido t={tms / 1000:.3f} s  RR={rr} ms  BPM={bpm:.1f}")
            if csv_latidos:
                csv_latidos.write(f"{tms},{rr},{bpm}\n")
            with cerrojo:
                latidos.append(tms / 1000)
                estado["rr"] = rr
                if bpm > 0:
                    estado["bpm"] = bpm
        elif partes[0] == "I":
            print(linea, f"| saltos detectados en el PC: {estado['saltos']}")


def main():
    puerto = serial.Serial(PUERTO, BAUDIOS, timeout=1)
    csv = open(CSV, "w", buffering=1) if CSV else None
    csv_latidos = None
    if csv:
        csv.write("t_ms,adc\n")
        csv_latidos = open(CSV.removesuffix(".csv") + "_latidos.csv", "w", buffering=1)
        csv_latidos.write("t_ms,rr_ms,bpm\n")
    threading.Thread(target=lector, args=(puerto, csv, csv_latidos), daemon=True).start()

    fig, ax = plt.subplots(figsize=(10, 4))
    (curva,) = ax.plot([], [], lw=1.2)
    (marcas,) = ax.plot([], [], "o", color="tab:red", ms=6)
    texto = ax.text(0.01, 0.95, "", transform=ax.transAxes, va="top", fontsize=13)
    ax.set_xlabel("t (s)")
    ax.set_ylabel("A0 (V)")
    ax.grid(alpha=0.3)
    fig.canvas.manager.set_window_title(f"M3 - {PUERTO}")

    def actualizar(_):
        with cerrojo:
            if not t:
                return (curva,)
            xs, ys = list(t), list(v)
            lats = [x for x in latidos if x >= xs[0]]
            bpm, rr = estado["bpm"], estado["rr"]
        curva.set_data(xs, ys)
        # Marca en la curva el valor de la señal en cada latido (muestra más cercana).
        marcas.set_data(lats, [ys[min(range(len(xs)), key=lambda i: abs(xs[i] - x))] for x in lats])
        if bpm:
            texto.set_text(f"{bpm:.0f} BPM   RR {rr} ms")
        ax.set_xlim(xs[0], max(xs[0] + VENTANA / 100, xs[-1]))
        lo, hi = min(ys), max(ys)
        centro, rango = (lo + hi) / 2, max(hi - lo, MIN_RANGO_V) * 1.2
        ax.set_ylim(centro - rango / 2, centro + rango / 2)
        return (curva, marcas, texto)

    _anim = FuncAnimation(fig, actualizar, interval=50, cache_frame_data=False)
    plt.tight_layout()
    plt.show()
    puerto.close()
    if csv:
        csv.close()
        csv_latidos.close()


if __name__ == "__main__":
    main()
