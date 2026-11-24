# Notas M2: amplificación con TL082 y fuente de ±12 V

Esquema: `figuras/m2_tl082.png` (fuente `figuras/m2_tl082.tex`).

## Por qué este diseño
- Único operacional disponible: TL082CP (2 amplificadores, entrada JFET, 8 patas).
- El TL082 no sirve con 5 V: su rango de entrada en modo común empieza ≈4 V por encima de V- y su salida no se acerca a menos de ≈1,5 V de cada alimentación. Se alimenta a ±12 V con la fuente doble del laboratorio (DF1731SB) y todas las etapas se referencian a 0 V (GND): no hace falta tensión de referencia.
- Como la salida podría llegar a ±10 V, se añade al final un desplazamiento a 2,5 V y una protección de A0.

## Valores
| Elemento | Valor | Justificación |
|---|---|---|
| C1, R_B1 | 10 µF, 47 kΩ | Paso alto f = 1/(2π·47k·10µ) = 0,34 Hz: quita la DC (2,6 V) y la deriva; conserva el pulso (0,67-3,3 Hz). τ = 0,47 s: se recupera rápido al meter el dedo. 47 kΩ >> 2 kΩ de salida del divisor: no lo carga. |
| R1, R2 | 4,7 kΩ, 100 kΩ | G1 = 1 + R2/R1 = 22,3. Pulso medido ≈9 mV p-p -> ≈0,2 V. Ganancia moderada para no saturar con el offset del TL082 (hasta ≈15 mV · 22 ≈ 0,3 V), que elimina C2. |
| Cf | 150 nF | Paso bajo f = 1/(2π·100k·150n) = 10,6 Hz: conserva la forma del pulso, quita ruido y 50 Hz. |
| C2, R_B2 | 10 µF, 47 kΩ | Segundo paso alto (0,34 Hz): elimina el offset amplificado de la etapa 1. |
| R3, R4 | 10 kΩ, trimmer 100 kΩ | G2 = 1 + R4/R3 = 1 a 11. Ganancia total 22-245. Objetivo ≈2 V p-p en A0 (9 mV · 220). |
| C3 + 2×100 kΩ | 10 µF | Desplaza la señal a 2,5 V (centro del ADC). Paso alto 1/(2π·50k·10µ) = 0,32 Hz. El + de C3 hacia el lado de 2,5 V. |
| Ro, D1, D2 | 10 kΩ, 1N4148 | Si la etapa satura, los diodos limitan A0 a -0,6...5,6 V y Ro limita la corriente a ≈1 mA. 10 kΩ es la impedancia de fuente máxima recomendada para el ADC del ATmega328P. |
| Co | 100 nF | Antialiasing f = 1/(2π·10k·100n) = 159 Hz < 250 Hz (Nyquist a 500 Hz). Además carga el condensador de muestreo del ADC. |
| 100 nF en patas 8 y 4 | | Desacoplo de la alimentación del TL082. |

Patillaje TL082: 1 OUT A, 2 IN- A, 3 IN+ A, 4 V-, 5 IN+ B, 6 IN- B, 7 OUT B, 8 V+.

## Medidas reales (multímetro)
### Alimentación
| Magnitud | Día 1 | Día 2 (fuente recalibrada) |
|---|---|---|
| +12 V | 11,71 V | 11,80 V |
| -12 V | -11,80 V | -11,75 V |
| Pata 8 (V+) en el chip | 11,62 V | |
| Pata 4 (V-) en el chip | -11,80 V | |
| Consumo | 0,01 A en -12 V, 0,00 A en +12 V (resolución de la fuente; es el consumo propio del TL082, ≈2,8 mA típico) | |

### Componentes
| Elemento | Nominal | Real |
|---|---|---|
| Desacoplo pata 8 | 100 nF | 97,1 nF |
| Desacoplo pata 4 | 100 nF | 98,9 nF |
| C1 | 10 µF | 10,2 µF (al principio se montó por error uno de 10 nF = 9,67 nF, que daba fc ≈ 340 Hz) |
| R_B1 | 47 kΩ | 47,3 kΩ |
| R1 | 4,7 kΩ | 4,6 kΩ |
| R2 | 100 kΩ | 99,2 kΩ |
| Cf | 150 nF | 147 nF |
| C2 | 10 µF | 9,34 µF |
| R_B2 | 47 kΩ | 46,2 kΩ |
| R3 | 10 kΩ | 9,79 kΩ |

Valores con componentes reales: G1 = 1 + 99,2/4,6 = 22,6; paso bajo 1/(2π·99,2k·147n) = 10,9 Hz; paso alto 1/(2π·47,3k·10,2µ) = 0,33 Hz.

### Comprobación de la etapa 1 (pata 1)
- Sin dedo: 0,06 V (offset de entrada ≈2,7 mV × 22,6).
- Con dedo: salto grande al meterlo, vuelve a ≈0 V en ≈1-2 s y oscila al ritmo del pulso.

### Primera prueba de la etapa 2 (pata 7): fallo
- Sin dedo: 11,23 V (saturada a +V).
- Con dedo: lecturas erráticas (-9...+5 V) y el raíl negativo cae a -9/-10 V: oscilación o enclavamiento. Diagnóstico: no se había montado R4 (pata 6-7 en abierto, el multímetro marcaba "1."), el op-amp estaba en lazo abierto. Además se midieron resistencias con la fuente encendida, lo que falsea la medida y cargaba el raíl negativo.
- Lección: medir resistencias siempre con la fuente apagada y desconectada.

