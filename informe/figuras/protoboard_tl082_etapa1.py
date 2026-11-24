"""Dibujo de la protoboard: TL082 A (etapa 1) con R2 y Cf entre pata 2 y pata 1.

Ejecutar:  python3 protoboard_tl082_etapa1.py
Genera:    protoboard_tl082_etapa1.png (en la misma carpeta que este script)

Convención de la protoboard (estándar 830 puntos):
  - Columnas a-e y f-j, separadas por el canal central.
  - Cada fila (1, 2, 3...) conecta sus 5 agujeros de un lado (a-e o f-j).
  - El TL082 (DIP-8) se coloca cruzando el canal: patas 1-4 en la columna e,
    patas 5-8 en la columna f. Pata 1 arriba a la izquierda (muesca arriba).
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

SALIDA = Path(__file__).with_name("protoboard_tl082_etapa1.png")

# ---------- Geometría ----------
COLS_IZQ = ["a", "b", "c", "d", "e"]
COLS_DER = ["f", "g", "h", "i", "j"]
X = {c: i for i, c in enumerate(COLS_IZQ)}
X.update({c: 5.6 + i for i, c in enumerate(COLS_DER)})  # canal central

FILA_PATA1 = 5          # fila donde está la pata 1
N_FILAS = 11            # filas dibujadas


def y(fila):
    return -fila        # fila 1 arriba, fila N abajo


# Pines del TL082 -> (columna, fila)
PATAS = {
    1: ("e", FILA_PATA1),
    2: ("e", FILA_PATA1 + 1),
    3: ("e", FILA_PATA1 + 2),
    4: ("e", FILA_PATA1 + 3),
    5: ("f", FILA_PATA1 + 3),
    6: ("f", FILA_PATA1 + 2),
    7: ("f", FILA_PATA1 + 1),
    8: ("f", FILA_PATA1),
}

COLOR_FILA_1 = "#f4c7c3"   # strip de la pata 1
COLOR_FILA_2 = "#c9dcf2"   # strip de la pata 2
COLOR_TABLERO = "#f2f2ee"
COLOR_HUECO = "#8a8a8a"
COLOR_CHIP = "#202020"
COLOR_R2 = "#e3c48d"
COLOR_CF = "#2e5c8a"


def dibujar_tablero(ax):
    ax.add_patch(FancyBboxPatch((-0.8, -N_FILAS - 0.6), 11.2, N_FILAS + 1.2,
                                boxstyle="round,pad=0.1,rounding_size=0.3",
                                fc=COLOR_TABLERO, ec="#b5b5a8", lw=1.5, zorder=0))
    # Canal central
    ax.add_patch(Rectangle((4.5, -N_FILAS - 0.4), 1.0, N_FILAS + 0.8,
                           fc="#dcdcd2", ec="none", zorder=0.2))

    for fila in range(1, N_FILAS + 1):
        # Resaltado de las filas que usan la pata 1 y la pata 2 (solo lado a-e)
        if fila == FILA_PATA1:
            ax.add_patch(Rectangle((-0.35, y(fila) - 0.35), 4.7, 0.7,
                                   fc=COLOR_FILA_1, ec="none", zorder=0.5))
        if fila == FILA_PATA1 + 1:
            ax.add_patch(Rectangle((-0.35, y(fila) - 0.35), 4.7, 0.7,
                                   fc=COLOR_FILA_2, ec="none", zorder=0.5))
        for c in COLS_IZQ + COLS_DER:
            ax.add_patch(Circle((X[c], y(fila)), 0.1, fc=COLOR_HUECO,
                                ec="none", zorder=1))
        ax.text(-0.6, y(fila), str(fila), ha="right", va="center",
                fontsize=8, color="#555")

    for c in COLS_IZQ + COLS_DER:
        ax.text(X[c], 0.5, c, ha="center", va="bottom", fontsize=9, color="#555")


def dibujar_chip(ax):
    # Cuerpo del TL082 cruzando el canal central
    top = y(FILA_PATA1) + 0.45
    bottom = y(FILA_PATA1 + 3) - 0.45
    ax.add_patch(FancyBboxPatch((3.85, bottom), 1.9, top - bottom,
                                boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=COLOR_CHIP, ec="black", zorder=4))    # Muesca de pata 1 (semicírculo arriba del cuerpo)
    ax.add_patch(Circle((4.8, top - 0.02), 0.13, fc=COLOR_TABLERO,
                        ec=COLOR_CHIP, zorder=5))
    ax.text(4.8, (top + bottom) / 2, "TL082\nA", color="white",
            ha="center", va="center", fontsize=10, weight="bold", zorder=5)

    # Patas: círculos metálicos sobre los agujeros
    for pata, (c, fila) in PATAS.items():
        ax.add_patch(Circle((X[c], y(fila)), 0.2, fc="#c0c0c0",
                            ec="black", lw=0.8, zorder=6))
        lado = -1 if c == "e" else 1
        ax.text(X[c] + lado * 0.42 if c == "f" else X[c] - 0.42,
                y(fila), str(pata), ha="center", va="center",
                fontsize=10, weight="bold", zorder=7,
                color="#b00020" if pata in (1, 2) else "black")


def dibujar_resistencia(ax, col, fila_a, fila_b):
    """R2 100 kΩ vertical entre dos filas, en la columna indicada."""
    x = X[col]
    ya, yb = y(fila_a), y(fila_b)
    ym = (ya + yb) / 2
    # patillas
    ax.plot([x, x], [ya, ym + 0.3], color="#777", lw=1.5, zorder=8)
    ax.plot([x, x], [yb, ym - 0.3], color="#777", lw=1.5, zorder=8)
    # cuerpo beige
    ax.add_patch(FancyBboxPatch((x - 0.17, ym - 0.3), 0.34, 0.6,
                                boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=COLOR_R2, ec="#8a6d3b", zorder=9))
    # bandas marrón-negro-amarillo (100 kΩ) + oro
    for dy, col_banda in [(0.2, "#7b3f00"), (0.07, "black"),
                          (-0.06, "#f1c40f"), (-0.2, "#c9a227")]:
        ax.plot([x - 0.17, x + 0.17], [ym + dy, ym + dy],
                color=col_banda, lw=3, zorder=10, solid_capstyle="butt")
    ax.annotate("R2 = 100 kΩ", xy=(x, yb - 0.35), xytext=(x - 0.6, -9.0),
                fontsize=9, color="#8a6d3b", weight="bold", ha="left",
                arrowprops=dict(arrowstyle="-", color="#8a6d3b", lw=0.8))


def dibujar_condensador(ax, col, fila_a, fila_b):
    """Cf 150 nF (cerámico azul) vertical entre dos filas, en la columna indicada."""
    x = X[col]
    ya, yb = y(fila_a), y(fila_b)
    ym = (ya + yb) / 2
    ax.plot([x, x], [ya, ym + 0.3], color="#777", lw=1.5, zorder=8)
    ax.plot([x, x], [yb, ym - 0.3], color="#777", lw=1.5, zorder=8)
    ax.add_patch(FancyBboxPatch((x - 0.2, ym - 0.3), 0.4, 0.6,
                                boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=COLOR_CF, ec="#1b3a57", zorder=9))
    ax.annotate("Cf = 150 nF", xy=(x, yb - 0.35), xytext=(x + 0.6, -10.0),
                fontsize=9, color=COLOR_CF, weight="bold", ha="left",
                arrowprops=dict(arrowstyle="-", color=COLOR_CF, lw=0.8))


def main():
    fig, ax = plt.subplots(figsize=(10, 8.2))
    ax.set_aspect("equal")
    ax.axis("off")

    dibujar_tablero(ax)
    dibujar_chip(ax)

    # Paso 5 y 6: R2 y Cf entre pata 2 (fila 6) y pata 1 (fila 5), en paralelo.
    dibujar_resistencia(ax, "b", FILA_PATA1, FILA_PATA1 + 1)
    dibujar_condensador(ax, "c", FILA_PATA1, FILA_PATA1 + 1)

    # Leyenda
    ax.text(-0.8, -N_FILAS - 1.1,
            "Fila roja (5): pata 1 (OUT A).   Fila azul (6): pata 2 (IN- A).\n"
            "Cada fila conecta a-e entre sí, así que R2 y Cf quedan entre "
            "pata 2 y pata 1, en paralelo.\n"
            "Las patas 3 y 4 (y el resto del circuito) se conectan en otras filas.",
            fontsize=9, va="top", color="#333")

    ax.set_title("Protoboard: TL082 (etapa 1) con R2 y Cf", fontsize=13,
                 weight="bold", loc="left")
    ax.set_xlim(-1.4, 10.6)
    ax.set_ylim(-N_FILAS - 3.0, 1.4)

    fig.savefig(SALIDA, dpi=160, bbox_inches="tight")
    print(f"Guardado: {SALIDA}")


if __name__ == "__main__":
    main()
