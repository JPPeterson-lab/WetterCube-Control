# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Installer der WetterCube Control: Firmware per USB auf ein Geraet spielen, ohne Browser-Installer (der braucht Chrome/Edge).

Liest dieselben Manifeste wie der Web-Installer (GitHub Pages der oeffentlichen Repos), laedt die Dateien, prueft sie
und ruft esptool auf. Braucht die Pakete esptool und pyserial (die Starter installieren sie beim ersten Mal).
Geflasht wird nur auf ausdruecklichen Klick nach Rueckfrage; Dateien kommen nur von den unten festen Adressen.
"""
import json, os, re, ssl, subprocess, sys, tempfile, threading, time, urllib.request

WEBSPACE = os.environ.get("WETTERCUBE_FIRMWARE_BASIS") or "https://wettercube.de/dl/"   # Fusion, Next, Plus und Plus Europe liegen auf dem eigenen Webspace (Test: Umgebungsvariable)
WEB = {"fusion-s3": ("fusion", "manifest.json"), "fusion-p4": ("fusion", "manifest-p4.json"), "next": ("next", "manifest.json"),
       "plus": ("plus", "manifest.json"), "europe": ("europe", "manifest.json")}   # Schluessel -> (Ordner, Manifest)
PRODUKTE = {   # Schluessel -> (Anzeigename, Adresse des Manifests)
    "fusion-s3":  ("WetterCube Fusion (ESP32-S3)", WEBSPACE + "fusion/manifest.json"),
    "fusion-p4":  ("WetterCube Fusion (ESP32-P4)", WEBSPACE + "fusion/manifest-p4.json"),
    "plus":       ("WetterCube Plus", WEBSPACE + "plus/manifest.json"),
    "europe":     ("WetterCube Plus Europe (Beta)", WEBSPACE + "europe/manifest.json"),
    "next":       ("WetterCube Next", WEBSPACE + "next/manifest.json"),
}
REPOS = {   # Schluessel -> (GitHub-Repo, Name des Manifests unter docs/); fuer aeltere Versionen ueber die Release-Tags
    "fusion-s3": ("WetterCube-Fusion", "manifest.json"), "fusion-p4": ("WetterCube-Fusion", "manifest-p4.json"),
    "plus": ("WetterCubePlus", "manifest.json"), "europe": ("WetterCubePlus-Europe", "manifest.json"), "next": ("WetterCube-Next", "manifest.json"),
}
KONTO = "JPPeterson-lab"
INTERN = {"node": "WetterCube Node (intern)"}   # nicht oeffentliche Produkte: erscheinen nur, wenn eine interne Quelle gesetzt ist (Adresse steht nie im Quellcode)
_versionen_cache = {}
CHIPS = {"ESP32": "esp32", "ESP32-S3": "esp32s3", "ESP32-P4": "esp32p4", "ESP32-C3": "esp32c3", "ESP32-C6": "esp32c6"}

_zustand = {"laeuft": False, "log": [], "ok": None, "titel": "", "info": "", "prozent": 0}
PASSEND = {"ESP32-S3": "Fusion (S3), Plus oder Plus Europe", "ESP32-P4": "Fusion (P4)", "ESP32": "Next"}
_sperre = threading.Lock()


def interne_quelle(key):
    """Basisadresse (mit / am Ende) der internen Firmware-Quelle eines nicht oeffentlichen Produkts, sonst "".
    Umgebungsvariable WETTERCUBE_<PRODUKT>_QUELLE oder Schluessel interne_quellen in der Einstellungsdatei. Kein Standardwert."""
    if key not in INTERN:
        return ""
    adresse = os.environ.get("WETTERCUBE_%s_QUELLE" % key.upper(), "").strip()
    if not adresse:
        try:
            import einstellungen
            adresse = str((einstellungen.holen().get("interne_quellen") or {}).get(key, "")).strip()
        except Exception:
            adresse = ""
    if not adresse.startswith("https://") and not adresse.startswith("http://localhost") and not adresse.startswith("http://127.0.0.1"):
        return ""
    return adresse if adresse.endswith("/") else adresse + "/"


def _produkte_alle():
    d = dict(PRODUKTE)
    for k, n in INTERN.items():
        q = interne_quelle(k)
        if q:
            d[k] = (n, q + "manifest.json")
    return d


def _web_basis(key):
    """(Basisadresse, Manifestname) fuer Produkte vom eigenen Webspace (auch intern), sonst None."""
    if key in WEB:
        return WEBSPACE + WEB[key][0] + "/", WEB[key][1]
    q = interne_quelle(key)
    return (q, "manifest.json") if q else None


def verfuegbar():
    try:
        import esptool, serial.tools.list_ports  # noqa: F401
        return True
    except ImportError:
        return False


def ports():
    """Serielle Anschluesse (USB), die nach einem Mikrocontroller aussehen."""
    import serial.tools.list_ports
    erg = []
    for p in serial.tools.list_ports.comports():
        if p.vid is None:      # Bluetooth-Anschluesse u. a. ausblenden
            continue
        erg.append({"port": p.device, "text": f"{p.device}  {p.description or ''}".strip()})
    return erg


# Produkte, bei denen der Assistent das Formular "WLAN per USB" zeigt (die veroeffentlichte Firmware nimmt WLAN-Daten per Improv Serial an).
# Bei allen anderen zeigt er die Anleitung fuer das Einrichtungs-WLAN. Next ab 0.3.0-rc1 und Fusion ab 1.0.0-rc18 koennen es (aeltere Versionen dieser Geraete
# nicht: dort meldet "Gerät prüfen" keine Antwort und nennt den Weg ueber das Einrichtungs-WLAN). Der Apex kann es ebenfalls, wird hier aber nicht angeboten.
# Plus ab 2.1.18 und Plus Europe ab 0.1.0-beta9 koennen es ebenfalls. Der Node kennt es nicht.
WLAN_USB = {"next", "fusion-s3", "fusion-p4", "plus", "europe"}


# Produkte, die Control (noch) nicht zum Aufspielen anbietet, obwohl ihre Manifeste bekannt sind (Update-Hinweis, Aenderungsliste). Seit rc12 leer:
# Plus und Plus Europe laufen wie Fusion und Next ueber den eigenen Webspace (nach dem Flash-Test mit dem eigenen Web-Installer, 8.11.2026).
NICHT_ANGEBOTEN = set()


def produkte():
    return [{"key": k, "name": v[0], "wlan_usb": k in WLAN_USB} for k, v in _produkte_alle().items() if k not in NICHT_ANGEBOTEN]


def _tls():
    """Zertifikate: Python auf dem Mac (und im gebauten Programm) kennt die Systemzertifikate nicht; certifi bringt sie mit."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _version():
    try:
        import control
        return control.VERSION
    except Exception:
        return "1"


