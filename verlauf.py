# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Verlauf der Werte aller Geraete (lokal, SQLite aus der Standardbibliothek). Nichts verlaesst den Rechner.

Alle 5 Minuten wird je erreichbarem Geraet eine Zeile gespeichert, 90 Tage lang. Die Seite /verlauf zeigt Kurven.
"""
import os, sqlite3, threading, time

DATEI = os.environ.get("WETTERCUBE_VERLAUF") or os.path.join(os.path.expanduser("~"), ".wettercube-control-verlauf.db")
INTERVALL = 300
TAGE = 90
METRIKEN = {"temp": "Temperatur (°C)", "gefuehlt": "Gefühlt (°C)", "feuchte": "Luftfeuchte (%)", "druck": "Luftdruck (hPa)",
            "wind": "Wind (km/h)", "uv": "UV-Index", "aqi": "Luftqualität (AQI)", "pm25": "Feinstaub PM2,5 (µg/m³)", "dwd": "DWD-Warnungen (Anzahl)",
            "s_temp": "Sensor: Temperatur (°C)", "s_feuchte": "Sensor: Luftfeuchte (%)"}
SENSOR = ("s_temp", "s_feuchte")   # eigene Messung der Geraete: Gehaeusesensor von Fusion und Apex (int_*), beim Sensorknoten seine Werte
_sperre = threading.Lock()
_letzte = {}


def _db():
    os.makedirs(os.path.dirname(DATEI) or ".", exist_ok=True)
    k = sqlite3.connect(DATEI, timeout=10)
    k.execute("CREATE TABLE IF NOT EXISTS m (ts INTEGER, geraet TEXT, name TEXT, " + ", ".join(f"{m} REAL" for m in METRIKEN) + ")")
    k.execute("CREATE INDEX IF NOT EXISTS i_m ON m (geraet, ts)")
    vorhanden = {z[1] for z in k.execute("PRAGMA table_info(m)")}
    for m in METRIKEN:                     # aeltere Dateien um neue Messgroessen ergaenzen
        if m not in vorhanden:
            k.execute(f"ALTER TABLE m ADD COLUMN {m} REAL")
    return k


def sensorwerte(s):
    """Eigene Messung eines Geraets: Sensorknoten liefern temp/feuchte direkt, Fusion und Apex ihren Gehaeusesensor als int_*."""
    if s.get("geraet") == "node":
        return {"s_temp": s.get("temp"), "s_feuchte": s.get("feuchte")}
    return {"s_temp": s.get("int_temp"), "s_feuchte": s.get("int_feuchte")}


def speichern(liste):
    """Eine Zeile je erreichbarem Geraet mit Werten, hoechstens alle INTERVALL Sekunden je Geraet."""
    jetzt = int(time.time())
    zeilen = []
    for d in liste:
        s = d.get("status") or {}
        if d.get("online") is False or "temp" not in s:
            continue
        if jetzt - _letzte.get(d["ip"], 0) < INTERVALL:
            continue
        _letzte[d["ip"]] = jetzt
        sw = sensorwerte(s)
        zeilen.append((jetzt, d["ip"], d.get("name", d["ip"])) + tuple(_zahl(sw.get(m) if m in SENSOR else s.get(m)) for m in METRIKEN))
    if not zeilen:
        return
    with _sperre:
        k = _db()
        try:
            k.executemany("INSERT INTO m (ts, geraet, name, " + ", ".join(METRIKEN) + ") VALUES (?,?,?," + ",".join("?" * len(METRIKEN)) + ")", zeilen)
            k.commit()
        finally:
            k.close()


def _zahl(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def aufraeumen():
    with _sperre:
        k = _db()
        try:
            k.execute("DELETE FROM m WHERE ts < ?", (int(time.time()) - TAGE * 86400,))
            k.commit()
        finally:
            k.close()


def abfrage(metrik, stunden, max_punkte=300):
    """{Name: [[ts, wert], ...]} der letzten `stunden`, auf hoechstens max_punkte je Geraet gemittelt."""
    if metrik not in METRIKEN:
        raise ValueError("unbekannte Messgroesse")
    stunden = max(1, min(int(stunden), TAGE * 24))
    ab = int(time.time()) - stunden * 3600
    with _sperre:
        k = _db()
        try:
            zeilen = k.execute(f"SELECT geraet, name, ts, {metrik} FROM m WHERE ts >= ? AND {metrik} IS NOT NULL ORDER BY geraet, ts", (ab,)).fetchall()
        finally:
            k.close()
    neuester = {}
    for ip, name, ts, v in zeilen:   # je Adresse eine Kurve unter dem neuesten Namen (ein umbenanntes Geraet zerfaellt nicht in zwei Kurven)
        neuester[ip] = name
    erg = {}
    for ip, name, ts, v in zeilen:
        erg.setdefault(neuester[ip], []).append((ts, v))
    breite = max(1, (stunden * 3600) // max_punkte)
    aus = {}
    for name, pkt in erg.items():
        eimer = {}
        for ts, v in pkt:
            b = ts // breite
            e = eimer.setdefault(b, [0.0, 0, 0])
            e[0] += v
            e[1] += 1
            e[2] = ts
        aus[name] = [[e[2], round(e[0] / e[1], 2)] for _, e in sorted(eimer.items())]
    return aus


def anzahl():
    with _sperre:
        k = _db()
        try:
            return k.execute("SELECT COUNT(*) FROM m").fetchone()[0]
        finally:
            k.close()


def csv_export(stunden):
    """Alle gespeicherten Werte der letzten `stunden` als CSV-Text (Semikolon, Dezimalpunkt)."""
    stunden = max(1, min(int(stunden), TAGE * 24))
    ab = int(time.time()) - stunden * 3600
    with _sperre:
        k = _db()
        try:
            zeilen = k.execute("SELECT ts, name, " + ", ".join(METRIKEN) + " FROM m WHERE ts >= ? ORDER BY ts, name", (ab,)).fetchall()
        finally:
            k.close()
    aus = ["zeit;geraet;" + ";".join(METRIKEN)]
    for z in zeilen:
        aus.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(z[0])) + ";" + str(z[1]).replace(";", ",") + ";" + ";".join("" if v is None else ("%g" % v) for v in z[2:]))
    return "\n".join(aus) + "\n"


def tage(metrik, anzahl_tage=14):
    """Tageswerte je Geraet: [{'geraet','tag','min','max','mittel','n'}], neueste Tage zuerst."""
    if metrik not in METRIKEN:
        raise ValueError("unbekannte Messgroesse")
    ab = int(time.time()) - max(1, min(int(anzahl_tage), TAGE)) * 86400
    with _sperre:
        k = _db()
        try:
            zeilen = k.execute(f"SELECT name, date(ts, 'unixepoch', 'localtime') AS tag, MIN({metrik}), MAX({metrik}), AVG({metrik}), COUNT({metrik}) "
                               f"FROM m WHERE ts >= ? AND {metrik} IS NOT NULL GROUP BY name, tag ORDER BY tag DESC, name", (ab,)).fetchall()
        finally:
            k.close()
    return [{"geraet": n, "tag": t, "min": round(mi, 1), "max": round(ma, 1), "mittel": round(av, 1), "n": cnt} for n, t, mi, ma, av, cnt in zeilen]


def loeschen(ip):
    """Alle gespeicherten Werte eines Geraets (nach seiner Adresse) loeschen; gibt die Zahl der Zeilen zurueck."""
    with _sperre:
        k = _db()
        try:
            n = k.execute("DELETE FROM m WHERE geraet = ?", (ip,)).rowcount
            k.commit()
            return n
        finally:
            k.close()


def vergleich(metrik, stunden):
    """Sensorvergleich: je Geraet der Mittelwert ueber die Zeit, in der ALLE beteiligten Geraete gemessen haben (gleiche 30-Minuten-Fenster),
    und die Abweichung vom Median der Geraete. [{'geraet','mittel','abw','n'}], sortiert nach Abweichung."""
    if metrik not in METRIKEN:
        raise ValueError("unbekannte Messgroesse")
    stunden = max(1, min(int(stunden), TAGE * 24))
    ab = int(time.time()) - stunden * 3600
    with _sperre:
        k = _db()
        try:
            roh = k.execute(f"SELECT geraet, ts / 1800 AS f, AVG({metrik}) FROM m WHERE ts >= ? AND {metrik} IS NOT NULL GROUP BY geraet, f", (ab,)).fetchall()
            namen_ip = dict(k.execute("SELECT geraet, name FROM m WHERE ts >= ? ORDER BY ts", (ab,)).fetchall())   # je Adresse der neueste Name
            zeilen = [(namen_ip.get(g, g), f, v) for g, f, v in roh]
        finally:
            k.close()
    fenster = {}
    for name, f, v in zeilen:
        fenster.setdefault(f, {})[name] = v
    namen = sorted({n for n, _, _ in zeilen})
    if len(namen) < 2:
        return []
    gemeinsam = [w for w in fenster.values() if len(w) == len(namen)]
    if not gemeinsam:
        return []
    mittel = {n: sum(w[n] for w in gemeinsam) / len(gemeinsam) for n in namen}
    werte = sorted(mittel.values())
    mitte = werte[len(werte) // 2] if len(werte) % 2 else (werte[len(werte) // 2 - 1] + werte[len(werte) // 2]) / 2
    return sorted(({"geraet": n, "mittel": round(mittel[n], 1), "abw": round(mittel[n] - mitte, 1), "n": len(gemeinsam)} for n in namen), key=lambda x: -abs(x["abw"]))
