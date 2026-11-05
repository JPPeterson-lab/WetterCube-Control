# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Selbsttest fuer improv.py gegen ein simuliertes Geraet an einem TCP-Verbindung (pyserial socket://) (keine echte Hardware, keine Netzverbindung).

  python3 -m unittest tests.test_improv -v
"""
import os, socket, sys, threading, time, unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import improv  # noqa: E402

try:
    import serial  # noqa: F401
except ImportError:
    raise unittest.SkipTest("pyserial fehlt")


class Attrappe(threading.Thread):
    """Spielt ein Geraet nach der Improv-Beschreibung: Zustand, Info, Netze, WLAN-Daten (richtiges Passwort: "geheim123")."""

    def __init__(self, server, bereit=True):
        super().__init__(daemon=True)
        self.server, self.leser, self.laeuft, self.bereit = server, improv.Leser(), True, bereit
        self.empfangen = []
        self.verbindung = None

    def senden(self, typ, daten=b""):
        self.verbindung.sendall(improv.paket(typ, daten))

    def run(self):
        try:
            self.verbindung, _ = self.server.accept()
        except OSError:
            return
        self.verbindung.sendall(b"I (1234) wlan: Log-Zeile vor dem Paket\r\n")
        while self.laeuft:
            try:
                daten = self.verbindung.recv(512)
            except OSError:
                return
            if not daten:
                return
            for typ, d in self.leser.fuettern(daten):
                if typ != improv.T_RPC:
                    continue
                befehl, laenge = d[0], d[1]
                nutz = d[2:2 + laenge]
                self.empfangen.append((befehl, nutz))
                self.senden(improv.T_FEHLER, b"\x00")
                if befehl == improv.C_ZUSTAND:
                    self.senden(improv.T_ZUSTAND, bytes([improv.Z_BEREIT if self.bereit else improv.Z_VERBUNDEN]))
                elif befehl == improv.C_INFO:
                    nutzlast = improv.texte_kodieren("WetterCube Apex", "0.0.74", "esp32p4", "wettercube-apex")
                    self.senden(improv.T_ERGEBNIS, bytes([improv.C_INFO, len(nutzlast)]) + nutzlast)
                elif befehl == improv.C_NETZE:
                    for s, r, a in (("Heimnetz", "-55", "YES"), ("Gastnetz", "-70", "NO"), ("Heimnetz", "-80", "YES")):
                        nutzlast = improv.texte_kodieren(s, r, a)
                        self.senden(improv.T_ERGEBNIS, bytes([improv.C_NETZE, len(nutzlast)]) + nutzlast)
                    self.senden(improv.T_ERGEBNIS, bytes([improv.C_NETZE, 0]))
                elif befehl == improv.C_WLAN:
                    s = improv.texte_lesen(nutz)
                    self.senden(improv.T_ZUSTAND, bytes([improv.Z_VERBINDET]))
                    time.sleep(0.3)
                    if s[1] == "geheim123":
                        self.senden(improv.T_ZUSTAND, bytes([improv.Z_VERBUNDEN]))
                        nutzlast = improv.texte_kodieren("http://192.168.178.50/")
                        self.senden(improv.T_ERGEBNIS, bytes([improv.C_WLAN, len(nutzlast)]) + nutzlast)
                    else:
                        self.senden(improv.T_FEHLER, b"\x03")
                        self.senden(improv.T_ZUSTAND, bytes([improv.Z_BEREIT]))


class Test(unittest.TestCase):
    def setUp(self):
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = "socket://127.0.0.1:%d" % self.server.getsockname()[1]
        self.gerat = Attrappe(self.server)
        self.gerat.start()

    def tearDown(self):
        self.gerat.laeuft = False
        for s in (self.gerat.verbindung, self.server):
            try:
                if s:
                    s.close()
            except OSError:
                pass

    def verbinden(self):
        return improv._oeffnen(self.port), improv.Leser()

    def test_paket_und_leser(self):
        p = improv.rpc(improv.C_WLAN, improv.texte_kodieren("Netz", "pw"))
        self.assertTrue(p.startswith(b"IMPROV\x01\x03"))
        self.assertEqual(p[-1:], b"\n")
        self.assertEqual(sum(p[:-2]) & 0xFF, p[-2])
        l = improv.Leser()
        erg = l.fuettern(b"Log...\r\n" + p[:7]) + l.fuettern(p[7:] + b"Rest")
        self.assertEqual(len(erg), 1)
        self.assertEqual(erg[0][0], improv.T_RPC)
        kaputt = bytearray(p); kaputt[-2] ^= 0xFF
        self.assertEqual(improv.Leser().fuettern(bytes(kaputt)), [])

    def test_texte(self):
        self.assertEqual(improv.texte_lesen(improv.texte_kodieren("Käse", "", "x" * 40)), ["Käse", "", "x" * 40])

    def test_pruefen(self):
        ser, l = self.verbinden()
        r = improv.pruefen(ser, l)
        ser.close()
        self.assertEqual(r["zustand"], improv.Z_BEREIT)
        self.assertEqual(r["info"][0], "WetterCube Apex")

    def test_netze(self):
        ser, l = self.verbinden()
        n = improv.netze_suchen(ser, l)
        ser.close()
        self.assertEqual([x["ssid"] for x in n], ["Heimnetz", "Gastnetz"])
        self.assertEqual(n[0]["rssi"], -55)
        self.assertFalse(n[1]["gesichert"])

    def test_wlan_richtig_und_falsch(self):
        ser, l = self.verbinden()
        meldungen = []
        ok, text, adresse = improv.wlan_senden(ser, l, "Heimnetz", "geheim123", melden=meldungen.append)
        self.assertTrue(ok, text)
        self.assertEqual(adresse, "http://192.168.178.50/")
        self.assertTrue(meldungen)
        ok, text, adresse = improv.wlan_senden(ser, l, "Heimnetz", "falsch")
        ser.close()
        self.assertFalse(ok)
        self.assertIn("Passwort", text)

    def test_ablauf_im_hintergrund(self):
        erlaubt = [self.port]
        self.assertTrue(improv.starten("senden", self.port, "Heimnetz", "geheim123", erlaubt))
        for _ in range(100):
            if not improv.status()["laeuft"]:
                break
            time.sleep(0.1)
        st = improv.status()
        self.assertTrue(st["ok"], st)
        self.assertNotIn("geheim123", str(st))
        with self.assertRaises(ValueError):
            improv.starten("senden", "/dev/ttyFALSCH", "x", "y", erlaubt)
        with self.assertRaises(ValueError):
            improv.starten("senden", self.port, "", "y", erlaubt)

class TestWlanUsbProdukte(unittest.TestCase):
    def test_wlan_usb_nur_fuer_geraete_mit_improv(self):
        """Der Assistent zeigt das Formular WLAN per USB nur fuer Geraete, die es koennen; sonst die Anleitung fuer das Einrichtungs-WLAN (zum Beispiel der interne Node)."""
        import installer
        flags = {p["key"]: p["wlan_usb"] for p in installer.produkte()}
        self.assertIn("plus", flags)        # Plus und Plus Europe werden ueber den eigenen Webspace wieder angeboten ...
        self.assertIn("europe", flags)
        self.assertTrue(flags["plus"])      # ... und seit Plus 2.1.18 / Europe beta9 mit Formular fuer WLAN per USB
        self.assertTrue(flags["europe"])
        self.assertEqual(set(k for k, v in flags.items() if v), set(installer.WLAN_USB))
        self.assertTrue(installer.PRODUKTE["plus"][1].startswith(installer.WEBSPACE))
        self.assertEqual(installer.WEB["plus"], ("plus", "manifest.json"))

    def test_assistent_hat_den_alternativen_weg(self):
        import seiten
        self.assertIn("192.168.4.1", seiten.ASSISTENT)
        self.assertIn("wlanAnsicht", seiten.ASSISTENT)


if __name__ == "__main__":
    unittest.main()
