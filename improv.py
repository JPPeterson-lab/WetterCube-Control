# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""WLAN per USB einrichten: Improv Serial (https://www.improv-wifi.com/serial/).

Ein frisch aufgespieltes Geraet (oder eines im Einrichtungsmodus) bekommt den WLAN-Namen und das Passwort ueber das USB-Kabel,
ohne dass man sich erst mit dem Einrichtungs-WLAN des Geraets verbinden muss. Das Geraet muss das Protokoll kennen.
Das Passwort wird nur ans Geraet gesendet: nie gespeichert, nie ins Protokoll geschrieben.

Paket: "IMPROV", Version 1, Typ, Laenge, Daten, Pruefsumme (Summe aller vorherigen Bytes modulo 256), Zeilenumbruch.
"""
import threading, time

KOPF = b"IMPROV"
VERSION = 1
T_ZUSTAND, T_FEHLER, T_RPC, T_ERGEBNIS = 1, 2, 3, 4
C_WLAN, C_ZUSTAND, C_INFO, C_NETZE = 1, 2, 3, 4
Z_GESTOPPT, Z_BEREIT, Z_VERBINDET, Z_VERBUNDEN = 0, 2, 3, 4
FEHLER = {
    0: "",
    1: "Das Gerät hat das Paket nicht verstanden.",
    2: "Das Gerät kennt diesen Befehl nicht.",
    3: "Das Gerät konnte sich nicht mit dem WLAN verbinden. Name und Passwort prüfen.",
    5: "Ungültiger Gerätename.",
    255: "Unbekannter Fehler im Gerät.",
}
ZUSTAND = {Z_GESTOPPT: "Das Gerät nimmt gerade keine WLAN-Daten an.", Z_BEREIT: "bereit", Z_VERBINDET: "verbindet", Z_VERBUNDEN: "verbunden"}


# ── Paket bauen und lesen ────────────────────────────────────────────────────
def paket(typ, daten=b""):
    if len(daten) > 255:
        raise ValueError("Paket zu lang")
    roh = KOPF + bytes([VERSION, typ, len(daten)]) + daten
    return roh + bytes([sum(roh) & 0xFF]) + b"\n"


def rpc(befehl, daten=b""):
    if len(daten) > 253:
        raise ValueError("Befehl zu lang")
    return paket(T_RPC, bytes([befehl, len(daten)]) + daten)


def texte_kodieren(*texte):
    """Zeichenketten mit vorangestellter Laenge (UTF-8) aneinanderhaengen."""
    aus = b""
    for t in texte:
        b = t.encode("utf-8")
        if len(b) > 255:
            raise ValueError("Text zu lang")
        aus += bytes([len(b)]) + b
    return aus


def texte_lesen(daten):
    """Gegenstueck: Liste von Zeichenketten aus laengenpraefixierten Bytes."""
    aus, i = [], 0
    while i < len(daten):
        n = daten[i]
        aus.append(daten[i + 1:i + 1 + n].decode("utf-8", "replace"))
        i += 1 + n
    return aus


class Leser:
    """Sammelt empfangene Bytes (dazwischen laufen die normalen Log-Zeilen des Geraets) und liefert vollstaendige Pakete."""

    def __init__(self):
        self.puffer = bytearray()

    def fuettern(self, daten):
        self.puffer += daten
        erg = []
        while True:
            i = self.puffer.find(KOPF)
            if i < 0:
                del self.puffer[:max(0, len(self.puffer) - len(KOPF) + 1)]   # Rest koennte der Anfang eines Kopfes sein
                break
            del self.puffer[:i]
            if len(self.puffer) < 9:
                break
            laenge = self.puffer[8]
            gesamt = 9 + laenge + 1
            if len(self.puffer) < gesamt:
                break
            p = bytes(self.puffer[:gesamt])
            if p[6] == VERSION and (sum(p[:-1]) & 0xFF) == p[-1]:
                erg.append((p[7], p[9:9 + laenge]))
                del self.puffer[:gesamt]
            else:
                del self.puffer[:1]   # kein gueltiges Paket: weitersuchen
        return erg


# ── Verbindung ───────────────────────────────────────────────────────────────
def _oeffnen(port):
    """Anschluss oeffnen, ohne das Geraet neu zu starten (DTR und RTS vor dem Oeffnen aus). Auch pyserial-Adressen (socket://) gehen, fuer Tests."""
    import serial
    s = serial.serial_for_url(port, do_not_open=True, baudrate=115200, timeout=0.1, write_timeout=2)
    try:
        s.dtr = False
        s.rts = False
    except Exception:
        pass
    s.open()
    return s


def _warten(ser, leser, bis, bedingung=None):
    """Pakete lesen, bis bedingung(typ, daten) wahr wird oder die Zeit ablaeuft. Rueckgabe: alle gelesenen Pakete."""
    gelesen = []
    while time.time() < bis:
        daten = ser.read(512)
        if not daten:
            continue
        for p in leser.fuettern(daten):
            gelesen.append(p)
            if bedingung and bedingung(*p):
                return gelesen
    return gelesen


def _zustand_abfragen(ser, leser, sekunden):
    """Zustand abfragen und die Anfrage jede Sekunde wiederholen: Viele Boards (CYD, ESP32 mit CH340/CH343) starten neu, sobald der Anschluss geoeffnet wird;
    die erste Anfrage geht dann waehrend des Starts verloren, und kurz nach dem Start meldet das Geraet noch "gestoppt" (WLAN wird gerade aufgebaut).
    Es wird gewartet, bis das Geraet bereit oder verbunden ist. Rueckgabe: Zustandsbyte (zuletzt gemeldet) oder None, wenn nichts geantwortet hat."""
    ende = time.time() + sekunden
    ser.reset_input_buffer()
    zuletzt = None
    while time.time() < ende:
        ser.write(rpc(C_ZUSTAND))
        ser.flush()
        pakete = _warten(ser, leser, min(ende, time.time() + 1.0), lambda t, d: t == T_ZUSTAND)
        zust = next((d[0] for t, d in pakete if t == T_ZUSTAND and d), None)
        if zust is not None:
            zuletzt = zust
            if zust != Z_GESTOPPT:
                return zust
    return zuletzt


def pruefen(ser, leser, sekunden=30):
    """Fragt Zustand und Geraeteinformation ab. Rueckgabe: None (kennt Improv nicht) oder {"zustand", "info"}."""
    zust = _zustand_abfragen(ser, leser, sekunden)
    if zust is None:
        return None
    ser.write(rpc(C_INFO))
    ser.flush()
    pakete = _warten(ser, leser, time.time() + 3, lambda t, d: t == T_ERGEBNIS and d[:1] == bytes([C_INFO]))
    info = []
    for t, d in pakete:
        if t == T_ERGEBNIS and len(d) >= 2 and d[0] == C_INFO:
            info = texte_lesen(d[2:2 + d[1]])
    return {"zustand": zust, "info": info}


def netze_suchen(ser, leser, sekunden=15):
    """Das Geraet sucht WLAN-Netze. Rueckgabe: Liste {"ssid", "rssi", "gesichert"} (staerkstes zuerst, ohne Doppelte)."""
    _zustand_abfragen(ser, leser, 30)    # nach dem Oeffnen des Anschlusses kann das Geraet noch neu starten
    ser.reset_input_buffer()
    ser.write(rpc(C_NETZE))
    ser.flush()
    ende = time.time() + sekunden
    erg = {}
    fertig = False
    while time.time() < ende and not fertig:
        for t, d in _warten(ser, leser, min(ende, time.time() + 1)):
            if t == T_ERGEBNIS and len(d) >= 2 and d[0] == C_NETZE:
                s = texte_lesen(d[2:2 + d[1]])
                if not s:
                    fertig = True
                elif len(s) >= 3 and s[0]:
                    try:
                        rssi = int(s[1])
                    except ValueError:
                        rssi = -100
                    if s[0] not in erg or rssi > erg[s[0]]["rssi"]:
                        erg[s[0]] = {"ssid": s[0], "rssi": rssi, "gesichert": s[2].upper() == "YES"}
            elif t == T_FEHLER and d and d[0] == 2:
                raise RuntimeError(FEHLER[2])
    return sorted(erg.values(), key=lambda n: -n["rssi"])


def wlan_senden(ser, leser, ssid, passwort, melden=lambda text: None, sekunden=50):
    """WLAN-Daten senden und auf das Ergebnis warten. Rueckgabe: (ok, text, adresse)."""
    _zustand_abfragen(ser, leser, 30)    # nach dem Oeffnen des Anschlusses kann das Geraet noch neu starten
    ser.reset_input_buffer()
    ser.write(rpc(C_WLAN, texte_kodieren(ssid, passwort)))
    ser.flush()
    ende = time.time() + sekunden
    adresse = ""
    verbunden = False
    gemeldet = False
    while time.time() < ende:
        for t, d in _warten(ser, leser, min(ende, time.time() + 1)):
            if t == T_FEHLER and d and d[0] != 0:
                return False, FEHLER.get(d[0], FEHLER[255]), ""
            if t == T_ZUSTAND and d:
                if d[0] == Z_VERBINDET and not gemeldet:
                    gemeldet = True
                    melden("Das Gerät verbindet sich mit dem WLAN ...")
                if d[0] == Z_VERBUNDEN:
                    verbunden = True
            if t == T_ERGEBNIS and len(d) >= 2 and d[0] == C_WLAN:
                s = texte_lesen(d[2:2 + d[1]])
                adresse = s[0] if s else ""
                verbunden = True
        if verbunden:
            return True, "Das Gerät ist mit dem WLAN verbunden.", adresse
    return False, ("Keine Antwort vom Gerät. Es kennt WLAN per USB vielleicht nicht (neuere Firmware nötig) oder steckt nicht im Einrichtungsmodus."
                   " Alternative: Verbinde dich mit dem Einrichtungs-WLAN des Geräts (Name und Passwort stehen auf seinem Display) und öffne 192.168.4.1."), ""


# ── Ablauf fuer die Oberflaeche (im Hintergrund, Status abfragbar) ─────────────
_sperre = threading.Lock()
_zustand = {"laeuft": False, "ok": None, "text": "", "netze": [], "adresse": "", "info": [], "aktion": ""}


def status():
    with _sperre:
        return dict(_zustand, netze=list(_zustand["netze"]), info=list(_zustand["info"]))


def _setze(**kw):
    with _sperre:
        _zustand.update(kw)


def starten(aktion, port, ssid="", passwort="", ports_erlaubt=()):
    """aktion: "pruefen", "netze" oder "senden". Rueckgabe False, wenn schon ein Vorgang laeuft."""
    if aktion not in ("pruefen", "netze", "senden"):
        raise ValueError("unbekannte Aktion")
    if port not in ports_erlaubt:
        raise ValueError("unbekannter Anschluss")
    if aktion == "senden" and (not ssid or len(ssid.encode("utf-8")) > 32 or len(passwort.encode("utf-8")) > 63):
        raise ValueError("WLAN-Name (bis 32 Zeichen) und Passwort (bis 63 Zeichen) prüfen")
    with _sperre:
        if _zustand["laeuft"]:
            return False
        _zustand.update({"laeuft": True, "ok": None, "text": "Verbinde mit dem Gerät (nach dem Öffnen des Anschlusses startet es manchmal neu, das kann bis zu 30 Sekunden dauern) ...", "aktion": aktion, "adresse": ""})
        if aktion == "pruefen":
            _zustand["info"] = []

    def arbeit():
        ser = None
        try:
            ser = _oeffnen(port)
            leser = Leser()
            if aktion == "pruefen":
                r = pruefen(ser, leser)
                if r is None:
                    _setze(ok=False, text="Das Gerät antwortet nicht auf WLAN per USB. Es braucht eine neuere Firmware und muss eingeschaltet sein (nicht im Flash-Modus)."
                                    + " Alternative: Verbinde dich mit dem Einrichtungs-WLAN des Geräts (Name und Passwort stehen auf seinem Display) und öffne 192.168.4.1.")
                else:
                    z = ZUSTAND.get(r["zustand"], "?")
                    _setze(ok=True, info=r["info"], text="Gerät gefunden: " + (" ".join(r["info"][:2]) or "unbekannt") + ". " + (
                        "Es nimmt WLAN-Daten an." if r["zustand"] == Z_BEREIT else ("Es ist schon mit einem WLAN verbunden." if r["zustand"] == Z_VERBUNDEN else z)))
            elif aktion == "netze":
                _setze(text="Das Gerät sucht WLAN-Netze ...")
                n = netze_suchen(ser, leser)
                _setze(ok=bool(n), netze=n, text=f"{len(n)} Netze gefunden." if n else "Das Gerät hat kein Netz gefunden (oder kennt die Suche nicht). Den Namen kannst du von Hand eintragen.")
            else:
                ok, text, adresse = wlan_senden(ser, leser, ssid, passwort, melden=lambda t: _setze(text=t))
                _setze(ok=ok, text=text, adresse=adresse)
        except Exception as e:
            _setze(ok=False, text="Das hat nicht geklappt: " + str(e).replace(passwort, "***") if passwort else "Das hat nicht geklappt: " + str(e))
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
            _setze(laeuft=False)

    threading.Thread(target=arbeit, daemon=True).start()
    return True