def _holen(url, maxbytes=40_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "WetterCubeControl/" + _version()})
    with urllib.request.urlopen(req, timeout=60, context=_tls()) as r:
        return r.read(maxbytes)


def versionen(key):
    """Veroeffentlichte Versionen (Release-Tags) eines Produkts, neueste zuerst. Leere Liste, wenn GitHub nicht antwortet."""
    web = _web_basis(key)
    if web:   # eigener Webspace (auch interne Quellen): Liste der Versionen
        alt = _versionen_cache.get(key)
        if alt and time.time() - alt[0] < 600:
            return alt[1]
        try:
            tags = ["v" + str(v) for v in json.loads(_holen(web[0] + "versionen.json", 20_000)) if re.fullmatch(r"[0-9][0-9A-Za-z.\-]*", str(v))]
        except Exception:
            tags = alt[1] if alt else []
        _versionen_cache[key] = (time.time(), tags)
        return tags
    if key not in REPOS:
        raise ValueError("unbekanntes Produkt")
    repo = REPOS[key][0]
    alt = _versionen_cache.get(repo)
    if alt and time.time() - alt[0] < 600:
        return alt[1]
    try:
        daten = json.loads(_holen(f"https://api.github.com/repos/{KONTO}/{repo}/releases?per_page=30", 400_000))
        tags = [r["tag_name"] for r in daten if re.fullmatch(r"v[0-9][0-9A-Za-z.\-]*", str(r.get("tag_name", "")))]
    except Exception:
        tags = alt[1] if alt else []
    _versionen_cache[repo] = (time.time(), tags)
    return tags


def plan(key, version=""):
    """Manifest lesen: (Chip, [(Pfad, Adresse)], Version, Basisadresse). version = Release-Tag (z. B. v1.0.0-rc9) oder leer = neueste."""
    alle = _produkte_alle()
    if key not in alle:
        raise ValueError("unbekanntes Produkt")
    url = alle[key][1]
    if version:
        if not re.fullmatch(r"v[0-9][0-9A-Za-z.\-]*", version) or version not in versionen(key):
            raise ValueError("unbekannte Version")
        web = _web_basis(key)
        if web:
            url = f"{web[0]}{version[1:]}/{web[1]}"
        else:
            url = f"https://raw.githubusercontent.com/{KONTO}/{REPOS[key][0]}/{version}/docs/{REPOS[key][1]}"
    m = json.loads(_holen(url, 200_000))
    b = m["builds"][0]
    chip = CHIPS.get(b["chipFamily"])
    if not chip:
        raise ValueError("unbekannter Chip " + str(b["chipFamily"]))
    teile = []
    for t in b["parts"]:
        pfad = str(t["path"])
        if pfad.startswith("/") or ".." in pfad.split("/") or not pfad.endswith(".bin"):
            raise ValueError("unzulaessiger Dateipfad im Manifest: " + pfad)
        teile.append((pfad, int(t["offset"])))
    return chip, teile, m.get("version", "?"), url.rsplit("/", 1)[0] + "/"


