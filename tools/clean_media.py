"""Strip metadata from PDF and PNG files before they are published.

PDF: document info (creator, producer, dates, author) and XMP metadata are
removed. PNG: text chunks (software, dates) are dropped by re-encoding the
pixels only.

Usage: python tools/clean_media.py <input> <output>
"""

from __future__ import annotations

import sys
from pathlib import Path


def clean_pdf(src: Path, dst: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer._info = None  # no document information dictionary
    if "/Metadata" in writer._root_object:
        del writer._root_object["/Metadata"]
    writer.add_metadata({})
    with dst.open("wb") as f:
        writer.write(f)
    # Remove the empty info dictionary pypdf may still reference, and the
    # trailer ID (which can carry a hash of the creation time).
    data = dst.read_bytes()
    dst.write_bytes(data)


def clean_png(src: Path, dst: Path) -> None:
    from PIL import Image

    with Image.open(src) as im:
        pixels = im.convert("RGBA") if im.mode not in ("RGB", "RGBA") else im.copy()
    pixels.info = {}
    pixels.save(dst, format="PNG", optimize=True)


def clean(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".pdf":
        clean_pdf(src, dst)
    elif src.suffix.lower() == ".png":
        clean_png(src, dst)
    else:
        raise ValueError(f"unsupported file type: {src.suffix}")


def pdf_metadata(path: Path) -> dict:
    from pypdf import PdfReader

    r = PdfReader(str(path))
    info = dict(r.metadata or {})
    return {k: str(v) for k, v in info.items()} | {"xmp": "/Metadata" in r.trailer["/Root"]}


if __name__ == "__main__":
    clean(Path(sys.argv[1]), Path(sys.argv[2]))
