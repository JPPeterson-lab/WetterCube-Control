# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Alle Geraete auf einmal: Updates nacheinander einspielen und Einstellungen fuer mehrere Geraete setzen.

Updates: immer nur ein Geraet zur Zeit; erst wenn es mit der neuen Version wieder antwortet, kommt das naechste. Alles nur auf Klick.
Einstellungen: wie beim Kopieren zuerst eine Vorschau, vor dem Schreiben eine Sicherheitskopie je Geraet; die Geraete starten danach neu.
"""
import json, threading, time

import control as c

# Aktion -> (Schluessel in der Sicherungsdatei, Mindestwert, Hoechstwert, Titel)
AKTIONEN = {
    "helligkeit": ("brightness", 5, 100, "Helligkeit (%)"),
    "auszeit": ("dim_timeout", 0, 60, "Display dimmen nach (Minuten, 0 = nie)"),
    "nachtmodus": ("night_modus", 0, 2, "Nachtmodus (0 aus, 1 feste Zeiten, 2 Sonnenuntergang bis Sonnenaufgang)"),
}

_sperre = threading.Lock()
_job = {"laeuft": False, "schritte": [], "fertig": False}


def status():
    with _sperre:
        return {"laeuft": _job["laeuft"], "fertig": _job["fertig"], "schritte": [dict(s) for s in _job["schritte"]]}


def _schritt(i, **kw):
    with _sperre:
        _job["schritte"][i].update(kw)


def updates_starten(ips):
    """Die gewaehlten Geraete nacheinander aktualisieren (nur solche, fuer die ein Update bereitliegt). False, wenn schon ein Lauf aktiv ist."""
    liste = []
    for ip in dict.fromkeys(ips):                     # jedes Geraet selbst fragen, ob ein Update bereitliegt
        try:
            j = c.update_pruefen(ip)
        except Exception:
            continue
        if j.get("verfuegbar") and not j.get("aus"):
            liste.append({"ip": ip, "name": c.anzeigename(c._geraete[ip]), "aktuell": j["aktuell"], "neueste": j["neueste"]})
    if not liste:
        raise ValueError("Für die gewählten Geräte liegt kein Update bereit.")
    with _sperre:
        if _job["laeuft"]:
            return False
        _job.update({"laeuft": True, "fertig": False, "schritte": [{"ip": p["ip"], "name": p["name"], "von": p["aktuell"], "nach": p["neueste"], "stand": "wartet", "ok": None} for p in liste]})

    def arbeit():
        try:
            for i, p in enumerate(liste):
                _schritt(i, stand="installiert ...")
                fehler = ""
                try:
                    c.update_starten(p["ip"])
                except Exception as e:     # Zeitueberschreitung heisst oft nur: Das Geraet startet schon neu; ob es klappte, zeigt die Version
                    fehler = str(e)
                _schritt(i, stand="startet neu, warte auf das Gerät ...")
                ende = time.time() + 240
                ok = False
                while time.time() < ende:
                    time.sleep(5)
                    try:
                        d = c.pruefen(p["ip"])
                    except Exception:
                        d = None
                    if d and (d.get("status") or {}).get("version") == p["neueste"]:
                        ok = True
                        break
                _schritt(i, ok=ok, stand="fertig, Version " + p["neueste"] if ok else ("nicht bestätigt" + (": " + fehler if fehler else "") + ". Bitte am Gerät nachsehen."))
        finally:
            with _sperre:
                _job.update({"laeuft": False, "fertig": True})
    threading.Thread(target=arbeit, daemon=True).start()
    return True


def einstellung(werte, ips, ausfuehren=False):
    """werte: {aktion: zahl}. Ohne ausfuehren nur Vorschau. Rueckgabe: Liste je Geraet mit den geplanten Aenderungen."""
    import sicherung
    schluessel = {}
    for a, w in (werte or {}).items():
        if a not in AKTIONEN:
            raise ValueError("Unbekannte Einstellung: " + str(a))
        k, lo, hi, _ = AKTIONEN[a]
        try:
            n = int(w)
        except (TypeError, ValueError):
            raise ValueError("Bitte eine ganze Zahl eintragen.")
        if not lo <= n <= hi:
            raise ValueError(f"{AKTIONEN[a][3]}: erlaubt sind {lo} bis {hi}.")
        schluessel[k] = n
    if not schluessel:
        raise ValueError("Bitte mindestens eine Einstellung wählen.")
    if not ips:
        raise ValueError("Bitte mindestens ein Gerät wählen.")
    erg = []
    for ip in ips:
        name, roh, z = sicherung._aktuell(ip)
        aend = {k: v for k, v in schluessel.items() if k in z and z[k] != v}
        fehlt = [k for k in schluessel if k not in z]
        e = {"ip": ip, "ziel": name, "aenderungen": [{"schluessel": k, "alt": z[k], "neu": v} for k, v in sorted(aend.items())], "fehlt": fehlt, "ok": None, "text": ""}
        if ausfuehren and aend:
            sicherung._sicherheitskopie(ip, name, roh)
            antwort = sicherung._post(f"http://{ip}/restore", json.dumps({"typ": z["typ"], **aend}).encode("utf-8"))
            e["ok"] = antwort.startswith("ok")
            e["text"] = "übernommen, Gerät startet neu" if e["ok"] else "abgelehnt: " + antwort[:100]
        elif ausfuehren:
            e["ok"], e["text"] = True, "nichts zu ändern"
        erg.append(e)
    return erg