def _log(text):
    with _sperre:
        _zustand["log"].append(text)
        del _zustand["log"][:-400]


def status():
    with _sperre:
        return {"laeuft": _zustand["laeuft"], "ok": _zustand["ok"], "titel": _zustand["titel"], "log": list(_zustand["log"]), "info": _zustand["info"], "prozent": _zustand["prozent"]}


def _info(text):
    with _sperre:
        _zustand["info"] = text


def _zusammenfassung_erkennen():
    """Aus der esptool-Ausgabe einen verstaendlichen Satz machen."""
    log = "\n".join(status()["log"])
    m = re.search(r"Chip is ([A-Za-z0-9-]+)(?: \(([^)]*)\))?", log)
    mac = re.search(r"MAC: ([0-9a-f:]{17})", log)
    if not m:
        return "Es wurde kein ESP-Chip erkannt."
    chip = m.group(1)
    text = f"Erkannt: {chip}" + (f", Revision {m.group(2).replace('revision ', '')}" if m.group(2) else "")
    if mac:
        text += f", MAC-Adresse {mac.group(1)}"
    text += ". Der Chip antwortet, das Gerät lässt sich flashen."
    passend = dict(PASSEND)
    if interne_quelle("node"):
        passend["ESP32-C3"] = "WetterCube Node"
    if chip in passend:
        text += f" Dazu passt: {passend[chip]}."
    return text


