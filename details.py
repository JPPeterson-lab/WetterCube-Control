# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Meldungen, Geraete-Gesundheit und Update-Hinweise von WetterCube Control.

- Meldungen: neue/beendete DWD-Warnung, Geraet offline/wieder da, neue Gesundheitsprobleme, neue Firmware.
  Sie landen in einer Liste (Seite) und werden von Menueleiste/Taskleiste als Mitteilung am Rechner gezeigt.
- Gesundheit: aus dem Diagnose-Log der Geraete (/log): WLAN-Staerke, freier Speicher, Alter der Daten.
- Update-Hinweis: Version des Geraets gegen die aktuelle Version im Manifest des Web-Installers.
"""
import os, re, threading, time

import control as c

EREIGNISSE = []
_eid = 0
_sperre = threading.Lock()
_z = {}               # ip -> Zustand je Geraet
_neueste = {}         # Produktschluessel -> aktuelle Version (aus den Manifesten)
_neueste_stand = 0
_angekuendigt = set()
_selbst = {}           # ip -> (Zeitpunkt, neueste Version laut Geraet) fuer Geraete ohne oeffentliches Manifest (Apex)
_selbst_laeuft = set()
OFFLINE_NACH = int(os.environ.get("WETTERCUBE_OFFLINE_NACH") or 120)    # Sekunden ohne Antwort, bevor "offline" gemeldet wird (ein Neustart dauert bis ~1 Minute)


# ── Meldungen ────────────────────────────────────────────────────────────────
def ereignis(art, text, geraet=""):
    """art: warnung | info | problem"""
    global _eid
    with _sperre:
        _eid += 1
        EREIGNISSE.append({"id": _eid, "ts": time.time(), "art": art, "text": text, "geraet": geraet})
        del EREIGNISSE[:-200]


def neue_ereignisse(seit=0):
    with _sperre:
        return [dict(e) for e in EREIGNISSE if e["id"] > seit]


def letzte_id():
    with _sperre:
        return _eid


# ── Log lesen und deuten ─────────────────────────────────────────────────────
def log_text(ip, maxbytes=200_000):
    return c.http_get(f"http://{ip}/log", 5, maxbytes).decode("utf-8", "replace")


def log_parse(text):
    """Die fuer die Gesundheit wichtigen Werte aus dem Diagnose-Log ziehen (fehlt etwas, bleibt es None)."""
    r = {"wlan_dbm": None, "heap": None, "abruf": {}, "ssid": None, "neustart": None, "heap_min": None, "heap_block": None, "uptime_min": None, "psram_frei": None, "zuletzt_aktiv": None}
    m = re.search(r"Signal (-?\d+) dBm", text)
    if m:
        r["wlan_dbm"] = int(m.group(1))
    m = re.search(r"WLAN jetzt: '([^']*)'", text)
    if m:
        r["ssid"] = m.group(1)
    m = re.search(r"Freier Heap: (\d+)", text)
    if m:
        r["heap"] = int(m.group(1))
    m = re.search(r"Freier Heap: \d+ Bytes \(intern, tiefster Stand seit Start: (\d+), groesster Block (\d+)", text)   # Fusion und Apex
    if m:
        r["heap_min"], r["heap_block"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"PSRAM: frei (\d+)", text)
    if m:
        r["psram_frei"] = int(m.group(1))
    m = re.search(r"Uptime: (\d+) Minuten", text)
    if m:
        r["uptime_min"] = int(m.group(1))
    m = re.search(r"Zuletzt aktiv vor dem Neustart: (.+)", text)
    if m:
        r["zuletzt_aktiv"] = m.group(1).strip()[:120]
    m = re.search(r"Letzter Neustart: (.+)", text)
    if m:
        r["neustart"] = m.group(1).strip()
    m = re.search(r"Letzter erfolgreicher Abruf: (.+)", text)
    if m:
        for teil in m.group(1).split(", "):
            n = re.match(r"^(.*?) vor (\d+) (Min|Std|Tag)", teil.strip())
            if n:
                faktor = {"Min": 1, "Std": 60, "Tag": 1440}[n.group(3)]
                r["abruf"][n.group(1).strip()] = int(n.group(2)) * faktor
            elif "noch nie" in teil:
                r["abruf"][teil.replace("noch nie", "").strip()] = None
    return r


def gesundheit(d):
    """(Stufe, [Gruende]) fuer ein Geraet. Stufe: ok | warn | problem."""
    ip = d["ip"]
    if d.get("online") is False:
        seit = _z.get(ip, {}).get("offline_seit")
        txt = "nicht erreichbar" + (f" seit {time.strftime('%H:%M', time.localtime(seit))}" if seit else "")
        return "problem", [txt]
    gr = []
    info = _z.get(ip, {}).get("log") or {}
    if info.get("wlan_dbm") is not None and info["wlan_dbm"] <= -80:
        gr.append(f"WLAN schwach ({info['wlan_dbm']} dBm)")
    if info.get("heap") is not None and info["heap"] < 50_000:
        gr.append(f"wenig freier Speicher ({info['heap'] // 1024} KB)")
    elif info.get("heap_min") is not None and info["heap_min"] < 16_000:
        gr.append(f"Speicher war zeitweise knapp (tiefster Stand {info['heap_min'] // 1024} KB seit dem Start)")
    if absturz(info):
        gr.append(f"Neustart nach {absturz(info)} vor {dauer_text(info['uptime_min'])}")
    for name, grenze in (("Wetter", 90), ("DWD-Warnungen", 60)):
        v = (info.get("abruf") or {}).get(name)
        if v is not None and v > grenze:
            gr.append(f"{name}-Daten veraltet (vor {v} Min.)")
    return ("warn" if gr else "ok"), gr


def absturz(info):
    """'Absturz', 'Watchdog' oder 'Spannungseinbruch', wenn das Geraet in den letzten 24 Stunden deswegen neu gestartet ist, sonst ''."""
    n, up = (info.get("neustart") or ""), info.get("uptime_min")
    if up is None or up >= 1440:
        return ""
    return "Watchdog" if "Watchdog" in n else "Absturz" if "ABSTURZ" in n else "Spannungseinbruch" if "BROWNOUT" in n else ""


def dauer_text(minuten):
    if minuten is None:
        return "?"
    return f"{minuten} Min." if minuten < 120 else f"{minuten // 60} Std."


# ── Versionen ────────────────────────────────────────────────────────────────
def versions_key(v):
    """'1.0.0-rc11' -> (1, 0, 0, 2, 11); Vorabversionen sind kleiner als die fertige Version."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z]+)(\d*))?", str(v))
    if not m:
        return None
    rang = {"alpha": 0, "beta": 1, "rc": 2}.get((m.group(4) or "").lower(), 3 if not m.group(4) else 1)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), rang, int(m.group(5) or 0))


