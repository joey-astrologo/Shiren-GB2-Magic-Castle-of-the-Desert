#!/usr/bin/env python3
"""Audit the complete English help, Secrets, and Monster Notebook domains.

These menu families live in seven pointer groups and contain several aliases plus
eighteen deliberately empty Monster Notebook slots.  This module resolves the domains
from the ROM reference graph, proves every real record has an English override,
and measures the authored text with the production VWF.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

import codec
import english_font
import extract
import layout
import translations as translation_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSLATIONS = ROOT / "script" / "en"
SCHEMA = "shiren-gb2-menu-text-v2"
CANVAS_PIXELS = layout.CANVAS_WIDTH_PIXELS
POSITIONED_PIXELS = CANVAS_PIXELS - 3


class MenuTextError(ValueError):
    """A menu text family is incomplete or violates its display contract."""


@dataclass(frozen=True)
class FamilySpec:
    name: str
    groups: tuple
    nonempty_only: bool = False


FAMILIES = (
    FamilySpec("control_help", (20,)),
    FamilySpec("technique_help", (21,)),
    FamilySpec("wanderers_guide", (19,)),
    FamilySpec("wanderer_secret_pages", (32,)),
    FamilySpec("monster_notebook_descriptions", (29, 30, 31), nonempty_only=True),
)

POSITIONED_TOPICS = (
    ("wanderers_guide", 19, 0, 9),
    ("control_help", 20, 0, 8),
    ("technique_help", 21, 0, 15),
)

POSITIONED_HEADERS = (
    ("help_popup_controls", 7, 113, 40),
    ("help_popup_techniques", 7, 114, 40),
    ("help_popup_secrets", 7, 115, 40),
    ("control_help_heading", 7, 117, POSITIONED_PIXELS),
)


def _group_rows(result, groups):
    rows = []
    for record in result["records"]:
        for reference in record.references:
            if reference.group in groups:
                rows.append((reference.group, reference.index, record))
    return tuple(sorted(rows, key=lambda row: (row[0], row[1], row[2].id)))


def resolve_families(result):
    """Return logical rows and stable records for every audited family."""
    out = {}
    owners = {}
    for spec in FAMILIES:
        logical_rows = _group_rows(result, spec.groups)
        if not logical_rows:
            raise MenuTextError("groups %s have no records" % (spec.groups,))
        records = []
        seen_records = set()
        for _group, _index, record in logical_rows:
            if spec.nonempty_only and not record.raw:
                continue
            if record.id not in seen_records:
                records.append(record)
                seen_records.add(record.id)
        if not records:
            raise MenuTextError("family %s has no records" % spec.name)
        for record in records:
            previous = owners.setdefault(record.id, spec.name)
            if previous != spec.name:
                raise MenuTextError(
                    "record %s crosses families %s and %s"
                    % (record.id, previous, spec.name)
                )
        out[spec.name] = {
            "spec": spec,
            "logical_rows": logical_rows,
            "records": tuple(records),
        }
    return out


def _membership_sha1(records):
    digest = sha1()
    for record in records:
        digest.update(record.id.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _translation_sha1(families, translated):
    digest = sha1()
    for spec in FAMILIES:
        digest.update(spec.name.encode("ascii"))
        digest.update(b"\0")
        for record in families[spec.name]["records"]:
            entry = translated[(record.bank, record.address)]
            digest.update(record.id.encode("ascii"))
            digest.update(b"\0")
            digest.update(entry.text.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def _critical_controls(data):
    """Return controls that affect runtime content, pacing, or canvas resets."""
    out = []
    for token in codec.parse_source(data):
        if token.kind == "source_control" or token.code in (0xF3, 0xFB, 0xFC):
            out.append(token.raw.hex().upper())
    return tuple(out)


def _line_count(data):
    return data.count(bytes((0xFD,))) + 1


def analyze(rom, result, translated):
    """Validate the production menu translations and return a fixture summary."""
    families = resolve_families(result)
    font_rom = english_font.install(rom)
    family_summaries = {}
    total_records = 0

    for spec in FAMILIES:
        family = families[spec.name]
        records = family["records"]
        logical_rows = family["logical_rows"]
        missing = [
            record.id
            for record in records
            if (record.bank, record.address) not in translated
            or not translated[(record.bank, record.address)].text
        ]
        if missing:
            raise MenuTextError(
                "%s is missing %d translation(s); first: %s"
                % (spec.name, len(missing), missing[0])
            )

        widest = None
        max_lines = 0
        for record in records:
            entry = translated[(record.bank, record.address)]
            if _critical_controls(entry.encoded) != _critical_controls(record.raw):
                raise MenuTextError(
                    "%s changes critical controls in %s" % (spec.name, record.id)
                )
            english_lines = _line_count(entry.encoded)
            source_lines = _line_count(record.raw)
            if (
                spec.name != "monster_notebook_descriptions"
                and english_lines > source_lines
            ):
                raise MenuTextError(
                    "%s uses %d lines but its source uses %d"
                    % (record.id, english_lines, source_lines)
                )
            measured = layout.source_layout(
                font_rom,
                entry.encoded,
                mode=0x02,
                record_id=record.id,
            )
            # These are full-screen help/tutorial canvases, so the generic
            # dialogue mode's three-line limit does not apply.  Width and
            # unresolved runtime content still fail closed; vertical safety is
            # bounded separately against each native record below.
            if (
                measured.unresolved_dynamic_offsets
                or measured.composer_overflows
                or measured.renderer_overflows
            ):
                raise MenuTextError("%s does not fit its text canvas" % record.id)
            max_lines = max(max_lines, english_lines)
            for line_number, line in enumerate(measured.lines):
                candidate = {
                    "record": record.id,
                    "line": line_number,
                    "composer_pixels": line.composer_pixels,
                    "renderer_pixels": line.renderer_pixels,
                }
                if widest is None or (
                    candidate["renderer_pixels"], candidate["composer_pixels"]
                ) > (widest["renderer_pixels"], widest["composer_pixels"]):
                    widest = candidate

            if spec.name == "monster_notebook_descriptions":
                undefined_bug = codec.decode_source(record.raw) == "みていぎ（バグ）"
                expected_lines = 1 if undefined_bug else 2
                if english_lines != expected_lines or len(measured.lines) != expected_lines:
                    raise MenuTextError(
                        "%s must use %d Notebook line(s)"
                        % (record.id, expected_lines)
                    )

        target_ids = {record.id for record in records}
        logical_target_rows = [
            row for row in logical_rows if row[2].id in target_ids
        ]
        total_records += len(records)
        family_summaries[spec.name] = {
            "groups": list(spec.groups),
            "logical_references": len(logical_target_rows),
            "stable_records": len(records),
            "translated_records": len(records),
            "first_id": records[0].id,
            "last_id": records[-1].id,
            "membership_sha1": _membership_sha1(records),
            "max_lines": max_lines,
            "widest": widest,
        }

    notebook_rows = families["monster_notebook_descriptions"]["logical_rows"]
    empty_records = []
    for _group, _index, record in notebook_rows:
        if record.raw or record.id in empty_records:
            continue
        empty_records.append(record.id)
        entry = translated.get((record.bank, record.address))
        if entry is not None and (
            not entry.explicit_empty or entry.text or entry.encoded
        ):
            raise MenuTextError(
                "native empty Notebook slot %s must remain empty" % record.id
            )

    by_reference = {
        (reference.group, reference.index): record
        for record in result["records"]
        for reference in record.references
    }
    positioned = {}
    for name, group, first_index, last_index in POSITIONED_TOPICS:
        rows = []
        for index in range(first_index, last_index + 1):
            record = by_reference[(group, index)]
            entry = translated[(record.bank, record.address)]
            measured = layout.source_layout(font_rom, entry.encoded, mode=0x02)
            composer = max(line.composer_pixels for line in measured.lines)
            renderer = max(line.renderer_pixels for line in measured.lines)
            if composer > POSITIONED_PIXELS or renderer > POSITIONED_PIXELS:
                raise MenuTextError(
                    "%s topic %s exceeds its %dpx list budget"
                    % (name, record.id, POSITIONED_PIXELS)
                )
            rows.append((record.id, composer, renderer))
        widest = max(rows, key=lambda row: (row[2], row[1]))
        positioned[name] = {
            "entries": len(rows),
            "pixel_budget": POSITIONED_PIXELS,
            "widest": {
                "record": widest[0],
                "composer_pixels": widest[1],
                "renderer_pixels": widest[2],
            },
        }

    positioned_headers = {}
    for name, group, index, pixel_budget in POSITIONED_HEADERS:
        record = by_reference[(group, index)]
        key = (record.bank, record.address)
        if key not in translated or not translated[key].text:
            raise MenuTextError("%s is missing translation %s" % (name, record.id))
        measured = layout.source_layout(font_rom, translated[key].encoded, mode=0x08)
        composer = max(line.composer_pixels for line in measured.lines)
        renderer = max(line.renderer_pixels for line in measured.lines)
        if composer > pixel_budget or renderer > pixel_budget:
            raise MenuTextError(
                "%s exceeds its %dpx positioned budget" % (name, pixel_budget)
            )
        positioned_headers[name] = {
            "record": record.id,
            "text": translated[key].text,
            "pixel_budget": pixel_budget,
            "composer_pixels": composer,
            "renderer_pixels": renderer,
        }

    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "families": family_summaries,
        "help_and_secrets_records": sum(
            family_summaries[spec.name]["stable_records"]
            for spec in FAMILIES
            if spec.name != "monster_notebook_descriptions"
        ),
        "monster_notebook_records": family_summaries[
            "monster_notebook_descriptions"
        ]["stable_records"],
        "total_translated_records": total_records,
        "native_empty_notebook_slots": empty_records,
        "positioned_topics": positioned,
        "positioned_headers": positioned_headers,
        "translation_sha1": _translation_sha1(families, translated),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--translations",
        default=str(DEFAULT_TRANSLATIONS),
        help="English TSV or category directory (default: script/en)",
    )
    args = parser.parse_args(argv)
    try:
        rom = Path(args.rom).read_bytes()
        result = extract.extract(rom)
        translated = translation_file.load_path(args.translations, result["records"])
        measured = analyze(rom, result, translated)
    except (
        OSError,
        english_font.FontError,
        extract.ExtractError,
        layout.LayoutError,
        MenuTextError,
        translation_file.TranslationError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print(json.dumps(measured, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
