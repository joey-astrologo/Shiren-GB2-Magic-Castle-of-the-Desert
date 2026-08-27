#!/usr/bin/env python3
"""Derive safe F6 substitution widths from completed English term domains.

F6 itself carries no useful length.  The runtime-term inventory classifies each
consumer, while this module connects those classes to their authoritative
translated directory families.  A domain receives a bound only when every
unique source record in every required family has an explicit English value.
Blank means incomplete; ``<empty>`` is an intentional zero-width translation.

Composed item names have three mutually exclusive shapes proven by the formatter
at 120:$47E9: an identified group-4 name, an unidentified group-5 appearance, or
a group-11 class fragment followed by an FF-terminated custom-name slot.  The 20
slots at WRAM $DD78 are eight bytes each, hence at most seven English glyph bytes
plus the terminator.  The bound is the maximum of those three shapes, not the sum
of every item family.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys
from typing import Optional

import codec
import english
import english_font
import extract
import layout
import runtime_terms
import translations as translation_file


SCHEMA = "shiren-gb2-runtime-widths-v1"
CUSTOM_ITEM_NAME_SLOTS = 20
CUSTOM_ITEM_NAME_SLOT_BYTES = 8
CUSTOM_ITEM_NAME_MAX_BYTES = CUSTOM_ITEM_NAME_SLOT_BYTES - 1

WIDTH_FAMILY_NAMES = (
    "actor_name_tier_1",
    "actor_name_tier_2",
    "actor_name_tier_3",
    "identified_item_names",
    "unidentified_item_appearances",
    "item_name_format_fragments",
    "trap_names",
    "location_names_primary",
    "location_names_history",
)

DOMAIN_FAMILIES = {
    "actor_name": (
        "actor_name_tier_1",
        "actor_name_tier_2",
        "actor_name_tier_3",
    ),
    "trap_name": ("trap_names",),
    "identified_item_name": ("identified_item_names",),
    "location_name": ("location_names_primary", "location_names_history"),
    "item_name": (
        "identified_item_names",
        "unidentified_item_appearances",
        "item_name_format_fragments",
    ),
    "location_record": ("location_names_primary", "location_names_history"),
    "sender_string": (),
    "debug_polymorphic": (),
}

PERMANENTLY_UNRESOLVED = frozenset({"debug_polymorphic"})

FORMATTER_ANCHORS = (
    (0x78, 0x47E9, 0x37, "three-way item name formatter"),
    (0x78, 0x4C09, 0x10, "eight-byte custom-name slot resolver"),
    (0x7A, 0x4229, 0x0A, "clear twenty custom-name slots"),
)


class RuntimeWidthError(ValueError):
    """Translated runtime terms cannot form a safe width contract."""


@dataclass(frozen=True)
class WidthMaximum:
    composer_pixels: int
    renderer_pixels: int
    composer_record_id: str
    renderer_record_id: str


@dataclass(frozen=True)
class FamilyStatus:
    name: str
    entries: int
    record_ids: tuple
    membership_sha1: str
    translated_records: int
    missing_record_ids: tuple
    maximum: Optional[WidthMaximum]

    @property
    def complete(self):
        return not self.missing_record_ids


@dataclass(frozen=True)
class DomainStatus:
    name: str
    families: tuple
    missing_record_ids: tuple
    permanently_unresolved: bool
    maximum: Optional[WidthMaximum]

    @property
    def ready(self):
        return self.maximum is not None


@dataclass(frozen=True)
class RuntimeWidthAnalysis:
    families: dict
    domains: dict
    f6_bounds: dict
    consumer_occurrences: dict
    consumer_records: dict
    player_name_maximum: WidthMaximum
    custom_item_name_maximum: WidthMaximum

    @property
    def contract(self):
        return layout.english_runtime_width_contract(self.f6_bounds)


def _record_map(result):
    by_target = {
        (record.bank, record.address): record for record in result["records"]
    }
    return {
        (reference.group, reference.index): by_target[
            (reference.target_bank, reference.target_address)
        ]
        for reference in result["references"]
    }


def _family_rows(result, family):
    records = _record_map(result)
    rows = []
    digest = sha1()
    for index in range(family.start_index, family.end_index + 1):
        try:
            record = records[(family.group, index)]
        except KeyError as exc:
            raise RuntimeWidthError(
                "missing group %d index %d for %s"
                % (family.group, index, family.name)
            ) from exc
        rows.append(record)
        digest.update(family.group.to_bytes(1, "little"))
        digest.update(index.to_bytes(2, "little"))
        digest.update(record.id.encode("ascii"))
        digest.update(b"\0")
    unique = tuple(dict.fromkeys(record.id for record in rows))
    return tuple(rows), unique, digest.hexdigest()


def _measure_codes(font_rom, codes, label):
    composer = max(layout.composer_advance(font_rom, bytes((code,))) for code in codes)
    renderer = max(layout.renderer_advance(font_rom, bytes((code,))) for code in codes)
    return WidthMaximum(composer, renderer, label, label)


def _measure_translation(font_rom, translation):
    if translation.explicit_empty:
        return 0, 0
    tokens = codec.parse_source(translation.encoded)
    if any(token.kind not in ("glyph", "kanji") for token in tokens):
        raise RuntimeWidthError(
            "%s runtime term contains a control or substitution"
            % translation.record_id
        )
    measured = layout.source_layout(font_rom, translation.encoded)
    if len(measured.lines) != 1 or measured.dynamic_offsets:
        raise RuntimeWidthError(
            "%s runtime term is not one static line" % translation.record_id
        )
    line = measured.lines[0]
    return line.composer_pixels, line.renderer_pixels


def _maximum(font_rom, records, translated):
    rows = []
    for record in records:
        entry = translated[(record.bank, record.address)]
        composer, renderer = _measure_translation(font_rom, entry)
        rows.append((record.id, composer, renderer))
    composer_row = max(rows, key=lambda row: (row[1], row[0]))
    renderer_row = max(rows, key=lambda row: (row[2], row[0]))
    return WidthMaximum(
        composer_row[1], renderer_row[2], composer_row[0], renderer_row[0]
    )


def _family_statuses(font_rom, result, translated):
    definitions = {family.name: family for family in runtime_terms.TERM_FAMILIES}
    out = {}
    for name in WIDTH_FAMILY_NAMES:
        family = definitions[name]
        rows, record_ids, membership = _family_rows(result, family)
        by_id = {record.id: record for record in rows}
        missing = tuple(
            record_id
            for record_id in record_ids
            if (by_id[record_id].bank, by_id[record_id].address) not in translated
        )
        present = tuple(
            by_id[record_id] for record_id in record_ids if record_id not in missing
        )
        for record in present:
            _measure_translation(
                font_rom, translated[(record.bank, record.address)]
            )
        maximum = None
        if not missing:
            maximum = _maximum(font_rom, present, translated)
        out[name] = FamilyStatus(
            name=name,
            entries=len(rows),
            record_ids=record_ids,
            membership_sha1=membership,
            translated_records=len(record_ids) - len(missing),
            missing_record_ids=missing,
            maximum=maximum,
        )
    return out


def _max_of(maxima):
    maxima = tuple(maxima)
    composer = max(maxima, key=lambda item: (item.composer_pixels, item.composer_record_id))
    renderer = max(maxima, key=lambda item: (item.renderer_pixels, item.renderer_record_id))
    return WidthMaximum(
        composer.composer_pixels,
        renderer.renderer_pixels,
        composer.composer_record_id,
        renderer.renderer_record_id,
    )


def _sum_maximum(first, second, label):
    return WidthMaximum(
        first.composer_pixels + second.composer_pixels,
        first.renderer_pixels + second.renderer_pixels,
        "%s+%s" % (first.composer_record_id, label),
        "%s+%s" % (first.renderer_record_id, label),
    )


def _domain_statuses(families, player_maximum, custom_maximum):
    out = {}
    for name, required in DOMAIN_FAMILIES.items():
        missing = tuple(
            record_id
            for family_name in required
            for record_id in families[family_name].missing_record_ids
        )
        permanent = name in PERMANENTLY_UNRESOLVED
        maximum = None
        if not missing and not permanent:
            if name in ("actor_name",):
                maximum = _max_of(
                    [families[family].maximum for family in required]
                    + [player_maximum]
                )
            elif name in ("sender_string",):
                maximum = player_maximum
            elif name in ("item_name",):
                custom_shape = _sum_maximum(
                    families["item_name_format_fragments"].maximum,
                    custom_maximum,
                    "custom_name_7_bytes",
                )
                maximum = _max_of(
                    (
                        families["identified_item_names"].maximum,
                        families["unidentified_item_appearances"].maximum,
                        custom_shape,
                    )
                )
            else:
                maximum = _max_of(families[family].maximum for family in required)
        out[name] = DomainStatus(name, required, missing, permanent, maximum)
    return out


def _consumer_domain(record, token):
    if token.args[0] == 0x01:
        return runtime_terms.record_lookup_domain(record)
    if token.args[0] == 0x03:
        address = token.args[1] | token.args[2] << 8
        return runtime_terms.cached_string_domain(record, address)
    raise RuntimeWidthError(
        "%s uses unsupported F6 mode $%02X" % (record.id, token.args[0])
    )


def analyze(font_rom, result, translated):
    """Return completed family/domain maxima and per-consumer F6 bounds."""
    font_rom = bytes(font_rom)
    families = _family_statuses(font_rom, result, translated)
    english_codes = tuple(sorted(english.ENGLISH_CODES.values()))
    player_unit = _measure_codes(font_rom, english_codes, "player_name_byte")
    player_maximum = WidthMaximum(
        player_unit.composer_pixels * 7,
        player_unit.renderer_pixels * 7,
        "player_name_7_bytes",
        "player_name_7_bytes",
    )
    custom_maximum = WidthMaximum(
        player_unit.composer_pixels * CUSTOM_ITEM_NAME_MAX_BYTES,
        player_unit.renderer_pixels * CUSTOM_ITEM_NAME_MAX_BYTES,
        "custom_name_7_bytes",
        "custom_name_7_bytes",
    )
    domains = _domain_statuses(families, player_maximum, custom_maximum)

    occurrences = Counter()
    records = {}
    f6_bounds = {}
    for record in result["records"]:
        record_domains = set()
        for token in codec.parse_source(record.raw):
            if token.kind != "source_control" or token.code != 0xF6:
                continue
            domain_name = _consumer_domain(record, token)
            occurrences[domain_name] += 1
            record_domains.add(domain_name)
            maximum = domains[domain_name].maximum
            if maximum is None:
                continue
            key = (record.id, token.raw)
            bound = layout.RuntimeF6Bound(
                "f6_%s" % domain_name,
                maximum.composer_pixels,
                maximum.renderer_pixels,
            )
            previous = f6_bounds.get(key)
            if previous is not None and previous != bound:
                raise RuntimeWidthError(
                    "%s has ambiguous bounds for %s"
                    % (record.id, codec.source_control_text(token))
                )
            f6_bounds[key] = bound
        for domain_name in record_domains:
            records.setdefault(domain_name, set()).add(record.id)
    return RuntimeWidthAnalysis(
        families=families,
        domains=domains,
        f6_bounds=f6_bounds,
        consumer_occurrences=dict(sorted(occurrences.items())),
        consumer_records={
            name: len(values) for name, values in sorted(records.items())
        },
        player_name_maximum=player_maximum,
        custom_item_name_maximum=custom_maximum,
    )


def _maximum_summary(maximum):
    if maximum is None:
        return None
    return {
        "composer_pixels": maximum.composer_pixels,
        "renderer_pixels": maximum.renderer_pixels,
        "composer_evidence": maximum.composer_record_id,
        "renderer_evidence": maximum.renderer_record_id,
    }


def summary(rom, result, translated, analysis=None):
    """Return a source-free readiness and fixture report."""
    analysis = analyze(rom, result, translated) if analysis is None else analysis
    anchors = []
    for bank, address, size, purpose in FORMATTER_ANCHORS:
        at = extract.file_offset(bank, address)
        anchors.append(
            {
                "location": extract.location(bank, address),
                "purpose": purpose,
                "bytes": bytes(rom[at:at + size]).hex().upper(),
            }
        )
    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "source_free": True,
        "custom_item_names": {
            "slots": CUSTOM_ITEM_NAME_SLOTS,
            "slot_bytes": CUSTOM_ITEM_NAME_SLOT_BYTES,
            "maximum_glyph_bytes": CUSTOM_ITEM_NAME_MAX_BYTES,
            "maximum": _maximum_summary(analysis.custom_item_name_maximum),
        },
        "families": [
            {
                "name": status.name,
                "entries": status.entries,
                "unique_records": len(status.record_ids),
                "membership_sha1": status.membership_sha1,
                "translated_records": status.translated_records,
                "missing_records": len(status.missing_record_ids),
                "complete": status.complete,
                "maximum": _maximum_summary(status.maximum),
            }
            for status in analysis.families.values()
        ],
        "domains": [
            {
                "name": status.name,
                "families": list(status.families),
                "consumer_occurrences": analysis.consumer_occurrences.get(status.name, 0),
                "consumer_records": analysis.consumer_records.get(status.name, 0),
                "missing_records": len(status.missing_record_ids),
                "permanently_unresolved": status.permanently_unresolved,
                "ready": status.ready,
                "maximum": _maximum_summary(status.maximum),
            }
            for status in analysis.domains.values()
        ],
        "bounded_consumer_keys": len(analysis.f6_bounds),
        "formatter_anchors": anchors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--translations",
        default="script/en",
        help="English category directory or TSV (default: script/en)",
    )
    args = parser.parse_args(argv)
    try:
        source = Path(args.rom).read_bytes()
        result = extract.extract(source)
        translated = translation_file.load_path(args.translations, result["records"])
        font_rom = english_font.install(source)
        analysis = analyze(font_rom, result, translated)
        measured = summary(font_rom, result, translated, analysis=analysis)
    except (
        OSError,
        ValueError,
        extract.ExtractError,
        english_font.FontError,
        translation_file.TranslationError,
        RuntimeWidthError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print(json.dumps(measured, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
