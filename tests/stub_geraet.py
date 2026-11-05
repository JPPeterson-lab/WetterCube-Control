# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Attrappe eines WetterCube-Geraets fuer die Tests von Control (keine echten Geraete noetig).

  python3 tests/stub_geraet.py PORT [--name NAME] [--passwort PW]

Steuerung waehrend des Tests ueber /_set?dwd=2&temp=5&offline=1 und Protokoll ueber /_log.
Mit --passwort verlangt sie Basic-Anmeldung (Benutzer admin) fuer alles ausser /api/status, wie die echten Geraete.
"""
import base64, http.server, json, struct, sys, zlib
from urllib.parse import parse_qs, urlparse


def png(breite=64, hoehe=40):
    roh = b"".join(b"\x00" + b"\x87\xce\xeb" * breite for _ in range(hoehe))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(roh)) + chunk(b"IEND", b"")


def main():
    port = int(sys.argv[1])
    name = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else "Test"
    passwort = sys.argv[sys.argv.index("--passwort") + 1] if "--passwort" in sys.argv else None
    zustand = {"dwd": 0, "temp": 12.5, "offline": False}
    einstellungen = {"typ": "WetterCube-Fusion-Einstellungen", "location": "Teststadt", "lat": 50.0, "lon": 8.0, "dwd_region": 5, "brightness": 80,
                     "night_modus": 1, "ntfy_aktiv": False, "ntfy_quellen": 1, "warn_region": True, "hinweis_uv": True, "muell_ab": 18, "muell_bis": 6}
    ota = {"current": "0.9.0-test", "latest": "0.9.1-test"}
    posts = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def senden(self, code, typ, b, extra=None):
            self.send_response(code); self.send_header("Content-Type", typ); self.send_header("Content-Length", str(len(b)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers(); self.wfile.write(b)

        def erlaubt(self, pfad):
            if not passwort or pfad == "/api/status" or pfad.startswith("/_"):
                return True
            a = self.headers.get("Authorization", "")
            ok = a.startswith("Basic ") and base64.b64decode(a[6:]).decode() == "admin:" + passwort
            if not ok:
                self.senden(401, "text/plain", b"Anmeldung noetig", {"WWW-Authenticate": 'Basic realm="WetterCube"'})
            return ok

        def do_GET(self):
            p = urlparse(self.path).path
            if zustand["offline"] and not p.startswith("/_"):
                self.connection.close(); return
            if not self.erlaubt(p):
                return
            if p == "/api/status":
                self.senden(200, "application/json", json.dumps({"temp": zustand["temp"], "gefuehlt": zustand["temp"] - 1, "feuchte": 55, "druck": 1012, "wind": 7,
                                                                 "wetter": "Test", "dwd": zustand["dwd"], "version": ota["current"]}).encode())
            elif p == "/backup":
                self.senden(200, "application/json", json.dumps(einstellungen).encode())
            elif p == "/log":
                self.senden(200, "text/plain; charset=utf-8", (f"WetterCube {name} Diagnose-Log\nVersion: {ota['current']}\nLetzter erfolgreicher Abruf: Wetter vor 130 Min., DWD-Warnungen vor 5 Min.\n"
                                                              "WLAN jetzt: 'TestNetz', Signal -85 dBm, IP 127.0.0.1\nFreier Heap: 40000 Bytes (intern)\nLetzter Neustart: Strom angeschlossen\n").encode())
            elif p == "/screenshot.png":
                self.senden(200, "image/png", png())
            elif p == "/ota_check":
                self.senden(200, "application/json", json.dumps({"current": ota["current"], "latest": ota["latest"], "update_available": ota["current"] != ota["latest"]}).encode())
            elif p == "/_log":
                self.senden(200, "application/json", json.dumps({"posts": posts, "einstellungen": einstellungen}).encode())
            elif p == "/_set":
                q = parse_qs(urlparse(self.path).query)
                if "dwd" in q: zustand["dwd"] = int(q["dwd"][0])
                if "temp" in q: zustand["temp"] = float(q["temp"][0])
                if "offline" in q: zustand["offline"] = q["offline"][0] == "1"
                self.senden(200, "text/plain", b"ok")
            else:
                self.senden(404, "text/plain", b"nein")

        def do_POST(self):
            p = urlparse(self.path).path
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n)
            if not self.erlaubt(p):
                return
            if p == "/restore":
                d = json.loads(body); posts.append(sorted(d)); einstellungen.update(d); self.senden(200, "text/plain", ("ok %d" % len(d)).encode())
            elif p == "/ota_update":
                ota["current"] = ota["latest"]; posts.append("OTA"); self.senden(200, "text/plain", b"ok")
            else:
                self.senden(404, "text/plain", b"nein")

    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    main()
