# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Installer der WetterCube Control: Firmware per USB auf ein Geraet spielen, ohne Browser-Installer (der braucht Chrome/Edge).

Liest dieselben Manifeste wie der Web-Installer (GitHub Pages der oeffentlichen Repos), laedt die Dateien, prueft sie
und ruft esptool auf. Braucht die Pakete esptool und pyserial (die Starter installieren sie beim ersten Mal).
Geflasht wird nur auf ausdruecklichen Klick nach Rueckfrage; Dateien kommen nur von den unten festen Adressen.
"""
import json, os, re, ssl, subprocess, sys, tempfile, threading, time, urllib.request

PRODUKTE = {   # Schluessel -> (Anzeigename, Adresse des Manifests)
    "fusion-s3":  ("WetterCube Fusion (ESP32-S3)", "https://jppeterson-lab.github.io/WetterCube-Fusion/manifest.json"),
    "fusion-p4":  ("WetterCube Fusion (ESP32-P4)", "https://jppeterson-lab.github.io/WetterCube-Fusion/manifest-p4.json"),
    "plus":       ("WetterCube Plus", "https://jppeterson-lab.github.io/WetterCubePlus/manifest.json"),
    "europe":     ("WetterCube Plus Europe (Beta)", "https://jppeterson-lab.github.io/WetterCubePlus-Europe/manifest.json"),
    "next":       ("WetterCube Next", "https://jppeterson-lab.github.io/WetterCube-Next/manifest.json"),
}
REPOS = {   # Schluessel -> (GitHub-Repo, Name des Manifests unter docs/); fuer aeltere Versionen ueber die Release-Tags
    "fusion-s3": ("WetterCube-Fusion", "manifest.json"), "fusion-p4": ("WetterCube-Fusion", "manifest-p4.json"),
    "plus": ("WetterCubePlus", "manifest.json"), "europe": ("WetterCubePlus-Europe", "manifest.json"), "next": ("WetterCube-Next", "manifest.json"),
}
KONTO = "JPPeterson-lab"
_versionen_cache = {}
CHIPS = {"ESP32": "esp32", "ESP32-S3": "esp32s3", "ESP32-P4": "esp32p4", "ESP32-C3": "esp32c3", "ESP32-C6": "esp32c6"}

_zustand = {"laeuft": False, "log": [], "ok": None, "titel": "", "info": ""}
PASSEND = {"ESP32-S3": "Fusion (S3), Plus oder Plus Europe", "ESP32-P4": "Fusion (P4)", "ESP32": "Next"}
_sperre = threading.Lock()


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


def produkte():
    return [{"key": k, "name": v[0]} for k, v in PRODUKTE.items()]


def _tls():
    """Zertifikate: Python auf dem Mac (und im gebauten Programm) kennt die Systemzertifikate nicht; certifi bringt sie mit."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _holen(url, maxbytes=40_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "WetterCubeControl/0.1"})
    with urllib.request.urlopen(req, timeout=60, context=_tls()) as r:
        return r.read(maxbytes)


def versionen(key):
    """Veroeffentlichte Versionen (Release-Tags) eines Produkts, neueste zuerst. Leere Liste, wenn GitHub nicht antwortet."""
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
    if key not in PRODUKTE:
        raise ValueError("unbekanntes Produkt")
    url = PRODUKTE[key][1]
    if version:
        if not re.fullmatch(r"v[0-9][0-9A-Za-z.\-]*", version) or version not in versionen(key):
            raise ValueError("unbekannte Version")
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
        return {"laeuft": _zustand["laeuft"], "ok": _zustand["ok"], "titel": _zustand["titel"], "log": list(_zustand["log"]), "info": _zustand["info"]}


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
    if chip in PASSEND:
        text += f" Dazu passt: {PASSEND[chip]}."
    return text


