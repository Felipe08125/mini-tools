import html


ETIQUETAS_ESTADO = {
    "optimo": ("✓ Óptimo", "ok"),
    "bueno": ("✓ Bueno", "ok"),
    "bien": ("✓ Bien", "ok"),
    "atencion": ("! Atención", "warn"),
    "critico": ("✕ Crítico", "bad"),
}

TRADUCCION_COMPONENTES = {
    "screen": "Pantalla",
    "cpu": "Procesador (CPU)",
    "mobile_radio": "Red móvil (4G/5G)",
    "audio": "Audio",
    "video": "Video",
    "camera": "Cámara",
    "bluetooth": "Bluetooth",
    "gnss": "GPS / Ubicación",
    "wakelock": "Actividad en segundo plano",
    "sensors": "Sensores",
    "wifi": "Wi-Fi",
    "ambient_display": "Pantalla ambiente",
}

TRADUCCION_CATEGORIAS_ESPACIO = {
    "App Size": "Aplicaciones (código)",
    "App Data Size": "Datos de aplicaciones",
    "App Cache Size": "Caché temporal de apps",
    "Photos Size": "Fotos",
    "Videos Size": "Videos",
    "Audio Size": "Audio y música",
    "Downloads Size": "Descargas",
    "System Size": "Sistema operativo",
    "Other Size": "Otros archivos",
}

TRADUCCION_SENAL = {
    "great": ("Excelente (> -98 dBm)", "ok"),
    "good": ("Buena (-108 a -98 dBm)", "ok"),
    "moderate": ("Media (-118 a -108 dBm)", "warn"),
    "poor": ("Débil (-128 a -118 dBm)", "bad"),
    "very poor": ("Muy débil (< -128 dBm)", "bad"),
}

TRADUCCION_REINICIO = {
    "normal": ("Normal", "ok"),
    "sin_bateria": ("Batería agotada", "warn"),
    "anormal": ("Inesperado / Fallo", "bad"),
    "otro": ("Otro", "neutral"),
}


def _esc(valor):
    """Escapa texto dinámico para prevenir inyección HTML."""
    return html.escape(str(valor), quote=True)


def _fmt_bytes(num_bytes):
    if num_bytes is None:
        return "N/D"
    valor = float(num_bytes)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if abs(valor) < 1024.0 or unidad == "TB":
            if unidad in ("B", "KB"):
                return f"{valor:.0f} {unidad}"
            return f"{valor:.2f} {unidad}"
        valor /= 1024.0
    return f"{num_bytes} B"


def _fmt_kb(kb):
    if kb is None:
        return "N/D"
    return _fmt_bytes(kb * 1024)


def _badge(estado, etiqueta_custom=None):
    texto_def, clase = ETIQUETAS_ESTADO.get(estado, ("Info", "neutral"))
    texto = etiqueta_custom or texto_def
    return f'<span class="badge badge-{clase}">{_esc(texto)}</span>'


def _barra(pct, clase="accent"):
    pct_val = max(0.0, min(100.0, float(pct or 0.0)))
    return (
        f'<div class="bar-track" aria-hidden="true">'
        f'<div class="bar-fill bar-{clase}" style="width:{pct_val:.1f}%"></div>'
        f"</div>"
    )


def _tarjeta_metrica(titulo, valor, subtexto="", badge_html=""):
    sub = f'<div class="metric-sub">{_esc(subtexto)}</div>' if subtexto else ""
    return (
        f'<div class="metric-card">'
        f'<div class="metric-top"><span class="metric-label">{_esc(titulo)}</span>{badge_html}</div>'
        f'<div class="metric-val">{_esc(valor)}</div>'
        f"{sub}"
        f"</div>"
    )


def _tabla(headers, filas_html):
    ths = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    if not filas_html:
        tbody = f'<tr><td colspan="{len(headers)}" class="muted">Sin registros en esta sección.</td></tr>'
    else:
        tbody = "".join(f"<tr>{fila}</tr>" for fila in filas_html)
    return f'<div class="table-wrap"><table><thead><tr>{ths}</tr></thead><tbody>{tbody}</tbody></table></div>'


def _detalle_tecnico(titulo, contenido_html):
    return (
        f'<details class="tech-details">'
        f"<summary>{_esc(titulo)}</summary>"
        f'<div class="tech-body">{contenido_html}</div>'
        f"</details>"
    )


def _render_psi_tabla(psi_dict, nombre):
    if not psi_dict:
        return ""
    filas = []
    for tipo in ("some", "full"):
        if tipo in psi_dict:
            v = psi_dict[tipo]
            filas.append(
                f"<td>{_esc(nombre)} ({_esc(tipo)})</td>"
                f"<td>{v['avg10']:.2f}%</td><td>{v['avg60']:.2f}%</td><td>{v['avg300']:.2f}%</td>"
            )
    return _tabla(["Métrica PSI", "10 seg", "1 min", "5 min"], filas)


