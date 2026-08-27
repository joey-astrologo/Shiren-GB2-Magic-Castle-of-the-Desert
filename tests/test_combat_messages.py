from hashlib import sha1
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build as translation_build
import capture_dialogue
import codec
import combat_messages
import english
import english_font
import extract
import layout
import mesen_state
import runtime_widths
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
ROM_SHA1 = "5264f6d0c4f12c9144de1d12fddadbadd82b3e33"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "combat_messages.json").read_text(
        encoding="utf-8"
    )
)


class CombatMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("matching original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != ROM_SHA1:
            raise unittest.SkipTest("matching original ROM not present")
        cls.result = extract.extract(cls.rom)
        cls.rows = combat_messages.message_rows(cls.result)
        cls.drafts = combat_messages.read_draft(
            ROOT / "script" / "drafts" / "combat_messages.tsv", cls.rows
        )
        cls.state = combat_messages.load_state(
            ROOT / "script" / "drafts" / "combat_messages.generated.json",
            cls.result,
            cls.rows,
        )
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.font_rom = english_font.install(cls.rom)
        cls.runtime = runtime_widths.analyze(
            cls.font_rom, cls.result, cls.translated
        )
        cls.domains, cls.domain_counts = combat_messages.runtime_candidate_domains(
            cls.font_rom, cls.result, cls.translated
        )
        cls.warnings = [
            combat_messages.combination_report(
                cls.font_rom,
                row,
                cls.drafts[row.record.id].draft,
                cls.runtime,
                cls.domains,
                cls.domain_counts,
            )
            for row in cls.rows
            if cls.drafts[row.record.id].draft
        ]

    def test_source_free_group_and_family_contract_is_frozen(self):
        measured = combat_messages.contract_summary(
            self.result,
            self.rows,
            self.drafts,
            self.state,
            warnings=self.warnings,
            domain_counts=self.domain_counts,
        )
        self.assertEqual(FIXTURE, measured)
        self.assertEqual(list(range(201)), [row.index for row in self.rows])
        self.assertEqual(
            [(name, first, last) for name, first, last in combat_messages.PARTITIONS],
            [
                (row["name"], row["index_range"][0], row["index_range"][1])
                for row in FIXTURE["partitions"]
            ],
        )

    def test_reviewed_batches_are_generated_idempotently_and_have_no_unsafe_name_case(self):
        self.assertEqual(201, len(self.state["generated"]))
        self.assertEqual(list(range(201)), [row["index"] for row in self.warnings])
        self.assertEqual(741656, sum(row["runtime_value_combinations"] for row in self.warnings))
        self.assertEqual(0, sum(row["unsafe"] for row in self.warnings))
        for row in self.rows:
            draft = self.drafts[row.record.id].draft
            if not draft:
                self.assertNotIn(row.record.id, self.state["generated"])
                continue
            with self.subTest(index=row.index, record=row.record.id):
                translation = self.translated[(row.record.bank, row.record.address)]
                self.assertEqual(draft, translation.text)
                generated = self.state["generated"][row.record.id]
                self.assertEqual(
                    sha1(draft.encode("utf-8")).hexdigest(),
                    generated["draft_sha1"],
                )
                self.assertEqual(
                    sha1(translation.text.encode("utf-8")).hexdigest(),
                    generated["generated_sha1"],
                )
                _text, _encoded, measured = combat_messages.validate_draft(
                    self.font_rom, row, draft, self.runtime.contract
                )
                self.assertTrue(measured.safe)
                self.assertFalse(measured.unresolved_dynamic_offsets)

    def test_reviewed_damage_and_attack_wording_is_present(self):
        expected = {
            0: "Hit <lookup:19:C5> for <cF3><copy:01:1B:C5> damage.",
            1: "Dealt <copy:01:19:C5> damage.",
            2: "<lookup:19:C5> took <cF3><copy:01:1B:C5> damage.",
            3: "<lookup:19:C5><cF3> hit you for<cF3> <copy:01:1B:C5> damage.",
            4: "Took <copy:01:19:C5> damage.",
            5: "The staff dealt <cF3><copy:01:19:C5> damage.",
            6: "<name> collapsed.",
            7: "<lookup:19:C5><cF3> collapsed.<page>",
            8: "But it revived as<cF3> <lookup:19:C5>!",
            9: "<lookup:19:C5><cF3> beat<cF3> <lookup:1B:C5>.",
            10: "Defeated<cF3> <lookup:19:C5>.",
            11: "<lookup:19:C5><cF3> missed.",
            12: "Dodged the attack by<cF3> <lookup:19:C5>.",
            13: "A critical hit!",
            14: "A brutal hit!",
            15: "A super critical hit!",
            16: "<lookup:19:C5><cF3> reflected the attack!",
            17: "<lookup:19:C5><cF3> turned the effect<cF3> into damage!",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_reviewed_experience_and_level_wording_is_present(self):
        expected = {
            18: "Gained <copy:03:19:C5><cF3> experience points.",
            19: "<name> reached<cF3> Level <copy:01:19:C5>.",
            20: "<name> fell to<cF3> Level <copy:01:19:C5>.",
            21: "You're already strong enough.",
            22: "Your level can't go any lower.",
            23: "<lookup:19:C5><cF3> leveled up into<cF3> <lookup:1B:C5>.",
            24: "<lookup:19:C5><cF3> leveled down into<cF3> <lookup:1B:C5>.",
            25: "<lookup:19:C5><cF3> grew a little stronger.",
            26: "<lookup:19:C5><cF3> is already strong enough.",
            27: "<lookup:19:C5>'s level<cF3> can't go any lower.",
            28: "<lookup:19:C5><cF3> grew a little weaker.",
            29: "<lookup:19:C5><cF3> reached<cF3> Level <copy:01:1B:C5>.",
            30: "<lookup:19:C5><cF3> fell to<cF3> Level <copy:01:1B:C5>.",
            31: "<lookup:19:C5>'s HP<cF3> fell to one quarter.",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_reviewed_resource_and_trap_wording_is_present(self):
        expected = {
            32: "No arrows are equipped.",
            33: "You don't have any Trap Parts.",
            34: "You can't use<cF3> special abilities.",
            35: "Strength decreased by <copy:01:19:C5>.",
            36: "Fullness dropped to<cF3> <copy:01:19:C5>{F182=%}!",
            37: "Max Fullness dropped to<cF3> <copy:01:19:C5>{F182=%}!",
            38: "Fullness is now<cF3> <copy:01:19:C5>{F182=%}!",
            39: "Max Fullness is now<cF3> <copy:01:19:C5>{F182=%}!",
            40: "Stepped on<cF3> <lookup:19:C5>.",
            41: "But the trap didn't activate.",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_all_translated_trap_names_fit_the_stepped_on_message(self):
        report = next(row for row in self.warnings if row["index"] == 40)
        self.assertEqual(["trap_name"], report["f6_domains"])
        self.assertEqual(22, report["runtime_value_combinations"])
        self.assertEqual(22, report["one_line"])
        self.assertEqual(0, report["soft_wrap"])
        self.assertEqual(0, report["unsafe"])
        self.assertLessEqual(report["max_renderer_pixels"], layout.CANVAS_WIDTH_PIXELS)

    def test_reviewed_monster_ability_and_theft_wording_is_present(self):
        expected = {
            42: "<lookup:19:C5><cF3> cast Hunger!",
            43: "<lookup:19:C5><cF3> did the Twisty Dance!",
            44: "<lookup:19:C5><cF3> cast a mysterious spell!",
            45: "<lookup:19:C5><cF3> sounded the alarm!",
            46: "<lookup:19:C5>'s eye<cF3> glowed!",
            47: "<lookup:19:C5><cF3> spat rotten fluid!",
            48: "<lookup:19:C5><cF3> lunged!",
            49: "<lookup:19:C5><cF3> dodged the rock!",
            50: "<lookup:19:C5><cF3> nullified the magic!",
            51: "<lookup:19:C5><cF3> made <number:1B:C5><cF3> vanish!",
            52: "<lookup:19:C5><cF3> didn't have<cF3> what it wanted.",
            53: "<copy:02:1B:C5> Gitan<cF3> was stolen!",
            54: "Stole <cF3><copy:02:1B:C5> Gitan!",
            55: "<number:19:C5><cF3> was stolen!",
            56: "Stole <cF3><number:19:C5>!",
            57: "It stuffed<cF3> <number:19:C5><cF3> in its cheek and flung it!",
            58: "It pecked at<cF3> <number:19:C5><cF3> and digested it!",
            59: "It tried to peck, but failed.",
            60: "But nothing was stolen.",
            61: "But you can't carry<cF3> any more!",
            62: "<lookup:19:C5><cF3> began chanting!<br>",
            63: "The curses on your items<cF3> were lifted!",
            64: "<lookup:19:C5><cF3> sapped <lookup:1B:C5>'s<cF3> power and recovered!",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_theft_and_drain_messages_cover_every_runtime_name_combination(self):
        reports = {row["index"]: row for row in self.warnings}
        self.assertEqual(
            ["actor_name", "item_name"], reports[51]["f6_domains"]
        )
        self.assertEqual(295 * 347, reports[51]["runtime_value_combinations"])
        for index in (55, 56, 57, 58):
            with self.subTest(index=index):
                self.assertEqual(["item_name"], reports[index]["f6_domains"])
                self.assertEqual(347, reports[index]["runtime_value_combinations"])
                self.assertEqual(0, reports[index]["unsafe"])
        self.assertEqual(
            ["actor_name", "actor_name"], reports[64]["f6_domains"]
        )
        self.assertEqual(295 * 295, reports[64]["runtime_value_combinations"])
        self.assertEqual(0, reports[51]["unsafe"])
        self.assertEqual(0, reports[64]["unsafe"])

    def test_reviewed_actor_stat_change_wording_is_present(self):
        expected = {
            65: "<lookup:19:C5><cF3> rusted and grew weaker.",
            66: "<lookup:19:C5><cF3> was drenched.",
            67: "<lookup:19:C5>'s<cF3> attack power and<cF3> defense fell!",
            68: "<lookup:19:C5>'s<cF3> attack power fell!",
            69: "<lookup:19:C5>'s<cF3> defense fell!",
            70: "<lookup:19:C5>'s<cF3> attack power rose!",
            71: "<lookup:19:C5>'s<cF3> explosion switch<cF3> was activated!",
            72: "<lookup:19:C5>'s<cF3> attack power<br>was temporarily halved!",
            73: "<lookup:19:C5>'s<cF3> Max HP<br>was temporarily halved!",
            74: "<lookup:19:C5>'s<cF3> level<br>was temporarily halved!",
            75: "<lookup:19:C5>'s<cF3> attack power<br>was halved!",
            76: "<lookup:19:C5>'s<cF3> Max HP<cF3> was halved!",
            77: "<lookup:19:C5>'s<cF3> level<cF3> was halved!",
            78: "<lookup:19:C5>'s<cF3> attack power<cF3> returned to normal.",
            79: "<lookup:19:C5>'s<cF3> Max HP<cF3> returned to normal.",
            80: "<lookup:19:C5>'s<cF3> level<cF3> returned to normal.",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_actor_stat_changes_cover_every_runtime_actor_name(self):
        reports = {row["index"]: row for row in self.warnings}
        for index in range(65, 81):
            with self.subTest(index=index):
                report = reports[index]
                self.assertEqual(["actor_name"], report["f6_domains"])
                self.assertEqual(295, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertLessEqual(
                    report["max_renderer_pixels"], layout.CANVAS_WIDTH_PIXELS
                )

    def test_reviewed_status_wording_is_present(self):
        expected = {
            81: "<lookup:19:C5><cF3> slowed down!",
            82: "<lookup:19:C5><cF3> sped up!",
            83: "<lookup:19:C5><cF3> returned to<cF3> normal speed.",
            84: "<lookup:19:C5><cF3> became confused!",
            85: "<lookup:19:C5><cF3> is no longer confused!",
            86: "<lookup:19:C5><cF3> fell asleep...",
            87: "<lookup:19:C5><cF3> woke up!",
            88: "Too sleepy to do anything...",
            89: "<lookup:19:C5><cF3> was paralyzed!",
            90: "<lookup:19:C5><cF3> is no longer paralyzed!",
            91: "...You can't move!",
            92: "<lookup:19:C5><cF3> was blinded!",
            93: "<lookup:19:C5><cF3> can see again.",
            94: "<lookup:19:C5><cF3> became invisible!",
            95: "<lookup:19:C5><cF3> became visible again.",
            96: "<lookup:19:C5><cF3> turned into<cF3> an Onigiri!",
            97: "<lookup:19:C5><cF3> returned to normal.",
            98: "<lookup:19:C5><cF3> became inaccurate!",
            99: "<lookup:19:C5><cF3> is accurate again.",
            100: "<lookup:19:C5><cF3> became enraged!",
            101: "<lookup:19:C5><cF3> calmed down.",
            102: "<lookup:19:C5><cF3> turned to face<cF3> backward!",
            103: "<lookup:19:C5><cF3> faced forward again.",
            104: "<lookup:19:C5><cF3> was muzzled!<page>",
            105: "<lookup:19:C5>'s<cF3> special abilities<cF3> were sealed!",
            106: "Caught in a bear trap!<cF3> Can't move!",
            107: "<lookup:19:C5><cF3> can move again!",
            108: "The spell on<cF3> <lookup:19:C5><cF3> wore off.",
            109: "<lookup:19:C5>'s status<cF3> was bugged!!",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_statuses_cover_every_runtime_actor_name(self):
        reports = {row["index"]: row for row in self.warnings}
        dynamic = set(range(81, 88)) | {89, 90} | set(range(92, 106)) | set(
            range(107, 110)
        )
        for index in range(81, 110):
            with self.subTest(index=index):
                report = reports[index]
                if index in dynamic:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertLessEqual(
                    report["max_renderer_pixels"], layout.CANVAS_WIDTH_PIXELS
                )

    def test_reviewed_shop_and_alarm_wording_is_present(self):
        expected = {
            110: "Shopkeeper: Welcome!",
            111: "<box>Shopkeeper: Thank you!<page>",
            112: "<box>Shopkeeper: That's too bad.<page>",
            113: "<box>Shopkeeper: Sorry...<page><br> You don't have enough Gitan.<page>",
            114: "Shopkeeper: Thank you!",
            115: "Thief alert!<br>Thief alert!",
            116: "<box>Shopkeeper: Your total is<br> <copy:03:19:C5> Gitan.<page>",
            117: "Shopkeeper: I'll pay you<br> <copy:03:19:C5> Gitan for<br> those items.<page>",
            118: "Shopkeeper: Hurry! Hurry!<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_shop_and_alarm_messages_fit_their_three_line_dialogue_surface(self):
        reports = {row["index"]: row for row in self.warnings}
        for index in range(110, 119):
            with self.subTest(index=index):
                report = reports[index]
                self.assertEqual([], report["f6_domains"])
                self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertLessEqual(
                    report["max_renderer_pixels"], layout.CANVAS_WIDTH_PIXELS
                )

    def test_reviewed_nfuu_ability_and_training_wording_is_present(self):
        expected = {
            119: "It's <lookup:19:C5>!",
            120: "<lookup:19:C5>: <cF3> BOOM!!!",
            121: "Nfuu used the power of<br><lookup:19:C5>!",
            122: "Nfuu: Thanks for the meal, fu!",
            123: "Nfuu: I don't need that<br>meat, fu!",
            124: "Nfuu: Huh...?<br>I forgot that power, fu.",
            125: "Nfuu:<br>If you throw meat at me,<br>I'll learn its power, fu!<page>",
            126: "Nfuu: If I eat the same<br>meat twice, I'll forget<br>its power, fu!<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_nfuu_ability_and_training_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        max_renderer_pixels = {
            119: 119,
            120: 135,
            121: 108,
            122: 139,
            123: 107,
            124: 113,
            125: 117,
            126: 111,
        }
        for index in range(119, 127):
            with self.subTest(index=index):
                report = reports[index]
                if index <= 121:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_reviewed_nfuu_condition_chatter_is_present(self):
        expected = {
            127: "Nfuu: <lookup:19:C5>?<br>No match for me, fu!<page>",
            128: "Nfuu: <lookup:19:C5>?<br>I'm totally fine, fu!<page>",
            129: "Nfuu: I don't feel so<br>good, fu.<page><box>Nfuu: I think I'll recover<br>if I walk a little, fu.<page>",
            130: "Nfuu: <lookup:19:C5><br>was a tough one, fu.<page>",
            131: "Nfuu: Yelp! That hurt, fu!!<br>That <lookup:19:C5>...!<page>",
            132: "Nfuu: I'm hurting, fu...<br>Please throw me<br>an Herb, fu...<page>",
            133: "Nfuu: I... can't go on, fu...<page><br>Otogirisou... please... fu...<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_nfuu_condition_chatter_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        dynamic = {127, 128, 130, 131}
        max_renderer_pixels = {
            127: 128,
            128: 128,
            129: 120,
            130: 122,
            131: 128,
            132: 102,
            133: 116,
        }
        for index in range(127, 134):
            with self.subTest(index=index):
                report = reports[index]
                if index in dynamic:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_reviewed_mamo_condition_chatter_is_present(self):
        expected = {
            134: "Mamo:<br>You can also store items<br>by throwing them at me!<page>",
            135: "Mamo: I'm built sturdy,<br>so I'll be fine!<page>",
            136: "Mamo: I'm doing just fine.<page>",
            137: "Mamo: <lookup:19:C5><br>can't break me!<page>",
            138: "Mamo: I'm starting to<br>rattle a little...<page>",
            139: "Mamo: <lookup:19:C5><br>sure is a brute...<page>",
            140: "Mamo: <lookup:19:C5><br>really hurt me...<page>",
            141: "Mamo: I'm creaking badly now.<br>I might break soon...<page>",
            142: "Mamo: Goodbye, <name>.<br>I'm about to fall apart...<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_mamo_condition_chatter_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        dynamic = {137, 139, 140}
        max_renderer_pixels = {
            134: 116,
            135: 106,
            136: 118,
            137: 123,
            138: 99,
            139: 123,
            140: 123,
            141: 135,
            142: 122,
        }
        for index in range(134, 143):
            with self.subTest(index=index):
                report = reports[index]
                if index in dynamic:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_reviewed_oryu_condition_chatter_is_present(self):
        expected = {
            143: "Oryu: With me by your side,<br>there's nothing to fear!<page>",
            144: "Oryu: Let's give it our all!<page>",
            145: "Oryu: <lookup:19:C5>?<br>What a pushover.<page>",
            146: "Oryu: I'm fine.<br><lookup:19:C5>?<br>No problem.<page>",
            147: "Oryu: Me? I'm still<br>doing just fine.<page>",
            148: "Oryu: That one's strong!<br><lookup:19:C5>!<br><name>, be careful!<page>",
            149: "Oryu: That was rough...<br><lookup:19:C5>...<page>",
            150: "Oryu: I'm really starting<br>to struggle...<page>",
            151: "Oryu: <name>, help me...<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_oryu_condition_chatter_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        dynamic = {145, 146, 148, 149}
        max_renderer_pixels = {
            143: 126,
            144: 124,
            145: 128,
            146: 101,
            147: 88,
            148: 110,
            149: 103,
            150: 116,
            151: 123,
        }
        for index in range(143, 152):
            with self.subTest(index=index):
                report = reports[index]
                if index in dynamic:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_reviewed_pekeji_condition_chatter_is_present(self):
        expected = {
            152: "Pekeji: Being with you is fun,<br>Bro!!<page>",
            153: "Pekeji: I'll give it my all<br>to help you, Bro!<page>",
            154: "Pekeji: Watch out for<br><lookup:19:C5>, Bro!<page>",
            155: "Pekeji: <lookup:19:C5>?<br>Didn't faze me!<page>",
            156: "Pekeji: My moves feel<br>a little sluggish...<page>",
            157: "Pekeji: Really watch out for<br><lookup:19:C5>, Bro!<page>",
            158: "Pekeji: <lookup:19:C5>!<br>Ow, ow, ow...<page>",
            159: "Pekeji: I-I can't breathe...<page>",
            160: "Pekeji: Sorry... In the end,<br>I guess I was just<br>dead weight after all...<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_pekeji_condition_chatter_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        dynamic = {154, 155, 157, 158}
        max_renderer_pixels = {
            152: 138,
            153: 119,
            154: 120,
            155: 136,
            156: 99,
            157: 132,
            158: 132,
            159: 123,
            160: 123,
        }
        for index in range(152, 161):
            with self.subTest(index=index):
                report = reports[index]
                if index in dynamic:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_reviewed_robot_condition_chatter_is_present(self):
        expected = {
            161: "<lookup:19:C5>: BWOFFO!<page>",
            162: "<lookup:19:C5>: BWOFFO!<page>",
            163: "<lookup:19:C5>: BWOFFO!<br><lookup:1B:C5>... WEAK!!<page>",
            164: "<lookup:19:C5>: BWOFFO!<br>I AM STURDY. FINE.<page>",
            165: "<lookup:19:C5>: BWOFFO!<br>BWOFFO! I CAN GO ON!!<page>",
            166: "<lookup:19:C5>: BWOFFO!<br><lookup:1B:C5>... TOUGH!!<page>",
            167: "<lookup:19:C5>: BWOFFO!<br><lookup:1B:C5>...<br>BROKE ME!<page>",
            168: "<lookup:19:C5>: BWOFFO!<br>DANGER! DANGER!<page>",
            169: "<lookup:19:C5>: ...BWO...<br>...FFO...<br>G-GI... GIGIGI...<page>",
            170: "<lookup:19:C5>: ......<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_robot_condition_chatter_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        double_actor = {163, 166, 167}
        max_renderer_pixels = {
            161: 139,
            162: 139,
            163: 139,
            164: 139,
            165: 139,
            166: 139,
            167: 139,
            168: 139,
            169: 131,
            170: 113,
        }
        for index in range(161, 171):
            with self.subTest(index=index):
                report = reports[index]
                if index in double_actor:
                    self.assertEqual(
                        ["actor_name", "actor_name"], report["f6_domains"]
                    )
                    self.assertEqual(87025, report["runtime_value_combinations"])
                else:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_reviewed_actor_behavior_and_labels_are_present(self):
        expected = {
            171: "<lookup:19:C5><cF3> is watching.",
            172: "The staff's effect<br>didn't make you fall.",
            173: "Big Moai: Throwing trash<br>at me?<br>You ungrateful brat!!<page>",
            174: "Unknown",
            175: "Onigiri",
            176: "<lookup:19:C5><cF3> is sleeping soundly.",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_actor_behavior_and_label_runtime_layouts_are_exhaustive_and_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        dynamic = {171, 176}
        max_renderer_pixels = {
            171: 140,
            172: 94,
            173: 115,
            174: 37,
            175: 33,
            176: 143,
        }
        for index in range(171, 177):
            with self.subTest(index=index):
                report = reports[index]
                if index in dynamic:
                    self.assertEqual(["actor_name"], report["f6_domains"])
                    self.assertEqual(295, report["runtime_value_combinations"])
                else:
                    self.assertEqual([], report["f6_domains"])
                    self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )
        self.assertEqual((289, 6), (reports[171]["one_line"], reports[171]["soft_wrap"]))
        self.assertEqual((114, 181), (reports[176]["one_line"], reports[176]["soft_wrap"]))

    def test_reviewed_scripted_boss_and_story_wording_is_present(self):
        expected = {
            177: "Nag, nag! You think<br>that's all I can say?!<br>In my day, swords...<page>",
            178: "When eating sushi,<br>don't drop the topping<br>in soy sauce! A sailor's...<page>",
            179: "Brush your teeth<br>before bed! Even saliva<br>can affect enamel...<page>",
            180: "Treat your elders well!<br>In my day, above all,<br>there was gol...<page>",
            181: "You must eat fish!<br>All that meat will<br>make you moi...<page>",
            182: "Don't turn down the AC<br>without asking! For<br>starters, the tem...<page>",
            183: "Always keep the kettle<br>full of hot water!<br>First of all, the tem...<page>",
            184: "Put trash out on<br>the proper day!! Those<br>who disobey are mojo...<page>",
            185: "Nag-Mo? You can't<br>abbreviate everything!<br>Kids these days...<page>",
            186: "Hey! Listen when<br>someone's talking! Why<br>leave it in a place like that...<page>",
            187: "Ahem. The equation<br>here goes like this,<br>therefore...<page>",
            188: "If you insist,<br>I have no choice.<page><box>I'll show you...<page><br>my true power!!<page><box>RUMBLE RUMBLE RUMBLE!!<page>",
            189: "Like I said...<page>That's not<br>what I mean...<page>",
            190: "So...<page>that...<page>baffles me.<page><br>That...<page>also...<page>baffles me.<page>",
            191: "Something still...<page><br>doesn't quite click...<page>",
            192: "....<page>It's hot.<page>",
            193: "....<page>I'm sleepy.<page>",
            194: "Heh heh...<page>No.<page>",
            195: "Heh heh...<page>Go to sleep.<page>",
            196: "I've felt lousy<br>since yesterday.<page><br>What a drag<D6><D7><D7><D7><D7><D7><D8>!!<page>",
            197: "Take this!<br>My ultimate technique!!<page><box>HAAAAAAAAAAAA!!<page>",
            198: "Don't stay out late!<br>Those who upset their<br>parents are topporo...<page>",
            199: "At last...<page>The Evil God...<page><br>finished regenerating...<page><box><br>and reached its<br>complete form!!<page>",
            200: "Koppa: This is bad!<br>Its regeneration is<br>already well underway...<page><box>Koppa: At this rate,<br>it'll reach its<br>complete form!!<page><box>Koppa: <name>! Hurry!!<page>",
        }
        for index, text in expected.items():
            row = self.rows[index]
            with self.subTest(index=index):
                self.assertEqual(text, self.drafts[row.record.id].draft)
                self.assertEqual(
                    text,
                    self.translated[(row.record.bank, row.record.address)].text,
                )

    def test_scripted_boss_and_story_layouts_are_safe(self):
        reports = {row["index"]: row for row in self.warnings}
        max_renderer_pixels = {
            177: 100, 178: 114, 179: 108, 180: 108, 181: 85, 182: 107,
            183: 107, 184: 103, 185: 104, 186: 139, 187: 92, 188: 120,
            189: 106, 190: 103, 191: 93, 192: 47, 193: 57, 194: 54,
            195: 96, 196: 115, 197: 106, 198: 103, 199: 107, 200: 117,
        }
        for index in range(177, 201):
            with self.subTest(index=index):
                report = reports[index]
                self.assertEqual([], report["f6_domains"])
                self.assertEqual(1, report["runtime_value_combinations"])
                self.assertEqual(0, report["unsafe"])
                self.assertEqual(
                    max_renderer_pixels[index], report["max_renderer_pixels"]
                )

    def test_mamel_damage_messages_stay_on_one_line(self):
        composer, renderer = combat_messages._plain_width(
            self.font_rom, english.encode_source("Mamel")
        )
        for index in (0, 2, 3):
            row = self.rows[index]
            encoded = english.encode_source(self.drafts[row.record.id].draft)
            bounds = {}
            for token in codec.parse_source(encoded):
                if token.kind == "source_control" and token.code == 0xF6:
                    bounds[(row.record.id, token.raw)] = layout.RuntimeF6Bound(
                        "f6_actor_name", composer, renderer
                    )
            measured = layout.source_layout(
                self.font_rom,
                encoded,
                mode=combat_messages.COMBAT_MODE,
                runtime_contract=layout.english_runtime_width_contract(bounds),
                record_id=row.record.id,
                simulate_soft_wrap=True,
            )
            with self.subTest(index=index):
                self.assertEqual((), measured.soft_wraps)
                self.assertEqual(1, len(measured.lines))
                self.assertTrue(measured.safe)

    def test_semantic_page_and_japanese_speaker_quote_policy_is_enforced(self):
        with self.assertRaisesRegex(combat_messages.CombatMessageError, "page"):
            combat_messages.validate_draft(
                self.font_rom,
                self.rows[7],
                "<lookup:19:C5><cF3> collapsed.",
                self.runtime.contract,
            )
        with self.assertRaisesRegex(combat_messages.CombatMessageError, "English colon"):
            combat_messages.validate_draft(
                self.font_rom,
                self.rows[110],
                "Shopkeeper<speaker>Welcome.",
                self.runtime.contract,
            )


class LiveLocalizedCombatMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        state_path = ROOT / "SaveStates" / "Mamel.mss"
        if not cls.path.exists() or not state_path.exists():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != ROM_SHA1:
            raise unittest.SkipTest("matching original ROM not present")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        result = extract.extract(cls.rom)
        translated = translations.load_path(ROOT / "script" / "en", result["records"])
        font_rom = english_font.install(cls.rom)
        runtime = runtime_widths.analyze(font_rom, result, translated)
        output, _allocation, _validation = translation_build.build_rom(
            cls.rom,
            translations.encoded_overrides(translated),
            runtime_contract=runtime.contract,
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized_path = Path(cls.temporary.name) / "localized.gbc"
        cls.localized_path.write_bytes(output)
        cls.ram = mesen_state.cart_ram(state_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_mamel_defeat_and_experience_route_renders_short_english_lines(self):
        pyboy = self.PyBoy(
            str(self.localized_path),
            window="null",
            ram_file=io.BytesIO(self.ram),
            sound_emulated=False,
        )
        pyboy.set_emulation_speed(0)
        rendered = []

        def at_full_renderer(_context=None):
            if pyboy.frame_count < 900:
                return
            staged = bytes(pyboy.memory[0xC800:0xC900])
            try:
                end = staged.index(0xFF) + 1
            except ValueError:
                return
            rendered.append((pyboy.memory[0xC4DA], staged[:end]))

        try:
            pyboy.hook_register(*layout.FULL_RENDERER_ENTRY, at_full_renderer, None)
            for frame in range(1221):
                if frame in (120, 240, 420, 600, 780, 960, 1080):
                    pyboy.button("a", capture_dialogue.PRESS_FRAMES)
                if frame in (180, 360):
                    pyboy.button("start", capture_dialogue.PRESS_FRAMES)
                pyboy.tick()

            outgoing = [
                (mode, event)
                for mode, event in rendered
                if english.encode("Hit Mamel for") in event
            ]
            incoming = [
                (mode, event)
                for mode, event in rendered
                if english.encode("Mamel") in event
                and english.encode(" hit you for") in event
            ]
            defeat = [
                (mode, event)
                for mode, event in rendered
                if english.encode(" beat") in event
                and english.encode("Mamel.") in event
            ]
            experience = [
                (mode, event)
                for mode, event in rendered
                if english.encode("Gained ") in event
                and english.encode(" experience points.") in event
            ]
            self.assertTrue(outgoing)
            self.assertTrue(incoming)
            self.assertTrue(defeat)
            self.assertTrue(experience)
            self.assertTrue(
                all(
                    mode == combat_messages.COMBAT_MODE and 0xFD not in event
                    for mode, event in outgoing + incoming + defeat + experience
                )
            )
            self.assertNotEqual(0, pyboy.register_file.PC)
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
