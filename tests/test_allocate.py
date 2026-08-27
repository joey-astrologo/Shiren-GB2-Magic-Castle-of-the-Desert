from collections import defaultdict
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import allocate
import extract


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "script_allocation.json").read_text(
        encoding="utf-8"
    )
)


def _structural_digests(document):
    directory = "\n".join(
        "%d:%s:%s" % (row["group"], row["source_table"], row["output_table"])
        for row in document["directory"]
    ).encode("ascii")
    tables = "\n".join(
        "%s:%s:%s:%d:%d:%d:%d:%s"
        % (
            row["source"],
            ",".join(map(str, row["groups"])),
            row["output"],
            row["entries"],
            row["unique_records"],
            row["alias_entries"],
            row["size"],
            row["payload_sha1"],
        )
        for row in document["tables"]
    ).encode("ascii")
    records = "\n".join(
        "%s:%s:%d:%s:%s:%s"
        % (
            record["source"],
            record["output"],
            record["raw_size"],
            ",".join(map(str, record["entry_indexes"])),
            record["interior_of"],
            record["interior_mode"],
        )
        for table in document["tables"]
        for record in table["records"]
    ).encode("ascii")
    return {
        "directory_sha256": sha256(directory).hexdigest(),
        "tables_sha256": sha256(tables).hexdigest(),
        "records_sha256": sha256(records).hexdigest(),
    }


class OriginalRomAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != FIXTURE["rom_sha1"]:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.extracted = extract.extract(cls.rom)
        cls.records = {
            (record.bank, record.address): record
            for record in cls.extracted["records"]
        }
        cls.allocation = allocate.allocate(cls.rom)
        cls.document = allocate.manifest(cls.allocation)

    def test_summary_and_bank_plan_are_frozen(self):
        self.assertEqual(FIXTURE["strategy"], allocate.STRATEGY)
        self.assertEqual(FIXTURE["summary"], self.allocation.summary)
        self.assertEqual(FIXTURE["banks"], self.document["banks"])

        reserved = FIXTURE["reserved_banks"]
        self.assertEqual(
            tuple(range(reserved["first"], reserved["last"] + 1)),
            self.allocation.free_banks,
        )
        self.assertEqual(reserved["count"], len(self.allocation.free_banks))
        for bank in self.allocation.free_banks:
            source = self.rom[bank * allocate.BANK_SIZE:(bank + 1) * allocate.BANK_SIZE]
            with self.subTest(bank=bank):
                self.assertEqual({allocate.FILL_BYTE}, set(source))
                self.assertEqual(reserved["blank_bank_sha1"], sha1(source).hexdigest())

    def test_far_tables_and_records_are_bank_safe_and_nonoverlapping(self):
        intervals = defaultdict(list)
        for table in self.allocation.tables:
            self.assertLessEqual(table.output_address + table.pointer_bytes, 0x8000)
            image = self.allocation.bank_images[table.output_bank]
            at = table.output_address - 0x4000
            entries = image[at] | (image[at + 1] << 8)
            self.assertEqual(table.entries, entries)
            intervals[table.output_bank].append(
                (table.output_address, table.output_address + table.pointer_bytes)
            )
            for index in range(table.entries):
                pointer_at = at + 2 + index * 3
                target = image[pointer_at] | (image[pointer_at + 1] << 8)
                target_bank = image[pointer_at + 2]
                self.assertTrue(0x4000 <= target < 0x8000)
                self.assertIn(target_bank, self.allocation.bank_images)

        for record in self.allocation.record_placements.values():
            self.assertLessEqual(record.output_address + record.raw_size + 1, 0x8000)
            intervals[record.output_bank].append(
                (
                    record.output_address,
                    record.output_address + record.raw_size + 1,
                )
            )

        for bank, spans in intervals.items():
            spans.sort()
            for previous, following in zip(spans, spans[1:]):
                with self.subTest(bank=bank, previous=previous, following=following):
                    self.assertLessEqual(previous[1], following[0])

    def test_every_logical_reference_resolves_to_byte_exact_source(self):
        for reference in self.extracted["references"]:
            with self.subTest(group=reference.group, index=reference.index):
                expected = self.records[
                    (reference.target_bank, reference.target_address)
                ].raw
                self.assertEqual(
                    expected,
                    allocate.read_allocated_record(
                        self.allocation, reference.group, reference.index
                    ),
                )

    def test_all_pointer_aliases_remain_aliases(self):
        physical = {}
        for reference in self.extracted["references"]:
            physical.setdefault(reference.pointer_offset, reference)
        by_table = defaultdict(list)
        for reference in physical.values():
            by_table[(reference.table_bank, reference.table_address)].append(reference)

        alias_entries = 0
        alias_tables = 0
        for source_key, references in by_table.items():
            references.sort(key=lambda reference: reference.index)
            table = next(
                table for table in self.allocation.tables if table.source_key == source_key
            )
            image = self.allocation.bank_images[table.output_bank]
            targets = []
            for reference in references:
                at = table.output_address - 0x4000 + 2 + reference.index * 3
                targets.append(
                    (
                        image[at + 2],
                        image[at] | (image[at + 1] << 8),
                    )
                )
            originals = [
                (reference.target_bank, reference.target_address)
                for reference in references
            ]
            self.assertEqual(len(set(originals)), len(set(targets)))
            mapping = defaultdict(set)
            for original, target in zip(originals, targets):
                mapping[original].add(target)
            self.assertTrue(all(len(values) == 1 for values in mapping.values()))
            aliases = len(originals) - len(set(originals))
            alias_entries += aliases
            alias_tables += aliases > 0
        self.assertEqual(FIXTURE["summary"]["alias_pointer_entries"], alias_entries)
        self.assertEqual(FIXTURE["summary"]["tables_with_aliases"], alias_tables)

    def test_duplicate_directory_groups_share_one_rebuilt_table(self):
        actual = []
        for table in self.allocation.tables:
            if len(table.groups) > 1:
                actual.append(
                    {
                        "groups": list(table.groups),
                        "output": extract.location(
                            table.output_bank, table.output_address
                        ),
                    }
                )
                for group in table.groups:
                    self.assertIs(table, self.allocation.group_tables[group])
        self.assertEqual(FIXTURE["duplicate_groups"], actual)

    def test_original_interior_suffix_is_explicitly_materialized(self):
        fixture = FIXTURE["interior"]
        parent_key = (205, 0x7122)
        child_key = (205, 0x7124)
        parent = self.records[parent_key]
        child = self.records[child_key]
        parent_place = self.allocation.record_placements[parent_key]
        child_place = self.allocation.record_placements[child_key]

        self.assertEqual(fixture["source_delta"], child.address - parent.address)
        self.assertEqual(child.raw, parent.raw[fixture["source_delta"]:])
        self.assertEqual(fixture["parent_source"], parent.id)
        self.assertEqual(
            fixture["parent_output"],
            extract.location(parent_place.output_bank, parent_place.output_address),
        )
        self.assertEqual(fixture["child_source"], child.id)
        self.assertEqual(
            fixture["child_output"],
            extract.location(child_place.output_bank, child_place.output_address),
        )
        self.assertEqual(fixture["mode"], child_place.interior_mode)
        self.assertNotEqual(parent_place.output_bank, child_place.output_bank)
        self.assertEqual(parent.id, child_place.interior_of)

    def test_anchor_placements_and_full_manifest_are_frozen(self):
        for anchor in FIXTURE["anchors"]:
            table = self.allocation.group_tables[anchor["group"]]
            with self.subTest(group=anchor["group"]):
                self.assertEqual(
                    anchor["source"], extract.location(*table.source_key)
                )
                self.assertEqual(
                    anchor["output"], extract.location(*table.output_key)
                )
                self.assertEqual(anchor["entries"], table.entries)
                self.assertEqual(anchor["records"], table.unique_records)
                self.assertEqual(anchor["aliases"], table.alias_entries)
                self.assertEqual(anchor["size"], table.size)

        expected_digests = dict(FIXTURE["digests"])
        manifest_data = allocate.manifest_bytes(self.allocation)
        self.assertEqual(expected_digests.pop("manifest_bytes"), len(manifest_data))
        self.assertEqual(expected_digests.pop("manifest_sha1"), sha1(manifest_data).hexdigest())
        self.assertEqual(expected_digests, _structural_digests(self.document))

    def test_too_few_destination_banks_fail_cleanly(self):
        with self.assertRaisesRegex(allocate.AllocationError, "exhausted 12 destination"):
            allocate.allocate(self.rom, allocate.FREE_BANKS[:12])

    def test_one_logical_table_can_store_records_across_multiple_banks(self):
        group_six = self.allocation.group_tables[6]
        overrides = {
            (record.source_bank, record.source_address): b"\x0A" * 100
            for record in group_six.records
        }
        allocation = allocate.allocate(self.rom, record_overrides=overrides)
        table = allocation.group_tables[6]
        record_banks = {record.output_bank for record in table.records}
        self.assertGreater(table.pointer_bytes + table.text_bytes, allocate.BANK_SIZE)
        self.assertGreater(len(record_banks), 1)
        for index in (0, len(table.records) // 2, len(table.records) - 1):
            self.assertEqual(
                b"\x0A" * 100,
                allocate.read_allocated_record(allocation, 6, index),
            )


if __name__ == "__main__":
    unittest.main()
