# Notas M0-M1: sensor y divisor de tensión

## M0: identificación del sensor (17/11/2026)
- Emisor: LED blanco. En modo diodo el multímetro marca "1" (fuera de rango) aunque el LED se enciende: Vf > rango de la prueba de diodo, típico de LED blanco (≈3 V).
- Detector: LDR (fotorresistencia). Resistencia simétrica (igual en ambos sentidos), depende de la luz:

| Situación | R_LDR |
|---|---|
| Tapada con la mano | ≈250 kΩ |
| Luz de sala | 10-90 kΩ |
| Linterna del móvil | < 1 kΩ |
| LED apagado (sala) | 13,5 kΩ |
| LED encendido, sin dedo | 0,3 kΩ |
| LED encendido, con dedo | ≈4,0 kΩ  (punto de trabajo) |

## Resistencia del LED: 100 Ω (medida 97,1 Ω)
I = (5 V - Vf) / R ≈ (5 - 3,1) / 97,1 ≈ 19,6 mA, dentro de los 20 mA nominales de un LED de 5 mm.

## Resistencia fija del divisor: R = R_LDR en el punto de trabajo (≈4 kΩ) -> 3,9 kΩ (E12)
Divisor con la LDR abajo: Vs = Vcc · R_LDR / (R + R_LDR).

El pulso produce una variación pequeña ΔR de R_LDR. La sensibilidad es
dVs/dR_LDR = Vcc · R / (R + R_LDR)^2.
Derivando respecto a R e igualando a 0: (R + R_LDR) - 2R = 0  ->  **R = R_LDR**.
Con R = R_LDR: ΔVs = (Vcc/4) · (ΔR/R_LDR) y Vs = Vcc/2 = 2,5 V (centro del ADC, mismo margen arriba y abajo).

Valores comerciales serie E12 cercanos a 4,0 kΩ: 3,9 kΩ y 4,7 kΩ.
Sensibilidad relativa respecto al óptimo: S/Smax = 4·R·R_LDR / (R + R_LDR)^2

| R | S/Smax | Vs con dedo |
|---|---|---|
| 3,9 kΩ | 99,98 % | 2,53 V |
| 4,7 kΩ | 99,35 % | 2,30 V |

El óptimo es muy plano: aunque R_LDR cambie con el dedo o la presión, la sensibilidad apenas varía.

Por qué la LDR va abajo (a GND): más sangre -> menos luz -> más R_LDR -> más Vs. El latido aparece como un máximo (onda no invertida).

Estimación: si el pulso cambia R_LDR un ≈1 %, ΔVs ≈ 1,25 V · 0,01 ≈ 12 mV ≈ 2-3 pasos del ADC (4,9 mV/paso) -> hace falta amplificar (M2). Verificar en el paso 4.

## Paso 4: divisor montado (R fija 3,9 kΩ, medida 3,86 kΩ)
Multímetro: Vs sin dedo 0,37 V (R_LDR ≈ 0,31 kΩ); con dedo 2,5-2,7 V (R_LDR ≈ 4,2 kΩ). Coincide con M0.

Registro de 52 s a 100 Hz sin amplificar: `datos/m1_divisor_sin_amplificar.csv`, figura `figuras/m1_senal_sin_amplificar.png`.
- Dedo dentro de ≈8 s a ≈44 s. Al meter/sacar el dedo hay un sobrepico (presión + respuesta lenta de la LDR).
- Con el dedo: deriva lenta de +70 mV en 30 s y variación de 20-30 mV p-p.
- Componente 0,5-5 Hz: ≈9 mV p-p ≈ 2 escalones del ADC (4,9 mV). Solo 17 niveles distintos del ADC en 32 s: la señal está dominada por la cuantización.
- Espectro: pico en 1,56 Hz (94 BPM) con armónico en ≈3,1 Hz, pero apenas 4,6 veces sobre el fondo. El pulso está, pero no se puede detectar latido a latido de forma fiable.
- Conclusión: confirma la predicción (≈12 mV) y justifica la etapa de amplificación M2 (ganancia ≈100: 9 mV -> ≈1 V p-p).
