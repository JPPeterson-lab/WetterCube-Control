#!/bin/bash
# Doppelklick im Finder: startet WetterCube Control (Seite auf http://localhost:8765, mit Installer)
# Beim ersten Mal richtet sich das Programm selbst ein (esptool und pyserial fuer den Installer).
cd "$(dirname "$0")" || exit 1
fehler() { echo; echo "Fehler: $1"; echo "Bitte diesen Text an Claude schicken."; read -n 1 -s -r -p "Taste druecken zum Schliessen"; exit 1; }
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c "import esptool, serial, certifi, keyring" 2>/dev/null; then
  echo "Einmalige Einrichtung ..."
  [ -x .venv/bin/python ] || python3 -m venv .venv || fehler "python3 fehlt (Befehl: xcode-select --install)"
  .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -q esptool pyserial certifi keyring || fehler "esptool oder pyserial konnten nicht installiert werden"
fi
( sleep 2; open "http://localhost:8765" ) &
.venv/bin/python control.py || fehler "control.py ist abgestuerzt (siehe oben). Laeuft schon eine andere Instanz? Dann dort Strg+C."
