#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""WetterCube Control: findet alle WetterCube-Geraete im Heimnetz und zeigt ihre Werte auf einer Seite.

Nur Python-Standardbibliothek, laeuft unter macOS, Windows und Linux.
  python3 control.py                 Seite auf http://localhost:8765 (auf localhost als Web-App installierbar)
  python3 control.py --lan           zusaetzlich im Heimnetz erreichbar (z. B. vom Handy: http://<IP des Rechners>:8765)
  python3 control.py --text          einmal suchen und eine Zeile je Geraet ausgeben
  python3 control.py --geraet 192.168.1.50 --geraet wettercube-apex.local   feste Adressen zusaetzlich zur Suche

Warum ein lokales Programm und keine Seite im Netz: Die Geraete antworten nur Anfragen, die an ihre eigene Adresse gehen,
senden keine CORS-Header und lehnen schreibende Anfragen fremder Seiten ab (Schutz gegen DNS-Rebinding und fremde Webseiten).
Eine Seite auf wettercube.de koennte sie also nie lesen. Dieses Programm fragt selbst (ohne Browser-Herkunft) und gibt
der Seite nur das fertige Ergebnis.
"""
import argparse, concurrent.futures as cf, ipaddress, json, os, re, socket, sys, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HIER = os.path.dirname(os.path.abspath(__file__))
if _HIER not in sys.path:   # auch mit python -I oder aus einem anderen Ordner gestartet: die Teilprogramme neben dieser Datei finden
    sys.path.insert(0, _HIER)

VERSION = "1.0.0-rc18"
PORT = int(os.environ.get("WETTERCUBE_PORT") or 8765)
SUCH_INTERVALL = 300          # Netz neu absuchen (Sekunden)
WERT_INTERVALL = int(os.environ.get("WETTERCUBE_TAKT") or 15)   # Werte neu holen (Sekunden; fuer Tests kuerzer)
_geraete = {}                 # ip -> Daten
_sperre = threading.Lock()
_extra = []
LAN = False             # --lan: auch IP-Adressen als Host erlaubt
DEMO = False            # --demo: erfundene Geraete fuer Fotos und zum Ausprobieren, keine Netzabfragen
KEINE_SUCHE = False     # --keine-suche: nur die ausdruecklich genannten Geraete (z. B. Tests, getrennte Netze)
MERKDATEI = os.environ.get("WETTERCUBE_MERKDATEI") or os.path.join(os.path.expanduser("~"), ".wettercube-control.json")   # bekannte Geraete (Name, Adresse), damit ein gerade ausgeschaltetes Geraet als "nicht erreichbar" stehen bleibt


ALTE_MERKDATEI = os.path.join(os.path.expanduser("~"), ".wettercube-zentrale.json")   # Name vor der Umbenennung in WetterCube Control


def merken_laden():
    if DEMO:
        return
    if not os.environ.get("WETTERCUBE_MERKDATEI") and not os.path.exists(MERKDATEI) and os.path.exists(ALTE_MERKDATEI):
        try:
            os.replace(ALTE_MERKDATEI, MERKDATEI)
        except OSError:
            pass
    try:
        with open(MERKDATEI, encoding="utf-8") as f:
            for ip, d in json.load(f).items():
                _geraete[ip] = {"ip": ip, "name": d.get("name", ip), "art": d.get("art", "nur_link"), "status": {}, "online": False, "zuletzt": d.get("zuletzt") or time.time()}
    except (OSError, ValueError):
        pass


def merken_speichern():
    if DEMO:
        return
    try:
        with _sperre:
            daten = {ip: {"name": d.get("name", ip), "art": d.get("art", "nur_link"), "zuletzt": d.get("zuletzt")} for ip, d in _geraete.items()}
        with open(MERKDATEI, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def http_get(url, timeout=1.5, maxbytes=65536):
    import passwoerter
    kopf = {"User-Agent": "WetterCubeControl/" + VERSION}
    kopf.update(passwoerter.kopf(urllib.parse.urlparse(url).netloc))   # gespeichertes Web-Passwort des Geraets (nur wenn eines hinterlegt ist)
    req = urllib.request.Request(url, headers=kopf)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(maxbytes)


def eigenes_netz():
    """/24 des Rechners (ohne Netzwerkbibliothek: UDP-Socket ohne Verbindung liefert die Ausgangsadresse)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ipaddress.ip_network(ip + "/24", strict=False), ip


def huebsch(n):
    """wettercube-apex -> WetterCube Apex, wettercubeplus -> WetterCube Plus, wettercube-next-556c -> WetterCube Next (556c)"""
    t = n.replace("wettercube", "wettercube-", 1).replace("--", "-").split("-")[1:]
    if not t:
        return n
    namen = [x.capitalize() for x in t if not (len(x) == 4 and any(c.isdigit() for c in x))]
    kenn = [x for x in t if len(x) == 4 and any(c.isdigit() for c in x)]
    return "WetterCube " + " ".join(namen) + (" (" + kenn[0] + ")" if kenn else "")


def name_von(ip):
    try:
        n = socket.gethostbyaddr(ip)[0].lower()
        if "wettercube" in n:
            return huebsch(n.split(".")[0])
    except OSError:
        pass
    try:   # Diagnose-Log: erste Zeile "WetterCube Fusion Diagnose-Log ..."
        z = http_get(f"http://{ip}/log", 2, 200).decode("utf-8", "replace").splitlines()[0]
        if "WetterCube" in z:
            return z.split(" Diagnose")[0].split(" diagnostic")[0].strip()
    except Exception:
        pass
    return ""


def ist_status(st):
    """Antwort von /api/status eines WetterCube? (Das Next hat vor dem ersten Abruf der Fusion noch keine Temperatur.)"""
    return isinstance(st, dict) and "version" in st and ("temp" in st or "geraet" in st)


_bild_sperren = {}   # ip -> Lock: hoechstens ein Bildschirmfoto je Geraet gleichzeitig
_FEST = set()   # ausdruecklich eingetragene Adressen (--geraet, hinzugefuegt): bekommen mehr Geduld als die Netzsuche


def pruefen(ip):
    """Gibt Daten zurueck, wenn unter ip ein WetterCube antwortet (sonst None). Feste Adressen: 4 s Geduld und ein zweiter Versuch
    (ein Geraet im WLAN antwortet manchmal kurz verzoegert), die Netzsuche bleibt schnell."""
    fest = ip in _FEST
    for versuch in range(2 if fest else 1):
        try:
            st = json.loads(http_get(f"http://{ip}/api/status", 4.0 if fest else 1.2))
            if ist_status(st):
                return {"ip": ip, "art": "status", "status": st}
            break
        except Exception:
            if fest and versuch == 0:
                time.sleep(1)
    n = name_von(ip) if (fest or ip_hat_http(ip)) else ""
    if "wettercube" in n.lower().replace(" ", ""):   # z. B. WetterCubePlus ohne /api/status
        return {"ip": ip, "art": "nur_link", "status": {}}
    return None


def ip_hat_http(ip):
    try:
        s = socket.create_connection((ip, 80), 0.4)
        s.close()
        return True
    except OSError:
        return False


def suchen():
    import einstellungen
    aus_umgebung = [x.strip() for x in (os.environ.get("WETTERCUBE_GERAETE") or "").split(",") if x.strip()]   # auch im Programm und im Container
    fest = list(dict.fromkeys(_extra + aus_umgebung + einstellungen.holen()["hinzugefuegt"]))
    if KEINE_SUCHE:
        kandidaten = list(fest)
    else:
        netz, eigene = eigenes_netz()
        kandidaten = [str(h) for h in netz.hosts() if str(h) != eigene] + fest
    gefunden = {}
    _FEST.update(fest)
    def erreichbar(ip):
        if ip in _FEST:
            return True   # ausdruecklich eingetragene Adressen immer pruefen
        return ip_hat_http(ip) if ip.replace(".", "").isdigit() else True   # Namen (z. B. x.local) immer pruefen
    with cf.ThreadPoolExecutor(64) as ex:
        offen = [ip for ip, ok in zip(kandidaten, ex.map(erreichbar, kandidaten)) if ok]
        for ip, d in zip(offen, ex.map(pruefen, offen)):
            if d:
                d["name"] = name_von(ip) or ip
                gefunden[ip] = d
    return gefunden


def werte_holen():
    with _sperre:
        ips = list(_geraete)
    for ip in ips:
        d = _geraete.get(ip)
        if not d or d.get("demo"):
            continue
        if d["art"] == "status":
            try:
                d["status"] = json.loads(http_get(f"http://{ip}/api/status", 2))
                d["online"] = True
                d["stand"] = time.time()
            except Exception:
                d["online"] = False
        else:
            try:   # neue Firmware kann /api/status inzwischen: Art sofort umstellen
                st = json.loads(http_get(f"http://{ip}/api/status", 1.5))
                if ist_status(st):
                    d["art"], d["status"], d["online"], d["stand"] = "status", st, True, time.time()
                    continue
            except Exception:
                pass
            d["online"] = ip_hat_http(ip)
            d["stand"] = time.time()


_letzte_aufraeumung = [0]


def zuletzt_aktualisieren():
    """Merkt sich, wann ein Geraet zuletzt erreichbar war (fuer die Anzeige und das automatische Entfernen)."""
    jetzt = time.time()
    with _sperre:
        for d in _geraete.values():
            if d.get("online"):
                d["zuletzt"] = jetzt
            elif not d.get("zuletzt"):
                d["zuletzt"] = jetzt


TAG_SEKUNDEN = int(os.environ.get("WETTERCUBE_TAG_SEKUNDEN") or 86400)   # nur fuer Tests kuerzer


def auto_entfernen_pruefen():
    """Nicht erreichbare Geraete nach der eingestellten Zahl von Tagen aus der Liste nehmen (0 = nie)."""
    import einstellungen
    tage = int(einstellungen.holen().get("auto_entfernen_tage") or 0)
    if tage <= 0:
        return
    jetzt = time.time()
    with _sperre:
        faellig = [(ip, d.get("name", ip)) for ip, d in _geraete.items() if not d.get("online") and jetzt - float(d.get("zuletzt") or jetzt) > tage * TAG_SEKUNDEN]
    for ip, name in faellig:
        geraet_vergessen(ip, False, True)
        import details
        details.ereignis("info", f"{name} war seit mehr als {tage} Tagen nicht erreichbar und wurde automatisch aus der Liste entfernt", "")


_suche_jetzt = threading.Lock()


def jetzt_suchen():
    """Einen Suchlauf sofort anstossen (im Hintergrund). False, wenn gerade schon einer laeuft."""
    if not _suche_jetzt.acquire(blocking=False):
        return False

    def los():
        try:
            neu = suchen()
            with _sperre:
                for ip, d in neu.items():
                    alt = _geraete.get(ip)
                    if alt is None:
                        d["zuletzt"] = time.time()
                        _geraete[ip] = d
                    else:
                        alt["name"], alt["art"] = d["name"], d["art"]
            merken_speichern()
        except Exception as e:
            print("Fehler:", e, file=sys.stderr)
        finally:
            _suche_jetzt.release()
    threading.Thread(target=los, daemon=True).start()
    return True


def hintergrund():
    merken_laden()
    letzte_suche = 0
    while True:
        try:
            if time.time() - letzte_suche > SUCH_INTERVALL:
                neu = suchen()
                with _sperre:
                    for ip, d in neu.items():
                        alt = _geraete.get(ip)
                        if alt is None:
                            d["zuletzt"] = time.time()
                            _geraete[ip] = d
                        else:
                            alt["name"], alt["art"] = d["name"], d["art"]
                letzte_suche = time.time()
                merken_speichern()
            werte_holen()
            zuletzt_aktualisieren()
            auto_entfernen_pruefen()
            import details, verlauf
            details.takt()
            verlauf.speichern(als_liste())
            import sicherung
            sicherung.auto_sichern_pruefen()
            if time.time() - _letzte_aufraeumung[0] > 86400:
                _letzte_aufraeumung[0] = time.time()
                verlauf.aufraeumen()
        except Exception as e:   # nie abstuerzen
            print("Fehler:", e, file=sys.stderr)
        time.sleep(WERT_INTERVALL)


SICHERUNGSORDNER = os.environ.get("WETTERCUBE_SICHERUNGEN") or os.path.join(os.path.expanduser("~"), "WetterCube-Sicherungen")


class SicherungsFehler(Exception):
    pass


def sicherung_holen(ip):
    """Einstellungen eines bekannten Geraets lesen (GET /backup). Die Datei enthaelt kein WLAN- und kein MQTT-Passwort."""
    with _sperre:
        d = _geraete.get(ip)
    if d is None:
        raise SicherungsFehler("Unbekanntes Gerät")
    try:
        roh = http_get(f"http://{ip}/backup", 10, 1_000_000)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            import passwoerter
            raise SicherungsFehler(passwoerter.fehlertext(ip))
        if e.code == 404:
            raise SicherungsFehler(f"{d.get('name', ip)} kann keine Einstellungen sichern oder kopieren (zum Beispiel das Next, es holt seine Einstellungen vom Fusion).")
        raise SicherungsFehler(f"Gerät antwortet mit Fehler {e.code}")
    except Exception:
        raise SicherungsFehler("Gerät nicht erreichbar")
    try:
        if not isinstance(json.loads(roh), dict):
            raise ValueError
    except ValueError:
        raise SicherungsFehler("Das Gerät lieferte keine gültige Sicherung")
    return d.get("name", ip), roh


def dateiname(name, ip):
    sauber = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.replace(" ", "-")).strip("-") or ip.replace(".", "-")
    return f"{sauber}-{time.strftime('%Y-%m-%d-%H%M')}.json"


