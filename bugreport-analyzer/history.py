from datetime import datetime
import json
from pathlib import Path

from parser import nombre_amigable, sanitizar_texto


SCHEMA_VERSION = 1


def _contar_anr_crashes_por_app(est):
    """Agrupa ANRs y crashes (Java y nativos) por aplicación o ejecutable sanitizado."""
    mapa = {}

    def _asegurar(clave):
        if clave not in mapa:
            mapa[clave] = {"anr": 0, "crashes_java": 0, "crashes_nativos": 0, "total": 0}
        return mapa[clave]

    for a in est.get("anrs_logcat", []):
        proc_raw = (a.get("proceso") or "desconocido").split("/", 1)[0].split()[0]
        item = _asegurar(sanitizar_texto(proc_raw))
        item["anr"] += 1
        item["total"] += 1

    for c in est.get("crashes_java", []):
        proc = sanitizar_texto(c.get("proceso") or "desconocido")
        item = _asegurar(proc)
        item["crashes_java"] += 1
        item["total"] += 1

    for c in est.get("crashes_nativos", []):
        proc_raw = c.get("ejecutable") or c.get("proceso") or "nativo"
        proc = sanitizar_texto(Path(str(proc_raw)).name if "/" in str(proc_raw) else str(proc_raw))
        item = _asegurar(proc)
        item["crashes_nativos"] += 1
        item["total"] += 1

    return mapa


