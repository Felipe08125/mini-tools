# bugreport-analyzer

Herramienta en Python (biblioteca estándar, 0 dependencias externas) que analiza informes de errores (`bugreport`) de Android mediante streaming en una sola pasada y mantiene seguimiento histórico entre fechas.

## Arquitectura modular

- `discovery.py`: descubrimiento de carpetas por fecha en `report/` (`YYYY-MM-DD` y `DD_MM_YY` / `DD-MM-YY`), localización automática de `dumpstate.txt` o `bugreport-*.txt` en raíz o subcarpetas extraídas, lectura streaming (`abrir_dumpstate`) y captura/descompresión segura vía `--adb`.
- `parser.py`: motor de análisis en una sola pasada por streaming (`analizar_dumpstate`), cálculo de *Deep Sleep*, temperaturas máximas, presión PSI / kills LMKD, reconstrucción de línea de tiempo unificada y correlaciones, sanitización estricta de privacidad y diagnóstico (`diagnosticar`).
- `history.py`: generación y carga de `metrics_summary.json` (`schema_version = 1`) y motor de comparación histórica (`comparar_reportes`) para detectar actualizaciones del sistema, regresiones y apps con drenaje en segundo plano.
- `html_report.py`: generador HTML autocontenido con evolución comparativa, gráfico SVG de tendencia histórica y línea de tiempo interactiva (SVG + Vanilla JS) filtrable por severidad y categoría.
- `main.py`: CLI principal, orquestación de modos (`--date`, `--all`, `--diff`, `--adb`) y salida en consola enriquecida con indicadores `▲` / `▼` / `=`.

## Requisitos

- Python 3.8 o superior
- Sin dependencias externas (exclusivamente biblioteca estándar de Python)

## Estructura esperada en `report/`

Acepta carpetas descomprimidas organizadas por fecha (`YYYY-MM-DD`, o formatos existentes tipo `DD_MM_YY` como `18_11_26`) con el archivo principal en la raíz o dentro de una subcarpeta extraída:

```text
report/
├── 2026-10-01/
│   ├── bugreport-SM8550-2026-10-01.txt
│   ├── FS/
│   └── version.txt
├── 2026-11-15/
│   └── bugreport-2026-11-15/
│       ├── dumpstate.txt
│       └── FS/
└── 2026-11-20/
    ├── dumpstate.txt
    └── lshal-debug/
```

## Uso rápido

```bash
# Analizar automáticamente la fecha más reciente en report/ (y comparar contra la anterior)
python3 bugreport-analyzer/main.py

# Analizar una fecha puntual
python3 bugreport-analyzer/main.py --date 2026-11-20

# Procesar en lote todas las fechas pendientes de report/
python3 bugreport-analyzer/main.py --all

# Comparar dos fechas explícitamente
python3 bugreport-analyzer/main.py --diff 2026-11-18 2026-11-20

# Capturar bugreport por ADB en report/<YYYY-MM-DD>/, descomprimir y analizar al instante
python3 bugreport-analyzer/main.py --adb

# Modo retrocompatible con ruta directa (.zip, dumpstate.txt o carpeta)
python3 bugreport-analyzer/main.py ruta/al/bugreport.zip -o mi_diagnostico.html
```

Cada carpeta analizada en `report/<fecha>/` guarda:
- `metrics_summary.json`: resumen ligero y sanitizado para comparaciones históricas.
- `informe_diagnostico.html`: reporte interactivo offline con evolución histórica y línea de tiempo SVG/JS.

## Privacidad

- El análisis corre **100% offline** en local.
- Se omiten y redactan identificadores sensibles: número de serie (`ro.boot.serialno`), IMEI/MEID/IMSI, direcciones MAC y nombres de redes Wi-Fi (SSID).
- `report/` e `informe_diagnostico*.html` permanecen ignorados en `.gitignore`.
