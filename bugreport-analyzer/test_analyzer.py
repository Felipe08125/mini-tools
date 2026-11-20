import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from discovery import (  # noqa: E402
    buscar_reporte_por_fecha,
    capturar_bugreport_adb,
    extraer_zip_seguro,
    listar_reportes_por_fecha,
    localizar_archivo_principal,
    parsear_fecha_carpeta,
)
from history import (  # noqa: E402
    SCHEMA_VERSION,
    comparar_reportes,
    construir_metrics_summary,
)
from html_report import generar_html  # noqa: E402
from main import (  # noqa: E402
    abrir_dumpstate,
    analizar_dumpstate,
    diagnosticar,
    main as cli_main,
    resolver_fuente,
)


DUMPSTATE_SANO = """========================================================
== dumpstate: 2026-06-15 12:00:00
========================================================

Build: TEST.202601.001
Network: OPERADOR-DEMO
Bootconfig: androidboot.hardware = "qcom"

------ MEMORY INFO (/proc/meminfo) ------
MemTotal:       11350572 kB
MemFree:          206264 kB
MemAvailable:    3061216 kB
Cached:          2961384 kB
SwapTotal:       4194300 kB
SwapFree:         173164 kB
------ 0.002s was the duration of 'MEMORY INFO' ------

------ DUMPSYS CRITICAL (/system/bin/dumpsys) ------
DUMP OF SERVICE CRITICAL cpuinfo:
Load: 1.21 / 1.82 / 2.13
CPU usage from 1000ms to 0ms ago:
  5.6% 2963/system_server: 2.1% user + 3.4% kernel / faults: 10 minor
  3.4% 1945/surfaceflinger: 1.0% user + 2.4% kernel
------ 1.000s was the duration of 'DUMPSYS CRITICAL' ------

------ SYSTEM LOG (logcat -v threadtime -v printable -v uid -d *:v) ------
06-14 08:10:00.000 10361  6461  6521 E AndroidRuntime: FATAL EXCEPTION: DefaultDispatcher-worker-3
06-14 08:10:00.000 10361  6461  6521 E AndroidRuntime: Process: com.example.demoapp, PID: 6461
06-14 08:10:00.000 10361  6461  6521 E AndroidRuntime: java.lang.IllegalStateException: SharedPreferences in credential encrypted storage are not available until after user (id 0) is unlocked
06-14 08:10:00.000 10361  6461  6521 E AndroidRuntime: \tat android.app.ContextImpl.getSharedPreferences(ContextImpl.java:693)
06-14 14:20:00.000  1047  1875  6946 F libc    : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0000001000 in tid 6946 (DemoWorker), pid 1875 (vendor.samsung.)
06-14 14:20:00.500  1047  7007  7007 F DEBUG   : *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
06-14 14:20:00.500  1047  7007  7007 F DEBUG   : Executable: /vendor/bin/hw/vendor.samsung.hardware.camera.provider-service_64
06-14 14:20:00.500  1047  7007  7007 F DEBUG   : pid: 1875, ppid: 1, tid: 6946, name: DemoWorker  >>> /vendor/bin/hw/vendor.samsung.hardware.camera.provider-service_64 <<<
06-14 14:20:00.500  1047  7007  7007 F DEBUG   : signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0000001000 (read)
06-14 14:20:00.500  1047  7007  7007 F DEBUG   :       #00 pc 000000000006ece8  /apex/com.android.runtime/lib64/bionic/libc.so
06-15 11:00:00.051  1000  2963  3228 E Watchdog: !@Sync: 8595 heap(MB): 182 / 198 FD: 1532 Threads: 602
06-15 11:00:30.065  1000  2963  3228 E Watchdog: !@Sync: 8596 heap(MB): 163 / 198 FD: 1517 Threads: 602
06-15 11:01:00.000 10000  1234  1234 E <script>alert(1)</script>: Error con tag malicioso
------ 1.000s was the duration of 'SYSTEM LOG' ------

------ KERNEL LOG (dmesg) ------
<6>[260772.449846][ T7291] thermal_sys: thermal: cdev
<3>[260773.987470][ T7966] sec_bat_thermal_check: co_c3: 0, tz(NORMAL)
------ 0.010s was the duration of 'KERNEL LOG (dmesg)' ------

------ PSI cpu (/proc/pressure/cpu) ------
some avg10=11.53 avg60=5.85 avg300=5.23 total=22160693527
full avg10=0.00 avg60=0.00 avg300=0.00 total=0
------ 0.001s was the duration of 'PSI cpu' ------

------ PSI memory (/proc/pressure/memory) ------
some avg10=2.64 avg60=0.83 avg300=0.23 total=768714613
full avg10=2.57 avg60=0.81 avg300=0.20 total=613689214
------ 0.001s was the duration of 'PSI memory' ------

------ PSI io (/proc/pressure/io) ------
some avg10=2.86 avg60=0.86 avg300=0.28 total=1500572057
full avg10=1.73 avg60=0.50 avg300=0.13 total=875636977
------ 0.001s was the duration of 'PSI io' ------

------ UFS PART NUMBER (/sys/block/sda/device/model) ------
DEMO256GB
------ 0.001s was the duration of 'UFS PART NUMBER' ------

------ UFS VENDOR (/sys/block/sda/device/vendor) ------
DEMO_VENDOR
------ 0.001s was the duration of 'UFS VENDOR' ------

------ UFS LT (/sys/class/sec/ufs/lt) ------
1
------ 0.001s was the duration of 'UFS LT' ------

------ UFS ERR SUMMARY (/sys/class/scsi_host/host0/SEC_UFS_err_summary) ------
OPERR : 0, UICCMD : 0, UICERR : 0, FATALERR : 0, UTPERR : 0, QUERYERR : 0
MEDIUM : 0, HWERR : 0
------ 0.001s was the duration of 'UFS ERR SUMMARY' ------

------ SYSTEM PROPERTIES (getprop) ------
[ro.product.manufacturer]: [samsung]
[ro.product.model]: [SM-DEMO1]
[ro.soc.model]: [SM8550]
[ro.hardware]: [qcom]
[ro.build.version.release]: [15]
[ro.build.version.sdk]: [35]
[ro.build.version.oneui]: [70000]
[ro.build.display.id]: [TEST.202601.001]
[ro.build.version.security_patch]: [2026-05-05]
[gsm.operator.alpha]: [OPERADOR-DEMO]
[persist.sys.timezone]: [UTC]
[ro.boot.verifiedbootstate]: [green]
[ro.boot.flash.locked]: [1]
[ro.boot.warranty_bit]: [0]
[ro.crypto.state]: [encrypted]
[ro.debuggable]: [0]
[ro.boot.serialno]: [SERIAL_SECRETO_123]
------ 0.001s was the duration of 'SYSTEM PROPERTIES' ------

------ AP RESET INFO EXTEND (/data/system/users/service/data/eRR.p) ------
2026-06-12 20:19:03-0300 |  REBOOT  |       | REASON: userrequested [-] ,mainline_update
2026-06-13 03:43:58-0300 | SHUTDOWN |       | REASON: no power [-]
------ 0.001s was the duration of 'AP RESET INFO EXTEND' ------

------ ANR FILES (ls -lt /data/anr/) ------
total 0
------ 0.001s was the duration of 'ANR FILES' ------

------ FILESYSTEMS & FREE SPACE (df) ------
Filesystem        1K-blocks     Used Available Use% Mounted on
/dev/block/dm-74  232583372 63441780 169010520  28% /data
------ 0.001s was the duration of 'FILESYSTEMS & FREE SPACE' ------

------ UPTIME (uptime) ------
 12:00:12 up 3 days, 04:10,  0 users,  load average: 1.98, 1.22, 1.12
------ 0.001s was the duration of 'UPTIME' ------

------ DROPBOX SYSTEM SERVER CRASHES (/system/bin/dumpsys -T 30000 dropbox -p system_server_crash) ------
Searching for: system_server_crash

(No entries found.)
------ 0.001s was the duration of 'DROPBOX SYSTEM SERVER CRASHES' ------

------ POWER ON INFO (/proc/boot_stat) ------
!@Boot: bootcomplete                                21206        15604          188
------ 0.001s was the duration of 'POWER ON INFO' ------

------ DUMPSYS HIGH (/system/bin/dumpsys) ------
DUMP OF SERVICE HIGH meminfo:
Total PSS by process:
    678,246K: com.instagram.android (pid 22004 / activities)              (  109,450K in swap)
    494,556K: system (pid 2963)                                           (   53,520K in swap)

Total PSS by OOM adjustment:
Total RAM: 11,350,572K (status normal)
 Free RAM: 5,357,398K (3,624,042K cached pss + 1,621,456K cached kernel +   111,900K free)
 Used RAM: 8,453,106K (6,748,194K used pss + 1,704,912K kernel)
 Lost RAM:   258,649K
     ZRAM: 1,376,868K physical used for 4,162,976K in swap (4,194,300K total swap)
--------- 0.050s was the duration of dumpsys HIGH meminfo

------ DUMPSYS NORMAL (/system/bin/dumpsys) ------
DUMP OF SERVICE adb:
  debugging_manager={
    connected_to_adb=false
    adb_wifi={
      enabled=false
    }
  }
--------- 0.010s was the duration of dumpsys adb

DUMP OF SERVICE battery:
  USB powered: true
  status: 2
  health: 2
  level: 65
  voltage: 4014
  temperature: 292
  technology: Li-ion
  current now: 609
  Adaptive Fast Charging Settings: true
  Super Fast Charging Settings: false
  mProtectBatteryMode: 1
  mProtectionThreshold: 80
  battery FirstUseDate: [20240101]
  mSavedBatteryAsoc: [99]
  mSavedBatteryUsage: [12500]
--------- 0.010s was the duration of dumpsys battery

DUMP OF SERVICE batterystats:
Statistics since last charge:
  Estimated battery capacity: 5000 mAh
  Time on battery: 5h 5m 42s 197ms (67.2%) realtime, 4h 9m 51s 720ms (81.7%) uptime
  Time on battery screen off: 1h 33m 33s 874ms (30.6%) realtime
  Discharge: 2949 mAh
  Screen on: 3h 32m 8s 323ms (69.4%) 39x
  Screen off discharge: 191 mAh
  Screen on discharge: 2758 mAh
  Charge time remaining: 43m 18s 0ms
  Connectivity changes: 292
  Mobile active time: 4h 34m 19s 347ms
  Mobile active 5G time: 46m 32s 319ms
  CONNECTIVITY POWER SUMMARY START
  Cellular Statistics:
     Cellular kernel active time: 4h 34m 19s 339ms (89.7%)
     Cellular data received: 1.23GB
     Cellular data sent: 303.58MB
     Cellular Rx signal strength (RSRP):
       very poor (less than -128dBm):  3s 172ms (0.0%)
       poor (-128dBm to -118dBm):  2s 459ms (0.0%)
       moderate (-118dBm to -108dBm):  3m 33s 43ms (1.2%)
       good (-108dBm to -98dBm):  2h 8m 9s 305ms (41.9%)
       great (greater than -98dBm):  2h 53m 54s 218ms (56.9%)
  Wifi Statistics:
     Wifi data received: 0B
     Wifi data sent: 0B
     Wifi states:
       scanning 5h 5m 42s 197ms (100.0%)
  Estimated power use (mAh):
    Capacity: 5000, Rated: 4855, Typical: 5000, Computed drain: 1982, actual drain: 1982
    Global
    screen: 730 apps: 730
    cpu: 863 apps: 863 duration: 6h 39m 3s 436ms
    mobile_radio: 822 apps: 821
      (on battery, screen on)
      screen: 730 apps: 730
  UID u0a473: 884 fg: 498 (1h 35m 44s 848ms) bg: 8.89 (69ms)
  UID u0a308: 287 fg: 80.1 (43m 22s 192ms) fgs: 31.2 (49m 57s 764ms)

  All partial wake locks:
  Wake lock u0a308 AudioMix: 18m 18s 43ms (0 times) max=834423
  Wake lock u0a354 com.whatsapp:sendinactive: 9s 251ms (5 times) max=3006

--------- 0.050s was the duration of dumpsys batterystats

DUMP OF SERVICE diskstats:
Latency: 0ms [512B Data Write]
Recent Disk Write Speed (kB/s) = 20551
File-based Encryption: true
App Size: 32493502464
App Data Size: 12061255952
App Cache Size: 4290445824
Package Names: ["com.spotify.music","com.whatsapp"]
App Sizes: [5000000000,200000000]
App Data Sizes: [1000000000,800000000]
Cache Sizes: [100000000,50000000]
--------- 0.020s was the duration of dumpsys diskstats

DUMP OF SERVICE thermalservice:
Thermal Status: 0
Current temperatures from HAL:
\tTemperature{mValue=40.1, mType=0, mName=AP, mStatus=0}
\tTemperature{mValue=34.4, mType=3, mName=SKIN, mStatus=0}
\tTemperature{mValue=29.7, mType=2, mName=BAT, mStatus=0}
Temperature static thresholds from HAL:
\tTemperatureThreshold{mType=3, mName=SKIN, mHotThrottlingThresholds=[38.0, 40.0, 42.0, 45.0, 47.0, 60.0, 90.0]}
--------- 0.010s was the duration of dumpsys thermalservice

DUMP OF SERVICE wifi:
ScanAlwaysAvailable true
Wi-Fi is disabled
  rec[0]: ssid = "MiRedPrivadaOculta"
--------- 0.010s was the duration of dumpsys wifi

DUMP OF SERVICE telephony.registry:
  Phone Id=0
    mServiceState={mVoiceRegState=0(IN_SERVICE), mDataRegState=0(IN_SERVICE)}
    mOperatorAlphaLong=OPERADOR-DEMO
    mSignalStrength=SignalStrength:{mLte=CellSignalStrengthLte: rssi=-65 rsrp=-97 rsrq=-11}
    mTelephonyDisplayInfo=TelephonyDisplayInfo {network=LTE, overrideNetwork=LTE_CA, isRoaming=false}
    mIsDataEnabled=true
--------- 0.010s was the duration of dumpsys telephony.registry

------ CHECKIN BATTERYSTATS (/system/bin/dumpsys -T 30000 batterystats -c) ------
9,0,i,uid,10473,com.spotify.music
9,0,i,uid,10308,com.google.android.youtube
9,0,i,uid,10354,com.whatsapp
------ 0.010s was the duration of 'CHECKIN BATTERYSTATS' ------

------ CHECKIN PACKAGE (/system/bin/dumpsys -T 30000 package --checkin) ------
pkg,com.whatsapp,10354
pkg,com.google.android.youtube,10308
pkg,com.spotify.music,10473
------ 0.010s was the duration of 'CHECKIN PACKAGE' ------
"""


