import argparse
from pathlib import Path
import sys


DIR_SCRIPT = Path(__file__).resolve().parent
if str(DIR_SCRIPT) not in sys.path:
    sys.path.insert(0, str(DIR_SCRIPT))

from discovery import (  # noqa: E402
    abrir_dumpstate,
    buscar_reporte_por_fecha,
    capturar_bugreport_adb,
    detectar_carpeta_fecha_de_ruta,
    es_carpeta_bugreport,
    extraer_zip_seguro,
    listar_reportes_por_fecha,
    localizar_archivo_principal,
    parsear_fecha_carpeta,
    resolver_carpeta_report,
    resolver_fuente,
)
from history import (  # noqa: E402
    cargar_historial_summaries,
    cargar_metrics_summary,
    comparar_reportes,
    construir_metrics_summary,
    guardar_metrics_summary,
)
from html_report import generar_html  # noqa: E402
from parser import (  # noqa: E402
    ESTADO_BATERIA,
    ESTADO_TERMICO,
    SALUD_BATERIA,
    analizar_dumpstate,
    diagnosticar,
    duracion_a_segundos,
    formatear_bytes,
    formatear_kb,
    limpiar_duracion,
    nombre_amigable,
    parsear_uid_android,
    resolver_uid,
    sanitizar_texto,
)


def _fmt_tendencia_consola(delta_info, sufijo="", entero=False):
    if not delta_info or delta_info.get("delta") is None:
        return ""
    simbolo = delta_info.get("simbolo", "=")
    if simbolo == "=":
        return " [=]"
    delta = delta_info["delta"]
    signo = "+" if delta > 0 else ""
    num_txt = f"{signo}{int(delta)}" if entero else f"{signo}{delta:.1f}"
    return f" [{simbolo} {num_txt}{sufijo}]"


