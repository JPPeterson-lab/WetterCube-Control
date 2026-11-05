# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Web-Passwoerter der Geraete (Benutzer "admin"), im Schluesselbund des Systems abgelegt (macOS-Schluesselbund, Windows-Anmeldeinformationen,
Linux: Secret Service). Ohne Schluesselbund bleibt das Passwort nur bis zum Beenden von Control im Speicher.

Die Geraete verlangen das Passwort nur fuer Sichern/Wiederherstellen, Log, Update usw.; /api/status bleibt offen. Nach einer Ablehnung
schickt Control das gespeicherte Passwort nicht noch einmal mit, damit die Sperre des Geraets (8 falsche Versuche, 1 Minute) nie ausgeloest wird.
"""
import base64, os, threading

DIENST = "WetterCube Control"
_sperre = threading.Lock()
_speicher = {}     # Adresse -> Passwort (Sitzung bzw. wenn kein Schluesselbund da ist)
_falsch = set()    # Adressen, deren Passwort das Geraet abgelehnt hat


def _schluesselbund():
    if os.environ.get("WETTERCUBE_PW_NUR_SPEICHER"):
        return None
    try:
        import keyring
        return keyring
    except Exception:
        return None


def holen(adresse):
    with _sperre:
        if adresse in _speicher:
            return _speicher[adresse]
    kr = _schluesselbund()
    if kr is None:
        return None
    try:
        return kr.get_password(DIENST, adresse)
    except Exception:
        return None


def setzen(adresse, passwort):
    """Gibt 'schluesselbund' oder 'sitzung' zurueck (wo das Passwort liegt)."""
    kr = _schluesselbund()
    with _sperre:
        _falsch.discard(adresse)
    if kr is not None:
        try:
            kr.set_password(DIENST, adresse, passwort)
            with _sperre:
                _speicher.pop(adresse, None)
            return "schluesselbund"
        except Exception:
            pass
    with _sperre:
        _speicher[adresse] = passwort
    return "sitzung"


def loeschen(adresse):
    with _sperre:
        _speicher.pop(adresse, None)
        _falsch.discard(adresse)
    kr = _schluesselbund()
    if kr is not None:
        try:
            kr.delete_password(DIENST, adresse)
        except Exception:
            pass


def abgelehnt(adresse):
    with _sperre:
        _falsch.add(adresse)


def status(adresse):
    pw = holen(adresse)
    with _sperre:
        return {"gesetzt": pw is not None, "falsch": adresse in _falsch}


def kopf(adresse):
    """HTTP-Kopf fuer Anfragen an das Geraet ({} ohne Passwort oder nach einer Ablehnung)."""
    pw = holen(adresse)
    with _sperre:
        if pw is None or adresse in _falsch:
            return {}
    return {"Authorization": "Basic " + base64.b64encode(("admin:" + pw).encode("utf-8")).decode("ascii")}


def fehlertext(adresse):
    """Verstaendlicher Text fuer eine 401-Antwort des Geraets; merkt sich eine Ablehnung des gespeicherten Passworts."""
    if kopf(adresse):
        abgelehnt(adresse)
        return "Das gespeicherte Passwort wurde vom Gerät abgelehnt. Bitte auf der Geräteseite unter „Passwort des Geräts“ neu eintragen."
    if status(adresse)["gesetzt"]:
        return "Das gespeicherte Passwort wurde abgelehnt. Bitte auf der Geräteseite unter „Passwort des Geräts“ neu eintragen."
    return "Das Gerät verlangt ein Passwort. Trage es auf der Geräteseite unter „Passwort des Geräts“ ein."
