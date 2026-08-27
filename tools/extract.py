#!/usr/bin/env python3
"""Extract GB2 text only through the game's proven group/pointer directory.

The ordinary text reader at 0:$1F58 takes a group ID in A and an entry index in C.
It indexes the three-byte directory at 4:$660E (LE16 table address, ROM bank), then
indexes that same-bank table for the final string address.  Each pointer table is
self-bounding: its first pointer is the address immediately after the table.

Generated ``script.json`` and ``script.tsv`` are deliberately ignored by git because
they contain extracted game text.  The structural fixtures under ``tests/fixtures``
are the tracked, redistributable regression contract.
"""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codec
import font
import textdump


BANK_SIZE = 0x4000
ROM_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"
TEXT_BANKS = frozenset(range(192, 206))

SELECTOR_BANK = 0
SELECTOR_ADDRESS = 0x1F58
DIRECTORY_BANK = 4
DIRECTORY_ADDRESS = 0x660E
DIRECTORY_COUNT = 126
DIRECTORY_RECORD_SIZE = 3
MAX_TABLE_ENTRIES = 256


class ExtractError(ValueError):
    """The ROM violates a proven extraction invariant."""


@dataclass(frozen=True)
class DirectoryEntry:
    group: int
    directory_offset: int
    table_bank: int
    table_address: int


@dataclass(frozen=True)
class Reference:
    group: int
    index: int
    directory_offset: int
    table_bank: int
    table_address: int
    pointer_offset: int
    target_bank: int
    target_address: int


@dataclass(frozen=True)
class Record:
    bank: int
    address: int
    terminator_address: int
    raw: bytes
    source: str
    references: tuple
    controls: tuple
    interior_of: str

    @property
    def id(self):
        return location(self.bank, self.address)


def file_offset(bank, address):
    """Convert a banked CPU address to a ROM file offset."""
    if bank == 0:
        if not 0 <= address < BANK_SIZE:
            raise ExtractError("bank 0 address out of range: $%04X" % address)
        return address
    if not 0x4000 <= address < 0x8000:
        raise ExtractError("bank %d address out of range: $%04X" % (bank, address))
    return bank * BANK_SIZE + address - 0x4000


def cpu_address(offset):
    bank = offset // BANK_SIZE
    return offset if bank == 0 else offset % BANK_SIZE + 0x4000


def location(bank, address):
    return "%d:$%04X" % (bank, address)


def read_directory(rom):
    """Return the 126 group records consumed by 0:$1F58."""
    start = file_offset(DIRECTORY_BANK, DIRECTORY_ADDRESS)
    out = []
    for group in range(DIRECTORY_COUNT):
        at = start + group * DIRECTORY_RECORD_SIZE
        table_address = rom[at] | (rom[at + 1] << 8)
        table_bank = rom[at + 2]
        if table_bank not in TEXT_BANKS:
            raise ExtractError(
                "group %d has non-script bank %d at %s"
                % (group, table_bank, location(DIRECTORY_BANK, cpu_address(at)))
            )
        if not 0x4000 <= table_address < 0x8000:
            raise ExtractError("group %d has bad table address $%04X" % (group, table_address))
        out.append(DirectoryEntry(group, at, table_bank, table_address))
    return tuple(out)


def read_table(rom, entry):
    """Return every logical group reference from one self-bounding pointer table."""
    table_offset = file_offset(entry.table_bank, entry.table_address)
    first_target = rom[table_offset] | (rom[table_offset + 1] << 8)
    span = first_target - entry.table_address
    if span < 2 or span % 2:
        raise ExtractError(
            "group %d table %s has invalid first pointer $%04X"
            % (entry.group, location(entry.table_bank, entry.table_address), first_target)
        )
    count = span // 2
    if count > MAX_TABLE_ENTRIES:
        raise ExtractError("group %d has implausible %d-entry table" % (entry.group, count))

    out = []
    for index in range(count):
        pointer_offset = table_offset + index * 2
        target = rom[pointer_offset] | (rom[pointer_offset + 1] << 8)
        if not first_target <= target < 0x8000:
            raise ExtractError(
                "group %d entry %d points outside its text block: $%04X"
                % (entry.group, index, target)
            )
        out.append(
            Reference(
                group=entry.group,
                index=index,
                directory_offset=entry.directory_offset,
                table_bank=entry.table_bank,
                table_address=entry.table_address,
                pointer_offset=pointer_offset,
                target_bank=entry.table_bank,
                target_address=target,
            )
        )
    return tuple(out)


def _read_raw(rom, bank, address):
    start = file_offset(bank, address)
    bank_end = (bank + 1) * BANK_SIZE
    at = start
    while at < bank_end:
        code = rom[at]
        if code == codec.TERMINATOR:
            return rom[start:at], cpu_address(at)
        size = codec.source_token_size(code)
        if at + size > bank_end:
            break
        at += size
    raise ExtractError("unterminated source record at %s" % location(bank, address))


