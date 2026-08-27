#!/usr/bin/env python3
"""Plan a deterministic far-pointer rebuild of every GB2 script table.

This allocator extracts the authoritative
126-group directory, collapses its eight duplicate directory entries into 118 physical
tables, applies optional stable-record byte overrides, materializes every table and its
records in empty-bank images, and emits an allocation manifest.  The input ROM is never
modified.  Relocated tables use a two-byte entry count followed by three-byte
``address-low, address-high, bank`` pointers.  The selector patch installed by
``insert.py`` follows those far pointers, so records no longer share a bank with their
table and translation length is constrained only by total free ROM space.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

import codec
import extract


BANK_SIZE = 0x4000
FREE_BANKS = tuple(range(215, 240))
FILL_BYTE = 0x00
STRATEGY = "far-tables-then-records-next-fit-v2"


class AllocationError(ValueError):
    """The source graph or requested destination banks cannot be allocated safely."""


@dataclass(frozen=True)
class Unit:
    source_bank: int
    source_address: int
    groups: tuple
    references: tuple
    records: tuple
    record_data: tuple
    override_keys: frozenset
    pointer_bytes: int
    text_bytes: int

    @property
    def key(self):
        return self.source_bank, self.source_address

    @property
    def size(self):
        return self.pointer_bytes + self.text_bytes


@dataclass(frozen=True)
class RecordPlacement:
    source_bank: int
    source_address: int
    output_bank: int
    output_address: int
    raw_size: int
    entry_indexes: tuple
    interior_of: str
    interior_mode: str
    overridden: bool

    @property
    def source_id(self):
        return extract.location(self.source_bank, self.source_address)


@dataclass(frozen=True)
class TablePlacement:
    source_bank: int
    source_address: int
    groups: tuple
    output_bank: int
    output_address: int
    entries: int
    unique_records: int
    alias_entries: int
    pointer_bytes: int
    text_bytes: int
    size: int
    payload_sha1: str
    records: tuple

    @property
    def source_key(self):
        return self.source_bank, self.source_address

    @property
    def output_key(self):
        return self.output_bank, self.output_address


@dataclass
class Allocation:
    source_rom_sha1: str
    free_banks: tuple
    tables: tuple
    group_tables: dict
    record_placements: dict
    bank_images: dict
    summary: dict
    override_keys: frozenset


def _physical_references(result):
    """Collapse duplicate directory groups without collapsing real pointer aliases."""
    by_offset = {}
    for reference in result["references"]:
        previous = by_offset.setdefault(reference.pointer_offset, reference)
        if (
            previous.table_bank,
            previous.table_address,
            previous.index,
            previous.target_bank,
            previous.target_address,
        ) != (
            reference.table_bank,
            reference.table_address,
            reference.index,
            reference.target_bank,
            reference.target_address,
        ):
            raise AllocationError(
                "logical references disagree at physical pointer offset $%06X"
                % reference.pointer_offset
            )
    return tuple(by_offset.values())


def build_units(result, record_overrides=None):
    """Build the 118 self-contained table units in first-directory-use order."""
    record_overrides = record_overrides or {}
    records = {(record.bank, record.address): record for record in result["records"]}
    references_by_table = defaultdict(list)
    for reference in _physical_references(result):
        references_by_table[(reference.table_bank, reference.table_address)].append(reference)

    groups_by_table = defaultdict(list)
    table_order = []
    for entry in result["directory"]:
        key = entry.table_bank, entry.table_address
        groups_by_table[key].append(entry.group)
        if key not in table_order:
            table_order.append(key)
    if set(table_order) != set(references_by_table):
        raise AllocationError("directory/table reference sets disagree")

    units = []
    for key in table_order:
        references = sorted(
            references_by_table[key], key=lambda reference: reference.pointer_offset
        )
        if [reference.index for reference in references] != list(range(len(references))):
            raise AllocationError(
                "%s physical entries are not a complete index sequence"
                % extract.location(*key)
            )
        table_offset = extract.file_offset(*key)
        if [reference.pointer_offset for reference in references] != [
            table_offset + index * 2 for index in range(len(references))
        ]:
            raise AllocationError(
                "%s physical pointer slots are not contiguous" % extract.location(*key)
            )

        record_keys = []
        seen_records = set()
        for reference in references:
            target = reference.target_bank, reference.target_address
            if target not in seen_records:
                seen_records.add(target)
                record_keys.append(target)
        if not record_keys or record_keys[0] != (
            references[0].target_bank,
            references[0].target_address,
        ):
            raise AllocationError("%s has no entry-zero record" % extract.location(*key))
        try:
            unit_records = tuple(records[target] for target in record_keys)
        except KeyError as exc:
            raise AllocationError(
                "%s points at unextracted record %s" % (extract.location(*key), exc.args[0])
            ) from None
        record_data = tuple(
            record_overrides.get((record.bank, record.address), record.raw)
            for record in unit_records
        )
        # Relocated tables are self-describing: a little-endian entry count is
        # followed by one address/address-bank triplet per physical entry.
        pointer_bytes = 2 + len(references) * 3
        text_bytes = sum(len(raw) + 1 for raw in record_data)
        units.append(
            Unit(
                source_bank=key[0],
                source_address=key[1],
                groups=tuple(groups_by_table[key]),
                references=tuple(references),
                records=unit_records,
                record_data=record_data,
                override_keys=frozenset(
                    (record.bank, record.address)
                    for record in unit_records
                    if (record.bank, record.address) in record_overrides
                ),
                pointer_bytes=pointer_bytes,
                text_bytes=text_bytes,
            )
        )
    return tuple(units)


def _verify_free_banks(rom, free_banks):
    if not free_banks:
        raise AllocationError("at least one destination bank is required")
    if len(set(free_banks)) != len(free_banks):
        raise AllocationError("destination bank list contains duplicates")
    for bank in free_banks:
        if bank <= 0 or (bank + 1) * BANK_SIZE > len(rom):
            raise AllocationError("destination bank %d is outside the ROM" % bank)
        data = rom[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        if data != bytes((FILL_BYTE,)) * BANK_SIZE:
            raise AllocationError("destination bank %d is not entirely $%02X" % (bank, FILL_BYTE))


def _pack(units, free_banks):
    """Place far tables first, then independently place terminated records."""
    table_placements = {}
    record_placements = {}
    bank_index = 0
    offset = 0

    def place(size, label):
        nonlocal bank_index, offset
        if size > BANK_SIZE:
            raise AllocationError(
                "%s needs %d bytes and cannot fit in one bank" % (label, size)
            )
        if offset + size > BANK_SIZE:
            bank_index += 1
            offset = 0
        if bank_index >= len(free_banks):
            raise AllocationError(
                "script allocation exhausted %d destination bank(s)" % len(free_banks)
            )
        destination = free_banks[bank_index], 0x4000 + offset
        offset += size
        return destination

    for unit in units:
        table_placements[unit.key] = place(
            unit.pointer_bytes, "%s far table" % extract.location(*unit.key)
        )
    for unit in units:
        for record, raw in zip(unit.records, unit.record_data):
            key = record.bank, record.address
            if key in record_placements:
                raise AllocationError(
                    "record %s belongs to multiple physical tables" % record.id
                )
            record_placements[key] = place(
                len(raw) + 1, "%s record" % extract.location(*key)
            )
    return table_placements, record_placements


def _materialize(unit, output_bank, output_address, record_destinations):
    """Build one far table and its independently placed terminated records."""
    data = bytearray(unit.pointer_bytes)
    data[0] = len(unit.references) & 0xFF
    data[1] = len(unit.references) >> 8
    address_by_source = {}
    records = []
    record_payloads = []
    for record, raw in zip(unit.records, unit.record_data):
        key = record.bank, record.address
        output_record_bank, output_record_address = record_destinations[key]
        if not 0x4000 <= output_record_address < 0x8000:
            raise AllocationError("record placement escaped its switchable bank")
        address_by_source[key] = output_record_bank, output_record_address
        record_payloads.append((output_record_bank, output_record_address, raw + bytes((codec.TERMINATOR,))))
        entry_indexes = tuple(
            reference.index
            for reference in unit.references
            if (reference.target_bank, reference.target_address)
            == (record.bank, record.address)
        )
        records.append(
            RecordPlacement(
                source_bank=record.bank,
                source_address=record.address,
                output_bank=output_record_bank,
                output_address=output_record_address,
                raw_size=len(raw),
                entry_indexes=entry_indexes,
                interior_of=record.interior_of,
                # The one original suffix-overlap crosses table ownership.  The
                # rebuilt representation gives it an independent terminated copy,
                # preserving both logical records without coupling table bytes to text.
                interior_mode="materialized_copy" if record.interior_of else "",
                overridden=(record.bank, record.address) in unit.override_keys,
            )
        )

    for reference in unit.references:
        target_bank, target_address = address_by_source[
            (reference.target_bank, reference.target_address)
        ]
        at = 2 + reference.index * 3
        data[at] = target_address & 0xFF
        data[at + 1] = target_address >> 8
        data[at + 2] = target_bank
    return bytes(data), tuple(records), tuple(record_payloads)


def allocate(rom, free_banks=FREE_BANKS, record_overrides=None):
    """Return the complete allocation plan, optionally resized by record overrides."""
    rom = bytes(rom)
    free_banks = tuple(free_banks)
    result = extract.extract(rom)
    known_records = {
        (record.bank, record.address) for record in result["records"]
    }
    normalized_overrides = {}
    for key, raw in (record_overrides or {}).items():
        if not isinstance(key, tuple) or len(key) != 2 or key not in known_records:
            raise AllocationError("override names unknown source record %r" % (key,))
        if not isinstance(raw, (bytes, bytearray)):
            raise AllocationError("override for %s is not bytes" % extract.location(*key))
        raw = bytes(raw)
        try:
            codec.parse_source(raw)
        except codec.ParseError as exc:
            raise AllocationError(
                "override for %s is not valid source text: %s"
                % (extract.location(*key), exc)
            ) from exc
        normalized_overrides[key] = raw
    _verify_free_banks(rom, free_banks)
    units = build_units(result, normalized_overrides)
    table_destinations, record_destinations = _pack(units, free_banks)

    bank_images = {}
    occupied_by_bank = defaultdict(list)
    table_placements = []
    record_placements = {}

    def write_block(bank, address, payload, label):
        image = bank_images.setdefault(
            bank, bytearray((FILL_BYTE,)) * BANK_SIZE
        )
        start = address - 0x4000
        end = start + len(payload)
        if not 0 <= start <= end <= BANK_SIZE:
            raise AllocationError("%s escaped bank %d" % (label, bank))
        if any(
            start < previous_end and previous_start < end
            for previous_start, previous_end in occupied_by_bank[bank]
        ):
            raise AllocationError("%s overlaps another allocation in bank %d" % (label, bank))
        occupied_by_bank[bank].append((start, end))
        image[start:end] = payload

    for unit in units:
        output_bank, output_address = table_destinations[unit.key]
        table_payload, placed_records, record_payloads = _materialize(
            unit, output_bank, output_address, record_destinations
        )
        write_block(
            output_bank,
            output_address,
            table_payload,
            "%s far table" % extract.location(*unit.key),
        )
        for record_bank, record_address, record_payload in record_payloads:
            write_block(
                record_bank,
                record_address,
                record_payload,
                "%s record"
                % next(
                    record.source_id
                    for record in placed_records
                    if record.output_bank == record_bank
                    and record.output_address == record_address
                ),
            )
        logical_payload = table_payload + b"".join(
            payload for _bank, _address, payload in record_payloads
        )
        placement = TablePlacement(
            source_bank=unit.source_bank,
            source_address=unit.source_address,
            groups=unit.groups,
            output_bank=output_bank,
            output_address=output_address,
            entries=len(unit.references),
            unique_records=len(unit.records),
            alias_entries=len(unit.references) - len(unit.records),
            pointer_bytes=unit.pointer_bytes,
            text_bytes=unit.text_bytes,
            size=unit.size,
            payload_sha1=sha1(logical_payload).hexdigest(),
            records=placed_records,
        )
        table_placements.append(placement)
        for record in placed_records:
            key = record.source_bank, record.source_address
            if key in record_placements:
                raise AllocationError("record %s belongs to multiple physical tables" % record.source_id)
            record_placements[key] = record

    tables_by_source = {table.source_key: table for table in table_placements}
    group_tables = {
        entry.group: tables_by_source[(entry.table_bank, entry.table_address)]
        for entry in result["directory"]
    }
    payload_bytes = sum(table.size for table in table_placements)
    used_banks = tuple(bank_images)
    summary = {
        "directory_groups": len(result["directory"]),
        "unique_tables": len(table_placements),
        "logical_references": len(result["references"]),
        "physical_pointer_entries": sum(table.entries for table in table_placements),
        "unique_records": len(record_placements),
        "pointer_bytes": sum(table.pointer_bytes for table in table_placements),
        "text_bytes": sum(table.text_bytes for table in table_placements),
        "payload_bytes": payload_bytes,
        "used_banks": len(used_banks),
        "used_bank_capacity": len(used_banks) * BANK_SIZE,
        "unused_bytes_in_used_banks": len(used_banks) * BANK_SIZE - payload_bytes,
        "reserved_banks": len(free_banks),
        "untouched_reserved_banks": len(free_banks) - len(used_banks),
        "tables_with_aliases": sum(table.alias_entries > 0 for table in table_placements),
        "alias_pointer_entries": sum(table.alias_entries for table in table_placements),
        "materialized_interior_records": sum(
            bool(record.interior_of) for record in record_placements.values()
        ),
    }
    if normalized_overrides:
        summary["overridden_records"] = len(normalized_overrides)
    return Allocation(
        source_rom_sha1=result["rom_sha1"],
        free_banks=free_banks,
        tables=tuple(table_placements),
        group_tables=group_tables,
        record_placements=record_placements,
        bank_images={bank: bytes(image) for bank, image in bank_images.items()},
        summary=summary,
        override_keys=frozenset(normalized_overrides),
    )


def read_allocated_record(allocation, group, index):
    """Follow one rebuilt far pointer and return its unterminated source bytes."""
    try:
        table = allocation.group_tables[group]
    except KeyError:
        raise AllocationError("unknown directory group %d" % group) from None
    if not 0 <= index < table.entries:
        raise AllocationError("group %d has no entry %d" % (group, index))
    table_bank = allocation.bank_images[table.output_bank]
    table_at = table.output_address - 0x4000
    entries = table_bank[table_at] | (table_bank[table_at + 1] << 8)
    if entries != table.entries:
        raise AllocationError("group %d far-table count changed" % group)
    pointer_at = table_at + 2 + index * 3
    address = table_bank[pointer_at] | (table_bank[pointer_at + 1] << 8)
    record_bank = table_bank[pointer_at + 2]
    try:
        bank = allocation.bank_images[record_bank]
    except KeyError:
        raise AllocationError(
            "group %d entry %d names unavailable bank %d"
            % (group, index, record_bank)
        ) from None
    at = address - 0x4000
    out = bytearray()
    while at < BANK_SIZE:
        code = bank[at]
        if code == codec.TERMINATOR:
            return bytes(out)
        size = codec.source_token_size(code)
        if at + size > BANK_SIZE:
            break
        out += bank[at:at + size]
        at += size
    raise AllocationError("unterminated allocated record for group %d entry %d" % (group, index))


def _record_dict(record):
    out = {
        "source": record.source_id,
        "output": extract.location(record.output_bank, record.output_address),
        "raw_size": record.raw_size,
        "stored_size": record.raw_size + 1,
        "entry_indexes": list(record.entry_indexes),
        "interior_of": record.interior_of,
        "interior_mode": record.interior_mode,
    }
    if record.overridden:
        out["overridden"] = True
    return out


def manifest(allocation):
    """Return the deterministic, text-free JSON allocation document."""
    banks = []
    for bank, image in allocation.bank_images.items():
        tables = [table for table in allocation.tables if table.output_bank == bank]
        used = sum(table.pointer_bytes for table in tables) + sum(
            record.raw_size + 1
            for record in allocation.record_placements.values()
            if record.output_bank == bank
        )
        banks.append(
            {
                "bank": bank,
                "tables": len(tables),
                "used": used,
                "free": BANK_SIZE - used,
                "payload_sha1": sha1(image).hexdigest(),
            }
        )
    return {
        "schema": "shiren-gb2-script-allocation-v2",
        "source_rom_sha1": allocation.source_rom_sha1,
        "strategy": STRATEGY,
        "fill_byte": "%02X" % FILL_BYTE,
        "reserved_banks": list(allocation.free_banks),
        "summary": allocation.summary,
        "banks": banks,
        "directory": [
            {
                "group": group,
                "source_table": extract.location(table.source_bank, table.source_address),
                "output_table": extract.location(table.output_bank, table.output_address),
            }
            for group, table in sorted(allocation.group_tables.items())
        ],
        "tables": [
            {
                "source": extract.location(table.source_bank, table.source_address),
                "groups": list(table.groups),
                "output": extract.location(table.output_bank, table.output_address),
                "entries": table.entries,
                "unique_records": table.unique_records,
                "alias_entries": table.alias_entries,
                "pointer_bytes": table.pointer_bytes,
                "text_bytes": table.text_bytes,
                "size": table.size,
                "table_end": extract.location(
                    table.output_bank, table.output_address + table.pointer_bytes
                ),
                "payload_sha1": table.payload_sha1,
                "records": [_record_dict(record) for record in table.records],
            }
            for table in allocation.tables
        ],
    }


def manifest_bytes(allocation):
    return (json.dumps(manifest(allocation), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--output",
        default="build/script-allocation.json",
        help="manifest path (default: build/script-allocation.json)",
    )
    parser.add_argument(
        "--check", action="store_true", help="validate and print the plan without writing it"
    )
    args = parser.parse_args(argv)
    try:
        allocation = allocate(Path(args.rom).read_bytes())
    except (AllocationError, extract.ExtractError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    summary = allocation.summary
    print(
        "%d groups / %d tables / %d physical pointers / %d records"
        % (
            summary["directory_groups"],
            summary["unique_tables"],
            summary["physical_pointer_entries"],
            summary["unique_records"],
        )
    )
    print(
        "%d bytes -> %d bank(s) (%d bytes free in used banks)"
        % (
            summary["payload_bytes"],
            summary["used_banks"],
            summary["unused_bytes_in_used_banks"],
        )
    )
    for row in manifest(allocation)["banks"]:
        print(
            "bank %3d  %2d table(s)  %5d used  %5d free"
            % (row["bank"], row["tables"], row["used"], row["free"])
        )
    if not args.check:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(manifest_bytes(allocation))
        print("wrote %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
