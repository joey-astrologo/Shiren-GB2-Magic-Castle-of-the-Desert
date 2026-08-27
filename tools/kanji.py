#!/usr/bin/env python3
"""Build and inspect the referenced Shiren GB2 prefixed-glyph inventory.

This is a mapping workbench, not the final table. It ties each code to the exact font
pixels and to source-composer-aware contexts so visually ambiguous glyphs can be proven
from language rather than guessed.

    kanji.py <rom> --list
    kanji.py <rom> --code F19E
    kanji.py <rom> --sheets build/kanji-review
    kanji.py <rom> --unmapped-sheets build/kanji-unmapped
"""
import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codec
import extract as script_extract
import font


def inventory(rom):
    """Return code counts and contexts from the authoritative pointer corpus."""
    counts = Counter()
    contexts = defaultdict(list)
    result = script_extract.extract(rom)
    for record in result["records"]:
        tokens = codec.parse_source(record.raw)
        for index, token in enumerate(tokens):
            if token.kind != "kanji":
                continue
            code = token.raw.hex().upper()
            counts[code] += 1
            if len(contexts[code]) < 12:
                left = max(0, index - 16)
                right = min(len(tokens), index + 17)
                snippet = codec.decode_source(codec.serialize(tokens[left:right]))
                contexts[code].append((record.id, snippet))
    return counts, contexts


def _review_sheet(rom, codes, title):
    from PIL import Image, ImageDraw

    columns = 6
    cell_w, cell_h = 112, 88
    header_h = 28
    rows = (len(codes) + columns - 1) // columns
    image = Image.new("RGB", (columns * cell_w, header_h + rows * cell_h), "white")
    draw = ImageDraw.Draw(image)
    draw.text((6, 7), "%s — %d observed codes" % (title, len(codes)), fill="black")
    for index, code in enumerate(codes):
        x = (index % columns) * cell_w
        y = header_h + (index // columns) * cell_h
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline=(210, 210, 210))
        draw.text((x + 5, y + 4), code, fill="black")
        glyph = font.read_glyph(rom, bytes.fromhex(code))
        rendered = font.render_glyph_image(glyph, scale=5, padding=1).convert("RGB")
        image.paste(rendered, (x + 38, y + 5))
    return image


def write_review_sheets(rom, output_dir):
    counts, _contexts = inventory(rom)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for prefix in ("F0", "F1", "F2"):
        codes = sorted(code for code in counts if code.startswith(prefix))
        path = output_dir / (prefix.lower() + "-observed.png")
        _review_sheet(rom, codes, prefix).save(path)
        paths.append(path)
    return paths


def write_unmapped_review(rom, output_dir):
    """Write a focused sheet and context TSV for valid referenced unmapped glyphs."""
    counts, contexts = inventory(rom)
    codes = [
        code
        for code in sorted(counts)
        if bytes.fromhex(code) not in codec.KANJI
        and font.read_glyph(rom, bytes.fromhex(code)).width >= 4
    ]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = output_dir / "unmapped.png"
    contexts_path = output_dir / "contexts.tsv"
    _review_sheet(rom, codes, "Referenced unmapped").save(sheet_path)
    with contexts_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("code", "count", "width", "record", "context"))
        for code in codes:
            glyph = font.read_glyph(rom, bytes.fromhex(code))
            for record_id, snippet in contexts[code]:
                writer.writerow((code, counts[code], glyph.width, record_id, snippet))
    return sheet_path, contexts_path


def _print_code(rom, code, counts, contexts):
    if code not in counts:
        raise SystemExit("%s is not an observed kanji code" % code)
    glyph = font.read_glyph(rom, bytes.fromhex(code))
    mapped = codec.KANJI.get(bytes.fromhex(code), "unmapped continuation")
    print("%s\t%d occurrence(s)\twidth %d\t%s"
          % (code, counts[code], glyph.width, mapped))
    for record_id, snippet in contexts[code]:
        print("  %s  %s" % (record_id, snippet))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="print every observed code and count")
    group.add_argument("--code", help="print representative contexts for one code, e.g. F19E")
    group.add_argument("--sheets", metavar="DIR", help="write labeled observed-glyph sheets")
    group.add_argument(
        "--unmapped-sheets",
        metavar="DIR",
        help="write a focused valid-unmapped sheet and context TSV",
    )
    args = parser.parse_args(argv)

    rom = Path(args.rom).read_bytes()
    font.verify_regions(rom)
    if args.sheets:
        for path in write_review_sheets(rom, args.sheets):
            print(path)
        return 0
    if args.unmapped_sheets:
        for path in write_unmapped_review(rom, args.unmapped_sheets):
            print(path)
        return 0
    counts, contexts = inventory(rom)
    if args.code:
        _print_code(rom, args.code.upper(), counts, contexts)
    else:
        for code in sorted(counts):
            glyph = font.read_glyph(rom, bytes.fromhex(code))
            encoded = bytes.fromhex(code)
            print("%s\t%d\twidth=%d\t%s\t%s"
                  % (code, counts[code], glyph.width,
                     codec.KANJI_KIND.get(encoded, "continuation"),
                     codec.KANJI.get(encoded, "-")))
        print("TOTAL\t%d codes\t%d occurrences" % (len(counts), sum(counts.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
