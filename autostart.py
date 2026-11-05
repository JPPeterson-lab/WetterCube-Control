# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Autostart beim Anmelden: damit der Verlauf lueckenlos mitlaeuft. Nur auf ausdruecklichen Klick des Nutzers (Seite Einstellungen).

Mac: Eintrag in ~/Library/LaunchAgents (wirkt ab der naechsten Anmeldung), Windows: Wert in HKCU\\...\\Run, Linux: ~/.config/autostart.
Nur im gebauten Programm moeglich (aus dem Quellcode gibt es keinen festen Pfad zum Starten).
"""
import os, plistlib, sys

LABEL = "de.wettercube.control"
TEST_ORDNER = os.environ.get("WETTERCUBE_AUTOSTART_ORDNER")   # nur fuer Tests: Zielordner statt der echten Systemstelle


def verfuegbar():
    return bool(getattr(sys, "frozen", False) or os.environ.get("WETTERCUBE_AUTOSTART_TEST"))


def _programm():
    """Pfad zum Programm: auf dem Mac die .app, sonst die exe."""
    exe = os.environ.get("WETTERCUBE_AUTOSTART_TEST") or sys.executable
    if sys.platform == "darwin" and ".app/" in exe:
        return exe.split(".app/")[0] + ".app"
    return exe


def _mac_datei():
    return os.path.join(TEST_ORDNER or os.path.expanduser("~/Library/LaunchAgents"), LABEL + ".plist")


def _linux_datei():
    return os.path.join(TEST_ORDNER or os.path.expanduser("~/.config/autostart"), "wettercube-control.desktop")


def aktiv():
    if sys.platform == "darwin":
        return os.path.exists(_mac_datei())
    if sys.platform.startswith("win") and not TEST_ORDNER:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, "WetterCubeControl")
                return True
        except OSError:
            return False
    return os.path.exists(_linux_datei())


def setzen(an):
    """Autostart ein- oder ausschalten; wirft OSError/ValueError mit verstaendlichem Text."""
    if not verfuegbar():
        raise ValueError("Autostart gibt es nur im Programm (App/exe), nicht beim Start aus dem Quellcode.")
    prog = _programm()
    if sys.platform == "darwin":
        pfad = _mac_datei()
        if an:
            os.makedirs(os.path.dirname(pfad), exist_ok=True)
            with open(pfad, "wb") as f:
                plistlib.dump({"Label": LABEL, "ProgramArguments": ["/usr/bin/open", "-a", prog], "RunAtLoad": True}, f)
        elif os.path.exists(pfad):
            os.remove(pfad)
    elif sys.platform.startswith("win") and not TEST_ORDNER:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as k:
            if an:
                winreg.SetValueEx(k, "WetterCubeControl", 0, winreg.REG_SZ, f'"{prog}"')
            else:
                try:
                    winreg.DeleteValue(k, "WetterCubeControl")
                except FileNotFoundError:
                    pass
    else:
        pfad = _linux_datei()
        if an:
            os.makedirs(os.path.dirname(pfad), exist_ok=True)
            with open(pfad, "w", encoding="utf-8") as f:
                f.write(f"[Desktop Entry]\nType=Application\nName=WetterCube Control\nExec=\"{prog}\"\nX-GNOME-Autostart-enabled=true\n")
        elif os.path.exists(pfad):
            os.remove(pfad)
    return aktiv()
