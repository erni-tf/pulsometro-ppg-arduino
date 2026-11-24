# Notas M4: visor en tiempo real (PC)

Código: `pc/visor.py`. Captura: `figuras/m4_visor.png`.

```
.venv/bin/python visor.py [puerto]                       # con el Nano
.venv/bin/python visor.py --reproducir ../datos/x.csv    # reproduce x.csv + x_latidos.csv
```

## Qué muestra
- Arriba: BPM, RMSSD y SDNN en grande ("--" hasta que el Nano los tiene).
- Onda PPG de los últimos 5 s con un punto rojo en cada latido detectado.
- Tacograma de los últimos 60 s. Los RR válidos van unidos por una línea, que se corta donde hubo un rechazo; los rechazados se marcan con una cruz roja.
- Barra de estado: fps, retraso acumulado, saltos de tiempo (muestras perdidas) y el último mensaje `I,` del Nano.
- Botón **Grabar**: guarda `datos/sesion_<fecha>.csv` (t_ms,adc) y `_latidos.csv` (t_ms,rr_ms,resultado,bpm,rmssd,sdnn), el mismo formato que usan `analisis.py` y `test_detector`.

## Arquitectura
- Un hilo lee el puerto serie (o la grabación, con sus tiempos reales) y deja las líneas en una `queue.Queue`.
- La interfaz (Tkinter con la figura de matplotlib embebida) vacía la cola y redibuja con `after()`.
- El modo reproducción permite desarrollar y probar el visor sin el Nano.

## Rendimiento (requisito: ≥ 20 fps sin retraso acumulado)
| Versión | fps | Causa |
|---|---|---|
| Redibujo completo de la figura en cada frame | 6 | matplotlib recalcula ejes, marcas y textos en cada frame |
| Blitting, `after(50)` fijo | 15-17 | el periodo real era 50 ms + lo que tarda el frame (~13 ms) |
| Blitting y periodo de 40 ms descontando el frame | **21-25** | |

- **Blitting:** los ejes están en tiempo relativo (0 = ahora), así que no cambian en cada frame. Se guarda el fondo (ejes, rejilla, etiquetas) y solo se redibujan las curvas encima. El fondo se rehace solo si cambia la escala vertical, que tiene histéresis: unas 13 veces en 20 s.
- Coste por frame: ~12 ms.
- Medido con el PC cargado (load average 5,4 en 8 núcleos, por otros procesos).
- Prueba de estrés: reproducción a 5× (500 líneas/s): 25 fps y retraso estable de 1-4 ms.
- Retraso acumulado = (reloj del PC - reloj del Nano) - el mínimo observado. Si el PC no diese abasto, crecería sin parar.
- Detalle corregido: el trazo antialiasado tocaba el borde derecho del área que se restaura y dejaba píxeles sueltos. Se deja un margen de 0,08 s.

## Cambios tras las pruebas en el lab (2026-11-23)
- Con el Nano graba **siempre** desde que se abre (se perdieron pruebas por no pulsar Grabar). Parar / Grabar corta en otro archivo.
- **Marcar fase** (botón o barra espaciadora): guarda el instante en `<sesión>_marcas.csv` para etiquetar las fases del protocolo.
- **Perfiles con nombre** (`datos/perfiles.json`): al calibrar se pide el nombre; al elegir un perfil en el menú se envía al Nano (`b<hr0×10>,<rmssd0×10>`), que lo guarda en su EEPROM. "Guardar la línea base actual con nombre…" nombra la que ya tiene el Nano.
- **Modo producción** (`--produccion`, F11 pantalla completa): tema oscuro, cabecera con perfil y Calibrar, cuatro tarjetas (pulso con corazón que late, estado en color, RMSSD, SDNN) y la onda sin ejes. Las fuentes escalan con el ancho de la ventana (probado a 960, 1280 y 1920 px). Sigue grabando en segundo plano. Captura: `figuras/m4_produccion.png`.
- Uso en el lab: varias sesiones de 5-15 min con el Nano a 25 fps, 0 saltos.