def _control_rows(tokens):
    rows = []
    byte_offset = 0
    for token in tokens:
        if token.kind in ("control", "source_control"):
            if token.kind == "source_control":
                name = codec.source_control_text(token)[1:].split(":", 1)[0].rstrip(">")
            else:
                name = codec.CONTROLS[token.code]
            rows.append(
                {
                    "offset": byte_offset,
                    "code": "%02X" % token.code,
                    "name": name,
                    "args": token.args.hex().upper(),
                }
            )
        byte_offset += len(token.raw)
    return tuple(rows)


def _interior_parents(records):
    """Map the rare pointer target that begins inside another referenced record."""
    by_bank = defaultdict(list)
    for record in records:
        by_bank[record.bank].append(record)
    out = {}
    for bank_records in by_bank.values():
        bank_records.sort(key=lambda record: record.address)
        for record in bank_records:
            parents = [
                candidate
                for candidate in bank_records
                if candidate.address < record.address < candidate.terminator_address
            ]
            if parents:
                out[(record.bank, record.address)] = max(
                    parents, key=lambda candidate: candidate.address
                ).id
    return out


def extract(rom):
    """Return deterministic group, reference, record, and coverage metadata."""
    rom = bytes(rom)
    digest = sha1(rom).hexdigest()
    if digest != ROM_SHA1:
        raise ExtractError("ROM SHA1 is %s; expected %s" % (digest, ROM_SHA1))

    directory = read_directory(rom)
    references = tuple(ref for entry in directory for ref in read_table(rom, entry))
    refs_by_target = defaultdict(list)
    for ref in references:
        refs_by_target[(ref.target_bank, ref.target_address)].append(ref)

    provisional = []
    unmapped = Counter()
    rendered_glyphs = 0
    for (bank, address), refs in sorted(refs_by_target.items()):
        raw, terminator = _read_raw(rom, bank, address)
        try:
            tokens = codec.parse_source(raw)
            source = codec.decode_source(raw)
        except codec.ParseError as exc:
            raise ExtractError("%s: %s" % (location(bank, address), exc))
        if codec.encode_source(source) != raw:
            raise ExtractError("text round-trip failed at %s" % location(bank, address))

        for token in tokens:
            if token.kind in ("glyph", "kanji"):
                rendered_glyphs += 1
            if token.kind != "kanji" or token.raw in codec.KANJI:
                continue
            glyph = font.read_glyph(rom, token.raw)
            if glyph.width < 4:
                raise ExtractError(
                    "%s contains continuation slice %s (width %d)"
                    % (location(bank, address), token.raw.hex().upper(), glyph.width)
                )
            unmapped[token.raw.hex().upper()] += 1

        provisional.append(
            Record(
                bank=bank,
                address=address,
                terminator_address=terminator,
                raw=raw,
                source=source,
                references=tuple(sorted(refs, key=lambda ref: (ref.group, ref.index))),
                controls=_control_rows(tokens),
                interior_of="",
            )
        )

    parents = _interior_parents(provisional)
    records = tuple(
        Record(
            bank=record.bank,
            address=record.address,
            terminator_address=record.terminator_address,
            raw=record.raw,
            source=record.source,
            references=record.references,
            controls=record.controls,
            interior_of=parents.get((record.bank, record.address), ""),
        )
        for record in provisional
    )

    candidates = dict(textdump._dialogue(rom))
    targets = {file_offset(record.bank, record.address) for record in records}
    candidate_offsets = set(candidates)
    table_keys = {(entry.table_bank, entry.table_address) for entry in directory}
    duplicate_groups = len(directory) - len(table_keys)
    physical_pointer_offsets = {ref.pointer_offset for ref in references}
    multi_group_records = sum(1 for record in records if len(record.references) > 1)
    aliased_records = sum(
        1
        for record in records
        if len({ref.pointer_offset for ref in record.references}) > 1
    )
    empty_records = sum(not record.raw for record in records)

    table_spans = []
    for entry in directory:
        table_start = file_offset(entry.table_bank, entry.table_address)
        first_target = rom[table_start] | (rom[table_start + 1] << 8)
        table_spans.append((table_start, file_offset(entry.table_bank, first_target)))
    record_spans = [
        (
            file_offset(record.bank, record.address),
            file_offset(record.bank, record.terminator_address),
        )
        for record in records
    ]
    coverage = defaultdict(list)
    for offset in sorted(candidate_offsets - targets):
        if any(start <= offset < end for start, end in table_spans):
            kind = "pointer_table_bytes"
        elif any(start < offset <= end for start, end in record_spans):
            kind = "inside_source_record"
        elif any(
            offset < target <= offset + len(candidates[offset]) for target in targets
        ):
            kind = "prefix_before_reference"
        else:
            kind = "unexplained"
        coverage[kind].append(offset)

    summary = {
        "directory_groups": len(directory),
        "unique_tables": len(table_keys),
        "duplicate_directory_groups": duplicate_groups,
        "pointer_references": len(references),
        "physical_pointer_references": len(physical_pointer_offsets),
        "unique_records": len(records),
        "nonempty_records": len(records) - empty_records,
        "empty_records": empty_records,
        "aliased_records": aliased_records,
        "multi_group_records": multi_group_records,
        "interior_records": len(parents),
        "rendered_glyphs": rendered_glyphs,
        "unmapped_valid_glyph_codes": len(unmapped),
        "unmapped_valid_glyph_occurrences": sum(unmapped.values()),
        "density_candidates": len(candidate_offsets),
        "referenced_density_candidates": len(candidate_offsets & targets),
        "density_pointer_table_false_positives": len(coverage["pointer_table_bytes"]),
        "density_source_continuations": len(coverage["inside_source_record"]),
        "density_prefix_before_reference": len(coverage["prefix_before_reference"]),
        "unexplained_density_candidates": len(coverage["unexplained"]),
    }
    return {
        "rom_sha1": digest,
        "directory": directory,
        "references": references,
        "records": records,
        "unmapped": dict(sorted(unmapped.items())),
        "coverage": {key: tuple(value) for key, value in sorted(coverage.items())},
        "summary": summary,
    }