def construir_metrics_summary(datos, diag, fecha_iso=None, carpeta_nombre=None):
    """Construye el diccionario ligero y sanitizado para guardar en metrics_summary.json."""
    disp = datos["dispositivo"]
    bat = datos["bateria"]
    rt = datos["rendimiento_termico"]
    mem = datos["memoria"]
    alm = datos["almacenamiento"]
    est = datos["estabilidad"]

    fecha_rep = fecha_iso
    if not fecha_rep and disp.get("fecha_informe"):
        fecha_rep = str(disp["fecha_informe"])[:10]

    sens_ap = next((s["valor_c"] for s in rt.get("sensores", []) if s["nombre"] == "AP"), None)
    sens_skin = next((s["valor_c"] for s in rt.get("sensores", []) if s["nombre"] == "SKIN"), None)

    apagados_sin_bat = sum(1 for r in est.get("reinicios", []) if r.get("categoria") == "sin_bateria")
    reinicios_anormales = sum(1 for r in est.get("reinicios", []) if r.get("categoria") == "anormal")
    panics_dmesg = sum(
        1
        for d in est.get("dmesg_incidentes", [])
        if "kernel panic" in d.lower() or "unable to handle kernel" in d.lower()
    )
    panics_reset = sum(
        1
        for r in est.get("reinicios", [])
        if r.get("categoria") == "anormal"
        and any(k in (r.get("motivo") or "").lower() for k in ("panic", "kernel", "wdt", "watchdog"))
    )

    top_bat = [
        {
            "paquete": sanitizar_texto(a.get("paquete")),
            "etiqueta": sanitizar_texto(a.get("etiqueta")),
            "mah": round(float(a.get("mah") or 0.0), 1),
            "tiempo_fg": a.get("tiempo_fg"),
            "tiempo_fgs": a.get("tiempo_fgs"),
            "segundos_fgs": round(float(a.get("segundos_fgs") or 0.0), 1),
        }
        for a in bat.get("consumo_apps", [])[:5]
    ]
    top_cpu = [
        {
            "nombre": sanitizar_texto(c.get("nombre")),
            "pct": round(float(c.get("pct") or 0.0), 1),
            "user_pct": round(float(c.get("user_pct") or 0.0), 1),
            "kernel_pct": round(float(c.get("kernel_pct") or 0.0), 1),
        }
        for c in rt.get("top_cpu", [])[:5]
    ]

    anr_total = len(est.get("anrs_logcat", [])) + len(est.get("anr_archivos", []))
    dropbox_crit = est.get("dropbox_crashes", {}).get("system_server", 0) + est.get(
        "dropbox_crashes", {}
    ).get("watchdog", 0)

    return {
        "schema_version": SCHEMA_VERSION,
        "fecha_reporte": fecha_rep,
        "carpeta_reporte": carpeta_nombre or fecha_rep,
        "fecha_informe": disp.get("fecha_informe"),
        "generado_en": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "dispositivo": {
            "fabricante": disp.get("fabricante"),
            "modelo": disp.get("modelo"),
            "nombre_comercial": disp.get("nombre_comercial"),
            "soc": disp.get("soc"),
            "android": disp.get("android"),
            "oneui": disp.get("oneui"),
            "compilacion": disp.get("compilacion"),
            "parche_seguridad": disp.get("parche_seguridad"),
        },
        "puntuacion_general": {
            "puntuacion": diag["puntuacion"],
            "nivel_global": diag["nivel_global"],
            "veredicto": diag["veredicto"],
        },
        "bateria": {
            "nivel_pct": bat.get("nivel"),
            "salud_asoc_pct": bat.get("salud_asoc_pct"),
            "capacidad_estimada_mah": bat.get("capacidad_diseno_mah"),
            "ciclos": bat.get("ciclos"),
            "descarga_mah": bat.get("descarga_mah"),
            "tiempo_en_bateria_seg": bat.get("tiempo_en_bateria_seg"),
            "pantalla_encendida_seg": bat.get("pantalla_encendida_seg"),
            "deep_sleep_pct": bat.get("deep_sleep_pct"),
            "deep_sleep_screen_off_pct": bat.get("deep_sleep_screen_off_pct"),
            "temperatura_actual_c": bat.get("temperatura_c"),
        },
        "top_procesos": {
            "bateria": top_bat,
            "cpu": top_cpu,
        },
        "termico": {
            "estado_termico": rt.get("estado_termico"),
            "temperatura_max_c": rt.get("temperatura_max_c"),
            "temperatura_max_sensor": rt.get("temperatura_max_sensor"),
            "temperatura_ap_c": sens_ap,
            "temperatura_skin_c": sens_skin,
            "eventos_throttling": rt.get("eventos_throttling", 0),
        },
        "memoria_psi": {
            "ram_total_kb": mem.get("total_kb"),
            "ram_disponible_kb": mem.get("disponible_kb"),
            "psi_memory_some_avg60": mem.get("psi", {}).get("some", {}).get("avg60"),
            "psi_memory_full_avg60": mem.get("psi", {}).get("full", {}).get("avg60"),
            "psi_cpu_some_avg60": rt.get("psi_cpu", {}).get("some", {}).get("avg60"),
            "psi_io_full_avg60": rt.get("psi_io", {}).get("full", {}).get("avg60"),
            "eventos_presion_memoria": mem.get("eventos_presion_memoria", 0),
            "lmkd_kills": mem.get("lmkd_kills", 0),
        },
        "almacenamiento": {
            "data_uso_pct": alm.get("data_uso_pct"),
            "data_libre_kb": alm.get("data_libre_kb"),
            "ufs_vida_util": alm.get("ufs_vida_util"),
            "ufs_errores_total": sum(alm.get("ufs_errores", {}).values()) if alm.get("ufs_errores") else 0,
        },
        "estabilidad": {
            "reinicios_total": len(est.get("reinicios", [])),
            "reinicios_anormales": reinicios_anormales,
            "apagados_sin_bateria": apagados_sin_bat,
            "kernel_panics": panics_dmesg + panics_reset,
            "dmesg_incidentes": len(est.get("dmesg_incidentes", [])),
            "dropbox_criticos": dropbox_crit,
            "anr_total": anr_total,
            "crashes_java_total": len(est.get("crashes_java", [])),
            "crashes_nativos_total": len(est.get("crashes_nativos", [])),
            "anr_crashes_por_app": _contar_anr_crashes_por_app(est),
        },
    }


def guardar_metrics_summary(summary, ruta):
    """Guarda el diccionario summary en disco en formato JSON UTF-8 legible."""
    ruta_p = Path(ruta)
    ruta_p.parent.mkdir(parents=True, exist_ok=True)
    ruta_p.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta_p


