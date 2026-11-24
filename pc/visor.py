"""M4 - Visor en tiempo real del pulsómetro.

Uso:
  python visor.py [puerto]                        conecta al Nano (por defecto, el primer
                                                  /dev/ttyUSB* o /dev/ttyACM*)
  python visor.py --reproducir datos/x.csv [-v 1] reproduce una grabación (x.csv y, si existe,
                                                  x_latidos.csv) a velocidad real o la indicada
  python visor.py --produccion [...]              pantalla limpia para demostraciones, fotos y
                                                  vídeos: onda, BPM, estado, RMSSD y SDNN.
                                                  F11 pantalla completa.

Perfiles: cada línea base (HR0, RMSSD0) se guarda con un nombre en datos/perfiles.json. Al
calibrar se pide el nombre; al elegir un perfil se envía al Nano (orden b), que lo guarda en
su EEPROM. Así varias personas pueden usar el pulsómetro sin recalibrar.

Ventana: onda PPG de los últimos 5 s con los latidos marcados, tacograma (RR de los últimos
60 s; los RR rechazados como artefacto en rojo), BPM, RMSSD, SDNN y estado (M7) en grande, y
botones para calibrar la línea base (envía "c" al Nano) y grabar la sesión en
datos/sesion_<fecha>.csv + _latidos.csv. Con el Nano la grabación empieza sola al abrir el
visor (así no se pierde ninguna prueba); Parar / Grabar la corta en otro archivo.

Arquitectura: un hilo lee el puerto (o la grabación) y deja las líneas en una cola; la
interfaz las procesa y se redibuja con after() cada 40 ms. Para llegar a 20 fps se usa
blitting: los ejes están en tiempo relativo (0 = ahora), así que no cambian en cada frame y
solo se redibujan las curvas sobre un fondo guardado. El fondo completo solo se redibuja si
cambia la escala vertical. En la barra de estado se ven los fps reales y el retraso acumulado
respecto al reloj del Nano (debe quedarse cerca de 0).
"""
import argparse
import bisect
import datetime
import json
import pathlib
import re
import queue
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import font as tkfont
from tkinter import simpledialog, ttk

import matplotlib

matplotlib.use("TkAgg")
import serial  # noqa: E402
import serial.tools.list_ports  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PIL import Image, ImageDraw, ImageTk  # noqa: E402

BAUDIOS = 115200
VREF = 4.7            # 5V del USB medido en el Nano: referencia del ADC
FS = 100              # muestras/s que llegan al PC
PASO_MS = 1000 // FS
VENTANA_S = 5
TACO_S = 60
REFRESCO_MS = 40          # 25 fps nominales (el plan pide >= 20)
DATOS = pathlib.Path(__file__).resolve().parent.parent / "datos"
PERFILES = DATOS / "perfiles.json"
VALIDO, SIN_RR, FUERA_RANGO, ARTEFACTO = range(4)
# Estado del M7: (texto, color)
ESTADOS = {0: ("sin calibrar", "#7f8c8d"), 1: ("calibrando", "#7f8c8d"),
           2: ("relajado", "#1e8449"), 3: ("normal", "#1f5fa8"), 4: ("estrés", "#c0392b")}

AZUL, ROJO, GRIS = "#1f5fa8", "#c0392b", "#7f8c8d"

# Modo producción: tema oscuro (mejor contraste en vídeo y proyector).
P_FONDO, P_TARJETA, P_TEXTO, P_TENUE, P_LINEA = "#0d1117", "#161b22", "#e6edf3", "#7d8590", "#30363d"
P_ONDA, P_LATIDO, P_CORAZON, P_REJILLA = "#58a6ff", "#ff5c5c", "#5c2b30", "#1f2630"
P_HOVER = "#21262d"
P_VARIAB = "#bc8cff"                     # acento de las tarjetas de variabilidad
P_ESTADOS = {0: ("sin calibrar", P_TENUE), 1: ("calibrando", P_TENUE),
             2: ("relajado", "#3fb950"), 3: ("normal", "#58a6ff"), 4: ("estrés", "#f85149")}
ANCHO_BASE, ALTO_TARJETA = 1280, 196   # diseño de referencia del modo producción
# Explicación bajo cada cifra (modo producción): el público no sabe qué es RMSSD.
P_AYUDA = {"bpm": "latidos por minuto",
           "estado": "según tu pulso y variabilidad en reposo",
           "rmssd": "variación latido a latido;\nalta = relajado",
           "sdnn": "variación total en los últimos 30 latidos"}
RE_LINEA_BASE = re.compile(r"hr0=([\d.]+),rmssd0=([\d.]+)")


def fuente_ui():
    familias = set(tkfont.families())
    for f in ("Inter", "Cantarell", "Noto Sans", "DejaVu Sans"):
        if f in familias:
            return f
    return "Helvetica"


