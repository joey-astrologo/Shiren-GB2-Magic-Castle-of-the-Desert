#!/usr/bin/env python3
"""Export one translator TSV matching the bytes of a validated English build.

The output is a review sheet, not the browser workbench's changes format. It contains
all extracted records, including native internal records and intentional empty slots.
Existing files are never overwritten, so regenerating cannot erase spreadsheet edits.
"""
import argparse
from collections import Counter
import csv
import io
from pathlib import Path

import build
import codec
import english
import english_font
import extract
import lint_en
import menu_text
import runtime_widths
import translations
import insert


FIELDS = ("id", "loc", "bytes", "jp", "en", "edited_en")


def export_sheet(rom_path, translation_path, destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("%s already exists; use --out with a new filename" % destination)
    source = Path(rom_path).read_bytes()
    extracted = extract.extract(source)
    translated = translations.load_path(translation_path, extracted["records"])
    if not translated:
        raise ValueError("The translation input has no populated English records")
    exceptions = lint_en.load_exceptions(lint_en.default_exceptions_path(translation_path), extracted)
    lint_en.require_clean(extracted, translated, exceptions)
    analysis = runtime_widths.analyze(english_font.install(source), extracted, translated)
    output, allocation, validation = build.build_rom(
        source, translations.encoded_overrides(translated), runtime_contract=analysis.contract,
    )
    menu_text.analyze(source, extracted, translated)
    build._validate_blank_scroll_catalog(extracted, translated)
    build._validate_unidentified_name_catalog(extracted, translated)

    rows, counts = [], Counter()
    for record in extracted["records"]:
        key = (record.bank, record.address)
        reference = record.references[0]
        # Follow the built ROM's actual far pointer; do not export unwrapped drafts.
        raw = insert.read_source_record(output, reference.group, reference.index)
        entry = translated.get(key)
        expected = entry.encoded if entry is not None else record.raw
        if raw != expected:
            raise ValueError("%s does not match the inserted text" % record.id)
        encoder = english.encode_source if entry is not None else codec.encode_source
        # Keep byte-specific glyph aliases from the inserted catalogue: decoding
        # F1 82 to plain '%' and re-encoding with the English font would yield 58.
        text = entry.text if entry is not None else record.source
        if encoder(text) != raw:
            raise ValueError("%s does not round-trip to the inserted bytes" % record.id)
        placement = allocation.record_placements[key]
        rows.append({
            "id": record.id,
            "loc": extract.location(placement.output_bank, placement.output_address),
            "bytes": str(len(raw)),
            "jp": record.source,
            "en": text if raw else translations.EMPTY_SENTINEL,
            "edited_en": "",
        })
        counts["translated" if entry is not None else "native"] += 1
        if not raw:
            counts["empty"] += 1

    if len({row["id"] for row in rows}) != len(extracted["records"]):
        raise ValueError("The sheet does not cover every source record exactly once")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = stream.getvalue()
    if list(csv.DictReader(io.StringIO(content, newline=""), delimiter="\t")) != rows:
        raise ValueError("TSV serialization changed a source or English cell")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A UTF-8 signature helps spreadsheet programs recognize the Japanese text.
    with destination.open("x", encoding="utf-8-sig", newline="") as handle:
        handle.write(content)
    print("Wrote %s: %d records; %d English overrides; %d retained native; %d empty slots."
          % (destination, len(rows), counts["translated"], counts["native"], counts["empty"]))
    print("Verified every exported cell against the build; %d logical references passed validation."
          % validation["exact_references"])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="matching original Japanese ROM")
    parser.add_argument("translations", help="current build translation TSV or directory, normally script/en")
    parser.add_argument("--out", default="script/translator-review.tsv", help="new output filename")
    args = parser.parse_args()
    export_sheet(args.rom, args.translations, args.out)


if __name__ == "__main__":
    main()
