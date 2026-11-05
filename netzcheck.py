# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Hilfe "Geraet nicht gefunden?": prueft Schritt fuer Schritt, woran es liegen kann, und sagt es in Klartext.

Alles bleibt im eigenen Netz (kein Internet). Die Pruefungen aendern nichts an den Geraeten.
"""
import ipaddress, re, socket, threading, time

import control as c

NAMEN = ["wettercube-fusion.local", "wettercube-apex.local", "wettercubeplus.local", "wettercube-next.local"]


def _privat(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _aufloesen(name, timeout=3.0):
    erg = []
    t = threading.Thread(target=lambda: erg.append(_gethost(name)), daemon=True)
    t.start()
    t.join(timeout)
    return erg[0] if erg else None


def _gethost(name):
    try:
        return socket.gethostbyname(name)
    except OSError:
        return None


def pruefen():
    """Liste von Schritten {"titel", "stufe": ok|warn|fehler|info, "text"}."""
    s = []
    netz, eigene = c.eigenes_netz()
    if eigene.startswith("127."):
        s.append({"titel": "Dein Rechner im Netzwerk", "stufe": "fehler", "text": "Dieser Rechner hat keine Netzwerkadresse. Ist er mit dem WLAN oder per Kabel mit dem Router verbunden?"})
    elif not _privat(eigene):
        s.append({"titel": "Dein Rechner im Netzwerk", "stufe": "warn", "text": f"Die Adresse dieses Rechners ({eigene}) sieht nicht nach einem Heimnetz aus. Läuft ein VPN? Dann schalte es zum Suchen kurz aus."})
    else:
        s.append({"titel": "Dein Rechner im Netzwerk", "stufe": "ok", "text": f"Adresse {eigene}. Control sucht die Geräte im Bereich {netz} (alle Adressen mit denselben ersten drei Zahlen)."})

    liste = c.als_liste(alle=True)
    on = [d for d in liste if d.get("online") is not False]
    off = [d for d in liste if d.get("online") is False]
    if on:
        s.append({"titel": "Gefundene Geräte", "stufe": "ok", "text": f"{len(on)} Gerät(e) antworten: " + ", ".join(d["name"] for d in on) + "."})
    else:
        s.append({"titel": "Gefundene Geräte", "stufe": "fehler", "text": "Kein Gerät antwortet im Moment."})
    for d in off:
        s.append({"titel": d["name"], "stufe": "warn", "text": f"Bekannt, antwortet aber nicht ({d['ip']}). Ist es eingeschaltet und im WLAN? Das Display zeigt bei Verbindungsproblemen den Einrichtungsmodus."})

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(len(NAMEN)) as ex:
        gefunden = {n: ip for n, ip in zip(NAMEN, ex.map(_aufloesen, NAMEN)) if ip}
    if gefunden:
        s.append({"titel": "Namen im Heimnetz (mDNS)", "stufe": "ok", "text": "Gefunden: " + ", ".join(f"{n} → {i}" for n, i in gefunden.items()) + "."})
    else:
        s.append({"titel": "Namen im Heimnetz (mDNS)", "stufe": "info", "text": "Keiner der Standardnamen (wettercube-fusion.local, wettercube-apex.local, …) wurde aufgelöst. Das ist kein Fehler: Manche Rechner oder Router lösen .local-Namen nicht auf. Die Suche über Adressen klappt trotzdem."})

    if not on:
        import sys
        tipps = [
            "Rechner und Gerät müssen im selben Netz sein: Ein Gast-WLAN oder ein anderes WLAN (zum Beispiel 5 GHz getrennt vom 2,4-GHz-Netz mit eigenem Namen) trennt sie oft. Die Geräte brauchen das 2,4-GHz-WLAN.",
            "Router (zum Beispiel FRITZ!Box): Prüfe, ob WLAN-Geräte untereinander kommunizieren dürfen (kein „Heimnetz-Isolation“, kein „Gerätesicherheit/AP-Isolation“).",
            "Repeater, Mesh oder getrennte Netze (VLAN): Das Gerät und dieser Rechner müssen im selben Bereich hängen. Sonst trage die Adresse des Geräts unten von Hand ein.",
            "Firewall oder Virenscanner auf dem Rechner kann das Suchen blockieren. Erlaube WetterCube Control das Netzwerk.",
        ]
        if sys.platform == "darwin":
            tipps.insert(0, "Mac: Seit macOS 15 muss jedes Programm den Zugriff auf das lokale Netzwerk erlauben. Öffne Systemeinstellungen → Datenschutz & Sicherheit → Lokales Netzwerk und schalte WetterCube Control (oder Terminal, wenn du es von dort startest) ein.")
        if sys.platform.startswith("win"):
            tipps.insert(0, "Windows: Fragt die Firewall beim ersten Start, ob Control Verbindungen annehmen darf, erlaube es für „Private Netzwerke“. Das Netzwerk muss als „Privat“ eingestuft sein.")
        s.append({"titel": "Das kann helfen", "stufe": "info", "text": "\n".join(tipps)})
    return s


def adresse(adr):
    """Eine Adresse von Hand pruefen: {"ok", "text", "name"}."""
    adr = (adr or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,80}(:\d{1,5})?", adr):
        return {"ok": False, "text": "Bitte eine IP-Adresse oder einen Namen eingeben, zum Beispiel 192.168.1.52.", "name": ""}
    host = adr.split(":")[0]
    if not host.replace(".", "").isdigit() and not _aufloesen(host):
        return {"ok": False, "text": f"Der Name „{host}“ lässt sich nicht auflösen. Probiere die IP-Adresse des Geräts (steht in deinem Router unter „Heimnetz“).", "name": ""}
    port = int(adr.split(":")[1]) if ":" in adr else 80
    try:
        socket.create_connection((host, port), 1.5).close()
        offen = True
    except OSError:
        offen = False
    if not offen:
        return {"ok": False, "text": "Unter dieser Adresse antwortet nichts. Gerät aus, anderes Netz, falsche Adresse oder Firewall.", "name": ""}
    d = c.pruefen(adr)
    if not d:
        return {"ok": False, "text": "Unter dieser Adresse antwortet ein Gerät, aber kein WetterCube.", "name": ""}
    return {"ok": True, "text": "Das ist ein WetterCube.", "name": c.name_von(adr) or adr}
