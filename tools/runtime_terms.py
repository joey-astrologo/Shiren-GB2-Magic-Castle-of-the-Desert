#!/usr/bin/env python3
"""Inventory GB2's runtime text substitutions and cached-string families.

Source F6 mode 1 resolves a group/index pair through the ordinary text
directory.  Mode 3 copies an FF-terminated string from a one-page WRAM cache.
That cache is generic: callers append directory records, formatted numbers and
composed item names.  This module freezes the call graph and the first proven
translation-critical directory families without pretending that every cache
value is an item name.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

import codec
import extract
import surfaces


F6_HANDLER = (0, 0x335E)
CACHE_RESET = (3, 0x5A2E)
CACHE_APPEND = (3, 0x5B1B)
CACHE_READ = (3, 0x5B33)
CACHE_BANK = 4
CACHE_BASE = 0xDE00
CACHE_CURSOR = 0xC532
PLAYER_NAME_SENTINEL = (1, 0xB0)
ITEM_BASE_RESOLVER = (0x78, 0x47E9)


@dataclass(frozen=True)
class OpcodeAnchor:
    bank: int
    address: int
    length: int
    purpose: str


OPCODE_ANCHORS = (
    OpcodeAnchor(0, 0x335E, 0x55, "F6 mode dispatch, cache read and lookup sentinel"),
    OpcodeAnchor(3, 0x5A2E, 0x3C, "clear both cache pages and reset the cursor"),
    OpcodeAnchor(3, 0x5B1B, 0x18, "append an FF-terminated string at DE00+cursor"),
    OpcodeAnchor(3, 0x5B33, 0x15, "read an FF-terminated string from DE00+offset"),
    OpcodeAnchor(0, 0x34FD, 0x13, "select a group-24 directory record and cache it"),
    OpcodeAnchor(0, 0x3530, 0x21, "format decimal text and cache it"),
    OpcodeAnchor(11, 0x7130, 0x21, "cache a sender string, compose an item name, then cache it"),
    OpcodeAnchor(17, 0x42CF, 0x78, "polymorphic value formatter branches before caching"),
    OpcodeAnchor(17, 0x4725, 0x2B, "encode a communication string at C16D and cache it"),
    OpcodeAnchor(17, 0x51AC, 0x12, "store a group-24 location lookup for rescue history"),
    OpcodeAnchor(0x78, 0x47C2, 0x15, "item structure wrappers format a name at C374"),
    OpcodeAnchor(0x78, 0x47E9, 0x37, "compose item names from groups 4, 5 and 11"),
    OpcodeAnchor(0x7A, 0x4437, 0x30, "long item wrapper formats before its cache append"),
)


@dataclass(frozen=True)
class TermFamily:
    name: str
    group: int
    start_index: int
    end_index: int
    role: str


# These are evidence-backed translation families encountered while tracing
# runtime producers.  They are not asserted to be the exhaustive value domain
# of every F6 use; call-site provenance will narrow those domains later.
TERM_FAMILIES = (
    TermFamily("actor_name_tier_1", 1, 0, 149, "monster and actor names, first tier"),
    TermFamily("actor_name_tier_2", 2, 0, 149, "monster and actor names, second tier"),
    TermFamily("actor_name_tier_3", 3, 0, 149, "monster and actor names, third tier"),
    TermFamily("identified_item_names", 4, 0, 215, "identified/base item names"),
    TermFamily("unidentified_item_appearances", 5, 0, 122, "unidentified item appearances"),
    TermFamily("item_name_format_fragments", 11, 0, 19, "item suffixes and composition fragments"),
    TermFamily("item_ability_roots", 12, 0, 122, "item ability/name roots used by item logic"),
    TermFamily("trap_menu_status", 17, 0, 0, "no-available-trap menu status"),
    TermFamily("trap_names", 17, 1, 22, "trap names"),
    TermFamily(
        "location_names_primary", 24, 1, 14,
        "front-end dungeon and location names",
    ),
    TermFamily(
        "location_names_history", 24, 19, 48,
        "main-menu and history location names",
    ),
)


@dataclass(frozen=True)
class ProducerClass:
    name: str
    sites: tuple
    construction: str
    value_domain: tuple


# Every immediate cache append is assigned exactly once.  Most consumers use
# the central item formatter, but keeping the six other writers separate is
# essential: the cache API itself does not carry a type tag.
CACHE_PRODUCER_CLASSES = (
    ProducerClass(
        "item_name",
        (
            (1, 0x659B), (1, 0x661F), (1, 0x6636), (1, 0x6669),
            (8, 0x5070), (8, 0x50AA), (8, 0x603E), (8, 0x6693),
            (8, 0x66A6), (8, 0x6ABF), (8, 0x7C70),
            (11, 0x714B), (16, 0x5331), (17, 0x4440),
            (120, 0x4B23), (120, 0x4B78), (120, 0x5D7F),
            (120, 0x6B92), (120, 0x6BA1), (120, 0x6E86),
            (120, 0x749B), (120, 0x77D4), (120, 0x77E6),
            (120, 0x7D0E),
            (122, 0x4460), (122, 0x44D5), (122, 0x5F2B),
            (122, 0x5F53), (181, 0x464B),
        ),
        "central item formatter 120:$47C2/$47CC, directly or through a wrapper",
        (
            "identified_item_names",
            "unidentified_item_appearances",
            "item_name_format_fragments",
        ),
    ),
    ProducerClass(
        "location_record",
        ((0, 0x350A),),
        "runtime-selected group-24 directory record copied to FFB0",
        ("location_names_primary", "location_names_history"),
    ),
    ProducerClass(
        "unsigned_integer",
        ((0, 0x3547),),
        "decimal formatter writes an FF-terminated value to FFB0",
        ("unsigned_integer",),
    ),
    ProducerClass(
        "sender_string",
        ((11, 0x7135),),
        "communication sender string already present at C16D",
        ("remote_player_name",),
    ),
    ProducerClass(
        "polymorphic_value",
        ((17, 0x4334),),
        "branch-selected item name or integer-derived display value in FFB0",
        (
            "identified_item_names",
            "unidentified_item_appearances",
            "item_name_format_fragments",
            "unsigned_integer",
        ),
    ),
    ProducerClass(
        "encoded_communication_string",
        ((17, 0x4749),),
        "communication formatter generates a bounded code string at C16D",
        ("communication_code",),
    ),
)


def _anchor_summary(rom):
    out = []
    for anchor in OPCODE_ANCHORS:
        at = extract.file_offset(anchor.bank, anchor.address)
        out.append(
            {
                "location": extract.location(anchor.bank, anchor.address),
                "purpose": anchor.purpose,
                "bytes": rom[at:at + anchor.length].hex().upper(),
            }
        )
    return out


def source_control_summary(rom, result=None):
    """Return corpus counts for the two supported F6 source modes."""
    result = extract.extract(rom) if result is None else result
    modes = {
        0x01: ("record_lookup", Counter(), set(), defaultdict(set)),
        0x03: ("cached_string", Counter(), set(), defaultdict(set)),
    }
    unexpected = Counter()
    for record in result["records"]:
        record_modes = set()
        for token in codec.parse_source(record.raw):
            if token.kind != "source_control" or token.code != 0xF6:
                continue
            mode = token.args[0]
            if mode not in modes:
                unexpected["%02X" % mode] += 1
                continue
            _name, addresses, records, _groups = modes[mode]
            address = token.args[1] | token.args[2] << 8
            addresses[address] += 1
            records.add(record.id)
            record_modes.add(mode)
        for mode in record_modes:
            groups = modes[mode][3]
            for reference in record.references:
                groups[reference.group].add(record.id)

    out = {}
    for mode in sorted(modes):
        name, addresses, records, groups = modes[mode]
        out[name] = {
            "mode": mode,
            "occurrences": sum(addresses.values()),
            "records": len(records),
            "address_occurrences": {
                "$%04X" % address: count
                for address, count in sorted(addresses.items())
            },
            "records_by_reference_group": {
                str(group): len(ids) for group, ids in sorted(groups.items())
            },
        }
    out["unexpected_modes"] = dict(sorted(unexpected.items()))
    return out


def _cached_string_domain(record, address):
    references = {(reference.group, reference.index) for reference in record.references}
    if (0, 228) in references:
        return "debug_polymorphic", (0, 228)
    if (7, 100) in references:
        if address == 0xC519:
            return "sender_string", (7, 100)
        if address == 0xC51A:
            return "item_name", (7, 100)
    if (7, 129) in references and address == 0xC519:
        return "location_record", (7, 129)
    for group in (8, 11, 33):
        matches = sorted(reference for reference in references if reference[0] == group)
        if matches:
            return "item_name", matches[0]
    raise extract.ExtractError(
        "unclassified cached-string consumer %s field $%04X"
        % (record.id, address)
    )


def cached_string_domain(record, address):
    """Return the proven semantic domain for one mode-3 F6 consumer."""
    return _cached_string_domain(record, address)[0]


def cached_string_consumer_summary(result):
    """Classify all 108 mode-3 source insertions by semantic value domain."""
    metadata = {
        "item_name": (
            "composed item name",
            (
                "identified_item_names",
                "unidentified_item_appearances",
                "item_name_format_fragments",
            ),
        ),
        "sender_string": ("communication sender name", ("remote_player_name",)),
        "location_record": (
            "runtime-selected location",
            ("location_names_primary", "location_names_history"),
        ),
        "debug_polymorphic": (
            "debug assertion value; item/integer branches remain possible",
            (
                "identified_item_names",
                "unidentified_item_appearances",
                "item_name_format_fragments",
                "unsigned_integer",
            ),
        ),
    }
    buckets = {
        name: {
            "rows": [],
            "records": set(),
            "fields": Counter(),
            "groups": Counter(),
            "digest": sha1(),
        }
        for name in metadata
    }
    for record in result["records"]:
        offset = 0
        for token in codec.parse_source(record.raw):
            if (
                token.kind == "source_control"
                and token.code == 0xF6
                and token.args[0] == 0x03
            ):
                address = token.args[1] | token.args[2] << 8
                name, reference = _cached_string_domain(record, address)
                bucket = buckets[name]
                row = (record, offset, address, reference)
                bucket["rows"].append(row)
                bucket["records"].add(record.id)
                bucket["fields"][address] += 1
                bucket["groups"][reference[0]] += 1
                bucket["digest"].update(record.id.encode("ascii"))
                bucket["digest"].update(offset.to_bytes(2, "little"))
                bucket["digest"].update(address.to_bytes(2, "little"))
                bucket["digest"].update(bytes((reference[0],)))
                bucket["digest"].update(reference[1].to_bytes(2, "little"))
            offset += len(token.raw)

    out = []
    for name in metadata:
        description, value_domain = metadata[name]
        bucket = buckets[name]
        rows = bucket["rows"]
        if not rows:
            raise extract.ExtractError("empty cached-string domain %s" % name)
        first_record, first_offset, first_address, first_reference = rows[0]
        out.append(
            {
                "name": name,
                "description": description,
                "value_domain": list(value_domain),
                "occurrences": len(rows),
                "records": len(bucket["records"]),
                "field_occurrences": {
                    "$%04X" % address: count
                    for address, count in sorted(bucket["fields"].items())
                },
                "reference_group_occurrences": {
                    str(group): count
                    for group, count in sorted(bucket["groups"].items())
                },
                "sha1": bucket["digest"].hexdigest(),
                "first": {
                    "record": first_record.id,
                    "offset": first_offset,
                    "field": "$%04X" % first_address,
                    "reference": list(first_reference),
                    "source": first_record.source,
                },
            }
        )
    return out


def _record_lookup_domain(record):
    """Return the semantic domain and evidence reference for an F6 mode-1 use."""
    references = {(reference.group, reference.index) for reference in record.references}

    # These two records are internal diagnostic displays.  Their source field
    # is not initialized by a production UI path, so keep the domain explicit
    # and unresolved rather than smuggling it into a translation width budget.
    for reference in ((0, 29), (0, 31)):
        if reference in references:
            return "debug_polymorphic", reference

    if (8, 40) in references:
        return "trap_name", (8, 40)
    group_8 = sorted(reference for reference in references if reference[0] == 8)
    if group_8:
        return "actor_name", group_8[0]

    actor_messages = {25, 39, 40, 69, 75, 88, 113, 135, 142}
    trap_messages = {145, 146, 147, 148, 151, 152}
    for index in sorted(actor_messages):
        if (11, index) in references:
            return "actor_name", (11, index)
    if (11, 68) in references:
        return "identified_item_name", (11, 68)
    for index in sorted(trap_messages):
        if (11, index) in references:
            return "trap_name", (11, index)

    for reference in ((16, 22), (18, 1), (18, 6), (18, 17), (24, 65), (24, 66)):
        if reference in references:
            return "actor_name", reference
    if (22, 73) in references:
        return "location_name", (22, 73)

    raise extract.ExtractError(
        "unclassified record-lookup consumer %s (references %s)"
        % (record.id, sorted(references))
    )


def record_lookup_domain(record):
    """Return the proven semantic domain for one mode-1 F6 consumer."""
    return _record_lookup_domain(record)[0]


def record_lookup_consumer_summary(result):
    """Classify every mode-1 directory lookup by semantic value domain."""
    metadata = {
        "actor_name": (
            "actor or monster name, including the player-name sentinel",
            (
                "actor_name_tier_1",
                "actor_name_tier_2",
                "actor_name_tier_3",
                "player_name",
            ),
        ),
        "trap_name": ("trap name", ("trap_names",)),
        "identified_item_name": (
            "identified item name revealed at runtime",
            ("identified_item_names",),
        ),
        "location_name": (
            "rescue-history location",
            ("location_names_primary", "location_names_history"),
        ),
        "debug_polymorphic": (
            "debug-only lookup with no proven production value domain",
            ("unresolved_debug_lookup",),
        ),
    }
    buckets = {
        name: {
            "rows": [],
            "records": set(),
            "fields": Counter(),
            "groups": Counter(),
            "digest": sha1(),
        }
        for name in metadata
    }
    for record in result["records"]:
        offset = 0
        for token in codec.parse_source(record.raw):
            if (
                token.kind == "source_control"
                and token.code == 0xF6
                and token.args[0] == 0x01
            ):
                address = token.args[1] | token.args[2] << 8
                name, reference = _record_lookup_domain(record)
                bucket = buckets[name]
                row = (record, offset, address, reference)
                bucket["rows"].append(row)
                bucket["records"].add(record.id)
                bucket["fields"][address] += 1
                bucket["groups"][reference[0]] += 1
                bucket["digest"].update(record.id.encode("ascii"))
                bucket["digest"].update(offset.to_bytes(2, "little"))
                bucket["digest"].update(address.to_bytes(2, "little"))
                bucket["digest"].update(bytes((reference[0],)))
                bucket["digest"].update(reference[1].to_bytes(2, "little"))
            offset += len(token.raw)

    out = []
    for name in metadata:
        description, value_domain = metadata[name]
        bucket = buckets[name]
        rows = bucket["rows"]
        if not rows:
            raise extract.ExtractError("empty record-lookup domain %s" % name)
        first_record, first_offset, first_address, first_reference = rows[0]
        out.append(
            {
                "name": name,
                "description": description,
                "value_domain": list(value_domain),
                "occurrences": len(rows),
                "records": len(bucket["records"]),
                "field_occurrences": {
                    "$%04X" % address: count
                    for address, count in sorted(bucket["fields"].items())
                },
                "reference_group_occurrences": {
                    str(group): count
                    for group, count in sorted(bucket["groups"].items())
                },
                "sha1": bucket["digest"].hexdigest(),
                "first": {
                    "record": first_record.id,
                    "offset": first_offset,
                    "field": "$%04X" % first_address,
                    "reference": list(first_reference),
                    "source": first_record.source,
                },
            }
        )
    return out


def cache_call_graph(rom):
    """Return every immediate caller of the generic cache primitives."""
    out = {}
    for name, entry in (
        ("reset", CACHE_RESET),
        ("append", CACHE_APPEND),
        ("read", CACHE_READ),
    ):
        out[name] = {
            "entry": extract.location(*entry),
            "near": list(surfaces.near_call_sites(rom, entry[0], entry[1])),
            "far": list(
                surfaces.far_call_sites(
                    rom, entry[0], entry[1], dispatchers=(0x09AC,)
                )
            ),
        }
    return out


def cache_producer_class_summary(rom, graph=None):
    """Classify every immediate cache writer and reject coverage drift."""
    graph = cache_call_graph(rom) if graph is None else graph
    actual = set(graph["append"]["far"])
    classified = []
    seen = set()
    out = []
    for producer_class in CACHE_PRODUCER_CLASSES:
        sites = [extract.location(*site) for site in producer_class.sites]
        duplicates = seen.intersection(sites)
        if duplicates:
            raise extract.ExtractError(
                "cache producer sites classified twice: %s"
                % ", ".join(sorted(duplicates))
            )
        seen.update(sites)
        classified.extend(sites)
        out.append(
            {
                "name": producer_class.name,
                "count": len(sites),
                "construction": producer_class.construction,
                "value_domain": list(producer_class.value_domain),
                "sites": sites,
            }
        )
    classified_set = set(classified)
    if classified_set != actual:
        missing = sorted(actual - classified_set)
        extra = sorted(classified_set - actual)
        raise extract.ExtractError(
            "cache producer classification drift (missing %s; extra %s)"
            % (missing, extra)
        )
    return out


def _record_maps(result):
    by_target = {(record.bank, record.address): record for record in result["records"]}
    by_reference = {}
    for reference in result["references"]:
        by_reference[(reference.group, reference.index)] = by_target[
            (reference.target_bank, reference.target_address)
        ]
    return by_reference


def term_family_summary(result):
    """Fingerprint the first proven finite directory families."""
    records = _record_maps(result)
    out = []
    for family in TERM_FAMILIES:
        rows = []
        digest = sha1()
        for index in range(family.start_index, family.end_index + 1):
            try:
                record = records[(family.group, index)]
            except KeyError as exc:
                raise extract.ExtractError(
                    "missing group %d index %d for %s"
                    % (family.group, index, family.name)
                ) from exc
            rows.append(record)
            digest.update(index.to_bytes(2, "little"))
            digest.update(len(record.raw).to_bytes(2, "little"))
            digest.update(record.raw)
        out.append(
            {
                "name": family.name,
                "role": family.role,
                "group": family.group,
                "index_range": [family.start_index, family.end_index],
                "entries": len(rows),
                "unique_records": len({record.id for record in rows}),
                "sha1": digest.hexdigest(),
                "first": {
                    "index": family.start_index,
                    "record": rows[0].id,
                    "source": rows[0].source,
                },
                "last": {
                    "index": family.end_index,
                    "record": rows[-1].id,
                    "source": rows[-1].source,
                },
            }
        )
    return out


def mixed_cache_evidence(result):
    """Return the source record that consumes two differently produced values."""
    record = next(record for record in result["records"] if record.id == "192:$6DCF")
    tokens = [
        {
            "offset": sum(len(part.raw) for part in codec.parse_source(record.raw)[:index]),
            "source": codec.source_control_text(token),
        }
        for index, token in enumerate(codec.parse_source(record.raw))
        if token.kind == "source_control" and token.code == 0xF6 and token.args[0] == 3
    ]
    return {
        "record": record.id,
        "source": record.source,
        "cached_string_tokens": tokens,
        "references": sorted(
            [[reference.group, reference.index] for reference in record.references]
        ),
    }


def inventory(rom):
    rom = bytes(rom)
    result = extract.extract(rom)
    graph = cache_call_graph(rom)
    return {
        "schema": "shiren-gb2-runtime-terms-v2",
        "rom_sha1": result["rom_sha1"],
        "f6_handler": extract.location(*F6_HANDLER),
        "player_name_sentinel": list(PLAYER_NAME_SENTINEL),
        "cache": {
            "bank": CACHE_BANK,
            "base": "$%04X" % CACHE_BASE,
            "cursor": "$%04X" % CACHE_CURSOR,
            "call_graph": graph,
            "producer_classes": cache_producer_class_summary(rom, graph=graph),
        },
        "source_controls": source_control_summary(rom, result=result),
        "record_lookup_consumers": record_lookup_consumer_summary(result),
        "cached_string_consumers": cached_string_consumer_summary(result),
        "opcode_anchors": _anchor_summary(rom),
        "term_families": term_family_summary(result),
        "mixed_cache_evidence": mixed_cache_evidence(result),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    try:
        measured = inventory(Path(args.rom).read_bytes())
    except (OSError, ValueError, extract.ExtractError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    print(json.dumps(measured, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
