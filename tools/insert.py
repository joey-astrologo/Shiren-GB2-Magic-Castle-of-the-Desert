#!/usr/bin/env python3
"""Write and verify deterministic GB2 script relocations.

This writes the bank images from :mod:`allocate`, repoints all 126 bank/address directory
rows, fixes both cartridge checksums, and re-reads all 7,163 logical references from the
actual output bytes.  The identity entry points retain the byte-exact no-translation build;
``write_relocated`` and ``validate_relocated`` support stable-record replacements.
"""
import argparse
from hashlib import sha1
from pathlib import Path
import sys

import allocate
import cartridge
import codec
import extract
import far_text


class InsertError(ValueError):
    """The identity ROM cannot be written or fails post-write validation."""


def directory_entry_offset(group):
    if not 0 <= group < extract.DIRECTORY_COUNT:
        raise InsertError("directory group out of range: %d" % group)
    return (
        extract.file_offset(extract.DIRECTORY_BANK, extract.DIRECTORY_ADDRESS)
        + group * extract.DIRECTORY_RECORD_SIZE
    )


def read_directory_entry(rom, group):
    """Return ``(bank, table_address)`` from one actual ROM directory row."""
    at = directory_entry_offset(group)
    address = rom[at] | (rom[at + 1] << 8)
    return rom[at + 2], address


def read_source_record(rom, group, index):
    """Follow the output ROM's directory and relocated far pointer losslessly."""
    bank, table_address = read_directory_entry(rom, group)
    if bank <= 0 or (bank + 1) * allocate.BANK_SIZE > len(rom):
        raise InsertError("group %d has invalid ROM bank %d" % (group, bank))
    if not 0x4000 <= table_address < 0x8000:
        raise InsertError(
            "group %d has invalid table address $%04X" % (group, table_address)
        )
    table_offset = extract.file_offset(bank, table_address)
    entries = rom[table_offset] | (rom[table_offset + 1] << 8)
    if not 0 <= index < entries:
        raise InsertError("group %d has no entry %d" % (group, index))
    pointer_offset = table_offset + 2 + index * 3
    table_bank_end = (bank + 1) * allocate.BANK_SIZE
    if pointer_offset + 3 > table_bank_end:
        raise InsertError("group %d entry %d pointer leaves bank %d" % (group, index, bank))
    address = rom[pointer_offset] | (rom[pointer_offset + 1] << 8)
    record_bank = rom[pointer_offset + 2]
    if not 0x4000 <= address < 0x8000:
        raise InsertError(
            "group %d entry %d has invalid target $%04X" % (group, index, address)
        )

    if record_bank <= 0 or (record_bank + 1) * allocate.BANK_SIZE > len(rom):
        raise InsertError(
            "group %d entry %d has invalid record bank %d"
            % (group, index, record_bank)
        )
    at = extract.file_offset(record_bank, address)
    bank_end = (record_bank + 1) * allocate.BANK_SIZE
    out = bytearray()
    while at < bank_end:
        code = rom[at]
        if code == codec.TERMINATOR:
            return bytes(out)
        size = codec.source_token_size(code)
        if at + size > bank_end:
            break
        out += rom[at:at + size]
        at += size
    raise InsertError("group %d entry %d is unterminated" % (group, index))


def write_relocated(rom, allocation):
    """Write one completed allocation into its source ROM and fix checksums."""
    rom = bytes(rom)
    if sha1(rom).hexdigest() != allocation.source_rom_sha1:
        raise InsertError("allocation source hash does not match the input ROM")

    out = bytearray(rom)
    for bank, image in allocation.bank_images.items():
        if len(image) != allocate.BANK_SIZE:
            raise InsertError("allocated bank %d has invalid image size" % bank)
        start = bank * allocate.BANK_SIZE
        out[start:start + allocate.BANK_SIZE] = image

    for group in range(extract.DIRECTORY_COUNT):
        try:
            table = allocation.group_tables[group]
        except KeyError:
            raise InsertError("allocation has no directory group %d" % group) from None
        at = directory_entry_offset(group)
        out[at] = table.output_address & 0xFF
        out[at + 1] = table.output_address >> 8
        out[at + 2] = table.output_bank

    try:
        out = bytearray(far_text.install(out))
    except far_text.FarTextError as exc:
        raise InsertError(str(exc)) from exc
    cartridge.fix_checksums(out)
    return bytes(out), allocation