def _seccion_bateria(bat, sec_info):
    salud_txt = f"{bat['salud_asoc_pct']}%" if bat["salud_asoc_pct"] is not None else bat["salud_texto"]
    ciclos_txt = f"~{bat['ciclos']:.0f}" if bat["ciclos"] is not None else "N/D"
    temp_txt = f"{bat['temperatura_c']:.1f} °C" if bat["temperatura_c"] is not None else "N/D"
    nivel_txt = f"{bat['nivel']}%" if bat["nivel"] is not None else "N/D"
    prot_txt = (
        f"Activa (máx. {bat['proteccion_limite']}%)"
        if bat["proteccion_modo"] == 1 and bat["proteccion_limite"]
        else "Estándar (100%)"
    )

    cards = "".join(
        [
            _tarjeta_metrica("Nivel actual", nivel_txt, bat["estado_texto"]),
            _tarjeta_metrica("Salud física", salud_txt, f"Primer uso: {bat['primer_uso'] or 'N/D'}"),
            _tarjeta_metrica("Ciclos de carga", ciclos_txt, "Desgaste acumulado"),
            _tarjeta_metrica("Temperatura", temp_txt, bat["fuente"] or "En batería"),
            _tarjeta_metrica(
                "Pantalla encendida",
                bat["pantalla_encendida"] or "N/D",
                f"En batería: {bat['tiempo_en_bateria'] or 'N/D'}",
            ),
            _tarjeta_metrica("Protección de batería", prot_txt, f"Capacidad: {bat['capacidad_diseno_mah'] or 'N/D'} mAh"),
        ]
    )

    # Barras de consumo por componente
    comps_html = ""
    if bat["consumo_componentes"]:
        total_comp = sum(bat["consumo_componentes"].values()) or 1.0
        items = sorted(bat["consumo_componentes"].items(), key=lambda x: x[1], reverse=True)[:8]
        filas_comp = []
        for k, v in items:
            nombre = TRADUCCION_COMPONENTES.get(k, k)
            pct = (v / total_comp) * 100.0
            filas_comp.append(
                f'<div class="bar-row">'
                f'<div class="bar-row-head"><span>{_esc(nombre)}</span><span>{v:.1f} mAh ({pct:.0f}%)</span></div>'
                f"{_barra(pct, 'accent')}"
                f"</div>"
            )
        comps_html = f'<div class="subblock"><h3>¿Qué gastó más batería desde la última carga?</h3>{"".join(filas_comp)}</div>'

    # Detalle técnico
    filas_apps = [
        f"<td><strong>{_esc(a['etiqueta'])}</strong><br><span class=\"code-sub\">{_esc(a['paquete'])}</span></td>"
        f"<td>{a['mah']:.1f} mAh</td>"
        f"<td>{_esc(a['tiempo_fg'] or '—')}</td>"
        f"<td>{_esc(a['tiempo_fgs'] or '—')}</td>"
        for a in bat["consumo_apps"]
    ]
    tabla_apps = _tabla(["Aplicación / Servicio", "Consumo", "Uso activo", "Segundo plano (FGS)"], filas_apps)

    filas_wl = [
        f"<td><strong>{_esc(w['etiqueta'])}</strong><br><span class=\"code-sub\">{_esc(w['nombre'])}</span></td>"
        f"<td>{_esc(w['duracion'])}</td>"
        f"<td>{w['veces']}</td>"
        for w in bat["wakelocks"]
    ]
    tabla_wl = _tabla(["Proceso / Wake lock", "Tiempo retenido", "Activaciones"], filas_wl)

    meta_bat = (
        f"<p class=\"tech-note\">Voltaje: {_esc(bat['voltaje_mv'] or 'N/D')} mV · "
        f"Corriente: {_esc(bat['corriente_ma'] if bat['corriente_ma'] is not None else 'N/D')} mA · "
        f"Descarga registrada: {_esc(bat['descarga_mah'] or 'N/D')} mAh "
        f"(pantalla encendida: {_esc(bat['descarga_pantalla_on_mah'] or 'N/D')} mAh, "
        f"pantalla apagada: {_esc(bat['descarga_pantalla_off_mah'] or 'N/D')} mAh).</p>"
    )
    if bat["refresco"]:
        ref_txt = ", ".join(f"{k}: {v}" for k, v in bat["refresco"].items())
        meta_bat += f"<p class=\"tech-note\">Tasa de refresco usada: {_esc(ref_txt)}.</p>"

    tech = _detalle_tecnico(
        "Ver análisis técnico de batería, consumo por app y wake locks",
        meta_bat
        + "<h4>Top aplicaciones y servicios por consumo (mAh)</h4>"
        + tabla_apps
        + "<h4>Principales wake locks parciales (mantienen el procesador despierto)</h4>"
        + tabla_wl,
    )

    return (
        f'<section class="card" id="bateria">'
        f'<div class="sec-head"><h2>🔋 Batería y consumo</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{cards}</div>'
        f"{comps_html}"
        f"{tech}</section>"
    )


