@echo off
rem Nur die Uebersichtsseite, ohne Taskleiste (keine Installation noetig, nur Python 3). Fenster offen lassen.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
start "" "http://localhost:8765"
%PY% control.py
pause
