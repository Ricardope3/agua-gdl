#!/usr/bin/env python3
"""Cuts of official documents and the paper cards that show them on the «No cuadra» pages (/zapopan, /tlajomulco).

    python3 pipelines/documentos.py            cut the images with pdftoppm (and cwebp) and write each card into its page
    python3 pipelines/documentos.py --check    fail if a card or photo in a page is stale, an image is missing or of
                                               another size, or an image in web/img/documentos/ belongs to none

A card is written between `<!-- documento:ID -->` and `<!-- /documento:ID -->` in its page; the figure and caption
around it are edited by hand. Boxes are pixels at 200 dpi on the page image (`boxes.swift` in experiments/carrusel
gives text boxes; pad about 8 px). Alt text and quotes give the words as printed: check each «i», «u» and «o» that
could carry an accent at 1200 dpi against a plain one in the same line, since at 200-400 dpi a slanted acute passes
for a dot («expondría», «Fiscalía», 27 Nov 2026). A cut leaves out signatures, initials, handwritten words and people's names, and stamps where
the text allows; a stamp or stroke that crosses a quoted line stays, in colour, and the caption says so. A sentence
that wraps is cut line by line, in order. A card's lines share one scale, so its widest cut fills the card and the
type is the same size on every line; the letterhead shows at `membrete` times that scale. A ring marks a point of a cut
(x, y, r in its pixels) with our own tag, centred dx, dy cut pixels away: a scanned chart's labels are too small to
read on a phone.

A photograph (FOTOS) is cut whole, in colour, into a WebP, and its `<img>` is written between `<!-- foto:ID -->` and
`<!-- /foto:ID -->`; the figure, caption and link around it are edited by hand. Its box leaves out the page's heading
(the caption gives its words as written) and any pen mark. Regenerating needs cwebp (`brew install webp`).

The PDFs come from web/datos/ (published) or from research/ in the main checkout: one not published yet, or one that
never will be because of private data (RESEARCH says which).
"""
import html
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web/img/documentos"
DPI = 200

PDFS = {
    "zapopan-978": "web/datos/zapopan-respuesta-140292426004978.pdf",
    "zapopan-980": "web/datos/zapopan-respuesta-140292426004980.pdf",
    "zapopan-981": "web/datos/zapopan-respuesta-140292426004981.pdf",
    "pcyb-089": "web/datos/pcyb-respuesta-ut-089-2026.pdf",
    "pcyb-091": "web/datos/pcyb-respuesta-ut-091-2026.pdf",
    "tlaj-1740": "web/datos/tlajomulco-respuesta-140290426001765.pdf",
    "siapa-dg135": "web/datos/siapa-dg-135-2026.pdf",
    "tlaj-0127": "web/datos/tlajomulco-dapih-0127-01-2026.pdf",
    "tlaj-0331": "web/datos/tlajomulco-dapih-0331-01-2026.pdf",
}
# Where each one sits in research/ (gitignored, main checkout only) until it is published in web/datos/.
RESEARCH = {
    "zapopan-980": "research/transparency/extracted/140292426004980/r6787.pdf",
    "tlaj-1740": "research/transparency/extracted/tlajomulco-1740-2026/1740-2026.pdf",
    "siapa-dg135": "research/transparency/extracted/tlajomulco-1740-2026/annexes-2026-11-24/DG-135-2026 Siapa.pdf",
    "tlaj-0127": "research/transparency/extracted/tlajomulco-1740-2026/annexes-2026-11-24/DAPIH-0127-01-2026 reporte descarga.pdf",
    "tlaj-0331": "research/transparency/extracted/tlajomulco-1740-2026/annexes-2026-11-24/DAPIH0331-012026.pdf",
    # Never published whole, so not in PDFS: SIAPA's p. 1 names the requester, and PROEPA's pages aren't all checked for
    # private data. Only these cuts appear.
    "siapa-1178": "research/transparency/extracted/140279226001178/respuesta exp. 1098-2026.pdf",
    "proepa-172": "research/transparency/extracted/140276526000172/140276526000172/4 Una combinación de las anteriores/Resp PNT 172-26.pdf",
    # Never published whole either: p. 1 names the requester below the letterhead (cut above it).
    "siapa-1270": "research/transparency/extracted/140279226001270/140279226001270/2 Negativa por ser reservada/exp. 1183-2026.pdf",
}

SKIP = "…"
# Letterheads shared by several cards: the issuer's logo and the oficio's number.
DG135 = "siapa-dg135"
T0127, T0331, T1740 = "tlaj-0127", "tlaj-0331", "tlaj-1740"
S1178, P172, S1270 = "siapa-1178", "proepa-172", "siapa-1270"


def cut(pdf, page, x, y, w, h, texto="", marca=True, color=False, escala=1.0, anillos=()):
    """One cut: `texto` is its alt text (the printed words, or what a chart shows); `anillos` are (x, y, r, tag, dx, dy)."""
    return dict(pdf=pdf, page=page, box=(x, y, w, h), texto=texto, marca=marca, color=color, escala=escala, anillos=anillos)


def logo(pdf, page, x, y, w, h, texto=""):
    return cut(pdf, page, x, y, w, h, texto, marca=False, color=True)