class Perfiles:
    """Líneas base con nombre, en datos/perfiles.json: {nombre: {hr0, rmssd0, fecha}}."""

    def __init__(self, ruta=PERFILES):
        self.ruta = ruta
        try:
            self.datos = json.loads(ruta.read_text())
        except (OSError, ValueError):
            self.datos = {}

    def nombres(self):
        return sorted(self.datos, key=str.lower)

    def guarda(self, nombre, hr0, rmssd0):
        self.datos[nombre] = {"hr0": hr0, "rmssd0": rmssd0,
                              "fecha": datetime.datetime.now().isoformat(timespec="minutes")}
        self.ruta.parent.mkdir(exist_ok=True)
        self.ruta.write_text(json.dumps(self.datos, indent=2, ensure_ascii=False) + "\n")

    def busca(self, hr0, rmssd0):
        """Nombre del perfil con esa línea base (la que dice el Nano al arrancar), o None."""
        for nombre, p in self.datos.items():
            if abs(p["hr0"] - hr0) < 0.05 and abs(p["rmssd0"] - rmssd0) < 0.05:
                return nombre
        return None


# ---------------------------------------------------------------------------- fuentes
class Redondeado(tk.Canvas):
    """Panel con esquinas redondeadas (Tk no las tiene). El fondo se dibuja con Pillow a 3x y
    se reduce: así las curvas salen suaves. Los widgets van en .interior."""

    def __init__(self, padre, relleno=P_TARJETA, borde=P_LINEA, radio=16, margen=(20, 14),
                 **kw):
        super().__init__(padre, bg=padre.cget("bg"), highlightthickness=0, bd=0, **kw)
        self.relleno, self.borde, self.radio = relleno, borde, radio
        self.foto = None
        self.interior = tk.Frame(self, bg=relleno)
        if margen:
            mx, my = margen
            self.interior.place(x=mx, y=my, relwidth=1, relheight=1, width=-2 * mx,
                                height=-2 * my)
        self.bind("<Configure>", lambda _e: self._pinta(), add="+")

    def colores(self, relleno=None, borde=None):
        self.relleno = relleno or self.relleno
        self.borde = borde or self.borde
        self.interior.config(bg=self.relleno)
        self._pinta()

    def _pinta(self):
        w, h, k = self.winfo_width(), self.winfo_height(), 3
        if w < 4 or h < 4:
            return
        im = Image.new("RGB", (w * k, h * k), self.cget("bg"))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=self.radio * k,
                                             fill=self.relleno, outline=self.borde, width=k)
        self.foto = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))
        self.delete("fondo")
        self.create_image(0, 0, anchor="nw", image=self.foto, tags="fondo")
        self.tag_lower("fondo")


class Boton(Redondeado):
    """Botón redondeado: texto (o variable de texto) y orden al soltar el clic."""

    def __init__(self, padre, fuente, orden, texto="", variable=None, activo=True):
        super().__init__(padre, radio=10, margen=None)
        self.orden, self.activo = orden, activo
        self.l = tk.Label(self, text=texto, textvariable=variable, font=fuente, bg=P_TARJETA,
                          fg=P_TEXTO if activo else P_TENUE)
        self.l.pack(padx=16, pady=8)
        for w in (self, self.l):
            w.bind("<Enter>", lambda _e: self._resalta(True))
            w.bind("<Leave>", lambda _e: self._resalta(False))
            w.bind("<ButtonRelease-1>", lambda _e: self.activo and self.orden())
            w.configure(cursor="hand2" if activo else "")

    def _resalta(self, si):
        if self.activo:
            self.colores(relleno=P_HOVER if si else P_TARJETA)
            self.l.config(bg=self.relleno)


class FuenteSerie:
    """Lee líneas del puerto serie en un hilo y las deja en la cola."""

    def __init__(self, puerto, cola):
        self.ser = serial.Serial(puerto, BAUDIOS, timeout=0.2)
        self.cola = cola
        self.activo = True
        threading.Thread(target=self._lee, daemon=True).start()

    def _lee(self):
        while self.activo:
            try:
                linea = self.ser.readline()
            except (serial.SerialException, TypeError, OSError) as e:
                if self.activo:
                    self.cola.put(("E", str(e)))
                return
            if linea:
                self.cola.put(("L", linea.decode("ascii", errors="replace").strip()))

    def envia(self, texto):
        self.ser.write(texto.encode("ascii"))

    def cierra(self):
        self.activo = False
        self.ser.close()


class FuenteReproduccion:
    """Reproduce una grabación como si llegara del Nano, respetando los tiempos."""

    def __init__(self, csv, cola, velocidad=1.0):
        self.cola = cola
        self.velocidad = velocidad
        self.activo = True
        self.eventos = self._carga(pathlib.Path(csv))
        threading.Thread(target=self._emite, daemon=True).start()

    @staticmethod
    def _carga(csv):
        eventos = []
        for fila in csv.read_text().splitlines()[1:]:
            t, adc = fila.split(",")[:2]
            eventos.append((int(t), f"S,{t},{adc}"))
        latidos = csv.with_name(csv.stem + "_latidos.csv")
        if latidos.exists():
            for fila in latidos.read_text().splitlines()[1:]:
                c = fila.split(",")
                if len(c) >= 7:     # formato actual: t,rr,resultado,bpm,rmssd,sdnn,estado
                    linea = "B," + ",".join(c[:7])
                elif len(c) == 6:   # M6, sin estado
                    linea = "B," + ",".join(c) + ",0"
                else:               # grabaciones del M5: t,rr,bpm
                    linea = f"B,{c[0]},{c[1]},0,{c[2]},0.0,0.0,0"
                eventos.append((int(c[0]), linea))
        eventos.sort(key=lambda e: e[0])
        return eventos

    def _emite(self):
        if not self.eventos:
            return
        t0 = self.eventos[0][0]
        inicio = time.monotonic()
        for t, linea in self.eventos:
            espera = inicio + (t - t0) / 1000 / self.velocidad - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            if not self.activo:
                return
            self.cola.put(("L", linea))
        self.cola.put(("E", "fin de la grabación"))

    def envia(self, texto):
        pass

    def cierra(self):
        self.activo = False


