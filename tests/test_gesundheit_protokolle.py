# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Tests ohne Netz: Log-Auswertung (Speicher, Laufzeit, Absturz), Protokoll-Sammler, Sensorvergleich und Verlaufs-Erweiterung alter Dateien."""
import os, sqlite3, sys, tempfile, time, unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
TMP = tempfile.mkdtemp(prefix="wc-test-")
os.environ.update(WETTERCUBE_PROTOKOLLE=TMP + "/p", WETTERCUBE_VERLAUF=TMP + "/v.db", WETTERCUBE_EINSTELLUNGEN=TMP + "/e.json")
import details, protokolle, verlauf  # noqa: E402

KOPF = ("WetterCube Apex Diagnose-Log (neueste zuerst)\nVersion: 0.0.95\n"
        "Freier Heap: 81234 Bytes (intern, tiefster Stand seit Start: 9000, groesster Block 40960)\n"
        "PSRAM: frei 19000000 von 33554432 Bytes (tiefster Stand seit Start: 1, groesster Block 2)\nUptime: 42 Minuten\n"
        "Letzter Neustart: ABSTURZ (Watchdog)\nZuletzt aktiv vor dem Neustart: Termine\nWLAN jetzt: 'Netz', Signal -60 dBm, IP 1.2.3.4\n")


class Gesundheit(unittest.TestCase):
    def test_parse(self):
        r = details.log_parse(KOPF)
        self.assertEqual((r["heap"], r["heap_min"], r["heap_block"], r["uptime_min"], r["psram_frei"]), (81234, 9000, 40960, 42, 19000000))
        self.assertEqual(r["zuletzt_aktiv"], "Termine")

    def test_gruende(self):
        details._z["9.9.9.9"] = {"log": details.log_parse(KOPF)}
        stufe, gr = details.gesundheit({"ip": "9.9.9.9", "online": True})
        self.assertEqual(stufe, "warn")
        self.assertTrue(any("knapp" in g for g in gr), gr)
        self.assertTrue(any("Neustart nach Watchdog vor 42 Min." in g for g in gr), gr)
        details._z["9.9.9.9"] = {"log": details.log_parse(KOPF.replace("Uptime: 42", "Uptime: 5000"))}
        self.assertFalse(any("Neustart" in g for g in details.gesundheit({"ip": "9.9.9.9", "online": True})[1]))


class Protokolle(unittest.TestCase):
    def test_neue_zeilen(self):
        a = ["10:00:01 a", "10:00:02 b", "10:00:03 c"]
        self.assertEqual(protokolle.neue_zeilen(a, a + ["10:00:04 d"]), (["10:00:04 d"], False))
        self.assertEqual(protokolle.neue_zeilen(a, a), ([], False))
        self.assertEqual(protokolle.neue_zeilen(a, ["[3s] neu"]), (["[3s] neu"], True))

    def test_sammeln(self):
        t1 = KOPF + "10:00:02 zwei\n10:00:01 eins\n"
        protokolle.sammeln("1.1.1.1", "WetterCube Apex", t1, details.log_parse(t1))
        t2 = KOPF + "10:00:03 drei\n10:00:02 zwei\n10:00:01 eins\n"
        protokolle.sammeln("1.1.1.1", "WetterCube Apex", t2, details.log_parse(t2))
        tag = protokolle.liste("WetterCube Apex", "1.1.1.1")[0]["tag"]
        inhalt = protokolle.lesen("WetterCube Apex", "1.1.1.1", tag).decode()
        z = [x for x in inhalt.splitlines() if x[:2].isdigit()]
        self.assertEqual(z, ["10:00:01 eins", "10:00:02 zwei", "10:00:03 drei"])
        self.assertIn("Zustand:", inhalt)
        with self.assertRaises(ValueError):
            protokolle.lesen("WetterCube Apex", "1.1.1.1", "../x")


class Knoten(unittest.TestCase):
    def test_aelteste_zuerst_ohne_messzeilen(self):
        t = "WetterCube Node Diagnose-Log\nVersion: 0.3.6\n[48:14:55] T=23.2 RH=55\n[48:15:00] [MQTT] verbunden\n[48:15:05] T=23.2 RH=55\n[48:15:09] [WLAN] Signal schwach\n"
        protokolle.sammeln("2.2.2.2", "Node", t)
        tag = protokolle.liste("Node", "2.2.2.2")[0]["tag"]
        z = [x for x in protokolle.lesen("Node", "2.2.2.2", tag).decode().splitlines() if x.startswith("[")]
        self.assertEqual(z, ["[48:15:00] [MQTT] verbunden", "[48:15:09] [WLAN] Signal schwach"])


class Vergleich(unittest.TestCase):
    def test_alte_datei_und_vergleich(self):
        k = sqlite3.connect(verlauf.DATEI)       # alte Datei ohne Sensorspalten
        k.execute("CREATE TABLE IF NOT EXISTS m (ts INTEGER, geraet TEXT, name TEXT, temp REAL)"); k.commit(); k.close()
        jetzt = time.time()
        for i in range(6):
            verlauf._letzte.clear()
            liste = [{"ip": "a", "name": "Apex", "status": {"temp": 5, "int_temp": 22.0 + 0.1 * i}},
                     {"ip": "n", "name": "Node", "status": {"geraet": "node", "temp": 21.0, "feuchte": 50}},
                     {"ip": "f", "name": "Fusion", "status": {"temp": 5, "int_temp": 21.2}}]
            verlauf.speichern(liste)
            k = verlauf._db(); k.execute("UPDATE m SET ts = ts - ? WHERE ts > ?", (1800, jetzt - 60 - i * 1800)); k.commit(); k.close()
        v = verlauf.vergleich("s_temp", 24)
        self.assertEqual(v[0]["geraet"], "Apex")
        self.assertGreater(v[0]["abw"], 0.5)
        self.assertEqual({x["geraet"] for x in v}, {"Apex", "Node", "Fusion"})


if __name__ == "__main__":
    unittest.main()
