@echo off
rem WetterCube in der Taskleiste (Windows). Doppelklick. Beim ersten Mal richtet sich das Programm selbst ein.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Einmalige Einrichtung, das dauert eine Minute ...
  where py >nul 2>nul && (py -3 -m venv .venv) || (where python >nul 2>nul && python -m venv .venv)
  if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Python fehlt. Bitte Python 3 von https://www.python.org/downloads/ installieren
    echo ^(Haken "Add python.exe to PATH" setzen^) und diese Datei noch einmal starten.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -q pystray pillow esptool pyserial certifi keyring
  if errorlevel 1 ( echo Einrichtung fehlgeschlagen. & pause & exit /b 1 )
)
start "" ".venv\Scripts\pythonw.exe" tray.py
echo WetterCube laeuft jetzt unten rechts in der Taskleiste (ggf. unter dem Pfeil ^). Seite: http://localhost:8765
timeout /t 5 >nul
