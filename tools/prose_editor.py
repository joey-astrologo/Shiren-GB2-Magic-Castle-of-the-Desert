#!/usr/bin/env python3
"""Maintain the scene-ordered, source-free GB2 prose editing document.

The ROM stores dialogue by pointer group.  This tool presents the same stable
records in authored narrative order, synchronizes approved edits into the
measured prose draft, and then uses ``wrap_en`` to update the build catalogs.
Hashes prevent simultaneous edits in both views from being silently lost.
"""
import argparse
import csv
from hashlib import sha1
import json
from pathlib import Path
import sys
import tempfile

import extract
import prose_scenes
import wrap_en


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDITOR = ROOT / "script" / "editing" / "prose.tsv"
DEFAULT_STATE = ROOT / "script" / "editing" / "prose.generated.json"
DEFAULT_DRAFT = wrap_en.DEFAULT_DRAFT
DEFAULT_WRAP_STATE = wrap_en.DEFAULT_STATE
DEFAULT_CATALOG = wrap_en.DEFAULT_CATALOG
DEFAULT_OVERLAYS = wrap_en.DEFAULT_OVERLAYS
SCHEMA = "shiren-gb2-scene-prose-editor-v1"
FIELDS = (
    "scene_order",
    "scene_id",
    "phase",
    "scene_title",
    "record_order",
    "id",
    "english",
)
EMPTY = "<empty>"


class ProseEditorError(ValueError):
    """The scene editor, prose draft, or synchronization state diverged."""


def expected_rows(result, scenes, drafts):
    """Return scene-ordered rows seeded from the authoritative prose draft."""
    records = {record.id: record for record in result["records"]}
    rows = []
    for scene_order, scene in enumerate(scenes, 1):
        for record_order, record_id in enumerate(scene.record_ids, 1):
            draft = drafts[record_id].draft
            if not draft and not records[record_id].raw:
                draft = EMPTY
            rows.append(
                {
                    "scene_order": str(scene_order),
                    "scene_id": scene.spec.scene_id,
                    "phase": scene.spec.phase,
                    "scene_title": scene.spec.title,
                    "record_order": str(record_order),
                    "id": record_id,
                    "english": draft,
                }
            )
    return tuple(rows)


def _metadata(row):
    return tuple(row[field] for field in FIELDS[:-1])