def produkt_von(d):
    """Zu welchem Produkt (Schluessel im Installer) gehoert das Geraet? None = unbekannt/privat (Apex)."""
    name = (d.get("name") or "").lower()
    v = ((d.get("status") or {}).get("version")) or ""
    if "fusion" in name:
        return "fusion-s3"           # S3 und P4 haben dieselbe Versionsnummer
    if "next" in name:
        return "next"
    if "apex" in name:
        return None
    if "plus" in name or (d.get("status") or {}).get("geraet") == "plus":
        return "plus" if v.startswith("2.") else ("europe" if v.startswith("0.") else None)
    return None


def update_info(d):
    """{'aktuell','neueste','neuer'} oder None, wenn nichts zu vergleichen ist."""
    v = ((d.get("status") or {}).get("version")) or ""
    key = produkt_von(d)
    neu = _neueste.get(key) if key else None
    if key is None and "apex" in (d.get("name") or "").lower():
        neu = (_selbst.get(d.get("ip")) or (0, None))[1]
    if not v or not neu:
        return None
    a, b = versions_key(v), versions_key(neu)
    if a is None or b is None:
        return None
    return {"aktuell": v, "neueste": neu, "neuer": b > a}


def selbst_fragen(liste):
    """Geraete ohne oeffentliches Manifest (Apex) einmal pro Stunde selbst nach ihrem neuesten Update fragen (/ota_check, im Hintergrund)."""
    for d in liste:
        ip = d.get("ip")
        if d.get("online") is False or produkt_von(d) is not None or "apex" not in (d.get("name") or "").lower():
            continue
        if ip in _selbst_laeuft or time.time() - (_selbst.get(ip) or (0, None))[0] < 3600:
            continue
        _selbst_laeuft.add(ip)

        def los(ip=ip):
            try:
                j = c.update_pruefen(ip)
                _selbst[ip] = (time.time(), j["neueste"] if j.get("neueste") and not j.get("aus") else None)
            except Exception:
                _selbst[ip] = (time.time() - 3000, None)   # in ca. 10 Minuten noch einmal versuchen
            finally:
                _selbst_laeuft.discard(ip)
        threading.Thread(target=los, daemon=True).start()


def neueste_holen():
    """Aktuelle Versionen aus den Manifesten (alle 60 Minuten)."""
    global _neueste_stand
    import installer
    if time.time() - _neueste_stand < 3600:
        return
    _neueste_stand = time.time()
    for key in ("fusion-s3", "plus", "europe", "next"):
        try:
            _neueste[key] = installer.plan(key)[2]
        except Exception:
            pass


# ── Eigene Alarme (Regeln aus den Einstellungen) ────────────────────────────
_regel_zustand = {}   # (Regel-ID, ip) -> verletzt?


