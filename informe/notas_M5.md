# Notas M5: detección de latidos y BPM

Código: `firmware/pulso/` (`pulso.ino`, `adquisicion.h/.cpp`, `detector.h/.cpp`).
Banco de pruebas en el PC con el mismo `detector.cpp`: `pc/test_detector.cpp`; señales sintéticas: `pc/sintetica.py`.

## Cadena de procesado (por muestra, a 500 Hz)
1. **Media móvil de 10 muestras (20 ms).** Ceros en 50 Hz y múltiplos: quita el ruido de red con una suma y una resta por muestra. Retardo constante de 9 ms, que no afecta a los RR.
2. **Aprendizaje (2 s).** Tras arrancar, perder la señal o saturar, se miden el máximo y el mínimo durante 2 s. Si la diferencia es menor de 0,1 V (22 LSB) no hay dedo y se sigue aprendiendo.
3. **Umbral adaptativo** u = valle + 0,6 (pico - valle). Pico y valle se promedian latido a latido (media exponencial, α = 0,25): se adapta en ~4 latidos a cambios de amplitud o de línea base.
   - Cambio respecto al plan: en vez de una envolvente con decaimiento continuo se actualizan pico y valle con cada latido. Con decaimiento continuo el umbral baja entre latidos, más cuanto más lento es el pulso, y se acerca a la onda dícrota.
4. **Máquina de estados** APRENDIZAJE → ESPERA → SUBIDA → REFRACTARIO → ESPERA.
   - ESPERA → SUBIDA solo en el cruce de subida del umbral (antes estaba debajo).
   - SUBIDA: sigue el máximo; al bajar del umbral se confirma el pico.
   - REFRACTARIO: 60 % del RR medio (mínimo 250 ms = 240 BPM).
   - Vuelta a APRENDIZAJE si no hay latido en 3 s (< 20 BPM), si SUBIDA dura más de 800 ms o si el ADC satura (< 3 o > 1020).
5. **Validación del pico.** Se descarta si su amplitud (pico - valle previo) es menor que 0,1 V o que el 40 % de la amplitud media, o si llega a menos de 300 ms del anterior.
6. **Instante del latido.** Parábola con el máximo y las muestras a ±20 ms: δ = (k/2)(y₋ₖ - y₊ₖ)/(y₋ₖ - 2y₀ + y₊ₖ), con k = 10 muestras.
   - Con vecinas inmediatas (±2 ms) la cima es casi plana (cambia < 1 LSB) y el ruido domina: error de RR de 1,8 ms rms. Con ±20 ms baja a 0,45 ms rms.
7. **BPM** = 60000 / media de los últimos 8 RR.

## Problemas encontrados al probar con grabaciones
- Primera versión (refractario fijo 250 ms, sin amplitud relativa): en `m2_amplificado_g68.csv` contó una onda dícrota como latido (RR 311 ms) y perdió el latido siguiente (RR 1239 ms), justo después del transitorio de meter el dedo. Además, si al acabar el refractario la señal seguía encima del umbral, se quedaba atascado en REFRACTARIO.
- Corregido con: refractario adaptativo (60 % RR), amplitud relativa mínima del 40 % y exigir cruce de subida en ESPERA.

## Resultados del banco de pruebas
Señal sintética a 500 Hz (120 s, onda sistólica + dícrota, 320 LSB, 50 Hz de 15 LSB, ruido blanco σ = 2 LSB):

| Caso | Latidos | Perdidos / duplicados | BPM medido | Error RR rms | Error RR máx |
|---|---|---|---|---|---|
| 40 BPM | 79 | 0 / 0 | 40,00 | 0,45 ms | 1,0 ms |
| 60 BPM | 118 | 0 / 0 | 60,00 | 0,37 ms | 2,0 ms |
| 72 BPM | 141 | 0 / 0 | 72,00 | 0,53 ms | 1,3 ms |
| 120 BPM | 236 | 0 / 0 | 120,00 | 0,41 ms | 1,0 ms |
| 180 BPM | 354 | 0 / 0 | 180,00 | 0,55 ms | 1,7 ms |
| Arritmia (RR = 800 ± 60 ms) | 147 | 0 / 0 | 74,98 (real 74,9) | 0,44 ms | 1,3 ms |

El error de RR está en el límite que impone enviar el RR redondeado a ms (≈ 0,4 ms rms).

Grabación real `datos/m2_amplificado_g68.csv` (a 100 Hz): 60 latidos, 59 RR, 82,1 BPM, SDNN 53,2 ms, RMSSD 28,4 ms. Coincide con la detección de referencia hecha en Python (54 / 30 ms).

Las grabaciones con G ≈ 22 (`test.csv`, `test5-5.csv`, `m2_amplificado_g1.csv`) tienen una relación señal/ruido peor y se pierden algunos latidos: otra razón para la ganancia final de 68.

## Firmware
- Compilado: 6980 B de flash (22 %), 848 B de RAM (41 %).
- Protocolo serie: `S,<t_ms>,<adc filtrado>` a 100 Hz; `B,<t_ms>,<rr_ms>,<bpm>` por latido; `I,...` cada 5 s.
- D13 parpadea 50 ms con cada latido.

