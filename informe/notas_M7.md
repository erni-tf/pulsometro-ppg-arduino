# Notas M7: indicador de estado {relajado, normal, estrés}

Código: `firmware/pulso/estado.h/.cpp` (lógica, C++ puro) e integración en `pulso.ino`. Se prueba en el PC con `pc/test_detector.cpp ... calibra`.

## Funcionamiento
1. **Calibración** (orden `c` desde el visor o pulsador en D2): 2 min en reposo y al menos 60 RR válidos.
   - HR0 = 60000 · N / ΣRR (BPM medio de todo el periodo).
   - RMSSD0 se calcula con **todas** las diferencias entre RR contiguos del periodo, no con la ventana de 30. Así la línea base usa más datos y es más estable.
2. **Clasificación** en cada latido, con el BPM (8 RR) y el RMSSD (30 RR) del M6, en enteros (décimas):

| Estado | Condición |
|---|---|
| Relajado | RMSSD ≥ 1,15 RMSSD0 y HR ≤ HR0 + 5 |
| Estrés | (HR ≥ HR0 + 10 y RMSSD ≤ 1,15 RMSSD0) o HR ≥ HR0 + 15 o RMSSD ≤ 0,50 RMSSD0 |
| Normal | en otro caso |

3. **Histéresis:** el estado mostrado solo cambia si el nuevo se mantiene 10 latidos seguidos.
4. **EEPROM:** la línea base se guarda al acabar la calibración (6 bytes en la dirección 0, con una marca 0x5052). Al abrir el puerto serie, el Nano se reinicia por la señal DTR; sin EEPROM habría que recalibrar cada vez que se abre el visor.

## Protocolo serie (ampliado)
- `B,<t_ms>,<rr_ms>,<res>,<bpm>,<rmssd>,<sdnn>,<estado>`, con estado 0 sin calibrar, 1 calibrando, 2 relajado, 3 normal y 4 estrés.
- `I,calibrando,<s restantes>` cada 5 s mientras calibra; `I,calibrado,hr0=..,rmssd0=..` al acabar; `I,linea base guardada,...` al arrancar si hay una en la EEPROM.
- Órdenes del PC: `c` calibrar, `r` reiniciar detector y HRV. La orden `i` (invertir) del plan no hace falta: con la LDR en la parte baja del divisor el pulso ya sale hacia arriba.

## Prueba con protocolo sintético (`sintetica.py protocolo`, 420 s a 500 Hz)
Figura `figuras/m7_protocolo_sintetico.png`.
- Fases: reposo 0-150 s (RR 850 ± 50 ms), estrés 150-270 s (RR 650 ± 8 ms), relajación 270-420 s (RR 950 ± 90 ms), con rampas de 15 s entre fases.
- Calibración desde el primer latido: acaba a los 123,6 s con HR0 = 70,6 BPM y RMSSD0 = 41,7 ms. Pasa a *normal*.
- *Estrés* a los 174,1 s (BPM 92, RMSSD 18 ms): 24 s después del inicio de la fase. Se suman la rampa (15 s), el llenado de la ventana de 30 RR y los 10 latidos de histéresis.
- *Normal* a los 289 s y *relajado* a los 299,4 s (BPM 64, RMSSD 64 ms).
- 515 de 516 RR válidos: las rampas no disparan el rechazo de artefactos.

## Firmware
- Con M7: 9998 B de flash (32 %) y 981 B de RAM (47 %).
- Visor: muestra el estado en color (verde relajado, azul normal, rojo estrés) y tiene el botón "Calibrar (2 min en reposo)". Captura en la fase de estrés: `figuras/m7_visor_estres.png`.

## Pruebas en el Nano (2026-11-23)
**Calibración** (`datos/sesion_20261123_124903`): 2 min, 164 RR, 1 rechazado. Línea base en la EEPROM: HR0 = 82,8 BPM, RMSSD0 = 25,0 ms.

**Regla del plan (estrés = RMSSD ≤ 0,7 RMSSD0 y HR ≥ HR0 + 10): no detecta el estrés.**
- Protocolo de 3 × 2 min (`sesion_20261123_125241`) y restas de 7 en silencio (`sesion_20261123_130304`): el pulso sube 12-18 BPM, pero el RMSSD se queda en 25-32 ms, nunca por debajo de 17,5 ms.
- Primero parecía que el RMSSD subía mucho (52-67 ms) con el estrés. Era un error de medida: a ~100 BPM la onda dícrota se junta con el pico y su instante "baila". Se cambió el detector para marcar el latido por la máxima pendiente (ver notas_M5). Con el pico, 47-52 ms; con la pendiente, 25-32 ms. En reposo ambos coinciden.
- Hacer las restas "en voz baja" también sube el RMSSD: hablar cambia la respiración.

