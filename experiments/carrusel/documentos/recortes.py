#!/usr/bin/env python3
"""Cut the pieces of official documents that slides show (a slide's "documento"), from the PDFs aguagdl.com publishes.

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

PDFS = {"zapopan": "web/datos/zapopan-respuesta-140292426004981.pdf"}

# name: (pdf, page, x, y, w, h)
RECORTES = {
    # Oficio 11000000/CER.CIU/2026/0878 (Coordinación General de Cercanía Ciudadana, 6 Nov 2026), p. 5 of the response.
    "zapopan-0878-logo.png": ("zapopan", 5, 130, 135, 325, 215),       # emblem and «Cercanía Ciudadana»; the stamp starts at x 469
    "zapopan-0878-oficio.png": ("zapopan", 5, 990, 280, 575, 135),     # date, oficio number, «Asunto: Respuesta»
    "zapopan-0878-linea-1.png": ("zapopan", 5, 1017, 1869, 539, 44),   # «se encontró un total de 9,828 reportes por»
    "zapopan-0878-linea-2.png": ("zapopan", 5, 99, 1910, 878, 46),     # «falta de agua, con corte al 04 de noviembre de la presente anualidad,»
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
