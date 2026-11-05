# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Attrappe eines WetterCube Node fuer die Tests von Control (keine echten Geraete noetig).

  python3 tests/stub_node.py PORT [--name NAME] [--seite pfad/zu/webseiten.h]

Spricht denselben Vertrag wie die Firmware: /api/status, /api/config (GET/POST), /api/kalibrierung/punkt|loeschen|kurve,
/backup, /restore (Typ WetterCube-Node-Einstellungen), /log. Steuerung ueber /_set?temp=..&offline=1, Protokoll ueber /_log.
Mit --seite wird zusaetzlich die echte Weboberflaeche aus der Firmware (webseiten.h) unter / ausgeliefert, zum Ansehen im Browser.
"""
import http.server, json, re, sys
from urllib.parse import parse_qs, urlparse

LIMIT = {"kt": 8, "kf": 5, "kp": 5}


def main():
    port = int(sys.argv[1])
    name = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else "WetterCube Node"
    seite = None
    if "--seite" in sys.argv:
        t = open(sys.argv[sys.argv.index("--seite") + 1], encoding="utf-8").read()
        seite = re.search(r'SEITE_HTML\[\] PROGMEM = R"HTML\((.*?)\)HTML"', t, re.S).group(1)
    z = {"roh_t": 24.2, "roh_f": 50.0, "roh_p": 1008.0, "offline": False}
    cfg = {"name": name, "wifi_ssid": "TestNetz", "wifi_pw_gesetzt": True, "mqtt_host": "", "mqtt_port": 1883, "mqtt_user": "", "mqtt_base": "wettercube/node", "mqtt_pw_gesetzt": False,
           "hoehe": 30.0, "oled_an": True, "oled_dreh": False, "t_off": 0.0, "f_off": -2.8, "p_off": 1.7, "kt": [], "kf": [], "kp": []}
    posts = []

    def status():
        t = z["roh_t"] + (cfg["kt"][0][1] - cfg["kt"][0][0] if cfg["kt"] else cfg["t_off"])
        return {"geraet": "node", "name": cfg["name"], "version": "0.1.0", "hw": "esp32c3", "temp": round(t, 1), "feuchte": round(z["roh_f"] + cfg["f_off"], 1), "druck": round(z["roh_p"] + cfg["p_off"], 1),
                "taupunkt": 10.0, "feuchte_phys": z["roh_f"], "rssi": -61, "uptime_s": 4000, "heap": 150000, "heap_min": 140000, "ip": "127.0.0.1", "setup": False,
                "mqtt_aktiv": False, "mqtt": False, "sensor": {"aht": True, "bmp": True},
                "roh": {"temp": z["roh_t"], "feuchte": z["roh_f"], "druck": z["roh_p"], "druck_nn": z["roh_p"]}}

    def setze(d):
        n = 0
        for k, v in d.items():
            if k in ("typ", "version"):
                continue
            if k in LIMIT:
                if not isinstance(v, list) or len(v) > LIMIT[k]:
                    return None, "Zu viele Punkte"
            elif k in cfg or k in ("wifi_pw", "mqtt_pw"):
                pass
            else:
                continue
            cfg[k] = v
            n += 1
        return n, ""

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def senden(self, code, typ, b):
            b = b if isinstance(b, bytes) else b.encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", typ); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def js(self, d, code=200):
            self.senden(code, "application/json", json.dumps(d))

        def do_GET(self):
            p, q = urlparse(self.path).path, parse_qs(urlparse(self.path).query)
            if z["offline"] and not p.startswith("/_"):
                self.connection.close(); return
            if p == "/" and seite:
                self.senden(200, "text/html; charset=utf-8", seite)
            elif p == "/node/manifest.json":      # interne Firmware-Quelle (Form wie bei Fusion/Next)
                self.js({"name": "WetterCube Node", "version": "0.1.0", "builds": [{"chipFamily": "ESP32-C3", "improv": False, "parts": [
                    {"path": "bootloader.bin", "offset": 0}, {"path": "partitions.bin", "offset": 32768}, {"path": "boot_app0.bin", "offset": 57344}, {"path": "firmware.bin", "offset": 65536}]}]})
            elif p == "/node/versionen.json":
                self.js(["0.1.0"])
            elif p == "/node/version.json":
                self.js({"version": "0.1.0"})
            elif p.startswith("/node/") and p.endswith(".bin"):
                self.senden(200, "application/octet-stream", b"\xe9" * 4096)
            elif p == "/api/status":
                self.js(status())
            elif p == "/api/config":
                self.js(cfg)
            elif p == "/api/kalibrierung/kurve":
                g = q.get("groesse", ["temp"])[0]
                lo, hi = {"temp": (14, 34), "feuchte": (0, 100), "druck": (990, 1030)}.get(g, (0, 1))
                k = cfg[{"temp": "kt", "feuchte": "kf", "druck": "kp"}.get(g, "kt")]
                xs = [lo + (hi - lo) * i / 40 for i in range(41)]
                self.js({"x": xs, "y": [x for x in xs], "punkte": k, "aktuell": z["roh_t"]})
            elif p == "/api/scan":
                self.js([{"ssid": "TestNetz", "rssi": -50}, {"ssid": "Nachbar", "rssi": -80}])
            elif p == "/backup":
                d = {"typ": "WetterCube-Node-Einstellungen", "version": "0.1.0"}
                d.update({k: v for k, v in cfg.items() if k not in ("wifi_ssid", "wifi_pw_gesetzt", "mqtt_pw_gesetzt")})
                self.senden(200, "application/json", json.dumps(d))
            elif p == "/log":
                self.senden(200, "text/plain; charset=utf-8", "WetterCube Node Diagnose-Log\nVersion: 0.1.0\n")
            elif p == "/_log":
                self.js({"posts": posts, "config": cfg})
            elif p == "/_set":
                for k, v in parse_qs(urlparse(self.path).query).items():
                    if k == "offline": z["offline"] = v[0] == "1"
                    elif k in ("roh_t", "roh_f", "roh_p"): z[k] = float(v[0])
                self.senden(200, "text/plain", "ok")
            else:
                self.senden(404, "text/plain", "nein")

        def do_POST(self):
            p = urlparse(self.path).path
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                d = json.loads(body or b"{}")
            except ValueError:
                return self.js({"ok": False, "fehler": "Kein gueltiges JSON"}, 400)
            if p == "/api/config":
                n, f = setze(d)
                if n is None:
                    return self.js({"ok": False, "fehler": f}, 400)
                posts.append(("config", sorted(d))); self.js({"ok": True, "felder": n, "neustart": False})
            elif p == "/api/kalibrierung/punkt":
                g = d.get("groesse"); k = {"temp": "kt", "feuchte": "kf", "druck": "kp"}.get(g)
                if not k or not isinstance(d.get("ref"), (int, float)):
                    return self.js({"ok": False, "fehler": "groesse und ref noetig"}, 400)
                if len(cfg[k]) >= LIMIT[k]:
                    return self.js({"ok": False, "fehler": "Hoechstens %d Punkte" % LIMIT[k]}, 409)
                x = {"kt": z["roh_t"], "kf": z["roh_f"], "kp": z["roh_p"]}[k]
                cfg[k].append([x, d["ref"]]); cfg[k].sort()
                posts.append(("punkt", g, d["ref"])); self.js({"ok": True, "roh": x, "punkte": len(cfg[k])})
            elif p == "/restore":
                if d.get("typ") != "WetterCube-Node-Einstellungen":
                    return self.senden(400, "text/plain", "Falscher Typ")
                n, f = setze(d)
                if n is None:
                    return self.senden(400, "text/plain", f)
                posts.append(("restore", sorted(d))); self.senden(200, "text/plain", "ok %d" % n)
            else:
                self.senden(404, "text/plain", "nein")

    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    main()
