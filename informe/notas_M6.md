# Notas M6: BPM y HRV

Código: `firmware/pulso/hrv.h/.cpp` (en el Nano) y `pc/analisis.py` (sesión completa en el PC).
Se prueba con el mismo banco que el M5 (`pc/test_detector.cpp`).

## En el Nano (por latido)
1. **Rechazo de artefactos.** Se descarta un RR:
   - fuera de 300-2000 ms (200-30 BPM);
   - que se aleje más de un **30 %** del último RR válido. Un latido perdido da un RR doble (+100 %) y uno de más lo parte (-50 %).
   - Si se rechazan 5 seguidos, la referencia estaba mal y se reinicia todo.
   - Sin referencia (al arrancar o tras reiniciar), el primer RR solo se acepta si coincide ±30 % con el anterior. Antes un primer RR malo se convertía en referencia y hacía rechazar los 5 buenos siguientes.
2. **Ventana de 30 RR válidos (~30 s).** SDNN = desviación típica de los RR; RMSSD = raíz de la media de las diferencias al cuadrado entre RR **contiguos**. Si entre dos RR válidos hubo uno rechazado, esa diferencia no se usa. Se publican a partir de 10 RR.
3. **BPM** = 60000 / media de los últimos 8 RR válidos (antes estaba en el detector, con todos los RR; ahora usa solo los válidos).
4. **Aritmética entera exacta** hasta la raíz: varianza = (N·ΣRR² - (ΣRR)²) / (N(N-1)) en `uint32_t`. Con N ≤ 30 y RR ≤ 2000 ms, N·ΣRR² ≤ 3,6·10⁹ < 2³² = 4,29·10⁹, así que no hay desbordamiento ni error de redondeo.

### Por qué 30 % y no el 20 % del plan
- En `m5_latidos_1` (tramo estable 65-106 s) el RR cambia de un latido al siguiente hasta un **25,5 %** (p95: 12,9 %) por la arritmia sinusal respiratoria: el tacograma oscila entre 590 y 830 ms con un periodo de ~10 s.
- Con un 20 % se rechazaban 17 RR buenos de 64. Con un 30 % solo se rechazan los 5 artefactos reales (un latido perdido de 1324 ms y 4 al sacar el dedo).
- También se probó comparar con la mediana de los últimos 5 RR: es peor, porque cuando el ritmo sube o baja varios latidos seguidos la mediana se queda atrás (desviación de hasta el 42 %).

## Validación (señal sintética a 500 Hz, ventana de 30 RR)
Primera tabla con el detector por pico (M5 inicial); segunda columna con el firmware final (latido en la máxima pendiente, ver notas_M5).

| Caso | Esperado | Pico | Final (pendiente) |
|---|---|---|---|
| RR alternando 800/900 ms (prueba del plan) | RMSSD 100 ± 2, SDNN 50,9 ± 2 ms | 100,0 / 50,9 ms | **100,9 / 51,4 ms** |
| Arritmia RR = 800 + 60 sin(2πn/5) | RMSSD 49,0, SDNN 43,2 ms | 49,0 / 43,1 ms | 49,4 / 43,6 ms |
| Arritmia con 3 latidos muy débiles | los 3 RR dobles rechazados; HRV igual que sin ellos | 3 rechazados; 49,3 / 43,3 ms | 3 rechazados; 49,8 / 43,8 ms |
| 60, 72, 120 BPM constantes | RMSSD ≈ 0, BPM exacto | 0,6-1,1 ms | RMSSD 3,4-3,8 ms; BPM 60,0 / 72,0 / 120,0 |

- Error de RR del firmware final frente a la verdad: medio < 0,1 ms, eficaz ~2 ms, máximo 5-6 ms. El detector por pico era más preciso con esta señal sintética (cima gaussiana limpia), pero con la señal real a ritmo alto su instante "baila" mucho más (ver notas_M5 y M7). El suelo de ~3,5 ms de RMSSD es pequeño frente a los 20-60 ms reales.
- Primer RR: ahora sale como "sin RR" (resultado 1) y el segundo solo se acepta si coincide ±30 % con el primero. Por eso los casos tienen 2 latidos sin RR.

## Datos reales
| Grabación | Latidos | Válidos | Rechazados | BPM | RMSSD | SDNN |
|---|---|---|---|---|---|---|
| `m2_amplificado_g68` (última ventana) | 60 | 59 | 0 | 77,1 | 29,9 ms | 53,7 ms |
| `m5_latidos_1` (última ventana) | 64 | 58 | 5 | 87,3 | 36,0 ms | 60,5 ms |

## Análisis en el PC (`pc/analisis.py`)
- Usa todos los RR válidos de la sesión y calcula BPM, SDNN, RMSSD, pNN50 y Poincaré (SD1, SD2).
- Comprobación: SD1 = RMSSD/√2 (28,4 = 40,2/√2).
- `m5_latidos_1`, tramo 65-106 s (figura `figuras/m6_hrv_m5_latidos_1.png`): 58 RR, 88,3 BPM, SDNN 73,1 ms, RMSSD 40,2 ms, pNN50 16 %, SD1 28 ms, SD2 99 ms. SD2 >> SD1: domina la oscilación lenta respiratoria sobre la variación latido a latido.
- Para el informe hay que grabar **5 min** (el estándar de registro corto). Con 41 s el SDNN se subestima, y el programa lo avisa.

## Limitación a discutir en el informe
Con PPG se mide la variabilidad del *pulso* (PRV), no la del ECG. En reposo coinciden bien; con movimiento o estrés la PRV se desvía.