def alle_sichern():
    """Alle erreichbaren Geraete in einen Ordner schreiben; gibt (Ordner, [(Name, ok, Text)]) zurueck."""
    ordner = os.path.join(SICHERUNGSORDNER, time.strftime("%Y-%m-%d"))
    os.makedirs(ordner, exist_ok=True)
    erg = []
    with _sperre:
        ips = [(ip, d.get("name", ip)) for ip, d in _geraete.items()]
    for ip, name in sorted(ips, key=lambda x: x[1]):
        try:
            _, roh = sicherung_holen(ip)
            with open(os.path.join(ordner, dateiname(name, ip)), "wb") as f:
                f.write(roh)
            erg.append((name, True, "gesichert"))
        except SicherungsFehler as e:
            erg.append((name, False, str(e)))
        except OSError as e:
            erg.append((name, False, f"Datei nicht schreibbar: {e}"))
    return ordner, erg


def demo_laden():
    """Erfundene Geraete, Meldungen und Verlauf (Adressen 192.168.1.x): fuer Bildschirmfotos und zum Ausprobieren ohne Geraete."""
    import details, einstellungen, math, verlauf
    jetzt = time.time()
    def st(version, temp, wetter, dwd=None, **extra):
        d = {"version": version, "temp": temp, "gefuehlt": round(temp - 1.5, 1), "feuchte": 78, "druck": 1016, "wind": 9, "wetter": wetter, "uv": 1.2, "aqi": 32}
        if dwd is not None:
            d["dwd"] = dwd
        d.update(extra)
        return d
    liste = [
        ("192.168.1.50", "WetterCube Fusion", st("1.0.0-rc14", 8.4, "Bedeckt", 0, lueften="Raumluft in Ordnung"), True, "fusion.png", {"wlan_dbm": -58, "heap": 196000, "heap_min": 151000, "heap_block": 110000, "uptime_min": 3170, "abruf": {"Wetter": 4, "DWD-Warnungen": 6}}),
        ("192.168.1.51", "WetterCube Apex", st("0.0.67", 8.6, "Bedeckt", 1), True, "apex.png", {"wlan_dbm": -61, "heap": 182000, "heap_min": 64000, "heap_block": 48000, "psram_frei": 19400000, "uptime_min": 820, "abruf": {"Wetter": 5, "DWD-Warnungen": 5}}),
        ("192.168.1.52", "WetterCube Plus", st("2.1.16", 7.9, "Leichter Regen", 0, druck=1012), True, None, {"wlan_dbm": -84, "heap": 150000, "abruf": {"Wetter": 8, "DWD-Warnungen": 12}}),
        ("192.168.1.53", "WetterCube Next (a1b2)", {"version": "0.3.0-beta4", "temp": 8.4, "gefuehlt": 6.9, "feuchte": 78, "uv": 1.2, "wetter": "Bedeckt", "geraet": "next", "daten_alter_s": 120, "fehler": 0, "quelle": "192.168.1.50"}, True, None, None),
        ("192.168.1.54", "WetterCube Plus Europe (Beta)", {}, False, None, None),
    ]
    with _sperre:
        for ip, name, status, online, bild, log in liste:
            _geraete[ip] = {"ip": ip, "name": name, "art": "status" if status else "nur_link", "status": status, "online": online, "zuletzt": jetzt if online else jetzt - 3 * 86400, "demo": True, "demo_bild": bild}
    for ip, name, status, online, bild, log in liste:
        details._z[ip] = {"dwd": (status or {}).get("dwd"), "gruende": [], "offline_seit": None if online else jetzt - 3 * 86400, "offline_gemeldet": not online,
                          "log": dict(log, ssid="Heimnetz", neustart="Strom angeschlossen") if log else None, "log_ts": jetzt + 10 ** 9}
    for ip, d in list(_geraete.items()):   # Ausgangslage der Gesundheit festhalten, damit keine doppelten Meldungen entstehen
        details._z[ip]["gruende"] = list(details.gesundheit(dict(d))[1])
    details._neueste.update({"fusion-s3": "1.0.0-rc14", "plus": "2.1.16", "europe": "0.1.0-beta8", "next": "0.3.0-beta4"})
    details._neueste_stand = jetzt + 10 ** 9
    einstellungen.aendern(lambda e: (e["alias"].update({"192.168.1.52": "Wohnzimmer"}), e["alarme"].append({"id": "frost", "name": "Frost", "geraet": "*", "metrik": "temp", "op": "<", "grenze": 2.0, "aktiv": True}),
                                     e["auto_sichern"].update(modus="taeglich", behalten=14)))
    for art, text, vor in (("warnung", "Neue DWD-Warnung bei WetterCube Apex (1 aktiv)", 1500), ("info", "WetterCube Next (a1b2) ist wieder erreichbar", 5400),
                           ("problem", "Wohnzimmer: WLAN schwach (-84 dBm)", 9000), ("info", "Automatische Sicherung: 4 von 4 Geräten gesichert", 30000)):
        details.ereignis(art, text, "")
        details.EREIGNISSE[-1]["ts"] = jetzt - vor
    # Verlauf: 7 Tage, alle 30 Minuten, drei Geraete mit leicht verschobenen Kurven
    k = verlauf._db()
    for i in range(0, 7 * 48):
        ts = int(jetzt - i * 1800)
        for ip, name, off in (("192.168.1.50", "WetterCube Fusion", 0.0), ("192.168.1.51", "WetterCube Apex", 0.4), ("192.168.1.52", "Wohnzimmer", -2.5)):
            t = 8 + 4.5 * math.sin((ts % 86400) / 86400 * 6.2832 - 2.2) + 1.5 * math.sin(ts / 260000) + off
            innen = 21.3 + 0.6 * math.sin(ts / 40000) + {"192.168.1.50": 0.1, "192.168.1.51": 1.1, "192.168.1.52": -0.2}[ip]   # Apex-Gehaeusesensor sitzt warm
            k.execute("INSERT INTO m (ts,geraet,name,temp,gefuehlt,feuchte,druck,wind,dwd,s_temp,s_feuchte) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (ts, ip, name, round(t, 1), round(t - 1.5, 1), round(75 - 8 * math.sin(ts / 9000), 0), round(1015 + 5 * math.sin(ts / 70000), 0), round(8 + 4 * math.sin(ts / 13000), 0), 0,
                       round(innen, 1), round(46 - 2 * math.sin(ts / 30000) - 3 * (ip == "192.168.1.51"), 0)))
    k.commit(); k.close()