def puerto_por_defecto():
    for p in serial.tools.list_ports.comports():
        if "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device
    return "/dev/ttyUSB0"


# ---------------------------------------------------------------------------- interfaz
class Visor:
    def __init__(self, raiz, puerto, reproducir=None, velocidad=1.0, produccion=False):
        self.raiz = raiz
        self.reproducir = reproducir
        self.velocidad = velocidad
        self.produccion = produccion
        self.perfiles = Perfiles()
        self.perfil = tk.StringVar(value="")             # nombre del perfil activo en el Nano
        self.linea_base = None                           # (hr0, rmssd0) que tiene el Nano
        self.nombre_calibrando = None                    # perfil que se está calibrando
        self.v_perfil = tk.StringVar(value="Perfil: --")
        self.fase = 0
        self.cola = queue.Queue()
        self.fuente = None
        self.grabacion = None

        self.t = deque(maxlen=VENTANA_S * FS)
        self.v = deque(maxlen=VENTANA_S * FS)
        self.adc_visto = 0                               # modo producción: valor dibujado
        self.latidos = deque(maxlen=30)                  # instantes (s) de latidos recientes
        self.taco = deque(maxlen=200)                    # (t_s, rr_ms, resultado)
        self.ultimo_t = None
        self.saltos = 0
        self.desfase_min = None                          # reloj PC - reloj Nano, mínimo visto
        self.retraso = 0.0
        self.frames, self.fps, self.t_fps = 0, 0.0, time.monotonic()
        self.info = ""

        raiz.title("Pulsómetro" if produccion else "Pulsómetro - visor")
        raiz.protocol("WM_DELETE_WINDOW", self.cierra)
        self.puerto = tk.StringVar(value=self.reproducir or puerto)
        if produccion:
            self._construye_produccion()
        else:
            self._construye(puerto)
        self.conecta()
        if not reproducir:              # con el Nano se graba siempre: Parar/Grabar parte archivos
            self.alterna_grabacion()
        self.raiz.after(REFRESCO_MS, self.refresca)

    # --- construcción de la ventana
    def _construye(self, puerto):
        barra = ttk.Frame(self.raiz, padding=(10, 8))
        barra.pack(fill="x")
        ttk.Label(barra, text="Puerto").pack(side="left")
        estado = "disabled" if self.reproducir else "normal"
        ttk.Entry(barra, textvariable=self.puerto, width=28, state=estado).pack(side="left", padx=6)
        self.b_conectar = ttk.Button(barra, text="Desconectar", command=self.alterna_conexion)
        self.b_conectar.pack(side="left")
        self.b_grabar = ttk.Button(barra, text="Grabar", command=self.alterna_grabacion)
        self.b_grabar.pack(side="right")
        self.b_marcar = ttk.Button(barra, text="Marcar fase (espacio)", command=self.marca_fase,
                                   state="disabled" if self.reproducir else "normal")
        self.b_marcar.pack(side="right", padx=(6, 0))
        if not self.reproducir:
            self.raiz.bind("<space>", lambda e: None if isinstance(e.widget, ttk.Entry)
                           else self.marca_fase())
        self.b_calibrar = ttk.Button(barra, text="Calibrar (2 min en reposo)",
                                     command=self.calibra, state=estado)
        self.b_calibrar.pack(side="right", padx=6)
        self.b_perfil = ttk.Menubutton(barra, textvariable=self.texto_perfil(), state=estado)
        self.b_perfil.pack(side="right")
        self.menu_perfiles = tk.Menu(self.b_perfil, tearoff=False)
        self.b_perfil["menu"] = self.menu_perfiles
        self._rehace_menu()
        self.l_grabando = ttk.Label(barra, text="", foreground=ROJO)
        self.l_grabando.pack(side="right", padx=8)

        metricas = ttk.Frame(self.raiz, padding=(10, 0))
        metricas.pack(fill="x")
        self.valores = {}
        for clave, titulo, unidad in (("bpm", "Pulso", "BPM"), ("rmssd", "RMSSD", "ms"),
                                      ("sdnn", "SDNN", "ms")):
            caja = ttk.Frame(metricas, padding=(0, 4))
            caja.pack(side="left", expand=True, fill="x")
            ttk.Label(caja, text=titulo, foreground=GRIS, font=("Helvetica", 11)).pack()
            fila = ttk.Frame(caja)
            fila.pack()
            self.valores[clave] = ttk.Label(fila, text="--", font=("Helvetica", 30, "bold"))
            self.valores[clave].pack(side="left")
            ttk.Label(fila, text=" " + unidad, foreground=GRIS,
                      font=("Helvetica", 12)).pack(side="left", anchor="s", pady=(0, 6))
        caja = ttk.Frame(metricas, padding=(0, 4))
        caja.pack(side="left", expand=True, fill="x")
        ttk.Label(caja, text="Estado", foreground=GRIS, font=("Helvetica", 11)).pack()
        self.l_estado = tk.Label(caja, text="--", font=("Helvetica", 22, "bold"), fg=GRIS,
                                 bg=self.raiz.cget("bg"))
        self.l_estado.pack(pady=(4, 0))

        self.fig = Figure(figsize=(10, 5.6), dpi=100, layout="constrained")
        gs = self.fig.add_gridspec(2, 1, height_ratios=[3, 2])
        self.ax = self.fig.add_subplot(gs[0])
        self.ax_taco = self.fig.add_subplot(gs[1])
        (self.curva,) = self.ax.plot([], [], color=AZUL, lw=1.4, animated=True)
        (self.marcas,) = self.ax.plot([], [], "o", color=ROJO, ms=6, animated=True)
        self.ax.set_xlim(-VENTANA_S, 0.08)       # margen: el trazo no toca el borde del blit
        self.ax.set_ylim(2.0, 3.0)
        self.ax.set_ylabel("A0 (V)")
        self.ax.set_xlabel("tiempo respecto a ahora (s)")
        self.ax.grid(alpha=0.3)
        (self.l_taco,) = self.ax_taco.plot([], [], ".-", color=AZUL, lw=1, ms=5, animated=True)
        (self.l_artef,) = self.ax_taco.plot([], [], "x", color=ROJO, ms=7, mew=2, animated=True)
        # Leyenda con artistas propios (los animados no se dibujan en el fondo).
        self.ax_taco.plot([], [], ".-", color=AZUL, lw=1, ms=5, label="RR válido")
        self.ax_taco.plot([], [], "x", color=ROJO, ms=7, mew=2, label="rechazado")
        self.ax_taco.set_xlim(-TACO_S, 1)
        self.ax_taco.set_ylim(500, 1000)
        self.ax_taco.set_ylabel("RR (ms)")
        self.ax_taco.set_xlabel("tiempo respecto a ahora (s)")
        self.ax_taco.grid(alpha=0.3)
        # Leyenda encima del área de datos: dentro tapaba puntos.
        self.ax_taco.legend(loc="lower right", bbox_to_anchor=(1, 1), fontsize=8,
                            frameon=False, ncol=2, borderaxespad=0.2)
        self.lienzo = FigureCanvasTkAgg(self.fig, master=self.raiz)
        self.lienzo.get_tk_widget().pack(fill="both", expand=True, padx=6)
        self.fondos = None
        self.lienzo.mpl_connect("draw_event", self._guarda_fondos)

        self.estado = ttk.Label(self.raiz, text="", foreground=GRIS, padding=(10, 4))
        self.estado.pack(fill="x")
        self.ejes = [(self.ax, (self.curva, self.marcas)),
                     (self.ax_taco, (self.l_taco, self.l_artef))]

    def _construye_produccion(self):
        """Pantalla limpia: cabecera con perfil y calibración, cifras grandes y la onda."""
        self.familia = fuente_ui()
        self.fuentes, self.tarjetas, self.unidades, self.escala = [], [], [], 1.0
        r = self.raiz
        r.configure(bg=P_FONDO)
        r.geometry("1280x720")
        r.minsize(960, 600)
        r.bind("<F11>", lambda _e: r.attributes("-fullscreen", not r.attributes("-fullscreen")))
        r.bind("<Escape>", lambda _e: r.attributes("-fullscreen", False))
        estado = "disabled" if self.reproducir else "normal"

        cab = tk.Frame(r, bg=P_FONDO, padx=32, pady=20)
        cab.pack(fill="x")
        tk.Label(cab, text="♥", font=self._fuente(20), fg=P_LATIDO, bg=P_FONDO).pack(side="left")
        tk.Label(cab, text="Pulsómetro", font=self._fuente(20, True), fg=P_TEXTO,
                 bg=P_FONDO).pack(side="left", padx=(8, 0))
        activo = not self.reproducir
        fuente_boton = self._fuente(12)
        self.b_calibrar = Boton(cab, fuente_boton, self.calibra, texto="Calibrar", activo=activo)
        self.b_calibrar.pack(side="right")
        self.b_perfil = Boton(cab, fuente_boton, self._abre_menu, variable=self.v_perfil,
                              activo=activo)
        self.b_perfil.pack(side="right", padx=(0, 10))
        self.menu_perfiles = tk.Menu(self.b_perfil, tearoff=False, font=self._fuente(11), bg=P_TARJETA,
                                     fg=P_TEXTO, activebackground=P_LINEA,
                                     activeforeground=P_TEXTO, disabledforeground=P_TENUE,
                                     relief="flat", bd=1)
        self._rehace_menu()

        # Cifras: pulso (grande, con corazón) | estado | RMSSD | SDNN, en tarjetas iguales.
        fila = tk.Frame(r, bg=P_FONDO, padx=24)
        fila.pack(fill="x")
        for c, peso in enumerate((4, 4, 3, 3)):      # el pulso necesita sitio para "180 BPM"
            fila.columnconfigure(c, weight=peso, uniform="tarjeta")
        self.valores = {}

        fuente_pie, fuente_titulo = self._fuente(11), self._fuente(12)

        def tarjeta(col, titulo, clave, acento):
            t = Redondeado(fila, height=ALTO_TARJETA)
            self.tarjetas.append(t)
            t.grid(row=0, column=col, sticky="nsew", padx=8)
            c = t.interior
            cab_t = tk.Frame(c, bg=P_TARJETA)
            cab_t.pack(fill="x")
            t.punto = tk.Label(cab_t, text="●", font=fuente_pie, fg=acento, bg=P_TARJETA)
            t.punto.pack(side="left", padx=(0, 6))
            tk.Label(cab_t, text=titulo, font=fuente_titulo, fg=P_TENUE, bg=P_TARJETA,
                     anchor="w").pack(side="left")
            # Pie con la explicación (en Estado, también el detalle). Mismo hueco de dos
            # líneas en todas para que las cifras queden a la misma altura.
            pie = tk.Label(c, text=P_AYUDA[clave], font=fuente_pie, fg=P_TENUE, bg=P_TARJETA,
                           anchor="nw", justify="left", height=2)
            pie.pack(side="bottom", fill="x")
            c.bind("<Configure>", lambda e, p=pie: p.config(wraplength=max(e.width - 4, 50)))
            t.pie = pie
            return t

        t = tarjeta(0, "Pulso", "bpm", P_LATIDO)
        linea = tk.Frame(t.interior, bg=P_TARJETA)
        linea.pack(fill="x", expand=True)
        self.l_corazon = tk.Label(linea, text="♥", font=self._fuente(34), fg=P_CORAZON, bg=P_TARJETA)
        self.l_corazon.pack(side="left", padx=(0, 10))
        self.valores["bpm"] = tk.Label(linea, text="–", font=self._fuente(56, True), fg=P_TEXTO,
                                       bg=P_TARJETA)
        self.valores["bpm"].pack(side="left")
        self._unidad(linea, "BPM", 16)

        t = tarjeta(1, "Estado", "estado", P_TENUE)
        self.t_estado = t
        self.l_estado = tk.Label(t.interior, text="–", font=self._fuente(34, True), fg=P_TENUE,
                                 bg=P_TARJETA, anchor="w")
        self.l_estado.pack(fill="x", expand=True)
        self.l_detalle = t.pie

        for col, clave, titulo in ((2, "rmssd", "Variabilidad · RMSSD"),
                                   (3, "sdnn", "Variabilidad · SDNN")):
            t = tarjeta(col, titulo, clave, P_VARIAB)
            linea = tk.Frame(t.interior, bg=P_TARJETA)
            linea.pack(fill="x", expand=True)
            self.valores[clave] = tk.Label(linea, text="–", font=self._fuente(44, True), fg=P_TEXTO,
                                           bg=P_TARJETA)
            self.valores[clave].pack(side="left")
            self._unidad(linea, "ms", 12)

        # Onda estilo monitor, en su propio panel: rejilla tenue, trazo con halo y un punto
        # brillante en el presente. Toma el color del estado.
        panel = Redondeado(r, margen=(12, 12))
        panel.pack(fill="both", expand=True, padx=32, pady=(16, 0))
        self.fig = Figure(figsize=(12, 4), dpi=100, facecolor=P_TARJETA)
        self.ax = self.fig.add_axes((0.005, 0.04, 0.99, 0.92))
        self.ax.set_facecolor(P_TARJETA)
        self.ax.set_axis_off()
        for seg in range(-VENTANA_S, 1):                         # un segundo por división
            self.ax.axvline(seg, color=P_REJILLA, lw=1, zorder=0)
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            self.ax.axhline(f, color=P_REJILLA, lw=1, zorder=0)
            self.ax.lines[-1].set_transform(self.ax.transAxes)
        # Dos halos y el trazo (ancho, opacidad).
        self.trazos = [self.ax.plot([], [], lw=lw, alpha=a, solid_capstyle="round",
                                    animated=True)[0] for lw, a in ((11, 0.07), (6, 0.16), (2.6, 1))]
        (self.cabeza_halo,) = self.ax.plot([], [], "o", ms=20, alpha=0.25, mew=0, animated=True)
        (self.cabeza,) = self.ax.plot([], [], "o", ms=8, mew=0, animated=True)
        self.ax.set_xlim(-VENTANA_S, 0.08)
        self.ax.set_ylim(VREF / 2 - 0.62, VREF / 2 + 0.62)     # reposo: a mitad de escala
        self.lienzo = FigureCanvasTkAgg(self.fig, master=panel.interior)
        w = self.lienzo.get_tk_widget()
        w.configure(bg=P_TARJETA, highlightthickness=0)
        w.pack(fill="both", expand=True)
        self.fondos = None
        self.lienzo.mpl_connect("draw_event", self._guarda_fondos)

        self.estado = tk.Label(r, text="", font=self._fuente(10), fg=P_TENUE, bg=P_FONDO, anchor="w",
                               padx=32, pady=10)
        self.estado.pack(fill="x")
        self.ejes = [(self.ax, (*self.trazos, self.cabeza_halo, self.cabeza))]
        self._colorea_onda(P_ONDA)
        r.bind("<Configure>", self._reescala)

    def _unidad(self, padre, texto, sobre_base):
        """Unidad junto a una cifra, alineada con su línea base (sobre_base px a escala 1)."""
        u = tk.Label(padre, text=texto, font=self._fuente(15), fg=P_TENUE, bg=P_TARJETA)
        u.pack(side="left", anchor="s", padx=(8, 0), pady=(0, sobre_base))
        self.unidades.append((u, sobre_base))

    def _fuente(self, tam, negrita=False):
        """Fuente con nombre: _reescala cambia su tamaño según el ancho de la ventana."""
        fu = tkfont.Font(family=self.familia, size=tam, weight="bold" if negrita else "normal")
        self.fuentes.append((fu, tam))
        return fu

    def _reescala(self, evento):
        """Todo proporcional al ancho: igual a 960 px que a pantalla completa en 1920 px."""
        if evento.widget is not self.raiz:
            return
        escala = min(max(evento.width / ANCHO_BASE, 0.7), 1.8)
        if abs(escala - self.escala) < 0.02:
            return
        self.escala = escala
        for fu, tam in self.fuentes:
            fu.configure(size=round(tam * escala))
        for t in self.tarjetas:
            t.configure(height=round(ALTO_TARJETA * escala))
        for u, sobre_base in self.unidades:
            u.pack_configure(pady=(0, round(sobre_base * escala)))

    def _abre_menu(self):
        b = self.b_perfil
        self.menu_perfiles.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 4)

    # --- perfiles y calibración
    def texto_perfil(self):
        return self.v_perfil

    def _actualiza_perfil(self):
        if self.linea_base is None:
            texto = "sin línea base"
        else:
            nombre = self.perfiles.busca(*self.linea_base)
            texto = nombre or f"sin nombre ({self.linea_base[0]:.0f} BPM)"
        # ttk.Menubutton ya dibuja su flecha; el de producción (tk) no.
        self.v_perfil.set(f"Perfil: {texto}" + ("  ▾" if self.produccion else ""))

    def _rehace_menu(self):
        m = self.menu_perfiles
        m.delete(0, "end")
        for nombre in self.perfiles.nombres():
            p = self.perfiles.datos[nombre]
            m.add_command(label=f"{nombre}   ({p['hr0']:.0f} BPM, RMSSD {p['rmssd0']:.0f} ms)",
                          command=lambda n=nombre: self.elige_perfil(n))
        if self.perfiles.nombres():
            m.add_separator()
        m.add_command(label="Guardar la línea base actual con nombre…", command=self.nombra_actual,
                      state="normal" if self.linea_base else "disabled")
        m.add_command(label="Sin perfil (el Nano olvida la línea base)", command=self.olvida_perfil,
                      state="normal" if self.linea_base else "disabled")
        self._actualiza_perfil()

    def elige_perfil(self, nombre):
        p = self.perfiles.datos[nombre]
        if self.fuente:
            self.fuente.envia(f"b{round(p['hr0'] * 10)},{round(p['rmssd0'] * 10)}\n")

    def olvida_perfil(self):
        if self.fuente:
            self.fuente.envia("o")

    def _pide_nombre(self, titulo, inicial=""):
        nombre = simpledialog.askstring(titulo, "Nombre del perfil:", initialvalue=inicial,
                                        parent=self.raiz)
        return nombre.strip() if nombre and nombre.strip() else None

    def nombra_actual(self):
        if not self.linea_base:
            return
        nombre = self._pide_nombre("Guardar línea base")
        if nombre:
            self.perfiles.guarda(nombre, *self.linea_base)
            self._rehace_menu()

    def calibra(self):
        if not self.fuente:
            return
        actual = self.perfiles.busca(*self.linea_base) if self.linea_base else None
        nombre = self._pide_nombre("Calibrar (2 min en reposo)", actual or "")
        if nombre:
            self.nombre_calibrando = nombre
            self.fuente.envia("c")

    def _linea_base_recibida(self, texto):
        """Mensajes I del Nano con hr0=..,rmssd0=.. (al arrancar, al calibrar o al cargar)."""
        if texto.startswith("linea base borrada"):
            self.linea_base = None
            self._muestra_estado(0)
            self._rehace_menu()
            return
        m = RE_LINEA_BASE.search(texto)
        if not m:
            return
        self.linea_base = (float(m.group(1)), float(m.group(2)))
        if texto.startswith("calibrado"):
            if self.nombre_calibrando:
                self.perfiles.guarda(self.nombre_calibrando, *self.linea_base)
                self.nombre_calibrando = None
            self._muestra_estado(3, "calibración terminada")
        self._rehace_menu()

    # --- conexión
    def conecta(self):
        try:
            if self.reproducir:
                self.fuente = FuenteReproduccion(self.reproducir, self.cola, self.velocidad)
            else:
                self.fuente = FuenteSerie(self.puerto.get(), self.cola)
        except (serial.SerialException, OSError) as e:
            self.fuente = None
            self.info = f"No se puede abrir {self.puerto.get()}: {e}"
        self.desfase_min = None
        self.ultimo_t = None
        if not self.produccion:
            self.b_conectar.config(text="Desconectar" if self.fuente else "Conectar")

    def desconecta(self):
        if self.fuente:
            self.fuente.cierra()
            self.fuente = None
        if not self.produccion:
            self.b_conectar.config(text="Conectar")

    def alterna_conexion(self):
        if self.fuente:
            self.desconecta()
        else:
            self.conecta()

    # --- grabación
    def alterna_grabacion(self):
        if self.grabacion:
            for f in self.grabacion:
                f.close()
            self.grabacion = None
            if not self.produccion:
                self.b_grabar.config(text="Grabar")
                self.l_grabando.config(text="")
            return
        DATOS.mkdir(exist_ok=True)
        base = DATOS / datetime.datetime.now().strftime("sesion_%Y%m%d_%H%M%S")
        senal = open(f"{base}.csv", "w", buffering=1)
        latidos = open(f"{base}_latidos.csv", "w", buffering=1)
        marcas = open(f"{base}_marcas.csv", "w", buffering=1)
        senal.write("t_ms,adc\n")
        latidos.write("t_ms,rr_ms,resultado,bpm,rmssd,sdnn,estado\n")
        marcas.write("t_ms,fase\n")
        self.grabacion = (senal, latidos, marcas)
        self.fase = 0
        if not self.produccion:
            self.b_grabar.config(text="Parar")
            self.l_grabando.config(text=f"● grabando {base.name}")

    def marca_fase(self):
        """Apunta en <base>_marcas.csv el instante (reloj del Nano) en que empieza otra fase."""
        if not self.grabacion or self.ultimo_t is None:
            return
        self.fase += 1
        self.grabacion[2].write(f"{self.ultimo_t},{self.fase}\n")
        self.info = f"fase {self.fase} marcada"

    # --- protocolo
    def procesa(self, linea):
        partes = linea.split(",")
        try:
            if partes[0] == "S" and len(partes) == 3:
                tms, adc = int(partes[1]), int(partes[2])
                if self.ultimo_t is not None and tms - self.ultimo_t != PASO_MS:
                    self.saltos += 1
                self.ultimo_t = tms
                desfase = time.monotonic() * self.velocidad - tms / 1000
                if self.desfase_min is None or desfase < self.desfase_min:
                    self.desfase_min = desfase
                self.retraso = (desfase - self.desfase_min) / self.velocidad
                self.t.append(tms / 1000)
                visto = adc
                if self.produccion and self.v and abs(adc - self.adc_visto) <= 1:
                    visto = self.adc_visto           # zona muerta de 1 LSB: sin dedo, línea recta
                self.adc_visto = visto
                self.v.append(visto * VREF / 1023)
                if self.grabacion:
                    self.grabacion[0].write(f"{tms},{adc}\n")
            elif partes[0] == "B" and len(partes) >= 8:
                tms, rr, res = int(partes[1]), int(partes[2]), int(partes[3])
                bpm, rmssd, sdnn = (float(x) for x in partes[4:7])
                self.latidos.append(tms / 1000)
                if rr:
                    self.taco.append((tms / 1000, rr, res))
                vacio = "–" if self.produccion else "--"
                self.valores["bpm"].config(text=f"{bpm:.0f}" if bpm else vacio)
                self.valores["rmssd"].config(text=f"{rmssd:.0f}" if rmssd else vacio)
                self.valores["sdnn"].config(text=f"{sdnn:.0f}" if sdnn else vacio)
                est = int(partes[7])
                if est != 1:                           # calibrando: lo pinta el mensaje I
                    self._muestra_estado(est)
                self._late()
                if self.grabacion:
                    self.grabacion[1].write(",".join(partes[1:8]) + "\n")
            elif partes[0] == "I":
                texto = ",".join(partes[1:])
                self.info = texto
                self._linea_base_recibida(texto)
                if partes[1:2] == ["calibrando"] and len(partes) > 2:
                    self.info = f"calibrando: quédate quieto y relajado, faltan {partes[2]} s"
                    self._muestra_estado(1, f"faltan {partes[2]} s")
        except ValueError:
            pass                                       # línea corrupta (p. ej. al conectar)

    def _muestra_estado(self, est, detalle=""):
        if self.produccion:
            texto, color = P_ESTADOS.get(est, ("--", P_TENUE))
            self.l_estado.config(text=texto, fg=color)
            if not detalle:
                detalle = {0: "pulsa Calibrar (2 min en reposo)",
                           1: "quédate quieto y relajado"}.get(est, P_AYUDA["estado"])
            self.l_detalle.config(text=detalle)
            self.t_estado.colores(borde=color if est >= 2 else P_LINEA)
            self.t_estado.punto.config(fg=color)
            self._colorea_onda(color if est >= 2 else P_ONDA)
        else:
            texto, color = ESTADOS.get(est, ("--", GRIS))
            self.l_estado.config(text=texto, fg=color)

    def _late(self):
        """Corazón que se enciende con cada latido (modo producción)."""
        if self.produccion:
            self.l_corazon.config(fg=P_LATIDO)
            self.raiz.after(160, lambda: self.l_corazon.config(fg=P_CORAZON))

    def _colorea_onda(self, color):
        for a in (*self.trazos, self.cabeza_halo):
            a.set_color(color)
        self.cabeza.set_color("white")

    # --- bucle de la interfaz
    def refresca(self):
        inicio = time.monotonic()
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "L":
                    self.procesa(dato)
                else:
                    self.info = dato
                    self.desconecta()
        except queue.Empty:
            pass

        if self.t:
            self._dibuja()

        self.frames += 1
        ahora = time.monotonic()
        if ahora - self.t_fps >= 1:
            self.fps = self.frames / (ahora - self.t_fps)
            self.frames, self.t_fps = 0, ahora
        if self.produccion:                            # solo avisos útiles para el público
            self.estado.config(text="" if self.fuente else self.info)
        else:
            partes = [f"{self.fps:.0f} fps", f"retraso {self.retraso * 1000:.0f} ms",
                      f"saltos {self.saltos}"] + ([self.info] if self.info else [])
            self.estado.config(text="  ·  ".join(partes))
        # Periodo fijo: se descuenta lo que ha tardado este frame.
        resto = REFRESCO_MS - int((time.monotonic() - inicio) * 1000)
        self.raiz.after(max(1, resto), self.refresca)

    # --- dibujo con blitting
    def _guarda_fondos(self, _evento):
        self.fondos = [self.lienzo.copy_from_bbox(ax.bbox) for ax, _ in self.ejes]

    @staticmethod
    def _escala(ax, lo, hi, minimo, margen):
        """Ajusta el eje Y con histéresis: solo cambia si los datos se salen o si sobra mucho."""
        rango = max(hi - lo, minimo) * (1 + 2 * margen)
        y0, y1 = ax.get_ylim()
        if lo < y0 or hi > y1 or (y1 - y0) > 1.8 * rango:
            centro = (lo + hi) / 2
            ax.set_ylim(centro - rango / 2, centro + rango / 2)
            return True
        return False

    def _dibuja(self):
        if self.produccion:
            self._dibuja_produccion()
            return
        xs, ys = list(self.t), list(self.v)
        ahora = xs[-1]
        cambia = self._escala(self.ax, min(ys), max(ys), 0.05, 0.08)
        visibles = [rr for t, rr, _ in self.taco if t >= ahora - TACO_S]
        if visibles and not self.produccion:
            cambia |= self._escala(self.ax_taco, min(visibles), max(visibles), 100, 0.1)
        if cambia or self.fondos is None:
            self.lienzo.draw()                         # fondo nuevo (dispara _guarda_fondos)

        self.curva.set_data([x - ahora for x in xs], ys)
        lat = [x for x in self.latidos if xs[0] <= x <= ahora]
        self.marcas.set_data([x - ahora for x in lat],
                             [ys[min(bisect.bisect_left(xs, x), len(ys) - 1)] for x in lat])
        buenos, anterior, t_ant = [], VALIDO, None
        for t, rr, r in self.taco:
            if r == VALIDO:
                # Corta la línea tras un rechazo o un hueco (latidos sin RR, p. ej. al reaprender).
                if anterior != VALIDO or (t_ant is not None and t - t_ant > 2 * rr / 1000):
                    buenos.append((float("nan"), float("nan")))
                buenos.append((t - ahora, rr))
                t_ant = t
            anterior = r
        malos = [(t - ahora, rr) for t, rr, r in self.taco if r != VALIDO]
        self.l_taco.set_data([t for t, _ in buenos], [rr for _, rr in buenos])
        self.l_artef.set_data([t for t, _ in malos], [rr for _, rr in malos])
        self._blit()

    def _dibuja_produccion(self):
        xs, ys = list(self.t), list(self.v)
        ahora = xs[-1]
        # Rango mínimo de 1 V (el pulso ocupa 1,4-3,7 V): sin dedo la señal varía 1 LSB y,
        # ampliada, parecía ruido. Así se ve plana, y al poner el dedo se ve la subida entera.
        if self._escala(self.ax, min(ys), max(ys), 1.0, 0.12) or self.fondos is None:
            self.lienzo.draw()
        x = [t - ahora for t in xs]
        for a in self.trazos:
            a.set_data(x, ys)
        for a in (self.cabeza_halo, self.cabeza):
            a.set_data([0], [ys[-1]])
        self._blit()

    def _blit(self):
        for fondo, (ax, artistas) in zip(self.fondos, self.ejes):
            self.lienzo.restore_region(fondo)
            for a in artistas:
                ax.draw_artist(a)
            self.lienzo.blit(ax.bbox)

    def cierra(self):
        self.desconecta()
        if self.grabacion:
            self.alterna_grabacion()
        self.raiz.destroy()


def main():
    ap = argparse.ArgumentParser(description="Visor en tiempo real del pulsómetro")
    ap.add_argument("puerto", nargs="?", default=None)
    ap.add_argument("--reproducir", metavar="CSV", help="reproduce una grabación en vez del puerto")
    ap.add_argument("-v", "--velocidad", type=float, default=1.0, help="velocidad de reproducción")
    ap.add_argument("--produccion", action="store_true",
                    help="pantalla limpia para demostraciones (F11: pantalla completa)")
    args = ap.parse_args()
    raiz = tk.Tk()
    Visor(raiz, args.puerto or puerto_por_defecto(), args.reproducir, args.velocidad,
          args.produccion)
    raiz.mainloop()


if __name__ == "__main__":
    main()
