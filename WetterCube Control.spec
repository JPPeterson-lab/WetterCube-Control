# PyInstaller-Spezifikation (Mac und Windows): .venv/bin/pyinstaller "WetterCube Control.spec"
import sys
from PyInstaller.utils.hooks import collect_all
datas, binaries, hidden = [("assets/logo", "assets/logo"), ("assets/icons", "assets/icons")], [], ["menueleiste", "tray", "installer", "control", "details", "verlauf", "sicherung", "seiten", "einstellungen", "autostart", "passwoerter", "protokolle"]
for paket in ("esptool", "serial", "certifi", "keyring"):
    d, b, h = collect_all(paket)
    datas += d; binaries += b; hidden += h
if sys.platform == "darwin":
    hidden += ["rumps"]
else:
    hidden += ["pystray", "PIL", "pystray._win32"]

a = Analysis(["app.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WetterCube Control", console=False, upx=False,
          icon=("assets/icons/WetterCube Control.icns" if sys.platform == "darwin" else "assets/icons/WetterCube Control.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="WetterCube Control")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="WetterCube Control.app", bundle_identifier="de.wettercube.control", icon="assets/icons/WetterCube Control.icns",
                 info_plist={"LSUIElement": True, "CFBundleShortVersionString": "1.0.0", "NSHumanReadableCopyright": "Jan Althaus"})
