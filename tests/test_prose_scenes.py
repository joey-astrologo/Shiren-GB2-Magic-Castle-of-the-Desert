from hashlib import sha1
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import build as translation_build
import capture_dialogue
import english_font
import insert
import prose_scenes
import runtime_widths
import translations
import wrap_en


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "prose_scenes.json").read_text(
        encoding="utf-8"
    )
)
OPENING_FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "prose_opening.json").read_text(
        encoding="utf-8"
    )
)
OPENING_IDS = (
    "195:$5593",
    "195:$55CF",
    "195:$55D8",
    "195:$55F2",
    "195:$55F4",
    "195:$560F",
    "195:$562F",
    "195:$56DA",
    "195:$5705",
    "195:$5718",
    "195:$5728",
    "195:$573F",
    "195:$576D",
    "195:$5794",
    "195:$57F2",
    "195:$57F4",
    "195:$5814",
)
ILPA_REUNION_IDS = tuple(
    "195:$" + address
    for address in (
        "5848", "5877", "5893", "58E9", "595C", "5968", "5988", "59B2",
        "5A52", "5A7A", "5A9F", "5AB1", "5ACA", "5AE7", "5AF9", "5B2F",
        "5B4A", "5B63", "5B85", "5BA8", "5C2B", "5CA0", "5CC0", "5CF0",
        "5D43", "5D58", "5D7B", "5DFE", "5E0E", "5E2D", "5E49", "5E7C",
        "5EA4", "5ECC",
    )
)
ANCIENT_RUINS_ENTRY_IDS = tuple(
    "195:$" + address
    for address in (
        "5F91", "5F9C", "5FA9", "6028", "6035", "6044", "6059", "60C4",
        "60D5",
    )
)
RETURN_TO_ILPA_IDS = tuple(
    "195:$" + address
    for address in (
        "61B1", "61C1", "61D1", "6274", "6290", "631B", "635F", "6370",
    )
)
NIGHT_DEPARTURE_IDS = ("195:$640C", "195:$645A")
EVIL_GOD_STATUE_IDS = tuple(
    "195:$" + address
    for address in (
        "64A3", "64B3", "64DD", "6509", "658A", "6598", "65A8",
        "65BE", "65D2", "65E2", "65F5", "65F7", "6601", "6674",
        "6684", "66A9", "66BA", "6705", "671A", "6728", "673C",
    )
)


class OriginalRomProseSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.specs = prose_scenes.read_map()
        cls.scenes = prose_scenes.build_scenes(cls.result, cls.specs)
        cls.eligible = wrap_en.prose_rows(cls.result)
        cls.drafts = wrap_en.read_draft(
            ROOT / "script" / "drafts" / "prose.tsv", cls.eligible
        )
        cls.summary = prose_scenes.summary(
            cls.result, cls.specs, cls.scenes, cls.drafts
        )

    def test_source_free_scene_and_membership_contract_is_frozen(self):
        measured = {key: self.summary[key] for key in FIXTURE}
        self.assertEqual(FIXTURE, measured)
        raw = (ROOT / "script" / "drafts" / "prose_scenes.tsv").read_bytes()
        self.assertTrue(raw.isascii())
        self.assertEqual(
            "scene_id\tgroups\tphase\ttitle", raw.decode("ascii").splitlines()[0]
        )

    def test_opening_arc_is_exact_complete_and_in_narrative_order(self):
        opening_scenes = [
            scene
            for scene in self.scenes
            if any(group in prose_scenes.OPENING_GROUPS for group in scene.spec.groups)
        ]
        self.assertEqual(OPENING_IDS, tuple(
            record_id for scene in opening_scenes for record_id in scene.record_ids
        ))
        self.assertTrue(all(self.drafts[record_id].draft for record_id in OPENING_IDS))
        self.assertEqual(17, self.summary["opening_batch"]["translated_records"])

    def test_ilpa_rumors_and_reunion_are_exact_complete_and_in_order(self):
        batch_scenes = [
            scene
            for scene in self.scenes
            if any(
                group in prose_scenes.ILPA_REUNION_GROUPS
                for group in scene.spec.groups
            )
        ]
        self.assertEqual(
            ILPA_REUNION_IDS,
            tuple(
                record_id
                for scene in batch_scenes
                for record_id in scene.record_ids
            ),
        )
        self.assertTrue(
            all(self.drafts[record_id].draft for record_id in ILPA_REUNION_IDS)
        )
        self.assertEqual(
            34, self.summary["ilpa_reunion_batch"]["translated_records"]
        )

    def test_ancient_ruins_entry_is_exact_complete_and_in_order(self):
        scene = next(
            scene
            for scene in self.scenes
            if scene.spec.scene_id == "ancient_ruins_entry"
        )
        self.assertEqual(ANCIENT_RUINS_ENTRY_IDS, scene.record_ids)
        self.assertTrue(
            all(
                self.drafts[record_id].draft
                for record_id in ANCIENT_RUINS_ENTRY_IDS
            )
        )

    def test_return_to_ilpa_is_exact_complete_and_in_order(self):
        scene = next(
            scene
            for scene in self.scenes
            if scene.spec.scene_id == "return_to_ilpa"
        )
        self.assertEqual(RETURN_TO_ILPA_IDS, scene.record_ids)
        self.assertTrue(
            all(self.drafts[record_id].draft for record_id in RETURN_TO_ILPA_IDS)
        )

    def test_night_departure_is_exact_complete_and_in_order(self):
        scene = next(
            scene
            for scene in self.scenes
            if scene.spec.scene_id == "night_departure"
        )
        self.assertEqual((42, 43), scene.spec.groups)
        self.assertEqual(NIGHT_DEPARTURE_IDS, scene.record_ids)
        self.assertTrue(
            all(self.drafts[record_id].draft for record_id in NIGHT_DEPARTURE_IDS)
        )

    def test_evil_god_statue_is_exact_complete_and_in_order(self):
        scene = next(
            scene
            for scene in self.scenes
            if scene.spec.scene_id == "evil_god_statue"
        )
        self.assertEqual((44,), scene.spec.groups)
        self.assertEqual(EVIL_GOD_STATUE_IDS, scene.record_ids)
        self.assertTrue(
            all(self.drafts[record_id].draft for record_id in EVIL_GOD_STATUE_IDS)
        )

    def test_item_tutorial_and_overlapping_bad_ending_are_separate(self):
        by_id = {scene.spec.scene_id: scene for scene in self.scenes}
        self.assertEqual(25, len(by_id["first_discovery_tutorials"].record_ids))
        self.assertEqual((33,), by_id["first_discovery_tutorials"].spec.groups)
        self.assertEqual((33, 95), by_id["bad_ending"].spec.groups)
        self.assertEqual(("205:$7122", "205:$7124"), by_id["bad_ending"].record_ids)

    def test_overlapping_logical_selectors_fail_closed(self):
        source = (ROOT / "script" / "drafts" / "prose_scenes.tsv").read_text(
            encoding="ascii"
        )
        broken = source.replace(
            "first_discovery_tutorials\t33:0-24",
            "first_discovery_tutorials\t33:0-25",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prose_scenes.tsv"
            path.write_text(broken, encoding="ascii")
            specs = prose_scenes.read_map(path)
            with self.assertRaisesRegex(prose_scenes.SceneMapError, "crosses scenes"):
                prose_scenes.build_scenes(self.result, specs)


class ProductionOpeningPyBoyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        result = extract.extract(cls.rom)
        translated = translations.load_path(ROOT / "script" / "en", result["records"])
        cls.result = result
        cls.translated = translated
        runtime_contract = runtime_widths.analyze(
            english_font.install(cls.rom), result, translated
        ).contract
        cls.output, _allocation, _validation = translation_build.build_rom(
            cls.rom,
            translations.encoded_overrides(translated),
            runtime_contract=runtime_contract,
        )
        payload = translated[(195, 0x562F)].encoded
        boundary = payload.index(bytes((0xFB, 0xFC))) + 2
        cls.prefix = payload[:boundary]

    def test_completed_story_payloads_are_relocated_exactly(self):
        by_id = {record.id: record for record in self.result["records"]}
        completed_ids = (
            ILPA_REUNION_IDS
            + ANCIENT_RUINS_ENTRY_IDS
            + RETURN_TO_ILPA_IDS
            + NIGHT_DEPARTURE_IDS
            + EVIL_GOD_STATUE_IDS
        )
        for record_id in completed_ids:
            record = by_id[record_id]
            payload = self.translated[(record.bank, record.address)].encoded
            with self.subTest(record_id=record_id):
                self.assertTrue(payload)
                for reference in record.references:
                    self.assertEqual(
                        payload,
                        insert.read_source_record(
                            self.output, reference.group, reference.index
                        ),
                    )

    def test_production_opening_stages_and_renders_after_variable_typewriter_time(self):
        fixture = OPENING_FIXTURE
        self.assertEqual(fixture["prefix_bytes"], len(self.prefix))
        self.assertEqual(fixture["prefix_sha1"], sha1(self.prefix).hexdigest())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "production-opening.gbc"
            path.write_bytes(self.output)
            pyboy = self.PyBoy(str(path), window="null")
            pyboy.set_emulation_speed(0)
            try:
                capture_dialogue.run_to_dialogue(pyboy)
                waited = capture_dialogue.wait_for_dialogue(
                    pyboy, self.prefix, fixture["max_wait_frames"]
                )
                self.assertLessEqual(waited, fixture["max_wait_frames"])
                for _ in range(fixture["post_stage_ticks"]):
                    pyboy.tick()
                screen = pyboy.screen.image.convert("RGBA").tobytes()
                final_pen = pyboy.memory[0xC4D6]
            finally:
                pyboy.stop(save=False)
        self.assertEqual(fixture["final_pen"], final_pen)
        self.assertEqual(fixture["screen_rgba_sha1"], sha1(screen).hexdigest())


if __name__ == "__main__":
    unittest.main()
