from hashlib import sha1
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import prose_editor
import prose_scenes
import wrap_en


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "prose_editor.json").read_text(
        encoding="ascii"
    )
)


class ProseEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.rom = path.read_bytes()
        if sha1(cls.rom).hexdigest() != extract.ROM_SHA1:
            raise unittest.SkipTest("ROM hash does not match the fixture")
        cls.result = extract.extract(cls.rom)
        cls.specs = prose_scenes.read_map()
        cls.scenes = prose_scenes.build_scenes(cls.result, cls.specs)
        cls.eligible = wrap_en.prose_rows(cls.result)
        cls.drafts = wrap_en.read_draft(
            ROOT / "script" / "drafts" / "prose.tsv", cls.eligible
        )
        cls.seeded = prose_editor.expected_rows(
            cls.result, cls.scenes, cls.drafts
        )
        cls.rows = prose_editor.read_editor(
            ROOT / "script" / "editing" / "prose.tsv", cls.seeded
        )

    def test_source_free_scene_ordered_contract_is_frozen(self):
        self.assertEqual(FIXTURE, prose_editor.summary(self.scenes, self.rows))
        raw = (ROOT / "script" / "editing" / "prose.tsv").read_bytes()
        self.assertTrue(raw.isascii())
        self.assertEqual(
            "\t".join(prose_editor.FIELDS), raw.decode("ascii").splitlines()[0]
        )

    def test_rows_follow_scene_and_record_order_exactly(self):
        expected_ids = tuple(
            record_id
            for scene in self.scenes
            for record_id in scene.record_ids
        )
        self.assertEqual(expected_ids, tuple(row["id"] for row in self.rows))
        for scene_order, scene in enumerate(self.scenes, 1):
            rows = [
                row for row in self.rows
                if row["scene_id"] == scene.spec.scene_id
            ]
            self.assertEqual(
                [str(scene_order)] * len(rows),
                [row["scene_order"] for row in rows],
            )
            self.assertEqual(
                [str(index) for index in range(1, len(rows) + 1)],
                [row["record_order"] for row in rows],
            )

    def test_only_native_empty_prose_slot_uses_explicit_empty(self):
        empty_rows = [row for row in self.rows if row["english"] == prose_editor.EMPTY]
        self.assertEqual(["197:$58DA"], [row["id"] for row in empty_rows])
        records = {record.id: record for record in self.result["records"]}
        self.assertEqual(b"", records[empty_rows[0]["id"]].raw)
        converted = prose_editor.draft_rows_from_editor(
            self.result, self.eligible, self.rows
        )
        self.assertEqual("", converted["197:$58DA"].draft)

    def test_scene_metadata_and_order_cannot_be_hand_edited(self):
        rows = [dict(row) for row in self.rows]
        rows[0]["scene_title"] = "Wrong Scene"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prose.tsv"
            prose_editor.write_editor(path, rows)
            with self.assertRaisesRegex(
                prose_editor.ProseEditorError, "metadata or ordering"
            ):
                prose_editor.read_editor(path, self.seeded)

    def test_explicit_empty_is_rejected_for_nonempty_source(self):
        rows = [dict(row) for row in self.rows]
        rows[0]["english"] = prose_editor.EMPTY
        with self.assertRaisesRegex(
            prose_editor.ProseEditorError, "native record is not empty"
        ):
            prose_editor.draft_rows_from_editor(
                self.result, self.eligible, rows
            )

    def test_generated_draft_cannot_diverge_behind_the_editor(self):
        editor_hash = prose_editor.editor_sha1(self.rows)
        draft_hash = prose_editor._draft_sha1(self.eligible, self.drafts)
        state = prose_editor._base_state(
            self.result, self.scenes, editor_hash, draft_hash
        )
        prose_editor._check_ownership(state, editor_hash, draft_hash)
        with self.assertRaisesRegex(
            prose_editor.ProseEditorError, "generated draft changed"
        ):
            prose_editor._check_ownership(state, editor_hash, "0" * 40)
        with self.assertRaisesRegex(
            prose_editor.ProseEditorError, "both views changed"
        ):
            prose_editor._check_ownership(state, "1" * 40, "0" * 40)


if __name__ == "__main__":
    unittest.main()
