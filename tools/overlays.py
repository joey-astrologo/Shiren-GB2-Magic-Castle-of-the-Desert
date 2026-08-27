#!/usr/bin/env python3
"""Synchronize rich GB2 catalogs with tracked source-free English overlays.

``script/organized`` contains Japanese source and is deliberately ignored.
``script/en`` contains only stable IDs, semantic sections and English cells, so
it can be versioned.  This tool merges nonblank cells in both directions.  If
both sides contain different text for one stable ID it stops before writing;
it never decides which translation wins.
"""
import argparse
from collections import Counter
import csv
from hashlib import sha1
import json
from pathlib import Path
import sys

import extract
import organize


SCHEMA = "shiren-gb2-english-overlays-v1"


class OverlayError(ValueError):
    """The rich and compact translation workspaces cannot be merged safely."""


def merge_english(result, catalog_dir, overlay_dir):
    """Return every stable ID after conflict-safe bidirectional merging."""
    catalog = organize.read_existing_english(Path(catalog_dir), result)
    overlay = organize.read_existing_english(Path(overlay_dir), result)
    merged = {}
    for record in result["records"]:
        catalog_text = catalog.get(record.id, "")
        overlay_text = overlay.get(record.id, "")
        if catalog_text and overlay_text and catalog_text != overlay_text:
            raise OverlayError(
                "%s conflicts between %s and %s"
                % (record.id, catalog_dir, overlay_dir)
            )
        merged[record.id] = catalog_text or overlay_text
    return merged


def summary(result, organized, english_by_id):
    """Return the source-free overlay census and translation fingerprints."""
    by_category = {category.name: [] for category in organize.CATEGORIES}
    for row in organized:
        by_category[row.category].append(row)

    categories = []
    workspace_digest = sha1()
    translated_total = 0
    explicit_empty_total = 0
    for category in organize.CATEGORIES:
        rows = by_category[category.name]
        digest = sha1()
        translated = 0
        explicit_empty = 0
        sections = Counter()
        for row in rows:
            text = english_by_id.get(row.record.id, "")
            section_text = ";".join(row.sections)
            if text:
                translated += 1
            if text == "<empty>":
                explicit_empty += 1
            for section in row.sections:
                sections[section] += 1
            for target in (digest, workspace_digest):
                target.update(category.name.encode("ascii"))
                target.update(b"\0")
                target.update(row.record.id.encode("ascii"))
                target.update(b"\0")
                target.update(section_text.encode("ascii"))
                target.update(b"\0")
                target.update(text.encode("utf-8"))
                target.update(b"\0")
        translated_total += translated
        explicit_empty_total += explicit_empty
        categories.append(
            {
                "name": category.name,
                "filename": category.filename,
                "records": len(rows),
                "translated_records": translated,
                "explicit_empty_records": explicit_empty,
                "sections": dict(sorted(sections.items())),
                "overlay_sha1": digest.hexdigest(),
            }
        )

    return {
        "schema": SCHEMA,
        "rom_sha1": result["rom_sha1"],
        "partition_sha1": organize.summary(
            result, organized=organized
        )["partition_sha1"],
        "source_free": True,
        "records": len(organized),
        "translated_records": translated_total,
        "explicit_empty_records": explicit_empty_total,
        "workspace_sha1": workspace_digest.hexdigest(),
        "categories": categories,
    }


def _write_overlay(path, rows, english_by_id):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("id", "sections", "english"))
        for row in rows:
            writer.writerow(
                (
                    row.record.id,
                    ";".join(row.sections),
                    english_by_id.get(row.record.id, ""),
                )
            )


def write_outputs(result, output_dir, organized, english_by_id):
    """Write the compact category TSVs and their source-free manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    by_category = {category.name: [] for category in organize.CATEGORIES}
    for row in organized:
        by_category[row.category].append(row)

    paths = []
    for category in organize.CATEGORIES:
        path = output_dir / category.filename
        _write_overlay(path, by_category[category.name], english_by_id)
        paths.append(path)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            summary(result, organized, english_by_id),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    paths.append(manifest_path)
    return tuple(paths)


def synchronize(result, catalog_dir, overlay_dir):
    """Merge both workspaces, then rewrite them from one proven partition."""
    catalog_dir = Path(catalog_dir)
    overlay_dir = Path(overlay_dir)
    if catalog_dir.resolve() == overlay_dir.resolve():
        raise OverlayError("catalog and overlay directories must be different")

    organized = organize.classify(result)
    english_by_id = merge_english(result, catalog_dir, overlay_dir)
    organize.write_outputs(
        result, catalog_dir, english_by_id=english_by_id
    )
    paths = write_outputs(result, overlay_dir, organized, english_by_id)
    return paths, summary(result, organized, english_by_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="original Shiren GB2 Japanese ROM")
    parser.add_argument(
        "--catalog",
        default="script/organized",
        help="rich ignored catalog directory (default: script/organized)",
    )
    parser.add_argument(
        "--out",
        default="script/en",
        help="source-free overlay directory (default: script/en)",
    )
    args = parser.parse_args(argv)
    try:
        result = extract.extract(Path(args.rom).read_bytes())
        paths, measured = synchronize(result, args.catalog, args.out)
    except (OSError, ValueError, extract.ExtractError, OverlayError) as exc:
        parser.exit(1, "error: %s\n" % exc)

    print(
        "%d records synchronized; %d translated; %d explicit empty"
        % (
            measured["records"],
            measured["translated_records"],
            measured["explicit_empty_records"],
        )
    )
    for category in measured["categories"]:
        print(
            "%-14s %4d / %4d translated  %s"
            % (
                category["name"],
                category["translated_records"],
                category["records"],
                category["filename"],
            )
        )
    print("manifest      %s" % paths[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