def regeln_pruefen(d, name):
    """Meldung, sobald ein Wert eine selbst eingestellte Grenze ueber-/unterschreitet, und wenn er wieder in Ordnung ist."""
    import einstellungen
    s = d.get("status") or {}
    for r in einstellungen.holen()["alarme"]:
        if not r.get("aktiv", True) or r.get("geraet") not in ("*", d["ip"]):
            continue
        try:
            v = float(s.get(r["metrik"]))
        except (TypeError, ValueError):
            continue
        verletzt = v < r["grenze"] if r["op"] == "<" else v > r["grenze"]
        schluessel = (r["id"], d["ip"])
        vorher = _regel_zustand.get(schluessel, False)
        if verletzt and not vorher:
            ereignis("warnung", f"{r['name']}: {name} meldet {v:g} (Grenze: {'unter' if r['op'] == '<' else 'über'} {r['grenze']:g})", name)
        elif vorher and not verletzt:
            ereignis("info", f"{r['name']}: {name} ist wieder in Ordnung ({v:g})", name)
        _regel_zustand[schluessel] = verletzt


# ── Auswertung nach jeder Abfrage ────────────────────────────────────────────
def nach_poll(d):
    """Einmal je Geraet und Abfrage aufrufen: erkennt Aenderungen und erzeugt Meldungen."""
    ip, name = d["ip"], c.anzeigename(d)
    z = _z.setdefault(ip, {"dwd": None, "gruende": None, "offline_seit": None, "offline_gemeldet": False, "log": None, "log_ts": 0})
    jetzt = time.time()
    if d.get("online") is False:
        if z["offline_seit"] is None:
            z["offline_seit"] = jetzt
        if not z["offline_gemeldet"] and jetzt - z["offline_seit"] >= OFFLINE_NACH:
            z["offline_gemeldet"] = True
            ereignis("problem", f"{name} ist nicht erreichbar", name)
        return
    if z["offline_gemeldet"]:
        ereignis("info", f"{name} ist wieder erreichbar", name)
    z["offline_seit"], z["offline_gemeldet"] = None, False
    s = d.get("status") or {}
    if "dwd" in s:
        n = int(s.get("dwd") or 0)
        if z["dwd"] is not None:
            if n > z["dwd"]:
                ereignis("warnung", f"Neue DWD-Warnung bei {name} ({n} aktiv)", name)
            elif z["dwd"] > 0 and n == 0:
                ereignis("info", f"Entwarnung bei {name}", name)
        z["dwd"] = n
    regeln_pruefen(d, name)
    stufe, gr = gesundheit(d)
    if z["gruende"] is not None:
        for g in gr:
            if g not in z["gruende"]:
                ereignis("problem", f"{name}: {g}", name)
    z["gruende"] = list(gr)
    u = update_info(d)
    if u and u["neuer"] and (ip, u["neueste"]) not in _angekuendigt:
        _angekuendigt.add((ip, u["neueste"]))
        ereignis("info", f"Für {name} gibt es eine neue Version: {u['aktuell']} → {u['neueste']}", name)


def log_aktualisieren(d):
    """Diagnose-Log eines erreichbaren Geraets lesen (alle 5 Minuten). Geraete mit Passwort liefern 401 und bleiben ohne Log-Werte."""
    z = _z.setdefault(d["ip"], {"dwd": None, "gruende": None, "offline_seit": None, "offline_gemeldet": False, "log": None, "log_ts": 0})
    if d.get("online") is False or time.time() - z["log_ts"] < 300:
        return
    z["log_ts"] = time.time()
    try:
        text = log_text(d["ip"])
        z["log"] = log_parse(text)
    except Exception:
        return
    try:
        import protokolle
        protokolle.sammeln(d["ip"], c.anzeigename(d), text, z["log"])
    except Exception as e:   # nie abstuerzen
        print("Protokolle:", e)


def anreichern(liste):
    """Gesundheit, Update-Info und Log-Werte an die Geraeteliste haengen (fuer die Seite)."""
    for d in liste:
        stufe, gr = gesundheit(d)
        d["gesundheit"] = {"stufe": stufe, "gruende": gr}
        d["update"] = update_info(d)
        import passwoerter
        d["passwort"] = passwoerter.status(d["ip"])
        lg = (_z.get(d["ip"]) or {}).get("log")
        if lg:
            d["log_info"] = {k: lg.get(k) for k in ("wlan_dbm", "ssid", "heap", "heap_min", "heap_block", "psram_frei", "uptime_min", "neustart", "zuletzt_aktiv", "abruf")}
    return liste


def takt():
    """Alle paar Sekunden aus dem Hintergrund-Thread: Geraete auswerten, Logs und neueste Versionen auffrischen."""
    import einstellungen
    with c._sperre:
        liste = [dict(d) for d in c._geraete.values()]
    for d in liste:
        if einstellungen.ausgeblendet(d["ip"]):
            continue
        try:
            log_aktualisieren(d)
            nach_poll(d)
        except Exception as e:   # nie abstuerzen
            print("Auswertung:", e)
    try:
        import einstellungen
        if einstellungen.holen().get("versionssuche") or os.environ.get("WETTERCUBE_VERSIONSSUCHE") == "1":   # nur wenn der Nutzer es eingeschaltet hat: sonst keine Verbindung ins Internet von selbst
            neueste_holen()
            selbst_fragen(liste)
    except Exception:
        pass
