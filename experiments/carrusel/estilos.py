"""Style themes for build.py (--estilo=NAME): CSS laid over the base look plus a few decorations, same copy and checks.

talavera    the site's Talavera look (web/contamina.html): cream paper, cobalt double rules and tile bands, Iowan italic
expediente  an investigator's folder: manila background, taped and clipped oficios, typed notes, red marker
cartel      a street poster: the site's yellow (--mark) and cobalt, Futura condensed, pasted-up documents, halftone
"""

TINTA, COBALTO, CREMA, AMARILLO = "#14213d", "#1d3f9e", "#fbfaf6", "#f2c84b"

# the site's tile (web/contamina.html --tile), drawn bigger
TILE = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24'%3E%3Cpath "
        "d='M12 2l4 10-4 10-4-10z M2 12l10-4 10 4-10 4z' fill='%231d3f9e'/%3E%3C/svg%3E\")")
CLIP = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='170' viewBox='0 0 60 170'%3E"
        "%3Cpath d='M22 46V128a14 14 0 0 0 28 0V30a20 20 0 0 0-40 0V122' fill='none' stroke='%237d838e' stroke-width='7' "
        "stroke-linecap='round'/%3E%3C/svg%3E\")")
TRAZO = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 20' preserveAspectRatio='none'%3E"
         "%3Cpath d='M3 13C40 6 80 9 110 11S170 8 197 7' fill='none' stroke='%23c8281c' stroke-width='7' stroke-linecap='round'/%3E%3C/svg%3E\")")

