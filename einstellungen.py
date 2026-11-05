# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Einstellungen von WetterCube Control (eine kleine JSON-Datei im Home-Ordner): Namen der Geraete, ausgeblendete und selbst
hinzugefuegte Geraete, Mitteilungen, automatische Sicherung, eigene Alarme."""
import json, os, threading, time

DATEI = os.environ.get("WETTERCUBE_EINSTELLUNGEN") or os.path.join(os.path.expanduser("~"), ".wettercube-control-einstellungen.json")
_sperre = threading.Lock()
STANDARD = {
    "alias": {},                                                       # ip -> frei gewaehlter Name
    "ausgeblendet": [],                                                # ips, die nicht angezeigt werden
    "hinzugefuegt": [],                                                # Adressen, die der Nutzer von Hand eingetragen hat
    "mitteilungen": {"warnung": True, "problem": True, "info": True},  # welche Meldungsarten als Mitteilung am Rechner erscheinen
    "auto_sichern": {"modus": "aus", "behalten": 14, "letzte": 0},     # aus | taeglich | woechentlich
    "auto_entfernen_tage": 0,                                          # nicht erreichbare Geraete nach so vielen Tagen automatisch entfernen (0 = nie)
    "versionssuche": False,                                            # Control sucht von selbst nach neuen Versionen (aus = nur auf Knopfdruck/im Installer)
    "alarme": [],                                                      # eigene Regeln, siehe regeln_pruefen in details.py
}
_cache = None


def _lesen():
    global _cache
    if _cache is None:
        daten = {}
        try:
            with open(DATEI, encoding="utf-8") as f:
                daten = json.load(f)
        except (OSError, ValueError):
            pass
        _cache = json.loads(json.dumps(STANDARD))
        for k, v in daten.items():
            if k in _cache:
                if isinstance(_cache[k], dict) and isinstance(v, dict):
                    _cache[k].update(v)
                else:
                    _cache[k] = v
    return _cache


def holen():
    """Kopie aller Einstellungen."""
    with _sperre:
        return json.loads(json.dumps(_lesen()))


def aendern(funktion):
    """funktion(dict) aendert die Einstellungen; danach wird gespeichert."""
    with _sperre:
        d = _lesen()
        funktion(d)
        try:
            os.makedirs(os.path.dirname(DATEI) or ".", exist_ok=True)
            with open(DATEI, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        except OSError:
            pass
        return json.loads(json.dumps(d))


def alias_von(ip):
    with _sperre:
        return _lesen()["alias"].get(ip)


def ausgeblendet(ip):
    with _sperre:
        return ip in _lesen()["ausgeblendet"]


def mitteilung_an(art):
    with _sperre:
        return bool(_lesen()["mitteilungen"].get(art, True))


# ── Eigene Alarme ────────────────────────────────────────────────────────────
METRIKEN = {"temp": "Temperatur (°C)", "gefuehlt": "Gefühlte Temperatur (°C)", "feuchte": "Luftfeuchte (%)", "druck": "Luftdruck (hPa)",
            "wind": "Wind (km/h)", "uv": "UV-Index", "aqi": "Luftqualität (AQI)", "pm25": "Feinstaub PM2,5"}


def alarm_pruefen(a):
    """Eine vom Nutzer eingegebene Regel bereinigen; wirft ValueError bei Unsinn."""
    if a.get("metrik") not in METRIKEN:
        raise ValueError("Unbekannte Messgröße")
    if a.get("op") not in ("<", ">"):
        raise ValueError("Bedingung muss „unter“ oder „über“ sein")
    try:
        grenze = float(a.get("grenze"))
    except (TypeError, ValueError):
        raise ValueError("Der Grenzwert muss eine Zahl sein")
    name = str(a.get("name") or "").strip()[:60] or f"{METRIKEN[a['metrik']]} {a['op']} {grenze:g}"
    return {"id": str(a.get("id") or int(time.time() * 1000)), "name": name, "geraet": str(a.get("geraet") or "*")[:60], "metrik": a["metrik"],
            "op": a["op"], "grenze": grenze, "aktiv": bool(a.get("aktiv", True))}
