import csv
from hashlib import sha1
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import dialogue_page_marker_audit


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"


class DialoguePageMarkerAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ROM_NAME
        if not cls.path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = cls.path.read_bytes()
        if sha1(cls.rom).hexdigest() != capture_dialogue.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.audit = dialogue_page_marker_audit.audit(
            cls.rom, ROOT / "script" / "en"
        )

    def test_production_catalog_has_no_detached_page_markers(self):
        self.assertEqual((), self.audit.candidates)
        self.assertEqual({}, self.audit.proposed_overrides)

    def test_every_proposal_removes_detached_markers_without_new_overflow(self):
        self.assertEqual((), self.audit.proposal_problems)

    def test_approved_pacing_wording_is_frozen_in_the_authoritative_editor(self):
        with (ROOT / "script" / "editing" / "prose.tsv").open(
            encoding="ascii", newline=""
        ) as handle:
            prose = {
                row["id"]: row["english"]
                for row in csv.DictReader(handle, delimiter="\t")
            }
        for record_id, (before, after) in (
            dialogue_page_marker_audit.PACING_SHORTENINGS.items()
        ):
            with self.subTest(record_id=record_id):
                self.assertNotIn(before, prose[record_id])
                self.assertIn(after, prose[record_id])


if __name__ == "__main__":
    unittest.main()