def anzeigename(d):
    """Der vom Nutzer vergebene Name, sonst der erkannte."""
    import einstellungen
    return einstellungen.alias_von(d["ip"]) or d.get("name", d["ip"])


def als_liste(alle=False):
    """Geraeteliste fuer Seiten und Menues: mit eigenem Namen; ausgeblendete nur mit alle=True."""
    import einstellungen
    e = einstellungen.holen()
    erg = []
    with _sperre:
        eintraege = list(_geraete.items())
    for ip, d in eintraege:
        if not alle and ip in e["ausgeblendet"]:
            continue
        x = dict(d)
        x["name_original"] = d.get("name", ip)
        x["name"] = e["alias"].get(ip) or d.get("name", ip)
        x["ausgeblendet"] = ip in e["ausgeblendet"]
        x["manuell"] = ip in e["hinzugefuegt"]
        erg.append(x)
    return sorted(erg, key=lambda x: x["name"])


def update_pruefen(ip):
    """Fragt das Geraet selbst, ob es ein neueres Update gibt (/ota_check; das Geraet schaut bei seiner Update-Quelle nach)."""
    if _geraete.get(ip, {}).get("demo"):
        v = (_geraete[ip].get("status") or {}).get("version")
        return {"aktuell": v, "neueste": v, "verfuegbar": False, "aus": False}
    if (_geraete.get(ip, {}).get("status") or {}).get("geraet") == "node":   # der Sensorknoten hat noch kein Update ueber das WLAN
        v = _geraete[ip]["status"].get("version")
        return {"aktuell": v, "neueste": v, "verfuegbar": False, "aus": False}
    # Fusion und Apex beantworten Anfragen nicht, solange sie Wetterdaten abrufen (alle 15/30 Minuten, bei wackeligem WLAN bis zu ein paar
    # Minuten): darum lange warten und bei "keine Antwort" zweimal nachfassen, statt nach 25 s "timed out" zu melden.
    letzter = None
    for versuch in range(3):
        try:
            j = json.loads(http_get(f"http://{ip}/ota_check", 60, 4096))
            return {"aktuell": j.get("current"), "neueste": j.get("latest"), "verfuegbar": bool(j.get("update_available")), "aus": bool(j.get("aus"))}
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            letzter = e
            if versuch < 2:
                time.sleep(10)
    raise ValueError("Das Gerät antwortet gerade nicht (es holt vermutlich gerade Wetterdaten oder das WLAN hakt). Bitte in ein, zwei Minuten noch einmal versuchen.") from letzter


