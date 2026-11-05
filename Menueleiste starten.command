#!/bin/bash
# Doppelklick im Finder: WetterCube in der Menueleiste (startet auch WetterCube Control auf http://localhost:8765)
cd "$(dirname "$0")" || exit 1
fehler() { echo; echo "Fehler: $1"; echo "Bitte diesen Text an Claude schicken."; read -n 1 -s -r -p "Taste druecken zum Schliessen"; exit 1; }
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c "import rumps, esptool, serial, certifi, keyring" 2>/dev/null; then
  echo "Einmalige Einrichtung ..."
  rm -rf .venv; python3 -m venv .venv || fehler "python3 fehlt (Befehl: xcode-select --install)"
  .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -q rumps esptool pyserial certifi keyring || fehler "rumps, esptool oder pyserial konnten nicht installiert werden"
fi
.venv/bin/python menueleiste.py || fehler "menueleiste.py ist abgestuerzt (siehe oben)"