### Etapa 2 corregida
- R4: potenciómetro de 100 kΩ (cursor + un extremo), puesto a 0,2 Ω -> G2 ≈ 1,0.
- Pata 7 sin dedo: 0,00 V. Con dedo: transitorio de unos segundos, después ≈0 V con variaciones de ±0,02-0,03 V (positivas y negativas: señal centrada en 0 V por el acoplo en alterna). El multímetro promedia, así que subestima el pico a pico (esperado ≈0,2 V).

### Etapa de salida: diodos
- No hay 1N4148: se usan 2 × 1N4007. Válidos: a < 5 Hz su lentitud (trr ≈µs) y su capacidad (≈15 pF) no importan; la fuga inversa (< 5 µA máx a 25 °C) por Ro = 10 kΩ daría como mucho ≈50 mV de error en continua, que no afecta al pulso (señal alterna).
- Alternativa estudiada sin diodos externos: Ro = 47 kΩ apoyándose en los diodos internos del ATmega328P (AVR182, ≈1 mA máx). C3 bloquea la DC, así que solo pasan transitorios: peor caso (24 - 5,5)/47k ≈ 0,4 mA. Antialiasing pasaría a 34 Hz.

### Etapa de salida (desplazamiento a 2,5 V y protección)
| Elemento | Nominal | Real |
|---|---|---|
| C3 | 10 µF | 11,25 µF |
| Divisor superior / inferior | 100 kΩ / 100 kΩ | 98,2 kΩ / 98,2 kΩ |
| Ro | 10 kΩ | 9,8 kΩ |
| Co | 100 nF | ≈100 nF |
| D1, D2 | 1N4148 | |

- Paso alto C3 con el divisor: 1/(2π·49,1k·11,25µ) = 0,29 Hz. Antialiasing Ro·Co: 1/(2π·9,8k·100n) = 162 Hz.
- Nodo c y A0: 2,35 V. Es la mitad del 5V del Nano por USB (≈4,7 V, el USB pasa por un diodo de protección). El ADC usa ese mismo 5V como referencia, así que 2,35 V es justo el centro de escala (ADC ≈ 512): el resultado no depende de que el USB dé 4,7 o 5,0 V.

### Primera señal amplificada (G ≈ 22,6, potenciómetro a 0)
- Fichero `datos/m2_amplificado_g1.csv` (70,6 s), figura `figuras/m2_senal_g1.png`.
- 0 muestras perdidas, 0 saltos de tiempo.
- Sin dedo: 2,323 V, con 5 mV p-p (1 LSB): ruido del circuito por debajo de la resolución del ADC.
- Con dedo (34-62 s): pulso de ≈0,5-0,6 V p-p, con la muesca dicrota visible. Pico espectral en 1,64 Hz = 99 BPM.
- El pulso en Vs es por tanto ≈0,55/22,6 ≈ 24 mV p-p (más que los 9 mV de la medida sin amplificar: depende de la presión y la posición del dedo).
- Al meter y sacar el dedo hay transitorios de 2-3 s. Al sacarlo la señal llegó a 0 V y a 4,3 V: los diodos y el rango del ADC la limitaron sin daño.
- Ajuste elegido: G2 ≈ 3 (R4 ≈ 20 kΩ), ganancia total ≈ 68, pulso esperado ≈1,5 V p-p. Deja margen frente a los 4,7 V del ADC si el pulso crece con la presión del dedo.

### Pruebas del usuario con G ≈ 22,6 (antes de ajustar el potenciómetro)
- `datos/test.csv` (46,5 s, ±11,8 V): igual que la primera grabación, pulso ≈0,3-0,7 V p-p, 0 saltos.
- `datos/test5-5.csv` (34 s, fuente a ±5 V): funciona igual, pulso ≈0,4-0,75 V p-p, 0 saltos.
- Por qué funciona a ±5 V: todas las señales del TL082 están cerca de 0 V. Su entrada admite hasta ≈3 V por encima de V- (-2 V) y su salida llega a ≈±3,5 V, de sobra para el pulso (≈1,5 V p-p con G ≈ 68). Aun así se mantiene ±12 V: es donde el fabricante garantiza las características y deja más margen a la salida.

### Ajuste de ganancia
- R4 (potenciómetro) = 19,9 kΩ -> G2 = 1 + 19,9/9,79 = 3,03. Ganancia total = 22,6 · 3,03 = 68,5.
- Grabación `datos/m2_amplificado_g68.csv` (83,6 s, 0 saltos): el pulso sigue en ≈0,45-0,65 V p-p, igual que con G ≈ 22. La ganancia de la etapa 2 no había subido: el potenciómetro estaba mal conectado (seguía habiendo ≈0 Ω entre las patas 6 y 7). Corregido por el usuario.
- Grabación repetida `datos/m2_amplificado_g68.csv` (76,7 s, 0 saltos), figura `figuras/m2_senal_g68.png`:
  - Sin dedo: 2,343 V, ruido 1 LSB.
  - Con dedo estable (27-68 s): pulso de 1,5-2,0 V p-p, entre ≈1,7 V y ≈3,8 V. Sin saturación: queda margen hasta 0 y 4,7 V. Muesca dicrota clara.
  - Al meter y sacar el dedo la etapa satura unos 8 s (0 / 4,7 V) hasta que se cargan C1-C3. Es el precio de la ganancia alta; el firmware deberá ignorar ese tramo.
  - Prueba rápida de detección (umbral 60 %, refractario 300 ms): 59 latidos, RR medio 731 ms = 82,1 BPM, RR de 610 a 850 ms, SDNN 54 ms, RMSSD 30 ms. Valores fisiológicos normales en reposo.
  - El espectro tiene varios picos entre 1,3 y 1,6 Hz: el ritmo varía latido a latido (arritmia sinusal respiratoria). Esa variación es justo la HRV que se quiere medir.
- Conclusión M2: G = 68,5 es la ganancia final.