def imprimir_resumen_consola(datos, diag, ruta_html, diff=None):
    """Imprime un diagnóstico legible y claro en la terminal con indicadores de tendencia."""
    disp = datos["dispositivo"]
    bat = datos["bateria"]
    alm = datos["almacenamiento"]
    mem = datos["memoria"]
    rt = datos["rendimiento_termico"]
    est = datos["estabilidad"]
    seg = datos["seguridad"]

    icono_global = {"bien": "🟢", "atencion": "🟡", "critico": "🔴"}[diag["nivel_global"]]
    modelo = disp["nombre_comercial"] or disp["modelo"] or "Android"
    sistema = f"Android {disp['android'] or '?'}"
    if disp["oneui"]:
        sistema += f" · One UI {disp['oneui']}"

    m_diff = diff.get("metricas", {}) if diff else {}
    t_pts = _fmt_tendencia_consola(m_diff.get("puntuacion"), " pts", entero=True)
    t_salud = _fmt_tendencia_consola(m_diff.get("salud_bateria_pct"), "%", entero=True)
    t_ds = _fmt_tendencia_consola(m_diff.get("deep_sleep_pct"), "%")
    t_tmax = _fmt_tendencia_consola(m_diff.get("temperatura_max_c"), " °C")

    print("=" * 66)
    print("📱 DIAGNÓSTICO DEL INFORME DE ERRORES")
    print("=" * 66)
    print(f"Equipo:         {disp['fabricante'] or ''} {modelo} ({disp['soc'] or disp['hardware'] or 'N/D'})".strip())
    print(f"Sistema:        {sistema} (parche {disp['parche_seguridad'] or 'N/D'})")
    print(f"Fecha informe:  {disp['fecha_informe'] or 'N/D'}")
    print(f"Encendido hace: {disp['uptime_texto'] or 'N/D'}")
    print("-" * 66)
    print(f"Estado general: {icono_global} {diag['veredicto']} — Puntuación: {diag['puntuacion']}/100{t_pts}")
    print(f"                {diag['frase_global']}")
    print("-" * 66)

    print("\n📊 RESUMEN RÁPIDO:")
    bat_extra = f"salud {bat['salud_asoc_pct']}%{t_salud}" if bat["salud_asoc_pct"] is not None else "salud N/D"
    if bat["ciclos"] is not None:
        bat_extra += f", ~{bat['ciclos']:.0f} ciclos"
    if bat.get("deep_sleep_pct") is not None:
        bat_extra += f", deep sleep {bat['deep_sleep_pct']:.1f}%{t_ds}"
    print(f"  🔋 Batería:        {bat['nivel'] if bat['nivel'] is not None else '?'}% ({bat_extra}, {bat['temperatura_c'] or '?'} °C)")
    if alm["data_uso_pct"] is not None:
        print(f"  💾 Almacenamiento: {alm['data_uso_pct']}% usado ({formatear_kb(alm['data_libre_kb'])} libres)")
    if mem["total_kb"] is not None:
        print(f"  🧠 Memoria RAM:    {formatear_kb(mem['total_kb'])} totales ({formatear_kb(mem['disponible_kb'])} disponibles)")
    sens_ap = next((s["valor_c"] for s in rt["sensores"] if s["nombre"] == "AP"), None)
    tmax = rt.get("temperatura_max_c")
    temp_extra = f" (CPU {sens_ap:.1f} °C" if sens_ap is not None else ""
    if tmax is not None:
        temp_extra = f"{temp_extra}, máx {tmax:.1f} °C{t_tmax})" if temp_extra else f" (máx {tmax:.1f} °C{t_tmax})"
    elif temp_extra:
        temp_extra += ")"
    print(f"  🌡️  Temperatura:    {ESTADO_TERMICO.get(rt['estado_termico'], 'N/D')}{temp_extra}")
    anormales = sum(1 for r in est["reinicios"] if r["categoria"] == "anormal")
    crashes = len(est["crashes_java"]) + len(est["crashes_nativos"])
    print(f"  🛡️  Estabilidad:    {anormales} reinicios anormales · {crashes} cierres puntuales en log")
    print(f"  🔒 Seguridad:      Arranque {seg['arranque_verificado'] or 'N/D'} · Cifrado {'sí' if seg['cifrado'] else 'no'}")

    if diff:
        print(f"\n📈 EVOLUCIÓN VS. {diff['fecha_anterior']}:")
        if diff["actualizacion_sistema"]["cambio"]:
            print(f"  🔄 Sistema: {' · '.join(diff['actualizacion_sistema']['detalles'])}")
        for reg in diff["regresiones"]:
            print(f"  ▼ Regresión: {reg}")
        for mej in diff["mejoras"]:
            print(f"  ▲ Mejora:    {mej}")
        if not diff["regresiones"] and not diff["mejoras"]:
            print("  = Sin variaciones significativas frente al reporte anterior.")

    criticos = [h for h in diag["hallazgos"] if h["severidad"] == "critico"]
    atencion = [h for h in diag["hallazgos"] if h["severidad"] == "atencion"]
    bien = [h for h in diag["hallazgos"] if h["severidad"] == "bien"]

    if criticos:
        print("\n🔴 PROBLEMAS IMPORTANTES:")
        for h in criticos:
            print(f"  • [{h['categoria']}] {h['titulo']}")
            print(f"    ↳ {h['explicacion']}")
            print(f"    ✔ Qué hacer: {h['recomendacion']}")

    if atencion:
        print("\n🟡 PUNTOS A REVISAR / SUGERENCIAS:")
        for h in atencion:
            print(f"  • [{h['categoria']}] {h['titulo']}")
            print(f"    ↳ {h['explicacion']}")
            print(f"    ✔ Qué hacer: {h['recomendacion']}")

    if bien:
        print("\n🟢 LO QUE ESTÁ BIEN:")
        for h in bien:
            print(f"  • [{h['categoria']}] {h['titulo']}")

    print("\n" + "=" * 66)
    print(f"📄 Reporte detallado HTML guardado en:\n   {ruta_html}")
    print("   Ábrelo en tu navegador para ver gráficos, línea de tiempo y detalles.")
    print("=" * 66)


def _imprimir_comparativa_diff(diff, ruta_html=None):
    """Imprime en consola el resumen dedicado de --diff entre dos fechas."""
    m = diff["metricas"]
    print("=" * 66)
    print(f"📊 COMPARATIVA HISTÓRICA: {diff['fecha_anterior']} → {diff['fecha_actual']}")
    print("=" * 66)
    if diff["actualizacion_sistema"]["cambio"]:
        print(f"🔄 Cambio de sistema: {' · '.join(diff['actualizacion_sistema']['detalles'])}")
    print(
        f"  • Puntuación:   {m['puntuacion']['anterior']}/100 → {m['puntuacion']['actual']}/100"
        f"{_fmt_tendencia_consola(m['puntuacion'], ' pts', entero=True)}"
    )
    print(
        f"  • Salud bat.:   {m['salud_bateria_pct']['anterior']}% → {m['salud_bateria_pct']['actual']}%"
        f"{_fmt_tendencia_consola(m['salud_bateria_pct'], '%', entero=True)}"
    )
    print(
        f"  • Deep Sleep:   {m['deep_sleep_pct']['anterior']}% → {m['deep_sleep_pct']['actual']}%"
        f"{_fmt_tendencia_consola(m['deep_sleep_pct'], '%')}"
    )
    print(
        f"  • Temp. máx.:   {m['temperatura_max_c']['anterior']} °C → {m['temperatura_max_c']['actual']} °C"
        f"{_fmt_tendencia_consola(m['temperatura_max_c'], ' °C')}"
    )
    print(
        f"  • Presión PSI:  {m['psi_memory_full_avg60']['anterior']}% → {m['psi_memory_full_avg60']['actual']}%"
        f"{_fmt_tendencia_consola(m['psi_memory_full_avg60'], '%')}"
    )
    if diff["regresiones"]:
        print("\n🔴 REGRESIONES / ALERTAS:")
        for r in diff["regresiones"]:
            print(f"  ▼ {r}")
    if diff["mejoras"]:
        print("\n🟢 MEJORAS:")
        for mej in diff["mejoras"]:
            print(f"  ▲ {mej}")
    if ruta_html:
        print(f"\n📄 Reporte HTML comparativo guardado en:\n   {ruta_html}")
    print("=" * 66)


