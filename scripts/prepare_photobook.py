#!/usr/bin/env python3
"""Inventory photos, flag monochrome candidates, and make labeled contact sheets."""
import argparse
import csv
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, ImageStat

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mean_saturation(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((32, 32))
        hsv = image.convert("HSV")
        return ImageStat.Stat(hsv.getchannel("S")).mean[0] / 255


def contact_sheets(rows, root, out, per_sheet=80):
    thumbs = []
    for row in rows:
        path = root / row["file"]
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((132, 112))
                thumbs.append((row["sequence"], row["file"], image.copy()))
        except Exception as error:
            raise ValueError(f"Cannot read {path}: {error}") from error
    out.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(thumbs), per_sheet):
        batch = thumbs[start:start + per_sheet]
        cols, cw, ch = 6, 160, 145
        sheet = Image.new("RGB", (cols * cw, ((len(batch) + cols - 1) // cols) * ch), "white")
        draw = ImageDraw.Draw(sheet)
        for index, (number, filename, image) in enumerate(batch):
            x, y = (index % cols) * cw, (index // cols) * ch
            sheet.paste(image, (x + (cw - image.width) // 2, y))
            draw.text((x + 4, y + 116), f"#{number}", fill="#222222")
        sheet.save(out / f"contact-{start // per_sheet + 1:03}.jpg", quality=88)


def prepare(source, output):
    source, output = source.resolve(), output.resolve()
    if not source.is_dir():
        raise ValueError(f"Photo folder does not exist: {source}")
    exclude_output = output != source and output.is_relative_to(source)
    files = sorted((p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
                    and not (exclude_output and p.resolve().is_relative_to(output))),
                   key=lambda p: p.relative_to(source).as_posix().casefold())
    if not files:
        raise ValueError(f"No supported images found in {source}")
    rows, duplicates, hashes = [], [], {}
    for path in files:
        sha = digest(path)
        rel = path.relative_to(source).as_posix()
        if sha in hashes:
            duplicates.append({"duplicate_file": rel, "canonical_file": hashes[sha], "sha256": sha})
            continue
        hashes[sha] = rel
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            width, height = im.size
        saturation = mean_saturation(path)
        rows.append({"sequence": len(rows) + 1, "file": rel, "sha256": sha,
                     "width": width, "height": height,
                     "mean_saturation": f"{saturation:.4f}",
                     "mono_suggested": "review" if saturation <= 0.06 else "",
                     "monochrome": "", "interior": "", "nature": "", "people": "",
                     "theme": ""})
    output.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (output / "photos.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (output / "duplicates.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["duplicate_file", "canonical_file", "sha256"])
        writer.writeheader()
        writer.writerows(duplicates)
    contact_sheets(rows, source, output / "contact-sheets")
    print(f"Prepared {len(rows)} unique photos; found {len(duplicates)} exact duplicates.")
    print(f"Review contact sheets in {output / 'contact-sheets'} and edit {output / 'photos.csv'}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", type=Path, help="Folder of extracted source images")
    parser.add_argument("output", type=Path, help="Folder for CSV manifests and contact sheets")
    args = parser.parse_args()
    prepare(args.photos, args.output)


if __name__ == "__main__":
    main()