CARDS = {
    # Oficio 11000000/CER.CIU/2026/0878, Cercanía Ciudadana, 6 Nov 2026: answer to 140292426004981, p. 5.
    "zapopan-reportes": dict(page="zapopan", membrete=0.55, cuts=[
        logo("zapopan-981", 5, 130, 135, 325, 215),
        logo("zapopan-981", 5, 990, 280, 575, 135, "Oficio 11000000/CER.CIU/2026/0878"),
    ], lines=[
        cut("zapopan-981", 5, 1017, 1869, 539, 44, "se encontró un total de 9,828 reportes por"),
        cut("zapopan-981", 5, 99, 1910, 878, 46, "falta de agua, con corte al 04 de noviembre de la presente anualidad,"),
    ]),
    # Oficio 011300/2026/0150, Protección Civil y Bomberos, 12 Nov 2026: answer UT-091, p. 4.
    "zapopan-pipas": dict(page="zapopan", membrete=0.5, cuts=[
        logo("pcyb-091", 4, 140, 52, 280, 295),
        logo("pcyb-091", 4, 1230, 284, 318, 98, "Dirección de Planificación, oficio 011300/2026/0150"),
    ], lines=[
        cut("pcyb-091", 4, 828, 1170, 779, 51, "la cantidad de pipas participantes durante cada jornada,"),
        cut("pcyb-091", 4, 395, 1916, 1010, 126, "La línea de pipas por día de la gráfica oficial, del 15 de octubre al 3 de noviembre: 11 el 19 de octubre, 34 el 27 de octubre", marca=False, color=True,
            anillos=[(257, 82, 26, "11 · 19 oct", 0, -54), (634, 24, 24, "34 · 27 oct", 0, 60)]),
    ]),
    # The same oficio, p. 5 (a continuation page with no number of its own): the table and the count at 3 Nov.
    "zapopan-36-pipas": dict(page="zapopan", membrete=0.5, cuts=[
        logo("pcyb-091", 4, 140, 52, 280, 295),
        logo("pcyb-091", 4, 1230, 284, 318, 98, "Dirección de Planificación, oficio 011300/2026/0150"),
    ], lines=[
        cut("pcyb-091", 5, 236, 445, 1371, 42, "Asimismo, se proporciona la relación de pipas participantes, desglosada por dependencia u", marca=False),
        cut("pcyb-091", 5, 232, 488, 1297, 42, "organismo de procedencia, conforme a los registros generales de seguimiento del operativo.", marca=False),
        cut("pcyb-091", 5, 276, 549, 1276, 317, "Tabla: dependencia y cantidad de pipas. Protección Civil y Bomberos Zapopan, 2; Agua Potable y "
            "Alcantarillado, 3; Parques y Jardines, 6; SIAPA, 25", marca=False),
        SKIP,
        cut("pcyb-091", 5, 236, 1336, 1375, 43, "Al corte de 3 de noviembre del presente, se cuenta con 36 pipas en servicio, bajo un esquema de"),
    ]),
    # Oficio 11000000/CER.CIU/2026/0876, Cercanía Ciudadana, 6 Nov 2026: answer to 140292426004978, pp. 7, 11 and 8.
    "zapopan-cisternas": dict(page="zapopan", membrete=0.5, cuts=[
        logo("zapopan-978", 7, 135, 135, 335, 225),
        logo("zapopan-978", 7, 980, 292, 590, 90, "Oficio 11000000/CER.CIU/2026/0876"),
    ], lines=[
        cut("zapopan-978", 7, 109, 1781, 391, 43, "listado de cisternas instaladas,"),
        SKIP,
        cut("zapopan-978", 11, 50, 483, 425, 142, "47 MIRAMAR, 48 CORDILLERAS", marca=False, escala=0.8),
        cut("zapopan-978", 11, 50, 625, 425, 66, "49 LOS CAJETES", escala=0.8),
        SKIP,
        cut("zapopan-978", 8, 113, 619, 676, 50, "en los archivos que obran en la Coordinación General,"),
        cut("zapopan-978", 8, 790, 619, 779, 50, "no se localizaron bitácoras, hojas de servicio, vales o registros"),
        cut("zapopan-978", 8, 113, 666, 592, 48, "de viaje de las pipas que llenaron las cisternas"),
    ]),
    # Oficio 011300/2026/0148, Protección Civil y Bomberos, 12 Nov 2026: answer UT-089, pp. 5 and 6.
    "zapopan-hospitales": dict(page="zapopan", membrete=0.5, cuts=[
        logo("pcyb-089", 5, 125, 126, 295, 298),
        logo("pcyb-089", 5, 1210, 383, 320, 95, "Dirección de Planificación, oficio 011300/2026/0148"),
    ], lines=[
        cut("pcyb-089", 6, 340, 1758, 995, 43, "Hospitales: Sin atenciones registradas"),
        cut("pcyb-089", 6, 340, 1801, 995, 38, "Espacios Públicos: Centro Comunitario N°3 - 09/11/2026", marca=False),
        cut("pcyb-089", 6, 340, 1836, 995, 35, "Escuelas: Centro Escolar Juan Mateo - 20/10/2026", marca=False),
    ]),
    "zapopan-75-pcyb": dict(page="zapopan", membrete=0.5, cuts=[
        logo("pcyb-089", 5, 125, 126, 295, 298),
        logo("pcyb-089", 5, 1210, 383, 320, 95, "Dirección de Planificación, oficio 011300/2026/0148"),
    ], lines=[
        cut("pcyb-089", 5, 232, 1177, 938, 41, "de las 75 colonias identificadas con mayor afectación, precisando que"),
        cut("pcyb-089", 5, 1167, 1172, 429, 40, "dicha información fue generada"),
        cut("pcyb-089", 5, 236, 1217, 595, 47, "por la Coordinación de Cercanía Ciudadana"),
        SKIP,
        # The printed line tilts about 12 px across the cut: 1251–1292 holds it whole and nothing of the lines around it.
        cut("pcyb-089", 5, 420, 1251, 1180, 42, "siendo esta la dependencia responsable de su elaboración, integración y actualización."),
    ]),
    # Oficio 11000000/CER.CIU/2026/0907, Cercanía Ciudadana, 17 Nov 2026: answer to 140292426004980, p. 6.
    "zapopan-75-cercania": dict(page="zapopan", membrete=0.5, cuts=[
        logo("zapopan-980", 6, 143, 135, 165, 225),
        logo("zapopan-980", 6, 1005, 286, 575, 135, "Oficio 11000000/CER.CIU/2026/0907"),
    ], lines=[
        cut("zapopan-980", 6, 212, 1265, 1086, 50, "1. El listado o los documentos en que consten las 211 colonias y las 75 más afectadas", marca=False),
        SKIP,
        cut("zapopan-980", 6, 509, 1831, 584, 50, "no se localizó información respecto a los puntos"),
        cut("zapopan-980", 6, 1092, 1831, 484, 50, "señalados y descritos anteriormente al"),
        cut("zapopan-980", 6, 116, 1873, 812, 47, "no tratarse de funciones inherentes a esta Coordinación General"),
    ]),
    # Oficio 011300/2026/0148 again, p. 6: the polygon calendar it hands over, then (item 2) that the calendarización
    # isn't its competence. The first line begins under the logo, so its cut starts at «se proporciona»; the line above
    # «la información» touches it, so that cut starts at 1210 (two rows of descenders at its left, none of the tops at
    # its right lost).
    "zapopan-calendario": dict(page="zapopan", membrete=0.5, cuts=[
        logo("pcyb-089", 5, 125, 126, 295, 298),
        logo("pcyb-089", 5, 1210, 383, 320, 95, "Dirección de Planificación, oficio 011300/2026/0148"),
    ], lines=[
        cut("pcyb-089", 6, 900, 397, 630, 40, "se proporciona el calendario de polígonos de"),
        cut("pcyb-089", 6, 228, 439, 507, 34, "distribución de agua potable vigente:"),
        cut("pcyb-089", 6, 226, 489, 1296, 592, "Tabla con las columnas «Día de atención», «Polígono» y «Principales colonias de referencia por "
            "polígono». Sábado, A: Ciudad Granja, Santa María del Pueblito. Domingo, B: Vallarta Patria, Camino Real, Prados "
            "Vallarta, Jardines de San Ignacio, Residencial Cordilleras, la Estancia. Lunes, C: Arcos de Guadalupe, Plaza "
            "Guadalupe, Tepeyac Casino, Mirador del Sol, Haciendas del Tepeyac. Martes, D: Jardines del Sol, Colli Urbano, "
            "Paseos del Sol, Victoria, Loma Bonita. Miércoles, E: Las Águilas, Pinar de la Calma, Agua Blanca Industrial, El "
            "Campanario. Jueves, F: La Floresta del Colli, Lomas de la Primavera, Arenales Tapatíos, Villas de la Primavera, "
            "Fracc. Citala, El Fortín, Monte Verde, Puerta del Bosque, Misión Floresta, Misión Santa Ana, La Haciendita, Los "
            "Pinos Campestre. Viernes, G: Lomas del Colli, La Gloria del Colli, Paseos del Colli, Arenales Tapatíos, Miramar",
            marca=False),
        SKIP,
        cut("pcyb-089", 6, 588, 1210, 948, 33, "la información de su interés en lo relativo a criterios de prioridad,", marca=False),
        cut("pcyb-089", 6, 238, 1245, 1298, 35, "calendarización del reparto y la duración del operativo no forma parte de nuestras competencias, por"),
        cut("pcyb-089", 6, 238, 1279, 1116, 36, "lo que se estima que quien pudiera contar con información al respecto es el SIAPA,"),
    ]),
    # Oficio 02050000/2026/7939, Dirección de Transparencia y Buenas Prácticas, 17 Nov 2026: answer to 140292426004978, p. 2.
    "zapopan-primera-fase": dict(page="zapopan", membrete=0.45, cuts=[
        logo("zapopan-978", 2, 150, 82, 535, 275),
        logo("zapopan-978", 2, 830, 92, 790, 158, "Oficio 02050000/2026/7939"),
    ], lines=[
        cut("zapopan-978", 2, 366, 1511, 861, 43, "cuya logística se plantea que en una primera fase sea la siguiente:"),
        SKIP,
        cut("zapopan-978", 2, 500, 1774, 645, 43, "Se llevarán a cabo las gestiones correspondientes"),
        cut("zapopan-978", 2, 1144, 1774, 458, 43, "para lograr materializar un sistema"),
        cut("zapopan-978", 2, 500, 1813, 534, 41, "de 45 pipas y 100 cisternas comunitarias"),
    ]),
}

