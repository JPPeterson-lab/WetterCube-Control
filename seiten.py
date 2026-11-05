# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Jan Althaus (JPPeterson-lab)
"""Die Seiten von WetterCube Control (reines HTML/JavaScript ohne fremde Bibliotheken, laeuft ohne Internet)."""

CSS = r"""
:root{--bg:#f5fbfe;--card:#e0f7ff;--tx:#111827;--mut:#4b5563;--ac:#2b7fa3;--acbg:#2b7fa3;--actx:#fff;--warn:#ce4b11;--ok:#0fa64a;--gelb:#b45309;--rand:#b9dcea;--feld:#fff}
@media(prefers-color-scheme:dark){:root:not([data-farbe=hell]){--bg:#06203b;--card:#184a7e;--tx:#fff;--mut:#bcd3e6;--ac:#87ceeb;--acbg:#87ceeb;--actx:#06203b;--warn:#ff8a50;--ok:#4ade80;--gelb:#ffd166;--rand:#2f6aa3;--feld:#0e3358}}
:root[data-farbe=dunkel]{--bg:#06203b;--card:#184a7e;--tx:#fff;--mut:#bcd3e6;--ac:#87ceeb;--acbg:#87ceeb;--actx:#06203b;--warn:#ff8a50;--ok:#4ade80;--gelb:#ffd166;--rand:#2f6aa3;--feld:#0e3358}
*{box-sizing:border-box}body{margin:0;font:16px system-ui,sans-serif;background:var(--bg);color:var(--tx)}
a{color:var(--ac);text-decoration:none}h1{font-size:20px;margin:0}h2{font-size:17px;margin:0 0 4px}.mut{color:var(--mut);font-size:13px}
nav{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline;padding:14px 16px 6px}nav .farbe{margin-left:auto;font-size:13px;color:var(--mut);cursor:pointer;background:none;border:0;padding:3px 6px}nav .logo{margin-right:12px;display:flex;align-items:center}nav .logo img{height:24px;width:auto;display:block}
.l-hell{display:none!important}
@media(prefers-color-scheme:dark){:root:not([data-farbe=hell]) .l-hell{display:block!important}:root:not([data-farbe=hell]) .l-dunkel{display:none!important}}
:root[data-farbe=dunkel] .l-hell{display:block!important}:root[data-farbe=dunkel] .l-dunkel{display:none!important}
nav a{font-size:14px;padding:3px 0;border-bottom:2px solid transparent}nav a.on{border-color:var(--ac);color:var(--tx);font-weight:600}
main{padding:8px 16px 28px;max-width:1200px;margin:0 auto}
.k{background:var(--card);border-radius:12px;padding:14px;margin-bottom:12px}
.raster{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}.raster .k{margin:0}
button,select,input[type=text]{font:inherit;font-size:14px;padding:6px 10px;border-radius:8px;border:1px solid var(--ac);background:transparent;color:var(--ac)}
button{cursor:pointer}button.v{background:var(--acbg);color:var(--actx);border-color:var(--acbg)}button:disabled{opacity:.5;cursor:default}
select,input[type=text]{color:var(--tx);border-color:var(--rand);background:var(--feld)}
.b{display:inline-block;border-radius:8px;padding:3px 9px;font-size:13px;margin:6px 6px 0 0;color:#fff;background:#cc0000}
.b.ok{background:#0fa64a}.b.off{background:#64748b}.b.neu{background:var(--acbg);color:var(--actx)}.b.gelb{background:var(--gelb)}
.t{font-size:38px;font-weight:600;margin:6px 0}.z{display:flex;gap:14px;flex-wrap:wrap;color:var(--mut);font-size:14px}
.punkt{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:var(--ok)}.punkt.warn{background:var(--gelb)}.punkt.problem{background:var(--warn)}
pre{background:#041525;color:#d7e3ee;border-radius:8px;padding:10px;font-size:12px;max-height:340px;overflow:auto;white-space:pre-wrap;margin:8px 0 0}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:5px 8px;border-bottom:1px solid var(--rand);text-align:left;vertical-align:top}
.zeile{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}.meld{font-size:14px;padding:4px 0;border-bottom:1px solid var(--rand)}
.meld .w{color:var(--warn)}.meld .p{color:var(--gelb)}label.c{display:flex;gap:8px;align-items:flex-start;margin:6px 0;font-size:14px}
"""

SEITEN = [("/", "Übersicht"), ("/verlauf", "Verlauf"), ("/wand", "Wetterwand"), ("/alle", "Alle Geräte"), ("/assistent", "Neues Gerät"), ("/kopieren", "Einstellungen kopieren"), ("/installer", "Installer"), ("/einstellungen", "Einstellungen"), ("/hilfe", "Hilfe")]

JS_GEMEINSAM = r"""
const $=id=>document.getElementById(id);
function farbeWechseln(){const h=document.documentElement;const dunkel=h.getAttribute('data-farbe')==='dunkel'||(!h.getAttribute('data-farbe')&&matchMedia('(prefers-color-scheme: dark)').matches);const n=dunkel?'hell':'dunkel';h.setAttribute('data-farbe',n);try{localStorage.setItem('farbe',n)}catch(x){}}
const e=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const q=new URLSearchParams(location.search);
async function api(pfad,daten){const r=await fetch(pfad,daten===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(daten)});
 const t=await r.text();let j=null;try{j=JSON.parse(t)}catch(x){}if(!r.ok)throw new Error(j&&j.fehler?j.fehler:(t||('Fehler '+r.status)));return j}
function zeit(ts){return new Date(ts*1000).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}
function datum(ts){return new Date(ts*1000).toLocaleString('de-DE',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}
function dialogBestaetigen(titel,html,ja,nein){return new Promise(res=>{const d=document.createElement('dialog');d.style.cssText='max-width:580px;width:92%;border:1px solid var(--rand);border-radius:12px;background:var(--bg);color:var(--tx);padding:16px';
 d.innerHTML='<h2>'+e(titel)+'</h2><div class="dlgk" style="max-height:52vh;overflow:auto;margin:8px 0">'+html+'</div><div class="zeile" style="justify-content:flex-end"><button class="dn">'+e(nein||'Abbrechen')+'</button><button class="v dj">'+e(ja)+'</button></div>';
 document.body.appendChild(d);const fertig=w=>{d.close();d.remove();res(w)};d.querySelector('.dj').onclick=()=>fertig(true);d.querySelector('.dn').onclick=()=>fertig(false);d.addEventListener('cancel',()=>fertig(false));
 window.dlgInhalt=h=>{const k=d.querySelector('.dlgk');if(k)k.innerHTML=h};d.showModal()})}
function neuesHtml(j){if(j&&j.zeilen&&j.zeilen.length)return '<div class="mut">Neu in Version '+e(j.version)+':</div>'+j.zeilen.map(z=>z.typ==='ueberschrift'?'<div style="font-weight:600;margin-top:8px">'+e(z.text)+'</div>':(z.typ==='punkt'?'<div style="padding:2px 0 2px 14px;text-indent:-14px">• '+e(z.text)+'</div>':'<div class="mut">'+e(z.text)+'</div>')).join('');
 return '<div class="mut">'+e(j&&j.hinweis?j.hinweis:'Keine Änderungsliste verfügbar.')+'</div>'}
async function neuesAnzeigen(ip,version,titel,ja,vorspann){const p=dialogBestaetigen(titel,(vorspann?'<div style="margin-bottom:8px">'+e(vorspann)+'</div>':'')+'<div id="dlgn" class="mut">Lade die Änderungsliste von GitHub (nur weil du auf das Update wartest) ...</div>',ja);
 api('/api/update/aenderungen?ip='+encodeURIComponent(ip)+'&version='+encodeURIComponent(version)).then(j=>window.dlgInhalt((vorspann?'<div style="margin-bottom:8px">'+e(vorspann)+'</div>':'')+neuesHtml(j))).catch(()=>window.dlgInhalt((vorspann?'<div style="margin-bottom:8px">'+e(vorspann)+'</div>':'')+'<div class="mut">Die Änderungsliste ist nicht verfügbar. Das Update geht trotzdem.</div>'));return p}
async function entfernen(ip,name){if(!confirm('„'+name+'“ aus WetterCube Control entfernen?\n\nWenn das Gerät später wieder im Netz auftaucht, erscheint es von selbst erneut.'))return;
 const v=confirm('Auch den gespeicherten Verlauf dieses Geräts löschen?\n\nOK = Verlauf löschen, Abbrechen = Verlauf behalten.');
 try{await api('/api/geraete/aendern',{ip:ip,entfernen:true,verlauf_loeschen:v});if(location.pathname==='/geraet')location.href='/';else if(typeof lade==='function')lade();else if(typeof laden==='function')laden()}catch(x){alert(x.message)}}
"""


# Hell/Dunkel: ?farbe=hell|dunkel waehlt, der Browser merkt es sich; ohne Wahl gilt die Einstellung des Systems
KOPF_SKRIPT = "<script>(function(){try{var q=new URLSearchParams(location.search).get('farbe');if(q==='hell'||q==='dunkel')localStorage.setItem('farbe',q);var f=localStorage.getItem('farbe');if(f)document.documentElement.setAttribute('data-farbe',f)}catch(x){}})()</script>"


def seite(titel, aktiv, body, script="", extra_css=""):
    nav = "".join(f'<a href="{p}"{" class=on" if p == aktiv else ""}>{t}</a>' for p, t in SEITEN)
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{titel} – WetterCube Control</title><link rel="manifest" href="/manifest.json"><link rel="icon" href="/icon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="any"><meta name="theme-color" content="#0b2545">'
            f'<style>{CSS}{extra_css}</style>{KOPF_SKRIPT}</head><body><nav><a class="logo" href="/"><img class="l-dunkel" src="/logo.svg" alt="WetterCube Control"><img class="l-hell" src="/logo-hell.svg" alt=""></a>{nav}<button class="farbe" onclick="farbeWechseln()" title="Hell oder dunkel">◐ hell/dunkel</button></nav><main>{body}</main>'
            f'<script>{JS_GEMEINSAM}{script}\nif("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js");</script></body></html>')


