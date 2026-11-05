# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Einstellungen wiederherstellen, auf andere Geraete kopieren und Diagnose-Pakete schnueren.

Schreibende Vorgaenge (Wiederherstellen, Kopieren) legen vorher immer eine Sicherheitskopie des Zielgeraets an und
pruefen, dass der Gerätetyp zur Datei passt. Die Geraete uebernehmen nur Schluessel, die in der Datei stehen (alles andere
bleibt unveraendert) und starten danach neu. Passwoerter sind nie in den Sicherungen.
"""
import io, json, os, platform, re, sys, time, urllib.error, urllib.parse, urllib.request, zipfile

import control as c

GRUPPEN = {   # Name -> (Titel, Schluessel der Sicherungsdatei)
    "ort": ("Standort (Ort, Koordinaten, Warnregion)", ["location", "lat", "lon", "dwd_region", "bio_zone"]),
    "ort2": ("Zweiter Standort", ["location2", "lat2", "lon2", "dwd_region2", "bio_zone2"]),
    "warnungen": ("Warnungen und Töne", ["warn_region", "pollen_warn", "pollen_schwelle", "pollen_auswahl", "warn_ton_an", "warn_ton", "warn_laut", "ruhe_modus", "ruhe_von", "ruhe_bis"]),
    "hinweise": ("Hinweise (Regen, Frost, UV, Hitze, ...)", ["hinweis_regen", "hinweis_frost", "verlauf_regen", "hinweis_uv", "hinweis_sensor", "hinweis_druck", "hinweis_schatten", "schatten_temp", "hinweis_giessen", "hinweis_gefuehlt"]),
    "anzeige": ("Anzeige (Helligkeit, Nachtmodus, Kacheln)", ["brightness", "dim_timeout", "night_mode", "night_modus", "night_sonne_ab", "night_sonne_bis", "night_theme", "night_uhr", "night_from", "night_to", "night_brightness", "kacheln_seite", "anim_symbole", "anim_stunden"]),
    "ntfy": ("Handy-Meldungen (ntfy: Schalter, Quellen)", ["ntfy_aktiv", "ntfy_quellen", "ntfy_entwarnung"]),
    "lueften": ("Lüften-Ampel", ["lueft_kuehlen", "lueft_hitze", "lueft_ampel", "lueft_warnung", "lueft_feuchte", "zf_lueften"]),
    "muell": ("Müllabfuhr", ["hinweis_muell", "muell_vorlauf", "muell_ab", "muell_bis", "muell_aktiv", "muell_url", "zf_muell"]),
    "updates": ("Updates", ["update_intervall_h", "update_modus"]),
}


class Fehler(Exception):
    pass


def _geraet(ip):
    with c._sperre:
        d = c._geraete.get(ip)
    if d is None:
        raise Fehler("Unbekanntes Gerät")
    return d


def _ordner(heute=True):
    o = os.path.join(c.SICHERUNGSORDNER, time.strftime("%Y-%m-%d"))
    os.makedirs(o, exist_ok=True)
    return o


def _post(url, daten, timeout=20):
    import passwoerter
    adresse = urllib.parse.urlparse(url).netloc
    req = urllib.request.Request(url, data=daten, method="POST", headers=dict({"Content-Type": "application/json", "User-Agent": "WetterCubeControl/" + c.VERSION}, **passwoerter.kopf(adresse)))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Fehler(passwoerter.fehlertext(adresse))
        raise Fehler(f"Gerät antwortet mit Fehler {e.code}")
    except Exception:
        raise Fehler("Gerät nicht erreichbar")


def _aktuell(ip):
    """(Name, Sicherungsdatei als Text, Inhalt als dict) des Geraets."""
    try:
        name, roh = c.sicherung_holen(ip)
    except c.SicherungsFehler as e:
        raise Fehler(str(e))
    return name, roh, json.loads(roh)


def _sicherheitskopie(ip, name, roh):
    pfad = os.path.join(_ordner(), "vor-Aenderung-" + c.dateiname(name, ip))
    with open(pfad, "wb") as f:
        f.write(roh)
    return pfad


# ── Vorhandene Sicherungen ───────────────────────────────────────────────────
def sicherungen_liste(ip):
    """Gespeicherte Sicherungen, die zu diesem Geraet passen (Dateiname beginnt mit seinem Namen), neueste zuerst."""
    d = _geraet(ip)
    prefix = c.dateiname(d.get("name", ip), ip).rsplit("-", 4)[0]
    erg = []
    for wurzel, _, dateien in os.walk(c.SICHERUNGSORDNER):
        for f in dateien:
            if f.endswith(".json") and (f.startswith(prefix) or f.startswith("vor-Aenderung-" + prefix)):
                p = os.path.join(wurzel, f)
                erg.append({"datei": os.path.relpath(p, c.SICHERUNGSORDNER), "zeit": time.strftime("%d.%m.%Y %H:%M", time.localtime(os.path.getmtime(p))), "ts": os.path.getmtime(p)})
    erg.sort(key=lambda x: -x["ts"])
    return erg[:30]


def sicherung_lesen(rel):
    p = os.path.realpath(os.path.join(c.SICHERUNGSORDNER, rel))
    wurzel = os.path.realpath(c.SICHERUNGSORDNER)
    if not p.startswith(wurzel + os.sep) or not p.endswith(".json") or not os.path.isfile(p) or os.path.getsize(p) > 1_000_000:
        raise Fehler("Datei nicht gefunden")
    with open(p, "rb") as f:
        return f.read()


# ── Wiederherstellen ─────────────────────────────────────────────────────────
def pruefen_datei(roh):
    try:
        inhalt = json.loads(roh)
    except ValueError:
        raise Fehler("Das ist keine gültige Sicherungsdatei (kein JSON).")
    if not isinstance(inhalt, dict) or not str(inhalt.get("typ", "")).startswith("WetterCube"):
        raise Fehler("Das ist keine WetterCube-Sicherung (Feld 'typ' fehlt).")
    return inhalt


def wiederherstellen(ip, roh):
    """Sicherungsdatei auf das Geraet spielen. Gibt (Meldung, Pfad der Sicherheitskopie) zurueck."""
    inhalt = pruefen_datei(roh)
    name, alt_roh, alt = _aktuell(ip)
    if inhalt.get("typ") != alt.get("typ"):
        raise Fehler(f"Die Datei gehört zu einem anderen Gerätetyp ({inhalt.get('typ')}), dieses Gerät ist „{alt.get('typ')}“.")
    kopie = _sicherheitskopie(ip, name, alt_roh)
    antwort = _post(f"http://{ip}/restore", roh if isinstance(roh, bytes) else roh.encode("utf-8"))
    if not antwort.startswith("ok"):
        raise Fehler("Das Gerät hat die Datei nicht angenommen: " + antwort[:120])
    return f"Eingespielt ({antwort.strip()}). Das Gerät startet neu.", kopie


# ── Kopieren auf andere Geraete ──────────────────────────────────────────────
def kopieren(quelle, ziele, gruppen, ausfuehren=False):
    """Ausgewaehlte Einstellungsgruppen von quelle auf ziele uebertragen. Ohne ausfuehren nur eine Vorschau der Aenderungen."""
    if not gruppen or any(g not in GRUPPEN for g in gruppen):
        raise Fehler("Bitte mindestens eine Einstellungsgruppe wählen.")
    if quelle in ziele:
        raise Fehler("Quelle und Ziel dürfen nicht dasselbe Gerät sein.")
    _, _, q = _aktuell(quelle)
    ergebnis = []
    for ziel in ziele:
        name, z_roh, z = _aktuell(ziel)
        schluessel = {k for g in gruppen for k in GRUPPEN[g][1]}
        aend = {k: q[k] for k in schluessel if k in q and k in z and q[k] != z[k]}
        eintrag = {"ziel": name, "ip": ziel, "aenderungen": [{"schluessel": k, "alt": z[k], "neu": v} for k, v in sorted(aend.items())], "ok": None, "text": ""}
        if ausfuehren and aend:
            _sicherheitskopie(ziel, name, z_roh)
            antwort = _post(f"http://{ziel}/restore", json.dumps({"typ": z["typ"], **aend}).encode("utf-8"))
            eintrag["ok"] = antwort.startswith("ok")
            eintrag["text"] = "übernommen, Gerät startet neu" if eintrag["ok"] else "abgelehnt: " + antwort[:100]
        elif ausfuehren:
            eintrag["ok"], eintrag["text"] = True, "nichts zu ändern"
        ergebnis.append(eintrag)
    return ergebnis


# ── Diagnose-Paket ───────────────────────────────────────────────────────────
DIAGNOSEORDNER = os.environ.get("WETTERCUBE_DIAGNOSE") or os.path.join(os.path.expanduser("~"), "WetterCube-Diagnose")


def diagnose(ips, mit_einstellungen=False):
    """ZIP mit Status, Log und Version je Geraet. Einstellungen nur auf ausdruecklichen Wunsch (enthalten Ort, aber keine Passwoerter).
    Das Log kann WLAN-Namen und Adressen enthalten: vor dem Weitergeben ansehen."""
    os.makedirs(DIAGNOSEORDNER, exist_ok=True)
    pfad = os.path.join(DIAGNOSEORDNER, "wettercube-diagnose-" + time.strftime("%Y-%m-%d-%H%M") + ".zip")
    hinweise = []
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("control.txt", f"WetterCube Control {c.VERSION}\n{platform.platform()}\nPython {sys.version.split()[0]}\nErstellt: {time.strftime('%d.%m.%Y %H:%M')}\n"
                   f"Einstellungen enthalten: {'ja' if mit_einstellungen else 'nein'}\n")
        for ip in ips:
            d = _geraet(ip)
            ordner = re.sub(r"[^A-Za-z0-9_-]+", "-", d.get("name", ip)).strip("-") + "/"
            z.writestr(ordner + "status.json", json.dumps({"ip": ip, "name": d.get("name"), "online": d.get("online"), "status": d.get("status")}, ensure_ascii=False, indent=1))
            for datei, url in (("log.txt", f"http://{ip}/log"),):
                try:
                    z.writestr(ordner + datei, c.http_get(url, 6, 400_000))
                except Exception as e:
                    hinweise.append(f"{d.get('name', ip)}: {datei} nicht lesbar ({e})")
            if mit_einstellungen:
                try:
                    z.writestr(ordner + "einstellungen.json", c.sicherung_holen(ip)[1])
                except Exception as e:
                    hinweise.append(f"{d.get('name', ip)}: Einstellungen nicht lesbar ({e})")
        if hinweise:
            z.writestr("hinweise.txt", "\n".join(hinweise))
    return pfad, hinweise


# ── Automatische Sicherung nach Zeitplan ─────────────────────────────────────
def auto_sichern_pruefen():
    """Aus dem Hintergrund-Thread aufrufen: sichert alle Geraete, wenn der Zeitplan (taeglich/woechentlich) es verlangt, und raeumt alte Tage auf."""
    import details, einstellungen
    plan = einstellungen.holen()["auto_sichern"]
    if plan.get("modus") not in ("taeglich", "woechentlich"):
        return
    intervall = 86400 if plan["modus"] == "taeglich" else 7 * 86400
    if time.time() - float(plan.get("letzte") or 0) < intervall:
        return
    einstellungen.aendern(lambda d: d["auto_sichern"].update(letzte=time.time()))
    ordner, erg = c.alle_sichern()
    ok = sum(1 for _, g, _ in erg if g)
    details.ereignis("info" if ok == len(erg) else "problem", f"Automatische Sicherung: {ok} von {len(erg)} Geräten gesichert", "")
    aufraeumen(int(plan.get("behalten") or 14))


def aufraeumen(behalten):
    """Nur Tagesordner (JJJJ-MM-TT) im Sicherungsordner; die neuesten `behalten` bleiben."""
    import shutil
    try:
        tage = sorted(n for n in os.listdir(c.SICHERUNGSORDNER) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", n) and os.path.isdir(os.path.join(c.SICHERUNGSORDNER, n)))
    except OSError:
        return
    for n in tage[:-max(1, behalten)]:
        shutil.rmtree(os.path.join(c.SICHERUNGSORDNER, n), ignore_errors=True)