def update_starten(ip):
    """Loest das Update am Geraet aus (/ota_update). Das Geraet laedt, installiert und startet neu; die Antwort kommt erst danach."""
    j = update_pruefen(ip)
    if j["aus"]:
        raise ValueError("Updates sind am Gerät ausgeschaltet (Einstellung in seiner Weboberfläche).")
    if not j["verfuegbar"]:
        raise ValueError("Es gibt kein neueres Update.")
    import passwoerter
    req = urllib.request.Request(f"http://{ip}/ota_update", data=b"", method="POST", headers=dict({"User-Agent": "WetterCubeControl/" + VERSION}, **passwoerter.kopf(ip)))
    try:
        for versuch in range(3):   # Verbindung abgelehnt oder nicht angenommen (Geraet beschaeftigt): kurz warten und erneut; nach dem Absenden nicht wiederholen
            try:
                r = urllib.request.urlopen(req, timeout=300)
                break
            except urllib.error.URLError as e:
                if isinstance(e, urllib.error.HTTPError) or versuch == 2 or not isinstance(e.reason, (ConnectionRefusedError, ConnectionResetError, OSError)) or isinstance(e.reason, TimeoutError):
                    raise
                time.sleep(10)
        with r:
            antwort = r.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError(passwoerter.fehlertext(ip))
        raise ValueError("Das Gerät meldet einen Fehler: " + e.read(200).decode("utf-8", "replace"))
    except Exception:
        raise ValueError("Keine Antwort vom Gerät. Es kann trotzdem installieren und neu starten, bitte gleich nachsehen.")
    import details
    details.ereignis("info", f"Update bei {anzeigename(_geraete[ip])} installiert ({j['aktuell']} → {j['neueste']}), das Gerät startet neu", "")
    return antwort


def passwort_pruefen_speichern(ip, passwort):
    """Web-Passwort eines Geraets pruefen (Anfrage an /log) und erst bei Erfolg speichern. Gibt {'ort': 'schluesselbund'|'sitzung'} zurueck."""
    import base64, passwoerter
    if not passwort:
        raise ValueError("Bitte ein Passwort eingeben.")
    try:   # ohne Passwort probieren: antwortet das Geraet ohne Anmeldung, hat es gar keines
        with urllib.request.urlopen(urllib.request.Request(f"http://{ip}/log", headers={"User-Agent": "WetterCubeControl/" + VERSION}), timeout=8) as r:
            r.read(100)
        raise ValueError("Dieses Gerät hat kein Web-Passwort. Es ist nichts zu hinterlegen.")
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise ValueError(f"Das Gerät antwortet mit Fehler {e.code}")
    except ValueError:
        raise
    except Exception:
        raise ValueError("Gerät nicht erreichbar")
    kopf = {"User-Agent": "WetterCubeControl/" + VERSION, "Authorization": "Basic " + base64.b64encode(("admin:" + passwort).encode("utf-8")).decode("ascii")}
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://{ip}/log", headers=kopf), timeout=8) as r:
            r.read(100)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError("Das Passwort ist falsch. (Nach acht falschen Versuchen sperrt das Gerät eine Minute lang.)")
        raise ValueError(f"Das Gerät antwortet mit Fehler {e.code}")
    except Exception:
        raise ValueError("Gerät nicht erreichbar")
    return {"ort": passwoerter.setzen(ip, passwort)}