def _seccion_almacenamiento(alm, sec_info):
    uso_pct = alm["data_uso_pct"]
    ufs_vida = (
        f"< {alm['ufs_vida_util'] * 10}% usado (nivel {alm['ufs_vida_util']}/10)"
        if alm["ufs_vida_util"] is not None
        else "N/D"
    )
    ufs_err = sum(alm["ufs_errores"].values()) if alm["ufs_errores"] else 0

    cards = "".join(
        [
            _tarjeta_metrica(
                "Espacio ocupado",
                f"{uso_pct}%" if uso_pct is not None else "N/D",
                f"{_fmt_kb(alm['data_usado_kb'])} de {_fmt_kb(alm['data_total_kb'])}",
            ),
            _tarjeta_metrica("Espacio libre", _fmt_kb(alm["data_libre_kb"]), "Disponible en /data"),
            _tarjeta_metrica(
                "Salud del chip UFS",
                ufs_vida,
                f"{alm['ufs_fabricante'] or ''} {alm['ufs_modelo'] or ''}".strip() or "Memoria flash",
            ),
            _tarjeta_metrica("Errores UFS", str(ufs_err), "Lectura/escritura hardware"),
        ]
    )

    barra_uso = ""
    if uso_pct is not None:
        clase = "bad" if uso_pct >= 90 else ("warn" if uso_pct >= 80 else "ok")
        barra_uso = (
            f'<div class="subblock">'
            f'<div class="bar-row-head"><span>Uso de almacenamiento interno</span><span>{uso_pct}%</span></div>'
            f"{_barra(uso_pct, clase)}</div>"
        )

    filas_cat = [
        f"<td>{_esc(TRADUCCION_CATEGORIAS_ESPACIO.get(k, k))}</td><td>{_esc(_fmt_bytes(v))}</td>"
        for k, v in sorted(alm["categorias_bytes"].items(), key=lambda x: x[1], reverse=True)
    ]
    tabla_cat = _tabla(["Categoría", "Tamaño"], filas_cat)

    filas_apps = [
        f"<td><strong>{_esc(a['etiqueta'])}</strong><br><span class=\"code-sub\">{_esc(a['paquete'])}</span></td>"
        f"<td><strong>{_esc(_fmt_bytes(a['total_bytes']))}</strong></td>"
        f"<td>{_esc(_fmt_bytes(a['app_bytes']))}</td>"
        f"<td>{_esc(_fmt_bytes(a['datos_bytes']))}</td>"
        f"<td>{_esc(_fmt_bytes(a['cache_bytes']))}</td>"
        for a in alm["top_apps"]
    ]
    tabla_apps = _tabla(["Aplicación", "Total", "App", "Datos", "Caché"], filas_apps)

    tech_nota = (
        f"<p class=\"tech-note\">Velocidad escritura reciente: "
        f"{_esc(alm['velocidad_escritura_kbs'] or 'N/D')} KB/s · "
        f"Latencia 512B: {_esc(alm['latencia_ms'] if alm['latencia_ms'] is not None else 'N/D')} ms · "
        f"Cifrado por archivo (FBE): {'Sí' if alm['cifrado_archivos'] else 'N/D'}</p>"
    )
    if alm["ufs_errores"]:
        err_txt = ", ".join(f"{k}={v}" for k, v in alm["ufs_errores"].items())
        tech_nota += f"<p class=\"tech-note\">Contadores de error UFS: {_esc(err_txt)}</p>"

    tech = _detalle_tecnico(
        "Ver desglose técnico de almacenamiento, chip UFS y apps más pesadas",
        tech_nota + "<h4>Distribución por categoría</h4>" + tabla_cat + "<h4>Top 12 aplicaciones por espacio</h4>" + tabla_apps,
    )

    return (
        f'<section class="card" id="almacenamiento">'
        f'<div class="sec-head"><h2>💾 Almacenamiento y apps</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{cards}</div>'
        f"{barra_uso}{tech}</section>"
    )


def _seccion_memoria(mem, sec_info):
    ram_usada_pct = (
        (mem["ram_usada_kb"] / mem["total_kb"]) * 100.0
        if mem["ram_usada_kb"] and mem["total_kb"]
        else 0.0
    )
    zram_pct = (
        (mem["zram_swap_kb"] / mem["zram_total_kb"]) * 100.0
        if mem["zram_swap_kb"] and mem["zram_total_kb"]
        else 0.0
    )
    psi_full60 = mem["psi"].get("full", {}).get("avg60", 0.0)

    cards = "".join(
        [
            _tarjeta_metrica("RAM total", _fmt_kb(mem["total_kb"]), f"Estado Android: {mem['estado_ram'] or 'N/D'}"),
            _tarjeta_metrica("RAM disponible", _fmt_kb(mem["disponible_kb"]), "Lista para nuevas apps"),
            _tarjeta_metrica(
                "ZRAM (RAM comprimida)",
                f"{_fmt_kb(mem['zram_fisica_kb'])} → {_fmt_kb(mem['zram_swap_kb'])}",
                f"De {_fmt_kb(mem['zram_total_kb'])} asignados ({zram_pct:.0f}%)",
            ),
            _tarjeta_metrica("Presión de RAM (PSI)", f"{psi_full60:.2f}%", "Promedio último minuto (full)"),
        ]
    )

    barras = ""
    if ram_usada_pct > 0:
        barras = (
            f'<div class="subblock">'
            f'<div class="bar-row-head"><span>RAM física en uso activo (incluye caché útil)</span><span>{ram_usada_pct:.0f}%</span></div>'
            f"{_barra(ram_usada_pct, 'accent')}</div>"
        )

    filas_proc = [
        f"<td><strong>{_esc(p['etiqueta'])}</strong><br><span class=\"code-sub\">{_esc(p['nombre'])} (PID {p['pid']})</span></td>"
        f"<td>{_esc(_fmt_kb(p['pss_kb']))}</td>"
        f"<td>{_esc(_fmt_kb(p['swap_kb']))}</td>"
        for p in mem["top_procesos"]
    ]
    tabla_proc = _tabla(["Proceso", "Memoria PSS", "En ZRAM/Swap"], filas_proc)

    nota_mem = (
        f"<p class=\"tech-note\">RAM usada (dumpsys): {_esc(_fmt_kb(mem['ram_usada_kb']))} · "
        f"RAM libre Android (con caché): {_esc(_fmt_kb(mem['ram_libre_android_kb']))} · "
        f"RAM perdida/kernel: {_esc(_fmt_kb(mem['ram_perdida_kb']))}</p>"
    )

    tech = _detalle_tecnico(
        "Ver detalle técnico de RAM, presión PSI y top procesos",
        nota_mem + _render_psi_tabla(mem["psi"], "Memoria") + "<h4>Top procesos por memoria PSS</h4>" + tabla_proc,
    )

    return (
        f'<section class="card" id="memoria">'
        f'<div class="sec-head"><h2>🧠 Memoria RAM</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{cards}</div>'
        f"{barras}{tech}</section>"
    )


