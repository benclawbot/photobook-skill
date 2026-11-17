# Photobook skill

A Codex skill and small Python toolkit for turning a supplied photo collection into a curated, varied-layout photobook PDF.

## Install

Copy this folder into your Codex skills directory. Install the Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Workflow

1. Extract the source archive into a photo folder. Keep the generated work folder outside that folder.
2. Inventory the images and generate contact sheets plus a CSV manifest:

   ```bash
   python scripts/prepare_photobook.py path/to/photos work/photobook
   ```

   `photos.csv` contains each exact-unique image, stable sequence, SHA-256, dimensions, mean saturation, and a `mono_suggested` review hint. Exact duplicate copies are listed in `duplicates.csv` and omitted from the manifest. Contact sheet labels point to the `sequence` column.
3. Review every contact sheet and edit `photos.csv`. Set `monochrome`, `interior`, `nature`, or `people` to `yes` only after visual review. Put a section name in `theme` for all remaining images. Reorder `sequence` within a section to set the photo flow. The saturation hint only flags possible monochromes; it does not classify them automatically.
4. Build the PDF from the reviewed manifest:

   ```bash
   python scripts/build_photobook.py work/photobook/photos.csv path/to/photos output/photobook.pdf --cover path/to/cover.jpg --title "The Shape of Looking" --theme-order "Monochrome Studies;Interiors in Color;Earth, Water, Weather;Human Presence"
   ```

   If using PowerShell, keep the `--theme-order` value quoted as one argument. Separate titles with semicolons. Without an explicit order, sections follow the order they first appear in the CSV.

## Grouping logic

The builder resolves overlapping flags with this default priority:

1. `monochrome=yes` → **Monochrome Studies**
2. `interior=yes` → **Interiors in Color**
3. `nature=yes` → **Earth, Water, Weather**
4. `people=yes` → **Human Presence**
5. Otherwise use the manually reviewed `theme` value.

This puts monochrome interiors in the monochrome section and color interiors in the interior section. Rename these section titles with `--mono-title`, `--interior-title`, `--nature-title`, or `--people-title`. Change the priority in `group_rows()` only when the project brief requires a different rule. Theme names must be based on the photos' visible content; use contact sheets to correct any false assignments.

The PDF uses a square page, a full-image cover fitted on black, Pecita typography, section dividers, centered folio numerals that match physical PDF page numbers, and a repeating 1/2/3/4-image layout rhythm. Edit `PAGE` and `LAYOUTS` in `scripts/build_photobook.py` only when a different format is requested.

## Font and PDF checks

The bundled `assets/Pecita.otf` is licensed under the SIL Open Font License 1.1; see `assets/OFL.txt`. The builder embeds Pecita. After building, render the output pages and inspect the cover, all dividers, and contact sheets of the full book. Check theme accuracy, photo coverage, page order, page labels, font appearance, and clipping before delivery.