## Prueba en vivo en el Nano (`datos/m5_latidos_1.csv` y `m5_latidos_1_latidos.csv`)
Figura `figuras/m5_latidos_real.png`.
- 114,7 s, 0 muestras perdidas. Dedo a los ~55 s; el transitorio satura hasta ~62 s y el primer latido se detecta a los 64,8 s (~3 s después: aprendizaje de 2 s).
- Tramo estable 65-106 s: 59 RR, 58 válidos, 88,3 BPM, SDNN 73 ms, RMSSD 43 ms.
- Un latido perdido a los 92,6 s: tras un movimiento la línea base bajó y ese latido quedó por debajo del umbral (RR = 1324 ms ≈ 2 RR). Lo debe filtrar la regla del 20 % de M6.
- Al final (106-112 s), con el dedo moviéndose al sacarlo, hay detecciones irregulares. Después la saturación lleva el detector a APRENDIZAJE, como se esperaba.

## Sesión en el lab del 2026-11-23 (firmware M5 + M6 + M7 en el Nano)
- `datos/sesion_20261123_121452`: 39 s, 53 latidos, 0 RR rechazados; 80,2 BPM, SDNN 60 ms, RMSSD 32 ms (figura `figuras/m6_hrv_nano_1.png`).
- `datos/sesion_20261123_122733`: 60 s desde Grabar, 89 latidos; un buscador de picos independiente (numpy) también cuenta 89 y ningún RR baja de 560 ms (sin dobles detecciones). Cuenta manual en el cuello: 85.
- `datos/sesion_20261123_123623`: la amplitud cayó de ~300 a ~60 LSB p-p (cambio de presión del dedo al contar con la otra mano). El umbral, adaptado latido a latido, se quedó por encima de los latidos pequeños: se perdieron ~12 latidos en 8,5 s y luego el detector reaprendió. Cuenta manual en la muñeca: 70, frente a ~83 estimados de la señal. La cuenta a mano no es una referencia válida para ±2 BPM.

### Cambios al detector tras esta sesión
1. **Decaimiento del umbral:** si pasan 1,5 RR medios sin latido, la amplitud media decae hacia el valle con tau = 1 s. El umbral alcanza los latidos pequeños sin esperar al reaprendizaje de 3 s.
2. **Refractario con tope de 500 ms:** la onda dícrota llega ~300 ms tras el pico sea cual sea el ritmo. Sin tope, un RR doble (latido perdido) alargaba el refractario, tapaba el latido siguiente y el detector se enganchaba a la mitad del ritmo (visto en `test.csv`).
- Resultado en `sesion_20261123_123623`: de 73 a 79 latidos; las demás grabaciones y las sintéticas, igual. Pendiente: con amplitud que cambia mucho latido a latido aún se pierde alguno (afinar FRACCION / AMP_REL o añadir búsqueda hacia atrás).
- Firmware: 10142 B de flash (33 %), 987 B de RAM (48 %).

### Validación del BPM frente a una referencia
- `datos/sesion_20261123_124604` (firmware con los cambios): 68 latidos, 0 rechazados, RR 637-911 ms, **77,6 BPM** de media.
- Referencia: aplicación de móvil con la cámara (fotopletismografía), **79 BPM**. Diferencia 1,4 BPM, dentro del ≤ 2 BPM del plan.
- Limitación: la app no es un instrumento calibrado y su ventana de medida no coincide exactamente con la grabación. Si hay un pulsioxímetro disponible, repetir.

### Cambio del instante del latido: máxima pendiente en lugar del pico
- En las pruebas de estrés (~100 BPM), el RMSSD con el pico salía 47-67 ms, con saltos de RR imposibles (623 → 475 → 581 ms). La onda dícrota se junta con el pico, la cima se achata y su instante baila.
- Ahora el latido se marca en la máxima pendiente del frente de subida. La pendiente se mide como y[n] - y[n - 20 ms] y el punto se refina con una parábola de puntos a ±20 ms. Con vecinos a ±1 muestra el máximo es casi plano y el ruido lo movía ±10 ms (RMSSD de 10 ms con ritmo constante).
- Resultado: en el estrés, el RMSSD pasa de 52 a 32 ms y de 47 a 25 ms; en reposo, igual que antes (31,7 frente a 32,5 ms). En las sintéticas, el error de RR es menor de 2 ms: RMSSD de 3-4 ms con ritmo constante, alterna 100,9 ms (verdad 100), arritmia 49,4 ms.
- Los puntos rojos del visor quedan ahora a media subida de la onda, no en la cima.
- HRV: el primer RR (al arrancar o tras un reinicio) solo se acepta si coincide (±30 %) con el siguiente. Antes, un primer RR malo (un latido perdido) se convertía en referencia y hacía rechazar los 5 siguientes.
- Firmware: 10544 B de flash (34 %), 1015 B de RAM (49 %).
