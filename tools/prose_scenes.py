#!/usr/bin/env python3
"""Validate the source-free scene map for GB2 story/event prose.

The script directory stores dialogue by logical group, not narrative order.  This
module joins groups 33..112 to an authored semantic scene map, collapses the
game's duplicate pointer tables, and proves that every one of the 1,768 prose
records belongs to exactly one scene family.  Japanese text never enters the
tracked map or fixture.
"""
import argparse
import csv
from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import re
import sys

import extract
import wrap_en


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "script" / "drafts" / "prose_scenes.tsv"
DEFAULT_DRAFT = ROOT / "script" / "drafts" / "prose.tsv"
SCHEMA = "shiren-gb2-prose-scenes-v1"
FIRST_GROUP = 33
LAST_GROUP = 112
OPENING_GROUPS = (34, 35, 36, 37)
ILPA_REUNION_GROUPS = (38, 39)


class SceneMapError(ValueError):
    """The prose scene map is stale, ambiguous, or incomplete."""


@dataclass(frozen=True)
class Selector:
    group: int
    first_index: int
    last_index: int


@dataclass(frozen=True)
class SceneSpec:
    scene_id: str
    selectors: tuple
    phase: str
    title: str

    @property
    def groups(self):
        return tuple(dict.fromkeys(selector.group for selector in self.selectors))


@dataclass(frozen=True)
class Scene:
    spec: SceneSpec
    record_ids: tuple


def _map_sha1(specs):
    digest = sha1()
    for spec in specs:
        for value in (
            spec.scene_id,
            ";".join(
                str(selector.group)
                if (selector.first_index, selector.last_index) == (0, 0xFF)
                else "%d:%d-%d"
                % (selector.group, selector.first_index, selector.last_index)
                for selector in spec.selectors
            ),
            spec.phase,
            spec.title,
        ):
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def read_map(path=DEFAULT_MAP):
    """Read and structurally validate the source-free authored scene map."""
    path = Path(path)
    out = []
    seen_ids = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or ())
        required = {"scene_id", "groups", "phase", "title"}
        if fields != required:
            raise SceneMapError(
                "%s must contain exactly: %s"
                % (path, ", ".join(sorted(required)))
            )
        for line_number, values in enumerate(reader, 2):
            if None in values or any(value is None for value in values.values()):
                raise SceneMapError("%s:%d has the wrong number of columns" % (path, line_number))
            scene_id = values["scene_id"]
            phase = values["phase"]
            title = values["title"]
            if not scene_id or not phase or not title:
                raise SceneMapError("%s:%d contains a blank field" % (path, line_number))
            if scene_id in seen_ids:
                raise SceneMapError("%s:%d duplicates scene %s" % (path, line_number, scene_id))
            selectors = []
            for value in values["groups"].split(";"):
                match = re.fullmatch(r"(\d+)(?::(\d+)(?:-(\d+))?)?", value)
                if not match:
                    raise SceneMapError("%s:%d has an invalid group selector" % (path, line_number))
                group = int(match.group(1))
                if not FIRST_GROUP <= group <= LAST_GROUP:
                    raise SceneMapError("%s:%d group %d is outside the prose range" % (path, line_number, group))
                if match.group(2) is None:
                    first_index, last_index = 0, 0xFF
                else:
                    first_index = int(match.group(2))
                    last_index = int(match.group(3) or match.group(2))
                if not 0 <= first_index <= last_index <= 0xFF:
                    raise SceneMapError("%s:%d has an invalid index range" % (path, line_number))
                selectors.append(Selector(group, first_index, last_index))
            if not selectors:
                raise SceneMapError("%s:%d has no group selectors" % (path, line_number))
            seen_ids.add(scene_id)
            out.append(SceneSpec(scene_id, tuple(selectors), phase, title))
    return tuple(out)


def _group_records(result):
    by_group = {group: [] for group in range(FIRST_GROUP, LAST_GROUP + 1)}
    for record in result["records"]:
        for reference in record.references:
            if FIRST_GROUP <= reference.group <= LAST_GROUP:
                by_group[reference.group].append((reference.index, record.id))
    return {group: tuple(sorted(rows)) for group, rows in by_group.items()}


def build_scenes(result, specs):
    """Resolve every scene and prove aliases do not cross semantic families."""
    by_group = _group_records(result)
    scenes = []
    owner = {}
    reference_owner = {}
    for spec in specs:
        record_ids = []
        for selector in spec.selectors:
            selected = [
                (index, record_id)
                for index, record_id in by_group[selector.group]
                if selector.first_index <= index <= selector.last_index
            ]
            if not selected:
                raise SceneMapError(
                    "scene %s selector %d:%d-%d has no records"
                    % (spec.scene_id, selector.group, selector.first_index, selector.last_index)
                )
            for index, record_id in selected:
                reference = (selector.group, index)
                previous = reference_owner.setdefault(reference, spec.scene_id)
                if previous != spec.scene_id:
                    raise SceneMapError(
                        "reference %d:%d crosses scenes %s and %s"
                        % (selector.group, index, previous, spec.scene_id)
                    )
                if record_id not in record_ids:
                    record_ids.append(record_id)
        for record_id in record_ids:
            previous = owner.setdefault(record_id, spec.scene_id)
            if previous != spec.scene_id:
                raise SceneMapError(
                    "record %s crosses scenes %s and %s"
                    % (record_id, previous, spec.scene_id)
                )
        scenes.append(Scene(spec, tuple(record_ids)))

    expected_references = {
        (group, index)
        for group, rows in by_group.items()
        for index, _record_id in rows
    }
    mapped_references = set(reference_owner)
    if mapped_references != expected_references:
        raise SceneMapError(
            "logical reference coverage changed: missing=%d extra=%d"
            % (
                len(expected_references - mapped_references),
                len(mapped_references - expected_references),
            )
        )

    eligible = {row.record.id for row in wrap_en.prose_rows(result)}
    mapped = set(owner)
    if mapped != eligible:
        raise SceneMapError(
            "scene membership changed: missing=%d extra=%d"
            % (len(eligible - mapped), len(mapped - eligible))
        )
    return tuple(scenes)


