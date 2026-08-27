import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract
import internal_audit
import translations


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "internal_audit.json").read_text(
        encoding="ascii"
    )
)


class InternalTextAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ROM_NAME
        if not path.exists():
            raise unittest.SkipTest("original ROM not present")
        cls.result = extract.extract(path.read_bytes())
        cls.translated = translations.load_path(
            ROOT / "script" / "en", cls.result["records"]
        )

    def test_internal_runtime_boundary_is_complete_and_frozen(self):
        self.assertEqual(
            FIXTURE,
            internal_audit.analyze(self.result, self.translated),
        )

    def test_missing_runtime_spell_fails_closed(self):
        broken = dict(self.translated)
        broken.pop((193, 0x6C4D))
        with self.assertRaisesRegex(
            internal_audit.InternalAuditError, "required internal runtime"
        ):
            internal_audit.analyze(self.result, broken)

    def test_engine_only_override_fails_closed(self):
        broken = dict(self.translated)
        translated = next(iter(broken.values()))
        broken[(192, 0x41D2)] = translated
        with self.assertRaisesRegex(
            internal_audit.InternalAuditError, "engine-only record"
        ):
            internal_audit.analyze(self.result, broken)


if __name__ == "__main__":
    unittest.main()
