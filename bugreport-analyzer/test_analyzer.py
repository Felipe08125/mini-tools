import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


if __name__ == "__main__":
    unittest.main()
