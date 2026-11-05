#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Erzeugt das Logo-Set von WetterCube Control im Markenstil: Wortmarke aus Montserrat Regular ("WetterCube" dunkel #111111 bzw. hell #f2f2f2,
das zweite Wort in Himmelblau #87CEEB), das Markensymbol (Navy-Quadrat mit hellblauem W) und daraus die App-Symbole.

Aufruf:  .venv/bin/python tools/logo_erzeugen.py <Montserrat-VariableFont_wght.ttf> <Website-Ordner>
  <Website-Ordner> = Repo "WetterCube Website" (liefert das Symbol wiki/wettercube-icon.svg und den Renderer tools/logos_erzeugen.py)
Braucht fonttools und Pillow. Schreibt nach assets/logo/ und assets/icons/ (SVG, PNG, .icns nur auf dem Mac, .ico).
"""
import importlib.util, os, re, subprocess, sys
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image

if len(sys.argv) != 3:
    sys.exit(__doc__)
schrift, website = sys.argv[1:3]
HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
LOGO, ICONS = os.path.join(WURZEL, "assets", "logo"), os.path.join(WURZEL, "assets", "icons")
os.makedirs(LOGO, exist_ok=True); os.makedirs(ICONS, exist_ok=True)

spec = importlib.util.spec_from_file_location("logos_erzeugen", os.path.join(website, "tools", "logos_erzeugen.py"))
renderer = importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)   # zeichne(svg_text, breite) -> PIL-Bild

f = TTFont(schrift)
if "fvar" in f:
    f = instancer.instantiateVariableFont(f, {"wght": 400})
gs, cmap, hm = f.getGlyphSet(), f.getBestCmap(), f["hmtx"]


def zahl(m):
    v = round(float(m.group(0)) * 2) / 2
    return ("%d" % v) if v == int(v) else ("%.1f" % v)


def pfad(ch):
    p = SVGPathPen(gs); gs[cmap[ord(ch)]].draw(p)
    return re.sub(r"-?\d+\.\d+|-?\d+", zahl, p.getCommands())


def logo(dunkel, wort2="Control"):
    x, t1, t2 = 0, [], []
    for ch in "WetterCube":
        t1.append('<path transform="translate(%d 0)" d="%s"/>' % (round(x), pfad(ch))); x += hm[cmap[ord(ch)]][0]
    x += hm[cmap[ord(" ")]][0]
    for ch in wort2:
        t2.append('<path transform="translate(%d 0)" d="%s"/>' % (round(x), pfad(ch))); x += hm[cmap[ord(ch)]][0]
    b = round(x) + 360
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d 1360" width="%d" height="680"><g transform="translate(180 900) scale(1 -1)">'
            '<g fill="%s">%s</g><g fill="#87CEEB">%s</g></g></svg>') % (b, b // 2, dunkel, "".join(t1), "".join(t2))


for suffix, farbe in (("", "#111111"), ("-hell", "#f2f2f2")):
    svg = logo(farbe)
    open(os.path.join(LOGO, "wettercube-control-logo%s.svg" % suffix), "w").write(svg)
    renderer.zeichne(svg, 2400).save(os.path.join(LOGO, "wettercube-control-logo%s.png" % suffix), optimize=True)

# Symbol der Marke (Navy-Quadrat, hellblaues W)
symbol = open(os.path.join(website, "wiki", "wettercube-icon.svg"), encoding="utf-8").read()
open(os.path.join(LOGO, "wettercube-symbol.svg"), "w", encoding="utf-8").write(symbol)
gross = renderer.zeichne(symbol, 1024)
gross.save(os.path.join(LOGO, "wettercube-symbol.png"), optimize=True)
for n in (192, 512):
    gross.resize((n, n), Image.LANCZOS).save(os.path.join(ICONS, "symbol-%d.png" % n), optimize=True)

# Windows-Symbol
gross.save(os.path.join(ICONS, "WetterCube Control.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

# Mac-Symbol (.icns ueber iconutil, nur auf dem Mac)
if sys.platform == "darwin":
    iconset = os.path.join(ICONS, "WetterCube Control.iconset"); os.makedirs(iconset, exist_ok=True)
    for s in (16, 32, 128, 256, 512):
        gross.resize((s, s), Image.LANCZOS).save(os.path.join(iconset, "icon_%dx%d.png" % (s, s)))
        gross.resize((s * 2, s * 2), Image.LANCZOS).save(os.path.join(iconset, "icon_%dx%d@2x.png" % (s, s)))
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(ICONS, "WetterCube Control.icns")], check=True)
    import shutil; shutil.rmtree(iconset)

# Menueleisten-Symbol (einfarbig schwarz, Alpha = Form des W; macOS faerbt es je nach Hell/Dunkel)
w = re.search(r'<path[^>]* d="([^"]+)"', symbol).group(1)
# nur das W, einfarbig, etwas groesser eingepasst (Menueleiste ist klein)
mono = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><g transform="translate(8 160) scale(0.17 -0.17)" fill="#000000">'
        '<path d="%s"/></g></svg>') % w
m = renderer.zeichne(mono, 144)
m.save(os.path.join(ICONS, "menueleiste.png"), optimize=True)
m.resize((72, 72), Image.LANCZOS).save(os.path.join(ICONS, "menueleiste-klein.png"), optimize=True)
for ordner in (LOGO, ICONS):
    for n in sorted(os.listdir(ordner)):
        print("%-34s %8d Bytes" % (n, os.path.getsize(os.path.join(ordner, n))))