**Regla nueva:** estrés si HR ≥ HR0 + 10 y RMSSD ≤ 1,15 RMSSD0 (pulso alto sin aumento de la HRV), o HR ≥ HR0 + 15, o RMSSD ≤ 0,5 RMSSD0. Simulada sobre las grabaciones: detecta el estrés en las dos pruebas de restas. En el protocolo sintético, estrés a los 167,5 s (antes, 174,1 s).

**Prueba rápida con prensión isométrica** (`sesion_20261123_133600`, con marcas de fase en `_marcas.csv`; figura `figuras/m7_prension_nano.png`). Apretar fuerte con la mano libre sube el pulso en segundos, y no hace falta material:

| Fase | BPM | Estado |
|---|---|---|
| Reposo (221-243 s) | 85-88 | normal |
| Apretar (243-272 s) | 103-107 en 5 s, luego 92-98 | **estrés a los 253 s** (10 s de retraso); vuelve a normal a los 267 s, al bajar el pulso |
| Respiración lenta, 5 s + 5 s (272 s-) | 73-77 | **relajado a los 289 s** |

**Limitaciones observadas:**
- El pulso en reposo varió entre 75 y 92 BPM durante la sesión: con HR0 + 10 hay alguna falsa alarma (por ejemplo, a los 62 s de `sesion_20261123_131912`).
- Con la respiración lenta (6 por minuto) el RMSSD casi no sube: la oscilación de los RR es lenta (±60 ms cada ~10 latidos) y el RMSSD solo ve diferencias entre latidos seguidos. El SDNN o la amplitud de la oscilación la recogerían mejor. Posible mejora.
- Indicador orientativo, no clínico; así debe presentarse.

## Visor
- Con el Nano graba automáticamente desde que se abre (se perdieron pruebas por no pulsar Grabar).
- Botón "Marcar fase" (barra espaciadora): guarda el instante en `<sesión>_marcas.csv` para etiquetar las fases.

## Sesión 2026-11-24: sin calibrar frente a calibrado (vídeos en `videos/`)
- Nueva orden `o`: el Nano olvida la línea base (también en la EEPROM) y vuelve a "sin calibrar". En el visor: menú de perfil, "Sin perfil".
- Sin calibrar (`sesion_20261124_124742`, `sin_calibrar.mp4`): 127 latidos, 124 válidos, 92 BPM de media, RMSSD 21-24 ms. Estado "sin calibrar": sin línea base no hay con qué comparar.
- Calibración (`sesion_20261124_125053`, `calibracion.mp4`): HR0 = 91,0 BPM, RMSSD0 = 27,8 ms (el día anterior: 82,8 y 25,0). Guardada como perfil con nombre en `datos/perfiles.json`.
- Prensión con la línea base del día (`sesion_20261124_125442`, `calibrado_prension.mp4`):

| Fase | Pulso (BPM) | RMSSD (ms) | Estado |
|---|---|---|---|
| Reposo | 86-103 | 15-29 | normal |
| Prensión | sube a 112-121 | 28-44 | estrés a los ~3 s de pasar HR0 + 15 |
| Al soltar | 92-102 | 24-40 | estrés unos 25 s más (histéresis y medias), luego normal |
| Relajación | 84-97 | 30-40, hasta 60 | relajado (RMSSD ≥ 1,15 RMSSD0 = 32) |

  Secuencia limpia normal → estrés → normal → relajado. Con la línea base del día anterior (HR0 82,8) el reposo de hoy (88-97) rozaba el umbral de estrés: hay que calibrar en cada sesión o con cada persona.

## Segunda persona (2026-11-24, `sesion_20261124_130053`, sin vídeo)
- Calibración: HR0 = 65,9 BPM, RMSSD0 = 69,2 ms (frente a 91,0 y 27,8 del primero): la línea base personal es imprescindible, con umbrales absolutos uno saldría siempre "estrés" y el otro siempre "relajado".
- Tras calibrar: normal (63-74 BPM, RMSSD 60-71) → estrés al subir el pulso a 91-102 BPM (RMSSD cae a 23-28) → sigue en estrés con el pulso ya en 64-69 porque RMSSD ≤ 0,5 RMSSD0 = 35 → normal al recuperarse el RMSSD (63-86) → estrés al final con 80-81 BPM (≥ HR0 + 15).
- Relajado no llegó: exige RMSSD ≥ 1,15 RMSSD0 = 80 ms sostenido 10 latidos y solo hubo picos sueltos de 82-86.
