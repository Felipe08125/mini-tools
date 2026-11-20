import html
import json


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


def _json_para_script(obj):
    """Serializa JSON de forma segura para incrustar dentro de un bloque <script>."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


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


def _trend_badge(delta_info, sufijo="", entero=False):
    if not delta_info or delta_info.get("delta") is None:
        return '<span class="trend-badge trend-info">= N/D</span>'
    simbolo = delta_info.get("simbolo", "=")
    val = delta_info.get("valoracion", "info")
    delta = delta_info["delta"]
    clase = {
        "mejora": "trend-good",
        "regresion": "trend-bad",
        "igual": "trend-eq",
    }.get(val, "trend-info")
    if simbolo == "=":
        txt = "= Sin cambio"
    else:
        signo = "+" if delta > 0 else ""
        num_txt = f"{signo}{int(delta)}" if entero else f"{signo}{delta:.1f}"
        txt = f"{simbolo} {num_txt}{sufijo}"
    return f'<span class="trend-badge {clase}">{_esc(txt)}</span>'


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


def _svg_tendencia_historica(historial):
    """Genera un gráfico SVG inline puro con la evolución histórica de puntuación y temperatura."""
    if not historial or len(historial) < 2:
        return ""

    w, h = 760, 210
    pad_l, pad_r, pad_t, pad_b = 48, 48, 26, 38
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    n = len(historial)

    def x_pos(idx):
        if n == 1:
            return pad_l + plot_w / 2.0
        return pad_l + (idx / float(n - 1)) * plot_w

    pts_score = []
    pts_temp = []
    etiquetas_x = []
    grid_lines = []

    for val in (0, 25, 50, 75, 100):
        y = pad_t + plot_h - (val / 100.0) * plot_h
        grid_lines.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" stroke="#e2e8f0" stroke-dasharray="3,3"/>'
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{val}</text>'
        )

    for temp_tick in (20, 40, 60, 80):
        y_t = pad_t + plot_h - ((temp_tick - 20.0) / 60.0) * plot_h
        grid_lines.append(
            f'<text x="{w - pad_r + 8}" y="{y_t + 4:.1f}" text-anchor="start" font-size="10" fill="#ea580c">{temp_tick}°C</text>'
        )

    circulos = []
    for idx, item in enumerate(historial):
        x = x_pos(idx)
        fecha_lbl = (item.get("fecha_reporte") or item.get("carpeta_reporte") or "?")[-5:]
        etiquetas_x.append(
            f'<text x="{x:.1f}" y="{h - 12}" text-anchor="middle" font-size="10" fill="#475569">{_esc(fecha_lbl)}</text>'
        )

        pts_val = item.get("puntuacion_general", {}).get("puntuacion")
        if pts_val is not None:
            y_s = pad_t + plot_h - (max(0.0, min(100.0, float(pts_val))) / 100.0) * plot_h
            pts_score.append(f"{x:.1f},{y_s:.1f}")
            circulos.append(
                f'<circle cx="{x:.1f}" cy="{y_s:.1f}" r="4.5" fill="#2563eb" stroke="#fff" stroke-width="1.5">'
                f"<title>{_esc(item.get('fecha_reporte'))}: {pts_val}/100</title></circle>"
                f'<text x="{x:.1f}" y="{y_s - 8:.1f}" text-anchor="middle" font-size="10" font-weight="700" fill="#1d4ed8">{pts_val}</text>'
            )

        tmax = item.get("termico", {}).get("temperatura_max_c")
        if tmax is not None:
            t_clamp = max(20.0, min(80.0, float(tmax)))
            y_t = pad_t + plot_h - ((t_clamp - 20.0) / 60.0) * plot_h
            pts_temp.append(f"{x:.1f},{y_t:.1f}")
            circulos.append(
                f'<circle cx="{x:.1f}" cy="{y_t:.1f}" r="4" fill="#ea580c" stroke="#fff" stroke-width="1.5">'
                f"<title>{_esc(item.get('fecha_reporte'))}: {tmax:.1f} °C</title></circle>"
                f'<text x="{x:.1f}" y="{y_t + 14:.1f}" text-anchor="middle" font-size="10" font-weight="600" fill="#c2410c">{tmax:.1f}°</text>'
            )

    poly_score = (
        f'<polyline fill="none" stroke="#2563eb" stroke-width="2.5" points="{" ".join(pts_score)}"/>'
        if len(pts_score) >= 2
        else ""
    )
    poly_temp = (
        f'<polyline fill="none" stroke="#ea580c" stroke-width="2" stroke-dasharray="5,3" points="{" ".join(pts_temp)}"/>'
        if len(pts_temp) >= 2
        else ""
    )

    return (
        f'<div class="subblock">'
        f'<div class="tl-legend">'
        f'<span><i class="dot" style="background:#2563eb"></i> Puntuación (/100)</span>'
        f'<span><i class="dot" style="background:#ea580c"></i> Temperatura máx. (°C)</span>'
        f"</div>"
        f'<div class="svg-scroll">'
        f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Tendencia histórica de puntuación y temperatura">'
        f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" rx="4"/>'
        f'{"".join(grid_lines)}{poly_score}{poly_temp}{"".join(circulos)}{"".join(etiquetas_x)}'
        f"</svg></div></div>"
    )


def _seccion_evolucion(diff, historial=None):
    if not diff:
        return ""

    m = diff["metricas"]
    so = diff["actualizacion_sistema"]
    banner_so = ""
    if so["cambio"]:
        detalles = " · ".join(so["detalles"])
        banner_so = (
            f'<div class="so-banner">'
            f"<strong>🔄 Actualización / cambio de sistema detectado:</strong> {_esc(detalles)}"
            f"</div>"
        )

    def fmt_val(v, suf=""):
        return "N/D" if v is None else f"{v}{suf}"

    cards = "".join(
        [
            _tarjeta_metrica(
                "Puntuación",
                f"{m['puntuacion']['actual']}/100",
                f"Antes: {m['puntuacion']['anterior']}/100",
                _trend_badge(m["puntuacion"], " pts", entero=True),
            ),
            _tarjeta_metrica(
                "Salud batería",
                fmt_val(m["salud_bateria_pct"]["actual"], "%"),
                f"Antes: {fmt_val(m['salud_bateria_pct']['anterior'], '%')}",
                _trend_badge(m["salud_bateria_pct"], "%", entero=True),
            ),
            _tarjeta_metrica(
                "Deep Sleep",
                fmt_val(m["deep_sleep_pct"]["actual"], "%"),
                f"Antes: {fmt_val(m['deep_sleep_pct']['anterior'], '%')}",
                _trend_badge(m["deep_sleep_pct"], "%"),
            ),
            _tarjeta_metrica(
                "Temp. máxima",
                fmt_val(m["temperatura_max_c"]["actual"], " °C"),
                f"Antes: {fmt_val(m['temperatura_max_c']['anterior'], ' °C')}",
                _trend_badge(m["temperatura_max_c"], " °C"),
            ),
            _tarjeta_metrica(
                "Presión RAM (PSI)",
                fmt_val(m["psi_memory_full_avg60"]["actual"], "%"),
                f"Antes: {fmt_val(m['psi_memory_full_avg60']['anterior'], '%')}",
                _trend_badge(m["psi_memory_full_avg60"], "%"),
            ),
            _tarjeta_metrica(
                "Cierres / ANR",
                f"{(m['crashes_total']['actual'] or 0) + (m['anr_total']['actual'] or 0)}",
                f"Antes: {(m['crashes_total']['anterior'] or 0) + (m['anr_total']['anterior'] or 0)} "
                f"(Reinicios anormales: {m['reinicios_anormales']['actual']})",
                _trend_badge(m["crashes_total"], " crashes", entero=True),
            ),
        ]
    )

    reg_html = ""
    if diff["regresiones"]:
        lis = "".join(f"<li>{_esc(r)}</li>" for r in diff["regresiones"])
        reg_html = f'<div class="diff-alert diff-alert-bad"><strong>⚠ Regresiones o aumentos detectados</strong><ul>{lis}</ul></div>'

    mej_html = ""
    if diff["mejoras"]:
        lis = "".join(f"<li>{_esc(x)}</li>" for x in diff["mejoras"])
        mej_html = f'<div class="diff-alert diff-alert-good"><strong>✓ Mejoras observadas</strong><ul>{lis}</ul></div>'

    if not reg_html and not mej_html:
        mej_html = '<p class="muted" style="margin-top:10px;">Sin regresiones significativas respecto al reporte previo.</p>'

    filas_apps_bat = []
    for a in diff["apps_bateria_delta"][:8]:
        ant_txt = f"{a['mah_anterior']:.1f} mAh" if a["mah_anterior"] is not None else "No en top 5"
        d_sign = "+" if a["delta_mah"] > 0 else ""
        cls_app = ' class="bad-txt"' if a["sospechosa"] else ""
        fgs_min = int(a["fgs_actual_seg"] // 60)
        filas_apps_bat.append(
            f"<td><strong>{_esc(a['etiqueta'])}</strong><br><span class=\"code-sub\">{_esc(a['paquete'])}</span></td>"
            f"<td>{a['mah_actual']:.1f} mAh</td>"
            f"<td>{_esc(ant_txt)}</td>"
            f"<td{cls_app}>{d_sign}{a['delta_mah']:.1f} mAh</td>"
            f"<td>{fgs_min} min</td>"
        )
    tabla_bat_diff = _tabla(
        ["Aplicación", "Consumo actual", "Consumo previo", "Variación", "2.º plano (FGS)"],
        filas_apps_bat,
    )

    filas_apps_est = []
    for ae in diff["apps_estabilidad_delta"][:8]:
        d = ae["delta_total"]
        d_txt = f"+{d}" if d > 0 else str(d)
        filas_apps_est.append(
            f"<td><strong>{_esc(ae['etiqueta'])}</strong></td>"
            f"<td>{ae['actual']['anr']} ANR / {ae['actual']['crashes_java'] + ae['actual']['crashes_nativos']} crashes</td>"
            f"<td>{ae['anterior']['anr']} ANR / {ae['anterior']['crashes_java'] + ae['anterior']['crashes_nativos']} crashes</td>"
            f"<td>{_esc(d_txt)}</td>"
        )
    tabla_est_diff = _tabla(["Aplicación / Proceso", "Actual", "Anterior", "Diferencia"], filas_apps_est)

    svg_hist = _svg_tendencia_historica(historial)
    tech = _detalle_tecnico(
        "Ver comparativa detallada por aplicación (batería y estabilidad)",
        "<h4>Variación de consumo de batería (top apps)</h4>"
        + tabla_bat_diff
        + "<h4>Variación de ANR y crashes por app</h4>"
        + tabla_est_diff,
    )

    dias_txt = (
        f" ({diff['dias_entre_reportes']} días de diferencia)"
        if diff.get("dias_entre_reportes") is not None
        else ""
    )

    return (
        f'<section class="card" id="evolucion">'
        f'<div class="sec-head"><h2>📈 Evolución vs. reporte anterior</h2>'
        f'<span class="badge badge-neutral">{_esc(diff["fecha_anterior"])} → {_esc(diff["fecha_actual"])}</span></div>'
        f'<p class="sec-summary">Comparativa histórica contra el reporte del {_esc(diff["fecha_anterior"])}{_esc(dias_txt)}.</p>'
        f"{banner_so}"
        f'<div class="metrics-grid">{cards}</div>'
        f"{reg_html}{mej_html}"
        f"{svg_hist}"
        f"{tech}</section>"
    )


def _seccion_linea_tiempo(linea_tiempo):
    """Genera la sección interactiva SVG/JS de correlación temporal unificada."""
    lt = linea_tiempo or {}
    series = lt.get("series") or []
    eventos = lt.get("eventos") or []
    correlaciones = lt.get("correlaciones") or []

    corr_html = ""
    if correlaciones:
        items_corr = "".join(
            f'<li><span class="badge badge-{"bad" if c["severidad"] == "critico" else "warn"}">'
            f'{_esc(c["ts_iso"][11:])}</span> {_esc(c["resumen"])}</li>'
            for c in correlaciones
        )
        corr_html = (
            f'<div class="diff-alert diff-alert-warn">'
            f"<strong>⚡ Correlaciones temporales detectadas (±5 min)</strong>"
            f"<ul>{items_corr}</ul></div>"
        )

    if not series and not eventos:
        return (
            f'<section class="card" id="linea-tiempo">'
            f'<div class="sec-head"><h2>⏱️ Correlación temporal interactiva</h2></div>'
            f'<p class="muted">Este informe no contiene suficientes marcas temporales en Battery History, logs o reinicios para construir la línea de tiempo.</p>'
            f"</section>"
        )

    # SVG fallback estático mínimo por si se visualiza sin JavaScript
    fallback_svg = (
        '<svg id="tl-svg" viewBox="0 0 920 340" class="chart-svg tl-svg" role="img" '
        'aria-label="Línea de tiempo unificada de temperatura, voltaje y eventos">'
        '<rect x="52" y="24" width="810" height="210" fill="#f8fafc" rx="6" stroke="#dfe6ee"/>'
        '<text x="457" y="130" text-anchor="middle" font-size="13" fill="#64748b">'
        f"Serie cargada: {len(series)} muestras y {len(eventos)} eventos registrados."
        "</text>"
        "</svg>"
    )

    lt_payload = {
        "series": series,
        "eventos": eventos,
        "ventana_inicio_epoch": lt.get("ventana_inicio_epoch"),
        "ventana_fin_epoch": lt.get("ventana_fin_epoch"),
        "total_inicio_epoch": lt.get("total_inicio_epoch"),
        "total_fin_epoch": lt.get("total_fin_epoch"),
    }
    json_embebido = _json_para_script(lt_payload)

    script_js = """
