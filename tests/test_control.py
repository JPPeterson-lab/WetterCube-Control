# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Selbsttest von WetterCube Control gegen Attrappen-Geraete (tests/stub_geraet.py). Beruehrt nie echte Geraete:
Control startet mit --keine-suche, alle Daten (Einstellungen, Sicherungen, Verlauf, Schluesselbund) liegen in einem Wegwerf-Ordner.

  python3 -m unittest discover -s tests -v          (dauert etwa 2 Minuten)
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
PY = sys.executable


def freier_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def warte(bedingung, sekunden=40, pause=0.5):
    ende = time.time() + sekunden
    while time.time() < ende:
        try:
            r = bedingung()
            if r:
                return r
        except Exception:
            pass
        time.sleep(pause)
    return None


class Umgebung:
    """Zwei Attrappen (A, B), eine mit Passwort (P) und eine laufende Control-Instanz."""
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="wc-control-test-")
        self.prozesse = []
        self.pa, self.pb, self.pp, self.pc, self.pl = (freier_port() for _ in range(5))
        for port, extra in ((self.pa, []), (self.pb, []), (self.pp, ["--passwort", "geheim"])):
            self.prozesse.append(subprocess.Popen([PY, os.path.join(HIER, "stub_geraet.py"), str(port)] + extra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.env = dict(os.environ, HOME=self.tmp, USERPROFILE=self.tmp, WETTERCUBE_TAKT="2", WETTERCUBE_OFFLINE_NACH="6", WETTERCUBE_TAG_SEKUNDEN="6",
                        WETTERCUBE_VERLAUF=self.tmp + "/v.db", WETTERCUBE_EINSTELLUNGEN=self.tmp + "/e.json", WETTERCUBE_SICHERUNGEN=self.tmp + "/s",
                        WETTERCUBE_DIAGNOSE=self.tmp + "/d", WETTERCUBE_PW_NUR_SPEICHER="1", WETTERCUBE_AUTOSTART_TEST="/Fake/WetterCube Control.app/Contents/MacOS/x",
                        WETTERCUBE_AUTOSTART_ORDNER=self.tmp + "/auto")
        geraete = []
        for port in (self.pa, self.pb, self.pp):
            geraete += ["--geraet", f"127.0.0.1:{port}"]
        self.prozesse.append(subprocess.Popen([PY, os.path.join(WURZEL, "control.py"), "--port", str(self.pc), "--keine-suche"] + geraete, env=self.env,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.prozesse.append(subprocess.Popen([PY, os.path.join(WURZEL, "control.py"), "--port", str(self.pl), "--keine-suche", "--lan", "--geraet", f"127.0.0.1:{self.pa}"],
                                              env=dict(self.env, WETTERCUBE_VERLAUF=self.tmp + "/v2.db", WETTERCUBE_EINSTELLUNGEN=self.tmp + "/e2.json"),
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.A, self.B, self.P = (f"127.0.0.1:{x}" for x in (self.pa, self.pb, self.pp))
        warte(lambda: len(self.get("/api/geraete")) == 3, 40)

    def anfrage(self, pfad, daten=None, port=None, kopf=None, methode=None):
        url = f"http://127.0.0.1:{port or self.pc}{pfad}"
        k = {"Origin": f"http://127.0.0.1:{port or self.pc}"} if daten is not None else {}
        k.update(kopf or {})
        if daten is not None:
            k["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=None if daten is None else json.dumps(daten).encode(), headers=k, method=methode)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type", "")

    def get(self, pfad, port=None):
        c, b, _ = self.anfrage(pfad, port=port)
        return json.loads(b) if b[:1] in (b"[", b"{") else b

    def post(self, pfad, daten, port=None):
        c, b, _ = self.anfrage(pfad, daten, port=port)
        try:
            return c, json.loads(b)
        except ValueError:
            return c, b

    def stub(self, port, **kw):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/_set?" + "&".join(f"{k}={v}" for k, v in kw.items()), timeout=5).read()

    def stublog(self, port):
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/_log", timeout=5).read())

    def ereignisse(self):
        return [e["text"] for e in self.get("/api/ereignisse?seit=0")]

    def ende(self):
        for p in self.prozesse:
            p.terminate()
        for p in self.prozesse:
            try:
                p.wait(5)
            except Exception:
                p.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


U = None


def setUpModule():
    global U
    U = Umgebung()


def tearDownModule():
    U.ende()


class T01_Geraete(unittest.TestCase):
    def test_seiten_und_logo(self):
        for pfad in ("/", "/geraet", "/verlauf", "/wand", "/kopieren", "/installer", "/einstellungen", "/logo.svg", "/logo-hell.svg", "/icon-192.png", "/manifest.json"):
            self.assertEqual(U.anfrage(pfad)[0], 200, pfad)

    def test_geraeteliste_und_gesundheit(self):
        l = {d["ip"]: d for d in U.get("/api/geraete")}
        self.assertEqual(set(l), {U.A, U.B, U.P})
        g = l[U.A]["gesundheit"]
        self.assertEqual(g["stufe"], "warn")
        self.assertTrue(any("WLAN schwach" in x for x in g["gruende"]))
        self.assertTrue(any("veraltet" in x for x in g["gruende"]))
        self.assertTrue(l[U.A]["update"] is None)

    def test_host_und_herkunftsschutz(self):
        self.assertEqual(U.anfrage("/", kopf={"Host": "boese.example"})[0], 403)
        c, _, _ = U.anfrage("/api/alle-sichern", {}, kopf={"Origin": "http://boese.example"})
        self.assertEqual(c, 403)
        self.assertEqual(U.anfrage("/api/bild?ip=10.9.9.9")[0], 404)
        self.assertEqual(U.anfrage(f"/api/bild?ip={U.A}&s=../x")[0], 400)

    def test_bildschirm_und_log(self):
        c, b, t = U.anfrage(f"/api/bild?ip={U.A}")
        self.assertEqual((c, t, b[:4]), (200, "image/png", b"\x89PNG"))
        self.assertIn(b"Diagnose-Log", U.anfrage(f"/api/log?ip={U.A}")[1])


class T02_Meldungen(unittest.TestCase):
    def test_dwd_und_alarm(self):
        U.post("/api/alarme", {"geraet": U.B, "metrik": "temp", "op": ">", "grenze": "10", "name": "Zu warm"})
        U.stub(U.pa, dwd=2)
        self.assertTrue(warte(lambda: any("Neue DWD-Warnung" in t for t in U.ereignisse()), 20), "Warnung nicht gemeldet")
        self.assertTrue(warte(lambda: any("Zu warm" in t and "meldet" in t for t in U.ereignisse()), 20), "Alarm nicht gemeldet")
        U.stub(U.pa, dwd=0); U.stub(U.pb, temp=5)
        self.assertTrue(warte(lambda: any(t.startswith("Entwarnung") for t in U.ereignisse()), 20))
        self.assertTrue(warte(lambda: any("wieder in Ordnung" in t for t in U.ereignisse()), 20))
        self.assertEqual(U.post("/api/alarme", {"metrik": "xyz", "op": ">", "grenze": "1"})[0], 400)

    def test_offline_und_wieder_da(self):
        U.stub(U.pb, offline=1)
        self.assertTrue(warte(lambda: any("nicht erreichbar" in t for t in U.ereignisse()), 25), "offline nicht gemeldet")
        l = {d["ip"]: d for d in U.get("/api/geraete")}
        self.assertFalse(l[U.B]["online"]); self.assertTrue(l[U.B]["zuletzt"])
        U.stub(U.pb, offline=0)
        self.assertTrue(warte(lambda: any("wieder erreichbar" in t for t in U.ereignisse()), 25))


class T03_Einstellungen(unittest.TestCase):
    def test_sichern_wiederherstellen_kopieren(self):
        c, b, _ = U.anfrage(f"/api/sicherung?ip={U.A}")
        self.assertEqual(c, 200)
        ordner = os.path.join(U.tmp, "s", time.strftime("%Y-%m-%d")); os.makedirs(ordner, exist_ok=True)
        datei = "WetterCube-Test-" + time.strftime("%Y-%m-%d-%H%M") + ".json"
        with open(os.path.join(ordner, datei), "wb") as f:
            f.write(b)
        liste = U.get(f"/api/sicherungen?ip={U.A}")
        self.assertTrue(liste)
        c, r = U.post("/api/wiederherstellen", {"ip": U.A, "datei": liste[0]["datei"]})
        self.assertEqual(c, 200, r); self.assertTrue(os.path.exists(r["kopie"]))
        self.assertEqual(U.post("/api/wiederherstellen", {"ip": U.A, "datei": "../../etc/passwd"})[0], 400)
        self.assertEqual(U.post("/api/wiederherstellen", {"ip": U.A, "inhalt": json.dumps({"typ": "WetterCube-Next-Einstellungen"})})[0], 400)
        self.assertEqual(U.post("/api/wiederherstellen", {"ip": U.A, "inhalt": json.dumps({"x": 1})})[0], 400)
        # Kopieren: A bekommt andere Werte, dann B angleichen (nur Gruppe Muell)
        urllib.request.urlopen(urllib.request.Request(f"http://{U.A}/restore", data=json.dumps({"typ": "WetterCube-Fusion-Einstellungen", "muell_ab": 17, "muell_bis": 7}).encode(), method="POST"), timeout=5).read()
        c, vor = U.post("/api/kopieren", {"quelle": U.A, "ziele": [U.B], "gruppen": ["muell"], "ausfuehren": False})
        self.assertEqual([a["schluessel"] for a in vor[0]["aenderungen"]], ["muell_ab", "muell_bis"])
        c, nach = U.post("/api/kopieren", {"quelle": U.A, "ziele": [U.B], "gruppen": ["muell"], "ausfuehren": True})
        self.assertTrue(nach[0]["ok"])
        self.assertEqual(U.stublog(U.pb)["einstellungen"]["muell_ab"], 17)
        self.assertEqual(U.post("/api/kopieren", {"quelle": U.A, "ziele": [U.A], "gruppen": ["muell"]})[0], 400)

    def test_diagnose(self):
        c, r = U.post("/api/diagnose", {"ips": [U.A], "einstellungen": False})
        self.assertEqual(c, 200)
        c, b, _ = U.anfrage("/api/diagnose-datei?name=" + r["name"]); self.assertEqual((c, b[:2]), (200, b"PK"))
        self.assertEqual(U.anfrage("/api/diagnose-datei?name=../../x")[0], 400)

    def test_update(self):
        u = U.get(f"/api/update/pruefen?ip={U.A}")
        self.assertTrue(u["verfuegbar"])
        c, _ = U.post("/api/update/starten", {"ip": U.A}); self.assertEqual(c, 200)
        self.assertFalse(U.get(f"/api/update/pruefen?ip={U.A}")["verfuegbar"])
        self.assertEqual(U.post("/api/update/starten", {"ip": U.A})[0], 400)

    def test_namen_verwalten_entfernen_zeitplan(self):
        U.post("/api/geraete/aendern", {"ip": U.A, "alias": "Wohnzimmer"})
        self.assertIn("Wohnzimmer", [d["name"] for d in U.get("/api/geraete")])
        U.post("/api/geraete/aendern", {"ip": U.A, "alias": ""})
        c, r = U.post("/api/geraete/aendern", {"ip": U.A, "entfernen": True})
        self.assertEqual(c, 400, "erreichbares, automatisch gefundenes Geraet darf nicht entfernt werden")
        U.post("/api/geraete/aendern", {"ip": U.B, "ausgeblendet": True})
        self.assertNotIn(U.B, [d["ip"] for d in U.get("/api/geraete")])
        U.post("/api/geraete/aendern", {"ip": U.B, "ausgeblendet": False})
        self.assertEqual(U.post("/api/geraete/hinzufuegen", {"adresse": "a b;rm"})[0], 400)
        self.assertEqual(U.post("/api/geraete/hinzufuegen", {"adresse": "127.0.0.1:9"})[0], 400)
        U.post("/api/einstellungen", {"auto_sichern": {"modus": "taeglich", "behalten": 2}})
        self.assertTrue(warte(lambda: any("Automatische Sicherung" in t for t in U.ereignisse()), 30))

    def test_autostart_nur_im_testordner(self):
        e = U.get("/api/einstellungen"); self.assertTrue(e["autostart"]["verfuegbar"])
        self.assertTrue(U.post("/api/autostart", {"an": True})[1]["aktiv"])
        self.assertTrue(os.listdir(os.path.join(U.tmp, "auto")))
        self.assertFalse(U.post("/api/autostart", {"an": False})[1]["aktiv"])


class T04_Passwort(unittest.TestCase):
    def test_geraet_mit_passwort(self):
        c, r = U.post("/api/passwort", {"ip": U.A, "passwort": "egal"})
        self.assertEqual(c, 400); self.assertIn("kein Web-Passwort", r["fehler"])
        self.assertIn("verlangt ein Passwort", U.anfrage(f"/api/sicherung?ip={U.P}")[1].decode())
        c, r = U.post("/api/passwort", {"ip": U.P, "passwort": "falsch"}); self.assertEqual(c, 400); self.assertIn("falsch", r["fehler"])
        self.assertEqual(U.anfrage(f"/api/sicherung?ip={U.P}")[0], 502)
        c, r = U.post("/api/passwort", {"ip": U.P, "passwort": "geheim"}); self.assertEqual(c, 200, r)
        self.assertEqual(U.anfrage(f"/api/sicherung?ip={U.P}")[0], 200)
        self.assertEqual(U.anfrage(f"/api/log?ip={U.P}")[0], 200)
        self.assertTrue(U.get(f"/api/passwort/status?ip={U.P}")["gesetzt"])
        U.post("/api/passwort", {"ip": U.P, "loeschen": True})
        self.assertFalse(U.get(f"/api/passwort/status?ip={U.P}")["gesetzt"])


class T05_Verlauf(unittest.TestCase):
    def test_verlauf_und_export(self):
        j = U.get("/api/verlauf?metrik=temp&stunden=1")
        self.assertTrue(j["daten"])
        self.assertIn(b"zeit;geraet;temp", U.anfrage("/api/verlauf.csv?stunden=1")[1])
        self.assertTrue(U.get("/api/verlauf/tage?metrik=temp&tage=2"))
        self.assertEqual(U.anfrage("/api/verlauf?metrik=drop")[0], 400)


class T06_Netzwerkmodus(unittest.TestCase):
    def test_nur_ansehen(self):
        for pfad in ("/", "/verlauf", "/wand", "/logo.svg", "/api/geraete"):
            self.assertEqual(U.anfrage(pfad, port=U.pl)[0], 200, pfad)
        for pfad in ("/installer", "/kopieren", "/einstellungen", f"/api/log?ip={U.A}", f"/api/sicherung?ip={U.A}", "/api/einstellungen", "/api/installer/info"):
            self.assertEqual(U.anfrage(pfad, port=U.pl)[0], 403, pfad)
        for pfad in ("/api/alle-sichern", "/api/wiederherstellen", "/api/update/starten", "/api/geraete/aendern", "/api/alarme", "/api/passwort", "/api/autostart"):
            self.assertEqual(U.anfrage(pfad, {}, port=U.pl)[0], 403, pfad)

    def test_update_pruefung_im_netzwerkmodus_erlaubt(self):
        self.assertNotEqual(U.anfrage(f"/api/update/pruefen?ip={U.A}", port=U.pl)[0], 403)   # rein lesend (Antwort des Attrappen-Geraets egal)


class T07_Versionssuche(unittest.TestCase):
    def test_standard_aus_keine_verbindung_von_selbst(self):
        sys.path.insert(0, WURZEL)
        d = tempfile.mkdtemp()
        os.environ["WETTERCUBE_EINSTELLUNGEN"] = os.path.join(d, "e.json")
        os.environ.pop("WETTERCUBE_VERSIONSSUCHE", None)
        import einstellungen, details
        einstellungen._cache = None
        self.assertFalse(einstellungen.holen()["versionssuche"])
        aufrufe = []
        alt = (details.neueste_holen, details.selbst_fragen)
        details.neueste_holen = lambda: aufrufe.append("m")
        details.selbst_fragen = lambda l: aufrufe.append("s")
        try:
            details.takt()
            self.assertEqual(aufrufe, [])
            einstellungen.aendern(lambda e: e.__setitem__("versionssuche", True))
            details.takt()
            self.assertEqual(aufrufe, ["m", "s"])
        finally:
            details.neueste_holen, details.selbst_fragen = alt
            einstellungen._cache = None
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
