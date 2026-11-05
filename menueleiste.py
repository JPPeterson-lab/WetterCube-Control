#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""WetterCube in der Menueleiste (macOS): Temperatur und Warnung deiner Geraete, ohne Fenster.

Startet zugleich WetterCube Control (Seite auf http://localhost:8765). Braucht das Paket rumps:
  python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install rumps
  .venv/bin/python menueleiste.py
(Windows/Linux: spaeter mit pystray; WetterCube Control selbst laeuft ueberall.)
"""
import os, sys, threading, webbrowser
from http.server import ThreadingHTTPServer

import rumps
import control


def kurz(d):
    s = d.get("status") or {}
    if d.get("art") != "status" or d.get("online") is False:
        return None
    return s


class Leiste(rumps.App):
    def __init__(self):
        symbol = None
        try:   # Markensymbol (einfarbiges W), macOS faerbt es passend zu Hell/Dunkel; fehlt die Datei, bleibt nur der Text
            basis = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            pfad = os.path.join(basis, "assets", "icons", "menueleiste-klein.png")
            symbol = pfad if os.path.exists(pfad) else None
        except Exception:
            pass
        super().__init__("WetterCube", title=" …", icon=symbol, template=True if symbol else None, quit_button=None)
        self.letzte = 0
        self.timer = rumps.Timer(self.aktualisieren, 10)
        self.timer.start()
        self.menu = [rumps.MenuItem("Suche läuft …")]

    def meldungen(self):
        """Neue Meldungen (DWD-Warnung, Geraet offline, Update ...) als Mitteilung am Rechner zeigen."""
        import details
        if self.letzte == 0:
            self.letzte = details.letzte_id()   # beim Start nichts Altes nachliefern
            return
        for e in details.neue_ereignisse(self.letzte):
            self.letzte = max(self.letzte, e["id"])
            import einstellungen
            if not einstellungen.mitteilung_an(e["art"]):
                continue
            try:
                rumps.notification("WetterCube Control", {"warnung": "DWD-Warnung", "problem": "Achtung"}.get(e["art"], "Hinweis"), e["text"])
            except Exception:
                pass

    def aktualisieren(self, _=None):
        liste = control.als_liste()
        items, temp, warn = [], None, 0
        for d in liste:
            s = kurz(d)
            name = d.get("name", d.get("ip", "?")).replace("WetterCube ", "")
            ip = d["ip"]
            if s:
                if temp is None:
                    temp = s.get("temp")
                w = int(s.get("dwd", 0) or 0)
                warn += 1 if w else 0
                zeile = f"{name}: {s.get('temp')} °C, {s.get('wetter', '')}" + (f"  ⚠ {w} Warnung" + ("en" if w > 1 else "") if w else "")
            else:
                zeile = f"{name}" + ("" if d.get("online", True) else "  (nicht erreichbar)")
            items.append(rumps.MenuItem(zeile, callback=lambda _, ip=ip: webbrowser.open(f"http://localhost:{control.PORT}/geraet?ip={ip}")))
        self.title = " " + (f"{temp}°" if temp is not None else "–") + (" ⚠" if warn else "")
        trenn = [None]
        self.menu.clear()
        seite = lambda pfad: (lambda _: webbrowser.open(f"http://localhost:{control.PORT}{pfad}"))
        self.menu = (items or [rumps.MenuItem("Keine Geräte gefunden")]) + trenn + [
            rumps.MenuItem("Übersicht öffnen", callback=seite("/")),
            rumps.MenuItem("Verlauf", callback=seite("/verlauf")),
            rumps.MenuItem("Wetterwand", callback=seite("/wand")),
            rumps.MenuItem("Installer", callback=seite("/installer")),
            None,
            rumps.MenuItem("Beenden", callback=lambda _: rumps.quit_application()),
        ]
        try:
            self.meldungen()
        except Exception:
            pass


def main():
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", control.PORT), control.Handler)
    except OSError:
        # Port belegt: WetterCube Control oder die Menueleiste laeuft schon (Symbol oben rechts in der Menueleiste)
        print("WetterCube laeuft schon (Port %d belegt). Symbol in der Menüleiste oben rechts, oder dort 'Beenden' und neu starten." % control.PORT)
        try:
            rumps.alert("WetterCube läuft schon", "Das Symbol ist oben rechts in der Menüleiste. Zum Neustart dort „Beenden“ wählen.")
        except Exception:
            pass
        return
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=control.hintergrund, daemon=True).start()
    Leiste().run()


if __name__ == "__main__":
    main()