# ── Uebersicht ───────────────────────────────────────────────────────────────
UEBERSICHT = seite("Übersicht", "/", r"""
<div class="zeile"><span class="mut" id="s">suche Geräte ...</span><button id="sb" onclick="alleSichern()">Alle Geräte sichern</button><button onclick="updatesPruefen()">Auf Updates prüfen</button><span class="mut" id="v"></span></div>
<div id="sm" class="mut"></div>
<div class="k" id="mk" style="display:none"><h2>Meldungen</h2><div id="mel"></div></div>
<div class="raster" id="m"></div>
""", r"""
function karte(d){const s=d.status||{};const on=d.online!==false;const g=d.gesundheit||{stufe:'ok',gruende:[]};const u=d.update;
 let h='<div class="k"><h2><span class="punkt '+(g.stufe==='ok'?'':g.stufe)+'" title="'+e(g.gruende.join(', ')||'alles in Ordnung')+'"></span>'+e(d.name)+'</h2><div class="mut">'+e(d.ip)+(s.version?' · v'+e(s.version):'')+'</div>';
 if(u&&u.neuer)h+='<span class="b neu" title="Installiert: '+e(u.aktuell)+'">Neu: '+e(u.neueste)+'</span>';
 if(d.art==='status'&&on){const t=(k,f)=>s[k]!=null?'<span>'+f(s[k])+'</span>':'';
  h+=s.temp!=null?'<div class="t">'+e(s.temp)+' °C</div><div class="z">'+t('wetter',e)+t('gefuehlt',v=>'gefühlt '+e(v)+' °')+t('feuchte',v=>e(v)+' % Feuchte')+t('druck',v=>e(v)+' hPa')+t('wind',v=>'Wind '+e(v)+' km/h')+(s.geraet==='node'?t('rssi',v=>'Signal '+e(v)+' dBm'):'')+'</div>':'<div class="mut" style="margin:10px 0">'+(s.fehler>0?'Noch keine Daten von der Fusion (sie ist nicht erreichbar).':'Noch keine Daten, der erste Abruf läuft ...')+'</div>';
  if(s.dwd!=null)h+=s.dwd>0?'<span class="b">⚠ '+s.dwd+' DWD-Warnung'+(s.dwd>1?'en':'')+'</span>':'<span class="b ok">keine Warnung</span>';
  if(s.daten_alter_s>0)h+='<div class="mut" style="margin-top:6px">Daten von der Fusion, vor '+Math.round(s.daten_alter_s/60)+' Min. geholt</div>';
  if(s.lueften)h+=' <span class="mut">'+e(s.lueften)+'</span>';}
 else if(on){h+='<div class="mut" style="margin:10px 0">Dieses Gerät meldet seine Werte noch nicht an WetterCube Control (nur Link). Ab der nächsten Firmware geht es.</div>';}
 else h+='<span class="b off">nicht erreichbar</span>'+(d.zuletzt?'<div class="mut" style="margin-top:6px">zuletzt erreichbar: '+datum(d.zuletzt)+'</div>':'');
 if(g.stufe==='warn')h+='<div class="mut" style="margin-top:6px;color:var(--gelb)">'+g.gruende.map(e).join('<br>')+'</div>';
 return h+'<div class="zeile" style="margin-bottom:0"><a href="/geraet?ip='+encodeURIComponent(d.ip)+'">Details</a>'+(s.geraet==='node'?'<a href="/kalibrierung?ip='+encodeURIComponent(d.ip)+'">Kalibrierung</a>':'')+'<a href="http://'+e(d.ip)+'/" target="_blank" rel="noopener">Weboberfläche</a>'+(!on?'<button data-ip="'+e(d.ip)+'" data-name="'+e(d.name)+'" onclick="entfernen(this.dataset.ip,this.dataset.name)">Entfernen</button>':'')+'</div></div>'}
async function lade(){try{const l=await api('/api/geraete');
 $('s').textContent=l.length?l.length+' Gerät(e), aktualisiert '+new Date().toLocaleTimeString('de-DE'):'noch keine Geräte gefunden, Suche läuft ...';
 l.sort((a,b)=>(a.online===false)-(b.online===false));$('m').innerHTML=l.map(karte).join('');const m=await api('/api/ereignisse?seit=0');
 $('mk').style.display=m.length?'block':'none';m.sort((a,b)=>b.ts-a.ts);$('mel').innerHTML=m.slice(0,8).map(x=>'<div class="meld"><span class="mut">'+zeit(x.ts)+'</span> <span class="'+(x.art==='warnung'?'w':(x.art==='problem'?'p':''))+'">'+e(x.text)+'</span></div>').join('');
 const i=await api('/api/info');$('v').textContent='Version '+i.version;
 }catch(x){$('s').textContent='Control nicht erreichbar'}}
async function alleSichern(){const m=$('sm');m.textContent='sichere ...';
 try{const j=await api('/api/alle-sichern',{});m.innerHTML='Gespeichert in <b>'+e(j.ordner)+'</b>: '+j.ergebnis.map(x=>e(x.name)+(x.ok?' ✓':' ✗ ('+e(x.text)+')')).join(', ')}catch(x){m.textContent='Sichern fehlgeschlagen: '+x.message}}
async function updatesPruefen(){const m=$('sm');m.textContent='frage die Geräte (das kann einige Sekunden dauern) ...';const l=await api('/api/geraete');let z=[];
 for(const d of l){if(d.online===false)continue;try{const u=await api('/api/update/pruefen?ip='+encodeURIComponent(d.ip));z.push('<a href="/geraet?ip='+encodeURIComponent(d.ip)+'">'+e(d.name)+'</a>: '+(u.aus?'Updates am Gerät aus':(u.verfuegbar?'<b>Update '+e(u.neueste)+' verfügbar</b> (installiert '+e(u.aktuell)+')':'aktuell ('+e(u.aktuell)+')')))}catch(x){z.push(e(d.name)+': '+e(x.message&&x.message.length<80?x.message:'keine Antwort'))}}
 m.innerHTML=z.join(' · ')}
lade();setInterval(lade,10000);
""")


# ── Geraetedetail ────────────────────────────────────────────────────────────
GERAET = seite("Gerät", "/", r"""
<p class="mut"><a href="/">← Übersicht</a></p>
<div class="k"><h2 id="n">…</h2><div class="mut" id="sub"></div><div id="ges" style="margin-top:8px"></div></div>
<div class="k"><h2>Bildschirm</h2>
 <div class="zeile"><select id="scr" onchange="bild()"><option value="">Hauptseite</option><option value="warnliste">Warnliste</option><option value="radar">Regenradar (Apex)</option><option value="historie">Verlauf (Apex)</option><option value="nachtuhr">Nachtuhr (Apex)</option></select>
 <label class="c" style="margin:0"><input type="checkbox" id="auto" onchange="autoBild()"> jede Minute aktualisieren</label><button onclick="bild()">Jetzt</button><a id="dl" class="mut" download>Bild speichern</a></div>
 <img id="b" alt="Bildschirm" style="max-width:100%;border-radius:8px;border:1px solid var(--rand);margin-top:6px;display:none"><div id="bf" class="mut"></div></div>
<div class="k"><h2>Zustand</h2><table id="zu"></table></div>
<div class="k"><h2>Firmware</h2><div class="mut" id="fw">…</div>
 <div class="zeile"><button onclick="fwPruefen()">Nach Update suchen</button><button class="v" id="fwgo" onclick="fwStarten()" style="display:none">Update installieren</button></div>
 <div class="mut">Das Gerät schaut bei seiner eigenen Update-Quelle nach und installiert selbst; danach startet es neu. Einstellungen bleiben erhalten.</div><div id="fwm" class="mut" style="margin-top:6px"></div></div>
<div class="k"><h2>Einstellungen</h2>
 <div class="zeile"><a id="sl" class="mut" download>Jetzt sichern (Download)</a></div>
 <div class="zeile"><select id="sicherungen"></select><button onclick="ausListe()">Diese Sicherung einspielen</button></div>
 <div class="zeile"><input type="file" id="datei" accept=".json,application/json"><button onclick="ausDatei()">Aus Datei einspielen</button></div>
 <div class="mut">Vor jedem Einspielen legt Control eine Sicherheitskopie des Geräts an. Das Gerät startet danach neu. Gerätetyp und Datei müssen zusammenpassen.</div><div id="wm" class="mut" style="margin-top:6px"></div></div>
<div class="k"><h2>Diagnose-Log</h2><div class="zeile"><button onclick="logLaden()">Log laden</button><input type="text" id="filter" placeholder="Filter (z. B. WLAN, Fehler)" oninput="logZeigen()"></div><pre id="log" style="display:none"></pre></div>
<div class="k"><h2>Gesammelte Protokolle</h2><div class="mut" id="prt">…</div><table id="prl"></table></div>
<div class="k"><h2>Passwort des Geräts</h2><div class="mut" id="pwt">…</div>
 <div class="zeile"><input type="password" id="pw" placeholder="Web-Passwort des Geräts" autocomplete="off" style="font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--rand);background:var(--feld);color:var(--tx)"><button onclick="pwSpeichern()">Prüfen und speichern</button><button onclick="pwWeg()" id="pwweg" style="display:none">Entfernen</button></div><div id="pwm" class="mut"></div></div>
<div class="k" id="entf" style="display:none"><h2>Gerät nicht mehr in Gebrauch?</h2><div class="mut" id="entft"></div><div class="zeile"><button id="entfb">Aus WetterCube Control entfernen</button></div></div>
<div class="k"><h2>Diagnose-Paket</h2><div class="mut">Sammelt Status und Log dieses Geräts in eine ZIP-Datei für die Fehlersuche. Das Log kann den WLAN-Namen und Adressen enthalten: vor dem Weitergeben ansehen.</div>
 <label class="c"><input type="checkbox" id="mitE"> Einstellungen mit aufnehmen (enthalten den Ort, keine Passwörter)</label><div class="zeile"><button onclick="diag()">Paket erstellen</button><span id="dm" class="mut"></span></div></div>
""", r"""
const ip=q.get('ip')||'';let timer=null,logtext='';
// Ein Bildschirmfoto belastet Fusion und Apex stark (ganzes Bild neu zeichnen, PNG, mehrere MB durchs WLAN; das Display kann dabei kurz
// aufblitzen, andere Anfragen warten): nie zwei gleichzeitig, nicht waehrend eines Updates, automatisch hoechstens jede Minute und nur auf Wunsch.
let bildLaeuft=false,updLaeuft=false;
function bild(){if(bildLaeuft||updLaeuft)return;const s=$('scr').value;const u='/api/bild?ip='+encodeURIComponent(ip)+(s?'&s='+s:'');const img=$('b');$('bf').textContent='';bildLaeuft=true;
 img.onload=()=>{bildLaeuft=false;img.style.display='block'};img.onerror=()=>{bildLaeuft=false;img.style.display='none';$('bf').textContent='Dieses Gerät liefert gerade kein Bildschirmfoto (beschäftigt oder nicht erreichbar).'};
 img.src=u+'&t='+Date.now();$('dl').href=u+'&dl=1'}
function autoBild(){if(timer){clearInterval(timer);timer=null}if($('auto').checked)timer=setInterval(bild,60000)}
async function zustand(){try{const l=await api('/api/geraete');const d=l.find(x=>x.ip===ip);if(!d){$('n').textContent='Unbekanntes Gerät';return}
 const s=d.status||{};const g=d.gesundheit||{stufe:'ok',gruende:[]};$('n').textContent=d.name;$('entf').style.display=d.online===false?'block':'none';if(d.online===false){$('entft').textContent='Dieses Gerät ist nicht erreichbar'+(d.zuletzt?' (zuletzt am '+datum(d.zuletzt)+')':'')+'. Wenn du es nicht mehr benutzt, kannst du es aus der Liste entfernen.';$('entfb').onclick=()=>entfernen(d.ip,d.name)}$('sub').innerHTML=e(d.ip)+(s.version?' · Version '+e(s.version):'')+' · <a href="http://'+e(d.ip)+'/" target="_blank" rel="noopener">Weboberfläche</a>';
 $('ges').innerHTML='<span class="punkt '+(g.stufe==='ok'?'':g.stufe)+'"></span>'+(g.stufe==='ok'?'alles in Ordnung':e(g.gruende.join(' · ')))+(d.update&&d.update.neuer?' <span class="b neu">Neu: '+e(d.update.neueste)+'</span>':'');
 const li=d.log_info||{};const ab=li.abruf||{};let z='';
 const zl=(a,b)=>{if(b!==undefined&&b!==null&&b!=='')z+='<tr><td>'+a+'</td><td>'+e(b)+'</td></tr>'};
 const kb=v=>v!=null?Math.round(v/1024).toLocaleString('de-DE')+' KB':null;const lauf=m=>m==null?null:(m<120?m+' Min.':m<2880?Math.round(m/60)+' Std.':Math.round(m/1440)+' Tage');
 zl('Erreichbar',d.online===false?'nein':'ja');zl('WLAN',li.ssid);zl('Signal',li.wlan_dbm!=null?li.wlan_dbm+' dBm':null);zl('Freier Speicher (intern)',kb(li.heap));
 zl('Tiefster Stand seit dem Start',li.heap_min!=null?kb(li.heap_min)+' (größter freier Block '+kb(li.heap_block)+')':null);zl('PSRAM frei',kb(li.psram_frei));zl('Läuft seit',lauf(li.uptime_min));zl('Letzter Neustart',li.neustart);zl('Zuletzt aktiv vor dem Neustart',li.zuletzt_aktiv);
 Object.keys(ab).forEach(k=>zl('Letzter Abruf: '+e(k),ab[k]==null?'noch nie':'vor '+ab[k]+' Min.'));$('zu').innerHTML=z||'<tr><td class="mut">Keine Zustandsdaten (Gerät mit Passwort oder ohne Diagnose-Log).</td></tr>';
 }catch(x){}}
async function pwStatus(){try{const j=await api('/api/passwort/status?ip='+encodeURIComponent(ip));$('pwt').textContent=j.falsch?'Das gespeicherte Passwort wurde vom Gerät abgelehnt. Bitte neu eintragen.':(j.gesetzt?'Ein Passwort ist gespeichert (im Schlüsselbund dieses Rechners). Control nutzt es für Sicherungen, Wiederherstellen, Log und Updates.':'Hat das Gerät ein Web-Passwort, trage es hier ein, damit Sicherungen, Wiederherstellen, Log und Updates gehen. Es wird im Schlüsselbund dieses Rechners gespeichert und nie ins Netz gesendet außer an das Gerät selbst.');$('pwweg').style.display=j.gesetzt?'inline-block':'none'}catch(x){}}
async function pwSpeichern(){$('pwm').textContent='prüfe ...';try{const j=await api('/api/passwort',{ip:ip,passwort:$('pw').value});$('pw').value='';$('pwm').textContent=j.ort==='schluesselbund'?'Passwort stimmt und ist im Schlüsselbund gespeichert.':'Passwort stimmt, gilt aber nur bis zum Beenden von Control (kein Schlüsselbund gefunden).';pwStatus()}catch(x){$('pwm').textContent=x.message}}
async function pwWeg(){if(!confirm('Das gespeicherte Passwort für dieses Gerät aus dem Schlüsselbund entfernen?'))return;await api('/api/passwort',{ip:ip,loeschen:true});$('pwm').textContent='Entfernt.';pwStatus()}
async function liste(){try{const l=await api('/api/sicherungen?ip='+encodeURIComponent(ip));$('sicherungen').innerHTML=l.length?l.map(x=>'<option value="'+e(x.datei)+'">'+e(x.zeit)+' – '+e(x.datei.split('/').pop())+'</option>').join(''):'<option value="">noch keine Sicherung vorhanden</option>'}catch(x){}}
async function einspielen(daten){if(!confirm('Einstellungen auf das Gerät spielen?\n\nControl legt vorher eine Sicherheitskopie an. Das Gerät startet danach neu.'))return;
 $('wm').textContent='spiele ein ...';try{const j=await api('/api/wiederherstellen',Object.assign({ip:ip},daten));$('wm').innerHTML=e(j.meldung)+'<br>Sicherheitskopie: '+e(j.kopie);setTimeout(liste,1500)}catch(x){$('wm').textContent='Nicht möglich: '+x.message}}
function ausListe(){const d=$('sicherungen').value;if(d)einspielen({datei:d})}
function ausDatei(){const f=$('datei').files[0];if(!f){$('wm').textContent='Bitte zuerst eine Datei wählen.';return}const r=new FileReader();r.onload=()=>einspielen({inhalt:r.result});r.readAsText(f)}
async function logLaden(){try{const r=await fetch('/api/log?ip='+encodeURIComponent(ip));logtext=await r.text();if(!r.ok)logtext='Log nicht lesbar: '+logtext;logZeigen()}catch(x){logtext='Log nicht lesbar.';logZeigen()}}
function logZeigen(){const f=$('filter').value.toLowerCase();const z=logtext.split('\n').filter(l=>!f||l.toLowerCase().includes(f));$('log').style.display='block';$('log').textContent=z.join('\n')||'(nichts gefunden)'}
async function diag(){$('dm').textContent='erstelle ...';try{const j=await api('/api/diagnose',{ips:[ip],einstellungen:$('mitE').checked});
 $('dm').innerHTML='Fertig: <a href="/api/diagnose-datei?name='+encodeURIComponent(j.name)+'" download>'+e(j.name)+'</a> (gespeichert in '+e(j.ordner)+')'+(j.hinweise.length?'<br>'+j.hinweise.map(e).join('<br>'):'')}catch(x){$('dm').textContent='Fehler: '+x.message}}
let neuesteV='';
async function fwPruefen(){$('fwm').textContent='frage das Gerät ...';$('fwgo').style.display='none';try{const u=await api('/api/update/pruefen?ip='+encodeURIComponent(ip));
 if(u.aus){$('fw').textContent='Installiert: '+u.aktuell+'. Updates sind am Gerät ausgeschaltet.'}else{neuesteV=u.neueste||'';$('fw').innerHTML='Installiert: <b>'+e(u.aktuell)+'</b> · Neueste: <b>'+e(u.neueste)+'</b>';$('fwgo').style.display=u.verfuegbar?'inline-block':'none'}
 $('fwm').textContent=u.verfuegbar?'Ein Update ist verfügbar.':(u.aus?'':'Das Gerät ist aktuell.')}catch(x){$('fwm').textContent='Keine Antwort vom Gerät.'}}
async function fwStarten(){if(!await neuesAnzeigen(ip,neuesteV,'Update installieren?','Jetzt installieren','Das Gerät lädt die Firmware, installiert sie und startet neu (etwa 1 bis 2 Minuten). Einstellungen bleiben erhalten. Bitte nicht ausschalten.'))return;
 $('fwgo').disabled=true;updLaeuft=true;if(timer){clearInterval(timer);timer=null}$('fwm').textContent='installiere ... bitte warten und das Gerät nicht ausschalten (kann bei schwachem WLAN einige Minuten dauern)';try{const j=await api('/api/update/starten',{ip:ip});$('fwm').textContent='Fertig, das Gerät startet neu. In einer Minute ist es wieder da.';$('fwgo').style.display='none'}catch(x){$('fwm').textContent='Nicht möglich: '+x.message}$('fwgo').disabled=false;updLaeuft=false;autoBild()}
async function protokolle(){try{const j=await api('/api/protokolle?ip='+encodeURIComponent(ip));
 $('prt').innerHTML=j.an?'Control hängt die neuen Zeilen des Diagnose-Logs alle 5 Minuten an eine Datei je Tag an (30 Tage, nur auf diesem Rechner, Ordner <b>'+e(j.ordner)+'</b>). So bleibt die Vorgeschichte eines Fehlers erhalten, auch wenn das Gerät neu startet.':'Das Sammeln ist ausgeschaltet (Einstellungen).';
 const u=x=>'/api/protokoll?ip='+encodeURIComponent(ip)+'&tag='+x.tag;$('prl').innerHTML=j.tage.length?j.tage.slice(0,14).map(x=>'<tr><td>'+e(x.tag)+'</td><td class="mut">'+Math.max(1,Math.round(x.groesse/1024))+' KB</td><td><a href="'+u(x)+'" target="_blank">Ansehen</a> · <a href="'+u(x)+'&dl=1">Laden</a></td></tr>').join(''):'<tr><td class="mut">Noch nichts gesammelt (Geräte mit Web-Passwort brauchen das Passwort in Control).</td></tr>'}catch(x){}}
protokolle();
$('sl').href='/api/sicherung?ip='+encodeURIComponent(ip);$('bf').textContent='Bildschirmfoto mit „Jetzt“ laden (belastet das Gerät kurz, deshalb nicht automatisch).';autoBild();zustand();setInterval(zustand,10000);liste();fwPruefen();pwStatus();
""")


