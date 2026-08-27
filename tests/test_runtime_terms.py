from hashlib import sha1
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import extract
import runtime_terms


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "runtime_terms.json"


class RuntimeTermInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_complete_inventory_is_frozen(self):
        self.assertEqual(self.fixture, runtime_terms.inventory(self.rom))

    def test_cache_is_generic_and_all_immediate_callers_are_frozen(self):
        cache = self.fixture["cache"]
        self.assertEqual(34, len(cache["call_graph"]["append"]["far"]))
        self.assertEqual(5, len(cache["call_graph"]["read"]["far"]))
        purposes = {anchor["purpose"] for anchor in self.fixture["opcode_anchors"]}
        self.assertIn("select a group-24 directory record and cache it", purposes)
        self.assertIn("format decimal text and cache it", purposes)
        self.assertIn(
            "cache a sender string, compose an item name, then cache it", purposes
        )

    def test_every_cache_writer_has_one_proven_construction_class(self):
        classes = {
            row["name"]: row for row in self.fixture["cache"]["producer_classes"]
        }
        self.assertEqual(
            {
                "item_name": 29,
                "location_record": 1,
                "unsigned_integer": 1,
                "sender_string": 1,
                "polymorphic_value": 1,
                "encoded_communication_string": 1,
            },
            {name: row["count"] for name, row in classes.items()},
        )
        sites = [site for row in classes.values() for site in row["sites"]]
        self.assertEqual(34, len(sites))
        self.assertEqual(34, len(set(sites)))
        self.assertIn("122:$4460", classes["item_name"]["sites"])
        self.assertEqual(
            ["location_names_primary", "location_names_history"],
            classes["location_record"]["value_domain"],
        )

    def test_mixed_message_consumes_two_cached_strings(self):
        evidence = self.fixture["mixed_cache_evidence"]
        self.assertEqual("192:$6DCF", evidence["record"])
        self.assertEqual(
            ["<number:19:C5>", "<number:1A:C5>"],
            [token["source"] for token in evidence["cached_string_tokens"]],
        )

    def test_every_cached_string_consumer_has_a_semantic_domain(self):
        domains = {
            row["name"]: row for row in self.fixture["cached_string_consumers"]
        }
        self.assertEqual(
            {
                "item_name": 104,
                "sender_string": 1,
                "location_record": 1,
                "debug_polymorphic": 2,
            },
            {name: row["occurrences"] for name, row in domains.items()},
        )
        self.assertEqual(108, sum(row["occurrences"] for row in domains.values()))
        self.assertEqual(
            {"$C519": 95, "$C51A": 6, "$C51B": 3},
            domains["item_name"]["field_occurrences"],
        )
        self.assertEqual(
            ["location_names_primary", "location_names_history"],
            domains["location_record"]["value_domain"],
        )

    def test_every_record_lookup_consumer_has_a_semantic_domain(self):
        domains = {
            row["name"]: row for row in self.fixture["record_lookup_consumers"]
        }
        self.assertEqual(
            {
                "actor_name": 127,
                "trap_name": 8,
                "identified_item_name": 1,
                "location_name": 1,
                "debug_polymorphic": 2,
            },
            {name: row["occurrences"] for name, row in domains.items()},
        )
        self.assertEqual(139, sum(row["occurrences"] for row in domains.values()))
        self.assertEqual(
            {"8": 112, "11": 9, "16": 1, "18": 3, "24": 2},
            domains["actor_name"]["reference_group_occurrences"],
        )
        self.assertEqual(
            {"8": 1, "11": 7},
            domains["trap_name"]["reference_group_occurrences"],
        )
        self.assertEqual(
            [
                "actor_name_tier_1",
                "actor_name_tier_2",
                "actor_name_tier_3",
                "player_name",
            ],
            domains["actor_name"]["value_domain"],
        )
        self.assertEqual(
            ["identified_item_names"],
            domains["identified_item_name"]["value_domain"],
        )
        self.assertEqual(
            ["location_names_primary", "location_names_history"],
            domains["location_name"]["value_domain"],
        )

    def test_term_families_cover_expected_logical_entries(self):
        families = {row["name"]: row for row in self.fixture["term_families"]}
        self.assertEqual(150, families["actor_name_tier_1"]["entries"])
        self.assertEqual(216, families["identified_item_names"]["entries"])
        self.assertEqual(123, families["unidentified_item_appearances"]["entries"])
        self.assertEqual(20, families["item_name_format_fragments"]["entries"])
        self.assertEqual(22, families["trap_names"]["entries"])
        self.assertEqual(14, families["location_names_primary"]["entries"])
        self.assertEqual(30, families["location_names_history"]["entries"])


if __name__ == "__main__":
    unittest.main()
