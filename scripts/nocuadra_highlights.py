"""Add translucent yellow evidence marks to the No cuadra document cutouts."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web" / "img" / "anunciado"
MARK = (242, 200, 75, 105)
RECTANGLES = {
    "corte-reportes.jpg": [
        (700, 232, 966, 263),   # un total de 9,828 reportes por
        (18, 264, 500, 294),    # falta de agua, con corte al 04 de noviembre
    ],
    "corte-pipas.jpg": [
        (381, 229, 435, 251),   # 840,000 litros
        (462, 445, 495, 470),   # máximo de 34 pipas
        (174, 484, 198, 504),   # 11 pipas el 19 de octubre
    ],
    "corte-cisternas.jpg": [
        (8, 48, 45, 76),        # No.
        (100, 48, 177, 76),     # Colonia
    ],
    "corte-hospitales.jpg": [
        (100, 81, 215, 109),    # Hospitales
        (405, 79, 685, 109),    # Sin atenciones registradas
        (584, 132, 711, 159),   # Primera escuela: 20/10/2026
    ],
}

for name, rectangles in RECTANGLES.items():
    source = ASSETS / name
    image = Image.open(source).convert("RGBA")
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)
    for rectangle in rectangles:
        draw.rectangle(rectangle, fill=MARK)
    marked = Image.alpha_composite(image, overlay).convert("RGB")
    output = source.with_name(source.stem + "-destacado.jpg")
    marked.save(output, quality=94, subsampling=0)
    print(output.relative_to(ROOT))

for page in [ROOT / "web" / "nocuadra.html", *sorted((ROOT / "web").glob("nocuadra-v?.html"))]:
    text = page.read_text()
    for name in RECTANGLES:
        text = text.replace(f"/img/anunciado/{name}", f"/img/anunciado/{Path(name).stem}-destacado.jpg")
    page.write_text(text)
