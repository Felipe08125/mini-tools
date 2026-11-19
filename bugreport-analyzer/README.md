# bugreport-analyzer

Herramienta en Python que analiza el **informe de errores (bugreport)** de un teléfono Android y combina un análisis técnico detallado con explicaciones claras para usuarios no técnicos.

Genera:

- 🖥️ Un resumen rápido con semáforo (`🟢` / `🟡` / `🔴`) y recomendaciones en consola
- 📄 Un reporte HTML interactivo offline (`informe_diagnostico.html`) con tarjetas visuales y bloques técnicos desplegables

## Requisitos

- Python 3.8 o superior
- Sin dependencias externas (solo usa la biblioteca estándar de Python)

## Cómo usarlo

1. Genera el informe de errores en tu teléfono Android:
   - Activa las **Opciones de desarrollador** (*Ajustes → Acerca del teléfono → Información de software → toca 7 veces en Número de compilación*)
   - Ve a **Ajustes → Opciones de desarrollador → Informe de errores → Informe completo** (o *Tomar informe de errores*)
2. Copia el archivo `.zip` o la carpeta descomprimida dentro de `bugreport-analyzer/report/` (a la misma altura que `main.py`), o pásale la ruta por argumento.
3. Ejecuta desde la raíz del proyecto o dentro de `bugreport-analyzer/`:

   ```bash
   python3 bugreport-analyzer/main.py
   # o desde dentro de bugreport-analyzer/:
   python3 main.py
   ```

   También puedes indicar una ruta específica o elegir el nombre del archivo HTML de salida:

   ```bash
   python3 bugreport-analyzer/main.py ruta/al/bugreport.zip -o mi_diagnostico.html
   ```

4. Abre `bugreport-analyzer/informe_diagnostico.html` en cualquier navegador web.

## Ejemplo de salida

```
==================================================================
📱 DIAGNÓSTICO DEL INFORME DE ERRORES
==================================================================
Equipo:         samsung SM-DEMO1 (SM8550)
Sistema:        Android 15 · One UI 7.0 (parche 2026-05-05)
Fecha informe:  2026-06-15 12:00:00
Encendido hace: 3 days, 04:10
------------------------------------------------------------------
Estado general: 🟡 Buen estado con observaciones — Puntuación: 84/100
...
📄 Reporte detallado HTML guardado en:
   .../bugreport-analyzer/informe_diagnostico.html
```

## Privacidad

Los informes de errores contienen registros del sistema, aplicaciones instaladas e identificadores del teléfono.
- El análisis corre **100% en local**, sin enviar datos a internet.
- La herramienta omite datos sensibles como número de serie, IMEI y nombres de redes Wi-Fi.
- Las carpetas `report/`, `bugreport-*/` y los archivos `informe_diagnostico*.html` están incluidos en `.gitignore` para evitar subirlos por accidente.

## Cómo funciona

- Acepta una carpeta `bugreport-*`, un archivo `.zip` o directamente un `dumpstate.txt`.
- Lee el archivo completo en **una sola pasada por streaming** (sin cargarlo entero en memoria) para procesar archivos grandes (200+ MB) en segundos.
- Cruza datos de `batterystats`, `battery`, `meminfo`, `diskstats`, `df`, `UFS`, `thermalservice`, `PSI`, `logcat`, `dmesg`, `AP RESET INFO`, `telephony`, `wifi` y `getprop`.
- Resuelve los identificadores `UID` internos de Android al nombre real de cada aplicación usando la tabla de paquetes del propio informe.
- Filtra latidos informativos de diagnóstico (como `Watchdog: !@Sync:`) para evitar falsas alarmas y traduce los hallazgos a lenguaje cotidiano.