CSS = {
    "talavera": f"""
html,body{{background:{CREMA}}}
body{{color:{TINTA};font-family:"Iowan Old Style",Palatino,Georgia,serif}}
.plain .tint{{background:radial-gradient(130% 90% at 50% 0%,#fffdf8 0%,{CREMA} 55%,#f1eee4 100%)}}
.banda{{position:absolute;left:0;right:0;height:30px;background:{TILE} center/30px 30px repeat-x}}
.banda.arriba{{top:0}}.banda.abajo{{bottom:0}}
.marco{{position:absolute;inset:44px 30px;border:7px double {COBALTO};pointer-events:none}}
.frame{{padding:84px 82px 76px}}
.top{{font-family:"Iowan Old Style";font-style:italic;font-weight:400;font-size:32px;color:{COBALTO}}}
.top .n{{font-style:normal;font-variant:small-caps;letter-spacing:.08em;opacity:1;color:#4f5b7a}}
.kicker{{font-family:"Iowan Old Style";font-style:italic;font-weight:400;font-size:34px;line-height:1.25;color:#4f5b7a}}
.kicker:before{{content:"";display:inline-block;width:26px;height:26px;margin:0 14px -2px 0;background:{TILE} center/26px 26px}}
.titular{{font-family:"Iowan Old Style";font-style:italic;font-weight:400;font-size:84px;line-height:1.04;color:{TINTA};text-shadow:none;letter-spacing:-.01em}}
.cifra{{font-family:"Iowan Old Style";font-weight:900;font-size:180px;color:{COBALTO};letter-spacing:-.03em}}
.cifra.long{{font-size:132px}}
.alarm{{color:{TINTA};font-weight:700;background:linear-gradient(transparent 58%,{AMARILLO} 58%,{AMARILLO} 94%,transparent 94%);-webkit-box-decoration-break:clone}}
.acc{{color:{COBALTO}}}
.cifra .alarm,.url .alarm{{background:none;color:inherit}}
.texto,.texto.small{{font-size:33px;line-height:1.36;font-weight:400;opacity:1;color:{TINTA};text-shadow:none}}
.doc{{background:#fff;border:5px double {COBALTO};border-radius:2px;transform:rotate(-.6deg);box-shadow:0 14px 30px rgba(20,33,61,.16)}}
.docw:nth-child(2) .doc{{transform:rotate(.5deg)}}
.hl{{background:rgba(242,200,75,.6)}}
.docet{{color:{COBALTO};font-family:"Iowan Old Style";font-style:italic;text-transform:none;letter-spacing:0;font-size:28px}}
.foot{{color:#4f5b7a;opacity:1;font-size:18px}}
.foot .site{{color:{COBALTO};font-style:italic}}
.acts{{font-weight:400;font-size:36px}}
.acts li:before{{content:"◆  ";color:{COBALTO};font-size:.7em;vertical-align:.12em}}
.url{{font-family:"Iowan Old Style";font-style:italic;font-weight:700;color:{COBALTO}}}
.bio{{background:{COBALTO};color:#fff;border-radius:4px;font-family:"Avenir Next"}}
.bio b{{font-family:"Iowan Old Style";font-style:italic}}
.pie{{color:#4f5b7a;opacity:1}}
.zoom{{border:6px solid #fff;box-shadow:0 0 0 3px {COBALTO},0 8px 20px rgba(20,33,61,.3)}}
.phone{{box-shadow:0 30px 70px rgba(20,33,61,.35)}}
.conf .tint,.heavy .tint{{background:linear-gradient(180deg,rgba(12,19,40,.55) 0%,rgba(12,19,40,.2) 25%,rgba(12,19,40,.35) 45%,rgba(12,19,40,.88) 68%,rgba(12,19,40,.96) 100%)}}
.conf,.heavy{{color:#fff}}
.conf .titular,.heavy .titular,.conf .texto,.heavy .texto{{color:#fff;text-shadow:0 2px 14px rgba(0,0,0,.5)}}
.conf .kicker,.heavy .kicker,.conf .foot,.heavy .foot,.conf .top .n,.heavy .top .n{{color:#dfe5f7}}
.conf .cifra,.heavy .cifra{{color:{AMARILLO}}}
.conf .top,.heavy .top,.conf .foot .site,.heavy .foot .site{{color:#fff}}
.conf .marco,.heavy .marco{{border-color:#fbfaf6}}
.conf .banda,.heavy .banda{{background-color:{CREMA}}}
""",
    "expediente": f"""
html,body{{background:#d5ba85}}
body{{color:#1f1a12}}
.plain .tint{{background:
 radial-gradient(120% 80% at 25% 10%,rgba(255,250,235,.38) 0%,transparent 60%),
 repeating-linear-gradient(97deg,rgba(120,86,30,.035) 0 2px,transparent 2px 7px),
 repeating-linear-gradient(8deg,rgba(255,255,255,.04) 0 1px,transparent 1px 5px),
 linear-gradient(180deg,#dcc392 0%,#d2b47c 100%)}}
.pestana{{position:absolute;top:0;right:96px;width:400px;height:64px;background:#c9a96d;border-radius:0 0 16px 16px;
 box-shadow:inset 0 -3px 0 rgba(0,0,0,.08);font-family:"American Typewriter";font-size:24px;letter-spacing:.12em;
 color:#4a3a1e;display:flex;align-items:center;justify-content:center}}
.top{{font-family:"American Typewriter";font-weight:600;font-size:28px;color:#2a2418}}
.top .n{{display:none}}
.frame{{padding:96px 76px 60px}}
.stack{{gap:24px}}
.kicker{{align-self:flex-start;font-family:"American Typewriter";font-weight:400;font-size:29px;line-height:1.35;color:#1f1a12;
 background:#fffdf4;padding:14px 22px;transform:rotate(-.8deg);box-shadow:0 3px 8px rgba(60,40,10,.18);max-width:100%}}
.titular{{font-family:"Avenir Next Condensed";font-weight:800;font-size:80px;line-height:1.02;color:#1f1a12;text-shadow:none}}
.alarm{{color:#b3231a;background:{TRAZO} 0 100%/100% .26em no-repeat;padding-bottom:.06em;-webkit-box-decoration-break:clone}}
.acc{{color:#1f1a12;font-style:italic}}
.cifra{{align-self:flex-start;font-family:"Marker Felt";font-weight:700;font-size:170px;color:#b3231a;line-height:1;padding:10px 40px 18px;
 border:7px solid #c8281c;border-radius:58% 42% 55% 45%/52% 60% 40% 48%;transform:rotate(-2.5deg);letter-spacing:0}}
.cifra.long{{font-size:120px}}
.cifra .alarm{{background:none}}
.sitio .cifra{{font-size:104px;white-space:nowrap;padding:6px 30px 12px}}
.texto,.texto.small{{font-family:"American Typewriter";font-size:30px;line-height:1.42;font-weight:400;opacity:1;color:#1f1a12;text-shadow:none}}
.docw{{position:relative}}
.docw:before{{content:"";position:absolute;z-index:3;left:-24px;top:-40px;width:44px;height:126px;background:{CLIP} center/contain no-repeat;transform:rotate(-8deg)}}
.doc{{position:relative;transform:rotate(-1.6deg);box-shadow:0 2px 0 rgba(0,0,0,.04),0 22px 40px rgba(60,40,10,.35);border-radius:2px}}
.doc:after{{content:"";position:absolute;right:46px;top:-18px;width:150px;height:40px;background:rgba(255,250,225,.6);transform:rotate(4deg);box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.docw:nth-child(2) .doc{{transform:rotate(1.2deg)}}
.hl{{background:rgba(255,226,64,.62)}}
.docet{{color:#4a3a1e;font-family:"American Typewriter"}}
.foot{{font-family:"American Typewriter";color:#3d3220;opacity:.85;font-size:17px}}
.foot .site{{font-size:22px}}
.acts{{font-family:"American Typewriter";font-weight:400;font-size:33px}}
.acts li:before{{content:"✓ ";color:#b3231a;font-family:"Marker Felt"}}
.url{{font-family:"Avenir Next Condensed";color:#1f1a12;background:{TRAZO} 0 100%/100% .2em no-repeat;padding-bottom:.08em}}
.bio{{background:#1f1a12;color:#fffdf4;border-radius:4px}}
.pie{{font-family:"American Typewriter";opacity:.8}}
.phone{{transform:translateY(-50%) rotate(5deg);box-shadow:0 30px 60px rgba(60,40,10,.45)}}
""",
    "cartel": f"""
html,body{{background:{AMARILLO}}}
body{{color:{TINTA};font-family:Futura,"Avenir Next",sans-serif}}
.stack{{gap:22px}}
.plain .tint{{background:{AMARILLO}}}
.puntos{{position:absolute;right:-120px;bottom:-120px;width:760px;height:760px;
 background:radial-gradient(circle,{COBALTO} 34%,transparent 37%) 0 0/24px 24px;
 -webkit-mask:radial-gradient(circle at 100% 100%,#000 0%,rgba(0,0,0,.6) 30%,transparent 66%);opacity:.32}}
.top{{font-family:Futura;font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-size:28px}}
.top .n{{opacity:1;background:{TINTA};color:{AMARILLO};font-size:24px;padding:6px 16px;border-radius:40px;letter-spacing:.04em}}
.kicker{{font-family:Futura;font-weight:500;font-size:27px;line-height:1.6;color:{AMARILLO}}}
.kicker>span.k{{background:{TINTA};padding:4px 14px;-webkit-box-decoration-break:clone}}
.titular{{font-family:Futura;font-stretch:condensed;font-weight:800;font-size:76px;line-height:1.05;text-transform:uppercase;color:{TINTA};text-shadow:none;letter-spacing:-.005em}}
.alarm{{color:#fff;background:{COBALTO};padding:0 .1em;-webkit-box-decoration-break:clone}}
.acc{{color:{COBALTO}}}
.cifra{{font-family:Futura;font-stretch:condensed;font-weight:800;font-size:190px;line-height:.86;color:{COBALTO};text-transform:uppercase;transform:rotate(-2deg);transform-origin:left;margin-top:12px}}
.cifra.long{{font-size:150px}}
.cifra .alarm{{background:none;color:inherit;padding:0}}
.texto,.texto.small{{font-family:Futura;font-weight:500;font-size:29px;line-height:1.34;opacity:1;color:{TINTA};text-shadow:none}}
.doc{{background:#fff;border:5px solid {TINTA};border-radius:0;transform:rotate(1.2deg);box-shadow:14px 14px 0 {TINTA}}}
.docw:nth-child(2) .doc{{transform:rotate(-1deg)}}
.hl{{background:rgba(242,200,75,.8)}}
.docet{{color:{TINTA}}}
.foot{{color:{TINTA};opacity:.8;font-size:17px;font-family:"Avenir Next"}}
.foot .site{{font-family:Futura;text-transform:uppercase;letter-spacing:.06em;font-size:22px}}
.acts{{font-family:Futura;font-weight:500;font-size:34px}}
.url{{font-family:Futura;font-stretch:condensed;font-weight:800;color:{TINTA}}}
.bio{{background:{TINTA};color:{AMARILLO};border-radius:0;font-family:Futura}}
.phone{{transform:translateY(-50%) rotate(3deg);box-shadow:16px 16px 0 {TINTA}}}
.t-cierre,.t-cierre html{{background:{COBALTO}}}
.t-cierre .tint{{background:{COBALTO}}}
.t-cierre .puntos{{background:radial-gradient(circle,{AMARILLO} 34%,transparent 37%) 0 0/24px 24px;opacity:.28}}
.t-cierre,.t-cierre .titular,.t-cierre .foot{{color:#fff}}
.t-cierre .url{{color:{AMARILLO}}}
.t-cierre .acts li:before{{color:{AMARILLO}}}
.t-cierre .top .n{{background:{AMARILLO};color:{TINTA}}}
""",
}


def nombres():
    return sorted(CSS)


def css(estilo):
    return CSS[estilo] if estilo else ""


def deco(estilo, i, total):
    if estilo == "talavera":
        return '<div class="banda arriba"></div><div class="banda abajo"></div><div class="marco"></div>'
    if estilo == "expediente":
        return f'<div class="pestana">EXPEDIENTE · HOJA {i}/{total}</div>'
    if estilo == "cartel":
        return '<div class="puntos"></div>'
    return ""
