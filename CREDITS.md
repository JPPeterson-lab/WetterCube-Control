# Credits und Lizenzen der Bausteine

WetterCube Control steht unter der **AGPL-3.0-only** (siehe `LICENSE`, `NOTICE`). Die gebauten Programme (`.app`, `.exe`) enthalten
folgende Bausteine mit eigenen Lizenzen:

| Baustein | Lizenz | Wofür |
|---|---|---|
| [esptool](https://github.com/espressif/esptool) 4.13 | GPL-2.0-or-later (hier unter GPL-3.0 genutzt, kompatibel mit AGPL-3.0) | Firmware per USB aufspielen (Installer) |
| [pyserial](https://github.com/pyserial/pyserial) | BSD-3-Clause | USB-Anschlüsse finden |
| [certifi](https://github.com/certifi/python-certifi) | MPL-2.0 (unverändert) | Zertifikate für den Download von GitHub |
| [rumps](https://github.com/jaredks/rumps) | BSD-3-Clause | Symbol in der Mac-Menüleiste |
| [pystray](https://github.com/moses-palmer/pystray) | LGPL-3.0 (als austauschbare Bibliothek im Programmordner) | Symbol in der Windows-Taskleiste |
| [keyring](https://github.com/jaraco/keyring) | MIT | Web-Passwörter der Geräte im Schlüsselbund des Systems |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU | Bilder für das Taskleisten-Symbol |
| [PyInstaller](https://pyinstaller.org) | GPL-2.0-or-later mit Ausnahme für den Bootloader | Bau der Programme (nicht im Quellcode) |
| Python | PSF-2.0 | Laufzeit |
| [Montserrat](https://github.com/JulietaUla/Montserrat) | OFL-1.1 | Wortmarke (Umrisse im Logo) |

**Warum AGPL:** Esptool ist GPL-lizenziert und steckt im selben Programm; das Ganze muss daher GPL-kompatibel verteilt werden. Die AGPL-3.0 ist
mit der GPL-3.0 ausdrücklich kombinierbar (Abschnitt 13) und passt zu Apex, Biker und Green. Die Netzwerkklausel ist hier sinnvoll,
weil Control eine Weboberfläche bereitstellt. Zu den gebauten Programmen gehört das Angebot des vollständigen Quellcodes (dieses Repository).

Wetterdaten stammen nicht von Control selbst: Control liest nur die Geräte im eigenen Netz.
