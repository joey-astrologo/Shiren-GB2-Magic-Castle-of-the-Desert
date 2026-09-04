from hashlib import sha1
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import build as translated_build
import codec
import english
import english_font
import extract
import layout
import runtime_widths
import surfaces
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "positioned_surfaces.json").read_text(
        encoding="utf-8"
    )
)


def _json_value(value):
    """Normalize immutable tuples to the fixture's JSON list representation."""
    return json.loads(json.dumps(value, ensure_ascii=False))


class OriginalRomPositionedSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")

    def test_copy_selector_and_complete_direct_call_graph_are_frozen(self):
        selector = FIXTURE["selector"]
        start = surfaces.DIRECT_SELECTOR[1]
        self.assertEqual(selector["entry"], "0:$%04X" % start)
        self.assertEqual(selector["span"], surfaces.SELECTOR_COPY_SPAN)
        self.assertEqual(
            selector["sha1"],
            sha1(self.rom[start:start + selector["span"]]).hexdigest(),
        )
        self.assertEqual(
            FIXTURE["call_graph"], _json_value(surfaces.call_graph(self.rom))
        )
        draw_record_far = FIXTURE["call_graph"]["wrappers"]["draw_record"]["far"]
        self.assertIn("4:$72E9", draw_record_far)
        self.assertNotIn("18:$76B0", draw_record_far)
        self.assertNotIn("18:$79A4", draw_record_far)

    def test_every_positioned_text_call_site_has_exactly_one_owner(self):
        measured = surfaces.call_graph_coverage(self.rom)
        self.assertEqual(FIXTURE["call_graph_coverage"], measured)
        self.assertTrue(measured["complete"])
        self.assertEqual(9, measured["api_count"])
        self.assertEqual(120, measured["discovered_count"])
        self.assertEqual(
            measured["discovered_count"], measured["assigned_count"]
        )
        for api, row in measured["apis"].items():
            with self.subTest(api=api):
                self.assertTrue(row["complete"])
                self.assertEqual([], row["unassigned"])
                self.assertEqual([], row["duplicates"])
                self.assertEqual([], row["stale"])
                self.assertEqual(row["discovered_count"], row["assigned_count"])

    def test_observed_opening_menu_contracts_resolve_and_fit(self):
        measured = surfaces.opening_menu_summary(self.rom)
        self.assertEqual(FIXTURE["observed_surfaces"], measured)
        for item in measured:
            with self.subTest(surface=item["name"]):
                self.assertEqual(
                    item["available_pixels"], item["right_edge"] - item["start_pen"][0]
                )
                self.assertLessEqual(item["final_pen"][0], item["right_edge"])
                self.assertEqual(item["start_pen"][1], item["final_pen"][1])

    def test_clean_boot_guide_contracts_resolve_and_fit(self):
        measured = surfaces.guide_menu_summary(self.rom)
        self.assertEqual(FIXTURE["guide_surfaces"], measured)
        self.assertEqual(11, len(measured))
        self.assertEqual(
            list(range(10)),
            [item["reference"][1] for item in measured[1:]],
        )
        for item in measured:
            with self.subTest(surface=item["name"]):
                self.assertEqual(
                    item["available_pixels"], item["right_edge"] - item["start_pen"][0]
                )
                self.assertLessEqual(item["final_pen"][0], item["right_edge"])
                self.assertEqual(item["start_pen"][1], item["final_pen"][1])

    def test_ingame_help_contracts_resolve_and_fit(self):
        summaries = (
            ("control_help_surfaces", surfaces.control_help_summary(self.rom), 20, 9),
            (
                "technique_help_surfaces",
                surfaces.technique_help_summary(self.rom),
                21,
                10,
            ),
        )
        for fixture_key, measured, group, topic_count in summaries:
            with self.subTest(family=fixture_key):
                self.assertEqual(FIXTURE[fixture_key], measured)
                self.assertEqual(topic_count + 1, len(measured))
                self.assertEqual(
                    list(range(topic_count)),
                    [item["reference"][1] for item in measured[1:]],
                )
                self.assertEqual({group}, {item["reference"][0] for item in measured[1:]})
                for item in measured:
                    self.assertEqual(
                        item["available_pixels"],
                        item["right_edge"] - item["start_pen"][0],
                    )
                    self.assertLessEqual(item["final_pen"][0], item["right_edge"])

    def test_dynamic_help_list_families_are_complete(self):
        measured = surfaces.dynamic_list_family_summary(self.rom)
        self.assertEqual(FIXTURE["dynamic_list_families"], measured)
        families = {item["name"]: item for item in measured}
        self.assertEqual(
            {
                "wanderers_guide_topics": 10,
                "control_help_topics": 9,
                "technique_help_topics": 16,
            },
            {name: item["entries"] for name, item in families.items()},
        )
        for item in measured:
            with self.subTest(family=item["name"]):
                self.assertEqual(10, item["page_rows"])
                self.assertEqual(141, item["physical_budget"])
                self.assertLessEqual(item["widest"]["renderer_pixels"], 141)

    def test_main_menu_domains_and_right_aligned_locations_are_frozen(self):
        self.assertEqual(
            FIXTURE["main_menu_surfaces"], surfaces.main_menu_summary(self.rom)
        )
        measured = surfaces.main_menu_contract_summary(self.rom)
        self.assertEqual(FIXTURE["main_menu_contract"], measured)
        self.assertEqual(
            [[7, 35], [7, 63]],
            [row["reference"] for row in measured["left_slots"][0]["records"]],
        )
        self.assertEqual(
            [[7, 36], [7, 39], [7, 56], [7, 64]],
            [row["reference"] for row in measured["left_slots"][1]["records"]],
        )
        for slot in measured["left_slots"]:
            with self.subTest(slot=slot["name"]):
                self.assertEqual(50, slot["visual_budget"])
                self.assertLessEqual(
                    slot["widest"]["renderer_pixels"], slot["visual_budget"]
                )

        panel = measured["location_panel"]
        self.assertEqual(30, panel["entries"])
        self.assertEqual([19, 48], panel["index_range"])
        self.assertEqual(83, panel["alignment_budget"])
        self.assertLessEqual(
            panel["widest_alignment"]["alignment_width"],
            panel["alignment_budget"],
        )
        self.assertEqual([24, 47], panel["observed"]["reference"])
        self.assertEqual(77, panel["observed"]["start_x"])

    def test_main_menu_numeric_status_domains_and_english_fit_are_frozen(self):
        measured = surfaces.main_menu_numeric_summary(self.rom)
        self.assertEqual(FIXTURE["main_menu_numeric_status"], measured)
        self.assertEqual(8, len(measured["fields"]))
        self.assertEqual(
            {
                "weapon_total": 255,
                "shield_total": 255,
                "strength_max": 255,
                "strength_current": 255,
                "fullness_current": 200,
                "fullness_max": 200,
                "money": 999999,
                "experience": 16777215,
            },
            {field["name"]: field["maximum"] for field in measured["fields"]},
        )
        for field in measured["fields"]:
            with self.subTest(field=field["name"]):
                self.assertEqual(4, field["input_bytes"])
                self.assertGreaterEqual(
                    field["original_maximum"]["clearance_pixels"], 0
                )
                self.assertGreaterEqual(
                    field["english_maximum"]["clearance_pixels"], 0
                )
                self.assertLessEqual(
                    field["english_maximum"]["alignment_width"],
                    field["original_maximum"]["alignment_width"],
                )
        self.assertEqual(
            99, measured["experience_thresholds"]["entries_before_sentinel"]
        )
        self.assertEqual(
            "$FFFFFF", measured["experience_thresholds"]["sentinel"]
        )
        self.assertEqual(
            [11, 5], measured["visible_tilemap"]["right_panel"]["size_tiles"]
        )
        self.assertEqual(
            [18, 5], measured["visible_tilemap"]["bottom_panel"]["size_tiles"]
        )

    def test_help_popup_canvas_strips_and_tilemap_remap_are_frozen(self):
        measured = surfaces.help_popup_summary(self.rom)
        self.assertEqual(FIXTURE["help_popup_surfaces"], measured)
        self.assertEqual(
            [[7, 113], [7, 114], [7, 115], [7, 53]],
            [item["reference"] for item in measured],
        )
        for item in measured:
            with self.subTest(surface=item["name"]):
                self.assertEqual(40, item["available_pixels"])
                self.assertLessEqual(item["renderer_pixels"], 40)

        remap = surfaces.help_popup_remap_summary(self.rom)
        self.assertEqual(FIXTURE["help_popup_remap"], remap)
        self.assertEqual(90, remap["canvas"]["tiles_copied"])
        self.assertEqual([8, 8], remap["visible_tilemap"]["size_tiles"])
        for strip in remap["strips"]:
            with self.subTest(strip=strip["name"]):
                self.assertEqual(40, strip["text_budget"])
                self.assertEqual(6, len(strip["tile_ids"][0]))
                self.assertEqual(3, len(strip["tile_ids"]))

        patched = english_font.install(self.rom)
        fitting = layout.validate_direct_surface(
            patched,
            english.encode("W" * 6),
            start_x=16,
            start_y=1,
            right_edge=56,
        )
        self.assertEqual(52, fitting.final_x)
        with self.assertRaisesRegex(layout.LayoutError, "beyond visual edge"):
            layout.validate_direct_surface(
                patched,
                english.encode("W" * 7),
                start_x=16,
                start_y=1,
                right_edge=56,
            )

    def test_status_condition_domain_and_full_screen_remap_are_frozen(self):
        measured = surfaces.status_condition_summary(self.rom)
        self.assertEqual(FIXTURE["status_condition_screen"], measured)
        self.assertEqual(
            [[7, 25], [7, 84]],
            [item["reference"] for item in measured["observed_surfaces"]],
        )

        selection = measured["selection"]
        self.assertEqual(48, selection["display_entries"])
        self.assertEqual(55, selection["mapped_effects"])
        self.assertEqual([22, 26, 54, 55], selection["unmapped_effect_ids"])
        self.assertEqual(10, selection["page_rows"])
        self.assertEqual(143, selection["visual_budget"])
        self.assertLessEqual(
            selection["widest"]["renderer_pixels"], selection["visual_budget"]
        )
        self.assertEqual(
            48, len({row["label_index"] for row in selection["records"]})
        )
        self.assertEqual(
            [
                effect_id
                for effect_id in range(59)
                if effect_id not in selection["unmapped_effect_ids"]
            ],
            sorted(
                effect_id
                for row in selection["records"]
                for effect_id in row["effect_ids"]
            ),
        )
        self.assertEqual(
            [20, 18], measured["visible_tilemap"]["size_tiles"]
        )

    def test_training_and_travel_dungeon_selector_domains_are_frozen(self):
        measured = surfaces.dungeon_selector_summary(self.rom)
        self.assertEqual(FIXTURE["dungeon_selectors"], measured)
        self.assertEqual(
            [0, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            measured["complete_union"]["indices"],
        )
        self.assertEqual(10, measured["complete_union"]["entries"])
        self.assertEqual(141, measured["shared"]["visual_budget"])
        self.assertEqual([20, 18], measured["shared"]["screen"]["size_tiles"])

        training = measured["variants"]["training"]
        travel = measured["variants"]["travel"]
        self.assertEqual([7, 131], training["heading_reference"])
        self.assertEqual([0], training["fixed_indices"])
        self.assertEqual(list(range(3, 12)), training["conditional_indices"])
        self.assertEqual(10, training["maximum_rows"])
        self.assertEqual(
            [[7, 131], [24, 0]],
            [item["reference"] for item in training["observed_surfaces"]],
        )

        self.assertEqual([7, 132], travel["heading_reference"])
        self.assertEqual([3, 4, 5, 6], travel["fixed_indices"])
        self.assertEqual([7], travel["conditional_indices"])
        self.assertEqual(5, travel["maximum_rows"])
        self.assertEqual(
            [[7, 132], [24, 3], [24, 4], [24, 5], [24, 6]],
            [item["reference"] for item in travel["observed_surfaces"]],
        )
        for variant in (training, travel):
            self.assertEqual(67, variant["widest"]["renderer_pixels"])
            for record in variant["records"]:
                self.assertLessEqual(
                    record["renderer_pixels"],
                    measured["shared"]["visual_budget"],
                )

        self.assertEqual(
            "4:$4687",
            measured["evidence"]["entry_and_header_branch"]["location"],
        )
        self.assertEqual(
            "3:$5FDB",
            measured["evidence"]["body_and_finite_domains"]["location"],
        )

    def test_adventure_history_and_wanderer_ranking_contracts_are_frozen(self):
        measured = surfaces.history_ranking_summary(self.rom)
        self.assertEqual(FIXTURE["history_and_ranking"], measured)

        history = measured["adventure_history"]
        self.assertEqual(40, history["entries"])
        self.assertEqual([0, 39], history["index_range"])
        self.assertEqual(10, history["page_rows"])
        self.assertEqual(40, history["flag_storage"]["bits"])
        self.assertEqual(list(range(10)), history["seeded_first_page"]["enabled_indices"])
        self.assertEqual(6, history["widest_bounded_stock_row"]["index"])
        self.assertEqual(
            144,
            history["widest_bounded_stock_row"][
                "renderer_pixels_with_bounded_runtime_maxima"
            ],
        )
        self.assertEqual(
            [22],
            [
                row["index"]
                for row in history["records"]
                if row["unresolved_dynamic_offsets"]
            ],
        )

        ranking = measured["wanderer_ranking"]
        self.assertEqual(50, ranking["maximum_records"])
        self.assertEqual(5, ranking["paged_rows"])
        self.assertEqual(0x20, ranking["record_schema"]["size"])
        self.assertEqual(18, len(ranking["record_schema"]["fields"]))
        self.assertEqual(0x85, ranking["extended_schema"]["size"])
        self.assertEqual(
            0x85,
            ranking["extended_schema"]["memo"]["size"]
            + ranking["extended_schema"]["final_message"]["size"],
        )
        self.assertEqual(28, len(ranking["domains"]["locations"]))
        self.assertEqual(41, len(ranking["domains"]["outcomes"]))
        self.assertEqual(
            {"wanderer": 11, "trap": 11, "cooking": 11},
            {
                name: len(records)
                for name, records in ranking["domains"]["titles"].items()
            },
        )
        self.assertEqual(
            {
                "rank": 50,
                "score": 0xFFFFFFFF,
                "floor": 0xFF,
                "level": 0xFF,
                "rescues": 0xFFFF,
                "maximum_hp": 0xFF,
                "maximum_strength": 0xFF,
                "turn_count": 0xFFFFFF,
            },
            {
                field["name"]: field["maximum"]
                for field in ranking["numeric_fields"]
            },
        )
        self.assertEqual(
            {
                "current_record_list": "3:$612D",
                "paged_record_list": "3:$632D",
                "record_detail": "3:$65CA",
                "final_message": "3:$663C",
            },
            {
                name: screen["body"]
                for name, screen in ranking["screens"].items()
            },
        )
        self.assertEqual(
            "11:$5655", measured["evidence"]["record_getters"]["location"]
        )
        self.assertEqual(
            "11:$59A8",
            measured["evidence"]["extended_record_getters"]["location"],
        )

    def test_production_ranking_max_strength_label_fits_before_value(self):
        result = extract.extract(self.rom)
        translated = translations.load_path(
            ROOT / "script" / "en", result["records"]
        )
        record = next(
            record for record in result["records"] if record.id == "194:$4FE0"
        )
        entry = translated[(record.bank, record.address)]
        self.assertEqual("Max Str", entry.text)

        measured = layout.validate_direct_surface(
            english_font.install(self.rom),
            entry.encoded,
            start_x=93,
            start_y=45,
            right_edge=130,
        )
        self.assertLessEqual(measured.final_x, 130)

    def test_production_ranking_score_and_floor_suffixes_are_unambiguous(self):
        result = extract.extract(self.rom)
        translated = translations.load_path(
            ROOT / "script" / "en", result["records"]
        )
        by_reference = {
            (reference.group, reference.index): record
            for record in result["records"]
            for reference in record.references
        }
        score_suffix = by_reference[(7, 62)]
        floor_suffix = by_reference[(7, 50)]

        # These are independent fixed draws after the numeric score and floor.
        # Freezing them separately prevents a long literal label from visually
        # merging with either neighboring value as "11250Fan".
        self.assertEqual(
            "G",
            translated[(score_suffix.bank, score_suffix.address)].text,
        )
        self.assertEqual(
            "F",
            translated[(floor_suffix.bank, floor_suffix.address)].text,
        )

        # Freeze the actual native-pixel pen geometry for the user's example.
        # The amount and suffix are separate draws, as are the floor and F.
        font_rom = english_font.install(self.rom)
        draws = (
            (codec.encode_source("11250"), 48, 90, 73),
            (
                translated[(score_suffix.bank, score_suffix.address)].encoded,
                90,
                125,
                96,
            ),
            (codec.encode_source("9"), 125, 137, 130),
            (
                translated[(floor_suffix.bank, floor_suffix.address)].encoded,
                137,
                layout.CANVAS_WIDTH_PIXELS,
                143,
            ),
        )
        for raw, start_x, right_edge, expected_final_x in draws:
            measured = layout.validate_direct_surface(
                font_rom,
                raw,
                start_x=start_x,
                start_y=1,
                right_edge=right_edge,
            )
            self.assertEqual(expected_final_x, measured.final_x)

    def test_record_pickers_and_graphical_input_contracts_are_frozen(self):
        measured = surfaces.record_picker_and_graphical_input_summary(self.rom)
        self.assertEqual(FIXTURE["record_picker_and_graphical_input"], measured)

        ranking = measured["ranking_record_picker"]
        grade = measured["grade_category_picker"]
        self.assertEqual(5, ranking["rows"])
        self.assertEqual(4, grade["rows"])
        self.assertEqual("11:$55FE", ranking["count_provider"]["entry"])
        self.assertEqual("C", ranking["count_provider"]["result_register"])
        self.assertEqual("11:$4EB9", grade["count_provider"]["entry"])
        self.assertEqual("D", grade["count_provider"]["result_register"])
        self.assertEqual(
            list(surfaces.INPUT_INDEX_NAMES),
            [item["input"] for item in ranking["dispatch"]],
        )
        self.assertEqual(
            ["16:$5A1B", "16:$5A1B", "16:$5A27", "16:$5A20"],
            [ranking["dispatch"][index]["target"] for index in (1, 2, 7, 8)],
        )
        self.assertEqual(
            ["16:$5A75", "16:$5A75", "16:$5A81", "16:$5A7A"],
            [grade["dispatch"][index]["target"] for index in (1, 2, 7, 8)],
        )

        editor = measured["graphical_input_mode_3"]
        self.assertEqual(3, editor["mode"])
        self.assertEqual(4, editor["buffer"]["bytes"])
        self.assertEqual(49, editor["cells"]["characters"])
        self.assertEqual(
            {"diacritic": 0x31, "backspace": 0x32, "confirm": 0x33},
            editor["cells"]["special"],
        )
        self.assertEqual("あ", editor["cells"]["characters_decoded"][0])
        self.assertEqual("ん", editor["cells"]["characters_decoded"][47])
        self.assertEqual("<D0>", editor["cells"]["characters_decoded"][48])
        graph = editor["cells"]["navigation_graph"]
        self.assertEqual(52, len(graph))
        self.assertEqual(
            {"down": 5, "up": 50, "left": 29, "right": 1},
            graph[0]["neighbors"],
        )
        self.assertEqual([0x31, 0x32, 0x33], [node["node"] for node in graph[-3:]])
        self.assertEqual([20, 16], editor["graphics"]["source_size_tiles"])
        self.assertEqual([20, 18], editor["graphics"]["visible_size_tiles"])
        self.assertEqual("$E7", editor["graphics"]["lcdc"])
        self.assertEqual(
            ["16:$5BF1"] * 4 + ["16:$5C12", "16:$5C26", "16:$5BF6", "16:$5C34"],
            [item["target"] for item in editor["dispatch"][1:]],
        )

    def test_diary_management_hub_and_mode_4_editor_are_frozen(self):
        measured = surfaces.diary_management_summary(self.rom)
        self.assertEqual(FIXTURE["diary_management"], measured)

        labels = measured["hub"]["labels"]
        self.assertEqual(10, len(labels))
        self.assertEqual(
            [[7, index] for index in range(67, 77)],
            [item["reference"] for item in labels],
        )
        self.assertEqual(
            [
                "16:$7714",
                "16:$7847",
                "16:$7893",
                "16:$786B",
                "16:$78C7",
                "16:$78E2",
                "16:$7957",
                "16:$797C",
                "16:$79E1",
                "16:$7A06",
            ],
            [item["handler"] for item in labels],
        )
        self.assertEqual("create_diary", labels[1]["name"])
        self.assertEqual("delete_diary", labels[3]["name"])
        self.assertEqual("rename", labels[4]["name"])
        for label in labels:
            self.assertLessEqual(
                label["all_enabled_final_pen"][0], label["right_edge"]
            )

        deletion = measured["delete_diary"]
        self.assertEqual("no", deletion["prompt"]["default_choice"])
        self.assertEqual([108, 60, 129], deletion["prompt"]["line_widths"])
        self.assertEqual(0, deletion["prompt"]["automatic_wraps"])
        self.assertEqual("$FB", deletion["outcomes"]["no"]["handler_result"])
        self.assertEqual("$EE", deletion["outcomes"]["yes"]["handler_result"])

        editor = measured["mode_4_name_editor"]
        self.assertEqual(4, editor["mode"])
        self.assertEqual(4, editor["buffer"]["bytes"])
        self.assertEqual(73, editor["cells"]["characters"])
        self.assertEqual(
            {
                "diacritic_plain": 0x49,
                "diacritic_voiced": 0x4A,
                "kana_page": 0x4B,
                "conversion": 0x4C,
                "confirm": 0x4D,
                "buffer_right": 0x4E,
                "buffer_left": 0x4F,
                "backspace": 0x50,
            },
            editor["cells"]["special"],
        )
        graph = editor["cells"]["navigation_graph"]
        self.assertEqual(81, len(graph))
        self.assertEqual(
            {"down": 5, "up": 78, "left": 54, "right": 1},
            graph[0]["neighbors"],
        )
        self.assertEqual([20, 18], editor["graphics"]["visible_size_tiles"])
        self.assertEqual("$E7", editor["graphics"]["lcdc"])
        self.assertEqual(
            ["16:$5AF5"] * 4
            + ["16:$5B30", "16:$5B50", "16:$5B0F", "16:$5B5E"],
            [item["target"] for item in editor["dispatch"][1:]],
        )

    def test_diary_storage_has_one_native_save_slot(self):
        # The persistent write has no diary index or slot-stride calculation:
        # it selects SRAM bank 1 and copies the sole 0x6A-byte structure from
        # $C23C directly to $A000. New Game and Adventure are therefore
        # intentionally mutually exclusive, rather than two file slots.
        save_at = extract.file_offset(11, 0x45F1)
        self.assertEqual(
            bytes.fromhex(
                "1100A03E01EA00413E0AEA0001213CC2016A00"
                "CD620AAFEA0001C9"
            ),
            self.rom[save_at:save_at + 0x1B],
        )

        predicates_at = extract.file_offset(11, 0x5079)
        self.assertEqual(
            bytes.fromhex("CD4C4A7AA7180ACD4C4A7AA720080E00C928030E00C90E01C9"),
            self.rom[predicates_at:predicates_at + 0x19],
        )

    def test_remaining_front_end_hub_routes_are_frozen(self):
        measured = surfaces.remaining_hub_routes_summary(self.rom)
        # The complete 219-record Notebook text membership is frozen by the
        # dedicated menu-text fixture.  Keep this route fixture focused on the
        # engine graph instead of duplicating hundreds of text contracts.
        expected_contract = deepcopy(FIXTURE["remaining_hub_routes"])
        measured_contract = deepcopy(measured)
        expected_contract["monster_notebook"]["text_domains"].pop("descriptions")
        measured_contract["monster_notebook"]["text_domains"].pop("descriptions")
        self.assertEqual(expected_contract, measured_contract)

        exchange = measured["item_exchange"]
        self.assertEqual(2, exchange["slot"])
        self.assertEqual(
            [[7, 80], [7, 81]],
            [row["reference"] for row in exchange["menu"]["choices"]],
        )
        self.assertEqual(
            [[7, index] for index in range(94, 109)],
            [
                row["reference"]
                for row in exchange["protocol_text"]["records"]
            ],
        )
        self.assertEqual(100, exchange["storage"]["slots"])

        secrets = measured["wanderers_secrets"]
        self.assertEqual(10, len(secrets["rows"]))
        self.assertEqual(
            list(range(4, 14)),
            [row["event_id"] for row in secrets["rows"]],
        )
        self.assertEqual(
            "194:$40DC",
            secrets["related_prose"]["records"][0]["record"],
        )
        self.assertEqual(
            secrets["related_prose"]["records"][0]["record"],
            secrets["related_prose"]["records"][1]["record"],
        )

        grade = measured["wanderer_grade"]
        self.assertEqual(
            [[22, index] for index in range(30, 34)],
            [row["reference"] for row in grade["picker"]["rows"]],
        )
        self.assertEqual(
            [[22, index] for index in range(34, 38)],
            [row["reference"] for row in grade["detail"]["headers"]],
        )
        self.assertEqual(
            [(10, 11), (10, 11), (10, 11)],
            [
                (len(domain["achievements"]), len(domain["titles"]))
                for domain in grade["detail"]["achievement_domains"]
            ],
        )
        self.assertEqual(
            [[22, 71], [22, 72], [22, 73]],
            [
                row["reference"]
                for row in grade["detail"]["rescue_category"]["records"]
            ],
        )

        notebook = measured["monster_notebook"]
        self.assertEqual(209, notebook["catalog"]["variants"])
        self.assertEqual(27, notebook["catalog"]["page_size"])
        self.assertEqual(8, notebook["catalog"]["pages"])
        self.assertEqual(7, notebook["catalog"]["maximum_page_index"])
        self.assertEqual(
            [24, 15], notebook["text_domains"]["page_counter"]["reference"]
        )
        descriptions = notebook["text_domains"]["descriptions"]
        self.assertEqual(219, len(descriptions["records"]))
        self.assertEqual(
            [[[29, 0], [29, 72]], [[30, 0], [30, 72]], [[31, 0], [31, 72]]],
            descriptions["tier_reference_ranges"],
        )

    def test_adventure_start_menu_slots_compaction_and_edges_are_frozen(self):
        measured = surfaces.adventure_start_menu_summary(self.rom)
        self.assertEqual(FIXTURE["adventure_start_menu"], measured)

        self.assertEqual(24, measured["group"])
        self.assertEqual([50, 58], measured["index_range"])
        self.assertEqual(
            list(range(9)), [row["slot"] for row in measured["slots"]]
        )
        self.assertEqual(
            [[24, index] for index in range(50, 59)],
            [row["reference"] for row in measured["slots"]],
        )
        self.assertEqual(88, measured["geometry"]["available_pixels"])
        for row in measured["slots"]:
            self.assertLessEqual(
                row["renderer_pixels"], row["available_pixels"]
            )

        maximum = measured["variants"]["maximum_predicate_consistent"]
        self.assertEqual(list(range(1, 9)), maximum["enabled_slots"])
        self.assertEqual(7, maximum["maximum_index"])
        self.assertEqual(
            [[56, 3 + row * 11] for row in range(8)],
            [item["start_pen"] for item in maximum["rows"]],
        )

        sparse = measured["variants"]["sparse_compaction_probe"]
        self.assertEqual([0, 3, 8], sparse["enabled_slots"])
        self.assertEqual(
            [0, 3, 8],
            [item["slot"] for item in sparse["compacted_ordinal_to_slot"]],
        )
        self.assertEqual(
            [[56, 3], [56, 14], [56, 25]],
            [item["start_pen"] for item in sparse["rows"]],
        )

    def test_at_feet_empty_trap_item_and_value_contracts_are_frozen(self):
        measured = surfaces.at_feet_summary(self.rom)
        self.assertEqual(FIXTURE["at_feet"], measured)

        shell = measured["common_shell"]
        self.assertEqual([7, 36], shell["heading"]["reference"])
        self.assertEqual([8, 4], shell["heading"]["start_pen"])
        self.assertEqual(
            [7, 49], shell["current_money"]["suffix"]["reference"]
        )
        self.assertEqual(
            [129, 4], shell["current_money"]["number"]["start_pen"]
        )
        self.assertEqual(
            "FEFEFEFE00", shell["current_money"]["number"]["raw"]
        )

        body = measured["body"]
        self.assertEqual([], body["empty"]["positioned_records"])
        traps = body["trap"]["records"]
        self.assertEqual(22, len(traps))
        self.assertEqual(
            [[17, index] for index in range(1, 23)],
            [row["reference"] for row in traps],
        )
        self.assertEqual([[3, 1]] * 22, [row["start_pen"] for row in traps])
        self.assertEqual(
            [1, 22],
            [
                row["trap_name_index"]
                for row in traps
                if row["live_endpoint_probe"]
            ],
        )
        self.assertEqual(
            [17, 0],
            body["trap"]["related_non_positioned_record"]["reference"],
        )

        item = body["item"]
        self.assertEqual("17:$5484", item["renderer"])
        self.assertEqual("120:$47C2", item["shared_formatter"])
        self.assertEqual([3, 1], item["nominal_start_pen"])
        self.assertEqual([7, 1], item["leading_fe_start_pen"])
        self.assertEqual(
            ["weapon", "money"],
            [row["category"] for row in item["live_representatives"]],
        )
        self.assertEqual(
            [[4, 1], [4, 200]],
            [row["base_reference"] for row in item["live_representatives"]],
        )
        metadata = item["metadata_value_branch"]
        self.assertEqual("0101000001000000", metadata["seed_object_bytes"])
        self.assertEqual(
            [[129, 1], [28, 32]],
            [row["start_pen"] for row in metadata["runtime_fields"]],
        )
        self.assertEqual([48, 32], metadata["value_suffix"]["start_pen"])
        self.assertEqual([7, 49], metadata["value_suffix"]["reference"])

    def test_seeded_item_list_record_geometry_and_remap_are_frozen(self):
        measured = surfaces.seeded_item_list_summary(self.rom)
        self.assertEqual(FIXTURE["seeded_item_list"], measured)
        self.assertEqual(20, measured["seed"]["inventory"]["slots"])
        self.assertEqual("$D2C1", measured["seed"]["inventory"]["address"])
        self.assertEqual(
            [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 255],
            measured["seed"]["inventory"]["first_bytes"],
        )
        self.assertEqual("$D482", measured["seed"]["object_pool"]["address"])
        self.assertEqual(
            [[7, 54], [7, 49]],
            [
                item["reference"]
                for item in measured["observed_surfaces"]
            ],
        )
        matrix = measured["category_matrix"]
        self.assertEqual(10, matrix["seeded_families"])
        self.assertEqual(
            [
                0, 1, 34, 63, 90, 97, 104, 124, 158, 184, 200, 201, 202,
                203, 204, 207, 208,
            ],
            [item["start"] for item in matrix["boundary_table"]["entries"]],
        )
        self.assertEqual(
            list(range(1, 11)),
            [row["category_index"] for row in matrix["rows"]],
        )
        self.assertEqual(
            list(range(1, 11)),
            [row["action_class"] for row in matrix["rows"]],
        )
        self.assertEqual(
            [1, 34, 63, 90, 97, 104, 124, 158, 184, 200],
            [row["item_index"] for row in matrix["rows"]],
        )
        self.assertEqual("0101000000000000", matrix["rows"][0]["object_bytes"])
        self.assertEqual("$D492", matrix["rows"][0]["object_address"])
        self.assertEqual("<cFE>こんぼう", matrix["rows"][0]["source"])
        self.assertEqual(
            "<cFE>ふきとばしの杖「0」",
            matrix["rows"][7]["source"],
        )
        self.assertEqual("staff", matrix["widest"]["category"])
        for name in matrix["rows"]:
            self.assertLessEqual(
                name["renderer_pixels"], name["available_pixels"]
            )

        action = measured["action_popup"]
        self.assertEqual(
            [[8, 17], [8, 30], [8, 43], [56, 17], [56, 30], [56, 43],
             [104, 17], [104, 30]],
            action["coordinate_slots"]["entries"],
        )
        domains = action["command_domains"]
        self.assertEqual(16, domains["action_classes"])
        self.assertEqual(12, domains["max_commands"])
        self.assertEqual(
            [4, 9, 9, 10, 9, 8, 9, 11, 9, 12, 6, 8, 6, 6, 6, 6],
            [item["entries"] for item in domains["records"]],
        )
        self.assertEqual(
            ["ひろう", "そうび", "はずす", "なげる", "おく", "出す",
             "こうかん", "すてる", "せつめい"],
            [item["source"] for item in domains["records"][1]["records"]],
        )
        inhibited = action["variants"]["inhibited"]
        ordinary = action["variants"]["ordinary_weapon"]
        self.assertEqual([24, 15], inhibited["enabled_indices"])
        self.assertEqual([1, 13, 17, 24, 15], ordinary["enabled_indices"])
        self.assertEqual(
            ["すてる", "せつめい"],
            [item["source"] for item in inhibited["observed_surfaces"]],
        )
        self.assertEqual(
            ["そうび", "なげる", "おく", "すてる", "せつめい"],
            [item["source"] for item in ordinary["observed_surfaces"]],
        )
        self.assertEqual([96, 16], action["window"]["screen_top_left"])
        self.assertEqual([8, 16], action["window"]["size_tiles"])

        equipment = measured["equipment_cycle"]
        state = equipment["object_state"]
        self.assertEqual("$D492", state["address"])
        self.assertEqual(4, state["flag_byte_offset"])
        self.assertEqual("$10", state["flag_mask"])
        self.assertEqual("0101000000000000", state["before_equip"])
        self.assertEqual("0101000010000000", state["after_equip"])
        self.assertEqual(state["before_equip"], state["after_remove"])
        equipped_row = equipment["equipped_list_surface"]
        self.assertEqual("$EA", equipped_row["marker"])
        self.assertEqual("<EA>こんぼう", equipped_row["source"])
        self.assertEqual([3, 1], equipped_row["start_pen"])
        equipped_action = equipment["equipped_action_popup"]
        self.assertEqual(
            [2, 13, 17, 24, 15], equipped_action["enabled_indices"]
        )
        self.assertEqual(
            ["はずす", "なげる", "おく", "すてる", "せつめい"],
            [item["source"] for item in equipped_action["observed_surfaces"]],
        )
        messages = equipment["result_messages"]
        self.assertEqual(
            [[11, 27], [11, 28]],
            [message["source_reference"] for message in messages],
        )
        self.assertEqual(
            ["194:$5623", "194:$5631"],
            [message["source_record"] for message in messages],
        )
        self.assertEqual(
            [95, 88], [message["renderer_pixels"] for message in messages]
        )
        self.assertEqual(
            [0, 0], [message["automatic_wraps"] for message in messages]
        )

        action_results = measured["action_results"]
        outcomes = action_results["outcomes"]
        self.assertEqual(
            [13, 17, 24], [outcome["command_index"] for outcome in outcomes]
        )
        self.assertEqual(
            [1, 2, 3],
            [outcome["selected_compacted_slot"] for outcome in outcomes],
        )
        self.assertEqual(
            [[11, 25], [11, 95], [11, 96]],
            [outcome["source_reference"] for outcome in outcomes],
        )
        self.assertEqual(
            [125, 81, 79],
            [outcome["renderer_pixels"] for outcome in outcomes],
        )
        self.assertEqual(
            [[117, 125], [81], [79]],
            [outcome["line_widths"] for outcome in outcomes],
        )
        self.assertEqual(
            [0, 0, 0],
            [outcome["automatic_wraps"] for outcome in outcomes],
        )
        self.assertEqual(
            [8, 1], outcomes[0]["appended_source"]["reference"]
        )
        self.assertEqual(
            ["0000000000000000", "0101000000000000", "0000000000000000"],
            [outcome["state"]["object_after"] for outcome in outcomes],
        )
        self.assertEqual(
            ["$FF", "$02", "$FF"],
            [outcome["state"]["floor_slot"]["after"] for outcome in outcomes],
        )
        self.assertEqual(
            1, len({outcome["state"]["inventory_after"] for outcome in outcomes})
        )
        confirmation = action_results["discard_confirmation"]
        self.assertEqual([7, 175], confirmation["reference"])
        self.assertEqual("no", confirmation["default_choice"])
        self.assertEqual("yes", confirmation["confirmed_choice"])
        self.assertEqual(129, confirmation["renderer_pixels"])
        self.assertEqual(0, confirmation["automatic_wraps"])

        representatives = measured["representative_item_routes"]
        self.assertEqual(
            {
                "representative_live_routes": 12,
                "equipment_cycles": 3,
                "primary_actions": 5,
                "container_or_writing": 4,
                "strategy": (
                    "one clean route per distinct high-risk behavior; shared "
                    "handlers are not repeated per item"
                ),
            },
            representatives["coverage"],
        )
        equipment_families = representatives["equipment_families"]
        self.assertEqual(
            ["shield", "bracelet", "arrow"],
            [route["category"] for route in equipment_families],
        )
        self.assertEqual(
            [53, 58, 32],
            [route["equipped_marker"]["renderer_pixels"]
             for route in equipment_families],
        )
        self.assertEqual(
            [[111, 104], [116, 109], [90, 83]],
            [[message["renderer_pixels"] for message in route["result_messages"]]
             for route in equipment_families],
        )
        for route in equipment_families:
            self.assertEqual("$EA", route["equipped_marker"]["marker"])
            self.assertEqual("$10", route["object_state"]["flag_mask"])
            self.assertEqual(
                route["object_state"]["before_equip"],
                route["object_state"]["after_remove"],
            )
            self.assertEqual(
                [0, 0],
                [message["automatic_wraps"]
                 for message in route["result_messages"]],
            )

        primary_actions = representatives["primary_actions"]
        self.assertEqual(
            ["item_shoot_route", "item_eat_route", "item_drink_route",
             "item_read_route", "item_wave_route"],
            [route["name"] for route in primary_actions],
        )
        self.assertEqual(
            [14, 7, 6, 4, 3],
            [route["command_index"] for route in primary_actions],
        )
        self.assertEqual(
            [[[112, 125]], [[83], [81, 55]], [[117], [55, 77]],
             [[111], [116]], [[116]]],
            [[message["line_widths"] for message in route["messages"]]
             for route in primary_actions],
        )
        self.assertEqual([7, 61], primary_actions[3]["target_selector"]["reference"])
        self.assertEqual(
            ["0000000000000000"] * 4 + ["9E08000000000000"],
            [route["state"]["object_after"] for route in primary_actions],
        )

        special_routes = representatives["container_and_writing"]
        self.assertEqual(
            ["item_jar_look_route", "item_jar_insert_full_route",
             "item_blank_scroll_write_route", "item_suction_jar_suck_route"],
            [route["name"] for route in special_routes],
        )
        self.assertEqual(
            [8, 9, 5, 10],
            [route["command_index"] for route in special_routes],
        )
        self.assertEqual(
            "ほぞんの壺「0」",
            special_routes[0]["direct_surfaces"][0]["source"],
        )
        self.assertEqual([7, 27], special_routes[0]["direct_surfaces"][1]["reference"])
        self.assertEqual([11, 77], special_routes[1]["messages"][0]["source_reference"])
        keyboard = special_routes[2]["keyboard_screen"]
        self.assertEqual("graphical tilemap; no direct/full text calls", keyboard["renderer"])
        self.assertEqual([20, 18], keyboard["size_tiles"])
        self.assertEqual("$E7", keyboard["lcdc"])
        self.assertEqual([11, 89], special_routes[3]["messages"][0]["source_reference"])
        self.assertEqual(130, special_routes[3]["messages"][0]["renderer_pixels"])

        descriptions = measured["description_domain"]
        self.assertEqual(216, descriptions["entries"])
        self.assertEqual(216, descriptions["safe_records"])
        self.assertEqual(0, descriptions["dynamic_records"])
        self.assertEqual(29, descriptions["longest"]["index"])
        self.assertEqual(10, descriptions["longest"]["lines"])
        self.assertEqual(192, descriptions["widest"]["index"])
        self.assertEqual(143, descriptions["widest"]["max_composer_pixels"])
        self.assertEqual(143, descriptions["widest"]["max_renderer_pixels"])
        self.assertEqual(
            [10, 12, 29, 42, 55, 23, 21, 15, 6, 3],
            [item["records"] for item in descriptions["line_count_histogram"]],
        )
        roots = measured["item_name_root_domain"]
        self.assertEqual(123, roots["entries"])
        self.assertEqual(7, roots["input_bytes"])
        self.assertEqual([69, 79, 114, 121], roots["disabled_indices"])
        self.assertEqual(
            [27, 20, 34, 26, 16],
            [partition["entries"] for partition in roots["partitions"]],
        )
        self.assertEqual([12, 122], roots["records"][-1]["reference"])
        self.assertEqual([4, 199], roots["records"][-1]["item_reference"])

        abilities = measured["ability_description_domain"]
        self.assertEqual(69, abilities["entries"])
        self.assertEqual("000F160F2D0F", abilities["mapping_table"]["bytes"])
        self.assertEqual(
            [22, 23, 24],
            [family["entries"] for family in abilities["families"]],
        )
        self.assertEqual(
            ["weapon", "shield", "bracelet"],
            [family["family"] for family in abilities["families"]],
        )
        self.assertEqual(141, abilities["records"][0]["available_pixels"])
        self.assertTrue(
            all(
                row["renderer_pixels"] <= row["available_pixels"]
                and row["final_pen"][1] == row["start_pen"][1]
                for row in abilities["records"]
            )
        )
        detail = measured["detail_screen"]
        self.assertEqual([6, 1], detail["body_source"]["reference"])
        self.assertEqual(5, detail["body_source"]["lines"])
        self.assertEqual(
            [[51, 51], [93, 93], [94, 93], [96, 95], [92, 92]],
            detail["body_source"]["line_widths"],
        )
        self.assertEqual(
            [[133, 12], [133, 23]],
            [field["start_pen"] for field in detail["numeric_fields"]],
        )
        self.assertEqual([20, 18], measured["visible_tilemap"]["size_tiles"])
        self.assertEqual(7, measured["money"]["alignment_width"])
        self.assertEqual([129, 4], measured["money"]["start_pen"])

    def test_constant_record_coordinates_and_physical_budgets_are_frozen(self):
        measured = surfaces.static_record_use_summary(self.rom)
        self.assertEqual(FIXTURE["static_record_uses"], measured)
        for use, item in zip(surfaces.STATIC_RECORD_USES, measured):
            with self.subTest(call_site=item["call_site"]):
                at = 17 * 0x4000 + use.evidence_address - 0x4000
                self.assertEqual(use.evidence, self.rom[at:at + len(use.evidence)])
                self.assertEqual(
                    item["physical_budget"],
                    item["physical_right_edge"] - item["start_pen"][0],
                )
                self.assertLessEqual(item["final_pen"][0], item["physical_right_edge"])

        narrowest = min(measured, key=lambda item: item["physical_budget"])
        self.assertEqual("17:$57B5", narrowest["call_site"])
        self.assertEqual(25, narrowest["physical_budget"])
        self.assertEqual(24, narrowest["renderer_pixels"])

    def test_direct_drawer_does_not_interpret_renderer_controls(self):
        payload = bytes((0xFD, 0xF7, 0x01, 0xFC, 0xFF))
        direct = layout.direct_layout(self.rom, payload, start_x=3, start_y=7)
        full = layout.renderer_layout(
            self.rom, payload[:-1], mode=0x02, start_x=3, start_y=7
        )
        self.assertEqual(
            ["FD", "F7", "01", "FC"],
            [item.encoded.hex().upper() for item in direct.placements],
        )
        self.assertEqual((), direct.explicit_breaks)
        self.assertEqual((), direct.boundaries)
        self.assertEqual(0, len(full.placements))
        self.assertEqual(((0, 3, 7),), full.explicit_breaks)
        self.assertEqual(((3, "box", 1, 18),), full.boundaries)
        self.assertEqual(
            layout.composer_advance(self.rom, b"\x01"),
            layout.direct_alignment_width(self.rom, payload),
        )

    def test_visual_edge_validator_accepts_exact_fit_and_rejects_spill(self):
        patched = english_font.install(self.rom)
        start_x = 6
        right_edge = 85
        advance = layout.renderer_advance(patched, english.encode("W"))
        fitting_count = (right_edge - start_x) // advance
        fitting = english.encode("W" * fitting_count)
        measured = layout.validate_direct_surface(
            patched, fitting, start_x=start_x, start_y=1, right_edge=right_edge
        )
        self.assertLessEqual(measured.rightmost_pen, right_edge)
        with self.assertRaisesRegex(layout.LayoutError, "beyond visual edge"):
            layout.validate_direct_surface(
                patched,
                english.encode("W" * (fitting_count + 1)),
                start_x=start_x,
                start_y=1,
                right_edge=right_edge,
            )

        aligned = layout.validate_direct_right_aligned_surface(
            patched,
            english.encode("W" * 13),
            left_edge=59,
            anchor_x=142,
            start_y=24,
        )
        self.assertEqual((64, 142), (aligned.start_x, aligned.final_x))
        with self.assertRaisesRegex(layout.LayoutError, "outside visual range"):
            layout.validate_direct_right_aligned_surface(
                patched,
                english.encode("W" * 14),
                left_edge=59,
                anchor_x=142,
                start_y=24,
            )

    def test_production_item_roots_and_ability_rows_are_complete_and_safe(self):
        result = extract.extract(self.rom)
        translated = translations.load_path(
            ROOT / "script" / "en", result["records"]
        )
        font_rom = english_font.install(self.rom)
        by_reference = {
            (reference.group, reference.index): record
            for record in result["records"]
            for reference in record.references
        }

        widths = []
        for index in range(surfaces.ITEM_ABILITY_DESCRIPTION_ENTRIES):
            record = by_reference[(surfaces.ITEM_ABILITY_DESCRIPTION_GROUP, index)]
            entry = translated[(record.bank, record.address)]
            self.assertTrue(entry.text.startswith("<EC>"))
            measured = layout.validate_direct_surface(
                font_rom,
                entry.encoded,
                start_x=surfaces.ITEM_ABILITY_DESCRIPTION_START_X,
                start_y=1,
                right_edge=surfaces.ITEM_ABILITY_DESCRIPTION_RIGHT_EDGE,
            )
            self.assertEqual((), measured.explicit_breaks)
            widths.append(
                measured.rightmost_pen
                - surfaces.ITEM_ABILITY_DESCRIPTION_START_X
            )
        self.assertEqual(69, len(widths))
        self.assertEqual(141, max(widths))

        disabled = set(surfaces.ITEM_NAME_ROOT_DISABLED_INDICES)
        checked = 0
        for _category, first, last, first_item in (
            surfaces.ITEM_NAME_ROOT_PARTITIONS
        ):
            for index in range(first, last + 1):
                root_record = by_reference[(surfaces.ITEM_NAME_ROOT_GROUP, index)]
                item_index = first_item + index - first
                item_record = by_reference[(4, item_index)]
                root = translated[(root_record.bank, root_record.address)].text
                item = translated[(item_record.bank, item_record.address)].text
                if index in disabled:
                    self.assertTrue(root.startswith("X"))
                    # The native root matcher disables a record only when its
                    # first encoded byte is $21.  Uppercase X deliberately
                    # retains that byte contract; lowercase x would not.
                    self.assertEqual(0x21, english.encode(root)[0])
                    root = root[1:]
                else:
                    self.assertNotEqual(0x21, english.encode(root)[0])
                self.assertTrue(item.casefold().startswith(root.casefold()))
                checked += 1
        self.assertEqual(123, checked)

        status_labels = {
            16: "Atk <27><br>Slots <hspace:01><27>  <hspace:05><25>",
            17: "Def <27><br>Slots <hspace:01><27>  <hspace:05><25>",
            18: "Slots <hspace:01><27>  <hspace:05><25>",
        }
        for index, expected in status_labels.items():
            record = by_reference[(24, index)]
            self.assertEqual(
                expected, translated[(record.bank, record.address)].text
            )

        action_labels = (
            "Items", "Equip", "Remove", "Wave", "Read", "Write", "Eat",
            "Eat", "Look", "Put In", "Absorb", "Push", "Take Out", "Throw",
            "Shoot", "Info", "Name", "Place", "Exchange", "Pick Up", "Set",
            "Step On", "Pick Up", "Modify", "Discard",
        )
        action_widths = []
        for index, expected in enumerate(action_labels):
            record = by_reference[(7, index)]
            entry = translated[(record.bank, record.address)]
            self.assertEqual(expected, entry.text)
            if index == 0:
                continue
            measured = layout.validate_direct_surface(
                font_rom,
                entry.encoded,
                start_x=surfaces.ITEM_ACTION_COORDINATES[0][0],
                start_y=surfaces.ITEM_ACTION_COORDINATES[0][1],
                right_edge=surfaces.ITEM_ACTION_COORDINATES[3][0],
            )
            self.assertEqual((), measured.explicit_breaks)
            action_widths.append(
                measured.rightmost_pen - surfaces.ITEM_ACTION_COORDINATES[0][0]
            )
        self.assertEqual(24, len(action_widths))
        self.assertEqual(41, max(action_widths))

    def test_production_condition_page_is_complete_series_consistent_and_safe(self):
        result = extract.extract(self.rom)
        translated = translations.load_path(
            ROOT / "script" / "en", result["records"]
        )
        font_rom = english_font.install(self.rom)
        by_reference = {
            (reference.group, reference.index): record
            for record in result["records"]
            for reference in record.references
        }

        expected = (
            "Asleep", "Paralyzed", "Onigiri", "Hiding", "Slumbering",
            "Asleep", "Bear Trap", "Invisible", "Confused", "Sealed",
            "Inaccurate", "Afraid", "Slow", "Swift", "Blind", "Invisible",
            "Enraged", "Under a Spell", "Disguised", "Empathetic",
            "1/2 Max HP", "1/2 Attack", "1/2 Level", "Invincible", "", "",
            "See All Monsters", "See All Items", "Muzzled", "Power Up",
            "Grounded", "Poisonproof", "Alert", "Silent", "Perfect Accuracy",
            "Misses Often", "Muzzled", "Satiated", "Identifier", "Sharp Eyes",
            "No Explosions", "Unpaid", "Wake Enemies", "Trapper", "Clumsy",
            "1/2 Hunger", "2x Hunger", "HP Regeneration", "Random Warp",
            "Satiated", "Water Walking", "Explosive", "Trapproof", "Thief!!!",
            "Starving", "Bracelet Effect Unknown",
        )
        widths = []
        widest = None
        for index, text in enumerate(expected):
            record = by_reference[(surfaces.STATUS_CONDITION_GROUP, index)]
            entry = translated.get((record.bank, record.address))
            self.assertEqual(text, "" if entry is None else entry.text)
            if not text:
                self.assertEqual(b"", record.raw)
                continue
            measured = layout.validate_direct_surface(
                font_rom,
                entry.encoded,
                start_x=1,
                start_y=1,
                right_edge=layout.CANVAS_WIDTH_PIXELS,
            )
            width = measured.rightmost_pen - 1
            widths.append(width)
            if widest is None or width > widest[0]:
                widest = (width, record.id)

        self.assertEqual(54, len(widths))
        self.assertEqual((116, "193:$78C5"), widest)

        adjacent = {
            (7, 25): "Current Status",
            (7, 27): "<26>Nothing inside.<26>",
            (7, 28): "<26>No abilities learned.<26>",
            (7, 32): "You have no items.",
            (7, 33): "Nothing is on the ground.",
            (7, 57): "Step On",
            (7, 61): "Choose an item.",
            (7, 65): "Pick Up",
            (7, 84): "Healthy",
            (7, 175): "Discard this item?<br><br><hspace:18>Yes<hspace:40>No",
            (17, 0): "No traps can be made.",
        }
        for reference, text in adjacent.items():
            record = by_reference[reference]
            self.assertEqual(
                text, translated[(record.bank, record.address)].text
            )


class ProductionRankingSuffixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / ROM_NAME
        if not cls.source_path.exists():
            raise unittest.SkipTest("original ROM not present")
        original = cls.source_path.read_bytes()
        if sha1(original).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

        extracted = extract.extract(original)
        localized = translations.load_path(
            ROOT / "script" / "en",
            extracted["records"],
        )
        overrides = translations.encoded_overrides(localized)
        width_analysis = runtime_widths.analyze(
            english_font.install(original),
            extracted,
            localized,
        )
        production, _allocation, _validation = translated_build.build_rom(
            original,
            overrides,
            runtime_contract=width_analysis.contract,
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.production_path = Path(cls.temporary.name) / "ranking-labels.gbc"
        cls.production_path.write_bytes(production)

        owner = cls.PyBoy(
            str(cls.production_path),
            window="null",
            sound_emulated=False,
        )
        owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(owner)
            for current in range(15000):
                if current % 180 == 0:
                    owner.button("a", capture_dialogue.PRESS_FRAMES)
                owner.tick()
            state = io.BytesIO()
            owner.save_state(state)
            cls.state_bytes = state.getvalue()
        finally:
            owner.stop(save=False)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_live_ranking_draws_11250g_and_9f_as_separate_bounded_fields(self):
        pyboy = self.PyBoy(
            str(self.production_path),
            window="null",
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        redirected = [False]
        events = []

        seeded = bytearray(surfaces.RANKING_SEEDED_RECORD)
        seeded[9:13] = (11250).to_bytes(4, "little")
        seeded[14] = 9

        def write_record():
            for offset, value in enumerate(seeded):
                pyboy.memory[surfaces.RANKING_RECORD_ADDRESS + offset] = value

        def at_dispatch(_context=None):
            if redirected[0]:
                return
            redirected[0] = True
            pyboy.register_file.A = surfaces.RANKING_SYNTHETIC_ROUTE["target_bank"]
            pyboy.register_file.HL = surfaces.RANKING_SYNTHETIC_ROUTE["entries"][
                "current_record_list"
            ]
            pyboy.register_file.C = 0

        def at_rank_scan_return(_context=None):
            pyboy.register_file.C = 0

        def at_list_row(_context=None):
            write_record()

        def at_direct(_context=None):
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                if value == 0xFF:
                    break
                raw.append(value)
            events.append(
                {
                    "raw": bytes(raw),
                    "text": codec.decode(bytes(raw)),
                    "start_pen": (
                        pyboy.memory[0xC4D6],
                        pyboy.memory[0xC4D7],
                    ),
                }
            )

        try:
            pyboy.load_state(io.BytesIO(self.state_bytes))
            pyboy.hook_register(
                *surfaces.RANKING_SYNTHETIC_ROUTE["dispatcher"],
                at_dispatch,
                None,
            )
            pyboy.hook_register(11, 0x5E32, at_rank_scan_return, None)
            pyboy.hook_register(3, 0x60D4, at_list_row, None)
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct, None)
            for _current in range(
                surfaces.RANKING_SYNTHETIC_ROUTE["final_frame"] + 1
            ):
                pyboy.tick()

            self.assertTrue(redirected[0])
            top_row = {
                event["start_pen"]: event
                for event in events
                if event["start_pen"][1] == 1
            }
            amount_events = [
                event
                for event in events
                if event["start_pen"][1] == 1 and event["text"] == "11250"
            ]
            self.assertEqual(
                1,
                len(amount_events),
                {pen: event["text"] for pen, event in top_row.items()},
            )
            self.assertLess(amount_events[0]["start_pen"][0], 90)
            self.assertEqual(english.encode_source("G"), top_row[(90, 1)]["raw"])
            floor_events = [
                event
                for event in events
                if (
                    event["start_pen"][1] == 1
                    and event["raw"]
                    == (b"\xFE" * 4) + codec.encode_source("9")
                    and 90 < event["start_pen"][0] < 137
                )
            ]
            self.assertEqual(
                1,
                len(floor_events),
                {pen: event["text"] for pen, event in top_row.items()},
            )
            self.assertEqual(english.encode_source("F"), top_row[(137, 1)]["raw"])
        finally:
            pyboy.stop(save=False)


class LiveOpeningPositionedSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        if sha1(cls.path.read_bytes()).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def test_clean_boot_trace_and_79_pixel_menu_column(self):
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        frame = [0]
        events = []

        def at_direct_draw(_context=None):
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                code = pyboy.memory[(pointer + offset) & 0xFFFF]
                if code == 0xFF:
                    break
                raw.append(code)
            events.append(
                {
                    "raw": bytes(raw),
                    "start_pen": [pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]],
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for current in range(621):
                frame[0] = current
                if current == 360:
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if current == 540:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            expected = FIXTURE["observed_surfaces"]
            self.assertEqual(2, len(events))
            for event, item in zip(events, expected):
                with self.subTest(surface=item["name"]):
                    self.assertEqual(item["start_pen"], event["start_pen"])
                    self.assertEqual(item["observed_mode"], event["mode"])
                    self.assertEqual(item["observed_frame"], event["frame"])

            # On a blank row through the menu, the interior ends at x=84 and
            # the stable bevel/border begins at x=85.  This makes x=85 the
            # exclusive pen edge and leaves 79 pixels from the observed x=6.
            image = pyboy.screen.image.convert("RGB")
            self.assertEqual((248, 248, 248), image.getpixel((84, 12)))
            self.assertEqual((168, 168, 168), image.getpixel((85, 12)))
            self.assertEqual((0, 0, 0), image.getpixel((86, 12)))
            self.assertEqual((248, 248, 248), image.getpixel((87, 12)))
            self.assertNotEqual((248, 248, 248), image.getpixel((88, 12)))
        finally:
            pyboy.stop(save=False)

    def test_narrow_25_pixel_suffix_fits_at_its_static_x_coordinate(self):
        narrow = next(
            item
            for item in FIXTURE["static_record_uses"]
            if item["call_site"] == "17:$57B5"
        )
        payload = codec.encode_source(narrow["source"])
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        direct_calls = [0]
        armed = [False]
        pre_wrap_pens = []

        def at_direct_draw(_context=None):
            direct_calls[0] += 1
            if direct_calls[0] != 2:
                return
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            for offset, value in enumerate(payload + b"\xFF"):
                pyboy.memory[pointer + offset] = value
            pyboy.memory[0xC4D6] = narrow["start_pen"][0]
            pyboy.memory[0xC4D7] = narrow["start_pen"][1]
            armed[0] = True

        def at_pre_wrap(_context=None):
            if armed[0]:
                pre_wrap_pens.append(
                    (pyboy.memory[0xC4D6], pyboy.memory[0xC4D7])
                )

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            pyboy.hook_register(3, 0x6F1F, at_pre_wrap, None)
            for current in range(582):
                if current == 360:
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if current == 540:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            self.assertTrue(armed[0])
            self.assertTrue(pre_wrap_pens)
            self.assertEqual(
                {narrow["start_pen"][1]}, {pen[1] for pen in pre_wrap_pens}
            )
            self.assertEqual(narrow["final_pen"][0], pyboy.memory[0xC4D6])
            self.assertEqual(narrow["final_pen"][1], pyboy.memory[0xC4D7])
        finally:
            pyboy.stop(save=False)

    def test_clean_boot_wanderers_guide_draws_all_ten_topic_rows(self):
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        frame = [0]
        events = []

        def at_direct_draw(_context=None):
            if frame[0] < 646:
                return
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            events.append(
                {
                    "raw": bytes(raw),
                    "start_pen": [pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]],
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        try:
            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            for current in range(681):
                frame[0] = current
                if current == 360:
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                if current == 540:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 620:
                    pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                if current == 640:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            expected = FIXTURE["guide_surfaces"]
            self.assertEqual(11, len(events))
            for event, item in zip(events, expected):
                with self.subTest(surface=item["name"]):
                    self.assertEqual(item["start_pen"], event["start_pen"])
                    self.assertEqual(item["observed_mode"], event["mode"])
                    self.assertEqual(item["observed_frame"], event["frame"])
                    self.assertEqual(
                        codec.encode_source(item["source"]) + b"\xFF", event["raw"]
                    )
        finally:
            pyboy.stop(save=False)

    def test_ingame_help_lists_and_status_conditions_draw_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        for fixture_key, submenu_down_frames, confirm_frame, frame_count, event_floor in (
            ("control_help_surfaces", (), 340, 371, 345),
            ("technique_help_surfaces", (300,), 340, 371, 345),
            ("status_condition_screen", (260, 290, 320), 370, 401, 372),
        ):
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            frame = [0]
            events = []
            numeric_calls = []
            menu_edge_pixels = [None]
            menu_tilemaps = [None]
            template_obstructions = [None]
            popup_tilemap = [None]
            status_tilemap = [None]

            def at_direct_draw(_context=None):
                pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
                raw = bytearray()
                for offset in range(0x100):
                    value = pyboy.memory[(pointer + offset) & 0xFFFF]
                    raw.append(value)
                    if value == 0xFF:
                        break
                events.append(
                    {
                        "raw": bytes(raw),
                        "start_pen": [pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]],
                        "mode": pyboy.memory[0xC4DA],
                        "frame": frame[0],
                    }
                )

            def at_unsigned_draw(_context=None):
                stack = pyboy.register_file.SP
                return_address = (
                    pyboy.memory[stack]
                    | (pyboy.memory[(stack + 1) & 0xFFFF] << 8)
                )
                raw = bytes(pyboy.memory[0xC800 + offset] for offset in range(4))
                numeric_calls.append(
                    {
                        "return_address": "$%04X" % return_address,
                        "anchor": [pyboy.register_file.E, pyboy.register_file.D],
                        "value": int.from_bytes(raw, "little"),
                        "frame": frame[0],
                    }
                )

            def at_main_menu_template(_context=None):
                old_svbk = pyboy.memory[0xFF70]
                pyboy.memory[0xFF70] = 7
                obstructions = {}
                for field in FIXTURE["main_menu_numeric_status"]["fields"]:
                    anchor_x, anchor_y = field["anchor"]
                    ink = []
                    for y in range(anchor_y, min(anchor_y + 8, 112)):
                        for x in range(anchor_x):
                            tile = (y // 8) * layout.CANVAS_TILE_COLUMNS + x // 8
                            high = pyboy.memory[
                                0xD000 + tile * 16 + (y % 8) * 2 + 1
                            ]
                            if high & (0x80 >> (x % 8)):
                                ink.append(x)
                    obstructions[field["name"]] = max(ink)
                template_obstructions[0] = obstructions
                pyboy.memory[0xFF70] = old_svbk & 7

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
                pyboy.hook_register(17, 0x410D, at_unsigned_draw, None)
                pyboy.hook_register(17, 0x6A2C, at_main_menu_template, None)
                for current in range(frame_count):
                    frame[0] = current
                    if current == 0:
                        pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                    if current in (100, 130, 160):
                        pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                    if current == 200:
                        pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                    if current in submenu_down_frames:
                        pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                    if current == confirm_frame:
                        pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                    pyboy.tick()
                    if current == 80:
                        image = pyboy.screen.image.convert("RGB")
                        menu_edge_pixels[0] = [
                            image.getpixel((x, 36)) for x in range(52, 56)
                        ]
                        old_vbk = pyboy.memory[0xFF4F]
                        pyboy.memory[0xFF4F] = 0
                        expected_maps = FIXTURE["main_menu_numeric_status"][
                            "visible_tilemap"
                        ]
                        menu_tilemaps[0] = {}
                        for name in ("right_panel", "bottom_panel"):
                            item = expected_maps[name]
                            left, top = item["top_left"]
                            width, height = item["size_tiles"]
                            menu_tilemaps[0][name] = [
                                [
                                    pyboy.memory[
                                        surfaces.MAIN_MENU_TILEMAP_BASE
                                        + (top + row) * 32
                                        + left
                                        + column
                                    ]
                                    for column in range(width)
                                ]
                                for row in range(height)
                            ]
                        pyboy.memory[0xFF4F] = old_vbk & 1
                    if current == 240:
                        old_vbk = pyboy.memory[0xFF4F]
                        pyboy.memory[0xFF4F] = 0
                        base = surfaces.HELP_POPUP_TILEMAP_BASE
                        left, top = surfaces.HELP_POPUP_TILEMAP_TOP_LEFT
                        popup_tilemap[0] = [
                            [
                                pyboy.memory[base + (top + row) * 32 + left + column]
                                for column in range(8)
                            ]
                            for row in range(8)
                        ]
                        pyboy.memory[0xFF4F] = old_vbk & 1
                    if fixture_key == "status_condition_screen" and current == 400:
                        old_vbk = pyboy.memory[0xFF4F]
                        pyboy.memory[0xFF4F] = 0
                        base = surfaces.STATUS_TILEMAP_BASE
                        left, top = surfaces.STATUS_TILEMAP_TOP_LEFT
                        status_tilemap[0] = [
                            [
                                pyboy.memory[
                                    base + (top + row) * 32 + left + column
                                ]
                                for column in range(20)
                            ]
                            for row in range(18)
                        ]
                        pyboy.memory[0xFF4F] = old_vbk & 1

                if fixture_key == "control_help_surfaces":
                    menu_items = list(FIXTURE["main_menu_surfaces"])
                    location = FIXTURE["main_menu_contract"]["location_panel"][
                        "observed"
                    ]
                    menu_items.append(
                        {
                            "name": "main_menu_location",
                            "source": location["source"],
                            "start_pen": [location["start_x"], 24],
                            "observed_mode": location["observed_mode"],
                            "observed_frame": location["observed_frame"],
                        }
                    )
                    for item in menu_items:
                        matches = [
                            event
                            for event in events
                            if event["raw"]
                            == codec.encode_source(item["source"]) + b"\xFF"
                            and event["start_pen"] == item["start_pen"]
                            and event["mode"] == item["observed_mode"]
                            and event["frame"] == item["observed_frame"]
                        ]
                        with self.subTest(surface=item["name"]):
                            self.assertEqual(1, len(matches))

                    # A blank scanline through the left column ends at x=52;
                    # the grey/black bevel starts at x=53.  Thus translated
                    # labels starting at x=3 have a 50-pixel visual budget.
                    self.assertEqual(
                        [
                            (248, 248, 248),
                            (168, 168, 168),
                            (0, 0, 0),
                            (248, 248, 248),
                        ],
                        menu_edge_pixels[0],
                    )

                    numeric = FIXTURE["main_menu_numeric_status"]
                    self.assertEqual(
                        {
                            "right_panel": numeric["visible_tilemap"][
                                "right_panel"
                            ]["rows"],
                            "bottom_panel": numeric["visible_tilemap"][
                                "bottom_panel"
                            ]["rows"],
                        },
                        menu_tilemaps[0],
                    )
                    self.assertEqual(
                        {
                            field["name"]: field["left_obstruction_right"]
                            for field in numeric["fields"]
                        },
                        template_obstructions[0],
                    )
                    self.assertEqual(
                        [
                            {
                                "return_address": field["return_address"],
                                "anchor": field["anchor"],
                                "value": field["observed"]["value"],
                                "frame": field["observed"]["frame"],
                            }
                            for field in numeric["fields"]
                        ],
                        numeric_calls,
                    )
                    for field in numeric["fields"]:
                        matches = [
                            event
                            for event in events
                            if event["raw"]
                            == bytes.fromhex(field["observed"]["formatted"])
                            and event["start_pen"]
                            == field["observed"]["start_pen"]
                            and event["mode"] == field["observed"]["mode"]
                            and event["frame"] == field["observed"]["frame"]
                        ]
                        with self.subTest(numeric_field=field["name"]):
                            self.assertEqual(1, len(matches))

                    for item in FIXTURE["help_popup_surfaces"]:
                        matches = [
                            event
                            for event in events
                            if event["raw"]
                            == codec.encode_source(item["source"]) + b"\xFF"
                            and event["start_pen"] == item["start_pen"]
                            and event["mode"] == item["observed_mode"]
                            and event["frame"] == item["observed_frame"]
                        ]
                        with self.subTest(surface=item["name"]):
                            self.assertEqual(1, len(matches))
                    self.assertEqual(
                        FIXTURE["help_popup_remap"]["visible_tilemap"]["rows"],
                        popup_tilemap[0],
                    )

                if fixture_key == "status_condition_screen":
                    expected = FIXTURE[fixture_key]["observed_surfaces"]
                    self.assertEqual(
                        FIXTURE[fixture_key]["visible_tilemap"]["rows"],
                        status_tilemap[0],
                    )
                else:
                    expected = FIXTURE[fixture_key]
                help_events = [
                    event for event in events if event["frame"] >= event_floor
                ]
                self.assertEqual(len(expected), len(help_events))
                for event, item in zip(help_events, expected):
                    with self.subTest(family=fixture_key, surface=item["name"]):
                        self.assertEqual(item["start_pen"], event["start_pen"])
                        self.assertEqual(item["observed_mode"], event["mode"])
                        self.assertEqual(item["observed_frame"], event["frame"])
                        self.assertEqual(
                            codec.encode_source(item["source"]) + b"\xFF",
                            event["raw"],
                        )
            finally:
                pyboy.stop(save=False)

    def test_training_and_travel_dungeon_selectors_draw_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["dungeon_selectors"]
        route = expected["synthetic_live_route"]
        dispatcher_bank, dispatcher_address = (
            surfaces.DUNGEON_SELECTOR_SYNTHETIC_ROUTE["dispatcher"]
        )
        for variant_name in ("training", "travel"):
            with self.subTest(selector=variant_name):
                variant = expected["variants"][variant_name]
                pyboy = self.PyBoy(str(self.path), window="null")
                pyboy.set_emulation_speed(0)
                frame = [0]
                redirected = [False]
                events = []
                tilemap = [None]
                registers = [None]

                def at_dispatch(_context=None):
                    if redirected[0]:
                        return
                    redirected[0] = True
                    pyboy.register_file.A = (
                        surfaces.DUNGEON_SELECTOR_ENTRY[0]
                    )
                    pyboy.register_file.HL = (
                        surfaces.DUNGEON_SELECTOR_ENTRY[1]
                    )
                    pyboy.register_file.C = variant["input_c"]

                def at_direct_draw(_context=None):
                    pointer = (
                        pyboy.register_file.D << 8
                    ) | pyboy.register_file.E
                    raw = bytearray()
                    for offset in range(0x100):
                        value = pyboy.memory[(pointer + offset) & 0xFFFF]
                        raw.append(value)
                        if value == 0xFF:
                            break
                    events.append(
                        {
                            "raw": bytes(raw),
                            "start_pen": [
                                pyboy.memory[0xC4D6],
                                pyboy.memory[0xC4D7],
                            ],
                            "mode": pyboy.memory[0xC4DA],
                            "frame": frame[0],
                        }
                    )

                try:
                    pyboy.load_state(io.BytesIO(state_bytes))
                    pyboy.hook_register(
                        dispatcher_bank,
                        dispatcher_address,
                        at_dispatch,
                        None,
                    )
                    pyboy.hook_register(
                        *surfaces.DIRECT_RENDERER, at_direct_draw, None
                    )
                    for current in range(route["final_frame"] + 1):
                        frame[0] = current
                        pyboy.tick()
                        if current == expected["shared"]["screen"][
                            "observed_frame"
                        ]:
                            old_vbk = pyboy.memory[0xFF4F]
                            pyboy.memory[0xFF4F] = 0
                            tilemap[0] = [
                                [
                                    pyboy.memory[
                                        surfaces.STATUS_TILEMAP_BASE
                                        + row * 32
                                        + column
                                    ]
                                    for column in range(20)
                                ]
                                for row in range(18)
                            ]
                            pyboy.memory[0xFF4F] = old_vbk & 1
                            registers[0] = {
                                "lcdc": "$%02X" % pyboy.memory[0xFF40],
                                "wx": pyboy.memory[0xFF4B],
                                "wy": pyboy.memory[0xFF4A],
                            }

                    self.assertTrue(redirected[0])
                    observed = variant["observed_surfaces"]
                    self.assertEqual(len(observed), len(events))
                    for item, event in zip(observed, events):
                        self.assertEqual(
                            codec.encode_source(item["source"]) + b"\xFF",
                            event["raw"],
                        )
                        self.assertEqual(item["start_pen"], event["start_pen"])
                        self.assertEqual(item["observed_mode"], event["mode"])
                        self.assertEqual(item["observed_frame"], event["frame"])

                    screen = expected["shared"]["screen"]
                    self.assertEqual(screen["rows"], tilemap[0])
                    self.assertEqual(
                        {"lcdc": screen["lcdc"], **screen["registers"]},
                        registers[0],
                    )
                finally:
                    pyboy.stop(save=False)

    def test_seeded_adventure_history_and_all_ranking_views_draw_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["history_and_ranking"]
        ranking = expected["wanderer_ranking"]
        route = expected["synthetic_live_route"]
        direct_renderer = surfaces.DIRECT_RENDERER
        source_renderer = layout.FULL_RENDERER_ENTRY

        def write_bytes(target, address, raw):
            for offset, value in enumerate(raw):
                target.memory[address + offset] = value

        for route_name, entry_address in (
            surfaces.RANKING_SYNTHETIC_ROUTE["entries"].items()
        ):
            with self.subTest(route=route_name):
                pyboy = self.PyBoy(str(self.path), window="null")
                pyboy.set_emulation_speed(0)
                frame = [0]
                redirected = [False]
                direct_events = []
                source_events = []
                record_loads = [0]

                def capture_event(renderer):
                    pointer = (
                        pyboy.register_file.D << 8
                    ) | pyboy.register_file.E
                    raw = bytearray()
                    for offset in range(0x100):
                        value = pyboy.memory[(pointer + offset) & 0xFFFF]
                        if value == 0xFF:
                            break
                        raw.append(value)
                    return {
                        "renderer": renderer,
                        "raw": bytes(raw).hex().upper(),
                        "staged_text": codec.decode(bytes(raw)),
                        "start_pen": [
                            pyboy.memory[0xC4D6],
                            pyboy.memory[0xC4D7],
                        ],
                        "mode": pyboy.memory[0xC4DA],
                        "frame": frame[0],
                    }

                def at_dispatch(_context=None):
                    if redirected[0]:
                        return
                    redirected[0] = True
                    pyboy.register_file.A = (
                        surfaces.RANKING_SYNTHETIC_ROUTE["target_bank"]
                    )
                    pyboy.register_file.HL = entry_address
                    pyboy.register_file.C = 0

                def at_direct(_context=None):
                    direct_events.append(capture_event("direct"))

                def at_source(_context=None):
                    source_events.append(capture_event("full_source"))

                def seed_record():
                    write_bytes(
                        pyboy,
                        surfaces.RANKING_RECORD_ADDRESS,
                        surfaces.RANKING_SEEDED_RECORD,
                    )

                def seed_extended():
                    write_bytes(
                        pyboy,
                        surfaces.RANKING_EXTENDED_ADDRESS,
                        b"\xFF" * surfaces.RANKING_EXTENDED_SIZE,
                    )
                    write_bytes(
                        pyboy,
                        surfaces.RANKING_EXTENDED_ADDRESS,
                        surfaces.RANKING_SEEDED_MEMO,
                    )
                    write_bytes(
                        pyboy,
                        surfaces.RANKING_EXTENDED_ADDRESS
                        + surfaces.RANKING_MEMO_SIZE,
                        surfaces.RANKING_SEEDED_FINAL_MESSAGE + b"\xFF",
                    )

                def at_history_body(_context=None):
                    write_bytes(
                        pyboy,
                        surfaces.ADVENTURE_HISTORY_FLAG_BASE,
                        bytes.fromhex("FF03000000"),
                    )

                def at_rank_scan_return(_context=None):
                    pyboy.register_file.C = 0

                def at_list_row(_context=None):
                    seed_record()

                def at_record_return(_context=None):
                    if record_loads[0] == 0:
                        seed_record()
                        pyboy.register_file.E = 0
                    else:
                        pyboy.register_file.E = 0xFF
                    record_loads[0] += 1

                def at_detail(_context=None):
                    seed_record()
                    seed_extended()

                def at_message(_context=None):
                    seed_extended()

                try:
                    pyboy.load_state(io.BytesIO(state_bytes))
                    pyboy.hook_register(
                        *surfaces.RANKING_SYNTHETIC_ROUTE["dispatcher"],
                        at_dispatch,
                        None,
                    )
                    pyboy.hook_register(*direct_renderer, at_direct, None)
                    pyboy.hook_register(*source_renderer, at_source, None)

                    if route_name == "adventure_history":
                        pyboy.hook_register(
                            *surfaces.ADVENTURE_HISTORY_BODY,
                            at_history_body,
                            None,
                        )
                    elif route_name == "current_record_list":
                        pyboy.hook_register(
                            11, 0x5E32, at_rank_scan_return, None
                        )
                        pyboy.hook_register(3, 0x60D4, at_list_row, None)
                    elif route_name == "paged_record_list":
                        pyboy.hook_register(
                            11, 0x5641, at_record_return, None
                        )
                        pyboy.hook_register(
                            11, 0x5654, at_record_return, None
                        )
                    elif route_name == "record_detail":
                        pyboy.hook_register(3, 0x65CA, at_detail, None)
                    elif route_name == "final_message":
                        pyboy.hook_register(3, 0x663C, at_message, None)

                    for current in range(route["final_frame"] + 1):
                        frame[0] = current
                        pyboy.tick()

                    self.assertTrue(redirected[0])
                    if route_name == "adventure_history":
                        expected_direct = expected["adventure_history"][
                            "seeded_first_page"
                        ]["expected_direct_draws"]
                        expected_source = []
                    else:
                        expected_route = ranking["seeded_routes"][route_name]
                        expected_direct = expected_route[
                            "expected_direct_draws"
                        ]
                        expected_source = expected_route[
                            "expected_source_draws"
                        ]
                    self.assertEqual(expected_direct, direct_events)
                    self.assertEqual(expected_source, source_events)
                finally:
                    pyboy.stop(save=False)

    def test_record_pickers_and_mode_3_graphical_input_replay_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["record_picker_and_graphical_input"]

        def invoke_constructor(entry, setup, return_hooks=()):
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            redirected = [False]
            captured = [None]

            def at_dispatch(_context=None):
                if redirected[0]:
                    return
                redirected[0] = True
                pyboy.register_file.A = entry[0]
                pyboy.register_file.HL = entry[1]
                setup(pyboy)

            def at_outer_return(_context=None):
                if captured[0] is not None or pyboy.memory[0xFFF7] != entry[0]:
                    return
                old_vbk = pyboy.memory[0xFF4F]
                pyboy.memory[0xFF4F] = 0
                rows = [
                    [
                        pyboy.memory[0x9800 + row * 32 + column]
                        for column in range(20)
                    ]
                    for row in range(18)
                ]
                pyboy.memory[0xFF4F] = old_vbk & 1
                captured[0] = {
                    "c14e": pyboy.memory[0xC14E],
                    "cursor": pyboy.memory[0xC14F],
                    "maximum_index": pyboy.memory[0xC151],
                    "buffer_position": pyboy.memory[0xC152],
                    "maximum_bytes": pyboy.memory[0xC153],
                    "mode": pyboy.memory[0xC195],
                    "rows": rows,
                    "lcdc": pyboy.memory[0xFF40],
                    "wx": pyboy.memory[0xFF4B],
                    "wy": pyboy.memory[0xFF4A],
                }

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(0, 0x09BD, at_outer_return, None)
                for bank, address, callback in return_hooks:
                    pyboy.hook_register(bank, address, callback(pyboy), None)
                for _current in range(20):
                    pyboy.tick()
                self.assertTrue(redirected[0])
                self.assertIsNotNone(captured[0])
                return captured[0]
            finally:
                pyboy.stop(save=False)

        def set_c(value):
            def factory(target):
                def callback(_context=None):
                    target.register_file.C = value
                return callback
            return factory

        def set_d(value):
            def factory(target):
                def callback(_context=None):
                    target.register_file.D = value
                return callback
            return factory

        ranking_constructor = invoke_constructor(
            surfaces.RANKING_RECORD_PICKER_ENTRY,
            lambda _target: None,
            ((4, 0x495E, set_c(5)),),
        )
        self.assertEqual(13, ranking_constructor["c14e"])
        self.assertEqual(4, ranking_constructor["maximum_index"])

        grade_constructor = invoke_constructor(
            surfaces.GRADE_CATEGORY_PICKER_ENTRY,
            lambda _target: None,
            ((4, 0x4990, set_d(4)),),
        )
        self.assertEqual(13, grade_constructor["c14e"])
        self.assertEqual(3, grade_constructor["maximum_index"])

        def setup_graphical(target):
            target.register_file.C = surfaces.GRAPHICAL_INPUT_MODE
            for offset in range(surfaces.GRAPHICAL_INPUT_BUFFER_SIZE + 1):
                target.memory[surfaces.GRAPHICAL_INPUT_BUFFER_ADDRESS + offset] = 0xFF

        graphical_constructor = invoke_constructor(
            surfaces.GRAPHICAL_INPUT_ENTRY, setup_graphical
        )
        constructor_expected = expected["graphical_input_mode_3"][
            "seeded_live_outcomes"
        ]["constructor"]
        self.assertEqual(constructor_expected["mode"], graphical_constructor["mode"])
        self.assertEqual(
            constructor_expected["maximum_bytes"],
            graphical_constructor["maximum_bytes"],
        )
        self.assertEqual(constructor_expected["cursor"], graphical_constructor["cursor"])
        self.assertEqual(
            constructor_expected["buffer_position"],
            graphical_constructor["buffer_position"],
        )
        self.assertEqual(
            [list(row) for row in surfaces.GRAPHICAL_INPUT_MODE_3_TILEMAP_ROWS],
            graphical_constructor["rows"],
        )
        self.assertEqual(
            {"lcdc": 0xE7, "wx": 7, "wy": 144},
            {
                "lcdc": graphical_constructor["lcdc"],
                "wx": graphical_constructor["wx"],
                "wy": graphical_constructor["wy"],
            },
        )

        def run_controller(address, setup, buttons, frames=20):
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            redirected = [False]
            result = [None]

            def at_dispatch(_context=None):
                if redirected[0]:
                    return
                redirected[0] = True
                pyboy.register_file.A = 16
                pyboy.register_file.HL = address
                setup(pyboy)

            def at_outer_return(_context=None):
                if result[0] is None and pyboy.memory[0xFFF7] == 16:
                    result[0] = pyboy.register_file.A

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(0, 0x09BD, at_outer_return, None)
                for current in range(frames):
                    for button_frame, button in buttons:
                        if current == button_frame:
                            pyboy.button(button, capture_dialogue.PRESS_FRAMES)
                    pyboy.tick()
                return {
                    "result": result[0],
                    "cursor": pyboy.memory[0xC14F],
                    "buffer_position": pyboy.memory[0xC152],
                    "buffer": bytes(
                        pyboy.memory[surfaces.GRAPHICAL_INPUT_BUFFER_ADDRESS + offset]
                        for offset in range(surfaces.GRAPHICAL_INPUT_BUFFER_SIZE + 1)
                    ),
                }
            finally:
                pyboy.stop(save=False)

        def picker_setup(maximum_index):
            def setup(target):
                target.memory[0xC14E] = 5
                target.memory[0xC14F] = 0
                target.memory[0xC150] = 0
                target.memory[0xC151] = maximum_index
            return setup

        picker_routes = (
            ("down_then_a", ((2, "down"), (8, "a"))),
            ("up_then_a", ((2, "up"), (8, "a"))),
            ("b", ((2, "b"),)),
        )
        for family, address, maximum_index in (
            ("ranking_record_picker", 0x59F8, 4),
            ("grade_category_picker", 0x5A52, 3),
        ):
            for route_name, buttons in picker_routes:
                with self.subTest(family=family, route=route_name):
                    observed = run_controller(
                        address, picker_setup(maximum_index), buttons
                    )
                    route_expected = expected[family]["seeded_live_outcomes"][
                        route_name
                    ]
                    self.assertEqual(route_expected["selection"], observed["cursor"])
                    self.assertEqual(
                        int(route_expected["result"][1:], 16), observed["result"]
                    )

        def editor_setup(buffer, position=0):
            def setup(target):
                for address, value in (
                    (0xC14E, 0x12),
                    (0xC14F, 0),
                    (0xC150, 0),
                    (0xC151, 1),
                    (0xC152, position),
                    (0xC153, surfaces.GRAPHICAL_INPUT_BUFFER_SIZE),
                    (0xC195, surfaces.GRAPHICAL_INPUT_MODE),
                ):
                    target.memory[address] = value
                for offset, value in enumerate(buffer):
                    target.memory[
                        surfaces.GRAPHICAL_INPUT_BUFFER_ADDRESS + offset
                    ] = value
            return setup

        blank = bytes((0xD5,) * 4 + (0xFF,))
        inserted = run_controller(
            0x5BCE, editor_setup(blank), ((2, "a"),), frames=10
        )
        self.assertIsNone(inserted["result"])
        self.assertEqual(0x80, inserted["buffer"][0])
        self.assertEqual(1, inserted["buffer_position"])

        voiced = run_controller(
            0x5BCE,
            editor_setup(bytes((0x35, 0xD5, 0xD5, 0xD5, 0xFF))),
            ((2, "select"),),
            frames=10,
        )
        self.assertIsNone(voiced["result"])
        self.assertEqual(0x67, voiced["buffer"][0])

        confirmed = run_controller(
            0x5BCE,
            editor_setup(bytes((0x30, 0xD5, 0xD5, 0xD5, 0xFF)), position=1),
            ((2, "start"), (8, "a")),
        )
        self.assertEqual(0x33, confirmed["cursor"])
        self.assertEqual(0xF8, confirmed["result"])

        cancelled = run_controller(
            0x5BCE, editor_setup(blank), ((2, "b"),), frames=12
        )
        self.assertEqual(0, cancelled["cursor"])
        self.assertEqual(0xFE, cancelled["result"])

    def test_diary_management_create_delete_and_rename_replay_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["diary_management"]

        def run_handler(handler, inputs, blank_name=False, frames=100):
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            frame = [0]
            observed = {
                "redirected": False,
                "return": None,
                "save_calls": 0,
                "delete_calls": 0,
                "controller_results": [],
                "constructor": None,
            }

            def at_dispatch(_context=None):
                if observed["redirected"]:
                    return
                observed["redirected"] = True
                pyboy.register_file.A = handler[0]
                pyboy.register_file.HL = handler[1]

            def blank_input_buffer(_context=None):
                if not blank_name:
                    return
                for offset in range(4):
                    pyboy.memory[0xC16D + offset] = 0xD5
                pyboy.memory[0xC171] = 0xFF

            def at_editor_controller(_context=None):
                if observed["constructor"] is not None:
                    return
                old_vbk = pyboy.memory[0xFF4F]
                pyboy.memory[0xFF4F] = 0
                rows = [
                    [
                        pyboy.memory[0x9800 + row * 32 + column]
                        for column in range(20)
                    ]
                    for row in range(18)
                ]
                pyboy.memory[0xFF4F] = old_vbk & 1
                observed["constructor"] = {
                    "mode": pyboy.memory[0xC195],
                    "maximum_bytes": pyboy.memory[0xC153],
                    "cursor": pyboy.memory[0xC14F],
                    "buffer_position": pyboy.memory[0xC152],
                    "rows": rows,
                    "lcdc": pyboy.memory[0xFF40],
                    "wx": pyboy.memory[0xFF4B],
                    "wy": pyboy.memory[0xFF4A],
                }

            def create_controller_return(_context=None):
                observed["controller_results"].append(pyboy.register_file.A)

            def delete_controller_return(_context=None):
                observed["controller_results"].append(pyboy.register_file.C)

            def rename_controller_return(_context=None):
                observed["controller_results"].append(pyboy.register_file.A)

            def save_call(_context=None):
                observed["save_calls"] += 1

            def delete_call(_context=None):
                observed["delete_calls"] += 1

            def handler_return(_context=None):
                if observed["return"] is not None:
                    return
                observed["return"] = {
                    "result": pyboy.register_file.A,
                    "controller_result": pyboy.register_file.C,
                    "buffer": bytes(pyboy.memory[0xC16D:0xC172]),
                }

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(18, 0x51CA, blank_input_buffer, None)
                pyboy.hook_register(16, 0x5AD2, at_editor_controller, None)
                pyboy.hook_register(16, 0x7864, create_controller_return, None)
                pyboy.hook_register(16, 0x787A, delete_controller_return, None)
                pyboy.hook_register(16, 0x78D4, rename_controller_return, None)
                pyboy.hook_register(11, 0x45E3, save_call, None)
                pyboy.hook_register(11, 0x49D2, delete_call, None)
                for address in (0x786A, 0x788C, 0x7892, 0x7956):
                    pyboy.hook_register(16, address, handler_return, None)

                input_frames = {at: button for at, button in inputs}
                for frame[0] in range(frames):
                    if frame[0] in input_frames:
                        pyboy.button(
                            input_frames[frame[0]],
                            capture_dialogue.PRESS_FRAMES,
                        )
                    pyboy.tick()
                self.assertTrue(observed["redirected"])
                self.assertIsNotNone(observed["return"])
                return observed
            finally:
                pyboy.stop(save=False)

        create = run_handler(
            surfaces.DIARY_CREATE_HANDLER,
            ((14, "b"), (28, "a"), (44, "start"), (56, "a")),
            blank_name=True,
        )
        create_expected = expected["create_diary"]["seeded_live_outcome"]
        self.assertEqual([0xFE, 0xF8], create["controller_results"])
        self.assertEqual(
            int(create_expected["result"][1:], 16),
            create["return"]["result"],
        )
        self.assertEqual(
            bytes.fromhex(create_expected["buffer"]),
            create["return"]["buffer"],
        )

        constructor_expected = expected["mode_4_name_editor"][
            "seeded_live_outcomes"
        ]["constructor"]
        self.assertEqual(
            constructor_expected,
            {
                key: create["constructor"][key]
                for key in (
                    "mode",
                    "maximum_bytes",
                    "cursor",
                    "buffer_position",
                )
            },
        )
        self.assertEqual(
            expected["mode_4_name_editor"]["graphics"]["visible_rows"],
            create["constructor"]["rows"],
        )
        self.assertEqual(
            {"lcdc": 0xE7, "wx": 7, "wy": 144},
            {
                key: create["constructor"][key]
                for key in ("lcdc", "wx", "wy")
            },
        )

        delete_no = run_handler(
            surfaces.DIARY_DELETE_HANDLER, ((30, "a"),)
        )
        no_expected = expected["delete_diary"]["outcomes"]["no"]
        self.assertEqual([no_expected["controller_result"]], delete_no["controller_results"])
        self.assertEqual(
            int(no_expected["handler_result"][1:], 16),
            delete_no["return"]["result"],
        )
        self.assertEqual(no_expected["mutation_calls"], delete_no["delete_calls"])

        delete_yes = run_handler(
            surfaces.DIARY_DELETE_HANDLER,
            ((24, "right"), (36, "a")),
        )
        yes_expected = expected["delete_diary"]["outcomes"]["yes"]
        self.assertEqual([yes_expected["controller_result"]], delete_yes["controller_results"])
        self.assertEqual(
            int(yes_expected["handler_result"][1:], 16),
            delete_yes["return"]["result"],
        )
        self.assertEqual(yes_expected["mutation_calls"], delete_yes["delete_calls"])

        rename_cancel = run_handler(
            surfaces.DIARY_RENAME_HANDLER,
            ((14, "b"),),
            blank_name=True,
        )
        cancel_expected = expected["rename"]["seeded_live_outcomes"]["blank_b"]
        self.assertEqual([0xFE], rename_cancel["controller_results"])
        self.assertEqual(cancel_expected["save_calls"], rename_cancel["save_calls"])
        self.assertEqual(
            int(cancel_expected["result"][1:], 16),
            rename_cancel["return"]["result"],
        )

        rename_accept = run_handler(
            surfaces.DIARY_RENAME_HANDLER,
            ((14, "a"), (30, "start"), (42, "a")),
            blank_name=True,
        )
        accept_expected = expected["rename"]["seeded_live_outcomes"]["accepted"]
        self.assertEqual([0xF8], rename_accept["controller_results"])
        self.assertEqual(accept_expected["save_calls"], rename_accept["save_calls"])
        self.assertEqual(
            int(accept_expected["result"][1:], 16),
            rename_accept["return"]["result"],
        )
        self.assertEqual(
            bytes.fromhex(accept_expected["buffer"]),
            rename_accept["return"]["buffer"],
        )

    def test_remaining_front_end_hub_routes_replay_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["remaining_hub_routes"]

        def run_route(
            entry,
            inputs=(),
            frames=100,
            return_sites=(),
            configure=None,
        ):
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            frame = [0]
            observed = {
                "redirected": False,
                "direct": [],
                "sources": [],
                "returns": [],
            }

            def at_dispatch(_context=None):
                if observed["redirected"]:
                    return
                observed["redirected"] = True
                pyboy.register_file.A = entry[0]
                pyboy.register_file.HL = entry[1]

            def at_direct_draw(_context=None):
                pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
                raw = bytearray()
                for offset in range(0x400):
                    value = pyboy.memory[(pointer + offset) & 0xFFFF]
                    if value == 0xFF:
                        break
                    raw.append(value)
                observed["direct"].append(
                    {
                        "raw": bytes(raw),
                        "start_pen": [
                            pyboy.memory[0xC4D6],
                            pyboy.memory[0xC4D7],
                        ],
                        "mode": pyboy.memory[0xC4DA],
                        "frame": frame[0],
                    }
                )

            def at_source_init(_context=None):
                source = capture_dialogue.source_location(pyboy)
                if not observed["sources"] or observed["sources"][-1] != source:
                    observed["sources"].append(source)

            def return_hook(bank, address):
                def at_return(_context=None):
                    observed["returns"].append(
                        {
                            "site": "%d:$%04X" % (bank, address),
                            "a": pyboy.register_file.A,
                            "c": pyboy.register_file.C,
                            "frame": frame[0],
                        }
                    )
                return at_return

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
                pyboy.hook_register(
                    *capture_dialogue.SOURCE_INIT, at_source_init, None
                )
                for bank, address in return_sites:
                    pyboy.hook_register(
                        bank, address, return_hook(bank, address), None
                    )
                if configure is not None:
                    configure(pyboy, observed, frame)

                input_frames = {at: button for at, button in inputs}
                for frame[0] in range(frames):
                    if frame[0] in input_frames:
                        pyboy.button(
                            input_frames[frame[0]],
                            capture_dialogue.PRESS_FRAMES,
                        )
                    pyboy.tick()
                self.assertTrue(observed["redirected"])
                return observed
            finally:
                pyboy.stop(save=False)

        def assert_positioned_rows(expected_rows, observed_rows):
            for row in expected_rows:
                raw = bytes.fromhex(row["raw"])
                matches = [event for event in observed_rows if event["raw"] == raw]
                self.assertTrue(matches, row["reference"])
                self.assertTrue(
                    any(event["start_pen"] == row["start_pen"] for event in matches),
                    row["reference"],
                )

        exchange = expected["item_exchange"]
        exchange_cancel = run_route(
            surfaces.ITEM_EXCHANGE_HANDLER,
            ((20, "b"),),
            return_sites=((16, 0x78AE),),
        )
        assert_positioned_rows(
            exchange["menu"]["choices"], exchange_cancel["direct"]
        )
        self.assertEqual(0xFB, exchange_cancel["returns"][-1]["a"])

        exchange_give = run_route(
            surfaces.ITEM_EXCHANGE_HANDLER,
            ((20, "a"), (50, "a")),
            return_sites=((16, 0x78BC),),
        )
        self.assertIn((192, 0x6D34), exchange_give["sources"])
        self.assertEqual(0xF4, exchange_give["returns"][-1]["a"])

        def seed_full_storage(pyboy, _observed, _frame):
            def at_storage_scan(_context=None):
                old_svbk = pyboy.memory[0xFF70]
                pyboy.memory[0xFF70] = 2
                for address in range(0xD000, 0xD064):
                    pyboy.memory[address] = 0
                pyboy.memory[0xFF70] = old_svbk

            pyboy.hook_register(11, 0x6FCC, at_storage_scan, None)

        exchange_receive = run_route(
            surfaces.ITEM_EXCHANGE_HANDLER,
            ((14, "down"), (26, "a"), (55, "a")),
            frames=120,
            return_sites=((16, 0x78C6),),
            configure=seed_full_storage,
        )
        self.assertIn((192, 0x6D61), exchange_receive["sources"])
        self.assertEqual(0xF4, exchange_receive["returns"][-1]["a"])

        secrets = expected["wanderers_secrets"]
        secrets_cancel = run_route(
            surfaces.WANDERERS_SECRETS_HANDLER,
            ((30, "b"),),
            return_sites=((16, 0x7956),),
        )
        assert_positioned_rows([secrets["heading"]], secrets_cancel["direct"])
        assert_positioned_rows(secrets["rows"], secrets_cancel["direct"])
        self.assertEqual(0xF4, secrets_cancel["returns"][-1]["a"])

        def capture_secret_event(pyboy, observed, frame):
            observed["events"] = []

            def at_event(_context=None):
                observed["events"].append(
                    {"id": pyboy.register_file.B, "frame": frame[0]}
                )

            pyboy.hook_register(0, 0x1D2F, at_event, None)

        secrets_first = run_route(
            surfaces.WANDERERS_SECRETS_HANDLER,
            ((30, "a"),),
            frames=45,
            configure=capture_secret_event,
        )
        self.assertEqual(4, secrets_first["events"][0]["id"])

        grade = expected["wanderer_grade"]

        def enable_all_grade_categories(pyboy, _observed, _frame):
            def force_count(_context=None):
                pyboy.register_file.D = 4

            def force_available(_context=None):
                pyboy.register_file.C = 1

            pyboy.hook_register(4, 0x4990, force_count, None)
            pyboy.hook_register(17, 0x58A9, force_available, None)

        grade_cancel = run_route(
            surfaces.WANDERER_GRADE_HANDLER,
            ((30, "b"),),
            return_sites=((16, 0x79F5),),
            configure=enable_all_grade_categories,
        )
        assert_positioned_rows(grade["picker"]["rows"], grade_cancel["direct"])
        self.assertEqual(0xFB, grade_cancel["returns"][-1]["a"])

        def select_grade_category(pyboy, observed, frame):
            enable_all_grade_categories(pyboy, observed, frame)
            observed["grade_details"] = 0

            def at_detail(_context=None):
                observed["grade_details"] += 1

            pyboy.hook_register(*surfaces.WANDERER_GRADE_SCREEN, at_detail, None)

        grade_selection = run_route(
            surfaces.WANDERER_GRADE_HANDLER,
            ((30, "a"), (55, "b")),
            frames=75,
            configure=select_grade_category,
        )
        self.assertEqual(1, grade_selection["grade_details"])
        assert_positioned_rows(
            [grade["detail"]["headers"][0]], grade_selection["direct"]
        )

        def seed_full_notebook(pyboy, observed, _frame):
            observed["notebook"] = {
                "states": [],
                "details": 0,
            }

            def force_catalog(_context=None):
                pyboy.register_file.A = 1

            def at_controller(_context=None):
                if not observed["notebook"]["states"]:
                    # Seed the bottom row so Down crosses to the next page.
                    pyboy.memory[0xC14F] = 18
                    pyboy.memory[0xC150] = 18
                state = (
                    pyboy.memory[0xC152],
                    pyboy.memory[0xC14F],
                    pyboy.memory[0xC153],
                )
                if not observed["notebook"]["states"] or (
                    observed["notebook"]["states"][-1] != state
                ):
                    observed["notebook"]["states"].append(state)

            def at_detail(_context=None):
                observed["notebook"]["details"] += 1

            pyboy.hook_register(11, 0x7A5A, force_catalog, None)
            pyboy.hook_register(11, 0x7ADC, force_catalog, None)
            pyboy.hook_register(16, 0x7EA5, at_controller, None)
            pyboy.hook_register(0xF4, 0x44E5, at_detail, None)

        notebook = expected["monster_notebook"]
        notebook_nav = run_route(
            surfaces.MONSTER_NOTEBOOK_HANDLER,
            ((25, "down"), (45, "b")),
            frames=65,
            return_sites=((16, 0x79E0),),
            configure=seed_full_notebook,
        )
        notebook_pages = [state[0] for state in notebook_nav["notebook"]["states"]]
        self.assertEqual(7, notebook_nav["notebook"]["states"][0][2])
        self.assertIn(1, notebook_pages, notebook_nav["notebook"])
        self.assertEqual(1, notebook_pages[-1])
        self.assertIn((193, 0x6F61), notebook_nav["sources"])
        self.assertEqual(0xF4, notebook_nav["returns"][-1]["a"])

        notebook_detail = run_route(
            surfaces.MONSTER_NOTEBOOK_HANDLER,
            ((25, "a"), (55, "b")),
            frames=75,
            return_sites=((16, 0x79E0),),
            configure=seed_full_notebook,
        )
        self.assertEqual(1, notebook_detail["notebook"]["details"])
        self.assertEqual(0xF4, notebook_detail["returns"][-1]["a"])

    def test_adventure_start_menu_maximum_and_sparse_masks_replay_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["adventure_start_menu"]

        def run_screen(variant_name):
            variant = expected["variants"][variant_name]
            enabled = set(variant["enabled_slots"])
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            frame = [0]
            observed = {
                "redirected": False,
                "slots": [],
                "direct": [],
                "return": None,
            }

            def at_dispatch(_context=None):
                if observed["redirected"]:
                    return
                observed["redirected"] = True
                pyboy.register_file.A = surfaces.ADVENTURE_START_SCREEN[0]
                pyboy.register_file.HL = surfaces.ADVENTURE_START_SCREEN[1]

            def force_body_predicate(_context=None):
                # At 4:$72D8 the predicate has reused E internally.  The
                # caller's saved BC is two bytes above SP, so its C byte is
                # the stable original slot number.
                slot = pyboy.memory[(pyboy.register_file.SP + 2) & 0xFFFF]
                observed["slots"].append(slot)
                pyboy.register_file.C = int(slot in enabled)

            def force_count_predicate(_context=None):
                pyboy.register_file.C = int(pyboy.register_file.E in enabled)

            def at_direct_draw(_context=None):
                if observed["return"] is not None:
                    return
                pointer = (
                    (pyboy.register_file.D << 8) | pyboy.register_file.E
                )
                raw = bytearray()
                for offset in range(0x100):
                    value = pyboy.memory[(pointer + offset) & 0xFFFF]
                    if value == 0xFF:
                        break
                    raw.append(value)
                observed["direct"].append(
                    {
                        "raw": bytes(raw).hex().upper(),
                        "start_pen": [
                            pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]
                        ],
                        "observed_mode": pyboy.memory[0xC4DA],
                        "observed_frame": frame[0],
                    }
                )

            def at_screen_return(_context=None):
                if observed["return"] is not None:
                    return
                tilemap = variant["tilemap"]
                left, top = tilemap["top_left_tile"]
                width, height = tilemap["size_tiles"]
                old_vbk = pyboy.memory[0xFF4F]
                pyboy.memory[0xFF4F] = 0
                rows = [
                    [
                        pyboy.memory[
                            0x9800 + (top + row) * 32 + left + column
                        ]
                        for column in range(width)
                    ]
                    for row in range(height)
                ]
                pyboy.memory[0xFF4F] = old_vbk & 1
                observed["return"] = {
                    "maximum_index": pyboy.memory[0xC151],
                    "tilemap_sha1": sha1(
                        bytes(value for row in rows for value in row)
                    ).hexdigest(),
                    "lcdc": pyboy.memory[0xFF40],
                    "wx": pyboy.memory[0xFF4B],
                    "wy": pyboy.memory[0xFF4A],
                    "frame": frame[0],
                }

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(4, 0x72D8, force_body_predicate, None)
                pyboy.hook_register(11, 0x517D, force_count_predicate, None)
                pyboy.hook_register(
                    *surfaces.DIRECT_RENDERER, at_direct_draw, None
                )
                pyboy.hook_register(18, 0x439D, at_screen_return, None)
                for frame[0] in range(20):
                    pyboy.tick()
                self.assertTrue(observed["redirected"])
                self.assertIsNotNone(observed["return"])
                return observed
            finally:
                pyboy.stop(save=False)

        for variant_name in (
            "maximum_predicate_consistent",
            "sparse_compaction_probe",
        ):
            with self.subTest(variant=variant_name):
                variant = expected["variants"][variant_name]
                observed = run_screen(variant_name)
                self.assertEqual(list(range(9)), observed["slots"])
                self.assertEqual(
                    [
                        {
                            key: row[key]
                            for key in (
                                "raw",
                                "start_pen",
                                "observed_mode",
                                "observed_frame",
                            )
                        }
                        for row in variant["rows"]
                    ],
                    observed["direct"],
                )
                self.assertEqual(
                    {
                        "maximum_index": variant["maximum_index"],
                        "tilemap_sha1": variant["tilemap"]["sha1"],
                        "lcdc": 0xE7,
                        "wx": 167,
                        "wy": 0,
                        "frame": variant["observed_final_frame"],
                    },
                    observed["return"],
                )

        def map_sparse_ordinal(ordinal):
            enabled = set(surfaces.ADVENTURE_START_SPARSE_PROBE)
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            redirected = [False]
            mapped_slot = [None]

            def at_dispatch(_context=None):
                if redirected[0]:
                    return
                redirected[0] = True
                pyboy.register_file.A = (
                    surfaces.ADVENTURE_START_ORDINAL_MAPPER[0]
                )
                pyboy.register_file.HL = (
                    surfaces.ADVENTURE_START_ORDINAL_MAPPER[1]
                )
                pyboy.register_file.D = ordinal

            def force_predicate(_context=None):
                pyboy.register_file.C = int(pyboy.register_file.E in enabled)

            def at_candidate_return(_context=None):
                if pyboy.register_file.D == 0:
                    mapped_slot[0] = pyboy.register_file.E

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(11, 0x5167, force_predicate, None)
                pyboy.hook_register(11, 0x5170, at_candidate_return, None)
                for _current in range(10):
                    pyboy.tick()
                self.assertTrue(redirected[0])
                self.assertIsNotNone(mapped_slot[0])
                return mapped_slot[0]
            finally:
                pyboy.stop(save=False)

        sparse_mapping = expected["variants"]["sparse_compaction_probe"][
            "compacted_ordinal_to_slot"
        ]
        self.assertEqual(
            [item["slot"] for item in sparse_mapping],
            [map_sparse_ordinal(item["ordinal"]) for item in sparse_mapping],
        )

    def test_at_feet_empty_trap_item_and_value_branches_draw_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        expected = FIXTURE["at_feet"]

        def run_variant(kind, trap_index=None, item_seed=None, metadata=False):
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            frame = [0]
            observed = {
                "redirected": False,
                "direct": [],
                "body_classifier_hits": 0,
                "auxiliary_classifier_hits": 0,
                "returns": 0,
            }

            def at_dispatch(_context=None):
                if observed["redirected"]:
                    return
                observed["redirected"] = True
                pyboy.register_file.A = surfaces.AT_FEET_ENTRY[0]
                pyboy.register_file.HL = surfaces.AT_FEET_ENTRY[1]
                pyboy.register_file.C = 1

            def at_direct_draw(_context=None):
                pointer = (
                    (pyboy.register_file.D << 8) | pyboy.register_file.E
                )
                raw = bytearray()
                for offset in range(0x100):
                    value = pyboy.memory[(pointer + offset) & 0xFFFF]
                    if value == 0xFF:
                        break
                    raw.append(value)
                observed["direct"].append(
                    {
                        "raw": bytes(raw),
                        "start_pen": [
                            pyboy.memory[0xC4D6],
                            pyboy.memory[0xC4D7],
                        ],
                        "mode": pyboy.memory[0xC4DA],
                        "frame": frame[0],
                    }
                )

            def force_classifier(auxiliary=False):
                def at_classifier(_context=None):
                    hit_name = (
                        "auxiliary_classifier_hits"
                        if auxiliary
                        else "body_classifier_hits"
                    )
                    observed[hit_name] += 1
                    if kind == "empty":
                        pyboy.register_file.F &= 0xEF
                    else:
                        pyboy.register_file.F |= 0x10
                        pyboy.register_file.A = (
                            0 if kind == "trap" else 0xFF
                        )

                return at_classifier

            def force_trap(_context=None):
                pyboy.register_file.A = trap_index

            def force_item(_context=None):
                pyboy.register_file.A = item_seed.object_index

            def at_return(_context=None):
                observed["returns"] += 1

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                if item_seed is not None:
                    object_bytes = (
                        surfaces.AT_FEET_METADATA_SEED_OBJECT
                        if metadata
                        else item_seed.object_record
                    )
                    old_svbk = pyboy.memory[0xFF70]
                    pyboy.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
                    object_at = (
                        surfaces.ITEM_OBJECT_BASE
                        + item_seed.object_index * surfaces.ITEM_OBJECT_SIZE
                    )
                    for offset, value in enumerate(object_bytes):
                        pyboy.memory[object_at + offset] = value
                    pyboy.memory[0xFF70] = old_svbk & 7

                pyboy.hook_register(0, 0x09AC, at_dispatch, None)
                pyboy.hook_register(
                    *surfaces.DIRECT_RENDERER, at_direct_draw, None
                )
                pyboy.hook_register(
                    17, 0x55B3, force_classifier(), None
                )
                pyboy.hook_register(
                    17, 0x5607, force_classifier(auxiliary=True), None
                )
                pyboy.hook_register(16, 0x4EC8, at_return, None)
                if kind == "trap":
                    pyboy.hook_register(17, 0x55BD, force_trap, None)
                if item_seed is not None:
                    pyboy.hook_register(17, 0x55CF, force_item, None)
                    pyboy.hook_register(17, 0x560E, force_item, None)

                for frame[0] in range(20):
                    pyboy.tick()
                self.assertTrue(observed["redirected"])
                self.assertEqual(1, observed["body_classifier_hits"])
                self.assertEqual(1, observed["auxiliary_classifier_hits"])
                self.assertGreaterEqual(observed["returns"], 1)
                return observed
            finally:
                pyboy.stop(save=False)

        def assert_direct(contract, events):
            raw = bytes.fromhex(contract["raw"])
            matches = [event for event in events if event["raw"] == raw]
            self.assertTrue(matches, contract.get("name", contract.get("reference")))
            self.assertTrue(
                any(
                    event["start_pen"] == contract["start_pen"]
                    and event["mode"] == contract["observed_mode"]
                    for event in matches
                ),
                contract.get("name", contract.get("reference")),
            )

        def assert_common(events):
            shell = expected["common_shell"]
            assert_direct(shell["heading"], events)
            assert_direct(shell["current_money"]["number"], events)
            assert_direct(shell["current_money"]["suffix"], events)

        empty = run_variant("empty")
        assert_common(empty["direct"])
        body_raws = {
            bytes.fromhex(row["raw"])
            for row in expected["body"]["trap"]["records"]
        }
        body_raws.update(
            bytes.fromhex(row["raw"])
            for row in expected["body"]["item"]["live_representatives"]
        )
        self.assertFalse(
            any(event["raw"] in body_raws for event in empty["direct"])
        )

        trap_rows = expected["body"]["trap"]["records"]
        for row in (trap_rows[0], trap_rows[-1]):
            with self.subTest(trap=row["trap_name_index"]):
                observed = run_variant(
                    "trap", trap_index=row["trap_name_index"]
                )
                assert_common(observed["direct"])
                assert_direct(row, observed["direct"])

        item_rows = expected["body"]["item"]["live_representatives"]
        item_seeds = (
            surfaces.ITEM_CATEGORY_SEEDS[0],
            surfaces.ITEM_CATEGORY_SEEDS[-1],
        )
        for row, seed in zip(item_rows, item_seeds):
            with self.subTest(item=row["category"]):
                observed = run_variant("item", item_seed=seed)
                assert_common(observed["direct"])
                assert_direct(row, observed["direct"])

        metadata = expected["body"]["item"]["metadata_value_branch"]
        observed = run_variant(
            "item", item_seed=surfaces.ITEM_CATEGORY_SEEDS[0], metadata=True
        )
        assert_common(observed["direct"])
        assert_direct(item_rows[0], observed["direct"])
        for field in metadata["runtime_fields"]:
            assert_direct(field, observed["direct"])
        assert_direct(metadata["value_suffix"], observed["direct"])

    def test_item_detail_maps_first_and_last_rune_bits_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        ability_rows = FIXTURE["seeded_item_list"][
            "ability_description_domain"
        ]["records"]
        variants = (
            ("weapon_first", 1, 1, 0, 0),
            ("weapon_critical", 1, 1, 10, 10),
            ("weapon_last", 1, 1, 21, 21),
            ("shield_first", 35, 2, 0, 22),
            ("shield_last", 35, 2, 22, 44),
            ("bracelet_first", 63, 3, 0, 45),
            ("bracelet_last", 63, 3, 23, 68),
        )
        for name, item_index, action_class, bit, description_index in variants:
            pyboy = self.PyBoy(str(self.path), window="null")
            pyboy.set_emulation_speed(0)
            frame = [0]
            events = []

            def at_direct_draw(_context=None):
                if frame[0] < 340:
                    return
                pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
                raw = bytearray()
                for offset in range(0x100):
                    value = pyboy.memory[(pointer + offset) & 0xFFFF]
                    if value == 0xFF:
                        break
                    raw.append(value)
                events.append(
                    {
                        "raw": bytes(raw),
                        "start_pen": [
                            pyboy.memory[0xC4D6],
                            pyboy.memory[0xC4D7],
                        ],
                    }
                )

            try:
                pyboy.load_state(io.BytesIO(state_bytes))
                old_svbk = pyboy.memory[0xFF70]
                pyboy.memory[0xFF70] = surfaces.ITEM_INVENTORY_WRAM_BANK
                pyboy.memory[surfaces.ITEM_INVENTORY_BASE] = 2
                pyboy.memory[surfaces.ITEM_INVENTORY_BASE + 1] = (
                    surfaces.ITEM_INVENTORY_SENTINEL
                )
                pyboy.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
                object_at = surfaces.ITEM_OBJECT_BASE + 2 * surfaces.ITEM_OBJECT_SIZE
                flags = [0, 0, 0]
                flags[bit // 8] = 1 << (bit % 8)
                object_record = bytes(
                    (item_index, action_class, 0, 0, 0, *flags)
                )
                for offset, value in enumerate(object_record):
                    pyboy.memory[object_at + offset] = value
                pyboy.memory[0xFF70] = old_svbk & 7

                pyboy.hook_register(
                    *surfaces.DIRECT_RENDERER, at_direct_draw, None
                )
                for current in range(421):
                    frame[0] = current
                    if current == 0:
                        pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                    if current in (100, 200, 350):
                        pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                    if current == 300:
                        pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                    pyboy.tick()
            finally:
                pyboy.stop(save=False)

            expected = ability_rows[description_index]
            matches = [
                event
                for event in events
                if event["raw"] == bytes.fromhex(expected["raw"])
                and event["start_pen"] == expected["start_pen"]
            ]
            with self.subTest(route=name, description=description_index):
                self.assertEqual(1, len(matches))

    def test_seeded_inventory_item_screen_draws_live(self):
        state_owner = self.PyBoy(str(self.path), window="null")
        state_owner.set_emulation_speed(0)
        try:
            capture_dialogue.run_to_dialogue(state_owner)
            for current in range(15000):
                if current % 180 == 0:
                    state_owner.button("a", capture_dialogue.PRESS_FRAMES)
                state_owner.tick()
            state = io.BytesIO()
            state_owner.save_state(state)
            state_bytes = state.getvalue()
        finally:
            state_owner.stop(save=False)

        def seed_inventory(target, assert_empty=False):
            old_svbk = target.memory[0xFF70]
            target.memory[0xFF70] = surfaces.ITEM_INVENTORY_WRAM_BANK
            if assert_empty:
                self.assertEqual(
                    surfaces.ITEM_INVENTORY_SENTINEL,
                    target.memory[surfaces.ITEM_INVENTORY_BASE],
                )
            for slot, seed in enumerate(surfaces.ITEM_CATEGORY_SEEDS):
                target.memory[surfaces.ITEM_INVENTORY_BASE + slot] = (
                    seed.object_index
                )
            target.memory[
                surfaces.ITEM_INVENTORY_BASE + len(surfaces.ITEM_CATEGORY_SEEDS)
            ] = surfaces.ITEM_INVENTORY_SENTINEL
            target.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
            for seed in surfaces.ITEM_CATEGORY_SEEDS:
                object_at = (
                    surfaces.ITEM_OBJECT_BASE
                    + seed.object_index * surfaces.ITEM_OBJECT_SIZE
                )
                for offset, value in enumerate(seed.object_record):
                    target.memory[object_at + offset] = value
            target.memory[0xFF70] = old_svbk & 7

        expected = FIXTURE["seeded_item_list"]
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        frame = [0]
        events = []
        source_events = []
        tilemap = [None]
        action_tilemap = [None]
        action_registers = [None]
        detail_tilemap = [None]
        detail_window_registers = [None]

        def at_direct_draw(_context=None):
            if frame[0] < 100:
                return
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            events.append(
                {
                    "raw": bytes(raw),
                    "start_pen": [pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]],
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        def at_source_init(_context=None):
            if frame[0] < 300:
                return
            bank, pointer = capture_dialogue.source_location(pyboy)
            source_events.append(
                {
                    "bank": bank,
                    "pointer": pointer,
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        try:
            pyboy.load_state(io.BytesIO(state_bytes))
            seed_inventory(pyboy, assert_empty=True)

            pyboy.hook_register(*surfaces.DIRECT_RENDERER, at_direct_draw, None)
            pyboy.hook_register(
                *capture_dialogue.SOURCE_INIT, at_source_init, None
            )
            for current in range(421):
                frame[0] = current
                if current == 0:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                if current == 100:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 200:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 300:
                    pyboy.button("down", capture_dialogue.PRESS_FRAMES)
                if current == 350:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
                if current == 150:
                    old_vbk = pyboy.memory[0xFF4F]
                    pyboy.memory[0xFF4F] = 0
                    tilemap[0] = [
                        [
                            pyboy.memory[
                                surfaces.ITEM_TILEMAP_BASE + row * 32 + column
                            ]
                            for column in range(20)
                        ]
                        for row in range(18)
                    ]
                    pyboy.memory[0xFF4F] = old_vbk & 1
                if current == 250:
                    old_vbk = pyboy.memory[0xFF4F]
                    pyboy.memory[0xFF4F] = 0
                    action_tilemap[0] = [
                        [
                            pyboy.memory[
                                surfaces.ITEM_ACTION_WINDOW_TILEMAP_BASE
                                + row * 32
                                + column
                            ]
                            for column in range(8)
                        ]
                        for row in range(16)
                    ]
                    action_registers[0] = {
                        "lcdc": "$%02X" % pyboy.memory[0xFF40],
                        "wx": pyboy.memory[0xFF4B],
                        "wy": pyboy.memory[0xFF4A],
                    }
                    pyboy.memory[0xFF4F] = old_vbk & 1
                if current == 400:
                    old_vbk = pyboy.memory[0xFF4F]
                    pyboy.memory[0xFF4F] = 0
                    detail_tilemap[0] = [
                        [
                            pyboy.memory[
                                surfaces.ITEM_TILEMAP_BASE + row * 32 + column
                            ]
                            for column in range(20)
                        ]
                        for row in range(18)
                    ]
                    detail_window_registers[0] = {
                        "wx": pyboy.memory[0xFF4B],
                        "wy": pyboy.memory[0xFF4A],
                    }
                    pyboy.memory[0xFF4F] = old_vbk & 1

            self.assertEqual(19, len(events))
            inhibited = expected["action_popup"]["variants"]["inhibited"]
            detail = expected["detail_screen"]
            expected_surfaces = (
                expected["observed_surfaces"]
                + expected["category_matrix"]["rows"]
                + inhibited["observed_surfaces"]
                + [inhibited["numeric_surface"]]
                + [detail["heading_surface"]]
            )
            for item in expected_surfaces:
                if "raw" in item:
                    raw = bytes.fromhex(item["raw"]) + b"\xFF"
                else:
                    raw = codec.encode_source(item["source"]) + b"\xFF"
                matches = [
                    event
                    for event in events
                    if event["raw"] == raw
                    and event["start_pen"] == item["start_pen"]
                    and event["mode"] == item["observed_mode"]
                    and event["frame"] == item["observed_frame"]
                ]
                with self.subTest(surface=item["name"]):
                    self.assertEqual(1, len(matches))

            money = expected["money"]
            self.assertEqual(
                1,
                len(
                    [
                        event
                        for event in events
                        if event["raw"] == bytes.fromhex(money["formatted"])
                        and event["start_pen"] == money["start_pen"]
                        and event["mode"] == money["mode"]
                        and event["frame"] == money["observed_frame"]
                    ]
                ),
            )
            self.assertEqual(expected["visible_tilemap"]["rows"], tilemap[0])
            action_window = expected["action_popup"]["window"]
            self.assertEqual(action_window["rows"], action_tilemap[0])
            self.assertEqual(
                {
                    "lcdc": action_window["lcdc"],
                    "wx": action_window["registers"]["wx"],
                    "wy": action_window["registers"]["wy"],
                },
                action_registers[0],
            )
            for field in detail["numeric_fields"]:
                matches = [
                    event
                    for event in events
                    if event["raw"] == bytes.fromhex(field["formatted"])
                    and event["start_pen"] == field["start_pen"]
                    and event["mode"] == field["observed_mode"]
                    and event["frame"] == field["observed_frame"]
                ]
                with self.subTest(detail_numeric=field["name"]):
                    self.assertEqual(1, len(matches))

            source_record = detail["body_source"]["record"]
            bank_text, pointer_text = source_record.split(":$")
            self.assertEqual(
                1,
                len(
                    [
                        event
                        for event in source_events
                        if event == {
                            "bank": int(bank_text),
                            "pointer": int(pointer_text, 16),
                            "mode": detail["body_source"]["observed_mode"],
                            "frame": detail["body_source"]["observed_frame"],
                        }
                    ]
                ),
            )
            self.assertEqual(detail["visible_tilemap"]["rows"], detail_tilemap[0])
            self.assertEqual(
                detail["window_hidden"]["registers"], detail_window_registers[0]
            )
        finally:
            pyboy.stop(save=False)

        # The same seeded club has a five-command ordinary route.  Only the
        # global progress gate changes; the item object and its two masks do
        # not, making this a narrow proof of the constructor's gated branch.
        pyboy = self.PyBoy(str(self.path), window="null")
        pyboy.set_emulation_speed(0)
        frame = [0]
        events = []
        source_events = []
        full_events = []
        action_tilemap = [None]
        equipped_action_tilemap = [None]
        equipped_object = [None]

        def at_ordinary_direct_draw(_context=None):
            if frame[0] < 200:
                return
            pointer = (pyboy.register_file.D << 8) | pyboy.register_file.E
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[(pointer + offset) & 0xFFFF]
                raw.append(value)
                if value == 0xFF:
                    break
            events.append(
                {
                    "raw": bytes(raw),
                    "start_pen": [pyboy.memory[0xC4D6], pyboy.memory[0xC4D7]],
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        def at_equipment_source_init(_context=None):
            if frame[0] < 300:
                return
            bank, pointer = capture_dialogue.source_location(pyboy)
            source_events.append(
                {
                    "bank": bank,
                    "pointer": pointer,
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        def at_equipment_full_draw(_context=None):
            if frame[0] < 300:
                return
            raw = bytearray()
            for offset in range(0x100):
                value = pyboy.memory[0xC800 + offset]
                raw.append(value)
                if value == 0xFF:
                    break
            full_events.append(
                {
                    "raw": bytes(raw),
                    "mode": pyboy.memory[0xC4DA],
                    "frame": frame[0],
                }
            )

        def read_seeded_club_object():
            old_svbk = pyboy.memory[0xFF70]
            pyboy.memory[0xFF70] = surfaces.ITEM_OBJECT_WRAM_BANK
            object_at = (
                surfaces.ITEM_OBJECT_BASE
                + surfaces.ITEM_CATEGORY_SEEDS[0].object_index
                * surfaces.ITEM_OBJECT_SIZE
            )
            raw = bytes(
                pyboy.memory[object_at + offset]
                for offset in range(surfaces.ITEM_OBJECT_SIZE)
            )
            pyboy.memory[0xFF70] = old_svbk & 7
            return raw

        try:
            pyboy.load_state(io.BytesIO(state_bytes))
            seed_inventory(pyboy)
            self.assertEqual(
                surfaces.ITEM_ACTION_INHIBITED_GATE_VALUE,
                pyboy.memory[surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS],
            )
            pyboy.memory[surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS] &= (
                ~surfaces.ITEM_ACTION_GLOBAL_GATE_MASK & 0xFF
            )
            self.assertEqual(
                surfaces.ITEM_ACTION_ORDINARY_GATE_VALUE,
                pyboy.memory[surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS],
            )
            pyboy.hook_register(
                *surfaces.DIRECT_RENDERER, at_ordinary_direct_draw, None
            )
            pyboy.hook_register(
                *capture_dialogue.SOURCE_INIT,
                at_equipment_source_init,
                None,
            )
            pyboy.hook_register(
                *layout.FULL_RENDERER_ENTRY, at_equipment_full_draw, None
            )
            for current in range(1001):
                frame[0] = current
                if current == 0:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                if current == 100:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 200:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 300:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 650:
                    pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                if current == 750:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 850:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if current == 950:
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()
                if current == 250:
                    old_vbk = pyboy.memory[0xFF4F]
                    pyboy.memory[0xFF4F] = 0
                    action_tilemap[0] = [
                        [
                            pyboy.memory[
                                surfaces.ITEM_ACTION_WINDOW_TILEMAP_BASE
                                + row * 32
                                + column
                            ]
                            for column in range(8)
                        ]
                        for row in range(16)
                    ]
                    pyboy.memory[0xFF4F] = old_vbk & 1
                if current == 600:
                    equipped_object[0] = read_seeded_club_object()
                if current == 900:
                    old_vbk = pyboy.memory[0xFF4F]
                    pyboy.memory[0xFF4F] = 0
                    equipped_action_tilemap[0] = [
                        [
                            pyboy.memory[
                                surfaces.ITEM_ACTION_WINDOW_TILEMAP_BASE
                                + row * 32
                                + column
                            ]
                            for column in range(8)
                        ]
                        for row in range(16)
                    ]
                    pyboy.memory[0xFF4F] = old_vbk & 1

            ordinary = expected["action_popup"]["variants"]["ordinary_weapon"]
            self.assertEqual(36, len(events))
            ordinary_surfaces = ordinary["observed_surfaces"] + [
                ordinary["numeric_surface"]
            ]
            for item in ordinary_surfaces:
                raw = (
                    bytes.fromhex(item["raw"]) + b"\xFF"
                    if "raw" in item
                    else codec.encode_source(item["source"]) + b"\xFF"
                )
                matches = [
                    event
                    for event in events
                    if event["raw"] == raw
                    and event["start_pen"] == item["start_pen"]
                    and event["mode"] == item["observed_mode"]
                    and event["frame"] == item["observed_frame"]
                ]
                with self.subTest(ordinary_action=item["name"]):
                    self.assertEqual(1, len(matches))
            self.assertEqual(
                expected["action_popup"]["window"]["rows"], action_tilemap[0]
            )
            equipment = expected["equipment_cycle"]
            self.assertEqual(
                bytes.fromhex(equipment["object_state"]["after_equip"]),
                equipped_object[0],
            )
            self.assertEqual(
                bytes.fromhex(equipment["object_state"]["after_remove"]),
                read_seeded_club_object(),
            )

            equipped_row = equipment["equipped_list_surface"]
            self.assertEqual(
                1,
                len(
                    [
                        event
                        for event in events
                        if event["raw"]
                        == bytes.fromhex(equipped_row["raw"]) + b"\xFF"
                        and event["start_pen"] == equipped_row["start_pen"]
                        and event["mode"] == equipped_row["observed_mode"]
                        and event["frame"] == equipped_row["observed_frame"]
                    ]
                ),
            )
            equipped_actions = equipment["equipped_action_popup"]
            for item in equipped_actions["observed_surfaces"] + [
                equipped_actions["numeric_surface"]
            ]:
                raw = (
                    bytes.fromhex(item["raw"]) + b"\xFF"
                    if "raw" in item
                    else codec.encode_source(item["source"]) + b"\xFF"
                )
                matches = [
                    event
                    for event in events
                    if event["raw"] == raw
                    and event["start_pen"] == item["start_pen"]
                    and event["mode"] == item["observed_mode"]
                    and event["frame"] == item["observed_frame"]
                ]
                with self.subTest(equipped_action=item["name"]):
                    self.assertEqual(1, len(matches))
            self.assertEqual(
                expected["action_popup"]["window"]["rows"],
                equipped_action_tilemap[0],
            )

            for message in equipment["result_messages"]:
                bank_text, pointer_text = message["source_record"].split(":$")
                source_match = {
                    "bank": int(bank_text),
                    "pointer": int(pointer_text, 16),
                    "mode": message["source_observed_mode"],
                    "frame": message["source_observed_frame"],
                }
                with self.subTest(equipment_result=message["name"]):
                    self.assertEqual(1, source_events.count(source_match))
                    self.assertEqual(
                        1,
                        len(
                            [
                                event
                                for event in full_events
                                if event
                                == {
                                    "raw": bytes.fromhex(
                                        message["terminated_raw"]
                                    ),
                                    "mode": message["renderer_mode"],
                                    "frame": message["render_observed_frame"],
                                }
                            ]
                        ),
                    )
        finally:
            pyboy.stop(save=False)

        # Throw, Place and Discard are terminal inventory routes, so each one
        # starts from an independent copy of the same deterministic state.
        action_results = expected["action_results"]
        for outcome in action_results["outcomes"]:
            with self.subTest(action_result=outcome["name"]):
                pyboy = self.PyBoy(str(self.path), window="null")
                pyboy.set_emulation_speed(0)
                frame = [0]
                source_events = []
                full_events = []
                selection_events = []

                def at_result_source(_context=None):
                    if frame[0] < 200:
                        return
                    bank, pointer = capture_dialogue.source_location(pyboy)
                    source_events.append(
                        {
                            "bank": bank,
                            "pointer": pointer,
                            "mode": pyboy.memory[0xC4DA],
                            "frame": frame[0],
                        }
                    )

                def at_result_full(_context=None):
                    if frame[0] < 200:
                        return
                    raw = bytearray()
                    for offset in range(0x100):
                        value = pyboy.memory[0xC800 + offset]
                        raw.append(value)
                        if value == 0xFF:
                            break
                    full_events.append(
                        {
                            "raw": bytes(raw),
                            "mode": pyboy.memory[0xC4DA],
                            "frame": frame[0],
                        }
                    )

                def at_result_selection(_context=None):
                    selection_events.append(
                        {
                            "frame": frame[0],
                            "selected_slot": pyboy.memory[0xC157],
                            "resolved_commands": list(
                                pyboy.memory[0xC52A:0xC532]
                            ),
                        }
                    )

                def read_banked(bank, address, size):
                    old_svbk = pyboy.memory[0xFF70]
                    pyboy.memory[0xFF70] = bank
                    raw = bytes(
                        pyboy.memory[address + offset]
                        for offset in range(size)
                    )
                    pyboy.memory[0xFF70] = old_svbk & 7
                    return raw

                try:
                    pyboy.load_state(io.BytesIO(state_bytes))
                    seed_inventory(pyboy)
                    pyboy.memory[surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS] &= (
                        ~surfaces.ITEM_ACTION_GLOBAL_GATE_MASK & 0xFF
                    )
                    state = outcome["state"]
                    self.assertEqual(
                        bytes.fromhex(state["inventory_before"]),
                        read_banked(
                            surfaces.ITEM_INVENTORY_WRAM_BANK,
                            surfaces.ITEM_INVENTORY_BASE,
                            surfaces.ITEM_INVENTORY_SLOTS,
                        ),
                    )
                    self.assertEqual(
                        bytes.fromhex(state["object_before"]),
                        read_banked(
                            state["object_wram_bank"],
                            int(state["object_address"][1:], 16),
                            surfaces.ITEM_OBJECT_SIZE,
                        ),
                    )
                    floor = state["floor_slot"]
                    self.assertEqual(
                        bytes((int(floor["before"][1:], 16),)),
                        read_banked(
                            floor["wram_bank"],
                            int(floor["address"][1:], 16),
                            1,
                        ),
                    )

                    pyboy.hook_register(
                        *capture_dialogue.SOURCE_INIT, at_result_source, None
                    )
                    pyboy.hook_register(
                        *layout.FULL_RENDERER_ENTRY, at_result_full, None
                    )
                    pyboy.hook_register(
                        *surfaces.ITEM_ACTION_SELECTION_HANDLER,
                        at_result_selection,
                        None,
                    )
                    route_inputs = {
                        item["frame"]: item["button"]
                        for item in outcome["inputs"]
                    }
                    for current in range(outcome["final_observed_frame"] + 1):
                        frame[0] = current
                        if current == 0:
                            pyboy.button("b", capture_dialogue.PRESS_FRAMES)
                        if current == 100:
                            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                        if current == 200:
                            pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                        if current in route_inputs:
                            pyboy.button(
                                route_inputs[current],
                                capture_dialogue.PRESS_FRAMES,
                            )
                        pyboy.tick()

                    first_confirm = next(
                        item["frame"]
                        for item in outcome["inputs"]
                        if item["button"] == "a"
                    )
                    self.assertEqual(
                        [
                            {
                                "frame": first_confirm,
                                "selected_slot": outcome[
                                    "selected_compacted_slot"
                                ],
                                "resolved_commands": outcome[
                                    "resolved_commands"
                                ],
                            }
                        ],
                        selection_events,
                    )
                    bank_text, pointer_text = outcome["source_record"].split(
                        ":$"
                    )
                    self.assertEqual(
                        1,
                        source_events.count(
                            {
                                "bank": int(bank_text),
                                "pointer": int(pointer_text, 16),
                                "mode": outcome["source_observed_mode"],
                                "frame": outcome["source_observed_frame"],
                            }
                        ),
                    )
                    self.assertEqual(
                        1,
                        full_events.count(
                            {
                                "raw": bytes.fromhex(
                                    outcome["terminated_raw"]
                                ),
                                "mode": outcome["renderer_mode"],
                                "frame": outcome["render_observed_frame"],
                            }
                        ),
                    )
                    self.assertEqual(
                        bytes.fromhex(state["inventory_after"]),
                        read_banked(
                            surfaces.ITEM_INVENTORY_WRAM_BANK,
                            surfaces.ITEM_INVENTORY_BASE,
                            surfaces.ITEM_INVENTORY_SLOTS,
                        ),
                    )
                    self.assertEqual(
                        bytes.fromhex(state["object_after"]),
                        read_banked(
                            state["object_wram_bank"],
                            int(state["object_address"][1:], 16),
                            surfaces.ITEM_OBJECT_SIZE,
                        ),
                    )
                    self.assertEqual(
                        bytes((int(floor["after"][1:], 16),)),
                        read_banked(
                            floor["wram_bank"],
                            int(floor["address"][1:], 16),
                            1,
                        ),
                    )

                    if outcome["name"] == "item_discard_result":
                        prompt = action_results["discard_confirmation"]
                        bank_text, pointer_text = prompt["record"].split(":$")
                        self.assertEqual(
                            1,
                            source_events.count(
                                {
                                    "bank": int(bank_text),
                                    "pointer": int(pointer_text, 16),
                                    "mode": prompt["renderer_mode"],
                                    "frame": prompt["source_observed_frame"],
                                }
                            ),
                        )
                        self.assertEqual(
                            1,
                            full_events.count(
                                {
                                    "raw": bytes.fromhex(
                                        prompt["terminated_raw"]
                                    ),
                                    "mode": prompt["renderer_mode"],
                                    "frame": prompt[
                                        "render_observed_frame"
                                    ],
                                }
                            ),
                        )
                finally:
                    pyboy.stop(save=False)

        # Twelve additional routes exercise behavior that the complete club
        # matrix cannot prove: the other equipment families, each distinct
        # primary verb, jar branches, and the blank-scroll graphical keyboard.
        representatives = expected["representative_item_routes"]

        def read_route_banked(target, bank, address, size):
            old_svbk = target.memory[0xFF70]
            target.memory[0xFF70] = bank
            raw = bytes(
                target.memory[address + offset] for offset in range(size)
            )
            target.memory[0xFF70] = old_svbk & 7
            return raw

        def run_representative_route(route, event_floor=0):
            route_pyboy = self.PyBoy(str(self.path), window="null")
            route_pyboy.set_emulation_speed(0)
            route_frame = [0]
            source_events = []
            full_events = []
            direct_events = []
            selection_events = []
            equipped_snapshot = [None]
            equipped_commands = [None]

            def at_route_source(_context=None):
                if route_frame[0] < event_floor:
                    return
                bank, pointer = capture_dialogue.source_location(route_pyboy)
                source_events.append(
                    {
                        "bank": bank,
                        "pointer": pointer,
                        "mode": route_pyboy.memory[0xC4DA],
                        "frame": route_frame[0],
                    }
                )

            def at_route_full(_context=None):
                if route_frame[0] < event_floor:
                    return
                raw = bytearray()
                for offset in range(0x200):
                    value = route_pyboy.memory[0xC800 + offset]
                    raw.append(value)
                    if value == 0xFF:
                        break
                full_events.append(
                    {
                        "raw": bytes(raw),
                        "mode": route_pyboy.memory[0xC4DA],
                        "frame": route_frame[0],
                    }
                )

            def at_route_direct(_context=None):
                if route_frame[0] < event_floor:
                    return
                pointer = (
                    route_pyboy.register_file.D << 8
                ) | route_pyboy.register_file.E
                raw = bytearray()
                for offset in range(0x100):
                    value = route_pyboy.memory[(pointer + offset) & 0xFFFF]
                    if value == 0xFF:
                        break
                    raw.append(value)
                direct_events.append(
                    {
                        "raw": bytes(raw),
                        "start_pen": [
                            route_pyboy.memory[0xC4D6],
                            route_pyboy.memory[0xC4D7],
                        ],
                        "mode": route_pyboy.memory[0xC4DA],
                        "frame": route_frame[0],
                    }
                )

            def at_route_selection(_context=None):
                selection_events.append(
                    {
                        "frame": route_frame[0],
                        "selected_slot": route_pyboy.memory[0xC157],
                        "resolved_commands": list(
                            route_pyboy.memory[0xC52A:0xC532]
                        ),
                    }
                )

            try:
                route_pyboy.load_state(io.BytesIO(state_bytes))
                seed_inventory(route_pyboy)
                route_pyboy.memory[
                    surfaces.ITEM_ACTION_GLOBAL_GATE_ADDRESS
                ] &= ~surfaces.ITEM_ACTION_GLOBAL_GATE_MASK & 0xFF

                state_contract = route.get("state", route.get("object_state"))
                object_bank = state_contract.get(
                    "object_wram_bank", state_contract.get("wram_bank")
                )
                object_address_text = state_contract.get(
                    "object_address", state_contract.get("address")
                )
                object_address = int(
                    object_address_text[1:], 16
                )
                object_before_key = (
                    "object_before"
                    if "object_before" in state_contract
                    else "before_equip"
                )
                object_before = bytes.fromhex(
                    state_contract[object_before_key]
                )
                old_svbk = route_pyboy.memory[0xFF70]
                route_pyboy.memory[0xFF70] = object_bank
                for offset, value in enumerate(object_before):
                    route_pyboy.memory[object_address + offset] = value
                route_pyboy.memory[0xFF70] = old_svbk & 7

                route_pyboy.hook_register(
                    *capture_dialogue.SOURCE_INIT, at_route_source, None
                )
                route_pyboy.hook_register(
                    *layout.FULL_RENDERER_ENTRY, at_route_full, None
                )
                route_pyboy.hook_register(
                    *surfaces.DIRECT_RENDERER, at_route_direct, None
                )
                route_pyboy.hook_register(
                    *surfaces.ITEM_ACTION_SELECTION_HANDLER,
                    at_route_selection,
                    None,
                )

                inputs = {
                    item["frame"]: item["button"] for item in route["inputs"]
                }
                reopen_frames = [
                    item["frame"]
                    for item in route["inputs"]
                    if item["button"] == "b" and item["frame"] > 0
                ]
                equipped_capture_frame = (
                    reopen_frames[0] - 50 if reopen_frames else None
                )
                popup_capture_frame = None
                if "equipped_popup" in route:
                    popup_capture_frame = route["equipped_popup"][
                        "observed_frame"
                    ]

                for current in range(route["final_observed_frame"] + 1):
                    route_frame[0] = current
                    if current in inputs:
                        route_pyboy.button(
                            inputs[current], capture_dialogue.PRESS_FRAMES
                        )
                    route_pyboy.tick()
                    if current == equipped_capture_frame:
                        equipped_snapshot[0] = read_route_banked(
                            route_pyboy,
                            object_bank,
                            object_address,
                            surfaces.ITEM_OBJECT_SIZE,
                        )
                    if current == popup_capture_frame:
                        equipped_commands[0] = list(
                            route_pyboy.memory[0xC52A:0xC532]
                        )

                keyboard_map = None
                keyboard_registers = None
                if route.get("keyboard_screen") is not None:
                    old_vbk = route_pyboy.memory[0xFF4F]
                    route_pyboy.memory[0xFF4F] = 0
                    keyboard_map = [
                        [
                            route_pyboy.memory[0x9800 + row * 32 + column]
                            for column in range(20)
                        ]
                        for row in range(18)
                    ]
                    route_pyboy.memory[0xFF4F] = old_vbk & 1
                    keyboard_registers = {
                        "lcdc": "$%02X" % route_pyboy.memory[0xFF40],
                        "wx": route_pyboy.memory[0xFF4B],
                        "wy": route_pyboy.memory[0xFF4A],
                    }

                return {
                    "source": source_events,
                    "full": full_events,
                    "direct": direct_events,
                    "selection": selection_events,
                    "equipped_object": equipped_snapshot[0],
                    "equipped_commands": equipped_commands[0],
                    "inventory": read_route_banked(
                        route_pyboy,
                        surfaces.ITEM_INVENTORY_WRAM_BANK,
                        surfaces.ITEM_INVENTORY_BASE,
                        surfaces.ITEM_INVENTORY_SLOTS,
                    ),
                    "object": read_route_banked(
                        route_pyboy,
                        object_bank,
                        object_address,
                        surfaces.ITEM_OBJECT_SIZE,
                    ),
                    "keyboard_map": keyboard_map,
                    "keyboard_registers": keyboard_registers,
                }
            finally:
                route_pyboy.stop(save=False)

        def assert_route_messages(route, observed):
            for message in route["messages"]:
                bank_text, pointer_text = message["source_record"].split(":$")
                with self.subTest(
                    representative=route["name"],
                    message=message["source_record"],
                ):
                    self.assertEqual(
                        1,
                        observed["source"].count(
                            {
                                "bank": int(bank_text),
                                "pointer": int(pointer_text, 16),
                                "mode": message["source_observed_mode"],
                                "frame": message["source_observed_frame"],
                            }
                        ),
                    )
                    self.assertEqual(
                        1,
                        observed["full"].count(
                            {
                                "raw": bytes.fromhex(
                                    message["terminated_raw"]
                                ),
                                "mode": message["renderer_mode"],
                                "frame": message["render_observed_frame"],
                            }
                        ),
                    )

        for route in representatives["equipment_families"]:
            with self.subTest(representative=route["name"]):
                first_equip_input = next(
                    item["frame"]
                    for item in route["inputs"]
                    if item["button"] == "a"
                    and item["frame"] > 200 + 50 * route["row"]
                )
                observed = run_representative_route(
                    route, event_floor=first_equip_input
                )
                self.assertEqual(
                    bytes.fromhex(route["object_state"]["after_equip"]),
                    observed["equipped_object"],
                )
                self.assertEqual(
                    route["equipped_popup"]["enabled_indices"]
                    + [0] * (8 - len(route["equipped_popup"]["enabled_indices"])),
                    observed["equipped_commands"],
                )
                self.assertEqual(
                    bytes.fromhex(route["object_state"]["after_remove"]),
                    observed["object"],
                )
                marker = route["equipped_marker"]
                self.assertEqual(
                    1,
                    observed["direct"].count(
                        {
                            "raw": bytes.fromhex(marker["raw"]),
                            "start_pen": marker["start_pen"],
                            "mode": marker["observed_mode"],
                            "frame": marker["observed_frame"],
                        }
                    ),
                )
                assert_route_messages(
                    {"name": route["name"], "messages": route["result_messages"]},
                    observed,
                )

        for family_name in ("primary_actions", "container_and_writing"):
            for route in representatives[family_name]:
                with self.subTest(representative=route["name"]):
                    popup_frame = 200 + 50 * route["row"]
                    action_frame = next(
                        item["frame"]
                        for item in route["inputs"]
                        if item["button"] == "a"
                        and item["frame"] > popup_frame
                    )
                    observed = run_representative_route(
                        route, event_floor=action_frame
                    )
                    self.assertEqual(
                        [
                            {
                                "frame": action_frame,
                                "selected_slot": route["selected_compacted_slot"],
                                "resolved_commands": route["resolved_commands"],
                            }
                        ],
                        observed["selection"],
                    )
                    assert_route_messages(route, observed)
                    for direct_surface in route.get("direct_surfaces", ()):
                        expected_raw = (
                            bytes.fromhex(direct_surface["raw"])
                            if "raw" in direct_surface
                            else codec.encode_source(direct_surface["source"])
                        )
                        self.assertEqual(
                            1,
                            observed["direct"].count(
                                {
                                    "raw": expected_raw,
                                    "start_pen": direct_surface["start_pen"],
                                    "mode": direct_surface["observed_mode"],
                                    "frame": direct_surface["observed_frame"],
                                }
                            ),
                        )
                    target_selector = route.get("target_selector")
                    if target_selector is not None:
                        self.assertEqual(
                            1,
                            observed["direct"].count(
                                {
                                    "raw": codec.encode_source(
                                        target_selector["source"]
                                    ),
                                    "start_pen": target_selector["start_pen"],
                                    "mode": target_selector["observed_mode"],
                                    "frame": target_selector["observed_frame"],
                                }
                            ),
                        )

                    state_contract = route["state"]
                    expected_inventory = state_contract.get(
                        "inventory_after", state_contract.get("inventory")
                    )
                    self.assertEqual(
                        bytes.fromhex(expected_inventory), observed["inventory"]
                    )
                    self.assertEqual(
                        bytes.fromhex(state_contract["object_after"]),
                        observed["object"],
                    )

                    keyboard = route.get("keyboard_screen")
                    if keyboard is not None:
                        self.assertEqual([], observed["source"])
                        self.assertEqual([], observed["full"])
                        self.assertEqual([], observed["direct"])
                        self.assertEqual(
                            keyboard["rows"], observed["keyboard_map"]
                        )
                        self.assertEqual(
                            {
                                "lcdc": keyboard["lcdc"],
                                **keyboard["registers"],
                            },
                            observed["keyboard_registers"],
                        )


if __name__ == "__main__":
    unittest.main()
