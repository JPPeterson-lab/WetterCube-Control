#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Einstieg der eigenstaendigen Programme (Mac: WetterCube Control.app, Windows: WetterCube Control.exe).

Ein Klick genuegt: Symbol in Menueleiste (Mac) bzw. Taskleiste (Windows), die Uebersichtsseite oeffnet sich im Browser.
Wird das Programm ein zweites Mal gestartet, oeffnet es nur die Seite der laufenden Instanz.
Intern ruft der Installer esptool ueber dasselbe Programm auf (`--esptool ...`), weil es keinen separaten Python-Aufruf gibt.
"""
import os, socket, sys, threading, webbrowser

PORT = int(os.environ.get("WETTERCUBE_PORT") or 8765)


def laeuft_schon():
    try:
        socket.create_connection(("127.0.0.1", PORT), 0.5).close()
        return True
    except OSError:
        return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--esptool":     # Unterprozess des Installers
        # Fehler von esptool (z. B. "Failed to connect") duerfen nie als Absturzfenster erscheinen: _main() faengt sie ab
        # und meldet sie als Text mit Rueckgabewert; alles andere wird ebenfalls nur als Text ausgegeben.
        for _n in ("stdout", "stderr"):   # fensterlose Windows-Programme haben manchmal keine Standardausgabe
            if getattr(sys, _n) is None:
                setattr(sys, _n, open(os.devnull, "w"))
        try:
            import esptool
            sys.argv = ["esptool"] + sys.argv[2:]
            esptool._main()
        except SystemExit as e:
            raise
        except BaseException as e:   # noqa: BLE001
            print("Fehler: %s: %s" % (type(e).__name__, e))
            sys.exit(1)
        return
    if laeuft_schon():
        webbrowser.open(f"http://localhost:{PORT}")
        return
    if not os.environ.get("WETTERCUBE_KEIN_BROWSER"):   # fuer Tests
        threading.Timer(2.0, webbrowser.open, (f"http://localhost:{PORT}",)).start()
    if sys.platform == "darwin":
        import menueleiste
        menueleiste.main()
    else:
        import tray
        tray.main()


if __name__ == "__main__":
    main()