def cargar_metrics_summary(ruta):
    """Lee un metrics_summary.json válido o retorna None si no existe o está corrupto."""
    ruta_p = Path(ruta)
    if not ruta_p.is_file():
        return None
    try:
        data = json.loads(ruta_p.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, dict) and "puntuacion_general" in data:
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def cargar_historial_summaries(reportes_fecha):
    """Carga todos los metrics_summary.json existentes ordenados cronológicamente."""
    historial = []
    for rep in reportes_fecha:
        summary = cargar_metrics_summary(rep["ruta_summary"])
        if summary is not None:
            historial.append(summary)
    historial.sort(key=lambda s: (s.get("fecha_reporte") or "", s.get("carpeta_reporte") or ""))
    return historial


def _delta_metrica(actual_val, anterior_val, direccion_buena="mayor", tolerancia=0.0, redondeo=1):
    """Calcula delta numérico, símbolo de tendencia (▲/▼/=) y valoración (mejora/regresion/igual)."""
    if actual_val is None or anterior_val is None:
        return {
            "actual": actual_val,
            "anterior": anterior_val,
            "delta": None,
            "simbolo": "=",
            "valoracion": "info",
        }
    diff = round(float(actual_val) - float(anterior_val), redondeo)
    if abs(diff) <= tolerancia:
        return {
            "actual": actual_val,
            "anterior": anterior_val,
            "delta": 0 if redondeo == 0 else 0.0,
            "simbolo": "=",
            "valoracion": "igual",
        }

    simbolo = "▲" if diff > 0 else "▼"
    if direccion_buena == "info":
        valoracion = "info"
    elif direccion_buena == "mayor":
        valoracion = "mejora" if diff > 0 else "regresion"
    else:
        valoracion = "mejora" if diff < 0 else "regresion"

    return {
        "actual": actual_val,
        "anterior": anterior_val,
        "delta": int(diff) if redondeo == 0 else diff,
        "simbolo": simbolo,
        "valoracion": valoracion,
    }