def _membership_sha1(scenes):
    digest = sha1()
    for scene in scenes:
        digest.update(scene.spec.scene_id.encode("ascii"))
        digest.update(b"\0")
        for record_id in scene.record_ids:
            digest.update(record_id.encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def _is_duplicate_group_scene(scene, by_group):
    if len(scene.spec.groups) < 2:
        return False
    rows = []
    for group in scene.spec.groups:
        selectors = [selector for selector in scene.spec.selectors if selector.group == group]
        group_rows = tuple(
            record_id
            for index, record_id in by_group[group]
            if any(selector.first_index <= index <= selector.last_index for selector in selectors)
        )
        rows.append(group_rows)
    return all(row == rows[0] for row in rows[1:])


def summary(result, specs, scenes, draft_rows):
    translated = {record_id for record_id, row in draft_rows.items() if row.draft}
    by_group = _group_records(result)
    opening = tuple(
        record_id
        for scene in scenes
        if any(group in OPENING_GROUPS for group in scene.spec.groups)
        for record_id in scene.record_ids
    )
    ilpa_reunion = tuple(
        record_id
        for scene in scenes
        if any(group in ILPA_REUNION_GROUPS for group in scene.spec.groups)
        for record_id in scene.record_ids
    )
    scene_rows = []
    for scene in scenes:
        translated_records = sum(record_id in translated for record_id in scene.record_ids)
        scene_rows.append(
            {
                "scene_id": scene.spec.scene_id,
                "groups": list(scene.spec.groups),
                "phase": scene.spec.phase,
                "records": len(scene.record_ids),
                "translated_records": translated_records,
                "complete": translated_records == len(scene.record_ids),
            }
        )
    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "group_range": [FIRST_GROUP, LAST_GROUP],
        "logical_groups": LAST_GROUP - FIRST_GROUP + 1,
        "scenes": len(scenes),
        "duplicate_group_scenes": sum(_is_duplicate_group_scene(scene, by_group) for scene in scenes),
        "multi_group_scenes": sum(len(scene.spec.groups) > 1 for scene in scenes),
        "records": sum(len(scene.record_ids) for scene in scenes),
        "translated_records": sum(record_id in translated for scene in scenes for record_id in scene.record_ids),
        "complete_scenes": sum(row["complete"] for row in scene_rows),
        "scene_map_sha1": _map_sha1(specs),
        "membership_sha1": _membership_sha1(scenes),
        "opening_batch": {
            "groups": list(OPENING_GROUPS),
            "records": len(opening),
            "first_id": opening[0],
            "last_id": opening[-1],
            "membership_sha1": sha1("\0".join(opening).encode("ascii")).hexdigest(),
            "translated_records": sum(record_id in translated for record_id in opening),
        },
        "ilpa_reunion_batch": {
            "groups": list(ILPA_REUNION_GROUPS),
            "records": len(ilpa_reunion),
            "first_id": ilpa_reunion[0],
            "last_id": ilpa_reunion[-1],
            "membership_sha1": sha1(
                "\0".join(ilpa_reunion).encode("ascii")
            ).hexdigest(),
            "translated_records": sum(
                record_id in translated for record_id in ilpa_reunion
            ),
        },
        "scene_rows": scene_rows,
    }


def analyze(rom, map_path=DEFAULT_MAP, draft_path=DEFAULT_DRAFT):
    result = extract.extract(rom)
    specs = read_map(map_path)
    scenes = build_scenes(result, specs)
    eligible = wrap_en.prose_rows(result)
    drafts = wrap_en.read_draft(draft_path, eligible)
    return summary(result, specs, scenes, drafts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--map", default=DEFAULT_MAP)
    parser.add_argument("--draft", default=DEFAULT_DRAFT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = analyze(Path(args.rom).read_bytes(), args.map, args.draft)
    except (OSError, SceneMapError, extract.ExtractError, wrap_en.WrapError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(
            "%d prose records in %d scenes (%d logical groups); %d translated"
            % (data["records"], data["scenes"], data["logical_groups"], data["translated_records"])
        )
        opening = data["opening_batch"]
        print(
            "opening groups %s: %d records, %d translated"
            % ("-".join(str(group) for group in opening["groups"]), opening["records"], opening["translated_records"])
        )
        ilpa_reunion = data["ilpa_reunion_batch"]
        print(
            "Ilpa/reunion groups %s: %d records, %d translated"
            % (
                "-".join(str(group) for group in ilpa_reunion["groups"]),
                ilpa_reunion["records"],
                ilpa_reunion["translated_records"],
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
