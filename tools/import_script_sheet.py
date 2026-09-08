#!/usr/bin/env python3
"""Check, build or apply the full translator-review TSV through GB2's existing owners.

Only edited_en proposes changes. By default nothing is written. --output creates a
test ROM and IPS; --apply updates authoritative project files. Both may be combined.
The sheet reader is separate from the browser and native insertion entry points.
"""
import argparse
import csv
from dataclasses import dataclass
import difflib
import io
from pathlib import Path
import tempfile

import allocate
import english_font
import extract
import ips
import prose_web
import runtime_widths
import translations
import workbench_web as web


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIRS = ("script/en", "script/organized", "script/drafts", "script/editing")
FIELDS = ("id", "loc", "bytes", "jp", "en", "edited_en")


def baseline_rows(rom, result, current):
    """Reconstruct the exported, inserted baseline without changing any files."""
    translated = translations.load_mapping(current, result["records"])
    allocation = allocate.allocate(rom, record_overrides=translations.encoded_overrides(translated))
    rows = {}
    for record in result["records"]:
        key = (record.bank, record.address)
        entry = translated.get(key)
        raw = entry.encoded if entry is not None else record.raw
        text = entry.text if entry is not None else record.source
        placement = allocation.record_placements[key]
        rows[record.id] = dict(id=record.id,
            loc=extract.location(placement.output_bank, placement.output_address),
            bytes=str(len(raw)), jp=record.source,
            en=text if raw else translations.EMPTY_SENTINEL, edited_en="")
    return rows


