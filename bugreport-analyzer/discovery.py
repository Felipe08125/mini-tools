from datetime import date, datetime
import os
from pathlib import Path
import re
import subprocess
import zipfile


# Carpetas internas de bugreport que nunca contienen el dumpstate principal
CARPETAS_IGNORADAS = {
    "fs",
    "proto",
    "lshal-debug",
    "__pycache__",
    ".git",
}

ARCHIVOS_TEXTO_SECUNDARIOS = {
    "dumpstate_board.txt",
    "dumpstate_log.txt",
    "main_entry.txt",
    "version.txt",
}

FECHA_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
FECHA_DMY_CORTA_RE = re.compile(r"^(\d{2})[_-](\d{2})[_-](\d{2})$")
FECHA_DMY_LARGA_RE = re.compile(r"^(\d{2})[_-](\d{2})[_-](\d{4})$")


def parsear_fecha_carpeta(nombre):
    """Convierte 'YYYY-MM-DD' o 'DD_MM_YY' / 'DD-MM-YY' / 'DD_MM_YYYY' a (date, iso_str)."""
    texto = str(nombre).strip()
    m_iso = FECHA_ISO_RE.match(texto)
    if m_iso:
        anio, mes, dia = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            d = date(anio, mes, dia)
            return d, d.isoformat()
        except ValueError:
            return None

    m_corta = FECHA_DMY_CORTA_RE.match(texto)
    if m_corta:
        dia, mes, anio_corto = int(m_corta.group(1)), int(m_corta.group(2)), int(m_corta.group(3))
        try:
            d = date(2000 + anio_corto, mes, dia)
            return d, d.isoformat()
        except ValueError:
            return None

    m_larga = FECHA_DMY_LARGA_RE.match(texto)
    if m_larga:
        dia, mes, anio = int(m_larga.group(1)), int(m_larga.group(2)), int(m_larga.group(3))
        try:
            d = date(anio, mes, dia)
            return d, d.isoformat()
        except ValueError:
            return None

    return None


def _buscar_archivo_principal_en_dir(carpeta):
    """Busca main_entry.txt, dumpstate.txt o el mayor bugreport-*.txt directo en 'carpeta'."""
    if not carpeta.is_dir():
        return None

    main_entry = carpeta / "main_entry.txt"
    if main_entry.is_file():
        nombre = main_entry.read_text(encoding="utf-8", errors="replace").strip()
        if nombre:
            candidato = (carpeta / nombre).resolve()
            carpeta_res = carpeta.resolve()
            if (carpeta_res in candidato.parents or candidato.parent == carpeta_res) and candidato.is_file():
                return candidato

    dumpstate = carpeta / "dumpstate.txt"
    if dumpstate.is_file():
        return dumpstate

    candidatos_bugreport = [
        p
        for p in carpeta.iterdir()
        if p.is_file()
        and p.name.startswith("bugreport-")
        and p.suffix.lower() == ".txt"
        and p.name.lower() not in ARCHIVOS_TEXTO_SECUNDARIOS
    ]
    if candidatos_bugreport:
        candidatos_bugreport.sort(key=lambda p: p.stat().st_size, reverse=True)
        return candidatos_bugreport[0]

    return None


def _subcarpetas_candidatas(carpeta):
    """Lista subcarpetas inmediatas potencialmente contenedoras de un dumpstate extraído."""
    subdirs = []
    for item in carpeta.iterdir():
        if not item.is_dir():
            continue
        nombre_low = item.name.lower()
        if item.name.startswith(".") or nombre_low in CARPETAS_IGNORADAS:
            continue
        subdirs.append(item)
    subdirs.sort(key=lambda p: (0 if p.name.startswith("bugreport-") else 1, p.name))
    return subdirs


