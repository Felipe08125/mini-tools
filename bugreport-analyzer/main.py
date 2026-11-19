import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
import io
import json
from pathlib import Path
import re
import sys
import zipfile


# Nombres amigables para los paquetes más frecuentes (evita mostrar solo IDs técnicos)
NOMBRES_AMIGABLES = {
    "com.whatsapp": "WhatsApp",
    "com.instagram.android": "Instagram",
    "com.google.android.youtube": "YouTube",
    "com.android.chrome": "Google Chrome",
    "com.google.android.gm": "Gmail",
    "com.spotify.music": "Spotify",
    "com.google.android.gms": "Servicios de Google Play",
    "com.google.android.googlequicksearchbox": "App de Google",
    "com.google.android.apps.messaging": "Mensajes de Google",
    "com.google.android.apps.maps": "Google Maps",
    "com.google.android.keep": "Google Keep",
    "com.android.vending": "Google Play Store",
    "com.android.systemui": "Interfaz del sistema",
    "com.sec.android.app.launcher": "Inicio de One UI",
    "com.sec.android.app.camera": "Cámara Samsung",
    "com.sec.android.gallery3d": "Galería Samsung",
    "com.sec.android.app.clockpackage": "Reloj Samsung",
    "com.samsung.android.honeyboard": "Teclado Samsung",
    "com.samsung.android.app.notes": "Samsung Notes",
    "com.samsung.android.scloud": "Samsung Cloud",
    "com.samsung.android.samsungpass": "Samsung Pass",
    "com.samsung.android.app.aodservice": "Always On Display",
    "com.samsung.android.app.routines": "Modos y Rutinas",
    "com.samsung.android.ipsgeofence": "Detección de ubicación Samsung",
    "com.samsung.android.smartsuggestions": "Sugerencias inteligentes",
    "com.samsung.android.lool": "Cuidado del dispositivo",
    "com.samsung.android.game.gamehome": "Gaming Hub",
    "com.samsung.knox.securefolder": "Carpeta Segura",
    "com.facebook.katana": "Facebook",
    "com.facebook.orca": "Messenger",
    "com.microsoft.office.outlook": "Microsoft Outlook",
    "com.linkedin.android": "LinkedIn",
    "com.android.settings": "Ajustes",
    "com.android.phone": "Teléfono",
    "com.android.bluetooth": "Bluetooth",
}

UIDS_SISTEMA = {
    0: ("root", "Sistema base (root)"),
    1000: ("system", "Sistema Android"),
    1001: ("radio", "Módem y telefonía"),
    1002: ("bluetooth", "Servicio Bluetooth"),
    1010: ("wifi", "Servicio Wi-Fi"),
    1041: ("audioserver", "Servidor de audio"),
    1047: ("cameraserver", "Servicio de cámara"),
    5022: ("com.samsung.android.ipsgeofence", "Detección de ubicación Samsung"),
    -5: ("tethering", "Red móvil / Tethering (sin app asignada)"),
    -4: ("removed", "Apps desinstaladas"),
}

ESTADO_BATERIA = {
    2: "Cargando",
    3: "Descargando",
    4: "Sin cargar",
    5: "Carga completa",
}

SALUD_BATERIA = {
    2: "Buena",
    3: "Sobrecalentada",
    4: "Dañada",
    5: "Sobrevoltaje",
    7: "Demasiado fría",
}

ESTADO_TERMICO = {
    0: "Normal (sin calentamiento)",
    1: "Tibio (ligero)",
    2: "Moderado (posible reducción leve de potencia)",
    3: "Alto (limitación activa de rendimiento)",
    4: "Crítico (sobrecalentamiento)",
    5: "Emergencia térmica",
    6: "Apagado térmico inminente",
}

MOTIVOS_REINICIO_NORMAL = {
    "userrequested",
    "recovery",
    "recovery-update",
    "mainline_update",
    "rampluschanged",
    "ota",
    "silent",
}

MOTIVOS_SIN_BATERIA = {"no power", "low battery", "low_battery"}

MOTIVOS_ANORMALES = (
    "panic",
    "watchdog",
    "kernel",
    "rpm",
    "upload",
    "crash",
    "thermal",
    "hardreset",
    "wdt",
    "tz",
    "smpl",
)

LOGCAT_RE = re.compile(
    r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\S+)\s+(\d+)\s+(\d+)\s+([VDIWEFA])\s+([^:]+?)\s*:\s?(.*)$"
)
DURACION_TOKEN_RE = re.compile(r"(\d+)\s*(d|h|m|s|ms)\b")


def nombre_amigable(identificador):
    """Convierte un nombre de paquete técnico en un nombre legible para usuarios."""
    if not identificador:
        return "Desconocido"
    base = identificador.split(":", 1)[0].strip()
    if base in NOMBRES_AMIGABLES:
        return f"{NOMBRES_AMIGABLES[base]} ({identificador})" if ":" in identificador else NOMBRES_AMIGABLES[base]
    return identificador


def formatear_bytes(num_bytes):
    """Formatea bytes en KB, MB o GB de forma legible."""
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


def formatear_kb(kb):
    """Formatea kilobytes (base 1024) en MB o GB."""
    if kb is None:
        return "N/D"
    return formatear_bytes(kb * 1024)


def limpiar_duracion(texto):
    """Resume una cadena de duración de Android quitando los milisegundos finales."""
    if not texto:
        return "N/D"
    sin_ms = re.sub(r"\s+\d+ms\b", "", texto).strip()
    return sin_ms or texto.strip()


def duracion_a_segundos(texto):
    """Convierte textos tipo '18m 18s 43ms' a segundos totales."""
    if not texto:
        return 0.0
    factores = {"d": 86400.0, "h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    total = 0.0
    for valor, unidad in DURACION_TOKEN_RE.findall(texto):
        total += int(valor) * factores[unidad]
    return total


def parsear_uid_android(uid_texto):
    """Convierte identificadores tipo 'u0a473', '1000' o '-5' al UID numérico."""
    uid_texto = uid_texto.strip()
    if re.fullmatch(r"-?\d+", uid_texto):
        return int(uid_texto)
    m = re.fullmatch(r"u(\d+)a(\d+)", uid_texto)
    if m:
        return int(m.group(1)) * 100000 + 10000 + int(m.group(2))
    m_sys = re.fullmatch(r"u(\d+)s(\d+)", uid_texto)
    if m_sys:
        return int(m_sys.group(1)) * 100000 + int(m_sys.group(2))
    return None


def resolver_uid(uid_texto, mapa_uid_paquetes):
    """Devuelve (paquete, nombre_legible) para un UID de batterystats."""
    uid_num = parsear_uid_android(uid_texto)
    if uid_num is not None:
        if uid_num in UIDS_SISTEMA:
            return UIDS_SISTEMA[uid_num]
        if uid_num in mapa_uid_paquetes:
            paquetes = mapa_uid_paquetes[uid_num]
            principal = paquetes[0]
            etiqueta = nombre_amigable(principal)
            if len(paquetes) > 1 and principal not in NOMBRES_AMIGABLES:
                etiqueta = f"{etiqueta} (+{len(paquetes) - 1})"
            return principal, etiqueta
    return uid_texto, f"Proceso {uid_texto}"


def es_carpeta_bugreport(carpeta):
    """Comprueba si una carpeta contiene un dumpstate o main_entry.txt."""
    if not carpeta.is_dir():
        return False
    if (carpeta / "main_entry.txt").is_file() or (carpeta / "dumpstate.txt").is_file():
        return True
    return any(carpeta.glob("bugreport-*.txt"))


def resolver_fuente(ruta_arg=None):
    """Encuentra el informe de errores indicado o detecta el más reciente en report/."""
    if ruta_arg:
        candidato = Path(ruta_arg).expanduser().resolve()
        if not candidato.exists():
            raise FileNotFoundError(f"No existe la ruta indicada: {candidato}")
        if candidato.is_file():
            return candidato
        if es_carpeta_bugreport(candidato):
            return candidato
        return _elegir_de_contenedor(candidato)

    base_script = Path(__file__).resolve().parent
    for carpeta_report in (base_script / "report", base_script.parent / "report"):
        if carpeta_report.is_dir():
            return _elegir_de_contenedor(carpeta_report)

    raise FileNotFoundError(
        "No se encontró la carpeta 'report'. Pasa la ruta del informe como argumento "
        "o coloca tu carpeta/zip dentro de 'report/'."
    )


def _elegir_de_contenedor(carpeta):
    """Selecciona el bugreport más reciente dentro de una carpeta contenedora."""
    if es_carpeta_bugreport(carpeta):
        return carpeta

    candidatos = []
    for item in carpeta.iterdir():
        if item.is_dir() and es_carpeta_bugreport(item):
            candidatos.append(item)
        elif item.is_file() and item.suffix.lower() == ".zip":
            candidatos.append(item)
        elif item.is_file() and item.suffix.lower() == ".txt" and (
            item.name == "dumpstate.txt" or item.name.startswith("bugreport-")
        ):
            candidatos.append(item)

    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró ningún informe de errores válido (.txt, .zip o carpeta bugreport-*) en: {carpeta}"
        )

    candidatos.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return candidatos[0]


@contextmanager
def abrir_dumpstate(fuente):
    """Abre el archivo principal del bugreport en modo streaming seguro UTF-8."""
    fuente = Path(fuente)
    if fuente.is_file() and fuente.suffix.lower() == ".zip":
        with zipfile.ZipFile(fuente, "r") as zf:
            nombres = set(zf.namelist())
            entrada = None
            if "main_entry.txt" in nombres:
                contenido = zf.read("main_entry.txt").decode("utf-8", errors="replace").strip()
                if contenido in nombres:
                    entrada = contenido
            if not entrada:
                txts = [
                    info
                    for info in zf.infolist()
                    if not info.is_dir()
                    and info.filename.lower().endswith(".txt")
                    and (
                        Path(info.filename).name == "dumpstate.txt"
                        or Path(info.filename).name.startswith("bugreport-")
                    )
                ]
                if not txts:
                    txts = [
                        info
                        for info in zf.infolist()
                        if not info.is_dir() and info.filename.lower().endswith(".txt")
                    ]
                if not txts:
                    raise FileNotFoundError(f"El archivo ZIP no contiene ningún .txt de informe: {fuente}")
                entrada = max(txts, key=lambda info: info.file_size).filename
            with zf.open(entrada, "r") as raw:
                yield f"{fuente.name} -> {entrada}", io.TextIOWrapper(
                    raw, encoding="utf-8", errors="replace", newline=None
                )
        return

    if fuente.is_dir():
        archivo = None
        main_entry = fuente / "main_entry.txt"
        if main_entry.is_file():
            nombre = main_entry.read_text(encoding="utf-8", errors="replace").strip()
            if nombre and (fuente / nombre).is_file():
                archivo = fuente / nombre
        if archivo is None and (fuente / "dumpstate.txt").is_file():
            archivo = fuente / "dumpstate.txt"
        if archivo is None:
            txts = sorted(fuente.glob("bugreport-*.txt"), key=lambda p: p.stat().st_size, reverse=True)
            if txts:
                archivo = txts[0]
        if archivo is None:
            raise FileNotFoundError(f"No se encontró dumpstate.txt ni bugreport-*.txt en: {fuente}")
        with archivo.open("r", encoding="utf-8", errors="replace") as f:
            yield str(archivo), f
        return

    if fuente.is_file():
        with fuente.open("r", encoding="utf-8", errors="replace") as f:
            yield str(fuente), f
        return

    raise FileNotFoundError(f"No se puede leer la fuente indicada: {fuente}")


