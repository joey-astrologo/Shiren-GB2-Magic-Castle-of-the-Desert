from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import codec
import capture_dialogue
import extract as script_extract


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "script_directory.json").read_text()
)


def _sha1(data):
    return hashlib.sha1(data).hexdigest()


class OriginalRomScriptExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if _sha1(cls.rom) != FIXTURE["rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = script_extract.extract(cls.rom)
        cls.records = {record.id: record for record in cls.result["records"]}

    def test_selector_and_directory_bytes_are_frozen(self):
        selector = FIXTURE["selector"]
        selector_at = script_extract.file_offset(
            selector["bank"], int(selector["address"], 16)
        )
        self.assertEqual(
            selector["sha1"],
            _sha1(self.rom[selector_at:selector_at + selector["span"]]),
        )

        directory = FIXTURE["directory"]
        directory_at = script_extract.file_offset(
            directory["bank"], int(directory["address"], 16)
        )
        size = directory["groups"] * directory["record_size"]
        self.assertEqual(
            directory["sha1"], _sha1(self.rom[directory_at:directory_at + size])
        )

    def test_corpus_summary_and_unmapped_glyph_inventory_are_frozen(self):
        self.assertEqual(FIXTURE["summary"], self.result["summary"])
        self.assertEqual(FIXTURE["unmapped_valid_glyphs"], self.result["unmapped"])
        summary = self.result["summary"]
        classified = (
            summary["referenced_density_candidates"]
            + summary["density_pointer_table_false_positives"]
            + summary["density_source_continuations"]
            + summary["density_prefix_before_reference"]
            + summary["unexplained_density_candidates"]
        )
        self.assertEqual(summary["density_candidates"], classified)
        self.assertEqual(0, summary["unexplained_density_candidates"])

    def test_every_table_is_self_bounding(self):
        for entry in self.result["directory"]:
            with self.subTest(group=entry.group):
                refs = script_extract.read_table(self.rom, entry)
                self.assertTrue(refs)
                first = refs[0].target_address
                self.assertEqual(entry.table_address + len(refs) * 2, first)
                self.assertEqual(list(range(len(refs))), [ref.index for ref in refs])

    def test_duplicate_directory_groups_are_explicit(self):
        groups_by_table = defaultdict(list)
        counts = Counter(ref.group for ref in self.result["references"])
        for entry in self.result["directory"]:
            groups_by_table[(entry.table_bank, entry.table_address)].append(entry.group)
        actual = []
        for (bank, address), groups in groups_by_table.items():
            if len(groups) < 2:
                continue
            actual.append(
                {
                    "groups": groups,
                    "table": script_extract.location(bank, address),
                    "entries": counts[groups[0]],
                }
            )
        self.assertEqual(FIXTURE["duplicate_tables"], actual)

    def test_opening_groups_resolve_to_the_runtime_records(self):
        refs_by_group = defaultdict(list)
        for ref in self.result["references"]:
            refs_by_group[ref.group].append(ref)
        directory = {entry.group: entry for entry in self.result["directory"]}
        for anchor in FIXTURE["opening_groups"]:
            group = anchor["group"]
            with self.subTest(group=group):
                entry = directory[group]
                self.assertEqual(
                    anchor["table"],
                    script_extract.location(entry.table_bank, entry.table_address),
                )
                self.assertEqual(
                    anchor["targets"],
                    [
                        script_extract.location(ref.target_bank, ref.target_address)
                        for ref in refs_by_group[group]
                    ],
                )

        opening = self.records[FIXTURE["anchors"]["captured_opening"]["id"]]
        self.assertTrue(opening.raw.startswith(capture_dialogue.DIALOGUE_PREFIX))

    def test_every_record_is_referenced_and_round_trips(self):
        for record in self.result["records"]:
            with self.subTest(record=record.id):
                self.assertTrue(record.references)
                self.assertEqual(record.raw, codec.encode_source(record.source))
                self.assertEqual(record.raw, codec.serialize(codec.parse_source(record.raw)))

    def test_alias_overlap_and_source_control_anchors(self):
        anchors = FIXTURE["anchors"]
        for name in (
            "dynamic_name", "opening_name", "captured_opening",
            "overlap_parent", "overlap_child",
        ):
            anchor = anchors[name]
            record = self.records[anchor["id"]]
            with self.subTest(anchor=name):
                self.assertEqual(anchor["length"], len(record.raw))
                self.assertEqual(anchor["raw_sha1"], _sha1(record.raw))
                if "source" in anchor:
                    self.assertEqual(anchor["source"], record.source)
                if "interior_of" in anchor:
                    self.assertEqual(anchor["interior_of"], record.interior_of)

        alias = self.records[anchors["physical_alias"]["id"]]
        pointer_locations = [
            script_extract.location(
                ref.table_bank, script_extract.cpu_address(ref.pointer_offset)
            )
            for ref in alias.references
        ]
        self.assertEqual(anchors["physical_alias"]["reference_count"], len(alias.references))
        self.assertEqual(anchors["physical_alias"]["first_pointer"], pointer_locations[0])
        self.assertEqual(anchors["physical_alias"]["last_pointer"], pointer_locations[-1])

        multi = self.records[anchors["multi_group_alias"]["id"]]
        self.assertEqual(
            anchors["multi_group_alias"]["groups"],
            sorted({ref.group for ref in multi.references}),
        )
        self.assertIn(
            script_extract.file_offset(201, 0x51BA),
            self.result["coverage"]["prefix_before_reference"],
        )

    def test_generated_files_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            json_path, tsv_path = script_extract.write_outputs(self.result, temporary)
            self.assertEqual(
                FIXTURE["outputs"]["script_json_sha1"], _sha1(json_path.read_bytes())
            )
            self.assertEqual(
                FIXTURE["outputs"]["script_tsv_sha1"], _sha1(tsv_path.read_bytes())
            )


if __name__ == "__main__":
    unittest.main()
