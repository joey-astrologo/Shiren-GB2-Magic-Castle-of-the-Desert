#!/usr/bin/env python3
"""Reflow item-description line breaks without shortening their English.

Group 6 uses the proven mode-$08 full-screen surface: 11 composer lines and
an 18-tile (144-pixel) canvas.  This tool preserves the title/stat header and
every visible body character, replacing only body spaces/``<br>`` boundaries
with greedily measured line breaks.  ROM storage is deliberately outside its
scope; the far-pointer allocator handles description length independently.
"""

import argparse
import csv
from pathlib import Path
import sys

import english
import english_font
import layout
import wrap_en


class ItemWrapError(ValueError):
    """An item description cannot be reflowed on the proven surface."""


def visible_words(text):
    """Normalize only line-boundary whitespace for content-preservation checks."""
    return " ".join(text.replace("<br>", " ").split())


def _is_stat_line(text):
    return text.startswith(("Atk ", "Def ", "Slots "))


def wrap_description(font_rom, text, record_id):
    """Return a mode-$08-safe description with identical visible content."""
    pieces = text.split("<br>")
    headers = [pieces.pop(0)]
    while pieces and _is_stat_line(pieces[0]):
        headers.append(pieces.pop(0))

    body = " ".join(piece for piece in pieces if piece)
    wrapped_body = []
    if body:
        try:
            wrapped_body = list(
                wrap_en._wrap_paragraph_greedy(
                    font_rom,
                    body,
                    record_id,
                    layout.english_runtime_width_contract(),
                )
            )
        except wrap_en.WrapError as exc:
            raise ItemWrapError(str(exc)) from exc

    wrapped = "<br>".join(headers + wrapped_body)
    if visible_words(wrapped) != visible_words(text):
        raise ItemWrapError("%s wrapping changed visible English" % record_id)
    measured = layout.source_layout(
        font_rom, english.encode_source(wrapped), mode=0x08, record_id=record_id
    )
    if not measured.safe:
        raise ItemWrapError("%s does not fit the mode-$08 surface" % record_id)
    return wrapped


def wrap_rows(font_rom, rows):
    out = []
    for row in rows:
        updated = dict(row)
        updated["english"] = wrap_description(font_rom, row["english"], row["id"])
        out.append(updated)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original or translated Shiren GB2 ROM")
    parser.add_argument("input", help="compact or rich item TSV")
    parser.add_argument("output", help="destination item TSV; may equal input")
    args = parser.parse_args(argv)

    source = Path(args.input)
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    if not fields or not {"id", "english"} <= set(fields):
        parser.error("item TSV must contain id and english columns")

    try:
        font_rom = english_font.install(Path(args.rom).read_bytes())
        wrapped = wrap_rows(font_rom, rows)
    except (OSError, english_font.FontError, ItemWrapError, ValueError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    destination = Path(args.output)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(wrapped)
    temporary.replace(destination)
    changed = sum(a["english"] != b["english"] for a, b in zip(rows, wrapped))
    print("%d description(s); %d rewrapped; visible English unchanged" % (len(rows), changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
