#!/usr/bin/env python3
"""Cut the pieces of official documents that slides show (a slide's "documento"), from the PDFs aguagdl.com publishes
(or will: see PDFS).

    python3 experiments/carrusel/documentos/recortes.py

Needs poppler's pdftoppm. Boxes are pixels at 200 dpi, measured on the page image. Each cut leaves out stamps,
handwriting, signatures and people's names; a sentence that wraps is cut line by line, in order, so it can be shown
large enough to read.
"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DPI = 200

PDFS = {
    "zapopan": "web/datos/zapopan-respuesta-140292426004981.pdf",
    # Not on aguagdl.com yet: research/ is gitignored and lives only in the main checkout. Publish each one in
    # web/datos/ (after a check for names and personal data) before a carousel that shows its cuts goes out.
    "pcyb-ut091": "research/transparency/extracted/pcyb-UT-091-2026/010400-2026-0286 UT-091.pdf",
    "pcyb-ut089": "research/transparency/extracted/pcyb-UT-089-2026/010400-2026-0284 UT-089.pdf",
    "r6785": "research/transparency/extracted/140292426004978/r6785.pdf",
    "r6787": "research/transparency/extracted/140292426004980/r6787.pdf",
}

# name: (pdf, page, x, y, w, h)
RECORTES = {
    # Oficio 11000000/CER.CIU/2026/0878 (Coordinación General de Cercanía Ciudadana, 6 Nov 2026), p. 5 of the response.
    "zapopan-0878-logo.png": ("zapopan", 5, 130, 135, 325, 215),       # emblem and «Cercanía Ciudadana»; the stamp starts at x 469
    "zapopan-0878-oficio.png": ("zapopan", 5, 990, 280, 575, 135),     # date, oficio number, «Asunto: Respuesta»
    "zapopan-0878-linea-1.png": ("zapopan", 5, 1017, 1869, 539, 44),   # «se encontró un total de 9,828 reportes por»
    "zapopan-0878-linea-2.png": ("zapopan", 5, 99, 1910, 878, 46),     # «falta de agua, con corte al 04 de noviembre de la presente anualidad,»
    # Oficio 011300/2026/0150 (PCyB, Dirección de Planificación, 12 Nov 2026), answer UT-091, p. 4. The stamp ends at x 1133.
    "pcyb-0150-logo.png": ("pcyb-ut091", 4, 140, 52, 280, 295),        # emblem and «PROTECCIÓN CIVIL Y BOMBEROS ZAPOPAN»; a pen mark at x < 133
    "pcyb-0150-oficio.png": ("pcyb-ut091", 4, 1230, 284, 318, 98),     # DIRECCION DE PLANIFICACION, oficio, asunto, fecha
    "pcyb-0150-linea.png": ("pcyb-ut091", 4, 828, 1170, 779, 51),      # «la cantidad de pipas participantes durante cada jornada,»
    "pcyb-0150-grafica.png": ("pcyb-ut091", 4, 395, 1916, 1010, 126),  # the pipas-per-day band of the chart, 15 Oct to 3 Nov, with its dates
    # Oficio 011300/2026/0148 (PCyB, 12 Nov 2026), answer UT-089, pp. 5-6. The addressee's name sits at y 486.
    "pcyb-0148-logo.png": ("pcyb-ut089", 5, 125, 126, 295, 298),
    "pcyb-0148-oficio.png": ("pcyb-ut089", 5, 1210, 383, 320, 95),
    "pcyb-0148-linea-1.png": ("pcyb-ut089", 5, 232, 1177, 938, 41),    # «de las 75 colonias identificadas con mayor afectación, precisando que»
    "pcyb-0148-linea-2.png": ("pcyb-ut089", 5, 1167, 1172, 429, 40),   # «dicha información fue generada»
    "pcyb-0148-linea-3.png": ("pcyb-ut089", 5, 236, 1217, 595, 47),    # «por la Coordinación de Cercanía Ciudadana»
    "pcyb-0148-hospitales.png": ("pcyb-ut089", 6, 340, 1758, 995, 43), # table rows: Hospitales | Sin atenciones registradas
    "pcyb-0148-espacios.png": ("pcyb-ut089", 6, 340, 1801, 995, 38),   # Espacios Públicos | Centro Comunitario N°3 - 09/11/2026
    "pcyb-0148-escuelas.png": ("pcyb-ut089", 6, 340, 1836, 995, 35),   # Escuelas | Centro Escolar Juan Mateo - 20/10/2026
    # Oficio 11000000/CER.CIU/2026/0876 (Cercanía Ciudadana, 6 Nov 2026), in the answer to 140292426004978, pp. 7, 8 and 11.
    # Stamp from y 389 at x 804-1260, handwriting at (595, 478), received-by and signer names below: all left out.
    "cercania-0876-logo.png": ("r6785", 7, 135, 135, 335, 225),
    "cercania-0876-oficio.png": ("r6785", 7, 980, 292, 590, 90),       # date and oficio number
    "cercania-0876-linea-1.png": ("r6785", 8, 113, 619, 676, 50),      # «en los archivos que obran en la Coordinación General,»
    "cercania-0876-linea-2.png": ("r6785", 8, 790, 619, 779, 50),      # «no se localizaron bitácoras, hojas de servicio, vales o registros»
    "cercania-0876-linea-3.png": ("r6785", 8, 113, 666, 592, 48),      # «de viaje de las pipas que llenaron las cisternas»
    "cercania-0876-lista-46-48.png": ("r6785", 11, 50, 418, 425, 207), # the list's last page, columns No. and COLONIA
    "cercania-0876-lista-49.png": ("r6785", 11, 50, 625, 425, 66),     # its last row, 49 LOS CAJETES
    # Oficio 02050000/2026/7939 (Dirección de Transparencia y Buenas Prácticas, 17 Nov 2026), the same answer, p. 2.
    "transparencia-7939-logo.png": ("r6785", 2, 150, 82, 535, 275),
    "transparencia-7939-oficio.png": ("r6785", 2, 830, 92, 790, 158),
    "transparencia-7939-linea-1.png": ("r6785", 2, 366, 1511, 861, 43),  # «cuya logística se plantea que en una primera fase sea la siguiente:»
    "transparencia-7939-linea-2.png": ("r6785", 2, 500, 1774, 645, 43),  # «Se llevarán a cabo las gestiones correspondientes»
    "transparencia-7939-linea-3.png": ("r6785", 2, 1144, 1774, 458, 43), # «para lograr materializar un sistema»
    "transparencia-7939-linea-4.png": ("r6785", 2, 500, 1813, 534, 41),  # «de 45 pipas y 100 cisternas comunitarias»
    # Oficio 11000000/CER.CIU/2026/0907 (Cercanía Ciudadana, 17 Nov 2026), in the answer to 140292426004980, p. 6.
    # The stamp runs from x 448 and touches «Ciudadana», so only the emblem; handwriting at (959-1082, 215-254).
    "cercania-0907-escudo.png": ("r6787", 6, 143, 135, 165, 225),
    "cercania-0907-oficio.png": ("r6787", 6, 1005, 286, 575, 135),     # date, oficio number, «Asunto: Respuesta»
    "cercania-0907-pregunta.png": ("r6787", 6, 212, 1265, 1086, 50),   # «1. El listado o los documentos en que consten las 211 colonias y las 75 más afectadas»
    "cercania-0907-linea-1.png": ("r6787", 6, 509, 1831, 584, 50),     # «no se localizó información respecto a los puntos»
    "cercania-0907-linea-2.png": ("r6787", 6, 1092, 1831, 484, 50),    # «señalados y descritos anteriormente al»
    "cercania-0907-linea-3.png": ("r6787", 6, 116, 1873, 812, 47),     # «no tratarse de funciones inherentes a esta Coordinación General»
}


def pdf(key):
    for base in (ROOT, pathlib.Path.home() / "agua-gdl"):
        p = base / PDFS[key]
        if p.is_file():
            return p
    sys.exit(f"recortes: no {PDFS[key]} here or in ~/agua-gdl")


def main():
    for name, (key, page, x, y, w, h) in RECORTES.items():
        out = HERE / name
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(DPI), "-x", str(x), "-y", str(y),
                        "-W", str(w), "-H", str(h), "-png", "-singlefile", str(pdf(key)), str(out.with_suffix(""))], check=True)
        print(f"  documentos/{name}")


if __name__ == "__main__":
    main()