def _ref_dict(ref):
    return {
        "group": ref.group,
        "index": ref.index,
        "directory_at": location(DIRECTORY_BANK, cpu_address(ref.directory_offset)),
        "table": location(ref.table_bank, ref.table_address),
        "pointer_at": location(ref.table_bank, cpu_address(ref.pointer_offset)),
    }


def _json_document(result):
    group_counts = Counter(ref.group for ref in result["references"])
    return {
        "schema": "shiren-gb2-script-v1",
        "rom_sha1": result["rom_sha1"],
        "selector": location(SELECTOR_BANK, SELECTOR_ADDRESS),
        "directory": {
            "location": location(DIRECTORY_BANK, DIRECTORY_ADDRESS),
            "record_size": DIRECTORY_RECORD_SIZE,
            "groups": [
                {
                    "group": entry.group,
                    "directory_at": location(
                        DIRECTORY_BANK, cpu_address(entry.directory_offset)
                    ),
                    "table": location(entry.table_bank, entry.table_address),
                    "entries": group_counts[entry.group],
                }
                for entry in result["directory"]
            ],
        },
        "summary": result["summary"],
        "unmapped_valid_glyphs": result["unmapped"],
        "coverage": {
            key: [
                location(offset // BANK_SIZE, cpu_address(offset)) for offset in offsets
            ]
            for key, offsets in result["coverage"].items()
        },
        "records": [
            {
                "id": record.id,
                "bank": record.bank,
                "address": "%04X" % record.address,
                "terminator_at": location(record.bank, record.terminator_address),
                "original_hex": record.raw.hex().upper(),
                "source": record.source,
                "interior_of": record.interior_of or None,
                "controls": list(record.controls),
                "references": [_ref_dict(ref) for ref in record.references],
            }
            for record in result["records"]
        ],
    }


def _ref_label(ref):
    return "g%03d[%03d]@%s" % (
        ref.group,
        ref.index,
        location(ref.table_bank, cpu_address(ref.pointer_offset)),
    )


def write_outputs(result, output_dir):
    """Write ignored machine-readable JSON and translator-facing TSV outputs."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "script.json"
    tsv_path = output_dir / "script.tsv"
    json_path.write_text(
        json.dumps(_json_document(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            (
                "id",
                "length",
                "original_hex",
                "references",
                "interior_of",
                "japanese",
                "english",
            )
        )
        for record in result["records"]:
            writer.writerow(
                (
                    record.id,
                    len(record.raw),
                    record.raw.hex().upper(),
                    ";".join(_ref_label(ref) for ref in record.references),
                    record.interior_of,
                    record.source,
                    "",
                )
            )
    return json_path, tsv_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--out", default="script", help="output directory (default: script)")
    parser.add_argument("--check", action="store_true", help="validate without writing outputs")
    args = parser.parse_args(argv)
    try:
        result = extract(Path(args.rom).read_bytes())
        paths = () if args.check else write_outputs(result, args.out)
    except (ExtractError, OSError, ValueError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    summary = result["summary"]
    print(
        "%d groups / %d tables / %d references -> %d unique records"
        % (
            summary["directory_groups"],
            summary["unique_tables"],
            summary["pointer_references"],
            summary["unique_records"],
        )
    )
    print(
        "%d rendered glyphs; %d valid glyph codes still unmapped (%d occurrences)"
        % (
            summary["rendered_glyphs"],
            summary["unmapped_valid_glyph_codes"],
            summary["unmapped_valid_glyph_occurrences"],
        )
    )
    print(
        "density census: %d referenced; %d table bytes; %d source continuations; "
        "prefix-before-reference: %d; %d unexplained"
        % (
            summary["referenced_density_candidates"],
            summary["density_pointer_table_false_positives"],
            summary["density_source_continuations"],
            summary["density_prefix_before_reference"],
            summary["unexplained_density_candidates"],
        )
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
