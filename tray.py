#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""WetterCube im Infobereich der Taskleiste (Windows, auch Linux): Temperatur und Warnung deiner Geraete.

Startet zugleich WetterCube Control (Seite auf http://localhost:8765). Braucht pystray und Pillow
(das erledigt `Control (Windows) starten.bat` beim ersten Mal selbst). Auf dem Mac stattdessen menueleiste.py.
"""
import threading, webbrowser
from http.server import ThreadingHTTPServer

import pystray
from PIL import Image, ImageDraw, ImageFont

import control


def symbol(temp, warn, online):
    """64x64-Symbol: Temperatur als Zahl, rote Ecke bei DWD-Warnung, grau ohne Verbindung."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 63, 63), 12, fill=(11, 37, 69, 255) if online else (90, 100, 110, 255))   # Navy der Marke
    text = "–" if temp is None else str(int(round(float(temp))))
    font = None
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            font = ImageFont.truetype(name, 40 if len(text) < 3 else 30)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    d.text(((64 - (box[2] - box[0])) / 2 - box[0], (64 - (box[3] - box[1])) / 2 - box[1] + 2), text, font=font, fill=(135, 206, 235, 255))   # Himmelblau der Marke
    if warn:
        d.ellipse((38, 0, 63, 25), fill=(206, 75, 17, 255), outline="white", width=2)   # Orange der Marke
        d.text((46, 3), "!", font=font if font else None, fill="white")
    return img


def lesen():
    """(Temperatur des ersten Geraets mit Werten, Zahl der Geraete mit Warnung, Menuezeilen [(Text, ip)])"""
    temp, warn, zeilen = None, 0, []
    for d in control.als_liste():
        s = d.get("status") or {}
        name = d.get("name", d.get("ip", "?")).replace("WetterCube ", "")
        if d.get("art") == "status" and d.get("online") is not False and s:
            if temp is None:
                temp = s.get("temp")
            w = int(s.get("dwd", 0) or 0)
            warn += 1 if w else 0
            zeilen.append((f"{name}: {s.get('temp')} °C, {s.get('wetter', '')}" + (f"  ⚠ {w} Warnung" + ("en" if w > 1 else "") if w else ""), d["ip"]))
        else:
            zeilen.append((name + ("" if d.get("online", True) else "  (nicht erreichbar)"), d["ip"]))
    return temp, warn, zeilen


def oeffnen(ip):
    """pystray erlaubt nur Aktionen mit hoechstens zwei Parametern (icon, item): darum diese Fabrik statt Standardwert im lambda"""
    return lambda icon, item: webbrowser.open(f"http://localhost:{control.PORT}/geraet?ip={ip}")


def menue():
    _, _, zeilen = lesen()
    punkte = [pystray.MenuItem(t, oeffnen(ip)) for t, ip in zeilen]
    if not punkte:
        punkte = [pystray.MenuItem("Keine Geräte gefunden (Suche läuft …)", None, enabled=False)]
    punkte += [pystray.Menu.SEPARATOR,
               pystray.MenuItem("Übersicht öffnen", lambda icon, item: webbrowser.open(f"http://localhost:{control.PORT}"), default=True),
               pystray.MenuItem("Verlauf", lambda icon, item: webbrowser.open(f"http://localhost:{control.PORT}/verlauf")),
               pystray.MenuItem("Wetterwand", lambda icon, item: webbrowser.open(f"http://localhost:{control.PORT}/wand")),
               pystray.MenuItem("Installer", lambda icon, item: webbrowser.open(f"http://localhost:{control.PORT}/installer")),
               pystray.MenuItem("Beenden", lambda icon, item: icon.stop())]
    return punkte


def aktualisieren(icon):
    import time, details
    letzte = 0
    while icon.visible or True:
        try:
            if letzte == 0:
                letzte = details.letzte_id()   # beim Start nichts Altes nachliefern
            for e in details.neue_ereignisse(letzte):
                letzte = max(letzte, e["id"])
                import einstellungen
                if not einstellungen.mitteilung_an(e["art"]):
                    continue
                try:
                    icon.notify(e["text"], {"warnung": "DWD-Warnung", "problem": "Achtung"}.get(e["art"], "Hinweis"))
                except Exception:
                    pass
            temp, warn, zeilen = lesen()
            icon.icon = symbol(temp, warn, bool(zeilen))
            icon.title = "WetterCube: " + ("keine Geräte" if not zeilen else (f"{temp} °C" if temp is not None else "") + (", DWD-Warnung" if warn else ""))
            icon.update_menu()
        except Exception as e:
            print("Fehler:", e)
        time.sleep(10)


def main():
    threading.Thread(target=control.hintergrund, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", control.PORT), control.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    icon = pystray.Icon("wettercube", symbol(None, 0, False), "WetterCube: suche Geräte …", pystray.Menu(menue))
    icon.run(setup=lambda i: (setattr(i, "visible", True), threading.Thread(target=aktualisieren, args=(i,), daemon=True).start()))


if __name__ == "__main__":
    main()