def _seccion_temperatura(rt, sec_info):
    sensores_cards = []
    etiquetas_sensor = {
        "AP": "Procesador (AP)",
        "SKIN": "Carcasa / Exterior",
        "BAT": "Batería",
        "PA": "Antena / Módem",
        "USB": "Puerto USB",
    }
    for s in rt["sensores"]:
        if s["nombre"] in etiquetas_sensor and s["valor_c"] > 0:
            sensores_cards.append(
                _tarjeta_metrica(
                    etiquetas_sensor[s["nombre"]],
                    f"{s['valor_c']:.1f} °C",
                    f"Estado sensor: {s['estado']}",
                )
            )
    if not sensores_cards:
        sensores_cards.append(_tarjeta_metrica("Estado térmico", rt["estado_termico_texto"]))

    sensores_cards.append(
        _tarjeta_metrica("Carga CPU (1 / 5 / 15m)", rt["cpu_load"] or "N/D", "Promedio de tareas activas")
    )

    filas_cpu = [
        f"<td><strong>{_esc(c['nombre'])}</strong> <span class=\"code-sub\">(PID {c['pid']})</span></td>"
        f"<td>{c['pct']:.1f}%</td>"
        f"<td>{c['user_pct']:.1f}%</td>"
        f"<td>{c['kernel_pct']:.1f}%</td>"
        for c in rt["top_cpu"]
    ]
    tabla_cpu = _tabla(["Proceso", "CPU Total", "Usuario", "Kernel"], filas_cpu)

    psi_html = _render_psi_tabla(rt["psi_cpu"], "CPU") + _render_psi_tabla(rt["psi_io"], "Disco I/O")
    nota_therm = (
        f"<p class=\"tech-note\">Estado térmico HAL: {_esc(rt['estado_termico_texto'])} · "
        f"Ajustes instantáneos LMH registrados en historial térmico: {rt['eventos_lmh']}."
    )
    if rt["umbrales_skin"]:
        nota_therm += f" Umbrales carcasa (SKIN °C): {_esc(', '.join(rt['umbrales_skin']))}."
    nota_therm += "</p>"

    tech = _detalle_tecnico(
        "Ver detalle técnico de CPU, PSI y sensores térmicos",
        nota_therm + psi_html + "<h4>Procesos con mayor uso de CPU en la muestra</h4>" + tabla_cpu,
    )

    return (
        f'<section class="card" id="temperatura">'
        f'<div class="sec-head"><h2>🌡️ Rendimiento y temperatura</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{"".join(sensores_cards)}</div>'
        f"{tech}</section>"
    )


