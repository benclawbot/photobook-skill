#!/usr/bin/env python3
"""Build a square, varied-layout photobook PDF from the reviewed photos.csv manifest."""
import argparse
import csv
from collections import OrderedDict
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PAGE = 720
LAYOUTS = (1, 2, 3, 2, 4, 1, 2, 3, 2, 2, 3, 2)


def enabled(value):
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "x"}


def group_rows(manifest, photos, mono_title, interior_title, nature_title, people_title):
    with manifest.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("The photo manifest is empty")
    groups = OrderedDict()
    seen_hashes = set()
    for row in rows:
        if row.get("sha256") and row["sha256"] in seen_hashes:
            raise ValueError(f"Duplicate photo in manifest: {row['file']}")
        if row.get("sha256"):
            seen_hashes.add(row["sha256"])
        filename = row.get("file", "").strip()
        path = (photos / filename).resolve()
        if not filename or not path.is_file() or not path.is_relative_to(photos.resolve()):
            raise ValueError(f"Missing or unsafe photo path in manifest: {filename!r}")
        # Explicit priority keeps overlapping visual classifications predictable.
        theme = (mono_title if enabled(row.get("monochrome")) else
                 interior_title if enabled(row.get("interior")) else
                 nature_title if enabled(row.get("nature")) else
                 people_title if enabled(row.get("people")) else
                 row.get("theme", "").strip())
        if not theme:
            raise ValueError(f"Choose a theme or classification for {filename}")
        row["_path"] = str(path)
        row["_sequence"] = int(row.get("sequence", 0) or 0)
        groups.setdefault(theme, []).append(row)
    return groups


def fit_image(c, path, x, y, size):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        image.load()
    scale = min(size / width, size / height)
    w, h = width * scale, height * scale
    c.drawImage(ImageReader(image), x + (size - w) / 2, y + (size - h) / 2,
                width=w, height=h, preserveAspectRatio=True, mask="auto")


def folio(c):
    c.setFillColor(HexColor("#4B4B4B"))
    c.roundRect(25, 675, 42, 21, 3, fill=1, stroke=0)


def cover_page(c, cover):
    c.setFillColor(HexColor("#050505"))
    c.rect(0, 0, PAGE, PAGE, fill=1, stroke=0)
    if cover:
        with Image.open(cover) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            width, height = image.size
            image.load()
        scale = min(PAGE / width, PAGE / height)
        w, h = width * scale, height * scale
        c.drawImage(ImageReader(image), (PAGE - w) / 2, (PAGE - h) / 2,
                    width=w, height=h, preserveAspectRatio=True, mask="auto")
    c.showPage()


def place_page_images(c, paths, page_in_theme):
    count = len(paths)
    if count == 1:
        size = (470, 520, 440)[page_in_theme % 3]
        fit_image(c, paths[0], (PAGE - size) / 2, (PAGE - size) / 2, size)
    elif count == 2:
        layouts = [[(70, 292, 340), (420, 112, 215)],
                   [(300, 300, 325), (82, 112, 220)],
                   [(76, 242, 252), (392, 242, 252)],
                   [(180, 357, 355), (285, 78, 238)]]
        for path, (x, y, size) in zip(paths, layouts[page_in_theme % len(layouts)]):
            fit_image(c, path, x, y, size)
    elif count == 3:
        layouts = [[(188, 315, 340), (58, 92, 190), (472, 92, 190)],
                   [(58, 294, 286), (374, 356, 255), (218, 54, 210)],
                   [(74, 370, 246), (365, 370, 246), (220, 92, 246)]]
        for path, (x, y, size) in zip(paths, layouts[page_in_theme % len(layouts)]):
            fit_image(c, path, x, y, size)
    else:
        for path, (x, y) in zip(paths, [(90, 384), (380, 384), (90, 96), (380, 96)]):
            fit_image(c, path, x, y, 250)


def compose(layout_pdf, groups, cover, title):
    c = canvas.Canvas(str(layout_pdf), pagesize=(PAGE, PAGE), pageCompression=1)
    c.setTitle(title)
    c.setAuthor("Photobook")
    cover_page(c, cover)
    for theme, rows in groups.items():
        c.setFillColor(white)
        c.rect(0, 0, PAGE, PAGE, fill=1, stroke=0)
        folio(c)
        c.showPage()
        ordered = sorted(rows, key=lambda row: row["_sequence"])
        cursor = page_in_theme = 0
        while cursor < len(ordered):
            count = min(LAYOUTS[page_in_theme % len(LAYOUTS)], len(ordered) - cursor)
            c.setFillColor(white)
            c.rect(0, 0, PAGE, PAGE, fill=1, stroke=0)
            folio(c)
            place_page_images(c, [row["_path"] for row in ordered[cursor:cursor + count]], page_in_theme)
            c.showPage()
            cursor += count
            page_in_theme += 1
    c.setFillColor(white)
    c.rect(0, 0, PAGE, PAGE, fill=1, stroke=0)
    c.showPage()
    c.save()