def read_editor(path, expected):
    """Read the editor and require exact scene membership and ordering."""
    path = Path(path)
    with path.open(encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ProseEditorError(
                "%s must contain exactly: %s" % (path, ", ".join(FIELDS))
            )
        rows = list(reader)
    if len(rows) != len(expected):
        raise ProseEditorError(
            "%s has %d rows; expected %d" % (path, len(rows), len(expected))
        )
    seen = set()
    for line_number, (row, wanted) in enumerate(zip(rows, expected), 2):
        if None in row or any(value is None for value in row.values()):
            raise ProseEditorError(
                "%s:%d has the wrong number of columns" % (path, line_number)
            )
        if row["id"] in seen:
            raise ProseEditorError(
                "%s:%d duplicates record %s" % (path, line_number, row["id"])
            )
        seen.add(row["id"])
        if _metadata(row) != _metadata(wanted):
            raise ProseEditorError(
                "%s:%d scene metadata or ordering changed for %s"
                % (path, line_number, wanted["id"])
            )
    return tuple(rows)


def write_editor(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def editor_sha1(rows):
    digest = sha1()
    for row in rows:
        for field in FIELDS:
            digest.update(row[field].encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def draft_rows_from_editor(result, eligible, rows):
    """Convert editor rows back to wrap_en rows without encoding fake empties."""
    by_id = {row["id"]: row for row in rows}
    records = {row.record.id: row.record for row in eligible}
    converted = {}
    for eligible_row in eligible:
        record_id = eligible_row.record.id
        text = by_id[record_id]["english"]
        if text == EMPTY:
            if records[record_id].raw:
                raise ProseEditorError(
                    "%s uses %s but its native record is not empty"
                    % (record_id, EMPTY)
                )
            text = ""
        converted[record_id] = wrap_en.DraftRow(
            record_id, eligible_row.sections, text
        )
    return converted


def _draft_sha1(eligible, drafts):
    return wrap_en.draft_sha1(
        tuple(drafts[row.record.id] for row in eligible)
    )


def _base_state(result, scenes, editor_hash, draft_hash):
    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "membership_sha1": prose_scenes._membership_sha1(scenes),
        "editor_sha1": editor_hash,
        "draft_sha1": draft_hash,
    }


def read_state(path, result, scenes):
    path = Path(path)
    if not path.exists():
        raise ProseEditorError("%s does not exist; run with --init" % path)
    data = json.loads(path.read_text(encoding="ascii"))
    if data.get("schema") != SCHEMA:
        raise ProseEditorError("%s has an unsupported schema" % path)
    if data.get("rom_sha1") != result["rom_sha1"]:
        raise ProseEditorError("%s belongs to a different ROM" % path)
    if data.get("membership_sha1") != prose_scenes._membership_sha1(scenes):
        raise ProseEditorError("%s belongs to a different scene map" % path)
    for field in ("editor_sha1", "draft_sha1"):
        value = data.get(field, "")
        if not isinstance(value, str) or len(value) != 40:
            raise ProseEditorError("%s has an invalid %s" % (path, field))
    return data


def write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )


def _check_ownership(state, editor_hash, draft_hash):
    editor_changed = editor_hash != state["editor_sha1"]
    draft_changed = draft_hash != state["draft_sha1"]
    if draft_changed:
        detail = "both views changed" if editor_changed else "the generated draft changed"
        raise ProseEditorError(
            "%s since the last scene-editor sync; reconcile before applying"
            % detail
        )


def _prepare(source_rom, result, eligible, converted, args):
    with tempfile.TemporaryDirectory(prefix="gb2-prose-editor-") as directory:
        prospective = Path(directory) / "prose.tsv"
        wrap_en.write_draft(prospective, eligible, converted)
        return wrap_en.prepare_workspace(
            source_rom,
            result,
            draft_path=prospective,
            state_path=args.wrap_state,
            catalog_dir=args.catalog,
            overlay_dir=args.translations,
            exceptions_path=args.exceptions,
        )


def summary(scenes, rows):
    authored = sum(bool(row["english"] and row["english"] != EMPTY) for row in rows)
    explicit_empty = sum(row["english"] == EMPTY for row in rows)
    complete_scenes = 0
    for scene in scenes:
        scene_rows = [row for row in rows if row["scene_id"] == scene.spec.scene_id]
        complete_scenes += all(row["english"] for row in scene_rows)
    return {
        "schema": SCHEMA,
        "scenes": len(scenes),
        "records": len(rows),
        "authored_records": authored,
        "explicit_empty_records": explicit_empty,
        "complete_scenes": complete_scenes,
        "editor_sha1": editor_sha1(rows),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--editor", default=str(DEFAULT_EDITOR))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--draft", default=str(DEFAULT_DRAFT))
    parser.add_argument("--wrap-state", default=str(DEFAULT_WRAP_STATE))
    parser.add_argument("--map", default=str(prose_scenes.DEFAULT_MAP))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--translations", default=str(DEFAULT_OVERLAYS))
    parser.add_argument("--exceptions")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--init", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        source_rom = Path(args.rom).read_bytes()
        result = extract.extract(source_rom)
        specs = prose_scenes.read_map(args.map)
        scenes = prose_scenes.build_scenes(result, specs)
        eligible = wrap_en.prose_rows(result)
        current_drafts = wrap_en.read_draft(args.draft, eligible)
        seeded = expected_rows(result, scenes, current_drafts)
        if args.init:
            if Path(args.editor).exists():
                rows = read_editor(args.editor, seeded)
            else:
                rows = seeded
                write_editor(args.editor, rows)
            converted = draft_rows_from_editor(result, eligible, rows)
            state = _base_state(
                result,
                scenes,
                editor_sha1(rows),
                _draft_sha1(eligible, current_drafts),
            )
            write_state(args.state, state)
            verb = "initialized"
        else:
            rows = read_editor(args.editor, seeded)
            state = read_state(args.state, result, scenes)
            editor_hash = editor_sha1(rows)
            current_draft_hash = _draft_sha1(eligible, current_drafts)
            _check_ownership(state, editor_hash, current_draft_hash)
            converted = draft_rows_from_editor(result, eligible, rows)
            workspace = _prepare(source_rom, result, eligible, converted, args)
            if args.apply:
                wrap_en.write_draft(args.draft, eligible, converted)
                wrap_en.apply_workspace(
                    result,
                    workspace,
                    args.catalog,
                    args.translations,
                    args.wrap_state,
                )
                write_state(
                    args.state,
                    _base_state(
                        result,
                        scenes,
                        editor_hash,
                        _draft_sha1(eligible, converted),
                    ),
                )
            verb = "applied" if args.apply else "checked"
        measured = summary(scenes, rows)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        extract.ExtractError,
        prose_scenes.SceneMapError,
        wrap_en.WrapError,
        ProseEditorError,
    ) as exc:
        parser.exit(1, "error: %s\n" % exc)

    if args.json:
        print(json.dumps(measured, indent=2, sort_keys=True))
    else:
        print(
            "%s: %d records in %d scenes; %d authored, %d explicit empty"
            % (
                verb,
                measured["records"],
                measured["scenes"],
                measured["authored_records"],
                measured["explicit_empty_records"],
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