def _seccion_estabilidad(est, sec_info):
    anormales = sum(1 for r in est["reinicios"] if r["categoria"] == "anormal")
    sin_bat = sum(1 for r in est["reinicios"] if r["categoria"] == "sin_bateria")
    total_anr = len(est["anrs_logcat"]) + len(est["anr_archivos"])
    total_crashes = len(est["crashes_java"]) + len(est["crashes_nativos"])

    cards = "".join(
        [
            _tarjeta_metrica("Reinicios por fallo", str(anormales), f"Historial analizado: {len(est['reinicios'])} eventos"),
            _tarjeta_metrica("Apagados sin batería", str(sin_bat), "Descarga completa al 0%"),
            _tarjeta_metrica("Bloqueos de app (ANR)", str(total_anr), "Pantalla congelada"),
            _tarjeta_metrica("Cierres en log reciente", str(total_crashes), "Java y procesos nativos"),
        ]
    )

    # Bloques de crashes
    crashes_html = ""
    if est["crashes_java"] or est["crashes_nativos"]:
        partes = ["<h4>Cierres inesperados detectados en los registros</h4>"]
        for c in est["crashes_java"]:
            traza = "\n".join(c["traza"])
            partes.append(
                f'<div class="crash-box">'
                f'<div><strong>App/Proceso:</strong> {_esc(c.get("etiqueta") or c.get("proceso") or "N/D")} '
                f'<span class="code-sub">({_esc(c.get("fecha") or "")})</span></div>'
                f'<div><strong>Motivo:</strong> {_esc(c.get("excepcion") or "N/D")}</div>'
                + (f'<pre>{_esc(traza)}</pre>' if traza else "")
                + "</div>"
            )
        for c in est["crashes_nativos"]:
            traza = "\n".join(c["traza"])
            partes.append(
                f'<div class="crash-box">'
                f'<div><strong>Proceso nativo:</strong> {_esc(c.get("ejecutable") or c.get("proceso") or "N/D")} '
                f'<span class="code-sub">({_esc(c.get("fecha") or "")}, hilo {_esc(c.get("hilo") or "?")})</span></div>'
                f'<div><strong>Señal:</strong> {_esc(c.get("senal") or "N/D")}</div>'
                + (f'<pre>{_esc(traza)}</pre>' if traza else "")
                + "</div>"
            )
        crashes_html = "".join(partes)

    filas_reinicios = []
    for r in reversed(est["reinicios"][-15:]):
        etiq, cls = TRADUCCION_REINICIO.get(r["categoria"], ("Otro", "neutral"))
        filas_reinicios.append(
            f"<td>{_esc(r['fecha'])}</td>"
            f"<td>{_esc(r['tipo'])}</td>"
            f'<td><span class="badge badge-{cls}">{_esc(etiq)}</span></td>'
            f"<td><code>{_esc(r['motivo'])}</code></td>"
        )
    tabla_reinicios = _tabla(["Fecha y hora", "Evento", "Clasificación", "Motivo técnico"], filas_reinicios)

    filas_tags = [
        f"<td><code>{_esc(tag)}</code></td><td>{cnt}</td>"
        for tag, cnt in est["top_tags_error"]
    ]
    tabla_tags = _tabla(["Etiqueta (Tag) de logcat", "Mensajes E/F"], filas_tags)

    lc = est["logcat_conteo"]
    db = est["dropbox_crashes"]
    nota_est = (
        f"<p class=\"tech-note\">Logcat: {lc['F']} fatales (F), {lc['E']} errores (E), {lc['W']} advertencias (W). "
        f"Se filtraron {est['watchdog_sync_latidos']} latidos normales de Watchdog (!@Sync). "
        f"Dropbox crashes: system_server={db['system_server']}, system_app={db['system_app']}, watchdog={db['watchdog']}. "
        f"Incidentes críticos en kernel (dmesg): {len(est['dmesg_incidentes'])}.</p>"
    )
    if est["dmesg_incidentes"]:
        nota_est += "<pre>" + _esc("\n".join(est["dmesg_incidentes"])) + "</pre>"

    tech = _detalle_tecnico(
        "Ver detalles técnicos de fallos, trazas e historial de reinicios",
        nota_est + crashes_html + "<h4>Últimos apagados y reinicios</h4>" + tabla_reinicios + "<h4>Etiquetas más activas con errores en logcat</h4>" + tabla_tags,
    )

    return (
        f'<section class="card" id="estabilidad">'
        f'<div class="sec-head"><h2>🛡️ Estabilidad y fallos</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{cards}</div>'
        f"{tech}</section>"
    )


def _seccion_conectividad(conn, disp, sec_info):
    wifi_txt = "Encendido" if conn["wifi_activo"] else ("Apagado" if conn["wifi_activo"] is False else "N/D")
    rsrp_txt = f"{conn['rsrp_dbm']} dBm" if conn["rsrp_dbm"] is not None else "N/D"
    radio_txt = f"{conn['radio_activa_pct']:.1f}%" if conn["radio_activa_pct"] is not None else "N/D"

    cards = "".join(
        [
            _tarjeta_metrica(
                "Red móvil actual",
                conn["operador_actual"] or disp["operador"] or "N/D",
                f"Tecnología: {conn['red_actual'] or 'N/D'} · Señal {rsrp_txt}",
            ),
            _tarjeta_metrica(
                "Datos móviles (sesión)",
                f"↓ {conn['datos_movil_rx'] or '0 B'}",
                f"↑ {conn['datos_movil_tx'] or '0 B'} enviados",
            ),
            _tarjeta_metrica("Módem celular activo", radio_txt, f"Tiempo en 5G: {conn['tiempo_5g'] or '0s'}"),
            _tarjeta_metrica(
                "Estado Wi-Fi",
                wifi_txt,
                f"Escaneo en segundo plano: {'Sí' if conn['escaneo_siempre_activo'] else 'No'}",
            ),
        ]
    )

    senal_html = ""
    if conn["senal_distribucion"]:
        barras_s = []
        for clave in ("great", "good", "moderate", "poor", "very poor"):
            if clave in conn["senal_distribucion"]:
                pct = conn["senal_distribucion"][clave]
                nombre_s, cls = TRADUCCION_SENAL[clave]
                barras_s.append(
                    f'<div class="bar-row">'
                    f'<div class="bar-row-head"><span>{_esc(nombre_s)}</span><span>{pct:.1f}%</span></div>'
                    f"{_barra(pct, cls)}</div>"
                )
        senal_html = f'<div class="subblock"><h3>Calidad de señal celular durante la sesión</h3>{"".join(barras_s)}</div>'

    scan_txt = f"{conn['wifi_scanning_pct']:.1f}%" if conn["wifi_scanning_pct"] is not None else "N/D"
    filas_conn = [
        f"<td>Cambios de conectividad</td><td>{_esc(conn['cambios_conectividad'] if conn['cambios_conectividad'] is not None else 'N/D')}</td>",
        f"<td>Tiempo radio celular activa</td><td>{_esc(conn['radio_activa_tiempo'] or 'N/D')} ({_esc(radio_txt)})</td>",
        f"<td>Datos Wi-Fi recibidos / enviados</td><td>{_esc(conn['wifi_datos_rx'] or '0B')} / {_esc(conn['wifi_datos_tx'] or '0B')}</td>",
        f"<td>Estado escaneo Wi-Fi</td><td>{_esc(scan_txt)}</td>",
    ]
    tech = _detalle_tecnico(
        "Ver estadísticas técnicas de red móvil y Wi-Fi",
        _tabla(["Parámetro", "Valor registrado"], filas_conn),
    )

    return (
        f'<section class="card" id="conectividad">'
        f'<div class="sec-head"><h2>📶 Conectividad y red</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{cards}</div>'
        f"{senal_html}{tech}</section>"
    )


