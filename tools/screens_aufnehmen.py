#!/usr/bin/env python3
"""Nimmt die Bildschirmfotos von WetterCube Control im Demo-Modus auf (erfundene Geraete, nichts wird gespeichert oder abgefragt).
Braucht Google Chrome (headless). Aufruf:  python3 tools/screens_aufnehmen.py [Zielordner]    Standard: assets/screens
Hell und dunkel je Seite; Hoehen wie bisher."""
import os, subprocess, sys, time, urllib.request
HIER = os.path.dirname(os.path.abspath(__file__))
ZIEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HIER, "..", "assets", "screens")
PORT = 8791
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SEITEN = [("uebersicht", "/", 880), ("geraet", "/geraet?ip=192.168.1.50", 1560), ("verlauf", "/verlauf", 900), ("wand", "/wand", 800),
          ("kopieren", "/kopieren", 760), ("installer", "/installer", 860), ("einstellungen", "/einstellungen", 1240)]
os.makedirs(ZIEL, exist_ok=True)
py = os.path.join(HIER, "..", ".venv", "bin", "python")
srv = subprocess.Popen([py if os.path.exists(py) else sys.executable, os.path.join(HIER, "..", "control.py"), "--demo", "--port", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen("http://localhost:%d/api/geraete" % PORT, timeout=1); break
        except Exception:
            time.sleep(0.5)
    for name, pfad, hoehe in SEITEN:
        for art, extra in (("hell", []), ("dunkel", ["--force-dark-mode"])):
            aus = os.path.abspath(os.path.join(ZIEL, "%s-%s.png" % (name, art)))
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars"] + extra + ["--window-size=1280,%d" % hoehe, "--virtual-time-budget=6000", "--screenshot=" + aus, "http://localhost:%d%s" % (PORT, pfad)], stderr=subprocess.DEVNULL, check=True)
            print(aus)
finally:
    srv.terminate()
