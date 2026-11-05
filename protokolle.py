# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Protokoll-Sammler: Control liest das Diagnose-Log der Geraete ohnehin alle 5 Minuten (Gesundheit). Die Geraete halten nur die
letzten paar hundert Zeilen; hier werden die neuen Zeilen je Geraet und Tag in Dateien angehaengt, damit bei einem Fehler die
Vorgeschichte da ist. Alles bleibt auf diesem Rechner. Ordner: ~/WetterCube-Protokolle/<Geraet>/<JJJJ-MM-TT>.log, 30 Tage.
"""
import json, os, re, threading, time

ORDNER = os.environ.get("WETTERCUBE_PROTOKOLLE") or os.path.join(os.path.expanduser("~"), "WetterCube-Protokolle")
TAGE = 30
_ZEILE = re.compile(r"^(\d\d:\d\d:\d\d |\[\d+s\] |\[\d+:\d\d:\d\d\] )")   # Logzeile: Uhrzeit, Sekunden seit dem Start oder Laufzeit (Sensorknoten)
_MESSUNG = re.compile(r"^\[\d+:\d\d:\d\d\] T=")                       # Messzeile des Sensorknotens alle 10 s: steht schon im Verlauf, nicht sammeln
_letzte = {}                                                 # ip -> letzte gespeicherte Zeilen (zum Erkennen, was neu ist)
_zustand = {}                                                # ip -> Zeit der letzten Zustandszeile
_sperre = threading.Lock()
_zuo_sperre = threading.Lock()
_fortgesetzt = {}
_aufgeraeumt = [0]


def an():
    import einstellungen
    return bool(einstellungen.holen().get("protokolle", True))


def _sauber(name, ip):
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (name or ip).replace(" ", "-")).strip("-") or ip.replace(".", "-")


def ordner_von(name, ip):
    """Ordner je Geraet. Er bleibt an der Adresse haengen: wird das Geraet in Control umbenannt, schreibt es weiter in denselben Ordner
    (Zuordnung in .zuordnung.json)."""
    datei = os.path.join(ORDNER, ".zuordnung.json")
    with _zuo_sperre:
        try:
            with open(datei, encoding="utf-8") as f:
                zuo = json.load(f)
        except (OSError, ValueError):
            zuo = {}
        if ip not in zuo:
            zuo[ip] = _sauber(name, ip)
            try:
                os.makedirs(ORDNER, exist_ok=True)
                with open(datei, "w", encoding="utf-8") as f:
                    json.dump(zuo, f, ensure_ascii=False, indent=1)
            except OSError:
                pass
        return os.path.join(ORDNER, zuo[ip])


def _schwanz_aus_datei(o):
    """Letzte Logzeilen der neuesten Tagesdatei (nach einem Neustart von Control: sonst wuerde das ganze Log noch einmal angehaengt)."""
    try:
        tage = sorted(d for d in os.listdir(o) if re.fullmatch(r"\d{4}-\d\d-\d\d\.log", d))
        if not tage:
            return None
        with open(os.path.join(o, tage[-1]), encoding="utf-8", errors="replace") as f:
            z = [x.rstrip("\n") for x in f if _ZEILE.match(x)]
        return z[-50:] or None
    except OSError:
        return None


def neue_zeilen(alt, neu):
    """alt, neu: Zeilen in zeitlicher Reihenfolge. Gibt (neue Zeilen, Luecke) zurueck: Luecke, wenn der alte Stand nicht mehr im Log steht
    (Neustart oder zu lange nicht gelesen)."""
    if not alt:
        return neu, False
    for laenge in (5, 3, 1):                                   # die letzten gespeicherten Zeilen im neuen Log suchen (von hinten)
        if len(alt) < laenge:
            continue
        schwanz = alt[-laenge:]
        for i in range(len(neu) - laenge, -1, -1):
            if neu[i:i + laenge] == schwanz:
                return neu[i + laenge:], False
    return neu, True


def _sekunden(z):
    m = re.match(r"^\[?(\d+):(\d\d):(\d\d)", z)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def neueste_zuerst(zeilen):
    """Reihenfolge am Log selbst erkennen: absteigende Zeiten ueberwiegen -> neueste zuerst (Mitternacht und Neustarts stoeren nur einzelne Paare)."""
    ab = auf = 0
    t = [x for x in (_sekunden(z) for z in zeilen) if x is not None]
    for a, b in zip(t, t[1:]):
        if b < a:
            ab += 1
        elif b > a:
            auf += 1
    return ab >= auf


def sammeln(ip, name, text, info=None):
    if not an():
        return
    o = ordner_von(name, ip)
    zeilen = [z for z in text.splitlines() if _ZEILE.match(z) and not _MESSUNG.match(z)]
    if neueste_zuerst(zeilen):
        zeilen.reverse()                                       # Fusion, Apex, Next, Plus: neueste zuerst; der Sensorknoten: aelteste zuerst
    with _sperre:
        erstes = ip not in _letzte
        if erstes:
            _letzte[ip] = _schwanz_aus_datei(o)   # Control wurde neu gestartet: an die vorhandene Datei anschliessen
            _fortgesetzt[ip] = _letzte[ip] is not None
        neu, luecke = neue_zeilen(_letzte.get(ip), zeilen)
        _letzte[ip] = zeilen[-50:]
        jetzt = time.time()
        zustand = info is not None and jetzt - _zustand.get(ip, 0) >= 3600
        if zustand:
            _zustand[ip] = jetzt
    if not neu and not zustand:
        return
    os.makedirs(o, exist_ok=True)
    with open(os.path.join(o, time.strftime("%Y-%m-%d") + ".log"), "a", encoding="utf-8") as f:
        if erstes and not _fortgesetzt.get(ip):
            f.write(f"=== {time.strftime('%H:%M:%S')} Control beginnt mit dem Sammeln ({name}, {ip}) ===\n")
        elif luecke:
            f.write(f"=== {time.strftime('%H:%M:%S')} Lücke: ältere Zeilen fehlen (Neustart des Geräts oder Control lief nicht) ===\n")
        for z in neu:
            f.write(z + "\n")
        if zustand:
            f.write(f"--- {time.strftime('%H:%M:%S')} Zustand: " + zustand_text(info) + "\n")
    aufraeumen()


def zustand_text(i):
    t = []
    if i.get("heap") is not None:
        t.append(f"Speicher frei {i['heap'] // 1024} KB" + (f" (tiefster {i['heap_min'] // 1024} KB, Block {i['heap_block'] // 1024} KB)" if i.get("heap_min") is not None else ""))
    if i.get("uptime_min") is not None:
        t.append(f"Laufzeit {i['uptime_min']} Min.")
    if i.get("wlan_dbm") is not None:
        t.append(f"WLAN {i['wlan_dbm']} dBm")
    if i.get("neustart"):
        t.append(f"letzter Neustart: {i['neustart']}")
    return ", ".join(t) or "keine Angaben"


def aufraeumen():
    if time.time() - _aufgeraeumt[0] < 86400:
        return
    _aufgeraeumt[0] = time.time()
    grenze = time.time() - TAGE * 86400
    try:
        for g in os.listdir(ORDNER):
            pfad = os.path.join(ORDNER, g)
            if not os.path.isdir(pfad):
                continue
            for d in os.listdir(pfad):
                if d.endswith(".log") and os.path.getmtime(os.path.join(pfad, d)) < grenze:
                    os.remove(os.path.join(pfad, d))
    except OSError:
        pass


def liste(name, ip):
    """Gesammelte Tage eines Geraets: [{'tag','groesse'}], neueste zuerst."""
    o = ordner_von(name, ip)
    try:
        return [{"tag": d[:-4], "groesse": os.path.getsize(os.path.join(o, d))} for d in sorted(os.listdir(o), reverse=True) if re.fullmatch(r"\d{4}-\d\d-\d\d\.log", d)]
    except OSError:
        return []


def lesen(name, ip, tag):
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", tag or ""):
        raise ValueError("ungültiger Tag")
    with open(os.path.join(ordner_von(name, ip), tag + ".log"), "rb") as f:
        return f.read()