def _seccion_seguridad(seg, sec_info):
    parche_sub = (
        f"Hace {seg['antiguedad_parche_dias']} días"
        if seg["antiguedad_parche_dias"] is not None
        else "Fecha del parche"
    )
    knox_txt = "Intacto" if seg["knox_intacto"] else ("Alterado" if seg["knox_intacto"] is False else "N/A")
    cards = "".join(
        [
            _tarjeta_metrica("Parche de seguridad", seg["parche_seguridad"] or "N/D", parche_sub),
            _tarjeta_metrica(
                "Cifrado de datos",
                "Activo" if seg["cifrado"] else "Inactivo",
                "Protección de archivos",
            ),
            _tarjeta_metrica(
                "Arranque verificado",
                "Oficial (green)" if seg["arranque_verificado"] == "green" else (seg["arranque_verificado"] or "N/D"),
                f"Bootloader: {'Bloqueado' if seg['bootloader_bloqueado'] else 'Desbloqueado / N/D'}",
            ),
            _tarjeta_metrica(
                "Garantía Knox / ADB",
                knox_txt,
                f"ADB Wi-Fi: {'Activo' if seg['adb_wifi_activo'] else 'Apagado'}",
            ),
        ]
    )

    filas_seg = [
        f"<td>Arranque verificado (verifiedbootstate)</td><td><code>{_esc(seg['arranque_verificado'] or 'N/D')}</code></td>",
        f"<td>Bootloader bloqueado</td><td>{'Sí' if seg['bootloader_bloqueado'] else 'No / N/D'}</td>",
        f"<td>Knox warranty bit</td><td>{'0 (Intacto)' if seg['knox_intacto'] else ('Alterado' if seg['knox_intacto'] is False else 'N/D')}</td>",
        f"<td>Cifrado de almacenamiento</td><td>{'Sí (encrypted)' if seg['cifrado'] else 'No'}</td>",
        f"<td>Modo debuggable del sistema</td><td>{'Sí' if seg['debuggable'] else 'No (producción)'}</td>",
        f"<td>ADB conectado / ADB por Wi-Fi</td><td>{'Sí' if seg['adb_conectado'] else 'No'} / {'Sí' if seg['adb_wifi_activo'] else 'No'}</td>",
    ]
    tech = _detalle_tecnico(
        "Ver propiedades técnicas de seguridad e integridad",
        _tabla(["Propiedad", "Estado"], filas_seg),
    )

    return (
        f'<section class="card" id="seguridad">'
        f'<div class="sec-head"><h2>🔒 Seguridad e integridad</h2>{_badge(sec_info["estado"])}</div>'
        f'<p class="sec-summary">{_esc(sec_info["resumen"])}</p>'
        f'<div class="metrics-grid">{cards}</div>'
        f"{tech}</section>"
    )