def localizar_archivo_principal(carpeta):
    """Detecta dumpstate.txt o bugreport-*.txt en la raíz de 'carpeta' o en subcarpetas extraídas."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return None

    directo = _buscar_archivo_principal_en_dir(carpeta)
    if directo is not None:
        return directo

    subdirs_n1 = _subcarpetas_candidatas(carpeta)
    for sub in subdirs_n1:
        encontrado = _buscar_archivo_principal_en_dir(sub)
        if encontrado is not None:
            return encontrado

    # Respaldo de profundidad 2 por si se descomprimió con una carpeta contenedora extra
    for sub in subdirs_n1:
        for sub2 in _subcarpetas_candidatas(sub):
            encontrado = _buscar_archivo_principal_en_dir(sub2)
            if encontrado is not None:
                return encontrado

    return None


def es_carpeta_bugreport(carpeta):
    """Comprueba si una carpeta (o su subcarpeta extraída) contiene un dumpstate o bugreport-*.txt."""
    return localizar_archivo_principal(carpeta) is not None


def resolver_carpeta_report(base_script=None):
    """Localiza la carpeta 'report/' relativa al módulo o su directorio padre."""
    base = Path(base_script).resolve() if base_script else Path(__file__).resolve().parent
    for candidata in (base / "report", base.parent / "report"):
        if candidata.is_dir():
            return candidata
    return None


def listar_reportes_por_fecha(carpeta_report):
    """Escanea 'carpeta_report' y retorna los reportes válidos ordenados cronológicamente (ascendente)."""
    carpeta_report = Path(carpeta_report)
    if not carpeta_report.is_dir():
        return []

    reportes = []
    for item in carpeta_report.iterdir():
        if not item.is_dir():
            continue
        fecha_parsed = parsear_fecha_carpeta(item.name)
        if not fecha_parsed:
            continue
        archivo = localizar_archivo_principal(item)
        if archivo is None:
            continue
        fecha_obj, fecha_iso = fecha_parsed
        reportes.append(
            {
                "fecha": fecha_obj,
                "fecha_iso": fecha_iso,
                "carpeta": item.resolve(),
                "carpeta_nombre": item.name,
                "archivo_principal": archivo.resolve(),
                "ruta_summary": (item / "metrics_summary.json").resolve(),
                "ruta_html": (item / "informe_diagnostico.html").resolve(),
            }
        )

    reportes.sort(key=lambda r: (r["fecha"], r["carpeta_nombre"]))
    return reportes


def buscar_reporte_por_fecha(carpeta_report, fecha_str):
    """Busca una carpeta de reporte por fecha ('YYYY-MM-DD', 'DD_MM_YY') o nombre exacto."""
    reportes = listar_reportes_por_fecha(carpeta_report)
    if not reportes:
        raise FileNotFoundError(
            f"No se encontraron carpetas de fecha con bugreports válidos en: {carpeta_report}"
        )

    texto = str(fecha_str).strip()
    for rep in reversed(reportes):
        if rep["carpeta_nombre"] == texto:
            return rep

    parsed = parsear_fecha_carpeta(texto)
    if parsed:
        _, fecha_iso = parsed
        for rep in reversed(reportes):
            if rep["fecha_iso"] == fecha_iso:
                return rep

    disponibles = ", ".join(f"{r['fecha_iso']} ({r['carpeta_nombre']})" for r in reportes)
    raise FileNotFoundError(
        f"No se encontró ningún reporte para la fecha '{fecha_str}'. Disponibles: {disponibles}"
    )


def detectar_carpeta_fecha_de_ruta(ruta, carpeta_report=None):
    """Si 'ruta' corresponde o vive dentro de una carpeta de fecha en report/, retorna su metadata."""
    ruta_res = Path(ruta).expanduser().resolve()
    rep_dir = Path(carpeta_report).resolve() if carpeta_report else resolver_carpeta_report()
    if rep_dir is None or not rep_dir.is_dir():
        return None

    for rep in listar_reportes_por_fecha(rep_dir):
        carpeta_rep = rep["carpeta"].resolve()
        if ruta_res == carpeta_rep or carpeta_rep in ruta_res.parents:
            return rep
    return None


def _elegir_de_contenedor(carpeta):
    """Selecciona el bugreport más reciente dentro de una carpeta contenedora sin esquema de fecha."""
    if es_carpeta_bugreport(carpeta):
        return carpeta

    candidatos = []
    for item in carpeta.iterdir():
        if item.is_dir() and es_carpeta_bugreport(item):
            candidatos.append(item)
        elif item.is_file() and item.suffix.lower() == ".zip":
            candidatos.append(item)
        elif (
            item.is_file()
            and item.suffix.lower() == ".txt"
            and (item.name == "dumpstate.txt" or item.name.startswith("bugreport-"))
            and item.name.lower() not in ARCHIVOS_TEXTO_SECUNDARIOS
        ):
            candidatos.append(item)

    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró ningún informe de errores válido (.txt, .zip o carpeta bugreport-*) en: {carpeta}"
        )

    candidatos.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return candidatos[0]


def resolver_fuente(ruta_arg=None, base_script=None):
    """Encuentra el informe indicado o detecta automáticamente la carpeta de fecha más reciente en report/."""
    if ruta_arg:
        candidato = Path(ruta_arg).expanduser().resolve()
        if not candidato.exists():
            raise FileNotFoundError(f"No existe la ruta indicada: {candidato}")
        if candidato.is_file():
            return candidato
        if es_carpeta_bugreport(candidato):
            return candidato
        reportes = listar_reportes_por_fecha(candidato)
        if reportes:
            return reportes[-1]["carpeta"]
        return _elegir_de_contenedor(candidato)

    carpeta_report = resolver_carpeta_report(base_script)
    if carpeta_report is not None:
        reportes = listar_reportes_por_fecha(carpeta_report)
        if reportes:
            return reportes[-1]["carpeta"]
        return _elegir_de_contenedor(carpeta_report)

    raise FileNotFoundError(
        "No se encontró la carpeta 'report'. Pasa la ruta del informe como argumento "
        "o coloca tus carpetas por fecha dentro de 'report/'."
    )


def abrir_dumpstate(fuente):
    """Abre el archivo principal del bugreport en modo streaming seguro UTF-8."""
    from contextlib import contextmanager
    import io

    @contextmanager
    def _abrir():
        src = Path(fuente)
        if src.is_file() and src.suffix.lower() == ".zip":
            with zipfile.ZipFile(src, "r") as zf:
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
                        and Path(info.filename).name.lower() not in ARCHIVOS_TEXTO_SECUNDARIOS
                    ]
                    if not txts:
                        txts = [
                            info
                            for info in zf.infolist()
                            if not info.is_dir()
                            and info.filename.lower().endswith(".txt")
                            and Path(info.filename).name.lower() not in ARCHIVOS_TEXTO_SECUNDARIOS
                        ]
                    if not txts:
                        raise FileNotFoundError(f"El archivo ZIP no contiene ningún .txt de informe: {src}")
                    entrada = max(txts, key=lambda info: info.file_size).filename
                with zf.open(entrada, "r") as raw:
                    yield f"{src.name} -> {entrada}", io.TextIOWrapper(
                        raw, encoding="utf-8", errors="replace", newline=None
                    )
            return

        if src.is_dir():
            archivo = localizar_archivo_principal(src)
            if archivo is None:
                raise FileNotFoundError(f"No se encontró dumpstate.txt ni bugreport-*.txt en: {src}")
            with archivo.open("r", encoding="utf-8", errors="replace") as f:
                yield str(archivo), f
            return

        if src.is_file():
            with src.open("r", encoding="utf-8", errors="replace") as f:
                yield str(src), f
            return

        raise FileNotFoundError(f"No se puede leer la fuente indicada: {src}")

    return _abrir()


def extraer_zip_seguro(ruta_zip, destino):
    """Descomprime un .zip validando cada ruta miembro contra path traversal (Zip-Slip)."""
    destino_res = Path(destino).resolve()
    destino_res.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ruta_zip, "r") as zf:
        for info in zf.infolist():
            nombre = info.filename
            if os.path.isabs(nombre):
                raise ValueError(f"Entrada ZIP insegura (ruta absoluta): {nombre}")
            objetivo = (destino_res / nombre).resolve()
            if objetivo != destino_res and destino_res not in objetivo.parents:
                raise ValueError(f"Entrada ZIP insegura fuera del destino (Zip-Slip): {nombre}")
        zf.extractall(destino_res)


def _verificar_dispositivo_adb():
    """Verifica que adb esté disponible y exista al menos un dispositivo en estado 'device'."""
    try:
        proc = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "No se encontró el ejecutable 'adb' en el PATH. Instala Android Platform Tools."
        ) from exc

    if proc.returncode != 0:
        detalle = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Error ejecutando 'adb devices': {detalle or proc.returncode}")

    conectados = []
    otros_estados = []
    for linea in proc.stdout.splitlines():
        s = linea.strip()
        if not s or s.startswith("List of devices"):
            continue
        partes = s.split()
        if len(partes) >= 2:
            if partes[1] == "device":
                conectados.append(partes[0])
            else:
                otros_estados.append(partes[1])

    if not conectados:
        if otros_estados:
            raise RuntimeError(
                f"Dispositivo detectado pero no autorizado/listo (estado: {', '.join(otros_estados)}). "
                "Acepta el diálogo de depuración USB en el teléfono."
            )
        raise RuntimeError(
            "No hay ningún dispositivo Android conectado por ADB. Activa Depuración USB y conéctalo."
        )
    return conectados[0]


def capturar_bugreport_adb(carpeta_report, fecha_iso=None):
    """Captura un bugreport vía ADB en report/<YYYY-MM-DD>/, lo descomprime y borra el .zip temporal."""
    _verificar_dispositivo_adb()

    fecha_dir = fecha_iso or datetime.now().strftime("%Y-%m-%d")
    carpeta_destino = Path(carpeta_report) / fecha_dir
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    zip_temporal = carpeta_destino / f"bugreport-{fecha_dir}.zip"
    print(f"Capturando bugreport vía ADB en {carpeta_destino} (esto puede tardar unos minutos)...")

    proc = subprocess.run(
        ["adb", "bugreport", str(zip_temporal)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detalle = (proc.stderr or proc.stdout or "").strip()
        if zip_temporal.exists():
            zip_temporal.unlink()
        raise RuntimeError(f"Falló 'adb bugreport': {detalle or proc.returncode}")

    archivo_zip = zip_temporal if zip_temporal.is_file() else None
    if archivo_zip is None:
        zips_encontrados = sorted(
            carpeta_destino.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if zips_encontrados:
            archivo_zip = zips_encontrados[0]

    if archivo_zip is None:
        if localizar_archivo_principal(carpeta_destino) is not None:
            return carpeta_destino
        raise RuntimeError(f"'adb bugreport' terminó sin generar archivo .zip en {carpeta_destino}")

    try:
        extraer_zip_seguro(archivo_zip, carpeta_destino)
    finally:
        if archivo_zip.exists():
            archivo_zip.unlink()

    if localizar_archivo_principal(carpeta_destino) is None:
        raise FileNotFoundError(
            f"Se extrajo el bugreport en {carpeta_destino}, pero no se encontró dumpstate.txt ni bugreport-*.txt."
        )

    return carpeta_destino