def _formatear_oneui(valor_raw):
    """Convierte '90000' -> '9.0' o '80500' -> '8.5'."""
    if not valor_raw or not valor_raw.isdigit():
        return valor_raw
    num = int(valor_raw)
    mayor = num // 10000
    menor = (num % 10000) // 100
    return f"{mayor}.{menor}"


def _int_limpio(texto):
    """Convierte enteros con comas ('11,350,572') a int."""
    return int(texto.replace(",", "").strip())


def _detectar_seccion(line):
    """Identifica el bloque actual del dumpstate según su línea de cabecera."""
    if line.startswith("------ "):
        if "was the duration of" in line:
            return None
        if line.startswith("------ MEMORY INFO"):
            return "meminfo_proc"
        if line.startswith("------ SYSTEM LOG (") and "AFTER DONE" not in line:
            return "system_log"
        if line.startswith("------ KERNEL LOG ("):
            return "dmesg"
        if line.startswith("------ PSI cpu "):
            return "psi_cpu"
        if line.startswith("------ PSI memory "):
            return "psi_memory"
        if line.startswith("------ PSI io "):
            return "psi_io"
        if line.startswith("------ UFS PART NUMBER"):
            return "ufs_model"
        if line.startswith("------ UFS VENDOR"):
            return "ufs_vendor"
        if line.startswith("------ UFS LT "):
            return "ufs_lt"
        if line.startswith("------ UFS ERR SUMMARY"):
            return "ufs_err"
        if line.startswith("------ SYSTEM PROPERTIES"):
            return "getprop"
        if line.startswith("------ POWER OFF RESET REASON ("):
            return "reset_reason"
        if line.startswith("------ AP RESET INFO EXTEND"):
            return "ap_reset"
        if line.startswith("------ ANR FILES"):
            return "anr_files"
        if line.startswith("------ FILESYSTEMS & FREE SPACE (df)"):
            return "df"
        if line.startswith("------ UPTIME ("):
            return "uptime"
        if line.startswith("------ DROPBOX SYSTEM SERVER CRASHES"):
            return "dropbox_sys_crash"
        if line.startswith("------ DROPBOX SYSTEM APP CRASHES"):
            return "dropbox_app_crash"
        if line.startswith("------ DROPBOX SYSTEM WATCHDOG CRASHES"):
            return "dropbox_wd_crash"
        if line.startswith("------ POWER ON INFO"):
            return "boot_stat"
        if line.startswith("------ THERMAL DUMP"):
            return "thermal_dump"
        if line.startswith("------ CHECKIN BATTERYSTATS"):
            return "checkin_batterystats"
        if line.startswith("------ CHECKIN PACKAGE"):
            return "checkin_package"
        return None

    if line.startswith("DUMP OF SERVICE "):
        nombre = line[len("DUMP OF SERVICE "):].strip().rstrip(":")
        mapa = {
            "CRITICAL cpuinfo": "svc_cpuinfo",
            "HIGH meminfo": "svc_meminfo",
            "battery": "svc_battery",
            "android.hardware.health.IHealth/default": "svc_ihealth",
            "batterystats": "svc_batterystats",
            "diskstats": "svc_diskstats",
            "thermalservice": "svc_thermalservice",
            "wifi": "svc_wifi",
            "telephony.registry": "svc_telephony",
            "adb": "svc_adb",
            "dropbox": "svc_dropbox",
        }
        return mapa.get(nombre, "__other_service__")

    if line.startswith("--------- ") and "was the duration of dumpsys" in line:
        return None

    return "__keep__"


def _parsear_psi(line, destino):
    """Extrae promedios some/full de /proc/pressure/*."""
    m = re.match(
        r"^(some|full)\s+avg10=([\d.]+)\s+avg60=([\d.]+)\s+avg300=([\d.]+)",
        line.strip(),
    )
    if m:
        destino[m.group(1)] = {
            "avg10": float(m.group(2)),
            "avg60": float(m.group(3)),
            "avg300": float(m.group(4)),
        }


def _clasificar_motivo_reinicio(motivo_raw):
    """Clasifica el motivo de un apagado o reinicio en normal, sin_bateria o anormal."""
    limpio = motivo_raw.lower().replace("[-]", "").strip()
    tokens = [t.strip() for t in re.split(r"[,/]+", limpio) if t.strip()]
    if any(t in MOTIVOS_SIN_BATERIA for t in tokens) or "no power" in limpio:
        return "sin_bateria"
    if any(t in MOTIVOS_REINICIO_NORMAL for t in tokens):
        return "normal"
    if any(k in limpio for k in MOTIVOS_ANORMALES):
        return "anormal"
    return "otro"