MEMBRETE = {
    DG135: [logo(DG135, 1, 580, 50, 425, 135), logo(DG135, 1, 890, 163, 588, 82, "Oficio no. DG-135/2026. Guadalajara, Jalisco a 06 de marzo del 2026")],
    T0127: [logo(T0127, 1, 1183, 109, 338, 103), logo(T0127, 1, 1062, 206, 456, 48, "Oficio: DAPIH/0127-01/2026")],
    T0331: [logo(T0331, 3, 1170, 125, 325, 105), logo(T0331, 3, 1070, 236, 448, 46, "Oficio: DAPIH/0331-01/2026")],
    T1740: [logo(T1740, 1, 1160, 110, 335, 112), logo(T1740, 1, 1150, 242, 385, 52, "Oficio DTRC/1740/2026")],
}
CARDS.update({
    # SIAPA, oficio DG-135/2026 to Tlajomulco, 6 Mar 2026, delivered by Tlajomulco for 140290426001765: p. 2.
    "tlaj-limite": dict(page="tlajomulco", membrete=0.6, cuts=MEMBRETE[DG135], lines=[
        cut(DG135, 2, 1005, 583, 517, 40, "un indicador clave de contaminación", marca=False),
        cut(DG135, 2, 131, 624, 1391, 36, "en el agua, a considerar, es el nivel de nitrógeno amoniacal aportado por estas descargas que han", marca=False),
        cut(DG135, 2, 131, 661, 1392, 37, "ocasionado un incremento perjudicial en el influente que es enviado a la planta potabilizadora no. 1,", marca=False),
        cut(DG135, 2, 131, 699, 1391, 42, "cabe señalar que el límite permisible establecido por la norma es de 0.5 mg/l, sin embargo, ha"),
        cut(DG135, 2, 132, 741, 592, 40, "alcanzado más de 3.50 mg/l. (ver figura 1)."),
    ]),
    # Anexo 01, p. 5: Gráfico 1. The rings and tags are ours, at the markers for July 2024 and January 2026.
    "tlaj-grafica": dict(page="tlajomulco", membrete=0.6, cuts=MEMBRETE[DG135], lines=[
        cut(DG135, 5, 105, 242, 1411, 42, "A continuación, se presentan los valores promedio mensuales de nitrógeno amoniacal del agua", marca=False),
        cut(DG135, 5, 106, 285, 391, 41, "cruda que ingresa a la PP1:", marca=False),
        cut(DG135, 5, 110, 372, 1405, 1080, "Gráfico 1 del oficio: nitrógeno amoniacal, valor promedio mensual en el influente de la planta 1, "
            "de enero de 2020 a febrero de 2026. En nuestra lectura, de 0.10 a 0.27 mg/L de 2020 a 2022, 2.18 en julio de 2024 y 3.62 en enero de 2026",
            marca=False, color=True, anillos=[(1052, 481, 30, "2.18 · julio de 2024", 0, -66), (1336, 176, 30, "3.62 · enero de 2026", -270, 0)]),
        cut(DG135, 5, 119, 1466, 1384, 39, "Gráfico 1. Comparativo de valores promedio de concentración de nitrógeno amoniacal en miligramos por", marca=False),
        cut(DG135, 5, 368, 1505, 886, 35, "litro (mg/l) en el influente de la planta potabilizadora no. 1 Miravalle.", marca=False),
    ]),
    # Anexo 01, pp. 4 and 6.
    "tlaj-planta": dict(page="tlajomulco", membrete=0.6, cuts=MEMBRETE[DG135], lines=[
        cut(DG135, 4, 110, 1431, 1411, 43, "Típicamente, durante el temporal de lluvias el deterioro en la calidad del agua es mayor que el", marca=False),
        cut(DG135, 4, 111, 1474, 1411, 41, "resto del año. Sin embargo, desde el mes de diciembre de 2025 se ha observado un deterioro"),
        cut(DG135, 4, 111, 1516, 1410, 38, "significativo y mucho mayor al registrado durante el propio temporal de lluvias. Esta condición"),
        cut(DG135, 4, 112, 1554, 1410, 40, "rebasa la capacidad operativa de la planta potabilizadora, ya que no fue diseñada para tratar agua"),
        cut(DG135, 4, 111, 1595, 1410, 39, "con estas características de calidad. A ello se suma la antigüedad de la infraestructura, la cual"),
        cut(DG135, 4, 111, 1635, 1133, 48, "data de 1956, lo que limita aún más la eficiencia del proceso de potabilización.", marca=False),
        SKIP,
        cut(DG135, 6, 1291, 329, 225, 38, "la calidad de la", marca=False),
        cut(DG135, 6, 107, 368, 1409, 44, "misma impacta directamente en nuestros procesos de potabilización, los cuales no son los"),
        cut(DG135, 6, 106, 413, 970, 36, "adecuados para tratar agua con una alta carga de contaminantes."),
    ]),
    # p. 1. A red receipt stamp and a blue pen stroke cross these lines, so they are cut in colour and the caption says so.
    "tlaj-transitan": dict(page="tlajomulco", membrete=0.6, cuts=MEMBRETE[DG135], lines=[
        cut(DG135, 1, 132, 1587, 1391, 32, "Del mismo modo, le informo que, personal de las Subdirecciones de Abastecimiento, Potabilización", marca=False, color=True),
        cut(DG135, 1, 131, 1618, 1392, 46, "y Laboratorios han documentado que en los últimos tiempos, por el Canal Las Pintas transitan aguas", color=True),
        cut(DG135, 1, 132, 1664, 1392, 35, "residuales provenientes de descargas de aguas sanitarias y/o residuales que se encuentran dentro", color=True),
        cut(DG135, 1, 132, 1701, 1392, 35, "del municipio de Tlajomulco de Zúñiga, son aguas residuales sin control, al parecer, principalmente,", color=True),
        cut(DG135, 1, 132, 1736, 1391, 35, "son aportaciones de origen diverso que descargan hacia el canal \"Las Pintas\" cauce a cielo abierto,", marca=False, color=True),
    ]),
    # Anexo 01, p. 4.
    "tlaj-puntos": dict(page="tlajomulco", membrete=0.6, cuts=MEMBRETE[DG135], lines=[
        cut(DG135, 4, 568, 1075, 952, 39, "se han identificado los ingresos de caudales hacia el Canal Las"),
        cut(DG135, 4, 111, 1115, 1409, 41, "Pintas con olor y color característico del agua residual, siendo los puntos principales en: El Capulín"),
        cut(DG135, 4, 109, 1157, 1412, 42, "1, 2 y 3, El Guayabo, El Zapote, La Carreta, El Edén, La Teja, Vaso Regulador Adolf Horn y 1°. De Mayo."),
        cut(DG135, 4, 110, 1199, 1410, 38, "Cabe señalar que, en estos sitios se han observado descargas abundantes, en algunas de manera", marca=False),
        cut(DG135, 4, 111, 1237, 1409, 37, "permanente y otras de forma intermitente, que de cualquier manera afectan considerablemente,", marca=False),
    ]),
    # Tlajomulco, oficio DAPIH/0331-01/2026 to its Dirección de Derechos Humanos for the CEDHJ, March 2026: p. 3.
    "tlaj-recorridos": dict(page="tlajomulco", membrete=0.7, cuts=MEMBRETE[T0331], lines=[
        cut(T0331, 3, 210, 575, 1307, 47, "Respecto a lo requerido, se manifiesta que el SIAPA informó al Municipio de Tlajomulco", marca=False),
        cut(T0331, 3, 209, 623, 1308, 39, "de Zúñiga, respecto a 10 (diez) presuntos puntos de descarga de aguas residuales", marca=False),
        cut(T0331, 3, 210, 663, 1307, 44, "hacia el sistema antiguo de abastecimiento de Chapala, en específico en el Canal Las", marca=False),
        cut(T0331, 3, 210, 708, 1308, 44, "Pintas, por lo cual se realizaron tres recorridos en campo en conjunto con el SIAPA"),
        cut(T0331, 3, 209, 753, 1308, 44, "para visitar estos 10 puntos, constatando que no existen descargas de aguas"),
        cut(T0331, 3, 209, 798, 481, 41, "residuales al canal \"Las pintas\"."),
    ]),
    # p. 4.
    "tlaj-conexiones": dict(page="tlajomulco", membrete=0.7, cuts=MEMBRETE[T0331], lines=[
        cut(T0331, 4, 206, 1102, 1309, 46, "Arroyo Seco, y tiene una longitud aproximada de 23 kilómetros, de los cuales", marca=False),
        cut(T0331, 4, 207, 1148, 1308, 40, "solamente 2.4 kilómetros se encuentran dentro del territorio del municipio de", marca=False),
        cut(T0331, 4, 206, 1188, 1308, 45, "Tlajomulco de Zúñiga, sin embargo, es de vital importancia aclarar que este Municipio", marca=False),
        cut(T0331, 4, 204, 1233, 1310, 42, "no tiene conexiones al colector Arroyo Seco en la zona donde se han detectado"),
        cut(T0331, 4, 205, 1275, 1003, 49, "descargas de aguas residuales hacia el cauce del mismo;"),
    ]),
    # Tlajomulco, oficio DAPIH/0127-01/2026 to the SIAPA, 27 Jan 2026: p. 1.
    "tlaj-tlaquepaque": dict(page="tlajomulco", membrete=0.7, cuts=MEMBRETE[T0127], lines=[
        cut(T0127, 1, 626, 720, 887, 39, "se identificó una línea sanitaria en estado de deterioro", marca=False),
        cut(T0127, 1, 176, 759, 1337, 38, "avanzado, la cual se encuentra expuesta y descargando aguas residuales sin tratamiento", marca=False),
        cut(T0127, 1, 176, 795, 579, 45, "al cauce conocido como Arroyo Seco.", marca=False),
        SKIP,
        cut(T0127, 1, 351, 916, 1161, 39, "generando un impacto negativo en la calidad del agua que se incorpora al"),
        cut(T0127, 1, 174, 954, 1336, 41, "sistema de escurrimientos naturales, particularmente en la zona del Canal de Las Pintas,"),
        SKIP,
        cut(T0127, 1, 173, 1061, 1337, 49, "Con base en la ubicación y el trazo de los sistemas de alcantarillado, se determinó que"),
        cut(T0127, 1, 172, 1109, 1338, 40, "esta descarga proviene del municipio de San Pedro Tlaquepaque, por lo que se"),
    ]),
    # Tlajomulco, resolution DTRC/1740/2026 for 140290426001765, 20 Nov 2026: pp. 4 and 5.
    "tlaj-sin-respuesta": dict(page="tlajomulco", membrete=0.7, cuts=MEMBRETE[T1740], lines=[
        cut(T1740, 4, 219, 1208, 1304, 62, "En este tenor, se informa que el municipio no emitió respuesta al referido oficio,"),
        cut(T1740, 4, 218, 1294, 1308, 50, "sino que se procedió a realizar los tres recorridos informados a la Comisión Estatal", marca=False),
        cut(T1740, 4, 218, 1374, 1308, 58, "de Derechos Humanos Jalisco (CEDHJ), los cuales fueron coordinados por el", marca=False),
        cut(T1740, 4, 217, 1458, 747, 54, "SIAPA en seguimiento al oficio DG-135/2026.", marca=False),
        SKIP,
        cut(T1740, 4, 1342, 1539, 182, 55, "las listas y"),
        cut(T1740, 4, 217, 1617, 1303, 61, "minutas que, en su caso, se hubieren levantado con motivo de dichos recorridos,"),
        cut(T1740, 4, 217, 1698, 1305, 61, "obran en los archivos del Sistema Intermunicipal de los Servicios de Agua Potable"),
        cut(T1740, 4, 216, 1785, 405, 55, "y Alcantarillado (SIAPA)."),
    ]),
    "tlaj-punto5": dict(page="tlajomulco", membrete=0.7, cuts=MEMBRETE[T1740], lines=[
        cut(T1740, 5, 211, 1818, 1305, 66, "Por último, con relación a lo solicitado en el punto 5, no se cuenta con"),
        cut(T1740, 5, 209, 1900, 405, 56, "información al respecto."),
    ]),
    # SIAPA, oficio UT/2475/2026, answer to 140279226001178, 13 Nov 2026: p. 2. From p. 1, which names the requester,
    # only the logo and the oficio's number.
    "tlaj-sin-registros": dict(page="tlajomulco", membrete=0.6, cuts=[
        logo(S1178, 1, 650, 55, 425, 105),
        logo(S1178, 1, 1135, 190, 340, 46, "Oficio UT/2475/2026"),
    ], lines=[
        cut(S1178, 2, 229, 272, 1236, 45, "PRIMERO. Se comunica que, la Unidad de Transparencia realizó las gestiones", marca=False),
        cut(S1178, 2, 229, 317, 1234, 40, "necesarias para obtener la información de su solicitud de acceso a la información con", marca=False),
        cut(S1178, 2, 229, 357, 671, 41, "la Dirección de Abastecimiento y Operación,"),
        SKIP,
        cut(S1178, 2, 837, 437, 470, 42, "misma que informo lo siguiente:", marca=False),
        cut(S1178, 2, 228, 513, 1234, 48, "Se hace de su conocimiento que, en esta área operativa, no se cuenta con"),
        cut(S1178, 2, 227, 562, 1238, 42, "documentales o archivos que contengan la información con la desagregación y"),
        cut(S1178, 2, 227, 604, 402, 44, "especificación pretendida."),
    ]),
    # PROEPA, oficio DJPA/UT/3292/0162/2026, answer to 140276526000172, 23 Nov 2026: p. 5. Point 4 of the request was
    # the 20 March meeting at the SEMADET.
    "tlaj-convocante": dict(page="tlajomulco", membrete=0.6, cuts=[
        logo(P172, 1, 570, 190, 560, 165),
        logo(P172, 1, 860, 578, 775, 56, "Oficio PROEPA DJPA/ UT/ 3292 / 0162 /2026"),
    ], lines=[
        cut(P172, 5, 364, 1580, 1281, 52, "Aunado a lo anterior, y relativo al punto 4 cuatro de su solicitud, se le", marca=False),
        cut(P172, 5, 367, 1631, 1277, 47, "informa que esta autoridad no cuenta con minutas o listas de asistencia, ni"),
        cut(P172, 5, 366, 1677, 1279, 46, "documentos relacionados con lo que refiere en este punto, toda vez que,"),
        cut(P172, 5, 366, 1724, 628, 42, "esta autoridad no fue la convocante."),
    ]),
    # SIAPA, oficio UT/2628/2026, answer to 140279226001270, 26 Nov 2026: the reserve (p. 3), the harm it alleges
    # (pp. 5-6) and the Comité (p. 6).
    "tlaj-reserva": dict(page="tlajomulco", membrete=0.6, cuts=[
        logo(S1270, 1, 650, 50, 430, 100),
        logo(S1270, 1, 1139, 193, 341, 46, "Oficio UT/2628/2026"),
    ], lines=[
        cut(S1270, 3, 228, 594, 1248, 40, "Derivado de la búsqueda y análisis realizado dentro del citado expediente, se advierte", marca=False),
        cut(S1270, 3, 228, 634, 1248, 40, "que la documentación especifica solicitada encuadra en el supuesto de reserva", marca=False),
        cut(S1270, 3, 228, 674, 1248, 42, "establecido en el articulo 17, numeral 1, fracción I, incisos d), f) y g), 18, 19 y 63-Bis de la"),
        cut(S1270, 3, 228, 716, 1248, 38, "Ley de Transparencia y Acceso a la Información Publica del Estado de Jalisco y sus", marca=False),
        cut(S1270, 3, 228, 754, 1248, 41, "Municipios. Lo anterior, toda vez que la misma se encuentra vinculada con hechos"),
        cut(S1270, 3, 228, 795, 1248, 38, "materia de una carpeta de investigación, radicada en la Fiscalía General de la"),
        cut(S1270, 3, 228, 833, 870, 37, "Republica, cuyas determinaciones no han causado estado."),
    ]),
    "tlaj-riesgo": dict(page="tlajomulco", membrete=0.6, cuts=[
        logo(S1270, 1, 650, 50, 430, 100),
        logo(S1270, 1, 1139, 193, 341, 46, "Oficio UT/2628/2026"),
    ], lines=[
        cut(S1270, 5, 318, 1800, 1146, 51, "Riesgo real: La divulgación de los oficios, anexos y documentación relativa al", marca=False),
        cut(S1270, 5, 318, 1851, 1146, 40, "mismo, expondría de forma pública y anticipada los mapeos"),
        cut(S1270, 5, 318, 1891, 1146, 40, "georreferenciados, coordenadas, infraestructura identificada y puntos"),
        cut(S1270, 5, 318, 1931, 1146, 45, "exactos de fuentes de descarga irregulares o contaminantes en el Arroyo Seco"),
        cut(S1270, 6, 314, 180, 1146, 52, "y el Canal de Las Pintas, así como los razonamientos y acciones institucionales"),
        cut(S1270, 6, 314, 232, 400, 36, "en torno a dichos hechos.", marca=False),
        SKIP,
        cut(S1270, 6, 224, 807, 1240, 56, "Por lo que el Comité de Transparencia, aprobó RESERVAR la información solicitada, en"),
        cut(S1270, 6, 224, 863, 480, 34, "la décima sesión extraordinaria."),
    ]),
})