def generar_html(datos, diag):
    """Genera un informe HTML autocontenido, responsive y sin dependencias externas."""
    disp = datos["dispositivo"]
    bat = datos["bateria"]
    alm = datos["almacenamiento"]
    mem = datos["memoria"]
    rt = datos["rendimiento_termico"]
    est = datos["estabilidad"]
    seg = datos["seguridad"]
    secs = diag["secciones"]

    modelo = disp["nombre_comercial"] or disp["modelo"] or "Dispositivo Android"
    sistema = f"Android {disp['android'] or '?'}"
    if disp["oneui"]:
        sistema += f" · One UI {disp['oneui']}"
    arranque_seg = (
        f"{disp['tiempo_arranque_ms'] / 1000.0:.1f} s"
        if disp["tiempo_arranque_ms"] is not None
        else "N/D"
    )

    score_cls = {"bien": "ok", "atencion": "warn", "critico": "bad"}[diag["nivel_global"]]

    # 6 tarjetas ejecutivas
    ap_temp = next((s["valor_c"] for s in rt["sensores"] if s["nombre"] == "AP"), None)
    anormales = sum(1 for r in est["reinicios"] if r["categoria"] == "anormal")
    resumen_exec = "".join(
        [
            _tarjeta_metrica(
                "Batería",
                f"{bat['salud_asoc_pct']}%" if bat["salud_asoc_pct"] is not None else f"{bat['nivel'] or '?'}%",
                f"Nivel {bat['nivel'] or '?'}% · {bat['temperatura_c'] or '?'} °C",
                _badge(secs["bateria"]["estado"]),
            ),
            _tarjeta_metrica(
                "Almacenamiento",
                f"{alm['data_uso_pct']}%" if alm["data_uso_pct"] is not None else "N/D",
                f"{_fmt_kb(alm['data_libre_kb'])} libres",
                _badge(secs["almacenamiento"]["estado"]),
            ),
            _tarjeta_metrica(
                "Memoria RAM",
                _fmt_kb(mem["total_kb"]),
                f"{_fmt_kb(mem['disponible_kb'])} disponibles",
                _badge(secs["memoria"]["estado"]),
            ),
            _tarjeta_metrica(
                "Temperatura",
                f"{ap_temp:.1f} °C" if ap_temp is not None else rt["estado_termico_texto"],
                rt["estado_termico_texto"],
                _badge(secs["temperatura"]["estado"]),
            ),
            _tarjeta_metrica(
                "Estabilidad",
                f"{anormales} fallos graves",
                f"{len(est['crashes_java']) + len(est['crashes_nativos'])} cierres puntuales",
                _badge(secs["estabilidad"]["estado"]),
            ),
            _tarjeta_metrica(
                "Seguridad",
                "Intacto" if seg["arranque_verificado"] == "green" and seg["cifrado"] else "Revisar",
                f"Parche {seg['parche_seguridad'] or 'N/D'}",
                _badge(secs["seguridad"]["estado"]),
            ),
        ]
    )

    # Hallazgos separados en revisar vs bien
    revisar = [h for h in diag["hallazgos"] if h["severidad"] in ("critico", "atencion")]
    bien = [h for h in diag["hallazgos"] if h["severidad"] == "bien"]

    def render_hallazgo(h):
        b = _badge(h["severidad"], "Importante" if h["severidad"] == "critico" else ("Sugerencia" if h["severidad"] == "atencion" else "Bien"))
        det = f'<div class="finding-tech">Dato técnico: <code>{_esc(h["detalle_tecnico"])}</code></div>' if h["detalle_tecnico"] else ""
        return (
            f'<div class="finding finding-{h["severidad"]}">'
            f'<div class="finding-head">{b}<span class="finding-cat">{_esc(h["categoria"])}</span><h3>{_esc(h["titulo"])}</h3></div>'
            f'<p>{_esc(h["explicacion"])}</p>'
            f'<p class="finding-rec"><strong>Qué hacer:</strong> {_esc(h["recomendacion"])}</p>'
            f"{det}"
            f"</div>"
        )

    bloque_revisar = (
        "".join(render_hallazgo(h) for h in revisar)
        if revisar
        else '<p class="muted">No hay alertas ni observaciones pendientes.</p>'
    )
    bloque_bien = "".join(render_hallazgo(h) for h in bien)

    secciones_html = "".join(
        [
            _seccion_bateria(bat, secs["bateria"]),
            _seccion_almacenamiento(alm, secs["almacenamiento"]),
            _seccion_memoria(mem, secs["memoria"]),
            _seccion_temperatura(rt, secs["temperatura"]),
            _seccion_estabilidad(est, secs["estabilidad"]),
            _seccion_conectividad(datos["conectividad"], disp, secs["conectividad"]),
            _seccion_seguridad(seg, secs["seguridad"]),
        ]
    )

    css = """
    :root {
      --bg: #f4f6f9;
      --surface: #ffffff;
      --text: #17202a;
      --muted: #566573;
      --border: #dfe6ee;
      --accent: #2563eb;
      --ok-bg: #e7f6ec; --ok-fg: #146c38;
      --warn-bg: #fff5db; --warn-fg: #8a5300;
      --bad-bg: #fde8e8; --bad-fg: #a61b1b;
      --neutral-bg: #eef2f6; --neutral-fg: #3b4856;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 24px 16px 48px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Ubuntu, Cantarell, sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.55;
    }
    .container { max-width: 1040px; margin: 0 auto; display: grid; gap: 20px; }
    .hero {
      background: linear-gradient(135deg, #0f172a, #1e3a8a);
      color: #fff; border-radius: 16px; padding: 24px 28px;
      display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 20px;
    }
    .hero h1 { margin: 0 0 6px; font-size: 1.65rem; }
    .hero-meta { color: #cbd5e1; font-size: 0.94rem; }
    .score-box {
      background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.22);
      border-radius: 14px; padding: 14px 20px; text-align: center; min-width: 190px;
    }
    .score-num { font-size: 2.1rem; font-weight: 800; line-height: 1.1; }
    .score-verdict { font-weight: 700; margin-top: 4px; font-size: 0.98rem; }
    .score-ok { color: #86efac; } .score-warn { color: #fde047; } .score-bad { color: #fca5a5; }
    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 14px; padding: 22px 24px; box-shadow: 0 2px 6px rgba(15,23,42,0.04);
    }
    .sec-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
    h2 { margin: 0; font-size: 1.25rem; }
    h3 { margin: 0; font-size: 1.02rem; }
    h4 { margin: 16px 0 8px; font-size: 0.95rem; color: var(--muted); }
    .sec-summary { margin: 0 0 16px; color: #2c3e50; font-size: 1rem; }
    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 12px; }
    .metric-card { background: #f8fafc; border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
    .metric-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 6px; }
    .metric-label { font-size: 0.82rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em; }
    .metric-val { font-size: 1.18rem; font-weight: 700; }
    .metric-sub { font-size: 0.83rem; color: var(--muted); margin-top: 3px; }
    .badge { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; white-space: nowrap; }
    .badge-ok { background: var(--ok-bg); color: var(--ok-fg); }
    .badge-warn { background: var(--warn-bg); color: var(--warn-fg); }
    .badge-bad { background: var(--bad-bg); color: var(--bad-fg); }
    .badge-neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
    .subblock { margin-top: 16px; }
    .bar-row { margin-top: 9px; }
    .bar-row-head { display: flex; justify-content: space-between; font-size: 0.88rem; margin-bottom: 4px; }
    .bar-track { height: 9px; background: #e8edf3; border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; }
    .bar-accent { background: var(--accent); }
    .bar-ok { background: #16a34a; }
    .bar-warn { background: #d97706; }
    .bar-bad { background: #dc2626; }
    .findings-grid { display: grid; gap: 12px; margin-top: 10px; }
    .finding { border-radius: 10px; padding: 14px 16px; border: 1px solid var(--border); background: #fbfcfe; }
    .finding-critico { border-left: 4px solid #dc2626; background: #fff9f9; }
    .finding-atencion { border-left: 4px solid #d97706; background: #fffdf7; }
    .finding-bien { border-left: 4px solid #16a34a; background: #f8fcf9; }
    .finding-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
    .finding-cat { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
    .finding p { margin: 4px 0; font-size: 0.94rem; }
    .finding-rec { color: #1e293b; }
    .finding-tech { margin-top: 6px; font-size: 0.82rem; color: var(--muted); }
    .tech-details { margin-top: 16px; border-top: 1px dashed var(--border); padding-top: 12px; }
    .tech-details summary { cursor: pointer; font-weight: 600; color: var(--accent); font-size: 0.93rem; user-select: none; }
    .tech-body { margin-top: 12px; }
    .tech-note { font-size: 0.88rem; color: var(--muted); margin: 6px 0; }
    .table-wrap { overflow-x: auto; margin-top: 6px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { background: #f8fafc; font-weight: 700; color: #334155; }
    .code-sub, code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.8rem; color: #475569; }
    pre {
      background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px;
      overflow-x: auto; font-size: 0.8rem; line-height: 1.4;
    }
    .crash-box { border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 10px; background: #f8fafc; }
    .muted { color: var(--muted); font-size: 0.9rem; }
    .nav-pills { display: flex; flex-wrap: wrap; gap: 8px; }
    .nav-pills a {
      text-decoration: none; color: #1e3a8a; background: #e8f0fe;
      padding: 6px 12px; border-radius: 999px; font-size: 0.86rem; font-weight: 600;
    }
    footer { text-align: center; color: var(--muted); font-size: 0.84rem; margin-top: 8px; }
    """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Diagnóstico del teléfono — {_esc(modelo)}</title>
  <style>{css}</style>