def geraet_hinzufuegen(adresse):
    """Von Hand eingetragene Adresse pruefen und aufnehmen; wirft ValueError mit Text."""
    import einstellungen
    adresse = (adresse or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,80}(:\d{1,5})?", adresse):
        raise ValueError("Bitte eine IP-Adresse oder einen Namen eingeben, zum Beispiel 192.168.1.52 oder wettercube-fusion.local")
    d = pruefen(adresse)
    if not d:
        raise ValueError("Unter dieser Adresse antwortet kein WetterCube-Gerät.")
    d["name"] = name_von(adresse) or adresse
    with _sperre:
        _geraete.setdefault(adresse, d)
    einstellungen.aendern(lambda e: e["hinzugefuegt"].append(adresse) if adresse not in e["hinzugefuegt"] else None)
    merken_speichern()
    return d["name"]


def geraet_vergessen(ip, verlauf_loeschen=False, erzwingen=False):
    """Ein Geraet aus Control entfernen (Liste, Merkdatei, eigener Name, Ausblenden). Erreichbare, automatisch gefundene Geraete
    kann man nur ausblenden, denn sie kaemen beim naechsten Suchlauf sofort zurueck; nicht erreichbare gehen immer."""
    import einstellungen, details, verlauf
    with _sperre:
        d = _geraete.get(ip)
    if d is None:
        raise ValueError("Unbekanntes Gerät")
    if d.get("online") and ip not in einstellungen.holen()["hinzugefuegt"] and not erzwingen:
        raise ValueError("Dieses Gerät ist gerade erreichbar und wurde automatisch gefunden. Du kannst es nur ausblenden, sonst käme es sofort wieder.")
    def weg(e):
        e["alias"].pop(ip, None)
        for liste in ("ausgeblendet", "hinzugefuegt"):
            if ip in e[liste]:
                e[liste].remove(ip)
    einstellungen.aendern(weg)
    with _sperre:
        _geraete.pop(ip, None)
    details._z.pop(ip, None)
    for k in [k for k in details._regel_zustand if k[1] == ip]:
        details._regel_zustand.pop(k, None)
    if verlauf_loeschen:
        verlauf.loeschen(ip)
    merken_speichern()


def ressource(pfad):
    """Datei aus assets/ lesen (aus dem Quellordner oder aus dem gebauten Programm)."""
    basis = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(basis, pfad), "rb") as f:
        return f.read()


ASSETS = {   # Adresse -> (Datei, Inhaltstyp)
    "/logo.svg": ("assets/logo/wettercube-control-logo.svg", "image/svg+xml"),
    "/logo-hell.svg": ("assets/logo/wettercube-control-logo-hell.svg", "image/svg+xml"),
    "/icon.svg": ("assets/logo/wettercube-symbol.svg", "image/svg+xml"),
    "/icon-192.png": ("assets/icons/symbol-192.png", "image/png"),
    "/icon-512.png": ("assets/icons/symbol-512.png", "image/png"),
    "/favicon.ico": ("assets/icons/WetterCube Control.ico", "image/x-icon"),
}
MANIFEST = {"name": "WetterCube Control", "short_name": "WetterCube", "start_url": "/", "display": "standalone",
            "background_color": "#06203b", "theme_color": "#0b2545",
            "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
                      {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]}
SW = "self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('fetch',e=>{});"
# Im Netzwerkmodus (--lan) ist Control nur zum Ansehen da: alles, was Einstellungen, Logs oder Geraete veraendert/preisgibt, ist gesperrt
LAN_GESPERRT = ("/api/passwort", "/api/update", "/api/einstellungen", "/einstellungen", "/api/alarme", "/api/geraete/", "/api/autostart", "/api/sicherung", "/api/sicherungen", "/api/log", "/api/diagnose", "/api/installer", "/installer", "/api/wlan", "/api/alle", "/alle", "/assistent", "/api/netzcheck", "/hilfe", "/api/suche", "/kopieren", "/api/kopieren", "/api/alle-sichern", "/api/wiederherstellen", "/kalibrierung", "/api/node", "/api/protokoll")