def _analizar_reporte_fecha(rep, carpeta_report, ruta_html_custom=None, reporte_anterior_override=None):
    """Analiza un reporte de fecha en report/, guarda metrics_summary.json e HTML con diff automático."""
    with abrir_dumpstate(rep["carpeta"]) as (origen_nombre, lineas):
        print(f"Analizando informe ({rep['fecha_iso']}): {origen_nombre} ...")
        datos = analizar_dumpstate(lineas)

    diag = diagnosticar(datos)
    summary = construir_metrics_summary(
        datos, diag, fecha_iso=rep["fecha_iso"], carpeta_nombre=rep["carpeta_nombre"]
    )
    guardar_metrics_summary(summary, rep["ruta_summary"])

    reportes = listar_reportes_por_fecha(carpeta_report)
    summary_prev = None
    if reporte_anterior_override is not None:
        summary_prev = _asegurar_summary_de_reporte(reporte_anterior_override)
    else:
        for idx, item in enumerate(reportes):
            if item["carpeta"] == rep["carpeta"] and idx > 0:
                summary_prev = _asegurar_summary_de_reporte(reportes[idx - 1])
                break

    diff = comparar_reportes(summary, summary_prev) if summary_prev else None
    historial = cargar_historial_summaries(reportes)

    ruta_html = (
        Path(ruta_html_custom).expanduser().resolve()
        if ruta_html_custom
        else rep["ruta_html"]
    )
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    ruta_html.write_text(generar_html(datos, diag, diff=diff, historial=historial), encoding="utf-8")
    return datos, diag, summary, diff, ruta_html