</head>
<body>
  <main class="container">
    <header class="hero">
      <div>
        <h1>Diagnóstico del teléfono: {_esc(disp['fabricante'] or '')} {_esc(modelo)}</h1>
        <div class="hero-meta">
          {_esc(sistema)} · Compilación {_esc(disp['compilacion'] or 'N/D')}<br>
          Informe generado: {_esc(disp['fecha_informe'] or 'N/D')} ·
          Encendido hace: {_esc(disp['uptime_texto'] or 'N/D')} ·
          Arranque: {_esc(arranque_seg)} ·
          Apps/paquetes: {_esc(disp['total_paquetes'])}
        </div>
      </div>
      <div class="score-box">
        <div class="score-num score-{score_cls}">{diag['puntuacion']}/100</div>
        <div class="score-verdict score-{score_cls}">{_esc(diag['veredicto'])}</div>
        <div class="hero-meta" style="margin-top:4px;">{_esc(diag['frase_global'])}</div>
      </div>
    </header>

    <nav class="nav-pills" aria-label="Secciones del informe">
      <a href="#resumen">Resumen</a>
      <a href="#hallazgos">Qué revisar</a>
      <a href="#bateria">Batería</a>
      <a href="#almacenamiento">Almacenamiento</a>
      <a href="#memoria">Memoria RAM</a>
      <a href="#temperatura">Temperatura</a>
      <a href="#estabilidad">Estabilidad</a>
      <a href="#conectividad">Conectividad</a>
      <a href="#seguridad">Seguridad</a>
    </nav>

    <section class="card" id="resumen">
      <div class="sec-head"><h2>📋 ¿Cómo está tu teléfono?</h2></div>
      <div class="metrics-grid">{resumen_exec}</div>
    </section>

    <section class="card" id="hallazgos">
      <div class="sec-head"><h2>🔍 Hallazgos y recomendaciones</h2></div>
      <h3>Qué conviene revisar</h3>
      <div class="findings-grid">{bloque_revisar}</div>
      <h3 style="margin-top:18px;">Lo que está funcionando bien</h3>
      <div class="findings-grid">{bloque_bien}</div>
    </section>

    {secciones_html}

    <footer>
      Análisis generado 100% en tu equipo local sin subir archivos a internet.
      Se omitieron identificadores personales sensibles (número de serie, redes Wi-Fi guardadas, IMEI y cuentas).
    </footer>
  </main>
</body>
</html>
"""