def comparar_reportes(actual, anterior):
    """Compara dos metrics_summary.json y detecta regresiones, mejoras y actualizaciones de sistema."""
    f_act = actual.get("fecha_reporte") or actual.get("carpeta_reporte") or "Actual"
    f_ant = anterior.get("fecha_reporte") or anterior.get("carpeta_reporte") or "Anterior"

    dias_entre = None
    try:
        d_act = datetime.strptime(str(f_act)[:10], "%Y-%m-%d").date()
        d_ant = datetime.strptime(str(f_ant)[:10], "%Y-%m-%d").date()
        dias_entre = (d_act - d_ant).days
    except ValueError:
        pass

    disp_act = actual.get("dispositivo", {})
    disp_ant = anterior.get("dispositivo", {})
    cambios_so = []
    for campo, etiqueta in (
        ("android", "Android"),
        ("oneui", "One UI"),
        ("compilacion", "Compilación"),
        ("parche_seguridad", "Parche de seguridad"),
    ):
        v_act = disp_act.get(campo)
        v_ant = disp_ant.get(campo)
        if v_act and v_ant and v_act != v_ant:
            cambios_so.append(f"{etiqueta}: {v_ant} → {v_act}")

    bat_act = actual.get("bateria", {})
    bat_ant = anterior.get("bateria", {})
    term_act = actual.get("termico", {})
    term_ant = anterior.get("termico", {})
    mem_act = actual.get("memoria_psi", {})
    mem_ant = anterior.get("memoria_psi", {})
    alm_act = actual.get("almacenamiento", {})
    alm_ant = anterior.get("almacenamiento", {})
    est_act = actual.get("estabilidad", {})
    est_ant = anterior.get("estabilidad", {})

    crashes_act = (est_act.get("crashes_java_total") or 0) + (est_act.get("crashes_nativos_total") or 0)
    crashes_ant = (est_ant.get("crashes_java_total") or 0) + (est_ant.get("crashes_nativos_total") or 0)

    metricas = {
        "puntuacion": _delta_metrica(
            actual.get("puntuacion_general", {}).get("puntuacion"),
            anterior.get("puntuacion_general", {}).get("puntuacion"),
            direccion_buena="mayor",
            tolerancia=0,
            redondeo=0,
        ),
        "salud_bateria_pct": _delta_metrica(
            bat_act.get("salud_asoc_pct"),
            bat_ant.get("salud_asoc_pct"),
            direccion_buena="mayor",
            tolerancia=0,
            redondeo=0,
        ),
        "ciclos": _delta_metrica(
            bat_act.get("ciclos"),
            bat_ant.get("ciclos"),
            direccion_buena="info",
            tolerancia=0.1,
            redondeo=1,
        ),
        "deep_sleep_pct": _delta_metrica(
            bat_act.get("deep_sleep_pct"),
            bat_ant.get("deep_sleep_pct"),
            direccion_buena="mayor",
            tolerancia=1.0,
            redondeo=1,
        ),
        "deep_sleep_screen_off_pct": _delta_metrica(
            bat_act.get("deep_sleep_screen_off_pct"),
            bat_ant.get("deep_sleep_screen_off_pct"),
            direccion_buena="mayor",
            tolerancia=1.0,
            redondeo=1,
        ),
        "temperatura_max_c": _delta_metrica(
            term_act.get("temperatura_max_c"),
            term_ant.get("temperatura_max_c"),
            direccion_buena="menor",
            tolerancia=0.5,
            redondeo=1,
        ),
        "temperatura_bat_c": _delta_metrica(
            bat_act.get("temperatura_actual_c"),
            bat_ant.get("temperatura_actual_c"),
            direccion_buena="menor",
            tolerancia=0.5,
            redondeo=1,
        ),
        "eventos_throttling": _delta_metrica(
            term_act.get("eventos_throttling"),
            term_ant.get("eventos_throttling"),
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
        "psi_memory_full_avg60": _delta_metrica(
            mem_act.get("psi_memory_full_avg60"),
            mem_ant.get("psi_memory_full_avg60"),
            direccion_buena="menor",
            tolerancia=0.5,
            redondeo=2,
        ),
        "eventos_presion_memoria": _delta_metrica(
            mem_act.get("eventos_presion_memoria"),
            mem_ant.get("eventos_presion_memoria"),
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
        "data_uso_pct": _delta_metrica(
            alm_act.get("data_uso_pct"),
            alm_ant.get("data_uso_pct"),
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
        "reinicios_anormales": _delta_metrica(
            est_act.get("reinicios_anormales"),
            est_ant.get("reinicios_anormales"),
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
        "kernel_panics": _delta_metrica(
            est_act.get("kernel_panics"),
            est_ant.get("kernel_panics"),
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
        "anr_total": _delta_metrica(
            est_act.get("anr_total"),
            est_ant.get("anr_total"),
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
        "crashes_total": _delta_metrica(
            crashes_act,
            crashes_ant,
            direccion_buena="menor",
            tolerancia=0,
            redondeo=0,
        ),
    }

    # Comparación de apps consumidoras de batería
    mapa_bat_ant = {a["paquete"]: a for a in anterior.get("top_procesos", {}).get("bateria", [])}
    mapa_bat_act = {a["paquete"]: a for a in actual.get("top_procesos", {}).get("bateria", [])}
    apps_bateria_delta = []
    apps_drenaje_nuevo = []

    for pkg, a_act in mapa_bat_act.items():
        a_ant = mapa_bat_ant.get(pkg)
        mah_act = a_act.get("mah") or 0.0
        mah_ant = a_ant.get("mah") if a_ant else 0.0
        delta_mah = round(mah_act - mah_ant, 1)
        fgs_act = a_act.get("segundos_fgs") or 0.0
        fgs_ant = a_ant.get("segundos_fgs") if a_ant else 0.0
        delta_fgs = round(fgs_act - fgs_ant, 1)

        es_sospechosa = False
        if a_ant is None and (mah_act >= 100.0 or fgs_act >= 900.0):
            es_sospechosa = True
        elif a_ant is not None and (
            (delta_mah >= 50.0 and mah_ant > 0 and (delta_mah / mah_ant) >= 0.30)
            or delta_fgs >= 900.0
        ):
            es_sospechosa = True

        item = {
            "paquete": pkg,
            "etiqueta": a_act.get("etiqueta") or nombre_amigable(pkg),
            "mah_actual": mah_act,
            "mah_anterior": mah_ant if a_ant else None,
            "delta_mah": delta_mah,
            "fgs_actual_seg": fgs_act,
            "fgs_anterior_seg": fgs_ant if a_ant else None,
            "delta_fgs_seg": delta_fgs,
            "nueva_en_top": a_ant is None,
            "sospechosa": es_sospechosa,
        }
        apps_bateria_delta.append(item)
        if es_sospechosa:
            apps_drenaje_nuevo.append(item)

    apps_bateria_delta.sort(key=lambda x: x["delta_mah"], reverse=True)

    # Comparación de estabilidad por app (ANR / crashes)
    est_apps_act = est_act.get("anr_crashes_por_app", {})
    est_apps_ant = est_ant.get("anr_crashes_por_app", {})
    todas_apps_est = sorted(set(est_apps_act.keys()) | set(est_apps_ant.keys()))
    apps_estabilidad_delta = []
    for pkg in todas_apps_est:
        c_act = est_apps_act.get(pkg, {"anr": 0, "crashes_java": 0, "crashes_nativos": 0, "total": 0})
        c_ant = est_apps_ant.get(pkg, {"anr": 0, "crashes_java": 0, "crashes_nativos": 0, "total": 0})
        diff_tot = c_act["total"] - c_ant["total"]
        if c_act["total"] > 0 or diff_tot != 0:
            apps_estabilidad_delta.append(
                {
                    "paquete": pkg,
                    "etiqueta": nombre_amigable(pkg),
                    "actual": c_act,
                    "anterior": c_ant,
                    "delta_total": diff_tot,
                }
            )
    apps_estabilidad_delta.sort(key=lambda x: (x["delta_total"], x["actual"]["total"]), reverse=True)

    # Detección estructurada de regresiones y mejoras
    regresiones = []
    mejoras = []
    sufijo_so = " (coincide con actualización de sistema)" if cambios_so else ""

    m_pts = metricas["puntuacion"]
    if m_pts["delta"] is not None:
        if m_pts["delta"] <= -5:
            regresiones.append(
                f"La puntuación global cayó {abs(m_pts['delta'])} pts ({m_pts['anterior']} → {m_pts['actual']}){sufijo_so}."
            )
        elif m_pts["delta"] >= 5:
            mejoras.append(
                f"La puntuación global mejoró +{m_pts['delta']} pts ({m_pts['anterior']} → {m_pts['actual']})."
            )

    m_salud = metricas["salud_bateria_pct"]
    if m_salud["delta"] is not None and m_salud["delta"] <= -2:
        regresiones.append(
            f"La salud física de batería descendió de {m_salud['anterior']}% a {m_salud['actual']}%."
        )

    m_ds = metricas["deep_sleep_pct"]
    t_bat_act = bat_act.get("tiempo_en_bateria_seg") or 0.0
    t_bat_ant = bat_ant.get("tiempo_en_bateria_seg") or 0.0
    if m_ds["delta"] is not None and t_bat_act >= 1800 and t_bat_ant >= 1800:
        if m_ds["delta"] <= -15.0:
            regresiones.append(
                f"El porcentaje de Deep Sleep cayó de {m_ds['anterior']}% a {m_ds['actual']}%{sufijo_so}."
            )
        elif m_ds["delta"] >= 15.0:
            mejoras.append(
                f"El Deep Sleep mejoró de {m_ds['anterior']}% a {m_ds['actual']}%."
            )

    m_tmax = metricas["temperatura_max_c"]
    if m_tmax["delta"] is not None:
        if m_tmax["delta"] >= 4.0 and (m_tmax["actual"] or 0.0) >= 40.0:
            regresiones.append(
                f"La temperatura máxima subió +{m_tmax['delta']:.1f} °C ({m_tmax['anterior']}°C → {m_tmax['actual']}°C){sufijo_so}."
            )
        elif m_tmax["delta"] <= -4.0:
            mejoras.append(
                f"La temperatura máxima bajó {abs(m_tmax['delta']):.1f} °C ({m_tmax['anterior']}°C → {m_tmax['actual']}°C)."
            )

    m_psi = metricas["psi_memory_full_avg60"]
    if m_psi["delta"] is not None and m_psi["delta"] >= 2.0:
        regresiones.append(
            f"La presión de memoria RAM (PSI full) subió de {m_psi['anterior']:.2f}% a {m_psi['actual']:.2f}%."
        )

    m_rei = metricas["reinicios_anormales"]
    if m_rei["delta"] is not None:
        if m_rei["delta"] > 0:
            regresiones.append(
                f"Aumentaron los reinicios anormales ({m_rei['anterior']} → {m_rei['actual']}){sufijo_so}."
            )
        elif m_rei["delta"] < 0:
            mejoras.append(
                f"Se redujeron los reinicios anormales ({m_rei['anterior']} → {m_rei['actual']})."
            )

    m_anr = metricas["anr_total"]
    if m_anr["delta"] is not None and m_anr["delta"] > 0:
        regresiones.append(
            f"Aumentaron los bloqueos ANR ({m_anr['anterior']} → {m_anr['actual']}){sufijo_so}."
        )
    elif m_anr["delta"] is not None and m_anr["delta"] < 0:
        mejoras.append(f"Disminuyeron los bloqueos ANR ({m_anr['anterior']} → {m_anr['actual']}).")

    m_cr = metricas["crashes_total"]
    if m_cr["delta"] is not None and m_cr["delta"] >= 2:
        regresiones.append(
            f"Aumentaron los cierres inesperados ({m_cr['anterior']} → {m_cr['actual']}){sufijo_so}."
        )
    elif m_cr["delta"] is not None and m_cr["delta"] <= -2:
        mejoras.append(f"Disminuyeron los cierres inesperados ({m_cr['anterior']} → {m_cr['actual']}).")

    for app in apps_drenaje_nuevo:
        if app["nueva_en_top"]:
            regresiones.append(
                f"{app['etiqueta']} entró al top de consumo ({app['mah_actual']:.0f} mAh"
                + (f", {int(app['fgs_actual_seg'] // 60)} min en segundo plano" if app["fgs_actual_seg"] >= 300 else "")
                + f"){sufijo_so}."
            )
        else:
            regresiones.append(
                f"{app['etiqueta']} aumentó su consumo en +{app['delta_mah']:.0f} mAh ({app['mah_anterior']:.0f} → {app['mah_actual']:.0f} mAh){sufijo_so}."
            )

    for app_est in apps_estabilidad_delta:
        if app_est["delta_total"] > 0:
            regresiones.append(
                f"{app_est['etiqueta']} registró más fallos ({app_est['anterior']['total']} → {app_est['actual']['total']})."
            )

    return {
        "fecha_actual": f_act,
        "fecha_anterior": f_ant,
        "carpeta_actual": actual.get("carpeta_reporte"),
        "carpeta_anterior": anterior.get("carpeta_reporte"),
        "dias_entre_reportes": dias_entre,
        "actualizacion_sistema": {
            "cambio": bool(cambios_so),
            "detalles": cambios_so,
            "compilacion_anterior": disp_ant.get("compilacion"),
            "compilacion_actual": disp_act.get("compilacion"),
        },
        "metricas": metricas,
        "apps_bateria_delta": apps_bateria_delta,
        "apps_drenaje_nuevo": apps_drenaje_nuevo,
        "apps_estabilidad_delta": apps_estabilidad_delta,
        "regresiones": regresiones,
        "mejoras": mejoras,
    }