def analizar_dumpstate(lineas):
    """Analiza un dumpstate.txt completo en una sola pasada por streaming."""
    datos = {
        "dispositivo": {
            "fecha_informe": None,
            "fabricante": None,
            "modelo": None,
            "nombre_comercial": None,
            "soc": None,
            "hardware": None,
            "android": None,
            "sdk": None,
            "oneui": None,
            "compilacion": None,
            "parche_seguridad": None,
            "operador": None,
            "zona_horaria": None,
            "uptime_texto": None,
            "load_avg": None,
            "tiempo_arranque_ms": None,
            "total_paquetes": 0,
        },
        "bateria": {
            "nivel": None,
            "estado_codigo": None,
            "salud_codigo": None,
            "fuente": None,
            "voltaje_mv": None,
            "temperatura_c": None,
            "corriente_ma": None,
            "tecnologia": None,
            "capacidad_diseno_mah": None,
            "salud_asoc_pct": None,
            "ciclos": None,
            "primer_uso": None,
            "proteccion_modo": None,
            "proteccion_limite": None,
            "carga_rapida": None,
            "carga_super_rapida": None,
            "tiempo_en_bateria": None,
            "tiempo_pantalla_off": None,
            "pantalla_encendida": None,
            "pantalla_encendida_pct": None,
            "descarga_mah": None,
            "descarga_pantalla_on_mah": None,
            "descarga_pantalla_off_mah": None,
            "tiempo_carga_restante": None,
            "brillo": {},
            "refresco": {},
            "consumo_componentes": {},
            "consumo_apps": [],
            "wakelocks": [],
        },
        "memoria": {
            "total_kb": None,
            "disponible_kb": None,
            "libre_kb": None,
            "cached_kb": None,
            "swap_total_kb": None,
            "swap_libre_kb": None,
            "estado_ram": None,
            "ram_usada_kb": None,
            "ram_libre_android_kb": None,
            "ram_perdida_kb": None,
            "zram_fisica_kb": None,
            "zram_swap_kb": None,
            "zram_total_kb": None,
            "top_procesos": [],
            "psi": {},
        },
        "almacenamiento": {
            "data_total_kb": None,
            "data_usado_kb": None,
            "data_libre_kb": None,
            "data_uso_pct": None,
            "latencia_ms": None,
            "velocidad_escritura_kbs": None,
            "cifrado_archivos": None,
            "categorias_bytes": {},
            "top_apps": [],
            "top_cache": [],
            "ufs_fabricante": None,
            "ufs_modelo": None,
            "ufs_vida_util": None,
            "ufs_errores": {},
        },
        "rendimiento_termico": {
            "cpu_load": None,
            "top_cpu": [],
            "psi_cpu": {},
            "psi_io": {},
            "estado_termico": None,
            "sensores": [],
            "sensores_cache": [],
            "umbrales_skin": [],
            "eventos_lmh": 0,
        },
        "estabilidad": {
            "logcat_conteo": {"W": 0, "E": 0, "F": 0},
            "watchdog_sync_latidos": 0,
            "top_tags_error": [],
            "crashes_java": [],
            "crashes_nativos": [],
            "anrs_logcat": [],
            "anr_archivos": [],
            "dropbox_crashes": {"system_server": 0, "system_app": 0, "watchdog": 0},
            "dropbox_total_entradas": 0,
            "dmesg_incidentes": [],
            "reinicios": [],
            "reinicios_backup": [],
        },
        "conectividad": {
            "datos_movil_rx": None,
            "datos_movil_tx": None,
            "radio_activa_tiempo": None,
            "radio_activa_pct": None,
            "tiempo_5g": None,
            "cambios_conectividad": None,
            "senal_distribucion": {},
            "operador_actual": None,
            "red_actual": None,
            "rsrp_dbm": None,
            "datos_movil_activos": None,
            "wifi_activo": None,
            "escaneo_siempre_activo": None,
            "wifi_datos_rx": None,
            "wifi_datos_tx": None,
            "wifi_scanning_pct": None,
        },
        "seguridad": {
            "arranque_verificado": None,
            "bootloader_bloqueado": None,
            "knox_intacto": None,
            "cifrado": None,
            "parche_seguridad": None,
            "antiguedad_parche_dias": None,
            "debuggable": None,
            "adb_conectado": None,
            "adb_wifi_activo": None,
        },
    }

    seccion = None
    cabecera_activa = True
    err_tags = Counter()
    mapa_uid_paquetes = {}

    # Estados auxiliares por sección
    mem_sub = None
    bstats_visto = False
    bstats_en_principal = False
    bstats_sub = None
    bstats_power_sub = None
    bstats_conn_sub = None
    disk_arrays = {}
    therm_sub = None
    telephony_sims = []
    telephony_actual = None

    # Estados de captura de crashes en logcat
    java_crash_activo = None
    debug_crash_activo = None
    libc_signals_por_pid = {}
    anr_pendiente = None

    for linea in lineas:
        if cabecera_activa and not linea.startswith("------ "):
            if linea.startswith("== dumpstate:"):
                datos["dispositivo"]["fecha_informe"] = linea.split(":", 1)[1].strip()
            elif linea.startswith("Build:"):
                datos["dispositivo"]["compilacion"] = linea.split(":", 1)[1].strip()
            elif linea.startswith("Network:"):
                datos["dispositivo"]["operador"] = linea.split(":", 1)[1].strip()
            elif linea.startswith("Bootconfig:"):
                cabecera_activa = False
            continue

        nueva = _detectar_seccion(linea)
        if nueva != "__keep__":
            cabecera_activa = False
            if java_crash_activo:
                datos["estabilidad"]["crashes_java"].append(java_crash_activo)
                java_crash_activo = None
            if debug_crash_activo:
                datos["estabilidad"]["crashes_nativos"].append(debug_crash_activo)
                debug_crash_activo = None
            seccion = nueva
            mem_sub = None
            bstats_sub = None
            bstats_power_sub = None
            bstats_conn_sub = None
            therm_sub = None
            if seccion == "svc_batterystats" and not bstats_visto:
                bstats_visto = True
                bstats_en_principal = False
            elif seccion != "svc_batterystats":
                bstats_en_principal = False
            continue

        if not seccion or seccion == "__other_service__":
            continue

        s = linea.strip()

        # 1. PROPIEDADES DEL SISTEMA
        if seccion == "getprop":
            if s.startswith("[") and "]: [" in s:
                clave, valor = s[1:-1].split("]: [", 1)
                disp = datos["dispositivo"]
                seg = datos["seguridad"]
                if clave == "ro.product.manufacturer":
                    disp["fabricante"] = valor
                elif clave == "ro.product.model":
                    disp["modelo"] = valor
                elif clave == "ro.product.marketname" and valor:
                    disp["nombre_comercial"] = valor
                elif clave == "ro.soc.model":
                    disp["soc"] = valor
                elif clave == "ro.hardware":
                    disp["hardware"] = valor
                elif clave == "ro.build.version.release":
                    disp["android"] = valor
                elif clave == "ro.build.version.sdk":
                    disp["sdk"] = valor
                elif clave == "ro.build.version.oneui":
                    disp["oneui"] = _formatear_oneui(valor)
                elif clave == "ro.build.display.id":
                    disp["compilacion"] = valor
                elif clave == "ro.build.version.security_patch":
                    disp["parche_seguridad"] = valor
                    seg["parche_seguridad"] = valor
                elif clave == "gsm.operator.alpha" and valor:
                    disp["operador"] = valor
                elif clave == "persist.sys.timezone":
                    disp["zona_horaria"] = valor
                elif clave == "ro.boot.verifiedbootstate":
                    seg["arranque_verificado"] = valor
                elif clave == "ro.boot.flash.locked":
                    seg["bootloader_bloqueado"] = valor == "1"
                elif clave == "ro.boot.warranty_bit":
                    seg["knox_intacto"] = valor == "0"
                elif clave == "ro.crypto.state":
                    seg["cifrado"] = valor == "encrypted"
                elif clave == "ro.debuggable":
                    seg["debuggable"] = valor == "1"
            continue

        if seccion == "uptime" and s:
            m_up = re.search(r"\bup\s+(.+?),\s+\d+\s+users?,\s+load average:\s+(.+)$", s)
            if m_up:
                datos["dispositivo"]["uptime_texto"] = m_up.group(1).strip()
                datos["dispositivo"]["load_avg"] = m_up.group(2).strip()
            continue

        if seccion == "boot_stat":
            if "!@Boot: bootcomplete" in s:
                partes = s.split()
                for idx, tok in enumerate(partes):
                    if tok == "bootcomplete" and idx + 1 < len(partes) and partes[idx + 1].isdigit():
                        datos["dispositivo"]["tiempo_arranque_ms"] = int(partes[idx + 1])
                        break
            continue

        if seccion == "checkin_package":
            if s.startswith("pkg,"):
                datos["dispositivo"]["total_paquetes"] += 1
            continue

        if seccion == "checkin_batterystats":
            if ",i,uid," in s:
                partes = s.split(",", 5)
                if len(partes) >= 6 and re.fullmatch(r"-?\d+", partes[4]):
                    uid_num = int(partes[4])
                    mapa_uid_paquetes.setdefault(uid_num, [])
                    if partes[5] not in mapa_uid_paquetes[uid_num]:
                        mapa_uid_paquetes[uid_num].append(partes[5])
            continue

        # 2. MEMORIA
        if seccion == "meminfo_proc":
            mem = datos["memoria"]
            if s.startswith("MemTotal:"):
                mem["total_kb"] = int(s.split()[1])
            elif s.startswith("MemFree:"):
                mem["libre_kb"] = int(s.split()[1])
            elif s.startswith("MemAvailable:"):
                mem["disponible_kb"] = int(s.split()[1])
            elif s.startswith("Cached:"):
                mem["cached_kb"] = int(s.split()[1])
            elif s.startswith("SwapTotal:"):
                mem["swap_total_kb"] = int(s.split()[1])
            elif s.startswith("SwapFree:"):
                mem["swap_libre_kb"] = int(s.split()[1])
            continue

        if seccion == "svc_meminfo":
            mem = datos["memoria"]
            if s == "Total PSS by process:":
                mem_sub = "pss"
            elif s.startswith("Total PSS by "):
                mem_sub = None
            elif mem_sub == "pss":
                if not s:
                    mem_sub = None
                else:
                    m_pss = re.match(
                        r"^([\d,]+)K:\s+(.+?)\s+\(pid\s+(\d+)(?:\s*/[^)]*)?\)(?:\s*\(\s*([\d,]+)K in swap\))?",
                        s,
                    )
                    if m_pss and len(mem["top_procesos"]) < 15:
                        mem["top_procesos"].append(
                            {
                                "nombre": m_pss.group(2).strip(),
                                "etiqueta": nombre_amigable(m_pss.group(2).strip()),
                                "pid": int(m_pss.group(3)),
                                "pss_kb": _int_limpio(m_pss.group(1)),
                                "swap_kb": _int_limpio(m_pss.group(4)) if m_pss.group(4) else 0,
                            }
                        )
            elif s.startswith("Total RAM:"):
                m_ram = re.match(r"Total RAM:\s+([\d,]+)K\s+\(status\s+(\w+)\)", s)
                if m_ram:
                    mem["estado_ram"] = m_ram.group(2)
            elif s.startswith("Free RAM:"):
                m = re.match(r"Free RAM:\s+([\d,]+)K", s)
                if m:
                    mem["ram_libre_android_kb"] = _int_limpio(m.group(1))
            elif s.startswith("Used RAM:"):
                m = re.match(r"Used RAM:\s+([\d,]+)K", s)
                if m:
                    mem["ram_usada_kb"] = _int_limpio(m.group(1))
            elif s.startswith("Lost RAM:"):
                m = re.match(r"Lost RAM:\s+([\d,]+)K", s)
                if m:
                    mem["ram_perdida_kb"] = _int_limpio(m.group(1))
            elif s.startswith("ZRAM:"):
                m = re.match(
                    r"ZRAM:\s+([\d,]+)K physical used for\s+([\d,]+)K in swap \(([\d,]+)K total swap\)",
                    s,
                )
                if m:
                    mem["zram_fisica_kb"] = _int_limpio(m.group(1))
                    mem["zram_swap_kb"] = _int_limpio(m.group(2))
                    mem["zram_total_kb"] = _int_limpio(m.group(3))
            continue

        if seccion == "psi_memory":
            _parsear_psi(s, datos["memoria"]["psi"])
            continue
        if seccion == "psi_cpu":
            _parsear_psi(s, datos["rendimiento_termico"]["psi_cpu"])
            continue
        if seccion == "psi_io":
            _parsear_psi(s, datos["rendimiento_termico"]["psi_io"])
            continue

        # 3. ALMACENAMIENTO Y UFS
        if seccion == "df":
            partes = s.split()
            if len(partes) >= 6 and partes[5] == "/data":
                alm = datos["almacenamiento"]
                alm["data_total_kb"] = int(partes[1])
                alm["data_usado_kb"] = int(partes[2])
                alm["data_libre_kb"] = int(partes[3])
                alm["data_uso_pct"] = int(partes[4].rstrip("%"))
            continue

        if seccion == "svc_diskstats":
            alm = datos["almacenamiento"]
            if s.startswith("Latency:"):
                m = re.search(r"(\d+)\s*ms", s)
                if m:
                    alm["latencia_ms"] = int(m.group(1))
            elif s.startswith("Recent Disk Write Speed"):
                m = re.search(r"=\s*(\d+)", s)
                if m:
                    alm["velocidad_escritura_kbs"] = int(m.group(1))
            elif s.startswith("File-based Encryption:"):
                alm["cifrado_archivos"] = s.split(":", 1)[1].strip().lower() == "true"
            elif s.startswith(
                (
                    "App Size:",
                    "App Data Size:",
                    "App Cache Size:",
                    "Photos Size:",
                    "Videos Size:",
                    "Audio Size:",
                    "Downloads Size:",
                    "System Size:",
                    "Other Size:",
                )
            ):
                k, v = s.split(":", 1)
                if v.strip().isdigit():
                    alm["categorias_bytes"][k.strip()] = int(v.strip())
            elif s.startswith(("Package Names:", "App Sizes:", "App Data Sizes:", "Cache Sizes:")):
                k, v = s.split(":", 1)
                try:
                    disk_arrays[k.strip()] = json.loads(v.strip())
                except json.JSONDecodeError:
                    pass
                if len(disk_arrays) == 4:
                    nombres = disk_arrays.get("Package Names", [])
                    apps_sz = disk_arrays.get("App Sizes", [])
                    data_sz = disk_arrays.get("App Data Sizes", [])
                    cache_sz = disk_arrays.get("Cache Sizes", [])
                    n = min(len(nombres), len(apps_sz), len(data_sz), len(cache_sz))
                    combinado = []
                    for idx in range(n):
                        total = apps_sz[idx] + data_sz[idx] + cache_sz[idx]
                        combinado.append(
                            {
                                "paquete": nombres[idx],
                                "etiqueta": nombre_amigable(nombres[idx]),
                                "app_bytes": apps_sz[idx],
                                "datos_bytes": data_sz[idx],
                                "cache_bytes": cache_sz[idx],
                                "total_bytes": total,
                            }
                        )
                    alm["top_apps"] = sorted(
                        combinado, key=lambda x: x["total_bytes"], reverse=True
                    )[:12]
                    alm["top_cache"] = sorted(
                        combinado, key=lambda x: x["cache_bytes"], reverse=True
                    )[:5]
            continue

        if seccion == "ufs_model" and s:
            datos["almacenamiento"]["ufs_modelo"] = s
            continue
        if seccion == "ufs_vendor" and s:
            datos["almacenamiento"]["ufs_fabricante"] = s
            continue
        if seccion == "ufs_lt" and s.isdigit():
            datos["almacenamiento"]["ufs_vida_util"] = int(s)
            continue
        if seccion == "ufs_err" and ":" in s:
            for k, v in re.findall(r"([A-Z]+)\s*:\s*(\d+)", s):
                datos["almacenamiento"]["ufs_errores"][k] = int(v)
            continue

        # 4. BATERÍA Y CONSUMO
        if seccion == "svc_battery":
            bat = datos["bateria"]
            if s.startswith("AC powered: true"):
                bat["fuente"] = "Cargador de pared (AC)"
            elif s.startswith("USB powered: true"):
                bat["fuente"] = "USB"
            elif s.startswith("Wireless powered: true"):
                bat["fuente"] = "Inalámbrica"
            elif s.startswith("status:"):
                bat["estado_codigo"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("health:"):
                bat["salud_codigo"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("level:"):
                bat["nivel"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("voltage:"):
                bat["voltaje_mv"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("temperature:"):
                bat["temperatura_c"] = int(s.split(":", 1)[1].strip()) / 10.0
            elif s.startswith("technology:"):
                bat["tecnologia"] = s.split(":", 1)[1].strip()
            elif s.startswith("current now:"):
                bat["corriente_ma"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("Adaptive Fast Charging Settings:"):
                bat["carga_rapida"] = s.split(":", 1)[1].strip().lower() == "true"
            elif s.startswith("Super Fast Charging Settings:"):
                bat["carga_super_rapida"] = s.split(":", 1)[1].strip().lower() == "true"
            elif s.startswith("mProtectBatteryMode:"):
                bat["proteccion_modo"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("mProtectionThreshold:"):
                bat["proteccion_limite"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("battery FirstUseDate:"):
                m = re.search(r"\[(\d{4})(\d{2})(\d{2})\]", s)
                if m:
                    bat["primer_uso"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            elif s.startswith("mSavedBatteryAsoc:"):
                m = re.search(r"\[(\d+)\]", s)
                if m:
                    bat["salud_asoc_pct"] = int(m.group(1))
            elif s.startswith("mSavedBatteryUsage:"):
                m = re.search(r"\[(\d+)\]", s)
                if m:
                    bat["ciclos"] = round(int(m.group(1)) / 100.0, 1)
            continue

        if seccion == "svc_ihealth":
            bat = datos["bateria"]
            if s.startswith("Full charge:") and bat["capacidad_diseno_mah"] is None:
                val = int(s.split(":", 1)[1].strip())
                bat["capacidad_diseno_mah"] = round(val / 1000)
            elif "batteryCycleCount:" in s and bat["ciclos"] is None:
                m = re.search(r"batteryCycleCount:\s*(\d+)", s)
                if m and int(m.group(1)) > 0:
                    bat["ciclos"] = int(m.group(1))
            continue

        if seccion == "svc_batterystats":
            bat = datos["bateria"]
            conn = datos["conectividad"]
            if s == "Statistics since last charge:":
                bstats_en_principal = True
                continue
            if not bstats_en_principal:
                continue

            if s.startswith("Estimated battery capacity:"):
                m = re.search(r"(\d+)\s*mAh", s)
                if m:
                    bat["capacidad_diseno_mah"] = int(m.group(1))
            elif s.startswith("Time on battery:") and not s.startswith("Time on battery screen"):
                m = re.match(r"Time on battery:\s+(.+?)\s*\(", s)
                if m:
                    bat["tiempo_en_bateria"] = limpiar_duracion(m.group(1))
            elif s.startswith("Time on battery screen off:"):
                m = re.match(r"Time on battery screen off:\s+(.+?)\s*\(", s)
                if m:
                    bat["tiempo_pantalla_off"] = limpiar_duracion(m.group(1))
            elif s.startswith("Screen on:"):
                m = re.match(r"Screen on:\s+(.+?)\s*\(([\d.]+)%\)", s)
                if m:
                    bat["pantalla_encendida"] = limpiar_duracion(m.group(1))
                    bat["pantalla_encendida_pct"] = float(m.group(2))
            elif s.startswith("Discharge:"):
                m = re.search(r"([\d.]+)\s*mAh", s)
                if m:
                    bat["descarga_mah"] = float(m.group(1))
            elif s.startswith("Screen on discharge:"):
                m = re.search(r"([\d.]+)\s*mAh", s)
                if m:
                    bat["descarga_pantalla_on_mah"] = float(m.group(1))
            elif s.startswith("Screen off discharge:"):
                m = re.search(r"([\d.]+)\s*mAh", s)
                if m:
                    bat["descarga_pantalla_off_mah"] = float(m.group(1))
            elif s.startswith("Charge time remaining:"):
                bat["tiempo_carga_restante"] = limpiar_duracion(s.split(":", 1)[1].strip())
            elif s.startswith("Connectivity changes:"):
                conn["cambios_conectividad"] = int(s.split(":", 1)[1].strip())
            elif s.startswith("Mobile active time:"):
                conn["radio_activa_tiempo"] = limpiar_duracion(s.split(":", 1)[1].strip())
            elif s.startswith("Mobile active 5G time:"):
                conn["tiempo_5g"] = limpiar_duracion(s.split(":", 1)[1].strip())
            elif s == "Screen brightnesses:":
                bstats_sub = "brightness"
                continue
            elif s == "Screen refresh rate:":
                bstats_sub = "refresh"
                continue
            elif s == "CONNECTIVITY POWER SUMMARY START":
                bstats_sub = "connectivity"
                bstats_conn_sub = None
                continue
            elif s == "Estimated power use (mAh):":
                bstats_sub = "power_use"
                bstats_power_sub = None
                continue
            elif s == "All partial wake locks:":
                bstats_sub = "wakelocks"
                continue

            if bstats_sub == "brightness":
                m = re.match(r"^(dark|dim|medium|light|bright)\s+.*?\(([\d.]+)%\)", s)
                if m:
                    bat["brillo"][m.group(1)] = float(m.group(2))
                elif s and not s.startswith(("dark", "dim", "medium", "light", "bright")):
                    bstats_sub = None
            elif bstats_sub == "refresh":
                m = re.match(r"^(low|high)\s+(.+)$", s)
                if m:
                    bat["refresco"][m.group(1)] = limpiar_duracion(m.group(2))
                elif s:
                    bstats_sub = None
            elif bstats_sub == "connectivity":
                if s.startswith("Cellular kernel active time:"):
                    m = re.search(r"\(([\d.]+)%\)", s)
                    if m:
                        conn["radio_activa_pct"] = float(m.group(1))
                elif s.startswith("Cellular data received:"):
                    conn["datos_movil_rx"] = s.split(":", 1)[1].strip()
                elif s.startswith("Cellular data sent:"):
                    conn["datos_movil_tx"] = s.split(":", 1)[1].strip()
                elif s.startswith("Cellular Rx signal strength"):
                    bstats_conn_sub = "rsrp"
                elif s.startswith("Wifi Statistics:"):
                    bstats_conn_sub = "wifi"
                elif s.startswith("Wifi data received:"):
                    conn["wifi_datos_rx"] = s.split(":", 1)[1].strip()
                elif s.startswith("Wifi data sent:"):
                    conn["wifi_datos_tx"] = s.split(":", 1)[1].strip()
                elif s.startswith("Wifi states:"):
                    bstats_conn_sub = "wifi_states"
                elif bstats_conn_sub == "rsrp":
                    m = re.match(r"^(very poor|poor|moderate|good|great)\s+.*?\(([\d.]+)%\)", s)
                    if m:
                        conn["senal_distribucion"][m.group(1)] = float(m.group(2))
                    else:
                        bstats_conn_sub = None
                elif bstats_conn_sub == "wifi_states":
                    if s.startswith("scanning "):
                        m = re.search(r"\(([\d.]+)%\)", s)
                        if m:
                            conn["wifi_scanning_pct"] = float(m.group(1))
                    elif s:
                        bstats_conn_sub = None
                if not s and bstats_conn_sub == "wifi":
                    bstats_conn_sub = None
            elif bstats_sub == "power_use":
                if s == "Global":
                    bstats_power_sub = "global"
                elif bstats_power_sub == "global" and s.startswith("("):
                    bstats_power_sub = "global_detail"
                elif bstats_power_sub == "global":
                    m = re.match(r"^([a-z_]+):\s+([\d.]+)", s)
                    if m:
                        bat["consumo_componentes"][m.group(1)] = float(m.group(2))
                elif s.startswith("UID "):
                    bstats_power_sub = "uids"
                    m_uid = re.match(r"^UID\s+([^:]+):\s+([\d.]+)(.*)$", s)
                    if m_uid:
                        resto = m_uid.group(3)
                        fg_t = re.search(r"\bfg:\s+[\d.]+\s+\(([^)]+)\)", resto)
                        fgs_t = re.search(r"\bfgs:\s+[\d.]+\s+\(([^)]+)\)", resto)
                        bat["consumo_apps"].append(
                            {
                                "uid": m_uid.group(1),
                                "mah": float(m_uid.group(2)),
                                "tiempo_fg": limpiar_duracion(fg_t.group(1)) if fg_t else None,
                                "tiempo_fgs": limpiar_duracion(fgs_t.group(1)) if fgs_t else None,
                            }
                        )
                elif not s and bstats_power_sub == "uids":
                    bstats_sub = None
                    bstats_power_sub = None
            elif bstats_sub == "wakelocks":
                if not s:
                    bstats_sub = None
                    bstats_en_principal = False
                else:
                    m_wl = re.match(
                        r"^Wake lock\s+(\S+)\s+(.+?):\s+(\d+\s*(?:d|h|m|s|ms)\b[^\(]*?)\s+\((\d+)\s+times\)",
                        s,
                    )
                    if m_wl:
                        dur_limpia = limpiar_duracion(m_wl.group(3))
                        bat["wakelocks"].append(
                            {
                                "uid": m_wl.group(1),
                                "nombre": m_wl.group(2).strip(),
                                "duracion": dur_limpia,
                                "segundos": duracion_a_segundos(m_wl.group(3)),
                                "veces": int(m_wl.group(4)),
                            }
                        )
            continue

        # 5. RENDIMIENTO Y TEMPERATURA
        if seccion == "svc_cpuinfo":
            rt = datos["rendimiento_termico"]
            if s.startswith("Load:"):
                rt["cpu_load"] = s.split(":", 1)[1].strip()
            else:
                m_cpu = re.match(
                    r"^([\d.]+)%\s+(\d+)/([^:]+):\s+([\d.]+)%\s+user\s+\+\s+([\d.]+)%\s+kernel",
                    s,
                )
                if m_cpu and len(rt["top_cpu"]) < 10:
                    rt["top_cpu"].append(
                        {
                            "pct": float(m_cpu.group(1)),
                            "pid": int(m_cpu.group(2)),
                            "nombre": m_cpu.group(3).strip(),
                            "user_pct": float(m_cpu.group(4)),
                            "kernel_pct": float(m_cpu.group(5)),
                        }
                    )
            continue

        if seccion == "svc_thermalservice":
            rt = datos["rendimiento_termico"]
            if s.startswith("Thermal Status:"):
                rt["estado_termico"] = int(s.split(":", 1)[1].strip())
            elif s == "Cached temperatures:":
                therm_sub = "cached"
            elif s == "Current temperatures from HAL:":
                therm_sub = "hal"
            elif s == "Temperature static thresholds from HAL:":
                therm_sub = "thresholds"
            elif s.startswith("Current cooling devices") or s.startswith("Temperature headroom"):
                therm_sub = None
            elif therm_sub in ("cached", "hal") and s.startswith("Temperature{"):
                m_t = re.search(r"mValue=([-\d.]+),\s*mType=\d+,\s*mName=([^,}]+),\s*mStatus=(\d+)", s)
                if m_t:
                    destino = rt["sensores"] if therm_sub == "hal" else rt["sensores_cache"]
                    destino.append(
                        {
                            "nombre": m_t.group(2).strip(),
                            "valor_c": float(m_t.group(1)),
                            "estado": int(m_t.group(3)),
                        }
                    )
            elif therm_sub == "thresholds" and "mName=SKIN" in s:
                m_th = re.search(r"mHotThrottlingThresholds=\[([^\]]+)\]", s)
                if m_th:
                    rt["umbrales_skin"] = [x.strip() for x in m_th.group(1).split(",")]
            continue

        if seccion == "thermal_dump":
            if "Start lmh" in s:
                datos["rendimiento_termico"]["eventos_lmh"] += 1
            continue

        # 6. CONECTIVIDAD Y SEGURIDAD
        if seccion == "svc_wifi":
            conn = datos["conectividad"]
            if s == "Wi-Fi is disabled":
                conn["wifi_activo"] = False
            elif s == "Wi-Fi is enabled":
                conn["wifi_activo"] = True
            elif s.startswith("ScanAlwaysAvailable "):
                conn["escaneo_siempre_activo"] = s.split()[1].lower() == "true"
            continue

        if seccion == "svc_telephony":
            if s.startswith("Phone Id="):
                telephony_actual = {"id": s.split("=", 1)[1].strip(), "en_servicio": False}
                telephony_sims.append(telephony_actual)
            elif telephony_actual is not None:
                if "mVoiceRegState=0(IN_SERVICE)" in s or "mDataRegState=0(IN_SERVICE)" in s:
                    telephony_actual["en_servicio"] = True
                if "mOperatorAlphaLong=" in s:
                    m_op = re.search(r"mOperatorAlphaLong=([^,}]+)", s)
                    if m_op and m_op.group(1).strip():
                        telephony_actual["operador"] = m_op.group(1).strip()
                if s.startswith("mSignalStrength="):
                    m_rsrp = re.search(r"\b(?:rsrp|ssRsrp)=(-\d+)", s)
                    if m_rsrp:
                        telephony_actual["rsrp_dbm"] = int(m_rsrp.group(1))
                elif s.startswith("mTelephonyDisplayInfo="):
                    m_net = re.search(r"network=([^,\s}]+),\s*overrideNetwork=([^,\s}]+)", s)
                    if m_net:
                        net = m_net.group(1)
                        ovr = m_net.group(2)
                        telephony_actual["red"] = ovr if ovr not in ("NONE", "null") else net
                elif s.startswith("mIsDataEnabled="):
                    telephony_actual["datos_activos"] = s.split("=", 1)[1].strip().lower() == "true"
            continue

        if seccion == "svc_adb":
            if "connected_to_adb=" in s:
                datos["seguridad"]["adb_conectado"] = s.split("=", 1)[1].strip().lower() == "true"
            elif s.startswith("enabled=") and datos["seguridad"]["adb_wifi_activo"] is None:
                datos["seguridad"]["adb_wifi_activo"] = s.split("=", 1)[1].strip().lower() == "true"
            continue

        # 7. ESTABILIDAD (LOGS, CRASHES, REINICIOS)
        if seccion == "system_log":
            if len(linea) > 35 and linea[2] == "-" and linea[5] == " ":
                m_log = LOGCAT_RE.match(linea.rstrip("\r\n"))
                if m_log:
                    ts, uid, pid_s, tid_s, nivel, tag, msg = m_log.groups()
                    pid = int(pid_s)
                    tid = int(tid_s)
                    tag = tag.strip()

                    if tag == "Watchdog" and msg.startswith("!@Sync:"):
                        datos["estabilidad"]["watchdog_sync_latidos"] += 1
                        continue

                    if nivel in ("W", "E", "F"):
                        datos["estabilidad"]["logcat_conteo"][nivel] += 1
                    if nivel in ("E", "F"):
                        err_tags[tag] += 1

                    # Crash Java
                    if java_crash_activo:
                        if (
                            tag == "AndroidRuntime"
                            and nivel == "E"
                            and pid == java_crash_activo["pid"]
                            and tid == java_crash_activo["tid"]
                            and not msg.startswith("FATAL EXCEPTION:")
                        ):
                            if msg.startswith("Process: "):
                                m_proc = re.match(r"Process:\s+([^,]+),\s*PID:\s*(\d+)", msg)
                                if m_proc:
                                    proc_pkg = m_proc.group(1).strip()
                                    java_crash_activo["proceso"] = proc_pkg
                                    java_crash_activo["etiqueta"] = nombre_amigable(proc_pkg)
                            elif java_crash_activo["excepcion"] is None:
                                java_crash_activo["excepcion"] = msg.strip()
                            elif len(java_crash_activo["traza"]) < 8:
                                java_crash_activo["traza"].append(msg.strip())
                            continue
                        else:
                            datos["estabilidad"]["crashes_java"].append(java_crash_activo)
                            java_crash_activo = None

                    if nivel == "E" and tag == "AndroidRuntime" and "FATAL EXCEPTION:" in msg:
                        java_crash_activo = {
                            "fecha": ts,
                            "pid": pid,
                            "tid": tid,
                            "hilo": msg.split("FATAL EXCEPTION:", 1)[1].strip(),
                            "proceso": None,
                            "excepcion": None,
                            "traza": [],
                        }
                        continue

                    # Crash nativo (F DEBUG y F libc)
                    if nivel == "F" and tag == "libc" and "Fatal signal" in msg:
                        m_pid = re.search(r"\bpid\s+(\d+)\s+\(([^)]+)\)", msg)
                        crashed_pid = int(m_pid.group(1)) if m_pid else pid
                        libc_signals_por_pid[crashed_pid] = {
                            "fecha": ts,
                            "pid": crashed_pid,
                            "senal": msg.strip(),
                            "proceso": m_pid.group(2) if m_pid else None,
                        }
                        continue

                    if debug_crash_activo:
                        if tag == "DEBUG" and nivel == "F" and pid == debug_crash_activo["debug_pid"] and "*** *** ***" not in msg:
                            if msg.startswith("Executable:"):
                                debug_crash_activo["ejecutable"] = msg.split(":", 1)[1].strip()
                            elif msg.startswith("pid:"):
                                m_info = re.search(r"pid:\s+(\d+).*?name:\s+(\S+)", msg)
                                if m_info:
                                    debug_crash_activo["crashed_pid"] = int(m_info.group(1))
                                    debug_crash_activo["hilo"] = m_info.group(2)
                                if ">>>" in msg and "<<<" in msg:
                                    debug_crash_activo["proceso"] = msg.split(">>>", 1)[1].split("<<<", 1)[0].strip()
                            elif msg.startswith("signal "):
                                debug_crash_activo["senal"] = msg.strip()
                            elif msg.strip().startswith("#0") and len(debug_crash_activo["traza"]) < 5:
                                debug_crash_activo["traza"].append(msg.strip())
                            continue
                        else:
                            datos["estabilidad"]["crashes_nativos"].append(debug_crash_activo)
                            debug_crash_activo = None

                    if nivel == "F" and tag == "DEBUG" and "*** *** ***" in msg:
                        debug_crash_activo = {
                            "fecha": ts,
                            "debug_pid": pid,
                            "crashed_pid": None,
                            "proceso": None,
                            "ejecutable": None,
                            "hilo": None,
                            "senal": None,
                            "traza": [],
                        }
                        continue

                    # ANR en logcat
                    if tag == "ActivityManager" and msg.startswith("ANR in "):
                        anr_pendiente = {"fecha": ts, "proceso": msg[7:].strip(), "razon": None}
                        datos["estabilidad"]["anrs_logcat"].append(anr_pendiente)
                    elif anr_pendiente and tag == "ActivityManager" and msg.startswith("Reason: "):
                        anr_pendiente["razon"] = msg[8:].strip()
                        anr_pendiente = None
            continue

        if seccion == "anr_files":
            if s and not s.startswith("total "):
                datos["estabilidad"]["anr_archivos"].append(s)
            continue

        if seccion in ("dropbox_sys_crash", "dropbox_app_crash", "dropbox_wd_crash"):
            clave = {
                "dropbox_sys_crash": "system_server",
                "dropbox_app_crash": "system_app",
                "dropbox_wd_crash": "watchdog",
            }[seccion]
            if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+", s):
                datos["estabilidad"]["dropbox_crashes"][clave] += 1
            continue

        if seccion == "svc_dropbox":
            m_db = re.match(r"^Drop box contents:\s+(\d+)\s+entries", s)
            if m_db:
                datos["estabilidad"]["dropbox_total_entradas"] = int(m_db.group(1))
            continue

        if seccion == "dmesg":
            low = s.lower()
            if any(
                k in low
                for k in (
                    "kernel panic",
                    "unable to handle kernel",
                    "oom-killer",
                    "out of memory:",
                    "i/o error",
                    "blk_update_request",
                    "hung_task",
                    "rcu_sched self-detected stall",
                )
            ):
                if len(datos["estabilidad"]["dmesg_incidentes"]) < 20:
                    datos["estabilidad"]["dmesg_incidentes"].append(s[:160])
            continue

        if seccion in ("ap_reset", "reset_reason"):
            if "|" in s:
                partes = [p.strip() for p in s.split("|")]
                if len(partes) >= 4 and partes[1] in ("REBOOT", "SHUTDOWN"):
                    motivo = partes[3]
                    if motivo.startswith("REASON:"):
                        motivo = motivo[7:].strip()
                    registro = {
                        "fecha": partes[0],
                        "tipo": partes[1],
                        "motivo": motivo,
                        "categoria": _clasificar_motivo_reinicio(motivo),
                    }
                    destino = (
                        datos["estabilidad"]["reinicios"]
                        if seccion == "ap_reset"
                        else datos["estabilidad"]["reinicios_backup"]
                    )
                    destino.append(registro)
            continue

    # Cierre de capturas abiertas al fin de archivo
    if java_crash_activo:
        datos["estabilidad"]["crashes_java"].append(java_crash_activo)
    if debug_crash_activo:
        datos["estabilidad"]["crashes_nativos"].append(debug_crash_activo)

    # Deduplicar señales libc contra bloques F DEBUG completos
    pids_con_debug = {
        c["crashed_pid"] for c in datos["estabilidad"]["crashes_nativos"] if c.get("crashed_pid")
    }
    for c_pid, info in libc_signals_por_pid.items():
        if c_pid not in pids_con_debug:
            datos["estabilidad"]["crashes_nativos"].append(
                {
                    "fecha": info["fecha"],
                    "debug_pid": None,
                    "crashed_pid": c_pid,
                    "proceso": info["proceso"],
                    "ejecutable": info["proceso"],
                    "hilo": None,
                    "senal": info["senal"],
                    "traza": [],
                }
            )

    if not datos["estabilidad"]["reinicios"] and datos["estabilidad"]["reinicios_backup"]:
        datos["estabilidad"]["reinicios"] = datos["estabilidad"]["reinicios_backup"]

    # Consolidar telefonía (elegir SIM en servicio, o la primera)
    if telephony_sims:
        elegida = next((sim for sim in telephony_sims if sim.get("en_servicio")), telephony_sims[0])
        datos["conectividad"]["operador_actual"] = elegida.get("operador")
        datos["conectividad"]["red_actual"] = elegida.get("red")
        datos["conectividad"]["rsrp_dbm"] = elegida.get("rsrp_dbm")
        datos["conectividad"]["datos_movil_activos"] = elegida.get("datos_activos")

    # Sensores térmicos: si HAL estuvo vacío, usar caché
    if not datos["rendimiento_termico"]["sensores"] and datos["rendimiento_termico"]["sensores_cache"]:
        datos["rendimiento_termico"]["sensores"] = datos["rendimiento_termico"]["sensores_cache"]

    # Resolver UIDs de batería y wakelocks usando el mapa de CHECKIN BATTERYSTATS
    for app in datos["bateria"]["consumo_apps"]:
        pkg, etiqueta = resolver_uid(app["uid"], mapa_uid_paquetes)
        app["paquete"] = pkg
        app["etiqueta"] = etiqueta
    datos["bateria"]["consumo_apps"].sort(key=lambda x: x["mah"], reverse=True)
    datos["bateria"]["consumo_apps"] = datos["bateria"]["consumo_apps"][:15]

    for wl in datos["bateria"]["wakelocks"]:
        pkg, etiqueta = resolver_uid(wl["uid"], mapa_uid_paquetes)
        wl["paquete"] = pkg
        wl["etiqueta"] = etiqueta
    datos["bateria"]["wakelocks"].sort(key=lambda x: x["segundos"], reverse=True)
    datos["bateria"]["wakelocks"] = datos["bateria"]["wakelocks"][:10]

    # Antigüedad del parche de seguridad
    if datos["dispositivo"]["fecha_informe"] and datos["seguridad"]["parche_seguridad"]:
        try:
            f_inf = datetime.strptime(datos["dispositivo"]["fecha_informe"][:10], "%Y-%m-%d").date()
            f_par = datetime.strptime(datos["seguridad"]["parche_seguridad"][:10], "%Y-%m-%d").date()
            datos["seguridad"]["antiguedad_parche_dias"] = max(0, (f_inf - f_par).days)
        except ValueError:
            pass

    datos["bateria"]["estado_texto"] = ESTADO_BATERIA.get(datos["bateria"]["estado_codigo"], "Desconocido")
    datos["bateria"]["salud_texto"] = SALUD_BATERIA.get(datos["bateria"]["salud_codigo"], "Desconocida")
    datos["rendimiento_termico"]["estado_termico_texto"] = ESTADO_TERMICO.get(
        datos["rendimiento_termico"]["estado_termico"], "N/D"
    )
    datos["estabilidad"]["top_tags_error"] = err_tags.most_common(12)
    return datos


def _explicar_crash_java(crash):
    """Traduce un crash Java común a una explicación comprensible."""
    proc = nombre_amigable(crash.get("proceso") or "una aplicación")
    exc = crash.get("excepcion") or ""
    if "credential encrypted storage are not available until after user" in exc:
        return (
            f"La app {proc} se cerró al iniciar",
            f"{proc} intentó abrir su configuración justo después de encender el teléfono y antes de que ingresaras tu PIN/huella.",
            "Es un fallo menor de la propia app tras un reinicio. Si no se repite cuando ya está desbloqueado, no requiere acción.",
        )
    return (
        f"Cierre inesperado en {proc}",
        f"La aplicación {proc} encontró un error interno ({exc[:90] or 'excepción de ejecución'}) y se detuvo.",
        f"Si te ocurre con frecuencia al usar {proc}, actualiza la app en Play Store o borra su caché.",
    )


def _explicar_crash_nativo(crash):
    """Traduce un crash nativo a una explicación comprensible."""
    ej = crash.get("ejecutable") or crash.get("proceso") or "un proceso del sistema"
    if "camera.provider" in ej:
        return (
            "Reinicio puntual del módulo de cámara",
            "El servicio interno encargado de procesar imágenes de la cámara sufrió un cierre puntual en memoria (SIGSEGV).",
            "Android lo reinicia automáticamente al instante. Solo revisa actualizaciones si notas cierres al tomar fotos.",
        )
    return (
        f"Fallo nativo en {Path(ej).name}",
        f"El proceso interno {Path(ej).name} se detuvo de forma inesperada ({crash.get('senal') or 'señal fatal'}).",
        "Si el teléfono se siente inestable o vuelve a ocurrir, busca actualizaciones del sistema.",
    )


def diagnosticar(datos):
    """Evalúa todas las métricas, calcula puntuación /100 y genera hallazgos no técnicos."""
    puntos = 100
    hallazgos = []

    def agregar(sev, cat, titulo, explicacion, recomendacion, detalle=""):
        hallazgos.append(
            {
                "severidad": sev,
                "categoria": cat,
                "titulo": titulo,
                "explicacion": explicacion,
                "recomendacion": recomendacion,
                "detalle_tecnico": detalle,
            }
        )

    # --- 1. Batería ---
    bat = datos["bateria"]
    est = datos["estabilidad"]
    estado_bat = "bueno"
    asoc = bat["salud_asoc_pct"]
    temp_bat = bat["temperatura_c"]
    ciclos = bat["ciclos"]
    apagados_cero = sum(1 for r in est["reinicios"] if r["categoria"] == "sin_bateria")

    if asoc is not None:
        if asoc >= 90:
            agregar(
                "bien",
                "Batería",
                f"Salud física de batería excelente ({asoc}%)",
                "Tu batería conserva prácticamente toda su capacidad original de fábrica.",
                "Mantén hábitos de carga moderada para alargar su vida útil.",
                f"mSavedBatteryAsoc={asoc}%, ciclos={ciclos}",
            )
            estado_bat = "optimo"
        elif asoc >= 80:
            puntos -= 8
            estado_bat = "atencion"
            agregar(
                "atencion",
                "Batería",
                f"Desgaste moderado de batería ({asoc}%)",
                "La batería ha perdido parte de su capacidad original; es normal tras muchos ciclos de uso.",
                "Si notas poca autonomía, activa el ahorro adaptable o evita descargarla por completo.",
                f"mSavedBatteryAsoc={asoc}%",
            )
        else:
            puntos -= 18
            estado_bat = "critico"
            agregar(
                "critico",
                "Batería",
                f"Batería desgastada ({asoc}%)",
                "La capacidad real de la batería bajó del 80%, lo que reduce notablemente las horas de uso.",
                "Conviene evaluar un cambio de batería en servicio técnico oficial.",
                f"mSavedBatteryAsoc={asoc}%",
            )

    if temp_bat is not None and temp_bat > 42.0:
        puntos -= 15
        estado_bat = "critico"
        agregar(
            "critico",
            "Batería",
            f"Batería muy caliente ({temp_bat:.1f} °C)",
            "Una temperatura superior a 42 °C acelera el deterioro de la batería.",
            "Retira el teléfono del cargador o funda gruesa y déjalo reposar sin uso intenso.",
            f"battery.temperature={temp_bat:.1f}°C",
        )
    elif temp_bat is not None and temp_bat > 38.0:
        puntos -= 6
        if estado_bat != "critico":
            estado_bat = "atencion"
        agregar(
            "atencion",
            "Batería",
            f"Temperatura de batería elevada ({temp_bat:.1f} °C)",
            "La batería estaba algo tibia al generar el informe (posiblemente por carga o juego reciente).",
            "Evita exigir juegos pesados mientras está cargando.",
            f"battery.temperature={temp_bat:.1f}°C",
        )

    if bat["proteccion_modo"] == 1 and bat["proteccion_limite"]:
        agregar(
            "bien",
            "Batería",
            f"Protección de carga activa (límite {bat['proteccion_limite']}%)",
            f"Tienes activado el límite de carga al {bat['proteccion_limite']}%, lo que protege la química de la batería.",
            "Excelente configuración; no hace falta cambiarla.",
            f"mProtectBatteryMode={bat['proteccion_modo']}, umbral={bat['proteccion_limite']}%",
        )

    if apagados_cero >= 2:
        puntos -= 3
        if estado_bat == "optimo":
            estado_bat = "bueno"
        agregar(
            "atencion",
            "Batería",
            f"{apagados_cero} apagados por batería agotada al 0%",
            "El historial muestra varias veces en que el teléfono se apagó completamente por quedarse sin energía.",
            "Procura cargarlo antes de llegar al 10–15% para evitar estrés innecesario en la batería.",
            f"Eventos 'no power' registrados: {apagados_cero}",
        )

    resumen_bat = f"Nivel {bat['nivel'] if bat['nivel'] is not None else '?'}%"
    if asoc is not None:
        resumen_bat += f", salud física del {asoc}%"
    if ciclos is not None:
        resumen_bat += f" con ~{ciclos:.0f} ciclos de carga"
    resumen_bat += "."
    if bat["consumo_apps"]:
        top_app = bat["consumo_apps"][0]
        resumen_bat += f" Mayor consumo desde la última carga: {top_app['etiqueta']} ({top_app['mah']:.0f} mAh)."

    # --- 2. Almacenamiento y UFS ---
    alm = datos["almacenamiento"]
    estado_alm = "bueno"
    uso_pct = alm["data_uso_pct"]
    ufs_lt = alm["ufs_vida_util"]
    ufs_err_total = sum(alm["ufs_errores"].values()) if alm["ufs_errores"] else 0

    if uso_pct is not None:
        if uso_pct >= 90:
            puntos -= 20
            estado_alm = "critico"
            agregar(
                "critico",
                "Almacenamiento",
                f"Espacio casi lleno ({uso_pct}% ocupado)",
                "Queda menos del 10% libre, lo que vuelve lento el sistema y bloquea actualizaciones.",
                "Libera espacio borrando videos pesados, descargas antiguas o caché de apps.",
                f"/data {uso_pct}% ({formatear_kb(alm['data_libre_kb'])} libres)",
            )
        elif uso_pct >= 80:
            puntos -= 10
            estado_alm = "atencion"
            agregar(
                "atencion",
                "Almacenamiento",
                f"Espacio acercándose al límite ({uso_pct}% ocupado)",
                "El almacenamiento está bastante ocupado y conviene hacer limpieza pronto.",
                "Revisa videos o archivos duplicados en Galería y Mis Archivos.",
                f"/data {uso_pct}%",
            )
        else:
            estado_alm = "optimo"
            agregar(
                "bien",
                "Almacenamiento",
                f"Espacio holgado ({uso_pct}% usado, {formatear_kb(alm['data_libre_kb'])} libres)",
                "Tienes muchísimo espacio disponible, así que el sistema puede escribir y actualizar sin atascos.",
                "Ninguna acción necesaria.",
                f"/data {formatear_kb(alm['data_usado_kb'])} / {formatear_kb(alm['data_total_kb'])}",
            )

    cache_total = alm["categorias_bytes"].get("App Cache Size", 0)
    if cache_total > 3 * 1024**3:
        puntos -= 2
        top_c = ", ".join(
            f"{nombre_amigable(a['paquete'])} ({formatear_bytes(a['cache_bytes'])})"
            for a in alm["top_cache"][:3]
            if a["cache_bytes"] > 0
        )
        agregar(
            "atencion",
            "Almacenamiento",
            f"Caché acumulada de aplicaciones ({formatear_bytes(cache_total)})",
            "Varias apps acumularon archivos temporales grandes (como miniaturas de redes sociales o videos).",
            f"No es urgente porque tienes espacio libre, pero puedes vaciar caché en: {top_c or 'tus apps principales'}.",
            f"App Cache Size={formatear_bytes(cache_total)}",
        )

    if ufs_err_total > 0:
        puntos -= 15
        estado_alm = "critico"
        agregar(
            "critico",
            "Almacenamiento",
            "Errores de hardware en memoria interna UFS",
            "El chip de almacenamiento reportó fallos de lectura/escritura.",
            "Haz una copia de seguridad de tus fotos y datos importantes de inmediato.",
            str(alm["ufs_errores"]),
        )
    elif ufs_lt is not None and ufs_lt >= 9:
        puntos -= 20
        estado_alm = "critico"
        agregar(
            "critico",
            "Almacenamiento",
            "Chip de almacenamiento cerca del fin de su vida útil",
            "La memoria flash interna acumula un desgaste físico elevado.",
            "Mantén respaldos frecuentes en la nube o PC.",
            f"UFS LT={ufs_lt}",
        )
    elif ufs_lt is not None and ufs_lt >= 6:
        puntos -= 8
        if estado_alm != "critico":
            estado_alm = "atencion"
        agregar(
            "atencion",
            "Almacenamiento",
            "Desgaste intermedio del chip de almacenamiento",
            "La memoria interna muestra uso acumulado medio.",
            "No requiere acción inmediata, solo mantener copias de seguridad periódicas.",
            f"UFS LT={ufs_lt}",
        )

    resumen_alm = (
        f"Usado el {uso_pct}% ({formatear_kb(alm['data_libre_kb'])} libres de {formatear_kb(alm['data_total_kb'])})."
        if uso_pct is not None
        else "Información parcial de espacio."
    )
    if ufs_lt is not None and ufs_err_total == 0:
        resumen_alm += f" El chip UFS está en excelente estado (desgaste < {ufs_lt * 10}%, 0 errores)."

    # --- 3. Memoria RAM ---
    mem = datos["memoria"]
    estado_ram_sec = "bueno"
    psi_mem_full60 = mem["psi"].get("full", {}).get("avg60", 0.0)
    if psi_mem_full60 >= 5.0:
        puntos -= 8
        estado_ram_sec = "atencion"
        agregar(
            "atencion",
            "Memoria RAM",
            "Presión alta de memoria RAM",
            "El sistema tuvo que esperar frecuentemente para liberar RAM entre aplicaciones.",
            "Cierra apps muy pesadas que queden en segundo plano o reinicia el equipo.",
            f"PSI memory full avg60={psi_mem_full60}%",
        )
    elif mem["total_kb"]:
        estado_ram_sec = "optimo"
        agregar(
            "bien",
            "Memoria RAM",
            f"Memoria RAM fluida ({formatear_kb(mem['total_kb'])} totales, presión mínima)",
            "Android mantiene varias apps listas en memoria y apenas sufre esperas al cambiar entre ellas.",
            "No necesitas usar limpiadores de RAM ni cerrar apps manualmente.",
            f"Estado RAM={mem['estado_ram'] or 'normal'}, PSI full avg60={psi_mem_full60}%",
        )

    resumen_ram = (
        f"{formatear_kb(mem['total_kb'])} de RAM total ({formatear_kb(mem['disponible_kb'])} disponibles inmediatamente); "
        f"la compresión ZRAM mantiene datos en espera con presión baja ({psi_mem_full60:.2f}% en 60s)."
        if mem["total_kb"]
        else "Sin datos suficientes de memoria."
    )

    # --- 4. Rendimiento y temperatura ---
    rt = datos["rendimiento_termico"]
    estado_term_sec = "bueno"
    est_term = rt["estado_termico"]
    psi_cpu_60 = rt["psi_cpu"].get("some", {}).get("avg60", 0.0)

    if est_term is not None and est_term >= 3:
        puntos -= 15
        estado_term_sec = "critico"
        agregar(
            "critico",
            "Temperatura",
            "Sobrecalentamiento activo del equipo",
            "El sistema está limitando el rendimiento porque la temperatura alcanzó un nivel alto.",
            "Deja reposar el teléfono, quita la funda y cierra juegos o cámara.",
            f"Thermal Status={est_term}",
        )
    elif est_term in (1, 2):
        puntos -= 6
        estado_term_sec = "atencion"
        agregar(
            "atencion",
            "Temperatura",
            "Equipo ligeramente caliente",
            "El teléfono está algo tibio y podría reducir levemente la velocidad máxima para enfriarse.",
            "Evita exposición directa al sol o carga rápida mientras juegas.",
            f"Thermal Status={est_term}",
        )
    elif est_term == 0:
        estado_term_sec = "optimo"
        sensores_txt = ", ".join(
            f"{s['nombre']}: {s['valor_c']:.1f}°C" for s in rt["sensores"] if s["valor_c"] > 0
        )
        agregar(
            "bien",
            "Temperatura",
            "Temperaturas normales sin limitación térmica",
            "Todos los sensores de procesador, batería y carcasa están en rangos frescos y seguros.",
            "Ninguna acción necesaria.",
            sensores_txt,
        )

    if psi_cpu_60 > 25.0:
        puntos -= 6
        if estado_term_sec != "critico":
            estado_term_sec = "atencion"
        agregar(
            "atencion",
            "Rendimiento",
            "Procesador muy ocupado recientemente",
            "Varias tareas compitieron por el procesador en el último minuto.",
            "Revisa en la tabla de CPU qué app consume más si notas tirones.",
            f"PSI cpu some avg60={psi_cpu_60}%",
        )

    sens_ap = next((s["valor_c"] for s in rt["sensores"] if s["nombre"] == "AP"), None)
    sens_skin = next((s["valor_c"] for s in rt["sensores"] if s["nombre"] == "SKIN"), None)
    resumen_term = f"Estado térmico: {ESTADO_TERMICO.get(est_term, 'Normal')}."
    if sens_ap is not None and sens_skin is not None:
        resumen_term += f" Procesador a {sens_ap:.1f} °C y carcasa a {sens_skin:.1f} °C."

    # --- 5. Estabilidad ---
    estado_est_sec = "optimo"
    reinicios_anormales = [r for r in est["reinicios"] if r["categoria"] == "anormal"]
    dropbox_crit = est["dropbox_crashes"]["system_server"] + est["dropbox_crashes"]["watchdog"]
    total_anr = len(est["anrs_logcat"]) + len(est["anr_archivos"])

    if reinicios_anormales:
        puntos -= 20
        estado_est_sec = "critico"
        agregar(
            "critico",
            "Estabilidad",
            f"{len(reinicios_anormales)} reinicio(s) inesperado(s)",
            "El teléfono se reinició por un fallo interno de sistema o hardware.",
            "Actualiza el software del teléfono y vigila si se repite.",
            "; ".join(f"{r['fecha']} {r['motivo']}" for r in reinicios_anormales[:3]),
        )
    else:
        agregar(
            "bien",
            "Estabilidad",
            "Sin reinicios por fallos de sistema",
            "Todos los reinicios recientes fueron pedidos por ti o por actualizaciones oficiales del sistema.",
            "Ninguna acción necesaria.",
            f"{len(est['reinicios'])} eventos en historial de reinicios",
        )

    if dropbox_crit > 0 or est["dmesg_incidentes"]:
        puntos -= 15
        estado_est_sec = "critico"
        agregar(
            "critico",
            "Estabilidad",
            "Errores graves del núcleo o servidor del sistema",
            "Se detectaron fallos críticos en componentes centrales de Android o el kernel Linux.",
            "Aplica las últimas actualizaciones del sistema y haz respaldo de tus archivos.",
            f"dropbox_crit={dropbox_crit}, dmesg={len(est['dmesg_incidentes'])}",
        )

    if total_anr > 0:
        puntos -= 6
        if estado_est_sec != "critico":
            estado_est_sec = "atencion"
        agregar(
            "atencion",
            "Estabilidad",
            f"{total_anr} bloqueo(s) temporal(es) de pantalla (ANR)",
            "Alguna aplicación dejó de responder momentáneamente.",
            "Actualiza las apps afectadas desde Google Play Store.",
            ", ".join(a["proceso"] for a in est["anrs_logcat"][:3]),
        )

    penal_crash = 0
    for c in est["crashes_java"]:
        titulo, exp, rec = _explicar_crash_java(c)
        penal = min(4, 12 - penal_crash)
        puntos -= penal
        penal_crash += penal
        if estado_est_sec == "optimo":
            estado_est_sec = "atencion"
        agregar("atencion", "Estabilidad", titulo, exp, rec, f"{c.get('fecha')} {c.get('proceso')}: {c.get('excepcion')}")

    for c in est["crashes_nativos"]:
        titulo, exp, rec = _explicar_crash_nativo(c)
        penal = min(4, 12 - penal_crash)
        puntos -= penal
        penal_crash += penal
        if estado_est_sec == "optimo":
            estado_est_sec = "atencion"
        agregar("atencion", "Estabilidad", titulo, exp, rec, f"{c.get('fecha')} {c.get('ejecutable')}: {c.get('senal')}")

    total_crashes = len(est["crashes_java"]) + len(est["crashes_nativos"])
    resumen_est = (
        f"0 reinicios por fallo y 0 bloqueos (ANR). "
        if not reinicios_anormales and total_anr == 0
        else f"{len(reinicios_anormales)} reinicios anormales y {total_anr} bloqueos ANR. "
    )
    if total_crashes == 0:
        resumen_est += "Sin cierres inesperados de apps o servicios."
    else:
        resumen_est += f"Se registraron {total_crashes} cierres puntuales en los logs recientes (ya recuperados)."

    # --- 6. Conectividad ---
    conn = datos["conectividad"]
    estado_conn_sec = "bueno"
    pobre_pct = conn["senal_distribucion"].get("poor", 0.0) + conn["senal_distribucion"].get("very poor", 0.0)

    if conn["wifi_activo"] is False and (
        (conn["wifi_scanning_pct"] or 0.0) >= 80.0 or conn["escaneo_siempre_activo"]
    ):
        puntos -= 3
        estado_conn_sec = "atencion"
        agregar(
            "atencion",
            "Conectividad",
            "Búsqueda de Wi-Fi activa en segundo plano con Wi-Fi apagado",
            "Aunque apagaste el Wi-Fi, el teléfono sigue escaneando redes constantemente para mejorar la ubicación.",
            "Si quieres ahorrar un poco de batería, ve a Ajustes → Ubicación → Servicios de ubicación → Búsqueda de Wi-Fi y desactívalo.",
            f"Wi-Fi apagado, scanning={conn['wifi_scanning_pct'] or 0:.0f}%, ScanAlwaysAvailable={conn['escaneo_siempre_activo']}",
        )

    if (conn["radio_activa_pct"] or 0.0) >= 75.0:
        puntos -= 3
        estado_conn_sec = "atencion"
        agregar(
            "atencion",
            "Conectividad",
            f"Uso intenso de datos móviles ({conn['radio_activa_pct']:.0f}% del tiempo activo)",
            "El módem celular estuvo transmitiendo casi todo el tiempo sin Wi-Fi, lo que consume mucha más batería que una red Wi-Fi.",
            "Usa Wi-Fi cuando estés en casa u oficina para reducir consumo y temperatura.",
            f"Radio activa {conn['radio_activa_pct']:.1f}%, RX {conn['datos_movil_rx']}, TX {conn['datos_movil_tx']}",
        )
    elif pobre_pct > 15.0:
        puntos -= 3
        estado_conn_sec = "atencion"
        agregar(
            "atencion",
            "Conectividad",
            f"Señal móvil débil parte del tiempo ({pobre_pct:.1f}%)",
            "Cuando hay poca cobertura, el teléfono aumenta la potencia de la antena y gasta más batería.",
            "Activa llamadas por Wi-Fi si estás en interiores con poca señal.",
            f"Señal pobre+muy pobre={pobre_pct:.1f}%",
        )
    elif estado_conn_sec == "bueno":
        estado_conn_sec = "optimo"

    buena_pct = conn["senal_distribucion"].get("good", 0.0) + conn["senal_distribucion"].get("great", 0.0)
    resumen_conn = f"Operador {conn['operador_actual'] or datos['dispositivo']['operador'] or 'N/D'}"
    if conn["red_actual"]:
        resumen_conn += f" ({conn['red_actual']})"
    if buena_pct > 0:
        resumen_conn += f", con señal buena/excelente el {buena_pct:.1f}% del tiempo."
    else:
        resumen_conn += "."

    # --- 7. Seguridad ---
    seg = datos["seguridad"]
    estado_seg_sec = "optimo"
    if (
        (seg["arranque_verificado"] and seg["arranque_verificado"] != "green")
        or seg["bootloader_bloqueado"] is False
        or seg["cifrado"] is False
    ):
        puntos -= 15
        estado_seg_sec = "critico"
        agregar(
            "critico",
            "Seguridad",
            "Integridad del sistema modificada o sin cifrado",
            "El arranque verificado, el bloqueo del bootloader o el cifrado no están en estado estándar.",
            "Ten precaución con apps bancarias o de trabajo; revisa si el equipo fue rooteado o desbloqueado.",
            f"verifiedboot={seg['arranque_verificado']}, locked={seg['bootloader_bloqueado']}, encrypted={seg['cifrado']}",
        )
    else:
        agregar(
            "bien",
            "Seguridad",
            "Sistema intacto, cifrado y sin modificaciones",
            "El sistema operativo es oficial, tus datos están cifrados y las protecciones de fábrica (incluyendo Knox) están intactas.",
            "Ninguna acción necesaria.",
            f"verifiedboot={seg['arranque_verificado']}, knox_intacto={seg['knox_intacto']}, cifrado={seg['cifrado']}",
        )

    dias_parche = seg["antiguedad_parche_dias"]
    if dias_parche is not None:
        if dias_parche > 180:
            puntos -= 6
            if estado_seg_sec == "optimo":
                estado_seg_sec = "atencion"
            agregar(
                "atencion",
                "Seguridad",
                f"Parche de seguridad antiguo ({seg['parche_seguridad']})",
                f"Han pasado {dias_parche} días desde la fecha del parche de seguridad.",
                "Busca actualizaciones de software en Ajustes → Actualización de software.",
                f"Parche {seg['parche_seguridad']} ({dias_parche} días)",
            )
        elif dias_parche > 90:
            puntos -= 3
            if estado_seg_sec == "optimo":
                estado_seg_sec = "atencion"
            agregar(
                "atencion",
                "Seguridad",
                f"Parche de seguridad con {dias_parche} días ({seg['parche_seguridad']})",
                "El parche tiene más de tres meses respecto a la fecha del informe.",
                "Comprueba si hay una actualización mensual pendiente.",
                f"Parche {seg['parche_seguridad']}",
            )

    if seg["adb_wifi_activo"]:
        puntos -= 4
        if estado_seg_sec == "optimo":
            estado_seg_sec = "atencion"
        agregar(
            "atencion",
            "Seguridad",
            "Depuración inalámbrica (ADB Wi-Fi) activada",
            "El teléfono permite conexión de desarrollador por Wi-Fi.",
            "Si ya no la usas, desactívala en Opciones de desarrollador.",
            "adb_wifi.enabled=true",
        )

    resumen_seg = (
        f"Parche de seguridad {seg['parche_seguridad'] or 'N/D'}, cifrado de archivos "
        f"{'activo' if seg['cifrado'] else 'inactivo'}, arranque verificado ({seg['arranque_verificado'] or 'N/D'})."
    )

    puntuacion = max(0, min(100, puntos))
    hay_critico = any(h["severidad"] == "critico" for h in hallazgos)
    cant_atencion = sum(1 for h in hallazgos if h["severidad"] == "atencion")

    if hay_critico or puntuacion < 65:
        veredicto = "Requiere revisión"
        nivel_global = "critico"
        frase_global = "Se detectaron puntos críticos que conviene atender pronto."
    elif puntuacion < 85 or cant_atencion >= 2:
        veredicto = "Buen estado con observaciones"
        nivel_global = "atencion"
        frase_global = "El teléfono funciona bien en general, aunque hay algunos detalles que puedes mejorar."
    else:
        veredicto = "Buen estado"
        nivel_global = "bien"
        frase_global = "Tu teléfono está sano, estable y sin problemas graves."

    orden_sev = {"critico": 0, "atencion": 1, "bien": 2}
    hallazgos.sort(key=lambda h: orden_sev[h["severidad"]])

    return {
        "puntuacion": puntuacion,
        "veredicto": veredicto,
        "nivel_global": nivel_global,
        "frase_global": frase_global,
        "hallazgos": hallazgos,
        "secciones": {
            "bateria": {"estado": estado_bat, "resumen": resumen_bat},
            "almacenamiento": {"estado": estado_alm, "resumen": resumen_alm},
            "memoria": {"estado": estado_ram_sec, "resumen": resumen_ram},
            "temperatura": {"estado": estado_term_sec, "resumen": resumen_term},
            "estabilidad": {"estado": estado_est_sec, "resumen": resumen_est},
            "conectividad": {"estado": estado_conn_sec, "resumen": resumen_conn},
            "seguridad": {"estado": estado_seg_sec, "resumen": resumen_seg},
        },
    }


def imprimir_resumen_consola(datos, diag, ruta_html):
    """Imprime un diagnóstico legible y claro en la terminal."""
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

    print("=" * 66)
    print("📱 DIAGNÓSTICO DEL INFORME DE ERRORES")
    print("=" * 66)
    print(f"Equipo:         {disp['fabricante'] or ''} {modelo} ({disp['soc'] or disp['hardware'] or 'N/D'})".strip())
    print(f"Sistema:        {sistema} (parche {disp['parche_seguridad'] or 'N/D'})")
    print(f"Fecha informe:  {disp['fecha_informe'] or 'N/D'}")
    print(f"Encendido hace: {disp['uptime_texto'] or 'N/D'}")
    print("-" * 66)
    print(f"Estado general: {icono_global} {diag['veredicto']} — Puntuación: {diag['puntuacion']}/100")
    print(f"                {diag['frase_global']}")
    print("-" * 66)

    print("\n📊 RESUMEN RÁPIDO:")
    bat_extra = f"salud {bat['salud_asoc_pct']}%" if bat["salud_asoc_pct"] is not None else "salud N/D"
    if bat["ciclos"] is not None:
        bat_extra += f", ~{bat['ciclos']:.0f} ciclos"
    print(f"  🔋 Batería:        {bat['nivel'] if bat['nivel'] is not None else '?'}% ({bat_extra}, {bat['temperatura_c'] or '?'} °C)")
    if alm["data_uso_pct"] is not None:
        print(f"  💾 Almacenamiento: {alm['data_uso_pct']}% usado ({formatear_kb(alm['data_libre_kb'])} libres)")
    if mem["total_kb"] is not None:
        print(f"  🧠 Memoria RAM:    {formatear_kb(mem['total_kb'])} totales ({formatear_kb(mem['disponible_kb'])} disponibles)")
    sens_ap = next((s["valor_c"] for s in rt["sensores"] if s["nombre"] == "AP"), None)
    print(
        f"  🌡️  Temperatura:    {ESTADO_TERMICO.get(rt['estado_termico'], 'N/D')}"
        + (f" (CPU {sens_ap:.1f} °C)" if sens_ap is not None else "")
    )
    anormales = sum(1 for r in est["reinicios"] if r["categoria"] == "anormal")
    crashes = len(est["crashes_java"]) + len(est["crashes_nativos"])
    print(f"  🛡️  Estabilidad:    {anormales} reinicios anormales · {crashes} cierres puntuales en log")
    print(f"  🔒 Seguridad:      Arranque {seg['arranque_verificado'] or 'N/D'} · Cifrado {'sí' if seg['cifrado'] else 'no'}")

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
    print("   Ábrelo en tu navegador para ver gráficos, tablas y detalles técnicos.")
    print("=" * 66)


def main(argv=None):
    dir_script = str(Path(__file__).resolve().parent)
    if dir_script not in sys.path:
        sys.path.insert(0, dir_script)
    from html_report import generar_html

    parser = argparse.ArgumentParser(
        description="Analiza un informe de errores (bugreport) de Android y genera un diagnóstico claro."
    )
    parser.add_argument(
        "ruta",
        nargs="?",
        help="Ruta al archivo .zip, dumpstate.txt o carpeta del informe (por defecto busca en report/).",
    )
    parser.add_argument(
        "-o",
        "--salida",
        default=str(Path(__file__).resolve().parent / "informe_diagnostico.html"),
        help="Ruta donde guardar el reporte HTML generado.",
    )
    args = parser.parse_args(argv)

    fuente = resolver_fuente(args.ruta)
    with abrir_dumpstate(fuente) as (origen_nombre, lineas):
        print(f"Analizando informe: {origen_nombre} ...")
        datos = analizar_dumpstate(lineas)

    diag = diagnosticar(datos)
    ruta_html = Path(args.salida).expanduser().resolve()
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    ruta_html.write_text(generar_html(datos, diag), encoding="utf-8")

    imprimir_resumen_consola(datos, diag, ruta_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
