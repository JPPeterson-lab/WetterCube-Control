# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Tests fuer Alle Geraete (Updates nacheinander, Einstellung fuer alle), Aenderungsliste, Hilfe (Netzcheck) und Neues Geraet (Suche).
Wie test_control.py gegen Attrappen-Geraete, nie gegen echte.

  python3 -m unittest tests.test_neu -v
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_control as tc  # noqa: E402
import aenderungen  # noqa: E402

U = None


def setUpModule():
    global U
    U = tc.Umgebung()


def tearDownModule():
    U.ende()


class T01_Aenderungsliste(unittest.TestCase):
    MD = "# Changelog\n\n## v1.0.0-rc15 (2026-11-05)\n\n### Neu\n- **Eins:** siehe [Doku](https://x.y)\n- Zwei\n\n## v1.0.0-rc14 (2026-11-04)\n- alt\n"

    def test_abschnitt(self):
        z = aenderungen.abschnitt(self.MD, "1.0.0-rc15")
        self.assertEqual([x["typ"] for x in z], ["ueberschrift", "punkt", "punkt"])
        self.assertEqual(z[1]["text"], "Eins: siehe Doku")
        self.assertEqual(aenderungen.abschnitt(self.MD, "v1.0.0-rc14")[0]["text"], "alt")
        self.assertIsNone(aenderungen.abschnitt(self.MD, "9.9.9"))

    def test_ohne_oeffentliche_liste(self):
        j = U.get("/api/update/aenderungen?ip=" + U.A + "&version=0.9.1-test")
        self.assertEqual(j["zeilen"], [])
        self.assertIn("keine öffentliche", j["hinweis"])

    def test_ungueltige_version(self):
        self.assertEqual(aenderungen.fuer("fusion-s3", "x y;z")["zeilen"], [])


class T02_AlleGeraete(unittest.TestCase):
    def test_plan(self):
        j = U.get("/api/alle/plan")
        self.assertEqual(len(j["geraete"]), 3)
        self.assertIn("helligkeit", j["aktionen"])

    def test_einstellung_vorschau_und_ausfuehren(self):
        c, j = U.post("/api/alle/einstellung", {"werte": {"helligkeit": 55}, "ips": [U.A, U.B], "ausfuehren": False})
        self.assertEqual(c, 200)
        self.assertEqual([x["aenderungen"][0]["neu"] for x in j], [55, 55])
        self.assertEqual(j[0]["aenderungen"][0]["alt"], 80)
        c, j = U.post("/api/alle/einstellung", {"werte": {"helligkeit": 55}, "ips": [U.A, U.B], "ausfuehren": True})
        self.assertTrue(all(x["ok"] for x in j), j)
        self.assertEqual(U.stublog(U.pa)["einstellungen"]["brightness"], 55)
        self.assertEqual(U.stublog(U.pb)["einstellungen"]["brightness"], 55)
        c, j = U.post("/api/alle/einstellung", {"werte": {"helligkeit": 55}, "ips": [U.A], "ausfuehren": True})
        self.assertEqual(j[0]["text"], "nichts zu ändern")

    def test_einstellung_falsche_werte(self):
        self.assertEqual(U.post("/api/alle/einstellung", {"werte": {"helligkeit": 500}, "ips": [U.A]})[0], 400)
        self.assertEqual(U.post("/api/alle/einstellung", {"werte": {"quatsch": 1}, "ips": [U.A]})[0], 400)
        self.assertEqual(U.post("/api/alle/einstellung", {"werte": {}, "ips": [U.A]})[0], 400)
        self.assertEqual(U.post("/api/alle/einstellung", {"werte": {"helligkeit": 50}, "ips": []})[0], 400)
        self.assertEqual(U.post("/api/alle/einstellung", {"werte": {"helligkeit": 50}, "ips": ["9.9.9.9"]})[0], 404)

    def test_updates_nacheinander(self):
        c, j = U.post("/api/alle/updates", {"ips": [U.A, U.B]})
        self.assertEqual(c, 200, j)
        st = tc.warte(lambda: (lambda s: s if s["fertig"] else None)(U.get("/api/alle/status")), 60)
        self.assertIsNotNone(st, "Updates wurden nicht fertig")
        self.assertEqual([x["ok"] for x in st["schritte"]], [True, True], st)
        self.assertEqual(U.stublog(U.pa)["posts"].count("OTA"), 1)
        c, j = U.post("/api/alle/updates", {"ips": [U.A]})     # nichts mehr zu tun
        self.assertEqual(c, 400)


class T04_BootHinweis(unittest.TestCase):
    def test_wrong_boot_mode_und_manuell(self):
        import installer, time
        gesehen = {}

        def falsch(argumente, dateien=None):
            gesehen["args"] = argumente
            installer._log("A fatal error occurred: Failed to connect to ESP32: Wrong boot mode detected (0x13)! The chip needs to be in download mode.")
            return 2
        alt, alt_ok = installer._esptool, installer._port_ok
        installer._esptool, installer._port_ok = falsch, lambda p: True
        try:
            self.assertTrue(installer.erkennen("COM99", True))
            for _ in range(50):
                if not installer.status()["laeuft"]:
                    break
                time.sleep(0.1)
            st = installer.status()
            self.assertFalse(st["ok"])
            self.assertIn("--before", gesehen["args"])
            self.assertIn("no_reset", gesehen["args"])
            self.assertTrue(any("BOOT-Taste" in z for z in st["log"]))
            self.assertIn("BOOT-Taste", st["info"])
        finally:
            installer._esptool, installer._port_ok = alt, alt_ok


class T03_Hilfe(unittest.TestCase):
    def test_netzcheck(self):
        l = U.get("/api/netzcheck")
        self.assertTrue(l and all({"titel", "stufe", "text"} <= set(x) for x in l))
        self.assertTrue(any("Gefundene Geräte" == x["titel"] and x["stufe"] == "ok" for x in l))

    def test_adresse(self):
        c, j = U.post("/api/netzcheck/adresse", {"adresse": U.A})
        self.assertTrue(j["ok"], j)
        c, j = U.post("/api/netzcheck/adresse", {"adresse": "127.0.0.1:1"})
        self.assertFalse(j["ok"])
        c, j = U.post("/api/netzcheck/adresse", {"adresse": "bad addr;"})
        self.assertFalse(j["ok"])

    def test_suche_jetzt(self):
        c, j = U.post("/api/suche", {})
        self.assertEqual(c, 200)

    def test_seiten_und_netzwerkmodus(self):
        for p in ("/alle", "/assistent", "/hilfe"):
            self.assertEqual(U.anfrage(p)[0], 200)
            self.assertEqual(U.anfrage(p, port=U.pl)[0], 403)          # im Netzwerkmodus gesperrt
        self.assertEqual(U.anfrage("/api/netzcheck", port=U.pl)[0], 403)


if __name__ == "__main__":
    unittest.main()