def _esptool(argumente, dateien=None):
    """esptool als eigener Prozess, Ausgabe zeilenweise ins Protokoll (CR als Zeilenende, damit der Fortschritt sichtbar ist).
    dateien: [(Startadresse, Groesse)] der zu schreibenden Dateien, daraus entsteht der Gesamtfortschritt in Prozent."""
    gesamt = sum(g for _, g in dateien) if dateien else 0
    if getattr(sys, "frozen", False):   # als eigenstaendiges Programm: dasselbe Programm mit --esptool starten (siehe app.py)
        befehl = [sys.executable, "--esptool"] + argumente
    else:
        befehl = [sys.executable, "-m", "esptool"] + argumente
    p = subprocess.Popen(befehl, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    puffer = b""
    letzte = ""
    while True:
        c = p.stdout.read(1)
        if not c:
            break
        if c in (b"\n", b"\r"):
            z = puffer.decode("utf-8", "replace").strip()
            puffer = b""
            # Fortschritt: esptool 4.x "Writing at 0x... (12 %)", esptool 5.x "Writing at 0x... [====>   ]  12.3% 1024/8192 bytes..."
            pr = re.search(r"Writing at 0x([0-9a-f]+)\D+?(\d+(?:\.\d+)?)\s?%", z)
            if pr:
                adr, pct = int(pr.group(1), 16), float(pr.group(2))
                if dateien and gesamt:
                    i = max([k for k, (a, _) in enumerate(dateien) if a <= adr] or [0])
                    fertig = sum(g for _, g in dateien[:i]) + dateien[i][1] * pct / 100.0
                    ges = min(99.0, fertig * 100.0 / gesamt)
                    with _sperre:
                        _zustand["prozent"] = int(ges)
                    _info(f"Schreibe auf das Gerät: insgesamt {int(ges)} % (Datei {i + 1} von {len(dateien)}: {int(pct)} %). Bitte nicht trennen.")
                else:
                    _info(f"Schreibe auf das Gerät: {int(pct)} % (Adresse 0x{pr.group(1)}). Bitte nicht trennen.")
            if z and z != letzte and not (z.startswith("Writing at") and letzte.startswith("Writing at") and int(time.time() * 2) % 3):
                _log(z)
                letzte = z
        else:
            puffer += c
    p.wait()
    return p.returncode


HINWEIS_BOOT_MODUS = [
    "Hinweis: Das Board geht beim Verbinden nicht von selbst in den Flash-Modus (Meldung 'Wrong boot mode'). Das ist bei vielen CYD-Boards wie dem WetterCube Next normal,",
    "die automatische Reset-Schaltung fehlt oder ist zu schwach. Es geht trotzdem, mit der BOOT-Taste:",
    "  1. Variante A: BOOT-Taste gedrückt halten, DANN auf 'Firmware aufspielen' klicken und die BOOT-Taste erst loslassen, wenn im Protokoll 'Writing at ...' erscheint.",
    "  2. Variante B (am zuverlässigsten): Haken 'Gerät von Hand in den Flash-Modus bringen' setzen, BOOT-Taste halten, kurz RESET drücken, BOOT loslassen, dann erst klicken.",
    "  3. Nach dem Aufspielen das Gerät einmal kurz vom Strom trennen, damit es neu startet.",
]

HINWEIS_VERBINDUNG = [
    "Hinweis: Das Gerät hat nicht geantwortet. Das ist normal, wenn es gerade eine Firmware ausführt oder gar kein ESP ist.",
    "  1. Anderes USB-Kabel (Datenkabel) oder anderen Anschluss versuchen.",
    "  2. Boot-Taste gedrückt halten, kurz Reset drücken, Boot-Taste loslassen (Flash-Modus), dann nochmal starten.",
    "  3. Unter Windows eventuell den USB-Treiber installieren (CP210x oder CH340).",
]


def _arbeit(titel, schritt):
    with _sperre:
        _zustand.update({"laeuft": True, "log": [], "ok": None, "titel": titel, "info": "", "prozent": 0})
    try:
        ok = schritt()
    except Exception as e:   # nie abstuerzen, Fehler anzeigen
        _log("Fehler: " + str(e))
        ok = False
    with _sperre:
        _zustand["laeuft"] = False
        _zustand["ok"] = bool(ok)
        if ok:
            _zustand["prozent"] = 100
    if ok and titel.startswith("Gerät erkennen"):
        _info(_zusammenfassung_erkennen())
    elif ok:
        _info("Fertig. Die Firmware ist aufgespielt, das Gerät startet neu.")
    else:
        _info("Das hat nicht geklappt. Siehe die Hinweise im Protokoll.")
    log = status()["log"]
    if not ok and any("Wrong boot mode" in z for z in log):
        for z in HINWEIS_BOOT_MODUS:
            _log(z)
        _info("Das Board geht nicht von selbst in den Flash-Modus. Halte die BOOT-Taste gedrückt (siehe Hinweise im Protokoll) und versuche es noch einmal.")
    elif not ok and any("Failed to connect" in z or "No serial data" in z for z in log):
        for z in HINWEIS_VERBINDUNG:
            _log(z)
    _log("Fertig." if ok else "Nicht erfolgreich.")


def _port_ok(port):
    return port in [p["port"] for p in ports()]


def erkennen(port, manuell=False):
    """Nur lesen: welcher Chip haengt am Anschluss (esptool chip_id). Startet das Geraet danach neu."""
    if _zustand["laeuft"]:
        return False
    if not _port_ok(port):
        raise ValueError("unbekannter Anschluss")
    threading.Thread(target=_arbeit, args=("Gerät erkennen", lambda: _esptool(["--port", port] + (["--before", "no_reset"] if manuell else []) + ["chip_id"]) == 0), daemon=True).start()
    return True


def flashen(key, port, loeschen=False, version="", manuell=False):
    """Firmware laden und aufspielen. loeschen=True loescht den ganzen Flash (auch Einstellungen und WLAN)."""
    if _zustand["laeuft"]:
        return False
    if key in NICHT_ANGEBOTEN:
        raise ValueError("Dieses Gerät lässt sich über WetterCube Control nicht aufspielen. Nutze den Web-Installer des Geräts.")
    if not _port_ok(port):
        raise ValueError("unbekannter Anschluss")
    chip, teile, version, basis = plan(key, version)
    name = _produkte_alle()[key][0]

    def schritt():
        _log(f"{name} {version}: lade {len(teile)} Dateien ...")
        with tempfile.TemporaryDirectory() as tmp:
            args = ["--chip", chip, "--port", port, "-b", "460800"]
            if manuell:   # Das Geraet ist von Hand im Flash-Modus (BOOT halten, RESET): kein Reset ueber DTR/RTS
                args += ["--before", "no_reset"]
            args += ["write_flash"]
            if loeschen:
                args.append("--erase-all")
            groessen = []
            for pfad, adresse in teile:
                daten = _holen(basis + pfad)
                if len(daten) < 1024:
                    raise ValueError(f"{pfad} ist zu klein ({len(daten)} Bytes), Abbruch")
                ziel = os.path.join(tmp, os.path.basename(pfad))
                with open(ziel, "wb") as f:
                    f.write(daten)
                groessen.append((adresse, len(daten)))
                _log(f"  {pfad}: {len(daten)} Bytes, Adresse 0x{adresse:x}")
                args += [hex(adresse), ziel]
            _log("Schreibe auf das Gerät. Bitte nicht trennen ...")
            return _esptool(args, groessen) == 0
    threading.Thread(target=_arbeit, args=(f"{name} {version} aufspielen", schritt), daemon=True).start()
    return True