# ── Verlauf ──────────────────────────────────────────────────────────────────
VERLAUF = seite("Verlauf", "/verlauf", r"""
<div class="k"><div class="zeile"><select id="metrik" onchange="laden()"></select>
<select id="std" onchange="laden()"><option value="6">6 Stunden</option><option value="24" selected>24 Stunden</option><option value="72">3 Tage</option><option value="168">7 Tage</option><option value="720">30 Tage</option><option value="2160">90 Tage</option></select>
<span class="mut" id="info"></span></div>
<canvas id="c" height="360" style="width:100%;height:360px"></canvas><div id="leg" class="zeile"></div><div id="tip" class="mut"></div></div>
<div class="k" id="vgk" style="display:none"><h2>Sensorvergleich</h2><div class="mut">Mittelwert jedes Geräts über die Zeit, in der alle gleichzeitig gemessen haben, und die Abweichung von der Mitte (Median). Aussagekräftig nur, wenn die Sensoren im selben Raum nebeneinander stehen: dann zeigt eine große Abweichung einen falsch kalibrierten oder warm sitzenden Sensor (Gehäusesensoren werden vom Gerät selbst erwärmt).</div><table id="vg"></table></div>
<div class="k"><h2>Tageswerte</h2><div class="zeile"><span class="mut">Niedrigster, höchster und mittlerer Wert je Tag (für die gewählte Messgröße), letzte 14 Tage.</span><a id="csv" download>Alle Werte als CSV laden</a></div><table id="tage"></table></div>
<div class="mut">Die Werte werden alle 5 Minuten lokal auf diesem Rechner gespeichert (90 Tage, nichts wird gesendet). Die Kurve füllt sich, solange Control läuft.</div>
""", r"""
const FARBEN=['#0b6fb3','#e57373','#43a047','#fb8c00','#8e24aa','#00acc1','#6d4c41','#546e7a'];let daten={};
async function start(){const m=await api('/api/verlauf/metriken');$('metrik').innerHTML=Object.keys(m).map(k=>'<option value="'+k+'">'+e(m[k])+'</option>').join('');laden()}
async function laden(){try{const j=await api('/api/verlauf?metrik='+$('metrik').value+'&stunden='+$('std').value);daten=j.daten;$('info').textContent=j.anzahl+' Messungen gespeichert';zeichnen()}catch(x){$('info').textContent='Fehler: '+x.message}}
function zeichnen(){const cv=$('c');const w=cv.clientWidth,h=360;cv.width=w*devicePixelRatio;cv.height=h*devicePixelRatio;const g=cv.getContext('2d');g.scale(devicePixelRatio,devicePixelRatio);g.clearRect(0,0,w,h);
 const namen=Object.keys(daten);const farbe=getComputedStyle(document.body).color;const mut='#7b8a97';
 if(!namen.length){g.fillStyle=mut;g.font='14px system-ui';g.fillText('Noch keine Messwerte in diesem Zeitraum.',20,40);$('leg').innerHTML='';return}
 let x0=1e18,x1=0,y0=1e18,y1=-1e18;namen.forEach(n=>daten[n].forEach(p=>{x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1])}));
 if(y1-y0<1){const m=(y0+y1)/2;y0=m-.5;y1=m+.5}const pad=(y1-y0)*.08;y0-=pad;y1+=pad;if(x1===x0)x1=x0+1;
 const L=48,R=12,T=10,B=26;const X=t=>L+(t-x0)/(x1-x0)*(w-L-R),Y=v=>T+(1-(v-y0)/(y1-y0))*(h-T-B);
 g.strokeStyle='#8a99a833';g.fillStyle=mut;g.font='12px system-ui';g.lineWidth=1;
 for(let i=0;i<=4;i++){const v=y0+(y1-y0)*i/4;const y=Y(v);g.beginPath();g.moveTo(L,y);g.lineTo(w-R,y);g.stroke();g.fillText(v.toFixed(Math.abs(y1-y0)<10?1:0),4,y+4)}
 const lang=(x1-x0)>2*86400;for(let i=0;i<=4;i++){const t=x0+(x1-x0)*i/4;const d=new Date(t*1000);g.fillText(lang?d.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'}):d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}),X(t)-16,h-6)}
 namen.forEach((n,i)=>{g.strokeStyle=FARBEN[i%FARBEN.length];g.lineWidth=2;g.beginPath();daten[n].forEach((p,k)=>{k?g.lineTo(X(p[0]),Y(p[1])):g.moveTo(X(p[0]),Y(p[1]))});g.stroke()});
 $('leg').innerHTML=namen.map((n,i)=>'<span><span class="punkt" style="background:'+FARBEN[i%FARBEN.length]+'"></span>'+e(n)+'</span>').join('');
 cv.onmousemove=ev=>{const r=cv.getBoundingClientRect();const t=x0+(ev.clientX-r.left-L)/(w-L-R)*(x1-x0);let s='';namen.forEach(n=>{let b=null;daten[n].forEach(p=>{if(b===null||Math.abs(p[0]-t)<Math.abs(b[0]-t))b=p});if(b)s+=e(n)+': '+b[1]+'   '});$('tip').textContent=new Date(t*1000).toLocaleString('de-DE')+'   '+s};}
async function tage(){try{const t=await api('/api/verlauf/tage?metrik='+$('metrik').value+'&tage=14');$('tage').innerHTML=t.length?'<tr><th>Tag</th><th>Gerät</th><th>niedrigster</th><th>höchster</th><th>Mittel</th></tr>'+t.map(x=>'<tr><td>'+e(x.tag)+'</td><td>'+e(x.geraet)+'</td><td>'+x.min+'</td><td>'+x.max+'</td><td>'+x.mittel+'</td></tr>').join(''):'<tr><td class="mut">Noch keine Werte.</td></tr>'}catch(x){}$('csv').href='/api/verlauf.csv?stunden='+$('std').value}
async function vergleich(){const m=$('metrik').value;$('vgk').style.display=m.startsWith('s_')?'block':'none';if(!m.startsWith('s_'))return;
 try{const v=await api('/api/verlauf/vergleich?metrik='+m+'&stunden='+$('std').value);const ein=m==='s_temp'?' °C':' %';const g=m==='s_temp'?[0.5,1.0]:[3,6];
 $('vg').innerHTML=v.length?'<tr><th>Gerät</th><th>Mittel</th><th>Abweichung</th><th></th></tr>'+v.map(x=>{const a=Math.abs(x.abw);return '<tr><td>'+e(x.geraet)+'</td><td>'+x.mittel.toLocaleString('de-DE')+ein+'</td><td>'+(x.abw>0?'+':'')+x.abw.toLocaleString('de-DE')+ein+'</td><td><span class="punkt '+(a>=g[1]?'problem':a>=g[0]?'warn':'')+'"></span>'+(a>=g[1]?'deutlich daneben':a>=g[0]?'leicht daneben':'passt')+'</td></tr>'}).join('')+'<tr><td colspan="4" class="mut">Grundlage: '+v[0].n+' gemeinsame halbe Stunden.</td></tr>':'<tr><td class="mut">Zu wenig gemeinsame Messwerte: Es braucht mindestens zwei Geräte mit eigenem Sensor (Fusion oder Apex mit Gehäusesensor, Sensorknoten), die gleichzeitig gemessen haben.</td></tr>'}catch(x){$('vg').innerHTML='<tr><td class="mut">'+e(x.message)+'</td></tr>'}}
const laden0=laden;laden=async function(){await laden0();tage();vergleich()};
addEventListener('resize',()=>zeichnen());start();setInterval(laden,60000);
""")