def _asegurar_summary_de_reporte(rep):
    """Devuelve el metrics_summary.json de un reporte, generándolo por streaming si aún no existe."""
    summary = cargar_metrics_summary(rep["ruta_summary"])
    if summary is not None:
        return summary
    with abrir_dumpstate(rep["carpeta"]) as (origen_nombre, lineas):
        print(f"Generando caché de métricas ({rep['fecha_iso']}): {origen_nombre} ...")
        datos = analizar_dumpstate(lineas)
    diag = diagnosticar(datos)
    summary = construir_metrics_summary(
        datos, diag, fecha_iso=rep["fecha_iso"], carpeta_nombre=rep["carpeta_nombre"]
    )
    guardar_metrics_summary(summary, rep["ruta_summary"])
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analiza informes de errores (bugreport) de Android con seguimiento histórico."
    )
    parser.add_argument(
        "ruta",
        nargs="?",
        help="Ruta al archivo .zip, dumpstate.txt o carpeta del informe (por defecto busca la fecha más reciente en report/).",
    )
    parser.add_argument(
        "-o",
        "--salida",
        default=None,
        help="Ruta personalizada donde guardar el reporte HTML generado.",
    )
    parser.add_argument(
        "--date",
        metavar="FECHA",
        help="Analiza una fecha puntual dentro de report/ (YYYY-MM-DD o DD_MM_YY).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Procesa en lote todas las carpetas de fecha en report/ que aún no tengan su análisis generado.",
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("FECHA_1", "FECHA_2"),
        help="Compara dos fechas dentro de report/ (ej. --diff 2026-11-18 2026-11-20).",
    )
    parser.add_argument(
        "--adb",
        action="store_true",
        help="Captura un nuevo bugreport por ADB en report/<YYYY-MM-DD>/, lo descomprime y lo analiza.",
    )
    args = parser.parse_args(argv)

    modos_exclusivos = sum(bool(x) for x in (args.date, args.all, args.diff, args.adb, args.ruta))
    if modos_exclusivos > 1 and (args.all or args.diff or args.adb):
        parser.error("Los flags --all, --diff y --adb son mutuamente excluyentes y no admiten otra ruta o --date.")

    if args.adb:
        carpeta_report = resolver_carpeta_report(DIR_SCRIPT) or (DIR_SCRIPT / "report")
        carpeta_report.mkdir(parents=True, exist_ok=True)
        nueva_carpeta = capturar_bugreport_adb(carpeta_report)
        rep = detectar_carpeta_fecha_de_ruta(nueva_carpeta, carpeta_report)
        if rep is None:
            raise FileNotFoundError(f"No se pudo indexar el bugreport capturado en {nueva_carpeta}")
        datos, diag, _, diff, ruta_html = _analizar_reporte_fecha(
            rep, carpeta_report, ruta_html_custom=args.salida
        )
        imprimir_resumen_consola(datos, diag, ruta_html, diff=diff)
        return 0

    if args.all:
        carpeta_report = resolver_carpeta_report(DIR_SCRIPT)
        if carpeta_report is None:
            raise FileNotFoundError("No se encontró la carpeta 'report/' para procesar con --all.")
        reportes = listar_reportes_por_fecha(carpeta_report)
        if not reportes:
            raise FileNotFoundError(f"No hay carpetas de fecha con bugreports válidos en {carpeta_report}")

        procesados = 0
        omitidos = 0
        for rep in reportes:
            if rep["ruta_summary"].is_file() and rep["ruta_html"].is_file():
                omitidos += 1
                print(f"Saltando {rep['fecha_iso']} ({rep['carpeta_nombre']}): análisis ya existente.")
                continue
            datos, diag, _, diff, ruta_html = _analizar_reporte_fecha(rep, carpeta_report)
            imprimir_resumen_consola(datos, diag, ruta_html, diff=diff)
            procesados += 1

        print(f"\nLote --all completado: {procesados} analizado(s), {omitidos} ya tenían análisis.")
        return 0

    if args.diff:
        carpeta_report = resolver_carpeta_report(DIR_SCRIPT)
        if carpeta_report is None:
            raise FileNotFoundError("No se encontró la carpeta 'report/' para comparar con --diff.")
        rep1 = buscar_reporte_por_fecha(carpeta_report, args.diff[0])
        rep2 = buscar_reporte_por_fecha(carpeta_report, args.diff[1])
        summary1 = _asegurar_summary_de_reporte(rep1)
        datos, diag, summary2, diff, ruta_html = _analizar_reporte_fecha(
            rep2,
            carpeta_report,
            ruta_html_custom=args.salida,
            reporte_anterior_override=rep1,
        )
        _imprimir_comparativa_diff(diff, ruta_html=ruta_html)
        return 0

    if args.date:
        carpeta_report = resolver_carpeta_report(DIR_SCRIPT)
        if carpeta_report is None:
            raise FileNotFoundError("No se encontró la carpeta 'report/' para buscar por --date.")
        rep = buscar_reporte_por_fecha(carpeta_report, args.date)
        datos, diag, _, diff, ruta_html = _analizar_reporte_fecha(
            rep, carpeta_report, ruta_html_custom=args.salida
        )
        imprimir_resumen_consola(datos, diag, ruta_html, diff=diff)
        return 0

    # Sin argumentos o con ruta posicional directa
    fuente = resolver_fuente(args.ruta, base_script=DIR_SCRIPT)
    carpeta_report = resolver_carpeta_report(DIR_SCRIPT)
    rep_meta = detectar_carpeta_fecha_de_ruta(fuente, carpeta_report)

    if rep_meta is not None and carpeta_report is not None:
        datos, diag, _, diff, ruta_html = _analizar_reporte_fecha(
            rep_meta, carpeta_report, ruta_html_custom=args.salida
        )
        imprimir_resumen_consola(datos, diag, ruta_html, diff=diff)
        return 0

    # Ruta externa arbitraria (.zip, dumpstate.txt o carpeta fuera de report/)
    with abrir_dumpstate(fuente) as (origen_nombre, lineas):
        print(f"Analizando informe: {origen_nombre} ...")
        datos = analizar_dumpstate(lineas)

    diag = diagnosticar(datos)
    ruta_html = (
        Path(args.salida).expanduser().resolve()
        if args.salida
        else (DIR_SCRIPT / "informe_diagnostico.html").resolve()
    )
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    ruta_html.write_text(generar_html(datos, diag), encoding="utf-8")

    imprimir_resumen_consola(datos, diag, ruta_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
