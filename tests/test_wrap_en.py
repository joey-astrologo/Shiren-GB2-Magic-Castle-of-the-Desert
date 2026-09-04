from hashlib import sha1
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import english
import english_font
import extract
import layout
import organize
import overlays
import runtime_widths
import translations
import wrap_en


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "prose_wrap.json").read_text(
        encoding="utf-8"
    )
)
WRAP_ID = "195:$573F"
WRAP_DRAFT = "Koppa: We should get out of here, <name>!<page><box>"
WRAP_OUTPUT = "Koppa: We should get<br>out of here, <name>!<page><box>"
FRESH_BOX_ID = "195:$64DD"
FRESH_BOX_DRAFT = (
    "Pekeji: This is it.<br>No doubt about it.<page><box>"
    "Pekeji: This is where the<br>treasure is, Bro.<page><box>"
)


class OriginalRomProseWrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.eligible = wrap_en.prose_rows(cls.result)
        cls.by_id = {record.id: record for record in cls.result["records"]}
        cls.font_rom = english_font.install(cls.rom)
        translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )
        cls.runtime_contract = runtime_widths.analyze(
            cls.font_rom, cls.result, translated
        ).contract

    @staticmethod
    def _file_sha1(path):
        return sha1(Path(path).read_bytes()).hexdigest()

    def test_source_free_catalog_and_contract_are_frozen(self):
        drafts = wrap_en.read_draft(
            ROOT / "script" / "drafts" / "prose.tsv", self.eligible
        )
        state = wrap_en.load_state(
            ROOT / "script" / "drafts" / "prose.generated.json",
            self.result,
            self.eligible,
        )
        self.assertEqual(
            FIXTURE,
            wrap_en.contract_summary(self.result, self.eligible, drafts, state),
        )
        raw = (ROOT / "script" / "drafts" / "prose.tsv").read_bytes()
        self.assertTrue(raw.isascii())
        self.assertNotIn("japanese", raw.decode("ascii").splitlines()[0])

    def test_initializer_is_deterministic_and_preserves_drafts(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prose.tsv"
            rows = wrap_en.refresh_draft(path, self.eligible)
            wanted = rows[WRAP_ID]
            wrap_en.write_draft(
                path,
                self.eligible,
                {
                    WRAP_ID: wrap_en.DraftRow(
                        WRAP_ID, wanted.sections, WRAP_DRAFT
                    )
                },
            )
            first = self._file_sha1(path)
            refreshed = wrap_en.refresh_draft(path, self.eligible)
            self.assertEqual(WRAP_DRAFT, refreshed[WRAP_ID].draft)
            self.assertEqual(first, self._file_sha1(path))

    def test_balanced_wrap_uses_both_native_width_models(self):
        wrapped = wrap_en.wrap_record(
            self.font_rom, self.by_id[WRAP_ID], WRAP_DRAFT
        )
        self.assertEqual(WRAP_OUTPUT, wrapped)
        measured = layout.source_layout(
            self.font_rom,
            english.encode_source(wrapped),
            mode=0x02,
            runtime_contract=layout.english_runtime_width_contract(),
        )
        self.assertTrue(measured.safe)
        self.assertLessEqual(
            max(line.composer_pixels for line in measured.lines), 143
        )
        self.assertLessEqual(
            max(line.renderer_pixels for line in measured.lines), 144
        )

    def test_story_boundaries_runtime_tokens_and_effects_are_not_guessable(self):
        record = self.by_id[WRAP_ID]
        with self.assertRaisesRegex(wrap_en.WrapError, "boundary"):
            wrap_en.wrap_record(
                self.font_rom,
                record,
                "Koppa: Run, <name>!<box>",
            )
        with self.assertRaisesRegex(wrap_en.WrapError, "runtime substitutions"):
            wrap_en.wrap_record(
                self.font_rom,
                record,
                "Koppa: Run!<page><box>",
            )

        effect = self.by_id["195:$560F"]
        encoded = english.encode_source("Wait...<delay:1E>")
        wrap_en.validate_control_contract(
            effect, "Wait...<delay:1E>", encoded
        )
        with self.assertRaisesRegex(wrap_en.WrapError, "effect multiset"):
            wrap_en.validate_control_contract(
                effect, "Wait...", english.encode_source("Wait...")
            )

    def test_unresolved_f6_runtime_width_fails_closed(self):
        record = self.by_id["205:$6905"]
        draft = (
            "<number:19:C5> was found.<page><br>It is a sturdy wooden weapon."
            "<page><box>Open the menu."
        )
        with self.assertRaisesRegex(wrap_en.WrapError, "runtime width maxima"):
            wrap_en.wrap_record(self.font_rom, record, draft)

    def test_required_post_page_break_and_tutorial_balance_are_enforced(self):
        record = self.by_id["205:$6B40"]
        missing_break = (
            "Got <number:19:C5>.<page>Consume it to restore a little HP."
            "<page><box>Press B to open the menu, then choose "
            "Items to view descriptions."
        )
        with self.assertRaisesRegex(wrap_en.WrapError, "required post-<page> <br>"):
            wrap_en.wrap_record(
                self.font_rom,
                record,
                missing_break,
                self.runtime_contract,
            )

        corrected = missing_break.replace(".<page>Consume", ".<page><br>Consume")
        wrapped = wrap_en.wrap_record(
            self.font_rom,
            record,
            corrected,
            self.runtime_contract,
        )
        self.assertEqual(
            "Got <number:19:C5>.<page><br>Consume it to<br>restore a little HP."
            "<page><box>Press B to open the<br>menu, then choose "
            "Items<br>to view descriptions.",
            wrapped,
        )
        self.assertNotIn(".<page>Consume", wrapped)

    def test_fresh_box_can_replace_a_native_post_page_line_advance(self):
        wrapped = wrap_en.wrap_record(
            self.font_rom,
            self.by_id[FRESH_BOX_ID],
            FRESH_BOX_DRAFT,
            self.runtime_contract,
        )
        self.assertEqual(FRESH_BOX_DRAFT, wrapped)
        self.assertIn(".<page><box>Pekeji:", wrapped)

        cumulative = FRESH_BOX_DRAFT.replace(
            ".<page><box>Pekeji: This is where",
            ".<page><br>Pekeji: This is where",
        )
        with self.assertRaisesRegex(wrap_en.WrapError, "physical lines"):
            wrap_en.wrap_record(
                self.font_rom,
                self.by_id[FRESH_BOX_ID],
                cumulative,
                self.runtime_contract,
            )

    def test_reported_cumulative_overflows_use_fresh_waited_boxes(self):
        drafts = wrap_en.read_draft(
            ROOT / "script" / "drafts" / "prose.tsv", self.eligible
        )
        expected = {
            "195:$5893": (2, 3, 2),
            "195:$58E9": (3, 2),
        }
        continuations = {
            "195:$5893": "<page><box>Wanda:",
            "195:$58E9": "<page><box>Mekerere:",
        }
        for record_id, counts in expected.items():
            with self.subTest(record=record_id):
                wrapped = wrap_en.wrap_record(
                    self.font_rom,
                    self.by_id[record_id],
                    drafts[record_id].draft,
                    self.runtime_contract,
                )
                self.assertIn(continuations[record_id], wrapped)
                self.assertEqual(
                    counts,
                    wrap_en.physical_box_line_counts(
                        english.encode_source(wrapped)
                    ),
                )
                self.assertLessEqual(max(counts), wrap_en.DIALOGUE_LINE_LIMIT)

    def test_page_scroll_can_preserve_an_inter_sentence_space(self):
        draft = "Pekeji: Well?<page> Tempting,<br>right?<page><box>"
        wrapped = wrap_en.wrap_record(
            self.font_rom,
            self.by_id["195:$5D43"],
            draft,
            self.runtime_contract,
        )
        self.assertEqual(draft, wrapped)

        with self.assertRaisesRegex(wrap_en.WrapError, "whitespace"):
            wrap_en.wrap_record(
                self.font_rom,
                self.by_id["195:$5D43"],
                draft.replace("<page> ", "<page>  "),
                self.runtime_contract,
            )

    def test_unmatched_japanese_speaker_quote_requires_an_english_colon(self):
        record = self.by_id[WRAP_ID]
        with self.assertRaisesRegex(wrap_en.WrapError, "English colon"):
            wrap_en.wrap_record(
                self.font_rom,
                record,
                "Koppa<speaker>Run, <name>!<page><box>",
            )

    def test_apply_synchronizes_both_catalogs_and_detects_manual_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft_path = root / "drafts" / "prose.tsv"
            state_path = root / "drafts" / "prose.generated.json"
            catalog = root / "organized"
            compact = root / "en"

            organize.write_outputs(self.result, catalog, english_by_id={})
            organized = organize.classify(self.result)
            overlays.write_outputs(self.result, compact, organized, {})
            wanted = next(
                row for row in self.eligible if row.record.id == WRAP_ID
            )
            wrap_en.write_draft(
                draft_path,
                self.eligible,
                {
                    WRAP_ID: wrap_en.DraftRow(
                        WRAP_ID, wanted.sections, WRAP_DRAFT
                    )
                },
            )
            wrap_en.write_state(
                state_path, wrap_en._base_state(self.result, self.eligible)
            )

            workspace = wrap_en.prepare_workspace(
                self.rom,
                self.result,
                draft_path,
                state_path,
                catalog,
                compact,
            )
            wrap_en.apply_workspace(
                self.result, workspace, catalog, compact, state_path
            )
            self.assertEqual(
                WRAP_OUTPUT,
                organize.read_existing_english(catalog, self.result)[WRAP_ID],
            )
            self.assertEqual(
                WRAP_OUTPUT,
                organize.read_existing_english(compact, self.result)[WRAP_ID],
            )

            rerun = wrap_en.prepare_workspace(
                self.rom,
                self.result,
                draft_path,
                state_path,
                catalog,
                compact,
            )
            self.assertEqual(workspace.state, rerun.state)

            changed = dict(rerun.english_by_id)
            changed[WRAP_ID] = "Manual edit<page><box>"
            organize.write_outputs(self.result, catalog, english_by_id=changed)
            overlays.write_outputs(self.result, compact, organized, changed)
            before = tuple(
                self._file_sha1(path)
                for path in (catalog / "prose.tsv", compact / "prose.tsv")
            )
            with self.assertRaisesRegex(wrap_en.WrapError, "outside the prose draft"):
                wrap_en.prepare_workspace(
                    self.rom,
                    self.result,
                    draft_path,
                    state_path,
                    catalog,
                    compact,
                )
            after = tuple(
                self._file_sha1(path)
                for path in (catalog / "prose.tsv", compact / "prose.tsv")
            )
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