# ── Wetterwand ───────────────────────────────────────────────────────────────
WAND = r"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wetterwand – WetterCube Control</title><link rel="icon" href="/icon.svg" type="image/svg+xml">
<style>
:root{--bg:#06203b;--card:#184a7e;--tx:#fff;--mut:#bcd3e6;--warn:#e90b0b;--ok:#4ade80}
body.hell{--bg:#fff;--card:#e0f7ff;--tx:#111827;--mut:#4b5563}
@media(prefers-color-scheme:light){body:not(.dunkel){--bg:#fff;--card:#e0f7ff;--tx:#111827;--mut:#4b5563}}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;display:flex;flex-direction:column}
header{display:flex;justify-content:space-between;align-items:center;padding:2vh 3vw}.uhr{font-size:7vh;font-weight:300;line-height:1}.datum{font-size:2.4vh;color:var(--mut)}
#warn{font-size:3vh;color:#fff;background:var(--warn);padding:1.2vh 2vw;border-radius:1vh;display:none}
main{flex:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(24vw,1fr));gap:2vh 2vw;padding:0 3vw 3vh;align-content:center}
.k{background:var(--card);border-radius:2vh;padding:3vh 2.5vw;text-align:center}.k.aus{opacity:.35}
.n{font-size:3vh;color:var(--mut)}.t{font-size:13vh;font-weight:300;line-height:1.1}.w{font-size:3.4vh}.z{font-size:2.4vh;color:var(--mut);margin-top:1vh}
.ba{position:fixed;right:1vw;bottom:1vh;font-size:1.6vh;color:var(--mut)}.ba a,.ba button{color:var(--mut);background:none;border:0;cursor:pointer;font:inherit;margin-left:1vw}
</style></head><body>
<header><div><div class="uhr" id="uhr"></div><div class="datum" id="datum"></div></div><div id="warn"></div></header>
<main id="m"></main>
<div class="ba"><a href="/">← Übersicht</a><button onclick="const h=document.body.classList.contains('hell')||(matchMedia('(prefers-color-scheme: light)').matches&&!document.body.classList.contains('dunkel'));document.body.classList.toggle('hell',!h);document.body.classList.toggle('dunkel',h)">hell/dunkel</button><button onclick="document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen()">Vollbild</button></div>
<script>
const e=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const q=new URLSearchParams(location.search);if(q.get('hell')||q.get('farbe')==='hell')document.body.classList.add('hell');if(q.get('farbe')==='dunkel')document.body.classList.add('dunkel');const nur=(q.get('geraete')||'').split(',').filter(x=>x);
function uhr(){const d=new Date();document.getElementById('uhr').textContent=d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'});document.getElementById('datum').textContent=d.toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}
async function lade(){try{let l=await (await fetch('/api/geraete')).json();l=l.filter(d=>d.art==='status'&&(!nur.length||nur.includes(d.ip)));
 const warn=l.filter(d=>d.online!==false&&(d.status||{}).dwd>0);const w=document.getElementById('warn');w.style.display=warn.length?'block':'none';w.textContent='⚠ DWD-Warnung: '+warn.map(d=>d.name.replace('WetterCube ','')).join(', ');
 document.getElementById('m').innerHTML=l.map(d=>{const s=d.status||{};const on=d.online!==false;return '<div class="k'+(on?'':' aus')+'"><div class="n">'+e(d.name.replace('WetterCube ',''))+'</div><div class="t">'+(on?e(s.temp)+'°':'–')+'</div><div class="w">'+e(on?s.wetter:'nicht erreichbar')+'</div><div class="z">'+(on?[s.gefuehlt!=null?'gefühlt '+e(s.gefuehlt)+'°':'',s.feuchte!=null?e(s.feuchte)+' %':'',s.wind!=null?'Wind '+e(s.wind)+' km/h':'',s.druck!=null?e(s.druck)+' hPa':''].filter(x=>x).join(' · '):'')+'</div></div>'}).join('')}catch(x){}}
uhr();setInterval(uhr,10000);lade();setInterval(lade,10000);
</script></body></html>"""


# ── Einstellungen kopieren ───────────────────────────────────────────────────
KOPIEREN = seite("Einstellungen kopieren", "/kopieren", r"""
<div class="k"><h2>Einstellungen auf andere Geräte übertragen</h2>
<div class="mut">Wähle ein Gerät als Vorlage, die Ziele und was übertragen wird. Du siehst zuerst eine Vorschau der Änderungen. Vorher legt Control von jedem Ziel eine Sicherheitskopie an, die Ziele starten danach neu. Passwörter, WLAN-Zugang und das ntfy-Topic werden nie übertragen. Geräte mit Web-Passwort gehen nicht. Zwischen verschiedenen Gerätetypen (zum Beispiel Apex nach Plus) werden nur Standort, Warnungen und Hinweise übertragen, weil Anzeige und Updates je Gerät verschieden sind.</div></div>
<div class="k"><h2>1. Vorlage</h2><select id="quelle" onchange="ziele()"></select></div>
<div class="k"><h2>2. Ziele</h2><div id="ziele"></div></div>
<div class="k"><h2>3. Was übertragen?</h2><div id="gr"></div></div>
<div class="k"><div class="zeile"><button onclick="vorschau()">Vorschau</button><button class="v" id="go" onclick="los()" disabled>Übernehmen</button></div><div id="erg"></div></div>
""", r"""
let geraete=[],gruppen={};
async function start(){const l=await api('/api/geraete');geraete=l.filter(d=>d.art==='status'&&d.online!==false);gruppen=await api('/api/kopieren/gruppen');
 $('quelle').innerHTML=geraete.map(d=>'<option value="'+e(d.ip)+'">'+e(d.name)+' ('+e(d.ip)+')</option>').join('');
 $('gr').innerHTML=Object.keys(gruppen).map(k=>'<label class="c"><input type="checkbox" class="gk" value="'+k+'"> '+e(gruppen[k])+'</label>').join('');ziele()}
function ziele(){const qip=$('quelle').value;$('ziele').innerHTML=geraete.filter(d=>d.ip!==qip).map(d=>'<label class="c"><input type="checkbox" class="zk" value="'+e(d.ip)+'"> '+e(d.name)+'</label>').join('')||'<div class="mut">Keine weiteren Geräte gefunden.</div>';$('go').disabled=true;$('erg').innerHTML=''}
function auswahl(){return{quelle:$('quelle').value,ziele:[...document.querySelectorAll('.zk:checked')].map(x=>x.value),gruppen:[...document.querySelectorAll('.gk:checked')].map(x=>x.value)}}
function fehlt(f){const g=(f&&f.gruppen)||[],n=(f&&f.einzeln)||0;if(!g.length&&!n)return'';return'<div class="mut" style="margin-top:6px">Auf diesem Gerät nicht vorhanden und übersprungen: '+(g.length?e(g.join(', '))+(n?' sowie '+n+' einzelne Einstellung(en)':''):n+' einzelne Einstellung(en)')+'.</div>'}
function gesperrt(l){if(!l||!l.length)return'';return'<div class="mut" style="margin-top:6px">Nicht übertragen, weil es zwischen diesen Gerätetypen nicht sinnvoll ist: '+l.map(x=>'<b>'+e(x.gruppe)+'</b> ('+e(x.grund)+')').join('; ')+'.</div>'}
function tabelle(r){return r.map(t=>'<h2 style="margin-top:12px">'+e(t.ziel)+(t.text?' – '+e(t.text):'')+'</h2>'+(t.aenderungen.length?'<table><tr><th>Einstellung</th><th>bisher</th><th>neu</th></tr>'+t.aenderungen.map(a=>'<tr><td>'+e(a.schluessel)+'</td><td>'+e(JSON.stringify(a.alt))+'</td><td>'+e(JSON.stringify(a.neu))+'</td></tr>').join('')+'</table>':'<div class="mut">Keine Änderungen nötig (schon gleich oder Einstellung nicht vorhanden).</div>')+fehlt(t.fehlt)+gesperrt(t.gesperrt)).join('')}
async function vorschau(){const a=auswahl();if(!a.ziele.length||!a.gruppen.length){$('erg').innerHTML='<div class="mut">Bitte mindestens ein Ziel und eine Einstellungsgruppe wählen.</div>';return}
 $('erg').innerHTML='<div class="mut">lese die Geräte ...</div>';try{const r=await api('/api/kopieren',Object.assign(a,{ausfuehren:false}));$('erg').innerHTML=tabelle(r);$('go').disabled=!r.some(t=>t.aenderungen.length)}catch(x){$('erg').innerHTML='<div class="mut">Nicht möglich: '+e(x.message)+'</div>'}}
async function los(){const a=auswahl();if(!confirm('Die Einstellungen jetzt auf '+a.ziele.length+' Gerät(e) übertragen? Sie starten danach neu.'))return;
 $('erg').innerHTML='<div class="mut">übertrage ...</div>';try{const r=await api('/api/kopieren',Object.assign(a,{ausfuehren:true}));$('erg').innerHTML=tabelle(r);$('go').disabled=true}catch(x){$('erg').innerHTML='<div class="mut">Nicht möglich: '+e(x.message)+'</div>'}}
start();
""")


# ── Installer ────────────────────────────────────────────────────────────────
INSTALLER = seite("Installer", "/installer", r"""
<div class="k" id="fehlt" style="display:none"><b>Esptool und pyserial fehlen.</b><br>Starte WetterCube Control über das Programm oder die Starter-Datei (richtet sich selbst ein), oder installiere: <code>pip install esptool pyserial certifi</code></div>
<div class="k" id="form" style="max-width:680px">
<h2>Firmware auf ein Gerät spielen</h2>
<div class="zeile"><label for="p" class="mut" style="min-width:90px">Gerät</label><select id="p" onchange="versionen()"></select></div>
<div class="zeile"><label for="v" class="mut" style="min-width:90px">Version</label><select id="v" onchange="hinweisV()"></select></div>
<div class="mut" id="vh" style="color:var(--gelb)"></div>
<div class="zeile"><label for="u" class="mut" style="min-width:90px">USB-Anschluss</label><select id="u"></select><button onclick="info()">Neu suchen</button></div>
<div class="mut">Gerät per USB anschließen. Fehlt der Anschluss, Kabel prüfen (es muss ein Datenkabel sein).</div>
<div class="zeile"><button onclick="start('erkennen')">Gerät erkennen (nur lesen)</button></div>
<label class="c"><input type="checkbox" id="l"> Flash vorher komplett löschen (löscht auch Einstellungen und WLAN)</label>
<details class="mut" style="margin:4px 0 8px"><summary style="cursor:pointer">Technische Optionen: Gerät lässt sich nicht erkennen oder flashen?</summary><div class="mut" style="margin:6px 0">Das brauchst du <b>normalerweise nicht</b>. Control schaltet die meisten Geräte selbst um. Nur wenn das Gerät nicht antwortet (vor allem beim Next/CYD unter Windows): BOOT-Taste gedrückt halten, kurz RESET drücken, BOOT loslassen, dann erst auf „Gerät erkennen“ oder „Firmware aufspielen“ klicken.</div><label class="c"><input type="checkbox" id="man"><span>Ich habe das Gerät schon von Hand in den Flash-Modus gebracht (Control schaltet dann nichts selbst um)</span></label></details>
<label class="c" style="margin-top:12px"><input type="checkbox" id="haftung" onchange="sperre()"><span>Ich habe die <a href="https://wettercube.de/nutzungshinweise/" target="_blank" rel="noopener">Nutzungshinweise</a> gelesen und nutze die Firmware auf eigene Gefahr.</span></label>
<div class="mut" style="margin:4px 0 10px">Datenschutz: Die Liste der Versionen, die Firmware und die Änderungsliste im Update-Dialog lädt das Programm von wettercube.de. Der jeweilige Server sieht deine IP-Adresse. Das geschieht nur, wenn du diese Seite öffnest, Firmware aufspielst oder im Update-Dialog auf die Bestätigung wartest. Sonst sendet WetterCube Control nichts ins Internet; Gerätesuche und Sicherungen bleiben in deinem Netz und auf deinem Rechner.</div>
<button class="v" id="go" onclick="start('flashen')">Firmware aufspielen</button><div class="mut" id="hinweis" style="color:var(--warn);margin-top:8px"></div>
</div>
<div class="k" id="wlan" style="max-width:680px;display:none">
<h2>WLAN per USB einrichten</h2>
<div class="mut">Für ein frisch aufgespieltes Gerät oder eines im Einrichtungsmodus: WLAN-Name und Passwort gehen über das USB-Kabel ans Gerät, du musst dich nicht mit dem Einrichtungs-WLAN des Geräts verbinden. Das Gerät braucht dafür eine Firmware, die das kann (WetterCube Apex, Next ab 0.3.0-rc1, Fusion ab 1.0.0-rc18, Plus ab 2.1.18 und Plus Europe ab 0.1.0-beta9), und muss im Einrichtungsmodus sein (frisch aufgespielt oder ohne erreichbares WLAN). Das Passwort geht nur ans Gerät und wird nirgends gespeichert. Der USB-Anschluss ist der oben gewählte.</div>
<div class="zeile"><button onclick="wlanAktion('pruefen')">Gerät prüfen</button><button onclick="wlanAktion('netze')">WLAN-Netze vom Gerät suchen</button></div>
<div class="zeile"><label for="w_s" class="mut" style="min-width:90px">WLAN-Name</label><input type="text" id="w_s" list="w_n" autocomplete="off" autocapitalize="off" style="min-width:240px"><datalist id="w_n"></datalist></div>
<div class="zeile"><label for="w_p" class="mut" style="min-width:90px">Passwort</label><input type="password" id="w_p" autocomplete="new-password" style="min-width:240px"><label class="c" style="margin:0"><input type="checkbox" onchange="$('w_p').type=this.checked?'text':'password'"> zeigen</label></div>
<button class="v" onclick="wlanAktion('senden')">WLAN ans Gerät senden</button>
<p id="w_t" class="mut" style="margin-top:10px"></p>
</div>
<div class="k" style="max-width:680px"><h2 id="t">Ergebnis</h2><div id="balk" style="display:none;height:14px;border-radius:999px;background:var(--feld);border:1px solid var(--rand);overflow:hidden;margin:8px 0"><div id="bal" style="height:100%;width:0;background:var(--ac);transition:width .3s"></div></div><p id="info" style="margin:8px 0">Noch nichts gestartet.</p><details><summary class="mut">Technisches Protokoll</summary><pre id="log">noch nichts gestartet</pre></details></div>
""", r"""
let wp=null;
async function wlanAktion(a){const port=$('u').value;if(!port){$('w_t').textContent='Kein USB-Anschluss gewählt (oben).';return}
 if(a==='senden'&&!$('w_s').value.trim()){$('w_t').textContent='Bitte den WLAN-Namen eintragen.';return}
 $('w_t').textContent='...';
 try{await api('/api/wlan/start',{aktion:a,port:port,ssid:$('w_s').value,passwort:$('w_p').value})}catch(x){$('w_t').textContent=x.message;return}
 if(wp)clearInterval(wp);
 const f=async()=>{const j=await api('/api/wlan/status');$('w_t').textContent=j.text||'';
  if(j.netze&&j.netze.length)$('w_n').innerHTML=j.netze.map(n=>'<option value="'+e(n.ssid)+'">'+e(n.ssid+' ('+n.rssi+' dBm'+(n.gesichert?'':', offen')+')')+'</option>').join('');
  if(!j.laeuft){clearInterval(wp);wp=null;if(a==='senden'&&j.ok){$('w_p').value='';if(j.adresse&&/^https?:\/\/[\w.:\/-]+$/.test(j.adresse))$('w_t').innerHTML=e(j.text)+' Das Gerät startet neu. Ort und alles Weitere stellst du im Browser ein: <a href="'+e(j.adresse)+'" target="_blank" rel="noopener">'+e(j.adresse)+'</a>';else $('w_t').textContent=j.text+' Das Gerät startet neu und erscheint gleich in der Übersicht (Ort und alles Weitere stellst du dann im Browser ein).'}}};
 await f();wp=setInterval(f,800)}
let pollt=null;
function sperre(){const g=$('go');g.disabled=!$('haftung').checked||g.dataset.laeuft==='1'}
function hinweisV(){$('vh').textContent=$('v').value?'Ältere Version: Einstellungen aus neueren Versionen kennt sie vielleicht nicht. Nur nutzen, wenn die neueste Version Probleme macht.':''}
async function versionen(){const k=$('p').value;$('v').innerHTML='<option value="">Neueste (empfohlen)</option>';hinweisV();try{const l=await api('/api/installer/versionen?produkt='+encodeURIComponent(k));$('v').innerHTML+=l.map(t=>'<option value="'+e(t)+'">'+e(t)+'</option>').join('')}catch(x){}}
async function info(){const j=await api('/api/installer/info');$('fehlt').style.display=j.verfuegbar?'none':'block';$('form').style.display=j.verfuegbar?'block':'none';$('wlan').style.display=j.verfuegbar?'block':'none';if(!j.verfuegbar)return;
 if(!$('p').options.length){$('p').innerHTML=j.produkte.map(x=>'<option value="'+x.key+'">'+e(x.name)+'</option>').join('');versionen()}
 $('u').innerHTML=j.ports.length?j.ports.map(x=>'<option value="'+e(x.port)+'">'+e(x.text)+'</option>').join(''):'<option value="">kein Gerät gefunden</option>'}
async function start(aktion){const port=$('u').value;if(!port){$('hinweis').textContent='Kein USB-Anschluss gewählt.';return}
 const name=$('p').selectedOptions[0].textContent;
 if(aktion==='flashen'){let ver='';try{const j=await api('/api/installer/plan?produkt='+encodeURIComponent($('p').value)+'&version='+encodeURIComponent($('v').value));ver=' (Version '+j.version+', '+j.dateien.length+' Dateien)'}catch(x){$('hinweis').textContent=x.message;return}
  const frage='Firmware "'+name+'"'+ver+' auf das Gerät an '+port+' aufspielen?'+($('l').checked?'\n\nACHTUNG: Der Flash wird vorher komplett gelöscht, Einstellungen und WLAN-Zugang gehen verloren.':'\n\nEinstellungen und WLAN bleiben erhalten.');if(!confirm(frage))return}
 $('hinweis').textContent='';
 try{await api('/api/installer/start',{aktion:aktion,produkt:$('p').value,version:$('v').value,port:port,loeschen:$('l').checked,manuell:$('man').checked,haftung:$('haftung').checked})}catch(x){$('hinweis').textContent=x.message;return}
 $('t').scrollIntoView({behavior:'smooth',block:'start'});poll()}
async function poll(){if(pollt)clearInterval(pollt);const f=async()=>{const j=await api('/api/installer/status');
 $('t').textContent=(j.titel||'Ergebnis')+(j.laeuft?' ...':(j.ok===true?' ✓ fertig':(j.ok===false?' ✗ fehlgeschlagen':'')));$('log').textContent=j.log.join('\n')||'...';$('info').textContent=j.info||(j.laeuft?'Bitte warten ...':'');$('log').scrollTop=1e9;$('balk').style.display=(j.laeuft||j.prozent)?'block':'none';$('bal').style.width=(j.prozent||0)+'%';
 $('go').dataset.laeuft=j.laeuft?'1':'';sperre();if(!j.laeuft){clearInterval(pollt);pollt=null}};await f();pollt=setInterval(f,1000)}
info();sperre();
""")


# ── Alle Geraete ─────────────────────────────────────────────────────────────
ALLE = seite("Alle Geräte", "/alle", r"""
<div class="k" style="max-width:760px"><h2>Updates für alle Geräte</h2>
<div class="mut">Control fragt jedes Gerät, ob ein Update bereitliegt. Die Updates laufen <b>nacheinander</b>: Erst wenn ein Gerät mit der neuen Version wieder antwortet, kommt das nächste. Vorher siehst du, was neu ist. Das Gerät lädt die Firmware selbst und startet neu (je etwa 1 bis 2 Minuten).</div>
<div class="zeile"><button onclick="suchen()">Nach Updates suchen</button><span class="mut" id="us"></span></div>
<table id="ut" style="display:none"></table>
<div class="zeile"><button class="v" id="ug" onclick="starten()" style="display:none">Ausgewählte aktualisieren</button></div>
<div id="up"></div></div>
<div class="k" style="max-width:760px"><h2>Einstellung für alle Geräte</h2>
<div class="mut">Eine Einstellung auf mehreren Geräten gleichzeitig setzen. Du siehst zuerst eine Vorschau. Control legt vor jeder Änderung eine Sicherheitskopie an, <b>die Geräte starten danach neu</b>. Geräte, die eine Einstellung nicht kennen, werden dabei übersprungen.</div>
<div id="ea"></div>
<div class="mut" style="margin-top:8px">Geräte</div><div id="eg"></div>
<div class="zeile"><button onclick="vorschau()">Vorschau</button><button class="v" id="eok" onclick="uebernehmen()" style="display:none">Übernehmen</button></div>
<div id="er" class="mut"></div></div>
""", r"""
let plan=null,geraete=[],ups=[],pollU=null;
async function init(){plan=await api('/api/alle/plan');geraete=plan.geraete;
 $('ea').innerHTML=Object.entries(plan.aktionen).map(([k,a])=>'<div class="zeile"><label class="c" style="margin:0;min-width:330px"><input type="checkbox" id="a_'+k+'"> '+e(a.titel)+'</label><input type="text" id="w_'+k+'" size="4" placeholder="'+a.min+'–'+a.max+'"></div>').join('');
 $('eg').innerHTML=geraete.map((g,i)=>'<label class="c"><input type="checkbox" class="gc" value="'+e(g.ip)+'" '+(g.online?'checked':'disabled')+'> '+e(g.name)+(g.online?'':' (nicht erreichbar)')+'</label>').join('')||'<div class="mut">Noch keine Geräte gefunden.</div>'}
async function suchen(){$('us').textContent='frage die Geräte (das kann einige Sekunden dauern) ...';ups=[];$('ut').style.display='none';$('ug').style.display='none';
 const r=await Promise.all(geraete.filter(g=>g.online).map(async g=>{try{const u=await api('/api/update/pruefen?ip='+encodeURIComponent(g.ip));return {g,u}}catch(x){return {g,u:null}}}));
 ups=r.filter(x=>x.u&&x.u.verfuegbar&&!x.u.aus);
 const aus=r.filter(x=>x.u&&x.u.aus).length,still=r.filter(x=>!x.u).length;
 $('us').textContent=(ups.length?ups.length+' Update(s) verfügbar.':'Alle Geräte sind aktuell.')+(aus?' '+aus+' Gerät(e) mit ausgeschalteten Updates.':'')+(still?' '+still+' ohne Antwort.':'');
 if(ups.length){$('ut').innerHTML=ups.map(x=>'<tr><td><input type="checkbox" class="uc" value="'+e(x.g.ip)+'" checked></td><td>'+e(x.g.name)+'</td><td>'+e(x.u.aktuell)+' → <b>'+e(x.u.neueste)+'</b></td></tr>').join('');$('ut').style.display='table';$('ug').style.display='inline-block'}}
async function starten(){const ips=[...document.querySelectorAll('.uc:checked')].map(x=>x.value);if(!ips.length){alert('Bitte mindestens ein Gerät wählen.');return}
 const p=dialogBestaetigen('Updates einspielen?','<div class="mut">Control lädt die Änderungslisten von GitHub (nur weil du gerade auf die Updates wartest) ...</div>','Jetzt nacheinander installieren','Abbrechen');
 const teile=await Promise.all(ips.map(async ip=>{const x=ups.find(y=>y.g.ip===ip);let j;try{j=await api('/api/update/aenderungen?ip='+encodeURIComponent(ip)+'&version='+encodeURIComponent(x.u.neueste))}catch(z){j=null}return '<h2 style="margin-top:10px">'+e(x.g.name)+': '+e(x.u.aktuell)+' → '+e(x.u.neueste)+'</h2>'+neuesHtml(j)}));
 window.dlgInhalt('<div style="margin-bottom:6px">Die Geräte werden <b>nacheinander</b> aktualisiert und starten dabei neu. Bitte nichts ausschalten.</div>'+teile.join(''));
 if(!await p)return;
 try{await api('/api/alle/updates',{ips:ips})}catch(x){$('up').textContent='Nicht möglich: '+x.message;return}
 $('ug').disabled=true;fortschritt();if(pollU)clearInterval(pollU);pollU=setInterval(fortschritt,3000)}
async function fortschritt(){const j=await api('/api/alle/status');$('up').innerHTML='<table>'+j.schritte.map(s=>'<tr><td>'+e(s.name)+'</td><td>'+e(s.von)+' → '+e(s.nach)+'</td><td>'+(s.ok===true?'<span style="color:var(--ok)">✓</span> ':(s.ok===false?'<span style="color:var(--warn)">✗</span> ':''))+e(s.stand)+'</td></tr>').join('')+'</table>'+(j.fertig?'<div class="mut" style="margin-top:6px">Fertig.</div>':'');
 if(!j.laeuft){clearInterval(pollU);pollU=null;$('ug').disabled=false}}
function auswahl(){const werte={};for(const k of Object.keys(plan.aktionen)){if($('a_'+k).checked){werte[k]=$('w_'+k).value.trim()}}return {werte:werte,ips:[...document.querySelectorAll('.gc:checked')].map(x=>x.value)}}
async function vorschau(){const d=auswahl();$('er').textContent='prüfe ...';$('eok').style.display='none';try{const r=await api('/api/alle/einstellung',d);
 $('er').innerHTML=r.map(x=>'<div style="margin-top:8px"><b>'+e(x.ziel)+'</b>: '+(x.aenderungen.length?x.aenderungen.map(a=>e(a.schluessel)+': '+e(a.alt)+' → <b>'+e(a.neu)+'</b>').join(', '):'nichts zu ändern')+(x.fehlt.length?' <span class="mut">(kennt nicht: '+e(x.fehlt.join(', '))+')</span>':'')+'</div>').join('');
 if(r.some(x=>x.aenderungen.length))$('eok').style.display='inline-block'}catch(x){$('er').textContent='Nicht möglich: '+x.message}}
async function uebernehmen(){if(!confirm('Die Einstellung auf den gewählten Geräten übernehmen?\n\nControl legt vorher eine Sicherheitskopie an, die Geräte starten danach neu.'))return;const d=auswahl();d.ausfuehren=true;$('er').textContent='übernehme ...';
 try{const r=await api('/api/alle/einstellung',d);$('er').innerHTML=r.map(x=>'<div><b>'+e(x.ziel)+'</b>: '+(x.ok?'<span style="color:var(--ok)">✓</span> ':'<span style="color:var(--warn)">✗</span> ')+e(x.text)+'</div>').join('');$('eok').style.display='none'}catch(x){$('er').textContent='Nicht möglich: '+x.message}}
init();
""")


# ── Hilfe: Geraet nicht gefunden? ────────────────────────────────────────────
HILFE = seite("Hilfe", "/hilfe", r"""
<div class="k" style="max-width:760px"><h2>Gerät nicht gefunden?</h2>
<div class="mut">Control prüft Schritt für Schritt, woran es liegen kann, und sagt es dir in Klartext. Alles bleibt in deinem Netz, es geht nichts ins Internet. An den Geräten wird nichts verändert.</div>
<div class="zeile"><button class="v" onclick="pruefen()">Jetzt prüfen</button><button onclick="suche()">Jetzt im Netz suchen</button><span class="mut" id="hs"></span></div>
<div id="hl"></div></div>
<div class="k" style="max-width:760px"><h2>Adresse von Hand prüfen</h2>
<div class="mut">Die IP-Adresse deines Geräts steht im Router unter „Heimnetz“ (zum Beispiel 192.168.178.52), oft auch auf dem Display des Geräts.</div>
<div class="zeile"><input type="text" id="adr" placeholder="z. B. 192.168.178.52" size="26" autocapitalize="off"><button onclick="adresse()">Prüfen</button><button class="v" id="hz" onclick="hinzu()" style="display:none">Hinzufügen</button></div>
<div id="ar" class="mut"></div></div>
""", r"""
const ICON={ok:'<span style="color:var(--ok)">✓</span>',warn:'<span style="color:var(--gelb)">!</span>',fehler:'<span style="color:var(--warn)">✗</span>',info:'<span class="mut">i</span>'};
async function pruefen(){$('hs').textContent='prüfe (etwa 5 Sekunden) ...';$('hl').innerHTML='';try{const l=await api('/api/netzcheck');
 $('hl').innerHTML=l.map(x=>'<div class="meld"><b>'+ICON[x.stufe]+' '+e(x.titel)+'</b><div class="mut" style="white-space:pre-line;margin-top:2px">'+e(x.text)+'</div></div>').join('');$('hs').textContent=''}catch(x){$('hs').textContent='Fehler: '+x.message}}
async function suche(){$('hs').textContent='suche im Netz ...';try{await api('/api/suche',{});setTimeout(()=>{$('hs').textContent='Die Suche läuft im Hintergrund. Schau in einer Minute auf der Übersicht nach.'},500)}catch(x){$('hs').textContent='Fehler: '+x.message}}
let gefundeneAdr='';
async function adresse(){const a=$('adr').value.trim();$('hz').style.display='none';if(!a){$('ar').textContent='Bitte eine Adresse eintragen.';return}$('ar').textContent='prüfe ...';
 try{const r=await api('/api/netzcheck/adresse',{adresse:a});$('ar').innerHTML=(r.ok?ICON.ok:ICON.fehler)+' '+e(r.text)+(r.name?' ('+e(r.name)+')':'');if(r.ok){gefundeneAdr=a;$('hz').style.display='inline-block'}}catch(x){$('ar').textContent='Fehler: '+x.message}}
async function hinzu(){try{const r=await api('/api/geraete/hinzufuegen',{adresse:gefundeneAdr});$('ar').textContent='Hinzugefügt: '+r.name+'. Du findest es auf der Übersicht.';$('hz').style.display='none'}catch(x){$('ar').textContent='Nicht möglich: '+x.message}}
""")


# ── Assistent: Neues Geraet einrichten ───────────────────────────────────────
ASSISTENT = seite("Neues Gerät", "/assistent", r"""
<div class="k" style="max-width:720px"><h2>Neues Gerät einrichten</h2>
<div class="mut">Schritt für Schritt vom neu gekauften Board bis zum fertigen Gerät: Firmware aufspielen, WLAN, finden, benennen, Ort, sichern. Du kannst jeden Schritt überspringen, den du schon erledigt hast.</div>
<div id="kopf" class="zeile" style="gap:14px;margin-top:10px"></div></div>

<div class="k" id="st0" style="max-width:720px"><h2>1 · Gerät und USB-Kabel</h2>
<div class="mut">Schließe das Gerät <b>per USB-Datenkabel</b> an den Rechner an (ein reines Ladekabel genügt nicht).</div>
<div class="zeile"><label for="p" class="mut" style="min-width:110px">Gerät</label><select id="p"></select></div>
<div class="zeile"><label for="u" class="mut" style="min-width:110px">USB-Anschluss</label><select id="u"></select><button onclick="ports()">Neu suchen</button></div>
<label class="c"><input type="checkbox" id="l"> Flash vorher komplett löschen (auch Einstellungen und WLAN). Für ein neues Gerät nicht nötig.</label>
<details class="mut" style="margin:4px 0 8px"><summary style="cursor:pointer">Technische Optionen: Gerät lässt sich nicht erkennen oder flashen?</summary><div class="mut" style="margin:6px 0">Das brauchst du <b>normalerweise nicht</b>. Control schaltet die meisten Geräte selbst um. Nur wenn das Gerät nicht antwortet (vor allem beim Next/CYD unter Windows): BOOT-Taste gedrückt halten, kurz RESET drücken, BOOT loslassen, dann erst auf „Firmware aufspielen“ klicken.</div><label class="c"><input type="checkbox" id="am"><span>Ich habe das Gerät schon von Hand in den Flash-Modus gebracht (Control schaltet dann nichts selbst um)</span></label></details>
<label class="c"><input type="checkbox" id="h"><span>Ich habe die <a href="https://wettercube.de/nutzungshinweise/" target="_blank" rel="noopener">Nutzungshinweise</a> gelesen und nutze die Firmware auf eigene Gefahr.</span></label>
<div class="zeile"><button class="v" onclick="flashen()">Firmware aufspielen</button><button onclick="zeige(2)">Firmware ist schon drauf: weiter zum WLAN</button></div>
<div class="mut" id="m0" style="color:var(--warn)"></div></div>

<div class="k" id="st1" style="max-width:720px;display:none"><h2>2 · Firmware wird aufgespielt</h2>
<div id="fbalk" style="height:14px;border-radius:999px;background:var(--feld);border:1px solid var(--rand);overflow:hidden;margin:8px 0"><div id="fbal" style="height:100%;width:0;background:var(--ac);transition:width .3s"></div></div>
<p id="f1" style="margin:8px 0">...</p><details><summary class="mut">Technisches Protokoll</summary><pre id="fl"></pre></details>
<div class="zeile"><button class="v" id="f1w" onclick="zeige(2)" style="display:none">Weiter zum WLAN</button><button id="f1z" onclick="zeige(0)" style="display:none">Zurück</button></div></div>

<div class="k" id="st2" style="max-width:720px;display:none"><h2>3 · WLAN</h2>
<div id="wAlt" style="display:none"><p>Dieses Gerät kennt <b>WLAN per USB nicht</b>. Du richtest es über sein eigenes Einrichtungs-WLAN ein:</p>
<ol style="margin:6px 0 10px 20px"><li>Verbinde Handy oder Rechner mit dem WLAN, das auf dem Display des Geräts steht (Name und Passwort stehen dort).</li><li>Öffne <b>192.168.4.1</b> im Browser (oft öffnet sich die Seite von selbst) und trage dein Heim-WLAN und den Ort ein.</li><li>Das Gerät startet neu und verbindet sich. Dann geht es hier weiter.</li></ol>
<div class="zeile"><button class="v" onclick="zeige(3)">Weiter: Gerät finden</button></div></div>
<div id="wUsb">
<div class="mut">WLAN-Name und Passwort gehen über das USB-Kabel ans Gerät. Das Gerät muss im Einrichtungsmodus sein (frisch aufgespielt) und eine Firmware mit dieser Funktion haben. Sonst überspringe den Schritt und verbinde das Gerät über sein Einrichtungs-WLAN (steht auf dem Display).</div>
<div class="zeile"><button onclick="wlan('pruefen')">Gerät prüfen</button><button onclick="wlan('netze')">WLAN-Netze vom Gerät suchen</button></div>
<div class="zeile"><label for="ws" class="mut" style="min-width:110px">WLAN-Name</label><input type="text" id="ws" list="wn" autocomplete="off" autocapitalize="off" style="min-width:230px"><datalist id="wn"></datalist></div>
<div class="zeile"><label for="wp" class="mut" style="min-width:110px">Passwort</label><input type="password" id="wp" autocomplete="new-password" style="min-width:230px"></div>
<div class="zeile"><button class="v" onclick="wlan('senden')">WLAN ans Gerät senden</button><button onclick="zeige(3)">Überspringen</button></div>
<p id="wt" class="mut"></p></div></div>

<div class="k" id="st3" style="max-width:720px;display:none"><h2>4 · Gerät finden</h2>
<p id="g1" style="margin:8px 0">...</p>
<div class="zeile"><button class="v" id="g1w" onclick="zeige(4)" style="display:none">Weiter</button><button id="g1n" onclick="finden()">Noch einmal suchen</button><a href="/hilfe" target="_blank">Gerät nicht gefunden? Hilfe</a></div></div>

<div class="k" id="st4" style="max-width:720px;display:none"><h2>5 · Name und Ort</h2>
<div class="zeile"><label for="nm" class="mut" style="min-width:110px">Name</label><input type="text" id="nm" size="26" placeholder="z. B. Wohnzimmer"><button onclick="benennen()">Name speichern</button></div>
<div class="mut" style="margin-top:8px">Den <b>Ort</b> (Standort, Warnregion) kannst du von einem vorhandenen Gerät übernehmen, oder im Browser am neuen Gerät einstellen. <b>Tipp:</b> Trägst du Ort und DWD-Region im Browser ein, speichere. Plus ab 2.1.19 und Plus Europe ab 0.1.0-beta10 starten danach selbst neu und suchen den Ort. Bei älteren Versionen <b>starte das Gerät danach einmal neu</b> (Strom kurz trennen oder „Neu starten“ in der Weboberfläche), sonst zeigt es den Ort nicht an.</div>
<div class="zeile"><select id="qo"></select><button onclick="ortVorschau()">Vorschau</button><button class="v" id="oj" onclick="ortJa()" style="display:none">Ort übernehmen</button><a id="ob" target="_blank" href="#">Ort im Browser am Gerät einstellen</a></div>
<p id="o1" class="mut"></p>
<div class="zeile"><button class="v" onclick="zeige(5)">Weiter</button></div></div>

<div class="k" id="st5" style="max-width:720px;display:none"><h2>6 · Sicherung und fertig</h2>
<div class="mut">Control sichert die Einstellungen aller Geräte in deinem Sicherungsordner. Damit kannst du ein Gerät später wiederherstellen.</div>
<div class="zeile"><button class="v" onclick="sichern()">Einstellungen jetzt sichern</button><a id="fg" href="/">Zur Übersicht</a></div><p id="s1" class="mut"></p></div>
""", r"""
const TITEL=['Gerät','Firmware','WLAN','Finden','Name und Ort','Sicherung'];
let S={n:0,vorher:[],ip:'',host:'',name:'',pr:[]},pf=null,pw=null,pg=null;
function wlanAnsicht(){const x=S.pr.find(y=>y.key===$('p').value),alt=!!x&&x.wlan_usb===false;$('wAlt').style.display=alt?'block':'none';$('wUsb').style.display=alt?'none':'block'}
function zeige(n){S.n=n;for(let i=0;i<6;i++)$('st'+i).style.display=i===n?'block':'none';
 $('kopf').innerHTML=TITEL.map((t,i)=>'<span class="'+(i===n?'':'mut')+'" style="'+(i===n?'font-weight:600;border-bottom:2px solid var(--ac)':'')+'">'+(i+1)+' '+e(t)+'</span>').join('');
 if(n===2)wlanAnsicht();if(n===3)finden();if(n===4)ortInit();if(n===5&&S.ip)$('fg').href='/geraet?ip='+encodeURIComponent(S.ip)}
async function ports(){const j=await api('/api/installer/info');$('u').innerHTML=j.ports.length?j.ports.map(x=>'<option value="'+e(x.port)+'">'+e(x.text)+'</option>').join(''):'<option value="">kein Gerät gefunden</option>';return j}
async function start(){const j=await ports();if(!j.verfuegbar){$('m0').textContent='Esptool und pyserial fehlen. Starte WetterCube Control über das Programm oder die Starter-Datei (richtet sich selbst ein).'}
 S.pr=j.produkte;
 $('p').innerHTML=j.produkte.map(x=>'<option value="'+x.key+'">'+e(x.name)+'</option>').join('');
 try{S.vorher=(await api('/api/geraete')).map(d=>d.ip)}catch(x){}zeige(0)}
async function flashen(){const port=$('u').value;if(!port){$('m0').textContent='Kein USB-Anschluss gewählt.';return}
 if(!$('h').checked){$('m0').textContent='Bitte zuerst die Nutzungshinweise bestätigen.';return}
 const name=$('p').selectedOptions[0].textContent;if(!confirm('Firmware "'+name+'" (neueste Version) auf das Gerät an '+port+' aufspielen?'+($('l').checked?'\n\nACHTUNG: Der Flash wird vorher komplett gelöscht.':'\n\nEinstellungen und WLAN bleiben erhalten.')))return;
 $('m0').textContent='';try{await api('/api/installer/start',{aktion:'flashen',produkt:$('p').value,version:'',port:port,loeschen:$('l').checked,manuell:$('am').checked,haftung:true})}catch(x){$('m0').textContent=x.message;return}
 zeige(1);$('f1w').style.display='none';$('f1z').style.display='none';if(pf)clearInterval(pf);const f=async()=>{const j=await api('/api/installer/status');$('f1').textContent=(j.titel||'')+(j.laeuft?' ... '+(j.info||'bitte warten und das Gerät nicht abziehen'):(j.ok===true?' ✓ fertig. '+j.info:(j.ok===false?' ✗ '+j.info:'')));$('fl').textContent=j.log.join('\n');$('fbal').style.width=(j.prozent||0)+'%';
  if(!j.laeuft){clearInterval(pf);pf=null;$('f1w').style.display=j.ok?'inline-block':'none';$('f1z').style.display=j.ok?'none':'inline-block'}};await f();pf=setInterval(f,1000)}
async function wlan(a){const port=$('u').value;if(!port){$('wt').textContent='Kein USB-Anschluss gewählt (Schritt 1).';return}
 if(a==='senden'&&!$('ws').value.trim()){$('wt').textContent='Bitte den WLAN-Namen eintragen.';return}$('wt').textContent='...';
 try{await api('/api/wlan/start',{aktion:a,port:port,ssid:$('ws').value,passwort:$('wp').value})}catch(x){$('wt').textContent=x.message;return}
 if(pw)clearInterval(pw);const f=async()=>{const j=await api('/api/wlan/status');$('wt').textContent=j.text||'';
  if(j.netze&&j.netze.length)$('wn').innerHTML=j.netze.map(n=>'<option value="'+e(n.ssid)+'">'+e(n.ssid+' ('+n.rssi+' dBm)')+'</option>').join('');
  if(!j.laeuft){clearInterval(pw);pw=null;if(a==='senden'&&j.ok){$('wp').value='';const m=/^https?:\/\/([\w.\-]+)/.exec(j.adresse||'');S.host=m?m[1]:'';$('wt').textContent=j.text+' Weiter geht es mit dem Finden des Geräts.';setTimeout(()=>zeige(3),1500)}}};await f();pw=setInterval(f,800)}
async function finden(){$('g1w').style.display='none';$('g1').textContent='Control sucht das Gerät im Netz (das Gerät startet gerade neu, das dauert bis zu zwei Minuten) ...';let n=0;if(pg)clearInterval(pg);
 const f=async()=>{n++;try{if(S.host){try{await api('/api/geraete/hinzufuegen',{adresse:S.host})}catch(x){}}else if(n%6===1){await api('/api/suche',{})}
  const l=await api('/api/geraete');const neu=l.find(d=>!S.vorher.includes(d.ip)&&d.online!==false);
  if(neu){clearInterval(pg);pg=null;S.ip=neu.ip;S.name=neu.name;$('g1').innerHTML='<span style="color:var(--ok)">✓</span> Gefunden: <b>'+e(neu.name)+'</b> ('+e(neu.ip)+').';$('g1w').style.display='inline-block';return}
  const schon=S.host&&l.find(d=>d.ip===S.host&&d.online!==false);if(schon){clearInterval(pg);pg=null;S.ip=schon.ip;S.name=schon.name;$('g1').innerHTML='<span style="color:var(--ok)">✓</span> Gefunden: <b>'+e(schon.name)+'</b> ('+e(schon.ip)+').';$('g1w').style.display='inline-block';return}}catch(x){}
  if(n>40){clearInterval(pg);pg=null;$('g1').textContent='Noch nichts gefunden. Ist das Gerät im WLAN? Dann „Noch einmal suchen“ oder die Hilfe öffnen.'}};
 await f();if(pg===null&&S.ip)return;pg=setInterval(f,4000)}
async function ortInit(){$('nm').value=S.name||'';$('ob').href=S.ip?'http://'+S.ip+'/':'#';const l=await api('/api/geraete');$('qo').innerHTML='<option value="">Ort übernehmen von ...</option>'+l.filter(d=>d.ip!==S.ip&&d.online!==false).map(d=>'<option value="'+e(d.ip)+'">'+e(d.name)+'</option>').join('')}
async function benennen(){if(!S.ip){$('o1').textContent='Das Gerät wurde noch nicht gefunden.';return}try{await api('/api/geraete/aendern',{ip:S.ip,alias:$('nm').value});$('o1').textContent='Name gespeichert.'}catch(x){$('o1').textContent=x.message}}
async function ortVorschau(){if(!S.ip||!$('qo').value){$('o1').textContent='Bitte ein Gerät wählen, von dem der Ort übernommen wird.';return}$('oj').style.display='none';
 try{const r=await api('/api/kopieren',{quelle:$('qo').value,ziele:[S.ip],gruppen:['ort'],ausfuehren:false});const x=r[0];$('o1').innerHTML=x.aenderungen.length?x.aenderungen.map(a=>e(a.schluessel)+': '+e(a.alt)+' → <b>'+e(a.neu)+'</b>').join('<br>'):'Nichts zu ändern.';if(x.aenderungen.length)$('oj').style.display='inline-block'}catch(x){$('o1').textContent=x.message}}
async function ortJa(){if(!confirm('Den Ort auf das neue Gerät übernehmen? Das Gerät startet danach neu.'))return;try{const r=await api('/api/kopieren',{quelle:$('qo').value,ziele:[S.ip],gruppen:['ort'],ausfuehren:true});$('o1').textContent=r[0].text||'übernommen';$('oj').style.display='none'}catch(x){$('o1').textContent=x.message}}
async function sichern(){$('s1').textContent='sichere ...';try{const r=await api('/api/alle-sichern',{});$('s1').textContent=r.ergebnis.filter(x=>x.ok).length+' von '+r.ergebnis.length+' Geräten gesichert in '+r.ordner+'.'}catch(x){$('s1').textContent=x.message}}
start();
""")


# ── Einstellungen ────────────────────────────────────────────────────────────
EINSTELLUNGEN = seite("Einstellungen", "/einstellungen", r"""
<div class="k"><h2>Geräte</h2><div class="mut">Eigener Name, ausblenden oder von Hand hinzufügen (zum Beispiel aus einem anderen Netz). Automatisch gefundene Geräte lassen sich nur ausblenden.</div><table id="gt"></table>
 <div class="zeile"><input type="text" id="adr" placeholder="Adresse, z. B. 192.168.1.52 oder wettercube-fusion.local" style="min-width:300px"><button onclick="hinzu()">Gerät hinzufügen</button></div><div class="zeile"><label class="mut">Nicht erreichbare Geräte automatisch entfernen nach</label><input type="text" id="ae" size="3" onchange="aeSpeichern()"><span class="mut">Tagen (0 = nie)</span></div><div id="gm" class="mut"></div></div>
<div class="k"><h2>Mitteilungen am Rechner</h2><div class="mut">Welche Meldungen als Mitteilung erscheinen (Symbol in der Menüleiste bzw. Taskleiste muss laufen). Die Liste „Meldungen“ auf der Übersicht zeigt immer alles.</div>
 <label class="c"><input type="checkbox" id="m_warnung" onchange="mSpeichern()"> Wetterwarnungen und eigene Alarme</label><label class="c"><input type="checkbox" id="m_problem" onchange="mSpeichern()"> Probleme (Gerät offline, schwaches WLAN, wenig Speicher, veraltete Daten)</label><label class="c"><input type="checkbox" id="m_info" onchange="mSpeichern()"> Hinweise (Entwarnung, Gerät wieder da, neue Firmware, Sicherung fertig)</label></div>
<div class="k"><h2>Eigene Alarme</h2><div class="mut">Control meldet, sobald ein Wert die Grenze über- oder unterschreitet, und wenn er wieder in Ordnung ist. Zum Beispiel Frost: Temperatur unter 2 °C.</div><table id="at"></table>
 <div class="zeile"><select id="a_g"></select><select id="a_m"></select><select id="a_o"><option value="<">unter</option><option value=">">über</option></select><input type="text" id="a_w" placeholder="Grenze" size="6"><input type="text" id="a_n" placeholder="Name (z. B. Frost)" size="16"><button onclick="alarmNeu()">Hinzufügen</button></div><div id="am" class="mut"></div></div>
<div class="k"><h2>Automatische Sicherung</h2><div class="mut">Control sichert die Einstellungen aller Geräte regelmäßig nach <span id="so">…</span>. Geräte mit Web-Passwort werden übersprungen.</div>
 <div class="zeile"><select id="s_m" onchange="sSpeichern()"><option value="aus">aus</option><option value="taeglich">täglich</option><option value="woechentlich">wöchentlich</option></select><label class="mut">Tage behalten</label><input type="text" id="s_b" size="4" onchange="sSpeichern()"><button onclick="jetztSichern()">Jetzt sichern</button></div><div id="sm2" class="mut"></div></div>
<div class="k"><h2>Nach neuen Versionen suchen</h2><div class="mut">Aus (Standard): Control sucht nie von selbst. Updates prüfst du auf der Übersicht mit „Auf Updates prüfen“. Ein: Control schaut stündlich nach, ob es neue Firmware gibt (Abruf der Update-Listen bei github.io, beim Apex fragt das Gerät selbst seine Update-Quelle), zeigt „Neu: …“ an der Karte und meldet es.</div>
 <label class="c"><input type="checkbox" id="vs" onchange="vsSpeichern()"> Stündlich nach neuen Versionen suchen</label><div id="vs_m" class="mut"></div></div>
<div class="k"><h2>Protokolle sammeln</h2><div class="mut">Control liest das Diagnose-Log der Geräte ohnehin alle 5 Minuten. Eingeschaltet (Standard) werden die neuen Zeilen je Gerät und Tag im Ordner WetterCube-Protokolle in deinem Benutzerordner gespeichert, 30 Tage lang. Nichts verlässt den Rechner. Ansehen auf der Seite des Geräts.</div>
 <label class="c"><input type="checkbox" id="pr" onchange="prSpeichern()"> Protokolle der Geräte sammeln</label><div id="pr_m" class="mut"></div></div>
<div class="k"><h2>Beim Anmelden starten</h2><div class="mut" id="as_t">…</div><div class="zeile"><button id="as_b" onclick="autostart()" style="display:none"></button></div><div id="as_m" class="mut"></div></div>
""", r"""
let E={};
async function laden(){E=await api('/api/einstellungen');const g=await api('/api/geraete?alle=1');
 $('gt').innerHTML='<tr><th>Gerät</th><th>Eigener Name</th><th></th></tr>'+g.map(d=>'<tr><td>'+e(d.name_original)+'<br><span class="mut">'+e(d.ip)+'</span></td><td><input type="text" value="'+e(E.alias[d.ip]||'')+'" placeholder="'+e(d.name_original)+'" onchange="alias(\''+e(d.ip)+'\',this.value)"></td><td><button onclick="blende(\''+e(d.ip)+'\','+(!d.ausgeblendet)+')">'+(d.ausgeblendet?'Einblenden':'Ausblenden')+'</button>'+((d.manuell||d.online===false)?' <button data-ip="'+e(d.ip)+'" data-name="'+e(d.name)+'" onclick="entfernen(this.dataset.ip,this.dataset.name)">Entfernen</button>':'')+'</td></tr>').join('');
 ['warnung','problem','info'].forEach(a=>$('m_'+a).checked=!!E.mitteilungen[a]);
 $('a_g').innerHTML='<option value="*">alle Geräte</option>'+g.map(d=>'<option value="'+e(d.ip)+'">'+e(d.name)+'</option>').join('');
 $('a_m').innerHTML=Object.keys(E.alarm_metriken).map(k=>'<option value="'+k+'">'+e(E.alarm_metriken[k])+'</option>').join('');
 const namen={};g.forEach(d=>namen[d.ip]=d.name);
 $('at').innerHTML=E.alarme.length?'<tr><th>Alarm</th><th>Gerät</th><th>Bedingung</th><th></th></tr>'+E.alarme.map(a=>'<tr><td>'+e(a.name)+'</td><td>'+e(a.geraet==='*'?'alle':(namen[a.geraet]||a.geraet))+'</td><td>'+e(E.alarm_metriken[a.metrik])+' '+(a.op==='<'?'unter':'über')+' '+a.grenze+'</td><td><button onclick="alarmWeg(\''+e(a.id)+'\')">Löschen</button></td></tr>').join(''):'<tr><td class="mut">Noch keine eigenen Alarme.</td></tr>';
 $('ae').value=E.auto_entfernen_tage||0;$('vs').checked=!!E.versionssuche;$('pr').checked=E.protokolle!==false;$('s_m').value=E.auto_sichern.modus;$('s_b').value=E.auto_sichern.behalten;$('so').textContent=E.sicherungsordner;
 const as=E.autostart;$('as_t').textContent=as.verfuegbar?(as.aktiv?'Control startet beim Anmelden automatisch, damit der Verlauf lückenlos mitläuft.':'Control startet nicht automatisch. Mit Autostart läuft der Verlauf auch nach einem Neustart lückenlos weiter.'):'Autostart gibt es im Programm (App/exe), nicht beim Start aus dem Quellcode.';
 $('as_b').style.display=as.verfuegbar?'inline-block':'none';$('as_b').textContent=as.aktiv?'Autostart ausschalten':'Autostart einschalten'}
async function alias(ip,n){await api('/api/geraete/aendern',{ip:ip,alias:n});laden()}
async function blende(ip,an){await api('/api/geraete/aendern',{ip:ip,ausgeblendet:an});laden()}
async function aeSpeichern(){try{await api('/api/einstellungen',{auto_entfernen_tage:parseInt($('ae').value)||0});$('gm').textContent='gespeichert'}catch(x){$('gm').textContent=x.message}}
async function hinzu(){$('gm').textContent='prüfe ...';try{const j=await api('/api/geraete/hinzufuegen',{adresse:$('adr').value});$('gm').textContent='Hinzugefügt: '+j.name;$('adr').value='';laden()}catch(x){$('gm').textContent=x.message}}
async function mSpeichern(){await api('/api/einstellungen',{mitteilungen:{warnung:$('m_warnung').checked,problem:$('m_problem').checked,info:$('m_info').checked}})}
async function alarmNeu(){$('am').textContent='';try{await api('/api/alarme',{geraet:$('a_g').value,metrik:$('a_m').value,op:$('a_o').value,grenze:$('a_w').value.replace(',','.'),name:$('a_n').value});$('a_w').value='';$('a_n').value='';laden()}catch(x){$('am').textContent=x.message}}
async function alarmWeg(id){await api('/api/alarme',{loeschen:id});laden()}
async function prSpeichern(){try{await api('/api/einstellungen',{protokolle:$('pr').checked});$('pr_m').textContent='gespeichert'}catch(x){$('pr_m').textContent=x.message}}
async function vsSpeichern(){try{await api('/api/einstellungen',{versionssuche:$('vs').checked});$('vs_m').textContent='gespeichert'}catch(x){$('vs_m').textContent=x.message}}
async function sSpeichern(){try{await api('/api/einstellungen',{auto_sichern:{modus:$('s_m').value,behalten:parseInt($('s_b').value)||14}});$('sm2').textContent='gespeichert'}catch(x){$('sm2').textContent=x.message}}
async function jetztSichern(){$('sm2').textContent='sichere ...';try{const j=await api('/api/alle-sichern',{});$('sm2').innerHTML='Gespeichert in <b>'+e(j.ordner)+'</b>: '+j.ergebnis.map(x=>e(x.name)+(x.ok?' ✓':' ✗')).join(', ')}catch(x){$('sm2').textContent=x.message}}
async function autostart(){const an=!E.autostart.aktiv;if(!confirm(an?'Control beim Anmelden automatisch starten?':'Autostart ausschalten?'))return;try{await api('/api/autostart',{an:an});$('as_m').textContent=an?'Eingeschaltet. Gilt ab der nächsten Anmeldung.':'Ausgeschaltet.';laden()}catch(x){$('as_m').textContent=x.message}}
laden();
""")


# ── Kalibrierung (Sensorknoten) ──────────────────────────────────────────────
KALIBRIERUNG = seite("Kalibrierung", "/", r"""
<p class="mut"><a href="/">← Übersicht</a></p>
<div class="k"><h2 id="n">Kalibrierung</h2><div class="mut" id="sub"></div>
 <div class="mut" style="margin-top:6px">Vor jedem Speichern legt Control eine Sicherheitskopie der Einstellungen des Geräts an. Sensor mit Abstand zu ESP und Anzeige betreiben und erst messen, wenn er eingeschwungen ist. Reihenfolge: erst Temperatur, dann Feuchte, dann Druck.</div>
 <div id="m" class="mut" style="margin-top:6px"></div></div>
<div id="gr"></div>
""", r"""
const ip=q.get('ip')||'';let D=null;
const G={temp:{n:'Temperatur',e:'°C',k:'kt',o:'t_off',max:8,roh:s=>s.roh&&s.roh.temp,kor:s=>s.temp,ein:'roh'},
 feuchte:{n:'Luftfeuchte',e:'%',k:'kf',o:'f_off',max:5,roh:s=>s.roh&&s.roh.feuchte,kor:s=>s.feuchte,ein:'nach Temperatur-Umrechnung'},
 druck:{n:'Luftdruck (auf Meereshöhe)',e:'hPa',k:'kp',o:'p_off',max:5,roh:s=>s.roh&&s.roh.druck_nn,kor:s=>s.druck,ein:'auf Meereshöhe umgerechnet'}};
const f1=v=>v==null?'–':Number(v).toFixed(1);
function meld(t,ok){$('m').style.color=ok?'':'var(--rot,#c0392b)';$('m').textContent=t}
function kurve(g){const k=D.kurven[g];if(!k||!k.x||k.x.length<2)return'';const W=320,H=170,L=34,B=22,T=6,R=6,xs=k.x,ys=k.y;
 const lo=Math.min(xs[0],Math.min.apply(null,ys)),hi=Math.max(xs[xs.length-1],Math.max.apply(null,ys))||lo+1;const X=v=>L+(v-xs[0])/(xs[xs.length-1]-xs[0])*(W-L-R),Y=v=>H-B-(v-lo)/((hi-lo)||1)*(H-B-T);
 let s='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;max-width:420px;border:1px solid var(--rand);border-radius:8px">';
 s+='<line x1="'+X(xs[0])+'" y1="'+Y(xs[0])+'" x2="'+X(xs[xs.length-1])+'" y2="'+Y(xs[xs.length-1])+'" stroke="currentColor" stroke-dasharray="3 3" opacity=".4"/>';
 s+='<polyline fill="none" stroke="var(--akzent,#2b7fa3)" stroke-width="2.5" points="'+xs.map((x,i)=>X(x).toFixed(1)+','+Y(ys[i]).toFixed(1)).join(' ')+'"/>';
 (k.punkte||[]).forEach(p=>{s+='<circle cx="'+X(p[0]).toFixed(1)+'" cy="'+Y(p[1]).toFixed(1)+'" r="4" fill="none" stroke="var(--akzent,#2b7fa3)" stroke-width="2"/>'});
 return s+'</svg>'}
function zeichne(){const s=D.status,c=D.config;$('n').textContent='Kalibrierung: '+s.name;$('sub').textContent=ip+' · v'+s.version;let o='';
 for(const g of ['temp','feuchte','druck']){const d=G[g],P=c[d.k]||[];
  o+='<div class="k"><h2>'+d.n+'</h2><div class="mut">Jetzt: korrigiert '+f1(d.kor(s))+' '+d.e+' · Eingang '+f1(d.roh(s))+' '+d.e+' ('+e(d.ein)+')</div>';
  o+='<div class="zeile"><input type="number" step="0.1" id="ref-'+g+'" placeholder="Wert des Referenzgeräts ('+d.e+')" style="font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--rand);background:var(--feld);color:var(--tx)"><button onclick="punkt(\''+g+'\')">Referenzwert übernehmen</button></div>';
  if(!P.length)o+='<div class="zeile"><span class="mut">Keine Punkte, fester Offset:</span><input type="number" step="0.1" id="off-'+g+'" value="'+(c[d.o]||0)+'" style="width:90px;font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--rand);background:var(--feld);color:var(--tx)"><button onclick="offset(\''+g+'\')">Offset speichern</button></div>';
  else{o+='<table><tr><th>Eingang ('+e(d.ein)+')</th><th>Referenz</th><th></th></tr>'+P.map((p,i)=>'<tr><td><input type="number" step="0.01" id="pr-'+g+'-'+i+'" value="'+p[0]+'" style="width:100px"></td><td><input type="number" step="0.01" id="pf-'+g+'-'+i+'" value="'+p[1]+'" style="width:100px"></td><td><button onclick="weg(\''+g+'\','+i+')">Löschen</button></td></tr>').join('')+'</table>';
   o+='<div class="zeile"><button class="v" onclick="speichere(\''+g+'\')">Punkte speichern</button><button onclick="alleWeg(\''+g+'\')">Alle löschen</button><span class="mut">'+P.length+' von '+d.max+' Punkten</span></div>'}
  o+=kurve(g)+'</div>'}
 $('gr').innerHTML=o}
async function laden(){try{D=await api('/api/node/kalibrierung?ip='+encodeURIComponent(ip));zeichne()}catch(x){meld('Gerät nicht lesbar: '+x.message)}}
async function senden(werte,text){try{const r=await api('/api/node/kalibrierung',{ip:ip,werte:werte});meld(text+' Sicherheitskopie: '+r.kopie,true);await laden()}catch(x){meld(x.message)}}
function punkte(g){const d=G[g],n=((D.config[d.k])||[]).length,l=[];for(let i=0;i<n;i++){const a=parseFloat($('pr-'+g+'-'+i).value),b=parseFloat($('pf-'+g+'-'+i).value);if(isNaN(a)||isNaN(b)){meld('Bitte alle Felder ausfüllen.');return null}l.push([a,b])}return l}
function speichere(g){const l=punkte(g);if(l){const w={};w[G[g].k]=l;senden(w,'Gespeichert.')}}
function offset(g){const v=parseFloat($('off-'+g).value);if(isNaN(v)){meld('Bitte eine Zahl eingeben.');return}const w={};w[G[g].o]=v;senden(w,'Gespeichert.')}
function weg(g,i){const l=punkte(g);if(l){l.splice(i,1);const w={};w[G[g].k]=l;senden(w,'Punkt gelöscht.')}}
async function alleWeg(g){if(!(await dialogBestaetigen('Alle Punkte löschen?','<p>Alle Kalibrierpunkte dieser Größe werden gelöscht. Vorher wird eine Sicherheitskopie angelegt.</p>','Löschen','Abbrechen')))return;const w={};w[G[g].k]=[];senden(w,'Punkte gelöscht.')}
async function punkt(g){const v=parseFloat($('ref-'+g).value);if(isNaN(v)){meld('Bitte den Wert des Referenzgeräts eintragen.');return}
 try{const r=await api('/api/node/punkt',{ip:ip,groesse:g,ref:v});meld('Punkt angelegt. Sicherheitskopie: '+r.kopie,true);await laden()}catch(x){meld(x.message)}}
laden();setInterval(()=>{if(!document.hidden&&!document.activeElement.matches('input'))laden()},8000);
""")
