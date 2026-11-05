# WetterCube Control als Dauerdienst (NAS, Raspberry Pi, Heimserver): nur zum Ansehen, erreichbar im Heimnetz auf Port 8765.
# Bauen:  docker build -f dauerbetrieb/Dockerfile -t wettercube-control .
# Starten: siehe docker-compose.yml (Host-Netzwerk, sonst findet der Container die Geraete nicht)
FROM python:3.12-slim
WORKDIR /app
COPY control.py details.py verlauf.py sicherung.py seiten.py installer.py einstellungen.py autostart.py passwoerter.py ./
COPY assets/logo assets/logo
COPY assets/icons assets/icons
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "control.py", "--lan"]