def foto(pagina, pdf, page, x, y, w, h, texto, gira=0, mini=False):
    """A photograph or plan cut whole, without our marks, as WebP; `gira` turns it clockwise (90, 180 or 270). `mini`
    adds a copy at half size, rendered at half the dpi (so the box must be even), for a grid whose tile links to the
    whole one; the page's <img> shows the copy."""
    assert not mini or all(v % 2 == 0 for v in (x, y, w, h)), f"{pdf} p. {page}: a mini needs an even box"
    return dict(pagina=pagina, pdf=pdf, page=page, box=(x, y, w, h), texto=texto, gira=gira, mini=mini)


# The SIAPA's plan and photographs in the annex of DG-135/2026, PDF pp. 7-16. Boxes hug each page's photographs (two
# side by side or stacked are one image, as the SIAPA laid them out) and leave out the page's heading, whose words go
# in the caption as written, and the pen marks at its foot. A photograph that shows a person's face or name, a licence
# plate or a house number doesn't go in whole: none of these do (checked by eye at 200 dpi, 24 Nov 2026).
FOTOS = {
    "dg135-plano": foto("tlajomulco", DG135, 7, 252, 266, 1066, 1588, "Plano general de localización de las descargas del SIAPA: una imagen de satélite con el trazo del canal, los puntos del 1 al 10 en círculos rojos, varios con una foto pequeña al lado, y la tabla de los diez puntos.", gira=90),
    "dg135-capulin-1": foto("tlajomulco", DG135, 8, 206, 366, 1224, 1060, "Dos fotografías: agua gris que sale con fuerza de un tubo roto entre el pasto, bajo un puente de barandal amarillo, y un tubo blanco que termina en un charco de agua gris, junto a un canal cubierto de plantas.", mini=True),
    "dg135-guayabo": foto("tlajomulco", DG135, 9, 254, 366, 1124, 1478, "Agua oscura y quieta bajo árboles y matorrales, junto a un muro de concreto, con una casa al fondo.", mini=True),
    "dg135-carreta": foto("tlajomulco", DG135, 10, 188, 366, 1236, 908, "Un puente de tres arcos sobre agua oscura, con basura en la ladera de atrás.", mini=True),
    "dg135-eden": foto("tlajomulco", DG135, 11, 270, 366, 1086, 1540, "Dos fotografías: una capa de espuma blanca que cubre el canal al pie de una caída de agua, y un sillón atorado en el borde de una caída, con espuma abajo.", mini=True),
    "dg135-teja": foto("tlajomulco", DG135, 12, 264, 444, 1032, 1342, "Un flujo de agua que entra a un cuerpo de agua turbia, bajo un cielo nublado.", mini=True),
    "dg135-adolf-horn": foto("tlajomulco", DG135, 13, 238, 334, 1148, 1294, "Agua verdosa que sale de un tubo azul y baja por un muro de piedra, bajo una cerca de lámina azul, hacia agua cubierta de espuma blanca, entre la maleza.", mini=True),
    "dg135-km4": foto("tlajomulco", DG135, 14, 212, 374, 1246, 948, "Dos fotografías: un puente de concreto sobre el agua, y una alcantarilla de concreto con grafiti por la que sale agua con espuma hacia agua turbia color café.", mini=True),
    "dg135-1-mayo": foto("tlajomulco", DG135, 15, 206, 374, 1212, 1044, "Dos fotografías: el canal con agua oscura bajo una barda blanca, y la boca de un tubo de concreto en la orilla, entre plantas.", mini=True),
    # Anexo 02, p. 16: its two photographs, without the map and text above them (the page quotes the text).
    "dg135-anexo02": foto("tlajomulco", DG135, 16, 110, 1038, 1414, 550, "Dos fotografías: agua con espuma que corre por una pendiente de concreto, entre la vegetación."),
}