(function() {
  var dataEl = document.getElementById("tl-data");
  var svg = document.getElementById("tl-svg");
  if (!dataEl || !svg) return;
  var data;
  try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }

  var sevFilter = "all";
  var catFilter = "all";
  var scopeFilter = "ventana";
  var seriesEnabled = { ap_c: true, bat_c: true, skin_c: true, volt_mv: true, nivel: false };

  var sevButtons = document.querySelectorAll("[data-tl-sev]");
  var catButtons = document.querySelectorAll("[data-tl-cat]");
  var scopeButtons = document.querySelectorAll("[data-tl-scope]");
  var seriesChecks = document.querySelectorAll("[data-tl-series]");
  var tbody = document.getElementById("tl-events-body");
  var hoverBox = document.getElementById("tl-hover-info");
  var countBadge = document.getElementById("tl-count-badge");

  function fmtTs(epochSec, spanSec) {
    var d = new Date(epochSec * 1000);
    var mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    var dd = String(d.getUTCDate()).padStart(2, "0");
    var hh = String(d.getUTCHours()).padStart(2, "0");
    var mi = String(d.getUTCMinutes()).padStart(2, "0");
    if (spanSec > 172800) return mm + "-" + dd + " " + hh + ":" + mi;
    return hh + ":" + mi;
  }

  function svgEl(tag, attrs, text) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) {
        el.setAttribute(k, String(attrs[k]));
      }
    }
    if (text !== undefined) el.textContent = String(text);
    return el;
  }

  function getFilteredEvents() {
    return (data.eventos || []).filter(function(ev) {
      if (scopeFilter === "ventana" && !ev.en_ventana) return false;
      if (sevFilter !== "all" && ev.severidad !== sevFilter) return false;
      if (catFilter !== "all" && ev.categoria !== catFilter) return false;
      return true;
    });
  }

  function sevColor(sev) {
    if (sev === "critico") return "#dc2626";
    if (sev === "atencion") return "#d97706";
    return "#2563eb";
  }

  function catLabel(cat) {
    var map = {
      termico: "Térmico",
      bateria: "Batería",
      estabilidad: "Estabilidad",
      memoria: "Memoria",
      reinicio: "Reinicio"
    };
    return map[cat] || cat;
  }

  function renderTable(events) {
    if (!tbody) return;
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    if (countBadge) countBadge.textContent = events.length + " eventos";
    if (!events.length) {
      var trEmpty = document.createElement("tr");
      var tdEmpty = document.createElement("td");
      tdEmpty.colSpan = 4;
      tdEmpty.className = "muted";
      tdEmpty.textContent = "No hay eventos que coincidan con los filtros activos.";
      trEmpty.appendChild(tdEmpty);
      tbody.appendChild(trEmpty);
      return;
    }
    var slice = events.slice(-40).reverse();
    slice.forEach(function(ev) {
      var tr = document.createElement("tr");
      var tdTs = document.createElement("td");
      tdTs.textContent = ev.ts_iso || "";
      var tdSev = document.createElement("td");
      var spanB = document.createElement("span");
      spanB.className = "badge " + (ev.severidad === "critico" ? "badge-bad" : (ev.severidad === "atencion" ? "badge-warn" : "badge-neutral"));
      spanB.textContent = ev.severidad;
      tdSev.appendChild(spanB);
      var tdCat = document.createElement("td");
      tdCat.textContent = catLabel(ev.categoria);
      var tdTit = document.createElement("td");
      var strong = document.createElement("strong");
      strong.textContent = ev.titulo || "";
      tdTit.appendChild(strong);
      if (ev.detalle) {
        tdTit.appendChild(document.createElement("br"));
        var sub = document.createElement("span");
        sub.className = "code-sub";
        sub.textContent = ev.detalle;
        tdTit.appendChild(sub);
      }
      tr.appendChild(tdTs);
      tr.appendChild(tdSev);
      tr.appendChild(tdCat);
      tr.appendChild(tdTit);
      tbody.appendChild(tr);
    });
  }

  function render() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var series = data.series || [];
    var events = getFilteredEvents();
    renderTable(events);

    var W = 920, H = 340;
    var padL = 52, padR = 56, padT = 22, chartH = 205;
    var evY = padT + chartH + 42;
    var plotW = W - padL - padR;

    var minEp = scopeFilter === "ventana" ? data.ventana_inicio_epoch : data.total_inicio_epoch;
    var maxEp = scopeFilter === "ventana" ? data.ventana_fin_epoch : data.total_fin_epoch;
    if (minEp == null || maxEp == null) {
      var allEp = series.map(function(p) { return p.epoch; }).concat(events.map(function(e) { return e.epoch; }));
      if (!allEp.length) return;
      minEp = Math.min.apply(null, allEp);
      maxEp = Math.max.apply(null, allEp);
    }
    if (maxEp - minEp < 60) minEp = maxEp - 300;
    var span = maxEp - minEp;

    function xOf(ep) {
      return padL + ((ep - minEp) / span) * plotW;
    }

    // Fondo y rejilla
    svg.appendChild(svgEl("rect", { x: padL, y: padT, width: plotW, height: chartH, fill: "#f8fafc", rx: 6, stroke: "#dfe6ee" }));
    svg.appendChild(svgEl("rect", { x: padL, y: evY - 16, width: plotW, height: 34, fill: "#f1f5f9", rx: 6 }));

    // Rangos dinámicos de temperatura (izq) y voltaje/nivel (der)
    var temps = [];
    var volts = [];
    series.forEach(function(p) {
      if (p.epoch < minEp || p.epoch > maxEp) return;
      if (seriesEnabled.ap_c && p.ap_c != null) temps.push(p.ap_c);
      if (seriesEnabled.bat_c && p.bat_c != null) temps.push(p.bat_c);
      if (seriesEnabled.skin_c && p.skin_c != null) temps.push(p.skin_c);
      if (seriesEnabled.volt_mv && p.volt_mv != null) volts.push(p.volt_mv);
    });
    var tMin = temps.length ? Math.floor(Math.min(20, Math.min.apply(null, temps) - 2)) : 20;
    var tMax = temps.length ? Math.ceil(Math.max(50, Math.max.apply(null, temps) + 3)) : 55;
    if (tMax - tMin < 10) tMax = tMin + 10;

    var vMin = volts.length ? Math.floor((Math.min.apply(null, volts) - 100) / 100) * 100 : 3400;
    var vMax = volts.length ? Math.ceil((Math.max.apply(null, volts) + 100) / 100) * 100 : 4500;
    if (vMax - vMin < 300) vMax = vMin + 300;

    function yTemp(v) { return padT + chartH - ((v - tMin) / (tMax - tMin)) * chartH; }
    function yVolt(v) { return padT + chartH - ((v - vMin) / (vMax - vMin)) * chartH; }
    function yPct(v) { return padT + chartH - (Math.max(0, Math.min(100, v)) / 100) * chartH; }

    for (var i = 0; i <= 4; i++) {
      var frac = i / 4;
      var y = padT + chartH - frac * chartH;
      svg.appendChild(svgEl("line", { x1: padL, y1: y, x2: W - padR, y2: y, stroke: "#e2e8f0", "stroke-dasharray": "3,3" }));
      var tLbl = Math.round(tMin + frac * (tMax - tMin));
      svg.appendChild(svgEl("text", { x: padL - 7, y: y + 4, "text-anchor": "end", "font-size": 10, fill: "#b91c1c" }, tLbl + "°C"));
      if (seriesEnabled.volt_mv) {
        var vLbl = Math.round(vMin + frac * (vMax - vMin));
        svg.appendChild(svgEl("text", { x: W - padR + 7, y: y + 4, "text-anchor": "start", "font-size": 10, fill: "#0f766e" }, vLbl + "mV"));
      } else if (seriesEnabled.nivel) {
        var pLbl = Math.round(frac * 100);
        svg.appendChild(svgEl("text", { x: W - padR + 7, y: y + 4, "text-anchor": "start", "font-size": 10, fill: "#2563eb" }, pLbl + "%"));
      }
    }

    // Línea de umbral térmico 45°C
    if (45 >= tMin && 45 <= tMax) {
      var y45 = yTemp(45);
      svg.appendChild(svgEl("line", { x1: padL, y1: y45, x2: W - padR, y2: y45, stroke: "#fca5a5", "stroke-dasharray": "5,4" }));
      svg.appendChild(svgEl("text", { x: padL + 6, y: y45 - 4, "font-size": 9, fill: "#b91c1c" }, "Umbral calor AP 45°C"));
    }

    // Eje X ticks
    for (var tx = 0; tx <= 5; tx++) {
      var epTick = minEp + (tx / 5) * span;
      var xx = xOf(epTick);
      svg.appendChild(svgEl("line", { x1: xx, y1: padT, x2: xx, y2: padT + chartH, stroke: "#eef2f6" }));
      svg.appendChild(svgEl("text", { x: xx, y: padT + chartH + 14, "text-anchor": "middle", "font-size": 10, fill: "#475569" }, fmtTs(epTick, span)));
    }

    // Series polilíneas
    var defs = [
      { key: "ap_c", color: "#dc2626", width: 2.2, yFn: yTemp },
      { key: "skin_c", color: "#ea580c", width: 1.8, yFn: yTemp },
      { key: "bat_c", color: "#d97706", width: 1.8, yFn: yTemp },
      { key: "volt_mv", color: "#0d9488", width: 1.8, yFn: yVolt, dash: "4,2" },
      { key: "nivel", color: "#2563eb", width: 1.6, yFn: yPct, dash: "2,2" }
    ];
    defs.forEach(function(def) {
      if (!seriesEnabled[def.key]) return;
      var pts = [];
      series.forEach(function(p) {
        if (p.epoch < minEp || p.epoch > maxEp) return;
        var val = p[def.key];
        if (val != null) pts.push(xOf(p.epoch).toFixed(1) + "," + def.yFn(val).toFixed(1));
      });
      if (pts.length >= 2) {
        var attrs = { fill: "none", stroke: def.color, "stroke-width": def.width, points: pts.join(" ") };
        if (def.dash) attrs["stroke-dasharray"] = def.dash;
        svg.appendChild(svgEl("polyline", attrs));
      } else if (pts.length === 1) {
        var coords = pts[0].split(",");
        svg.appendChild(svgEl("circle", { cx: coords[0], cy: coords[1], r: 3.5, fill: def.color }));
      }
    });

    // Pista de eventos
    svg.appendChild(svgEl("text", { x: padL - 6, y: evY + 4, "text-anchor": "end", "font-size": 10, fill: "#475569", "font-weight": 700 }, "Eventos"));
    events.forEach(function(ev) {
      if (ev.epoch < minEp || ev.epoch > maxEp) return;
      var ex = xOf(ev.epoch);
      var col = sevColor(ev.severidad);
      svg.appendChild(svgEl("line", { x1: ex, y1: padT, x2: ex, y2: evY - 12, stroke: col, "stroke-opacity": "0.28", "stroke-dasharray": "2,3" }));
      var marker = svgEl("circle", { cx: ex, cy: evY, r: ev.severidad === "critico" ? 6 : 5, fill: col, stroke: "#fff", "stroke-width": 1.5, style: "cursor:pointer" });
      marker.appendChild(svgEl("title", {}, (ev.ts_iso || "") + " — " + (ev.titulo || "")));
      marker.addEventListener("mouseenter", function() {
        if (hoverBox) {
          hoverBox.textContent = "[" + (ev.ts_iso || "") + "] " + (ev.titulo || "") + (ev.detalle ? " · " + ev.detalle : "");
        }
      });
      svg.appendChild(marker);
    });

    // Crosshair interactivo
    var guide = svgEl("line", { x1: padL, y1: padT, x2: padL, y2: evY + 12, stroke: "#334155", "stroke-width": 1, "stroke-dasharray": "3,3", visibility: "hidden" });
    svg.appendChild(guide);

    var overlay = svgEl("rect", { x: padL, y: padT, width: plotW, height: chartH + 22, fill: "transparent" });
    overlay.addEventListener("mousemove", function(evt) {
      var rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      var svgX = ((evt.clientX - rect.left) / rect.width) * W;
      var clampedX = Math.max(padL, Math.min(W - padR, svgX));
      guide.setAttribute("x1", clampedX);
      guide.setAttribute("x2", clampedX);
      guide.setAttribute("visibility", "visible");

      var targetEp = minEp + ((clampedX - padL) / plotW) * span;
      var nearest = null;
      var bestDist = Infinity;
      series.forEach(function(p) {
        if (p.epoch < minEp || p.epoch > maxEp) return;
        var d = Math.abs(p.epoch - targetEp);
        if (d < bestDist) { bestDist = d; nearest = p; }
      });
      if (hoverBox && nearest) {
        var parts = [nearest.ts_iso || ""];
        if (nearest.ap_c != null) parts.push("AP: " + nearest.ap_c.toFixed(1) + "°C");
        if (nearest.skin_c != null) parts.push("SKIN: " + nearest.skin_c.toFixed(1) + "°C");
        if (nearest.bat_c != null) parts.push("BAT: " + nearest.bat_c.toFixed(1) + "°C");
        if (nearest.volt_mv != null) parts.push("Voltaje: " + nearest.volt_mv + " mV");
        if (nearest.nivel != null) parts.push("Nivel: " + nearest.nivel + "%");
        hoverBox.textContent = parts.join(" · ");
      }
    });
    overlay.addEventListener("mouseleave", function() {
      guide.setAttribute("visibility", "hidden");
    });
    svg.appendChild(overlay);
  }

  function updateButtons(nodeList, attr, currentVal) {
    nodeList.forEach(function(btn) {
      if (btn.getAttribute(attr) === currentVal) btn.classList.add("active");
      else btn.classList.remove("active");
    });
  }

  sevButtons.forEach(function(btn) {
    btn.addEventListener("click", function() {
      sevFilter = btn.getAttribute("data-tl-sev");
      updateButtons(sevButtons, "data-tl-sev", sevFilter);
      render();
    });
  });
  catButtons.forEach(function(btn) {
    btn.addEventListener("click", function() {
      catFilter = btn.getAttribute("data-tl-cat");
      updateButtons(catButtons, "data-tl-cat", catFilter);
      render();
    });
  });
  scopeButtons.forEach(function(btn) {
    btn.addEventListener("click", function() {
      scopeFilter = btn.getAttribute("data-tl-scope");
      updateButtons(scopeButtons, "data-tl-scope", scopeFilter);
      render();
    });
  });
  seriesChecks.forEach(function(chk) {
    chk.addEventListener("change", function() {
      seriesEnabled[chk.getAttribute("data-tl-series")] = chk.checked;
      render();
    });
  });

  render();
})();
"""

    return (
        f'<section class="card" id="linea-tiempo">'
        f'<div class="sec-head"><h2>⏱️ Correlación temporal interactiva</h2>'
        f'<span class="badge badge-neutral" id="tl-count-badge">{len(eventos)} eventos</span></div>'
        f'<p class="sec-summary">Línea de tiempo unificada cruzando temperatura, voltaje de batería y eventos críticos (ANR, crashes, throttling térmico, LMKD y reinicios).</p>'
        f"{corr_html}"
        f'<div class="tl-controls">'
        f'<div class="tl-group"><span class="tl-lbl">Severidad:</span>'
        f'<button type="button" class="tl-btn active" data-tl-sev="all">Todos</button>'
        f'<button type="button" class="tl-btn" data-tl-sev="critico">Crítico</button>'
        f'<button type="button" class="tl-btn" data-tl-sev="atencion">Atención</button>'
        f'<button type="button" class="tl-btn" data-tl-sev="info">Info</button>'
        f"</div>"
        f'<div class="tl-group"><span class="tl-lbl">Categoría:</span>'
        f'<button type="button" class="tl-btn active" data-tl-cat="all">Todas</button>'
        f'<button type="button" class="tl-btn" data-tl-cat="termico">Térmico</button>'
        f'<button type="button" class="tl-btn" data-tl-cat="bateria">Batería</button>'
        f'<button type="button" class="tl-btn" data-tl-cat="estabilidad">Estabilidad</button>'
        f'<button type="button" class="tl-btn" data-tl-cat="memoria">Memoria</button>'
        f'<button type="button" class="tl-btn" data-tl-cat="reinicio">Reinicios</button>'
        f"</div>"
        f'<div class="tl-group"><span class="tl-lbl">Ventana:</span>'
        f'<button type="button" class="tl-btn active" data-tl-scope="ventana">Sesión reciente</button>'
        f'<button type="button" class="tl-btn" data-tl-scope="all">Todo el historial</button>'
        f"</div>"
        f"</div>"
        f'<div class="tl-series-toggles">'
        f'<label><input type="checkbox" data-tl-series="ap_c" checked> <i class="dot" style="background:#dc2626"></i> Temp. AP (°C)</label>'
        f'<label><input type="checkbox" data-tl-series="skin_c" checked> <i class="dot" style="background:#ea580c"></i> Carcasa SKIN (°C)</label>'
        f'<label><input type="checkbox" data-tl-series="bat_c" checked> <i class="dot" style="background:#d97706"></i> Batería (°C)</label>'
        f'<label><input type="checkbox" data-tl-series="volt_mv" checked> <i class="dot" style="background:#0d9488"></i> Voltaje (mV)</label>'
        f'<label><input type="checkbox" data-tl-series="nivel"> <i class="dot" style="background:#2563eb"></i> Nivel (%)</label>'
        f"</div>"
        f'<div id="tl-hover-info" class="tl-hover">Pasa el cursor sobre la gráfica o sobre un marcador de evento para inspeccionar ese instante.</div>'
        f'<div class="svg-scroll">{fallback_svg}</div>'
        f'<div class="table-wrap" style="margin-top:12px;"><table>'
        f"<thead><tr><th>Fecha y hora</th><th>Severidad</th><th>Categoría</th><th>Evento</th></tr></thead>"
        f'<tbody id="tl-events-body"></tbody></table></div>'
        f'<script id="tl-data" type="application/json">{json_embebido}</script>'
        f"<script>{script_js}</script>"
        f"</section>"
    )


def _seccion_bateria(bat, sec_info):
    salud_txt = f"{bat['salud_asoc_pct']}%" if bat["salud_asoc_pct"] is not None else bat["salud_texto"]
    ciclos_txt = f"~{bat['ciclos']:.0f}" if bat["ciclos"] is not None else "N/D"
    temp_txt = f"{bat['temperatura_c']:.1f} °C" if bat["temperatura_c"] is not None else "N/D"
    nivel_txt = f"{bat['nivel']}%" if bat["nivel"] is not None else "N/D"
    ds_txt = f"{bat['deep_sleep_pct']:.1f}%" if bat.get("deep_sleep_pct") is not None else "N/D"
    ds_sub = (
        f"Pantalla apagada: {bat['deep_sleep_screen_off_pct']:.1f}%"
        if bat.get("deep_sleep_screen_off_pct") is not None
        else f"En batería: {bat['tiempo_en_bateria'] or 'N/D'}"
    )
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
            _tarjeta_metrica("Deep Sleep", ds_txt, ds_sub),
            _tarjeta_metrica("Temperatura", temp_txt, bat["fuente"] or "En batería"),
            _tarjeta_metrica(
                "Pantalla encendida",
                bat["pantalla_encendida"] or "N/D",
                f"En batería: {bat['tiempo_en_bateria'] or 'N/D'}",
            ),
            _tarjeta_metrica("Protección de batería", prot_txt, f"Capacidad: {bat['capacidad_diseno_mah'] or 'N/D'} mAh"),
        ]
    )

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
    lmkd_kills = mem.get("lmkd_kills", 0)

    cards = "".join(
        [
            _tarjeta_metrica("RAM total", _fmt_kb(mem["total_kb"]), f"Estado Android: {mem['estado_ram'] or 'N/D'}"),
            _tarjeta_metrica("RAM disponible", _fmt_kb(mem["disponible_kb"]), "Lista para nuevas apps"),
            _tarjeta_metrica(
                "ZRAM (RAM comprimida)",
                f"{_fmt_kb(mem['zram_fisica_kb'])} → {_fmt_kb(mem['zram_swap_kb'])}",
                f"De {_fmt_kb(mem['zram_total_kb'])} asignados ({zram_pct:.0f}%)",
            ),
            _tarjeta_metrica(
                "Presión de RAM (PSI)",
                f"{psi_full60:.2f}%",
                f"Avg 60s (full) · LMKD kills: {lmkd_kills}",
            ),
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
        f"RAM perdida/kernel: {_esc(_fmt_kb(mem['ram_perdida_kb']))} · "
        f"Eventos LMKD: {lmkd_kills}.</p>"
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

    if rt.get("temperatura_max_c") is not None:
        sensores_cards.append(
            _tarjeta_metrica(
                "Temperatura máx. registrada",
                f"{rt['temperatura_max_c']:.1f} °C",
                f"Sensor: {rt.get('temperatura_max_sensor') or 'N/D'}",
            )
        )

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
        f"Ajustes LMH en historial térmico: {rt['eventos_lmh']} · "
        f"Episodios throttling detectados: {rt.get('eventos_throttling', 0)}."
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


def generar_html(datos, diag, diff=None, historial=None):
    """Genera un informe HTML autocontenido, responsive, con línea de tiempo SVG/JS y evolución histórica."""
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
    score_trend_html = ""
    if diff and diff.get("metricas", {}).get("puntuacion"):
        score_trend_html = (
            f'<div style="margin-top:6px;">{_trend_badge(diff["metricas"]["puntuacion"], " pts", entero=True)} '
            f'<span class="hero-meta">vs {_esc(diff["fecha_anterior"])}</span></div>'
        )

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
                f"Máx: {rt['temperatura_max_c']:.1f} °C" if rt.get("temperatura_max_c") is not None else rt["estado_termico_texto"],
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

    evolucion_html = _seccion_evolucion(diff, historial)
    timeline_html = _seccion_linea_tiempo(datos.get("linea_tiempo"))

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

    nav_evol = '<a href="#evolucion">Evolución</a>' if diff else ""

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
    .container { max-width: 1060px; margin: 0 auto; display: grid; gap: 20px; }
    .hero {
      background: linear-gradient(135deg, #0f172a, #1e3a8a);
      color: #fff; border-radius: 16px; padding: 24px 28px;
      display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 20px;
    }
    .hero h1 { margin: 0 0 6px; font-size: 1.65rem; }
    .hero-meta { color: #cbd5e1; font-size: 0.94rem; }
    .score-box {
      background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.22);
      border-radius: 14px; padding: 14px 20px; text-align: center; min-width: 195px;
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
    .metric-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
    .metric-label { font-size: 0.8rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em; }
    .metric-val { font-size: 1.18rem; font-weight: 700; }
    .metric-sub { font-size: 0.83rem; color: var(--muted); margin-top: 3px; }
    .badge { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; white-space: nowrap; }
    .badge-ok { background: var(--ok-bg); color: var(--ok-fg); }
    .badge-warn { background: var(--warn-bg); color: var(--warn-fg); }
    .badge-bad { background: var(--bad-bg); color: var(--bad-fg); }
    .badge-neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
    .trend-badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.76rem; font-weight: 700; white-space: nowrap; }
    .trend-good { background: var(--ok-bg); color: var(--ok-fg); }
    .trend-bad { background: var(--bad-bg); color: var(--bad-fg); }
    .trend-eq { background: var(--neutral-bg); color: var(--neutral-fg); }
    .trend-info { background: #e0f2fe; color: #0369a1; }
    .so-banner { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a; border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; font-size: 0.92rem; }
    .diff-alert { border-radius: 10px; padding: 12px 16px; margin-top: 14px; font-size: 0.92rem; }
    .diff-alert ul { margin: 6px 0 0 18px; padding: 0; }
    .diff-alert li { margin: 4px 0; }
    .diff-alert-bad { background: #fff5f5; border: 1px solid #fecaca; color: #991b1b; }
    .diff-alert-good { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
    .diff-alert-warn { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; margin-bottom: 14px; }
    .bad-txt { color: #b91c1c; font-weight: 700; }
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
    .svg-scroll { overflow-x: auto; margin-top: 8px; }
    .chart-svg { width: 100%; min-width: 620px; height: auto; display: block; }
    .tl-controls { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 10px; }
    .tl-group { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }
    .tl-lbl { font-size: 0.82rem; font-weight: 700; color: var(--muted); margin-right: 2px; }
    .tl-btn {
      border: 1px solid var(--border); background: #f8fafc; color: #334155;
      padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; cursor: pointer;
    }
    .tl-btn.active { background: #1e3a8a; color: #fff; border-color: #1e3a8a; }
    .tl-series-toggles { display: flex; flex-wrap: wrap; gap: 14px; font-size: 0.84rem; margin-bottom: 8px; color: #334155; }
    .tl-series-toggles label { display: inline-flex; align-items: center; gap: 5px; cursor: pointer; }
    .tl-legend { display: flex; gap: 18px; font-size: 0.85rem; color: #334155; margin-bottom: 4px; }
    .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; vertical-align: middle; }
    .tl-hover {
      background: #f8fafc; border: 1px solid var(--border); border-radius: 8px;
      padding: 8px 12px; font-size: 0.85rem; color: #1e293b; min-height: 36px;
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
        {score_trend_html}
        <div class="hero-meta" style="margin-top:4px;">{_esc(diag['frase_global'])}</div>
      </div>
    </header>

    <nav class="nav-pills" aria-label="Secciones del informe">
      <a href="#resumen">Resumen</a>
      {nav_evol}
      <a href="#linea-tiempo">Línea de tiempo</a>
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

    {evolucion_html}

    {timeline_html}

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
      Se omitieron identificadores personales sensibles (número de serie, direcciones MAC, redes Wi-Fi guardadas, IMEI y cuentas).
    </footer>
  </main>
</body>
</html>
"""