DUMPSTATE_TIMELINE_Y_PRIVACIDAD = """========================================================
== dumpstate: 2026-11-20 15:00:00
========================================================

Build: TEST.202611.002
Network: OPERADOR-DEMO

------ SYSTEM LOG (logcat -v threadtime -v printable -v uid -d *:v) ------
11-20 14:11:00.100  1000  2000  2000 I ActivityManager: ANR in com.instagram.android (com.instagram.android/.MainActivity)
11-20 14:11:00.101  1000  2000  2000 I ActivityManager: Reason: Input dispatching timed out MAC=AA:BB:CC:DD:EE:FF IMEI=123456789012345
11-20 14:11:10.000  1000  1100  1100 I lowmemorykiller: Kill 'com.spotify.music' (4100), uid 10473, oom_score_adj 900
11-20 14:12:00.000  1000  2963  3296 D BrightnessThermalClamper: Thermal status observer already started
11-20 14:12:05.000  1000  2963  3296 W ThermalManager: Throttling active status=2 serialno=SERIAL_SECRETO_XYZ
11-20 14:13:00.000 10000  5000  5000 E </script><script>alert(9)</script>: fallo con tag
------ 0.500s was the duration of 'SYSTEM LOG' ------

------ KERNEL LOG (dmesg) ------
<6>[10000.000000][ T100] init: running
<3>[13600.000000][ T101] oom-killer invoked for SERIAL_SECRETO_XYZ MAC=11:22:33:44:55:66
------ 0.010s was the duration of 'KERNEL LOG (dmesg)' ------

------ THERMAL DUMP (/proc/sec_pm_log/thermal_log) ------
[10665.000000] Start lmh cpu7 @2937
[10666.000000] Start lmh cpu7 @2995
------ 0.001s was the duration of 'THERMAL DUMP' ------

------ SYSTEM PROPERTIES (getprop) ------
[ro.product.manufacturer]: [samsung]
[ro.product.model]: [SM-DEMO1]
[ro.build.version.release]: [16]
[ro.build.version.oneui]: [80500]
[ro.build.display.id]: [TEST.202611.002]
[ro.build.version.security_patch]: [2026-11-01]
[ro.boot.verifiedbootstate]: [green]
[ro.boot.flash.locked]: [1]
[ro.boot.warranty_bit]: [0]
[ro.crypto.state]: [encrypted]
[ro.boot.serialno]: [SERIAL_SECRETO_XYZ]
------ 0.001s was the duration of 'SYSTEM PROPERTIES' ------

------ DUMPSYS NORMAL (/system/bin/dumpsys) ------
DUMP OF SERVICE battery:
  level: 45
  voltage: 3810
  temperature: 395
  mSavedBatteryAsoc: [96]
  mSavedBatteryUsage: [15000]
--------- 0.010s was the duration of dumpsys battery

DUMP OF SERVICE batterystats:
  Battery History [Format: 2] (5% used):
    11-20 14:00:00.000 RESET:TIME: 2026-11-20-14-00-00-000
    11-20 14:00:00.100 060 c010001a status=discharging temp=310 volt=4120 ap_temp=35.0 skin_temp=32.0
    11-20 14:10:00.000 058 c010001a status=discharging temp=405 volt=3820 ap_temp=48.5 skin_temp=42.1
    11-20 14:15:00.000 055 c010001a status=discharging temp=395 volt=3890 ap_temp=41.0 skin_temp=37.0
Statistics since last charge:
  Estimated battery capacity: 5000 mAh
  Time on battery: 2h 0m 0s 0ms (80.0%) realtime, 1h 0m 0s 0ms (50.0%) uptime
  Time on battery screen off: 1h 0m 0s 0ms (50.0%) realtime, 40m 0s 0ms (66.7%) uptime
  Discharge: 1100 mAh
  Screen on: 1h 0m 0s 0ms (50.0%) 12x
  Estimated power use (mAh):
    Global
    screen: 400 apps: 400
  UID u0a200: 550 fg: 120 (20m 0s 0ms) fgs: 180 (45m 0s 0ms)
--------- 0.020s was the duration of dumpsys batterystats

DUMP OF SERVICE wifi:
  rec[0]: ssid = "SSID_SECRETO_CASA"
--------- 0.010s was the duration of dumpsys wifi

------ CHECKIN BATTERYSTATS (/system/bin/dumpsys -T 30000 batterystats -c) ------
9,0,i,uid,10200,com.instagram.android
------ 0.010s was the duration of 'CHECKIN BATTERYSTATS' ------
"""