def pdf_path(key):
    found = ([ROOT / PDFS[key]] if key in PDFS else []) + (
        [ROOT / RESEARCH[key], pathlib.Path.home() / "agua-gdl" / RESEARCH[key]] if key in RESEARCH else [])
    for p in found:
        if p.is_file():
            return p
    sys.exit(f"documentos: no PDF for {key}: " + " or ".join(
        ([f"publish {PDFS[key]}"] if key in PDFS else []) + ([f"keep {RESEARCH[key]} in ~/agua-gdl"] if key in RESEARCH else [])))


def name(card, kind, i):
    return f"{card}-{kind}{i}.png"


def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{p} is not a PNG")
    return struct.unpack(">II", head[16:24])


def webp_size(p):
    with open(p, "rb") as f:
        head = f.read(30)
    if head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        raise ValueError(f"{p} is not a WebP")
    if head[12:16] == b"VP8 ":
        w, h = struct.unpack("<HH", head[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if head[12:16] == b"VP8L":
        bits = int.from_bytes(head[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if head[12:16] == b"VP8X":
        return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    raise ValueError(f"{p}: unknown WebP chunk {head[12:16]!r}")


def foto_files(foto_id, f):
    """Each WebP a photograph makes, as (name, its size, the divisor of dpi and box): whole, then the half-size copy."""
    w, h = f["box"][2:]
    if f["gira"] in (90, 270):
        w, h = h, w
    yield f"{foto_id}.webp", (w, h), 1
    if f["mini"]:
        yield f"{foto_id}-mini.webp", (w // 2, h // 2), 2


def read_ppm(b):
    parts, i = [], 0
    while len(parts) < 4:
        while b[i:i + 1].isspace():
            i += 1
        j = i
        while not b[j:j + 1].isspace():
            j += 1
        parts.append(b[i:j])
        i = j
    if parts[0] != b"P6" or parts[3] != b"255":
        raise ValueError(f"not an 8-bit PPM: {parts[0]!r}")
    w, h = int(parts[1]), int(parts[2])
    return w, h, b[i + 1:i + 1 + 3 * w * h]


def turn(w, h, px, gira):
    """Turn RGB pixels clockwise by `gira` degrees: each new row is an old column, read bottom to top."""
    for _ in range(gira // 90 % 4):
        rows = []
        for x in range(w):
            row = bytearray(3 * h)
            for c in range(3):
                row[c::3] = px[3 * x + c::3 * w][::-1]
            rows.append(row)
        w, h, px = h, w, b"".join(rows)
    return w, h, px


def cut_foto(foto_id, f):
    for out, _, div in foto_files(foto_id, f):
        x, y, w, h = (v // div for v in f["box"])
        with tempfile.TemporaryDirectory() as tmp:
            raw = pathlib.Path(tmp) / "f"
            subprocess.run(["pdftoppm", "-f", str(f["page"]), "-l", str(f["page"]), "-r", str(DPI // div), "-x", str(x), "-y", str(y),
                            "-W", str(w), "-H", str(h), "-singlefile", str(pdf_path(f["pdf"])), str(raw)], check=True)
            tw, th, px = turn(*read_ppm(raw.with_suffix(".ppm").read_bytes()), f["gira"])
            turned = pathlib.Path(tmp) / "t.ppm"
            turned.write_bytes(b"P6\n%d %d\n255\n" % (tw, th) + px)
            subprocess.run(["cwebp", "-quiet", "-q", "78", "-m", "6", "-metadata", "none", str(turned), "-o", str(OUT / out)], check=True)


def render_foto(foto_id, f):
    img, (w, h), _ = list(foto_files(foto_id, f))[-1]
    return (f'<img src="/img/documentos/{img}" width="{w}" height="{h}" alt="{html.escape(f["texto"])}" '
            f'loading="lazy" decoding="async">')


def pct(v):
    return f"{v:.2f}".rstrip("0").rstrip(".") + "%"


def images(card_id, card):
    yield from ((name(card_id, "m", i), c) for i, c in enumerate(card["cuts"], 1))
    yield from ((name(card_id, "", i), c) for i, c in enumerate((c for c in card["lines"] if c != SKIP), 1))


def render(card_id, card):
    lines = [c for c in card["lines"] if c != SKIP]
    ref = max(c["box"][2] * c["escala"] for c in lines)
    esc = html.escape
    out = [f'<div class="hoja" data-documento="{card_id}">']
    if card["cuts"]:
        out.append('<div class="membrete">' + "".join(
            f'<img src="/img/documentos/{name(card_id, "m", i)}" width="{c["box"][2]}" height="{c["box"][3]}" '
            f'style="width:{pct(100 * c["box"][2] * card["membrete"] / ref)}" alt="{esc(c["texto"])}" loading="lazy">'
            for i, c in enumerate(card["cuts"], 1)) + "</div>")
    out.append('<div class="renglones">')
    i = 0
    for c in card["lines"]:
        if c == SKIP:
            out.append('<span class="salto" aria-hidden="true">[…]</span>')
            continue
        i += 1
        x0, y0, w, h = c["box"]
        rings = "".join(
            f'<span class="anillo" style="left:{pct(100 * x / w)};top:{pct(100 * y / h)};width:{pct(200 * r / w)}"></span>'
            f'<span class="etiqueta" style="left:{pct(100 * (x + dx) / w)};top:{pct(100 * (y + dy) / h)}">{esc(t)}</span>'
            for x, y, r, t, dx, dy in c["anillos"])
        out.append(f'<span class="renglon{" marca" if c["marca"] else ""}" style="width:{pct(100 * w * c["escala"] / ref)}">'
                   f'<img src="/img/documentos/{name(card_id, "", i)}" width="{w}" height="{h}" alt="{esc(c["texto"])}" loading="lazy">{rings}</span>')
    out.append("</div></div>")
    return "\n".join(out)


def pages():
    texts = {p: p.read_text() for p in sorted((ROOT / "web").glob("*.html"))}
    return {p: t for p, t in texts.items() if "<!-- documento:" in t or "<!-- foto:" in t}


def block(card_id, kind="documento"):
    return re.compile(rf"(<!-- {kind}:{re.escape(card_id)} -->\n).*?(\n<!-- /{kind}:{re.escape(card_id)} -->)", re.S)


def main(argv):
    check = "--check" in argv
    found = pages()
    problems, cards, imgs, fotos = [], 0, 0, 0
    for kind, defined in (("documento", CARDS), ("foto", FOTOS)):
        marked = {m for text in found.values() for m in re.findall(rf"<!-- {kind}:([\w-]+) -->", text)}
        for extra in sorted(marked - defined.keys()):
            problems.append(f"a page marks {kind}:{extra}, which {'CARDS' if kind == 'documento' else 'FOTOS'} doesn't define")
    new = dict(found)
    for card_id, card in CARDS.items():
        page = ROOT / "web" / f"{card['page']}.html"
        if page not in found or not block(card_id).search(found[page]):
            problems.append(f"web/{card['page']}.html has no <!-- documento:{card_id} --> block")
            continue
        cards += 1
        if not check:
            OUT.mkdir(parents=True, exist_ok=True)
            for img, c in images(card_id, card):
                x, y, w, h = c["box"]
                subprocess.run(["pdftoppm", "-f", str(c["page"]), "-l", str(c["page"]), "-r", str(DPI), "-x", str(x), "-y", str(y),
                                "-W", str(w), "-H", str(h), *([] if c["color"] else ["-gray"]), "-png", "-singlefile",
                                str(pdf_path(c["pdf"])), str(OUT / img[:-4])], check=True)
        for img, c in images(card_id, card):
            imgs += 1
            p = OUT / img
            if not p.is_file():
                problems.append(f"{img} is missing: run python3 pipelines/documentos.py")
            elif png_size(p) != c["box"][2:]:
                problems.append(f"{img} is {png_size(p)}, its box says {c['box'][2:]}")
        new[page] = block(card_id).sub(lambda m: m.group(1) + render(card_id, card) + m.group(2), new[page])
    for foto_id, f in FOTOS.items():
        page = ROOT / "web" / f"{f['pagina']}.html"
        if page not in found or not block(foto_id, "foto").search(found[page]):
            problems.append(f"web/{f['pagina']}.html has no <!-- foto:{foto_id} --> block")
            continue
        fotos += 1
        if not check:
            OUT.mkdir(parents=True, exist_ok=True)
            cut_foto(foto_id, f)
        for img, size, _ in foto_files(foto_id, f):
            imgs += 1
            p = OUT / img
            if not p.is_file():
                problems.append(f"{img} is missing: run python3 pipelines/documentos.py")
            elif webp_size(p) != size:
                problems.append(f"{img} is {webp_size(p)}, its box says {size}")
        new[page] = block(foto_id, "foto").sub(lambda m: m.group(1) + render_foto(foto_id, f) + m.group(2), new[page])
    stale = [p for p in found if new[p] != found[p]]
    if check:
        problems += [f"{p.relative_to(ROOT)} has a stale card or photo: run python3 pipelines/documentos.py" for p in stale]
        made = {img for k, c in CARDS.items() for img, _ in images(k, c)} | {img for k, f in FOTOS.items() for img, _, _ in foto_files(k, f)}
        unused = sorted(p.name for p in OUT.iterdir() if p.is_file() and not p.name.startswith(".")) if OUT.is_dir() else []
        problems += [f"web/img/documentos/{u} belongs to no card or photo" for u in unused if u not in made]
    else:
        for p in stale:
            p.write_text(new[p])
    if problems:
        sys.exit("documentos:\n  " + "\n  ".join(problems))
    if not cards:
        sys.exit("documentos: no cards found in web/*.html")
    print(f"documentos: {cards} cards and {imgs} images, {fotos} photographs, in {len(found)} pages"
          + ("" if check else f"; wrote {len(stale)} pages"))


if __name__ == "__main__":
    main(sys.argv[1:])