def _esptool(argumente):
    """esptool als eigener Prozess, Ausgabe zeilenweise ins Protokoll (CR als Zeilenende, damit der Fortschritt sichtbar ist)."""
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
            pr = re.search(r"Writing at 0x([0-9a-f]+)\.\.\. \((\d+) %\)", z)
            if pr:
                _info(f"Schreibe auf das Gerät: {pr.group(2)} % (Adresse 0x{pr.group(1)}). Bitte nicht trennen.")
            if z and z != letzte and not (z.startswith("Writing at") and letzte.startswith("Writing at") and int(time.time() * 2) % 3):
                _log(z)
                letzte = z
        else:
            puffer += c
    p.wait()
    return p.returncode


HINWEIS_VERBINDUNG = [
    "Hinweis: Das Gerät hat nicht geantwortet. Das ist normal, wenn es gerade eine Firmware ausführt oder gar kein ESP ist.",
    "  1. Anderes USB-Kabel (Datenkabel) oder anderen Anschluss versuchen.",
    "  2. Boot-Taste gedrückt halten, kurz Reset drücken, Boot-Taste loslassen (Flash-Modus), dann nochmal starten.",
    "  3. Unter Windows eventuell den USB-Treiber installieren (CP210x oder CH340).",
]


def _arbeit(titel, schritt):
    with _sperre:
        _zustand.update({"laeuft": True, "log": [], "ok": None, "titel": titel, "info": ""})
    try:
        ok = schritt()
    except Exception as e:   # nie abstuerzen, Fehler anzeigen
        _log("Fehler: " + str(e))
        ok = False
    with _sperre:
        _zustand["laeuft"] = False
        _zustand["ok"] = bool(ok)
    if ok and titel.startswith("Gerät erkennen"):
        _info(_zusammenfassung_erkennen())
    elif ok:
        _info("Fertig. Die Firmware ist aufgespielt, das Gerät startet neu.")
    else:
        _info("Das hat nicht geklappt. Siehe die Hinweise im Protokoll.")
    if not ok and any("Failed to connect" in z or "No serial data" in z for z in status()["log"]):
        for z in HINWEIS_VERBINDUNG:
            _log(z)
    _log("Fertig." if ok else "Nicht erfolgreich.")


def _port_ok(port):
    return port in [p["port"] for p in ports()]


def erkennen(port):
    """Nur lesen: welcher Chip haengt am Anschluss (esptool chip_id). Startet das Geraet danach neu."""
    if _zustand["laeuft"]:
        return False
    if not _port_ok(port):
        raise ValueError("unbekannter Anschluss")
    threading.Thread(target=_arbeit, args=("Gerät erkennen", lambda: _esptool(["--port", port, "chip_id"]) == 0), daemon=True).start()
    return True


def flashen(key, port, loeschen=False, version=""):
    """Firmware laden und aufspielen. loeschen=True loescht den ganzen Flash (auch Einstellungen und WLAN)."""
    if _zustand["laeuft"]:
        return False
    if not _port_ok(port):
        raise ValueError("unbekannter Anschluss")
    chip, teile, version, basis = plan(key, version)

    def schritt():
        _log(f"{PRODUKTE[key][0]} {version}: lade {len(teile)} Dateien ...")
        with tempfile.TemporaryDirectory() as tmp:
            args = ["--chip", chip, "--port", port, "-b", "460800", "write_flash"]
            if loeschen:
                args.append("--erase-all")
            for pfad, adresse in teile:
                daten = _holen(basis + pfad)
                if len(daten) < 1024:
                    raise ValueError(f"{pfad} ist zu klein ({len(daten)} Bytes), Abbruch")
                ziel = os.path.join(tmp, os.path.basename(pfad))
                with open(ziel, "wb") as f:
                    f.write(daten)
                _log(f"  {pfad}: {len(daten)} Bytes, Adresse 0x{adresse:x}")
                args += [hex(adresse), ziel]
            _log("Schreibe auf das Gerät. Bitte nicht trennen ...")
            return _esptool(args) == 0
    threading.Thread(target=_arbeit, args=(f"{PRODUKTE[key][0]} {version} aufspielen", schritt), daemon=True).start()
    return True
