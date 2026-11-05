# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Tests der Node-Anbindung in Control (Attrappe tests/stub_node.py, nie ein echtes Geraet):
Erkennen, Karte, Kalibrierung lesen/schreiben mit Sicherheitskopie, Kopiersperre, Installer-Quelle nur wenn gesetzt.

  python3 -m unittest tests.test_node -v
"""
import glob, json, os, shutil, subprocess, sys, tempfile, unittest, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.dirname(HIER))
import test_control as tc  # noqa: E402

N = None


class Node:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="wc-node-test-")
        self.pn, self.pa, self.c1, self.c2 = (tc.freier_port() for _ in range(4))
        self.pr = []
        self.pr.append(subprocess.Popen([tc.PY, os.path.join(HIER, "stub_node.py"), str(self.pn)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.pr.append(subprocess.Popen([tc.PY, os.path.join(HIER, "stub_geraet.py"), str(self.pa)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.NODE, self.A = f"127.0.0.1:{self.pn}", f"127.0.0.1:{self.pa}"
        basis = dict(os.environ, HOME=self.tmp, USERPROFILE=self.tmp, WETTERCUBE_TAKT="2", WETTERCUBE_PW_NUR_SPEICHER="1")
        basis.pop("WETTERCUBE_NODE_QUELLE", None)
        self.env1 = dict(basis, WETTERCUBE_VERLAUF=self.tmp + "/v1.db", WETTERCUBE_EINSTELLUNGEN=self.tmp + "/e1.json", WETTERCUBE_SICHERUNGEN=self.tmp + "/s1")
        self.env2 = dict(basis, WETTERCUBE_VERLAUF=self.tmp + "/v2.db", WETTERCUBE_EINSTELLUNGEN=self.tmp + "/e2.json", WETTERCUBE_SICHERUNGEN=self.tmp + "/s2",
                         WETTERCUBE_NODE_QUELLE=f"http://127.0.0.1:{self.pn}/node")
        for port, env in ((self.c1, self.env1), (self.c2, self.env2)):   # c1: ohne interne Quelle, c2: mit
            self.pr.append(subprocess.Popen([tc.PY, os.path.join(tc.WURZEL, "control.py"), "--port", str(port), "--keine-suche", "--geraet", self.NODE, "--geraet", self.A],
                                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        tc.warte(lambda: len(self.get("/api/geraete", self.c1)) == 2 and len(self.get("/api/geraete", self.c2)) == 2, 40)

    def anfrage(self, pfad, daten=None, port=None):
        port = port or self.c1
        k = {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"} if daten is not None else {}
        req = urllib.request.Request(f"http://127.0.0.1:{port}{pfad}", data=None if daten is None else json.dumps(daten).encode(), headers=k)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def get(self, pfad, port=None):
        c, b = self.anfrage(pfad, port=port)
        return json.loads(b)

    def post(self, pfad, daten, port=None):
        c, b = self.anfrage(pfad, daten, port)
        return c, json.loads(b)

    def stublog(self):
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.pn}/_log", timeout=5).read())

    def ende(self):
        for p in self.pr:
            p.terminate()
        for p in self.pr:
            try:
                p.wait(5)
            except Exception:
                p.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


def setUpModule():
    global N
    N = Node()


def tearDownModule():
    N.ende()


class T01_Erkennen(unittest.TestCase):
    def test_node_wird_erkannt_und_zeigt_werte(self):
        l = {d["ip"]: d for d in N.get("/api/geraete")}
        d = l[N.NODE]
        self.assertEqual(d["art"], "status")
        s = d["status"]
        self.assertEqual(s["geraet"], "node")
        for k in ("temp", "feuchte", "druck", "rssi", "version"):
            self.assertIn(k, s)

    def test_seite_und_karte(self):
        c, b = N.anfrage("/kalibrierung")
        self.assertEqual(c, 200)
        self.assertIn(b"Kalibrierung", b)
        c, b = N.anfrage("/")
        self.assertIn(b"geraet==='node'", b)       # Signal und Link nur beim Node

    def test_update_pruefung_ohne_ota(self):
        j = N.get("/api/update/pruefen?ip=" + N.NODE)
        self.assertFalse(j["verfuegbar"])


class T02_Kalibrierung(unittest.TestCase):
    def test_lesen(self):
        j = N.get("/api/node/kalibrierung?ip=" + N.NODE)
        self.assertEqual(j["config"]["f_off"], -2.8)
        self.assertEqual(set(j["kurven"]), {"temp", "feuchte", "druck"})
        self.assertEqual(j["status"]["geraet"], "node")

    def test_kein_node_wird_abgelehnt(self):
        c, j = N.post("/api/node/kalibrierung", {"ip": N.A, "werte": {"t_off": 1}})
        self.assertEqual(c, 400)
        self.assertIn("kein Sensorknoten", j["fehler"])

    def test_ungueltige_angaben(self):
        for w in ({"unbekannt": 1}, {"kt": "x"}, {"kt": [[1]]}, {"t_off": "a"}, {}):
            c, _ = N.post("/api/node/kalibrierung", {"ip": N.NODE, "werte": w})
            self.assertEqual(c, 400, w)

    def test_speichern_mit_sicherheitskopie(self):
        c, j = N.post("/api/node/kalibrierung", {"ip": N.NODE, "werte": {"kt": [[24.2, 22.4]], "t_off": 0.5}})
        self.assertEqual(c, 200, j)
        self.assertTrue(glob.glob(N.tmp + "/s1/*/vor-Aenderung-*"))
        self.assertTrue(os.path.isfile(j["kopie"]))
        kopie = json.load(open(j["kopie"]))
        self.assertEqual(kopie["typ"], "WetterCube-Node-Einstellungen")
        self.assertEqual(kopie["kt"], [])                      # Zustand VOR der Aenderung
        self.assertEqual(N.get("/api/node/kalibrierung?ip=" + N.NODE)["config"]["kt"], [[24.2, 22.4]])
        self.assertAlmostEqual(N.get("/api/geraete")[0]["status"]["temp"] if N.get("/api/geraete")[0]["ip"] == N.NODE else 22.4, 22.4, delta=3)

    def test_punkt_aus_referenzwert(self):
        c, j = N.post("/api/node/punkt", {"ip": N.NODE, "groesse": "feuchte", "ref": 48.0})
        self.assertEqual(c, 200, j)
        self.assertTrue(os.path.isfile(j["kopie"]))
        self.assertEqual(N.get("/api/node/kalibrierung?ip=" + N.NODE)["config"]["kf"][-1][1], 48.0)
        c, _ = N.post("/api/node/punkt", {"ip": N.NODE, "groesse": "unsinn", "ref": 1})
        self.assertEqual(c, 400)

    def test_zu_viele_punkte_meldet_geraetefehler(self):
        c, j = N.post("/api/node/kalibrierung", {"ip": N.NODE, "werte": {"kf": [[i, i] for i in range(6)]}})
        self.assertEqual(c, 400)
        self.assertIn("Zu viele", j["fehler"])                 # Meldung des Geraets kommt durch


class T03_Kopieren(unittest.TestCase):
    def test_zwischen_typen_gesperrt(self):
        import sicherung
        self.assertEqual(sicherung.erlaubte_gruppen("WetterCube-Node-Einstellungen", "WetterCube-Fusion-Einstellungen"), set())
        self.assertEqual(sicherung.erlaubte_gruppen("WetterCube-Fusion-Einstellungen", "WetterCube-Node-Einstellungen"), set())
        self.assertEqual(sicherung.erlaubte_gruppen("WetterCubePlus-Einstellungen", "WetterCube-Node-Einstellungen"), set())
        self.assertIn("kalibrierung", sicherung.erlaubte_gruppen("WetterCube-Node-Einstellungen", "WetterCube-Node-Einstellungen"))
        self.assertEqual(sicherung.FAMILIE["WetterCube-Node-Einstellungen"], "node")

    def test_vorschau_node_nach_fusion(self):
        c, j = N.post("/api/kopieren", {"quelle": N.NODE, "ziele": [N.A], "gruppen": ["ort", "kalibrierung"], "ausfuehren": False})
        self.assertEqual(c, 200, j)
        self.assertEqual(j[0]["aenderungen"], [])
        self.assertTrue(j[0]["gesperrt"])

    def test_gruppe_nur_mit_node_sichtbar(self):
        self.assertIn("kalibrierung", N.get("/api/kopieren/gruppen"))

    def test_sicherung_und_wiederherstellen(self):
        c, b = N.anfrage("/api/sicherung?ip=" + N.NODE)
        self.assertEqual(c, 200)
        d = json.loads(b)
        self.assertEqual(d["typ"], "WetterCube-Node-Einstellungen")
        self.assertNotIn("wifi_pw", d)
        self.assertNotIn("wifi_ssid", d)
        c, j = N.post("/api/wiederherstellen", {"ip": N.NODE, "inhalt": b.decode()})
        self.assertEqual(c, 200, j)


class T04_InstallerQuelle(unittest.TestCase):
    def test_ohne_quelle_kein_node(self):
        j = N.get("/api/installer/info", N.c1)
        self.assertNotIn("node", [p["key"] for p in j["produkte"]])
        c, _ = N.anfrage("/api/installer/plan?produkt=node", port=N.c1)
        self.assertNotEqual(c, 200)

    def test_mit_quelle_node_flashbar(self):
        j = N.get("/api/installer/info", N.c2)
        self.assertIn("node", [p["key"] for p in j["produkte"]])
        self.assertEqual([p["name"] for p in j["produkte"] if p["key"] == "node"], ["WetterCube Node (intern)"])
        p = N.get("/api/installer/plan?produkt=node", N.c2)
        self.assertEqual(p["chip"], "esp32c3")
        self.assertEqual(p["dateien"], ["bootloader.bin", "partitions.bin", "boot_app0.bin", "firmware.bin"])
        self.assertEqual(N.get("/api/installer/versionen?produkt=node", N.c2), ["v0.1.0"])

    def test_adressen_stimmen(self):
        import installer
        os.environ["WETTERCUBE_NODE_QUELLE"] = f"http://127.0.0.1:{N.pn}/node"
        try:
            chip, teile, ver, basis = installer.plan("node")
            self.assertEqual((chip, ver), ("esp32c3", "0.1.0"))
            self.assertEqual([hex(o) for _, o in teile], ["0x0", "0x8000", "0xe000", "0x10000"])
            self.assertEqual(basis, f"http://127.0.0.1:{N.pn}/node/")
            self.assertEqual(len(installer._holen(basis + "firmware.bin")), 4096)
        finally:
            del os.environ["WETTERCUBE_NODE_QUELLE"]
        self.assertNotIn("node", [p["key"] for p in installer.produkte()])

    def test_fremde_adressen_werden_ignoriert(self):
        import installer
        for adr in ("ftp://x/y", "javascript:1", "http://boese.example/n/", "file:///etc"):
            os.environ["WETTERCUBE_NODE_QUELLE"] = adr
            try:
                self.assertEqual(installer.interne_quelle("node"), "", adr)
            finally:
                del os.environ["WETTERCUBE_NODE_QUELLE"]

    def test_einstellungsdatei_und_nie_in_der_oberflaeche(self):
        import einstellungen, installer
        alt = einstellungen.DATEI
        einstellungen.DATEI = N.tmp + "/eigene.json"
        einstellungen._cache = None
        try:
            with open(einstellungen.DATEI, "w") as f:
                json.dump({"interne_quellen": {"node": "https://beispiel.invalid/geheim/node/"}}, f)
            einstellungen._cache = None
            self.assertEqual(installer.interne_quelle("node"), "https://beispiel.invalid/geheim/node/")
        finally:
            einstellungen.DATEI = alt
            einstellungen._cache = None
        self.assertNotIn("interne_quellen", N.get("/api/einstellungen", N.c1))


class T05_KeineAdresseImQuellcode(unittest.TestCase):
    def test_quellcode_ohne_interne_adresse(self):
        env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "WetterCube Website", "tools", "server.env")
        if not os.path.isfile(env):
            self.skipTest("server.env nicht vorhanden")
        with open(env) as f:
            ordner = [z.split("=", 1)[1].strip() for z in f if z.startswith("NODE_TEST_ORDNER=")]
        if not ordner or not ordner[0]:
            self.skipTest("NODE_TEST_ORDNER noch nicht gesetzt")
        for datei in glob.glob(os.path.join(tc.WURZEL, "*.py")) + glob.glob(os.path.join(tc.WURZEL, "tests", "*.py")) + glob.glob(os.path.join(tc.WURZEL, "*.md")):
            with open(datei, encoding="utf-8") as f:
                self.assertNotIn(ordner[0], f.read(), datei)


if __name__ == "__main__":
    unittest.main()
