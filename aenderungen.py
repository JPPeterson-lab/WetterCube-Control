# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Aenderungsliste ("Was ist neu?") vor einem Update.

Die Liste kommt aus der CHANGELOG.md des oeffentlichen Repos des Geraetetyps (GitHub, raw.githubusercontent.com). Der Abruf geschieht nur,
wenn jemand im Dialog vor dem Update darauf wartet, nie im Hintergrund. Geraete ohne oeffentliches Repo (Apex u. a.) haben keine Liste.
"""
import re, time

KONTO = "JPPeterson-lab"
REPOS = {"fusion-s3": "WetterCube-Fusion", "plus": "WetterCubePlus", "europe": "WetterCubePlus-Europe", "next": "WetterCube-Next"}
_cache = {}


def abschnitt(markdown, version):
    """Die Zeilen unter der Ueberschrift '## v<version> (...)'. None, wenn es keinen solchen Abschnitt gibt."""
    ziel = str(version).strip().lstrip("vV")
    zeilen = markdown.splitlines()
    start = None
    for i, z in enumerate(zeilen):
        if z.startswith("## "):
            kopf = z[3:].strip().split()
            if start is not None:
                return _bereinigen(zeilen[start:i])
            if kopf and kopf[0].lstrip("vV") == ziel:
                start = i + 1
    return _bereinigen(zeilen[start:]) if start is not None else None


def _bereinigen(zeilen):
    """Markdown in einfache Zeilen {typ: ueberschrift|punkt|text, text} umwandeln (kein HTML, die Seite setzt den Text sicher ein)."""
    aus, laenge = [], 0
    for z in zeilen:
        t = z.strip()
        if not t:
            continue
        typ = "text"
        if t.startswith("### "):
            typ, t = "ueberschrift", t[4:]
        elif t[:2] in ("- ", "* "):
            typ, t = "punkt", t[2:]
        t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)       # Links: nur der Text
        t = re.sub(r"[*_`]+", "", t).strip()
        if not t:
            continue
        laenge += len(t)
        if laenge > 5000 or len(aus) >= 60:
            aus.append({"typ": "text", "text": "… (gekürzt, den Rest findest du im Changelog des Projekts)"})
            break
        aus.append({"typ": typ, "text": t})
    return aus


def holen_text(repo):
    """CHANGELOG.md des Repos (10 Minuten zwischengespeichert)."""
    alt = _cache.get(repo)
    if alt and time.time() - alt[0] < 600:
        return alt[1]
    import installer
    text = installer._holen(f"https://raw.githubusercontent.com/{KONTO}/{repo}/main/CHANGELOG.md", 400_000).decode("utf-8", "replace")
    _cache[repo] = (time.time(), text)
    return text


def fuer_web(ordner, version):
    """Aenderungsliste von unserem Webspace (eine Datei je Version, vom Hochladeskript aus dem Changelog erzeugt)."""
    import installer
    try:
        text = installer._holen(f"{installer.WEBSPACE}{ordner}/{version.lstrip('vV')}/aenderungen.md", 100_000).decode("utf-8", "replace")
    except Exception:
        return None
    z = _bereinigen(text.splitlines())
    return z or None


def fuer(produkt, version):
    """Antwort fuer die Oberflaeche: {"version", "zeilen", "hinweis"}; zeilen leer + hinweis, wenn es nichts gibt."""
    if not re.fullmatch(r"[0-9A-Za-z.\-]{1,30}", str(version or "")):
        return {"version": "", "zeilen": [], "hinweis": "Die neue Version ist unbekannt."}
    import installer
    if produkt in installer.INTERN:
        return {"version": version, "zeilen": [], "hinweis": "Für dieses Gerät gibt es keine öffentliche Änderungsliste."}
    if produkt in installer.WEB:      # Fusion und Next: vom eigenen Webspace
        z = fuer_web(installer.WEB[produkt][0], version)
        if z:
            return {"version": version, "zeilen": z, "hinweis": ""}
        return {"version": version, "zeilen": [], "hinweis": "Zu dieser Version liegt keine Änderungsliste vor. Das Update geht trotzdem."}
    repo = REPOS.get(produkt)
    if not repo:
        return {"version": version, "zeilen": [], "hinweis": "Für dieses Gerät gibt es keine öffentliche Änderungsliste."}
    try:
        text = holen_text(repo)
    except Exception:
        return {"version": version, "zeilen": [], "hinweis": "Die Änderungsliste konnte nicht von GitHub geladen werden (kein Internet?). Das Update geht trotzdem."}
    z = abschnitt(text, version)
    if not z:
        return {"version": version, "zeilen": [], "hinweis": "Zu dieser Version steht noch keine Änderungsliste im Changelog."}
    return {"version": version, "zeilen": z, "hinweis": ""}
