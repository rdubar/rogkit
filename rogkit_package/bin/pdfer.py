"""
PDF creator from images.

Converts a folder of JPG/PNG images into a single PDF document with A4 page size,
automatically rotating landscape images and centering content.
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image  # type: ignore
from reportlab.lib.pagesizes import A4  # type: ignore
from reportlab.lib.utils import ImageReader  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore


ImagePathSeq = Sequence[Path]


def _iter_image_files(folder_path: Path, exts: Iterable[str]) -> list[Path]:
    """Return image files in name order with allowed extensions."""
    normalized_exts = {ext.lower() for ext in exts}
    return sorted(
        [
            p
            for p in folder_path.iterdir()
            if p.is_file() and p.suffix.lower().lstrip(".") in normalized_exts
        ],
        key=lambda p: p.name.lower(),
    )


def create_pdf_from_images(folder_path: Path, output_pdf: Path) -> None:
    """Create PDF from JPG/PNG images in a folder."""
    images = _iter_image_files(folder_path, ("jpg", "jpeg", "png"))
    if not images:
        print(f"No JPG/PNG images found in {folder_path}")
        return

    c = canvas.Canvas(str(output_pdf), pagesize=A4)
    page_width, page_height = A4

    for image_path in images:
        with Image.open(image_path) as img:
            if img.width > img.height:
                img = img.rotate(270, expand=True)

            dpi = img.info.get("dpi", (300, 300))
            dpi_x, dpi_y = dpi if isinstance(dpi, (tuple, list)) and len(dpi) == 2 else (300, 300)
            dpi_x = dpi_x or 300
            dpi_y = dpi_y or 300

            scale_x = page_width / (img.width * 72 / dpi_x)
            scale_y = page_height / (img.height * 72 / dpi_y)
            scale = min(scale_x, scale_y)

            new_width = img.width * scale
            new_height = img.height * scale

            x = (page_width - new_width * 72 / dpi_x) / 2
            y = (page_height - new_height * 72 / dpi_y) / 2

            new_width_pt = new_width * 72 / dpi_x
            new_height_pt = new_height * 72 / dpi_y

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            buffer.seek(0)
            img_reader = ImageReader(buffer)

            c.drawImage(img_reader, x, y, new_width_pt, new_height_pt)
            c.showPage()

    c.save()
    print(f"PDF saved to {output_pdf}")


def main() -> None:
    """CLI entry point for PDF creator."""
    parser = argparse.ArgumentParser(description="Convert images in a folder to a single PDF document.")
    parser.add_argument("folder", type=str, help="The folder containing images to be converted.")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output PDF path (default: folder/output.pdf)",
    )
    args = parser.parse_args()

    folder_path = Path(args.folder).expanduser().resolve()
    output_pdf = Path(args.output).expanduser().resolve() if args.output else folder_path / "output.pdf"

    create_pdf_from_images(folder_path, output_pdf)


if __name__ == "__main__":
    main()