def add_type(layout_pdf, output, groups, title, font_path):
    doc = pymupdf.open(layout_pdf)
    font = pymupdf.Font(fontfile=str(font_path))
    physical = 1
    for page in doc:
        page.insert_font(fontname="Pecita", fontfile=str(font_path))
        if physical == 1:
            cover_title = title.replace(" ", "\n", 1)
            for size in range(31, 19, -1):
                if page.insert_textbox(pymupdf.Rect(468, 617, 703, 704), cover_title,
                                       fontname="Pecita", fontsize=size, lineheight=1.0,
                                       color=(1, 1, 1), align=2) >= 0:
                    break
            else:
                raise ValueError("Cover title does not fit in the title area")
        elif physical < len(doc):
            size = 12
            baseline = 34.5 + (font.ascender + font.descender) * size / 2
            label = str(physical)
            x = 25 + (42 - font.text_length(label, fontsize=size)) / 2
            page.insert_text((x, baseline), label, fontname="Pecita", fontsize=size,
                             color=(0.14, 0.14, 0.14))
            if physical in groups:
                for heading_size in range(42, 23, -1):
                    if page.insert_textbox(pymupdf.Rect(86, 505, 650, 590), groups[physical],
                                           fontname="Pecita", fontsize=heading_size, lineheight=1.0,
                                           color=(0.15, 0.15, 0.14)) >= 0:
                        break
                else:
                    raise ValueError(f"Theme title does not fit: {groups[physical]}")
        physical += 1
    doc.set_metadata({"title": title, "author": "Photobook"})
    doc.save(output, garbage=4, deflate=True, deflate_fonts=True)
    doc.close()


def build(manifest, photos, output, cover, title, font_path, theme_order=None,
          mono_title="Monochrome Studies", interior_title="Interiors in Color",
          nature_title="Earth, Water, Weather", people_title="Human Presence"):
    groups = group_rows(manifest.resolve(), photos.resolve(), mono_title, interior_title,
                        nature_title, people_title)
    if theme_order:
        requested = [name.strip() for name in theme_order.split(";") if name.strip()]
        unknown = set(groups) - set(requested)
        if unknown:
            requested.extend(theme for theme in groups if theme not in requested)
        groups = OrderedDict((name, groups[name]) for name in requested if name in groups)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    layout_pdf = output.with_name(output.stem + ".layout.pdf")
    # Cover is page 1; each divider is followed by its section's image pages.
    divider_pages = {}
    physical = 2
    for theme, rows in groups.items():
        divider_pages[physical] = theme
        remaining = len(rows)
        layout_index = 0
        while remaining:
            count = min(LAYOUTS[layout_index % len(LAYOUTS)], remaining)
            remaining -= count
            physical += 1
            layout_index += 1
        physical += 1
    compose(layout_pdf, groups, cover, title)
    add_type(layout_pdf, output, divider_pages, title, font_path.resolve())
    layout_pdf.unlink()
    print(f"Created {output}: {physical} pages including cover and back; "
          f"{sum(map(len, groups.values()))} unique photos in {len(groups)} themes.")


def main():
    script_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Reviewed photos.csv from prepare_photobook.py")
    parser.add_argument("photos", type=Path, help="Extracted source photo folder")
    parser.add_argument("output", type=Path, help="Destination PDF file")
    parser.add_argument("--cover", type=Path, help="Optional cover image; full image is fitted on black")
    parser.add_argument("--title", default="The Shape of Looking")
    parser.add_argument("--font", type=Path, default=script_root / "assets" / "Pecita.otf")
    parser.add_argument("--theme-order", help="Comma-separated section titles in reading order")
    parser.add_argument("--mono-title", default="Monochrome Studies")
    parser.add_argument("--interior-title", default="Interiors in Color")
    parser.add_argument("--nature-title", default="Earth, Water, Weather")
    parser.add_argument("--people-title", default="Human Presence")
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error(f"Font file not found: {args.font}")
    build(args.manifest, args.photos, args.output, args.cover, args.title, args.font,
          args.theme_order, args.mono_title, args.interior_title,
          args.nature_title, args.people_title)


if __name__ == "__main__":
    main()