def write_identity(rom, allocation=None):
    """Return the identity-relocated ROM and the allocation used to build it."""
    rom = bytes(rom)
    allocation = allocation or allocate.allocate(rom)
    if allocation.override_keys:
        raise InsertError("identity writer received translated record overrides")
    return write_relocated(rom, allocation)


def validate_relocated(original, output, allocation, record_overrides=None):
    """Validate every relocated lookup directly from the output ROM bytes."""
    original = bytes(original)
    output = bytes(output)
    if len(output) != len(original):
        raise InsertError(
            "identity output changed ROM size from %d to %d" % (len(original), len(output))
        )
    record_overrides = {
        key: bytes(raw) for key, raw in (record_overrides or {}).items()
    }
    if frozenset(record_overrides) != allocation.override_keys:
        raise InsertError("validation overrides do not match the allocation")
    source = extract.extract(original)
    try:
        far_text.verify(output)
    except far_text.FarTextError as exc:
        raise InsertError(str(exc)) from exc
    records = {(record.bank, record.address): record for record in source["records"]}

    for group in range(extract.DIRECTORY_COUNT):
        table = allocation.group_tables[group]
        actual = read_directory_entry(output, group)
        expected = table.output_bank, table.output_address
        if actual != expected:
            raise InsertError(
                "group %d directory is %d:$%04X, expected %d:$%04X"
                % (group, actual[0], actual[1], expected[0], expected[1])
            )

    exact = 0
    overridden = 0
    for reference in source["references"]:
        source_key = reference.target_bank, reference.target_address
        expected = record_overrides.get(source_key, records[source_key].raw)
        actual = read_source_record(output, reference.group, reference.index)
        if actual != expected:
            raise InsertError(
                "group %d entry %d identity mismatch" % (reference.group, reference.index)
            )
        exact += 1
        overridden += source_key in record_overrides

    for bank, image in allocation.bank_images.items():
        start = bank * allocate.BANK_SIZE
        if output[start:start + allocate.BANK_SIZE] != image:
            raise InsertError("output bank %d differs from its allocation image" % bank)
    try:
        header, global_value = cartridge.verify_checksums(output)
    except ValueError as exc:
        raise InsertError(str(exc)) from exc
    validation = {
        "directory_groups": extract.DIRECTORY_COUNT,
        "logical_references": len(source["references"]),
        "exact_references": exact,
        "written_banks": len(allocation.bank_images),
        "header_checksum": "%02X" % header,
        "global_checksum": "%04X" % global_value,
    }
    if record_overrides:
        validation["overridden_records"] = len(record_overrides)
        validation["overridden_references"] = overridden
    return validation


def validate_identity(original, output, allocation=None):
    """Validate the override-free identity build."""
    allocation = allocation or allocate.allocate(original)
    if allocation.override_keys:
        raise InsertError("identity validation received translated record overrides")
    return validate_relocated(original, output, allocation)


def mutation_offsets(original, output):
    """Return every changed file offset in ascending order."""
    if len(original) != len(output):
        raise InsertError("cannot compare mutations across different ROM sizes")
    return tuple(
        offset
        for offset, (before, after) in enumerate(zip(original, output))
        if before != after
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument("output", help="output identity-relocated ROM")
    args = parser.parse_args(argv)
    source = Path(args.rom).read_bytes()
    try:
        output, allocation = write_identity(source)
        validation = validate_identity(source, output, allocation)
    except (allocate.AllocationError, extract.ExtractError, InsertError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print(
        "%d directory groups / %d references exact"
        % (validation["directory_groups"], validation["exact_references"])
    )
    print(
        "%d script bank(s) written; %d byte(s) changed"
        % (validation["written_banks"], len(mutation_offsets(source, output)))
    )
    print(
        "checksums   : header $%s global $%s"
        % (validation["header_checksum"], validation["global_checksum"])
    )
    print("output      : %s" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