def geraet_pruefen(ip):
    with _sperre:
        if ip not in _geraete:
            raise KeyError("Unbekanntes Gerät")
    return ip


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def senden(self, code, typ, body, kopf=None):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (kopf or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def json(self, daten, code=200):
        self.senden(code, "application/json; charset=utf-8", json.dumps(daten, ensure_ascii=False))

    def fehler(self, text, code=400):
        self.json({"fehler": text}, code)

    def host_ok(self):
        """Gegen DNS-Rebinding: nur localhost oder eine IP-Adresse (im --lan-Modus) als Host."""
        h = (self.headers.get("Host") or "").lower().rsplit(":", 1)[0].strip("[]")
        return h in ("localhost", "127.0.0.1", "::1") or (LAN and h.replace(".", "").isdigit())

    def lan_gesperrt(self, p):
        if p == "/api/update/pruefen":
            return False   # rein lesend (fragt nur, ob ein Update da ist); Installieren ist ein POST und im Netzwerkmodus ohnehin gesperrt
        return LAN and any(p == x or p.startswith(x + "/") or p.startswith(x) for x in LAN_GESPERRT)

    def body_json(self, maxbytes=1_100_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > maxbytes:
            raise ValueError("Anfrage zu groß")
        return json.loads(self.rfile.read(n) or b"{}")

    # ── POST ──
    def do_POST(self):
        p = self.path.split("?")[0]
        o = self.headers.get("Origin")
        if not self.host_ok() or (o and o.split("://", 1)[-1] != (self.headers.get("Host") or "")):
            return self.senden(403, "text/plain", "abgelehnt")
        if LAN:
            return self.fehler("Im Netzwerkmodus ist Control nur zum Ansehen da.", 403)
        try:
            if p == "/api/installer/start":
                import installer
                d = self.body_json(4096)
                if not installer.verfuegbar():
                    return self.fehler("esptool und pyserial fehlen")
                if d.get("aktion") == "erkennen":
                    ok = installer.erkennen(str(d.get("port", "")), bool(d.get("manuell")))
                else:
                    if d.get("haftung") is not True:
                        return self.fehler("Bitte zuerst die Nutzungshinweise bestätigen.")
                    ok = installer.flashen(str(d.get("produkt", "")), str(d.get("port", "")), bool(d.get("loeschen")), str(d.get("version", "")), bool(d.get("manuell")))
                return self.json({"ok": ok, "text": "gestartet" if ok else "Es läuft schon ein Vorgang"}, 200 if ok else 409)
            if p == "/api/node/kalibrierung":
                import nodekal
                d = self.body_json(20_000)
                kopie = nodekal.speichern(geraet_pruefen(str(d.get("ip", ""))), d.get("werte"))
                return self.json({"ok": True, "kopie": kopie})
            if p == "/api/node/punkt":
                import nodekal
                d = self.body_json(2000)
                kopie, antwort = nodekal.punkt(geraet_pruefen(str(d.get("ip", ""))), str(d.get("groesse", "")), d.get("ref"))
                return self.json({"ok": True, "kopie": kopie, "antwort": antwort})
            if p == "/api/wlan/start":
                import installer, improv
                if not installer.verfuegbar():
                    return self.fehler("pyserial fehlt")
                d = self.body_json(4096)
                ok = improv.starten(str(d.get("aktion", "")), str(d.get("port", "")), str(d.get("ssid", "")), str(d.get("passwort", "")),
                                    [x["port"] for x in installer.ports()])
                return self.json({"ok": ok, "text": "gestartet" if ok else "Es läuft schon ein Vorgang"}, 200 if ok else 409)
            if p == "/api/alle/updates":
                import gruppe
                d = self.body_json(20_000)
                ok = gruppe.updates_starten([geraet_pruefen(str(x)) for x in d.get("ips", [])])
                return self.json({"ok": ok, "text": "gestartet" if ok else "Es läuft schon ein Vorgang"}, 200 if ok else 409)
            if p == "/api/alle/einstellung":
                import gruppe
                d = self.body_json(20_000)
                return self.json(gruppe.einstellung(d.get("werte") or {}, [geraet_pruefen(str(x)) for x in d.get("ips", [])], bool(d.get("ausfuehren"))))
            if p == "/api/netzcheck/adresse":
                import netzcheck
                return self.json(netzcheck.adresse(str(self.body_json(2000).get("adresse", ""))))
            if p == "/api/suche":
                return self.json({"ok": jetzt_suchen()})
            if p == "/api/alle-sichern":
                ordner, erg = alle_sichern()
                return self.json({"ordner": ordner, "ergebnis": [{"name": n, "ok": ok, "text": t} for n, ok, t in erg]})
            if p == "/api/passwort":
                import passwoerter
                d = self.body_json(2000)
                ip = geraet_pruefen(str(d.get("ip", "")))
                if d.get("loeschen"):
                    passwoerter.loeschen(ip)
                    return self.json({"ok": True})
                return self.json(passwort_pruefen_speichern(ip, str(d.get("passwort", ""))))
            if p == "/api/update/starten":
                ip = geraet_pruefen(str(self.body_json(2000).get("ip", "")))
                return self.json({"antwort": update_starten(ip)})
            if p == "/api/geraete/hinzufuegen":
                return self.json({"name": geraet_hinzufuegen(str(self.body_json(2000).get("adresse", "")))})
            if p == "/api/geraete/aendern":
                import einstellungen
                d = self.body_json(2000)
                ip = geraet_pruefen(str(d.get("ip", "")))
                def aendern(e):
                    if "alias" in d:
                        n = str(d["alias"] or "").strip()[:60]
                        e["alias"].pop(ip, None) if not n else e["alias"].__setitem__(ip, n)
                    if "ausgeblendet" in d:
                        if d["ausgeblendet"] and ip not in e["ausgeblendet"]:
                            e["ausgeblendet"].append(ip)
                        elif not d["ausgeblendet"] and ip in e["ausgeblendet"]:
                            e["ausgeblendet"].remove(ip)
                einstellungen.aendern(aendern)
                if d.get("entfernen"):
                    geraet_vergessen(ip, bool(d.get("verlauf_loeschen")))
                return self.json({"ok": True})
            if p == "/api/einstellungen":
                import einstellungen
                d = self.body_json(4000)
                def aendern(e):
                    for art in ("warnung", "problem", "info"):
                        if art in d.get("mitteilungen", {}):
                            e["mitteilungen"][art] = bool(d["mitteilungen"][art])
                    if "versionssuche" in d:
                        e["versionssuche"] = bool(d["versionssuche"])
                    if "protokolle" in d:
                        e["protokolle"] = bool(d["protokolle"])
                    if "auto_entfernen_tage" in d:
                        e["auto_entfernen_tage"] = max(0, min(int(d["auto_entfernen_tage"]), 365))
                    if "auto_sichern" in d:
                        a = d["auto_sichern"]
                        if a.get("modus") in ("aus", "taeglich", "woechentlich"):
                            e["auto_sichern"]["modus"] = a["modus"]
                        if "behalten" in a:
                            e["auto_sichern"]["behalten"] = max(1, min(int(a["behalten"]), 365))
                einstellungen.aendern(aendern)
                return self.json({"ok": True})
            if p == "/api/alarme":
                import einstellungen
                d = self.body_json(4000)
                if d.get("loeschen"):
                    einstellungen.aendern(lambda e: e.__setitem__("alarme", [a for a in e["alarme"] if a["id"] != str(d["loeschen"])]))
                else:
                    neu = einstellungen.alarm_pruefen(d)
                    einstellungen.aendern(lambda e: e.__setitem__("alarme", [a for a in e["alarme"] if a["id"] != neu["id"]] + [neu]))
                return self.json({"ok": True})
            if p == "/api/autostart":
                import autostart
                return self.json({"aktiv": autostart.setzen(bool(self.body_json(500).get("an")))})
            if p == "/api/wiederherstellen":
                import sicherung
                d = self.body_json()
                ip = geraet_pruefen(str(d.get("ip", "")))
                roh = sicherung.sicherung_lesen(str(d["datei"])) if d.get("datei") else str(d.get("inhalt", "")).encode("utf-8")
                meldung, kopie = sicherung.wiederherstellen(ip, roh)
                return self.json({"meldung": meldung, "kopie": kopie})
            if p == "/api/kopieren":
                import sicherung
                d = self.body_json(20_000)
                erg = sicherung.kopieren(geraet_pruefen(str(d.get("quelle", ""))), [geraet_pruefen(str(x)) for x in d.get("ziele", [])],
                                         [str(g) for g in d.get("gruppen", [])], bool(d.get("ausfuehren")))
                return self.json(erg)
            if p == "/api/diagnose":
                import sicherung
                d = self.body_json(20_000)
                pfad, hinweise = sicherung.diagnose([geraet_pruefen(str(x)) for x in d.get("ips", [])], bool(d.get("einstellungen")))
                return self.json({"name": os.path.basename(pfad), "ordner": os.path.dirname(pfad), "hinweise": hinweise})
        except KeyError as e:
            return self.fehler(str(e).strip("'\""), 404)
        except Exception as e:   # Fehler der Module (Fehler-Klassen) und Netz
            return self.fehler(str(e) or type(e).__name__, 400)
        self.senden(404, "text/plain", "nicht gefunden")

    # ── GET ──
    def do_GET(self):
        p = self.path.split("?")[0]
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        arg = lambda k, d="": qs.get(k, [d])[0]
        if not self.host_ok():
            return self.senden(403, "text/plain", "abgelehnt")
        if self.lan_gesperrt(p):
            return self.senden(403, "text/plain; charset=utf-8", "Im Netzwerkmodus ist Control nur zum Ansehen da.")
        import seiten
        seiten_tabelle = {"/": seiten.UEBERSICHT, "/geraet": seiten.GERAET, "/verlauf": seiten.VERLAUF, "/wand": seiten.WAND, "/kopieren": seiten.KOPIEREN, "/installer": seiten.INSTALLER, "/einstellungen": seiten.EINSTELLUNGEN, "/alle": seiten.ALLE, "/assistent": seiten.ASSISTENT, "/hilfe": seiten.HILFE, "/kalibrierung": seiten.KALIBRIERUNG}
        if p in seiten_tabelle:
            return self.senden(200, "text/html; charset=utf-8", seiten_tabelle[p])
        if p in ASSETS:
            datei, typ = ASSETS[p]
            return self.senden(200, typ, ressource(datei), {"Cache-Control": "max-age=3600"})
        if p == "/manifest.json":
            return self.senden(200, "application/manifest+json", json.dumps(MANIFEST))
        if p == "/sw.js":
            return self.senden(200, "application/javascript", SW)
        try:
            if p == "/api/geraete":
                import details
                return self.json(details.anreichern(als_liste(alle=bool(arg("alle")) and not LAN)))
            if p == "/api/einstellungen":
                import einstellungen, autostart
                e = einstellungen.holen()
                e.pop("interne_quellen", None)   # nie an die Oberflaeche geben
                e["autostart"] = {"verfuegbar": autostart.verfuegbar(), "aktiv": autostart.aktiv() if autostart.verfuegbar() else False}
                e["alarm_metriken"] = einstellungen.METRIKEN
                e["sicherungsordner"] = SICHERUNGSORDNER
                return self.json(e)
            if p == "/api/passwort/status":
                import passwoerter
                return self.json(passwoerter.status(geraet_pruefen(arg("ip"))))
            if p == "/api/update/pruefen":
                return self.json(update_pruefen(geraet_pruefen(arg("ip"))))
            if p == "/api/verlauf.csv":
                import verlauf
                return self.senden(200, "text/csv; charset=utf-8", verlauf.csv_export(int(arg("stunden", "168"))),
                                   {"Content-Disposition": f'attachment; filename="wettercube-verlauf-{time.strftime("%Y-%m-%d")}.csv"'})
            if p == "/api/verlauf/tage":
                import verlauf
                return self.json(verlauf.tage(arg("metrik", "temp"), int(arg("tage", "14"))))
            if p == "/api/info":
                return self.json({"version": VERSION})
            if p == "/api/ereignisse":
                import details
                return self.json(details.neue_ereignisse(int(arg("seit", "0") or 0)))
            if p == "/api/bild":
                ip = geraet_pruefen(arg("ip"))
                if _geraete[ip].get("demo"):
                    if not _geraete[ip].get("demo_bild"):
                        return self.fehler("Kein Bildschirmfoto verfügbar", 502)
                    return self.senden(200, "image/png", ressource("assets/demo/" + _geraete[ip]["demo_bild"]))
                s = arg("s")
                if s and not re.fullmatch(r"[a-z0-9_]{1,20}", s):
                    return self.fehler("ungültiger Bildschirm")
                roh = None
                sperre = _bild_sperren.setdefault(ip, threading.Lock())
                if not sperre.acquire(blocking=False):   # je Geraet nur ein Bildschirmfoto gleichzeitig (es belastet Fusion und Apex stark)
                    return self.fehler("Das Gerät erstellt gerade schon ein Bildschirmfoto", 429)
                try:
                    for pfad in ("/screenshot.png", "/screenshot"):   # Fusion/Apex liefern PNG, das Next ein BMP unter /screenshot
                        try:
                            roh = http_get(f"http://{ip}{pfad}" + (f"?s={s}" if s else ""), 30, 4_000_000)
                            break
                        except Exception:
                            continue
                finally:
                    sperre.release()
                if roh is None:
                    return self.fehler("Kein Bildschirmfoto verfügbar", 502)
                bmp = roh[:2] == b"BM"
                kopf = {"Content-Disposition": f'attachment; filename="{dateiname(_geraete[ip].get("name", ip), ip).replace(".json", ".bmp" if bmp else ".png")}"'} if arg("dl") else None
                return self.senden(200, "image/bmp" if bmp else "image/png", roh, kopf)
            if p == "/api/log":
                import details
                ip = geraet_pruefen(arg("ip"))
                try:
                    return self.senden(200, "text/plain; charset=utf-8", details.log_text(ip))
                except urllib.error.HTTPError as e:
                    import passwoerter
                    return self.senden(502, "text/plain; charset=utf-8", passwoerter.fehlertext(ip) if e.code == 401 else f"Fehler {e.code}")
                except Exception:
                    return self.senden(502, "text/plain; charset=utf-8", "Gerät nicht erreichbar")
            if p == "/api/sicherung":
                name, roh = sicherung_holen(arg("ip"))
                return self.senden(200, "application/json", roh, {"Content-Disposition": f'attachment; filename="{dateiname(name, arg("ip"))}"'})
            if p == "/api/sicherungen":
                import sicherung
                return self.json(sicherung.sicherungen_liste(geraet_pruefen(arg("ip"))))
            if p == "/api/diagnose-datei":
                import sicherung
                name = arg("name")
                if not re.fullmatch(r"wettercube-diagnose-[0-9-]+\.zip", name):
                    return self.fehler("ungültiger Name")
                with open(os.path.join(sicherung.DIAGNOSEORDNER, name), "rb") as f:
                    return self.senden(200, "application/zip", f.read(), {"Content-Disposition": f'attachment; filename="{name}"'})
            if p == "/api/verlauf/vergleich":
                import verlauf
                return self.json(verlauf.vergleich(arg("metrik", "s_temp"), int(arg("stunden", "24"))))
            if p == "/api/protokolle":
                import protokolle
                ip = geraet_pruefen(arg("ip"))
                with _sperre:
                    d = dict(_geraete[ip])
                return self.json({"ordner": protokolle.ordner_von(anzeigename(d), ip), "an": protokolle.an(), "tage": protokolle.liste(anzeigename(d), ip)})
            if p == "/api/protokoll":
                import protokolle
                ip = geraet_pruefen(arg("ip"))
                with _sperre:
                    d = dict(_geraete[ip])
                tag = arg("tag")
                kopf = {"Content-Disposition": f'attachment; filename="{os.path.basename(protokolle.ordner_von(anzeigename(d), ip))}-{tag}.log"'} if arg("dl") else None
                return self.senden(200, "text/plain; charset=utf-8", protokolle.lesen(anzeigename(d), ip, tag), kopf)
            if p == "/api/verlauf/metriken":
                import verlauf
                return self.json(verlauf.METRIKEN)
            if p == "/api/verlauf":
                import verlauf
                return self.json({"daten": verlauf.abfrage(arg("metrik", "temp"), int(arg("stunden", "24"))), "anzahl": verlauf.anzahl()})
            if p == "/api/kopieren/gruppen":
                import sicherung
                with _sperre:
                    hat_node = any((d.get("status") or {}).get("geraet") == "node" for d in _geraete.values())
                return self.json({k: v[0] for k, v in sicherung.GRUPPEN.items() if hat_node or k not in sicherung.NUR_NODE})
            if p == "/api/node/kalibrierung":
                import nodekal
                return self.json(nodekal.lesen(geraet_pruefen(arg("ip"))))
            if p == "/api/installer/info":
                import installer
                ok = installer.verfuegbar()
                return self.json({"verfuegbar": ok, "produkte": installer.produkte(), "ports": installer.ports() if ok else []})
            if p == "/api/installer/versionen":
                import installer
                return self.json(installer.versionen(arg("produkt")))
            if p == "/api/installer/plan":
                import installer
                chip, teile, ver, _ = installer.plan(arg("produkt"), arg("version"))
                return self.json({"chip": chip, "version": ver, "dateien": [t[0] for t in teile]})
            if p == "/api/update/aenderungen":
                import aenderungen, details
                ip = geraet_pruefen(arg("ip"))
                with _sperre:
                    d = dict(_geraete[ip])
                produkt = details.produkt_von(d)
                if produkt is None and "apex" in (d.get("name") or "").lower():   # Apex: verdeckte Update-Quelle, das Geraet liefert die Liste selbst
                    return self.json(aenderungen.vom_geraet(ip, arg("version")))
                return self.json(aenderungen.fuer(produkt, arg("version")))
            if p == "/api/alle/plan":
                import gruppe
                return self.json({"geraete": [{"ip": d["ip"], "name": d["name"], "online": d.get("online") is not False} for d in als_liste()],
                                  "aktionen": {k: {"titel": v[3], "min": v[1], "max": v[2]} for k, v in gruppe.AKTIONEN.items()}})
            if p == "/api/alle/status":
                import gruppe
                return self.json(gruppe.status())
            if p == "/api/netzcheck":
                import netzcheck
                return self.json(netzcheck.pruefen())
            if p == "/api/wlan/status":
                import improv
                return self.json(improv.status())
            if p == "/api/installer/status":
                import installer
                return self.json(installer.status())
        except KeyError as e:
            return self.fehler(str(e).strip("'\""), 404)
        except SicherungsFehler as e:
            return self.fehler(str(e), 502)
        except FileNotFoundError:
            return self.fehler("Datei nicht gefunden", 404)
        except ValueError as e:   # ungueltige Eingabe
            return self.fehler(str(e) or "ungültige Eingabe", 400)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                import passwoerter
                return self.fehler(passwoerter.fehlertext(arg("ip")), 502)
            return self.fehler(f"Das Gerät antwortet mit Fehler {e.code}", 502)
        except Exception as e:
            return self.fehler("Fehler: " + (str(e) or type(e).__name__), 502)
        self.senden(404, "text/plain", "nicht gefunden")


def main():
    global _extra, LAN, KEINE_SUCHE, DEMO
    ap = argparse.ArgumentParser(description="WetterCube Control " + VERSION)
    ap.add_argument("--lan", action="store_true", help="im Heimnetz erreichbar, aber nur zum Ansehen (fuer NAS/Raspberry Pi/Handy)")
    ap.add_argument("--text", action="store_true", help="einmal suchen, Zeilen ausgeben, beenden")
    ap.add_argument("--geraet", action="append", default=[], help="feste Adresse zusaetzlich (mehrfach moeglich)")
    ap.add_argument("--demo", action="store_true", help="erfundene Geraete zeigen (fuer Fotos und zum Ausprobieren), keine Netzabfragen, nichts wird gespeichert")
    ap.add_argument("--keine-suche", action="store_true", help="das Netz nicht absuchen, nur --geraet-Adressen und selbst hinzugefuegte Geraete verwenden")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args()
    _extra = list(a.geraet)
    LAN = a.lan
    KEINE_SUCHE = a.keine_suche
    if a.demo:
        import tempfile
        DEMO = KEINE_SUCHE = True
        tmp = tempfile.mkdtemp(prefix="wettercube-demo-")
        for k, v in (("WETTERCUBE_VERLAUF", "/v.db"), ("WETTERCUBE_EINSTELLUNGEN", "/e.json"), ("WETTERCUBE_SICHERUNGEN", "/s"), ("WETTERCUBE_DIAGNOSE", "/d"), ("WETTERCUBE_PROTOKOLLE", "/p")):
            os.environ[k] = tmp + v
        os.environ["WETTERCUBE_PW_NUR_SPEICHER"] = "1"
        globals()["SICHERUNGSORDNER"] = tmp + "/s"
        demo_laden()
    if a.text:
        g = suchen()
        for ip, d in sorted(g.items()):
            s = d["status"]
            if s:
                print(f"{d['name']:<22} {ip:<15} v{s['version']:<12} {s['temp']:>5} °C  {s.get('wetter','')}  Warnungen: {s.get('dwd', 0)}")
            else:
                print(f"{d['name']:<22} {ip:<15} (nur Link, keine /api/status)")
        if not g:
            print("keine Geraete gefunden")
        return
    threading.Thread(target=hintergrund, daemon=True).start()
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, a.port), Handler)
    print(f"WetterCube Control {VERSION}: http://localhost:{a.port}" + ("  (im Netzwerk, nur zum Ansehen)" if a.lan else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.modules["control"] = sys.modules["__main__"]   # die Teilprogramme (details, verlauf, ...) importieren "control" und sehen so denselben Zustand
    main()