class TestBugreportAnalyzer(unittest.TestCase):
    def test_parseo_y_resolucion_uids(self):
        datos = analizar_dumpstate(io.StringIO(DUMPSTATE_SANO))
        self.assertEqual(datos["dispositivo"]["modelo"], "SM-DEMO1")
        self.assertEqual(datos["dispositivo"]["oneui"], "7.0")
        self.assertEqual(datos["dispositivo"]["tiempo_arranque_ms"], 21206)
        self.assertEqual(datos["dispositivo"]["total_paquetes"], 3)

        apps = datos["bateria"]["consumo_apps"]
        self.assertEqual(apps[0]["paquete"], "com.spotify.music")
        self.assertEqual(apps[0]["etiqueta"], "Spotify")
        self.assertEqual(apps[1]["paquete"], "com.google.android.youtube")

        # Wakelock con ':' en el nombre debe parsearse y resolver UID
        wls = datos["bateria"]["wakelocks"]
        self.assertEqual(len(wls), 2)
        self.assertEqual(wls[1]["paquete"], "com.whatsapp")
        self.assertEqual(wls[1]["nombre"], "com.whatsapp:sendinactive")

    def test_filtrado_watchdog_y_crashes_sin_duplicar(self):
        datos = analizar_dumpstate(io.StringIO(DUMPSTATE_SANO))
        est = datos["estabilidad"]

        # Watchdog !@Sync NO debe contar en errores E ni como alerta
        self.assertEqual(est["watchdog_sync_latidos"], 2)
        self.assertEqual(est["logcat_conteo"]["E"], 5)  # 4 de AndroidRuntime + 1 de <script>
        tags = dict(est["top_tags_error"])
        self.assertNotIn("Watchdog", tags)

        # 1 crash Java + 1 crash nativo (sin duplicar F libc con F DEBUG del mismo PID)
        self.assertEqual(len(est["crashes_java"]), 1)
        self.assertEqual(est["crashes_java"][0]["proceso"], "com.example.demoapp")
        self.assertEqual(len(est["crashes_nativos"]), 1)
        self.assertEqual(est["crashes_nativos"][0]["crashed_pid"], 1875)
        self.assertIn("camera.provider", est["crashes_nativos"][0]["ejecutable"])

    def test_lectura_carpeta_y_zip_con_bytes_invalidos(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Caso 1: carpeta bugreport con bytes inválidos UTF-8
            carpeta = tmp_path / "bugreport-test-1"
            carpeta.mkdir()
            (carpeta / "main_entry.txt").write_text("dumpstate.txt\n", encoding="utf-8")
            (carpeta / "dumpstate.txt").write_bytes(
                DUMPSTATE_SANO.encode("utf-8") + b"\xff\xfe\x00\n"
            )

            fuente_dir = resolver_fuente(str(carpeta))
            with abrir_dumpstate(fuente_dir) as (_, lineas):
                datos_dir = analizar_dumpstate(lineas)
            self.assertEqual(datos_dir["bateria"]["nivel"], 65)

            # Caso 2: archivo ZIP con main_entry.txt
            ruta_zip = tmp_path / "bugreport-test-2.zip"
            with zipfile.ZipFile(ruta_zip, "w") as zf:
                zf.writestr("main_entry.txt", "dumpstate.txt")
                zf.writestr("dumpstate.txt", DUMPSTATE_SANO.encode("utf-8") + b"\x80\x81")

            fuente_zip = resolver_fuente(str(ruta_zip))
            with abrir_dumpstate(fuente_zip) as (_, lineas):
                datos_zip = analizar_dumpstate(lineas)
            self.assertEqual(datos_zip["almacenamiento"]["data_uso_pct"], 28)

    def test_diagnostico_sano_vs_critico(self):
        datos_sano = analizar_dumpstate(io.StringIO(DUMPSTATE_SANO))
        diag_sano = diagnosticar(datos_sano)
        self.assertEqual(diag_sano["nivel_global"], "atencion")  # 2 crashes menores + wifi scan + 4G
        self.assertGreaterEqual(diag_sano["puntuacion"], 75)

        # Simular escenario crítico: batería < 80%, almacenamiento > 90%, reinicio panic
        datos_crit = analizar_dumpstate(io.StringIO(DUMPSTATE_SANO))
        datos_crit["bateria"]["salud_asoc_pct"] = 72
        datos_crit["almacenamiento"]["data_uso_pct"] = 95
        datos_crit["estabilidad"]["reinicios"].append(
            {
                "fecha": "2026-06-15 10:00:00",
                "tipo": "REBOOT",
                "motivo": "kernel panic",
                "categoria": "anormal",
            }
        )
        diag_crit = diagnosticar(datos_crit)
        self.assertEqual(diag_crit["nivel_global"], "critico")
        self.assertLess(diag_crit["puntuacion"], 60)
        severidades = [h["severidad"] for h in diag_crit["hallazgos"]]
        self.assertIn("critico", severidades)

    def test_html_valido_y_escape_xss_y_privacidad(self):
        datos = analizar_dumpstate(io.StringIO(DUMPSTATE_SANO))
        diag = diagnosticar(datos)
        html_out = generar_html(datos, diag)

        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("Batería y consumo", html_out)
        self.assertIn("Seguridad e integridad", html_out)
        # Escapado de XSS
        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_out)
        # Privacidad: ni serial ni SSID deben aparecer
        self.assertNotIn("SERIAL_SECRETO_123", html_out)
        self.assertNotIn("MiRedPrivadaOculta", html_out)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            carpeta = tmp_path / "bugreport-cli"
            carpeta.mkdir()
            (carpeta / "dumpstate.txt").write_text(DUMPSTATE_SANO, encoding="utf-8")
            salida_html = tmp_path / "salida.html"

            rc = cli_main([str(carpeta), "-o", str(salida_html)])
            self.assertEqual(rc, 0)
            self.assertTrue(salida_html.is_file())
            self.assertIn("SM-DEMO1", salida_html.read_text(encoding="utf-8"))

    def test_descubrimiento_fechas_mixto_y_subcarpetas(self):
        self.assertEqual(parsear_fecha_carpeta("2026-10-01")[1], "2026-10-01")
        self.assertEqual(parsear_fecha_carpeta("18_11_26")[1], "2026-11-18")
        self.assertIsNone(parsear_fecha_carpeta("no-es-fecha"))

        with tempfile.TemporaryDirectory() as tmp:
            rep_dir = Path(tmp) / "report"
            rep_dir.mkdir()

            # 1) YYYY-MM-DD con bugreport-*.txt en raíz y carpeta FS/
            d1 = rep_dir / "2026-10-01"
            (d1 / "FS").mkdir(parents=True)
            (d1 / "bugreport-SM8550-2026-10-01.txt").write_text(DUMPSTATE_SANO, encoding="utf-8")
            (d1 / "version.txt").write_text("1", encoding="utf-8")

            # 2) DD_MM_YY con subcarpeta extraída
            d2 = rep_dir / "18_11_26"
            sub2 = d2 / "bugreport-2026-11-18"
            (sub2 / "FS").mkdir(parents=True)
            (sub2 / "dumpstate.txt").write_text(DUMPSTATE_SANO, encoding="utf-8")

            # 3) YYYY-MM-DD con dumpstate.txt en raíz
            d3 = rep_dir / "2026-11-20"
            (d3 / "lshal-debug").mkdir(parents=True)
            (d3 / "dumpstate.txt").write_text(DUMPSTATE_TIMELINE_Y_PRIVACIDAD, encoding="utf-8")

            reportes = listar_reportes_por_fecha(rep_dir)
            self.assertEqual([r["fecha_iso"] for r in reportes], ["2026-10-01", "2026-11-18", "2026-11-20"])
            self.assertEqual(localizar_archivo_principal(d1).name, "bugreport-SM8550-2026-10-01.txt")
            self.assertEqual(localizar_archivo_principal(d2), (sub2 / "dumpstate.txt").resolve())

            # Buscar por YYYY-MM-DD debe encontrar 18_11_26
            hallado = buscar_reporte_por_fecha(rep_dir, "2026-11-18")
            self.assertEqual(hallado["carpeta_nombre"], "18_11_26")

            # resolver_fuente sin argumento sobre base_script apuntando al tmp padre selecciona el más reciente
            mas_reciente = resolver_fuente(base_script=Path(tmp))
            self.assertEqual(mas_reciente.name, "2026-11-20")

    def test_metricas_streaming_timeline_correlacion_y_privacidad(self):
        datos = analizar_dumpstate(io.StringIO(DUMPSTATE_TIMELINE_Y_PRIVACIDAD))
        bat = datos["bateria"]
        rt = datos["rendimiento_termico"]
        mem = datos["memoria"]
        lt = datos["linea_tiempo"]

        # Deep sleep: 2h realtime - 1h uptime = 50%; screen off: 60m - 40m = 33.3%
        self.assertEqual(bat["deep_sleep_pct"], 50.0)
        self.assertEqual(bat["deep_sleep_screen_off_pct"], 33.3)
        self.assertEqual(rt["temperatura_max_c"], 48.5)
        self.assertEqual(rt["temperatura_max_sensor"], "AP")
        self.assertEqual(rt["eventos_throttling"], 2)  # 1 episodio LMH coalescido + 1 logcat
        self.assertEqual(mem["lmkd_kills"], 1)
        self.assertGreaterEqual(mem["eventos_presion_memoria"], 2)

        # Serie Battery History + eventos correlacionados
        self.assertGreaterEqual(len(lt["series"]), 3)
        tipos_ev = {e["tipo"] for e in lt["eventos"]}
        self.assertIn("pico_termico", tipos_ev)
        self.assertIn("caida_voltaje", tipos_ev)
        self.assertIn("anr", tipos_ev)
        self.assertIn("lmkd_kill", tipos_ev)
        self.assertIn("throttling_lmh", tipos_ev)
        self.assertGreaterEqual(len(lt["correlaciones"]), 1)

        # Privacidad y escape seguro en JSON/HTML
        diag = diagnosticar(datos)
        summary = construir_metrics_summary(datos, diag, fecha_iso="2026-11-20")
        html_out = generar_html(datos, diag)
        todo = json.dumps(summary, ensure_ascii=False) + "\n" + html_out

        for secreto in (
            "SERIAL_SECRETO_XYZ",
            "AA:BB:CC:DD:EE:FF",
            "11:22:33:44:55:66",
            "123456789012345",
            "SSID_SECRETO_CASA",
        ):
            self.assertNotIn(secreto, todo)
        # No debe romper el tag <script> con cierre prematuro
        self.assertNotIn("</script><script>alert(9)</script>", html_out)

    def test_esquema_summary_all_diff_y_regresiones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rep_dir = root / "report"
            (rep_dir / "2026-10-01").mkdir(parents=True)
            (rep_dir / "2026-11-20" / "sub").mkdir(parents=True)

            (rep_dir / "2026-10-01" / "dumpstate.txt").write_text(DUMPSTATE_SANO, encoding="utf-8")
            (rep_dir / "2026-11-20" / "sub" / "dumpstate.txt").write_text(
                DUMPSTATE_TIMELINE_Y_PRIVACIDAD, encoding="utf-8"
            )

            with mock.patch("main.DIR_SCRIPT", root):
                buf1 = io.StringIO()
                with contextlib.redirect_stdout(buf1):
                    rc1 = cli_main(["--all"])
                self.assertEqual(rc1, 0)
                self.assertIn("2 analizado(s)", buf1.getvalue())

                # Segunda pasada con --all debe omitir ambos
                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    rc2 = cli_main(["--all"])
                self.assertEqual(rc2, 0)
                self.assertIn("0 analizado(s), 2 ya tenían análisis", buf2.getvalue())

                # Verificar metrics_summary.json y evolución automática en el más reciente
                sum_ruta_1 = rep_dir / "2026-10-01" / "metrics_summary.json"
                sum_ruta_2 = rep_dir / "2026-11-20" / "metrics_summary.json"
                html_ruta_2 = rep_dir / "2026-11-20" / "informe_diagnostico.html"
                self.assertTrue(sum_ruta_1.is_file())
                self.assertTrue(sum_ruta_2.is_file())
                self.assertTrue(html_ruta_2.is_file())

                s1 = json.loads(sum_ruta_1.read_text(encoding="utf-8"))
                s2 = json.loads(sum_ruta_2.read_text(encoding="utf-8"))
                self.assertEqual(s2["schema_version"], SCHEMA_VERSION)
                for clave in (
                    "schema_version",
                    "fecha_reporte",
                    "dispositivo",
                    "puntuacion_general",
                    "bateria",
                    "top_procesos",
                    "termico",
                    "memoria_psi",
                    "almacenamiento",
                    "estabilidad",
                ):
                    self.assertIn(clave, s2)

                diff = comparar_reportes(s2, s1)
                self.assertTrue(diff["actualizacion_sistema"]["cambio"])
                self.assertTrue(any("Instagram" in r for r in diff["regresiones"]))

                html_2 = html_ruta_2.read_text(encoding="utf-8")
                self.assertIn("Evolución vs. reporte anterior", html_2)
                self.assertIn("Correlación temporal interactiva", html_2)

                # Ejecutar --diff explícito y --date
                buf_diff = io.StringIO()
                with contextlib.redirect_stdout(buf_diff):
                    rc_diff = cli_main(["--diff", "2026-10-01", "2026-11-20"])
                self.assertEqual(rc_diff, 0)
                out_diff = buf_diff.getvalue()
                self.assertIn("COMPARATIVA HISTÓRICA", out_diff)
                self.assertTrue(any(sim in out_diff for sim in ("▲", "▼", "=")))

                buf_date = io.StringIO()
                with contextlib.redirect_stdout(buf_date):
                    rc_date = cli_main(["--date", "2026-10-01"])
                self.assertEqual(rc_date, 0)
                self.assertIn("2026-06-15", buf_date.getvalue())

    def test_adb_captura_descompresion_y_zip_slip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rep_dir = root / "report"
            rep_dir.mkdir()

            # 1) Sin dispositivo conectado debe lanzar error descriptivo
            fake_empty = subprocess.CompletedProcess(
                args=["adb", "devices"],
                returncode=0,
                stdout="List of devices attached\n\n",
                stderr="",
            )
            with mock.patch("discovery.subprocess.run", return_value=fake_empty):
                with self.assertRaises(RuntimeError):
                    capturar_bugreport_adb(rep_dir, fecha_iso="2026-11-20")

            # 2) Flujo exitoso: crea report/<fecha>/, descomprime y borra el .zip temporal
            def fake_adb_run(cmd, capture_output=True, text=True, check=False):
                if cmd[:2] == ["adb", "devices"]:
                    return subprocess.CompletedProcess(
                        cmd, 0, "List of devices attached\nFAKE123\tdevice\n", ""
                    )
                if cmd[:2] == ["adb", "bugreport"]:
                    ruta_zip = Path(cmd[2])
                    with zipfile.ZipFile(ruta_zip, "w") as zf:
                        zf.writestr("main_entry.txt", "dumpstate.txt")
                        zf.writestr("dumpstate.txt", DUMPSTATE_SANO)
                    return subprocess.CompletedProcess(cmd, 0, "ok", "")
                raise AssertionError(f"Comando inesperado: {cmd}")

            with mock.patch("discovery.subprocess.run", side_effect=fake_adb_run):
                carpeta = capturar_bugreport_adb(rep_dir, fecha_iso="2026-11-20")
            self.assertTrue((carpeta / "dumpstate.txt").is_file())
            self.assertEqual(list(carpeta.glob("*.zip")), [])

            # 3) Protección contra Zip-Slip
            mal_zip = Path(tmp) / "malicioso.zip"
            with zipfile.ZipFile(mal_zip, "w") as zf:
                zf.writestr("../../escape.txt", "evil")
            with self.assertRaises(ValueError):
                extraer_zip_seguro(mal_zip, rep_dir / "zip_test")


if __name__ == "__main__":
    unittest.main()