def parse_sheet(text, baseline, profiles):
    """Accept spreadsheet quoting/BOM/CRLF and row sorting; preserve cell text exactly."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline=""), delimiter="\t", strict=True)
    if len(reader.fieldnames or ()) != len(FIELDS) or set(reader.fieldnames or ()) != set(FIELDS):
        raise ValueError("Use the full review TSV with columns: " + ", ".join(FIELDS))
    seen, changes = set(), {}
    for row in reader:
        line = reader.line_num
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Line %d has the wrong number of TSV cells" % line)
        record_id = row["id"]
        if record_id not in baseline:
            raise ValueError("Line %d has unknown record ID %r" % (line, record_id))
        if record_id in seen:
            raise ValueError("Line %d duplicates record %s" % (line, record_id))
        seen.add(record_id)
        for field in FIELDS[:-1]:
            if row[field] != baseline[record_id][field]:
                raise ValueError("%s: %s baseline differs from this project. Keep the original columns; "
                                 "reconcile with a fresh sheet if the project changed." % (record_id, field))
        edited = row["edited_en"]
        # A filled copy of the baseline is still a no-op, including fixed rows.
        if not edited or edited == row["en"]:
            continue
        profile = profiles[record_id]
        if not profile["editable"]:
            raise ValueError("%s is reference-only: %s" % (record_id, profile["reason"]))
        if len(edited) > prose_web.MAX_TEXT or any(c in edited for c in "\t\r\n"):
            raise ValueError("%s: edited_en is too long or contains a tab/newline; use <br> for a game line break"
                             % record_id)
        changes[record_id] = edited
    missing = set(baseline) - seen
    if missing:
        raise ValueError("The full sheet is missing %d records (first: %s). Export all rows, including filtered rows."
                         % (len(missing), sorted(missing)[0]))
    return changes


def workspace_snapshot():
    return {p: p.read_bytes() for folder in WORKSPACE_DIRS
            for p in (ROOT / folder).glob("*") if p.is_file()}


@dataclass
class PreparedSheet:
    rom_path: Path
    rom: bytes
    sheet_path: Path
    sheet_bytes: bytes
    revision: str
    originals: dict
    changes: dict
    files: dict
    records: tuple
    merged: dict
    validation: dict


def prepare_sheet(rom_path, sheet_path):
    """Use the same whole-workspace checks and draft owners as the subject workbenches."""
    data = web.check_assets()
    originals = workspace_snapshot()
    rom_path, sheet_path = Path(rom_path).resolve(), Path(sheet_path).resolve()
    rom, sheet_bytes = rom_path.read_bytes(), sheet_path.read_bytes()
    result, scenes, editor, current, font_rom, _, exceptions, _ = prose_web.load_workspace(rom)
    web.check_ownership(result, scenes, editor, current)
    profiles = {row["loc"]: row for row in data["records"]}
    baseline = baseline_rows(rom, result, current)
    if set(profiles) != set(baseline):
        raise ValueError("Workbench coverage differs from the extracted script")
    changes = parse_sheet(sheet_bytes.decode("utf-8-sig"), baseline, profiles)

    # Static names are applied before measuring any consumer. Unchanged owned
    # entries keep their authored drafts, not the wrapped en copied into the sheet.
    merged = dict(current)
    merged.update(changes)
    contract = runtime_widths.analyze(font_rom, result,
        translations.load_mapping(merged, result["records"])).contract
    by_id = {record.id: record for record in result["records"]}
    for row in data["records"]:
        if not row["editable"]:
            continue
        record_id = row["loc"]
        checked = web.python_check(by_id[record_id], row, changes.get(record_id, row["draft"]), font_rom, contract)
        if not checked["valid"]:
            raise ValueError("%s: %s" % (record_id, checked["error"]))
        merged[record_id] = checked["wrapped"]
    _, validation = web.check_project(rom, result, merged, exceptions)
    with tempfile.TemporaryDirectory(prefix="gb2-script-sheet-") as directory:
        proposed = web.staged_files(rom, result, scenes, editor, merged, changes, directory)
    files = {p: value for p, value in proposed.items() if value != originals.get(p)} if changes else {}
    prepared = PreparedSheet(rom_path, rom, sheet_path, sheet_bytes, data["inputRevision"], originals,
        changes, files, tuple(result["records"]), merged, validation)
    require_unchanged(prepared)
    return prepared


def require_unchanged(prepared):
    if web.input_revision() != prepared.revision or workspace_snapshot() != prepared.originals:
        raise ValueError("Project files changed during the check; rerun before writing")
    if prepared.sheet_path.read_bytes() != prepared.sheet_bytes:
        raise ValueError("The review sheet changed during the check; rerun before writing")
    if prepared.rom_path.read_bytes() != prepared.rom:
        raise ValueError("The source ROM changed during the check; rerun before writing")


def output_paths(destination, font_style):
    path = Path(destination).absolute()
    if path.suffix.lower() not in (".gbc", ".gb"):
        raise ValueError("--output must name a .gbc or .gb file")
    if font_style == "both":
        import build
        roms = build.font_variant_output_paths(path)
    else:
        roms = {font_style: path}
    for rom in roms.values():
        for target in (rom, rom.with_suffix(".ips")):
            if target.exists() or target.is_symlink():
                raise FileExistsError("%s already exists; choose a new --output filename" % target)
    return roms


def build_outputs(prepared, paths):
    import build
    translated = translations.load_mapping(prepared.merged, prepared.records)
    result = extract.extract(prepared.rom)
    contract = runtime_widths.analyze(english_font.install(prepared.rom), result, translated).contract
    files = {}
    for style, path in paths.items():
        output, _, _ = build.build_rom(prepared.rom, translations.encoded_overrides(translated),
            runtime_contract=contract, font_style=style)
        patch = ips.create_patch(prepared.rom, output)
        if ips.apply_patch(prepared.rom, patch) != output:
            raise ValueError("The generated IPS does not reconstruct its ROM")
        files[path], files[path.with_suffix(".ips")] = output, patch
    return files


def execute(prepared, apply=False, output=None, font_style=english_font.SHADOWED_STYLE):
    require_unchanged(prepared)
    paths = output_paths(output, font_style) if output is not None else {}
    output_files = build_outputs(prepared, paths) if paths else {}
    for path, content in prepared.files.items():
        if path.suffix == ".tsv" and "organized" not in path.parts:
            relative = str(path.relative_to(ROOT))
            print("".join(difflib.unified_diff((prepared.originals.get(path) or b"").decode().splitlines(True),
                content.decode().splitlines(True), fromfile=relative, tofile="proposed/" + relative)), end="")
    print("Validated %d proposed edits across %d records; %d logical references passed the full build."
          % (len(prepared.changes), len(prepared.records), prepared.validation["exact_references"]))
    require_unchanged(prepared)
    proposed = dict(prepared.files) if apply else {}
    proposed.update(output_files)
    if proposed:
        originals = dict(prepared.originals)
        originals.update({path: None for path in output_files})
        web.apply_transaction(proposed, originals)
    if apply and prepared.changes:
        print("Applied %d project files. Regenerate both web catalogues and export a fresh sheet for the next batch."
              % len(prepared.files))
    elif apply:
        print("No proposed edits; project files unchanged.")
    else:
        print("Project files unchanged. Add --apply to synchronize approved edits.")
    for path in output_files:
        print("Wrote %s" % path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="matching original Japanese ROM")
    parser.add_argument("sheet", help="full TSV with id, loc, bytes, jp, en, edited_en")
    parser.add_argument("--apply", action="store_true", help="apply validated edits to the project owners")
    parser.add_argument("--output", help="write a separate test ROM and IPS without requiring --apply")
    parser.add_argument("--font-style", choices=english_font.FONT_STYLES + ("both",),
                        default=english_font.SHADOWED_STYLE, help="test ROM font (default: shadowed)")
    args = parser.parse_args(argv)
    try:
        if args.output:
            output_paths(args.output, args.font_style)
        prepared = prepare_sheet(args.rom, args.sheet)
        execute(prepared, apply=args.apply, output=args.output, font_style=args.font_style)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, "error: %s\n" % exc)


if __name__ == "__main__":
    main()
