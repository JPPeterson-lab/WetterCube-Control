# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Kalibrierung eines Sensorknotens (Offsets und Kalibrierpunkte) lesen, bearbeiten und speichern.

Schreiben nur auf Klick der Oberflaeche. Vorher legt Control immer eine Sicherheitskopie der Einstellungen des Geraets an
(wie beim Wiederherstellen und Kopieren). Aenderungen gehen ueber /api/config des Geraets, das selbst prueft.
"""
import json, urllib.error, urllib.parse, urllib.request

import control as c

SCHLUESSEL = ("t_off", "f_off", "p_off", "kt", "kf", "kp")
GROESSEN = ("temp", "feuchte", "druck")


def _geraet(ip):
    with c._sperre:
        d = c._geraete.get(ip)
    if d is None:
        raise ValueError("Unbekanntes Gerät")
    if (d.get("status") or {}).get("geraet") != "node":
        raise ValueError("Das ist kein Sensorknoten.")
    return d


def _holen(ip, pfad):
    try:
        return json.loads(c.http_get(f"http://{ip}{pfad}", 8, 200_000))
    except urllib.error.HTTPError as e:
        raise ValueError(_haftung(e, ip))
    except Exception:
        raise ValueError("Gerät nicht erreichbar")


def _haftung(e, ip):
    if e.code == 401:
        import passwoerter
        return passwoerter.fehlertext(ip)
    try:
        j = json.loads(e.read(2000))
        if j.get("fehler"):
            return str(j["fehler"])
    except Exception:
        pass
    return f"Gerät antwortet mit Fehler {e.code}"


def _post(ip, pfad, daten):
    import passwoerter
    req = urllib.request.Request(f"http://{ip}{pfad}", data=json.dumps(daten).encode("utf-8"), method="POST",
                                 headers=dict({"Content-Type": "application/json", "User-Agent": "WetterCubeControl/" + c.VERSION}, **passwoerter.kopf(ip)))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read(4000) or b"{}")
    except urllib.error.HTTPError as e:
        raise ValueError(_haftung(e, ip))
    except Exception:
        raise ValueError("Gerät nicht erreichbar")


def lesen(ip):
    """Status (Rohwerte und korrigierte Werte), Einstellungen und die Kurven fuer die Vorschau."""
    _geraet(ip)
    erg = {"status": _holen(ip, "/api/status"), "config": _holen(ip, "/api/config"), "kurven": {}}
    for g in GROESSEN:
        try:
            erg["kurven"][g] = _holen(ip, "/api/kalibrierung/kurve?groesse=" + g)
        except ValueError:
            erg["kurven"][g] = None
    return erg


def _kopie(ip):
    import sicherung
    name, roh, _ = sicherung._aktuell(ip)
    return sicherung._sicherheitskopie(ip, name, roh)


def speichern(ip, werte):
    """Offsets/Punkte auf das Geraet schreiben (Sicherheitskopie vorher). Gibt den Pfad der Kopie zurueck."""
    _geraet(ip)
    if not isinstance(werte, dict) or not werte or any(k not in SCHLUESSEL for k in werte):
        raise ValueError("Ungültige Angaben.")
    for k, v in werte.items():
        if k.endswith("_off"):
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError("Offset muss eine Zahl sein.")
        else:
            if not isinstance(v, list) or not all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in p) for p in v):
                raise ValueError("Punkte müssen Paare [Eingang, Referenz] sein.")
    kopie = _kopie(ip)
    _post(ip, "/api/config", werte)
    return kopie


def punkt(ip, groesse, ref):
    """Punkt aus dem aktuellen Wert des Geraets und dem Referenzwert anlegen (Sicherheitskopie vorher)."""
    _geraet(ip)
    if groesse not in GROESSEN or not isinstance(ref, (int, float)) or isinstance(ref, bool):
        raise ValueError("Ungültige Angaben.")
    kopie = _kopie(ip)
    antwort = _post(ip, "/api/kalibrierung/punkt", {"groesse": groesse, "ref": ref})
    return kopie, antwort
