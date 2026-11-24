# Notas M3: adquisición a 500 Hz

Código: `firmware/pruebas/m3_timer/` (prueba) y `firmware/pulso/adquisicion.h/.cpp` (final). Monitor: `pc/monitor_m3.py`.

- Timer1 en modo CTC, prescaler 64, OCR1A = 499: 16 MHz / (64 · 500) = 500 Hz.
- La ISR lee A0 y lo guarda en un buffer circular de 256 muestras `uint16_t` (512 B, ≈0,5 s de margen). Índices de 8 bits: dan la vuelta solos a 256.
- `loop()` saca las muestras con `adquisicionLee()`. Si se ha retrasado más de 256 muestras, se marcan como perdidas y el índice salta (el detector se reinicia: un RR con hueco no sería fiable).
- D12 (PB4) está alto durante la ISR, para medirla con el osciloscopio.

## Verificación en el Nano (2026-11-16)
- 12 s de lectura: 1202 líneas a 100 Hz, ningún salto distinto de 10 ms; el Nano informa `perdidas=0` en 5000 muestras.
- Frecuencia real medida con el reloj del PC: **500,39 Hz** (+0,08 %, tolerancia del oscilador del clon). Un RR de 800 ms se mide con ≈0,6 ms de error: despreciable para BPM y HRV.
- Segunda prueba de ≈20 s: 10 000 muestras, 0 perdidas.
- Con el firmware completo (detector, HRV, estado y envío serie a 100 Hz) en las sesiones del 2026-11-23: 0 muestras perdidas y 0 saltos en grabaciones de hasta 6 min.
