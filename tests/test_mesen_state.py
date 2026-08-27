from pathlib import Path
import sys
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mesen_state


def _field(name, value):
    return name.encode("ascii") + b"\0" + len(value).to_bytes(4, "little") + value


class MesenStateTests(unittest.TestCase):
    def test_preview_member_is_skipped_and_named_fields_are_parsed(self):
        payload = _field("cpu.pc", b"\x34\x12") + _field(
            "cartRam", b"\xA5" * 0x2000
        )
        archive = b"MSS\x01" + zlib.compress(b"preview") + b"metadata" + zlib.compress(
            payload
        )
        self.assertEqual(payload, mesen_state.state_payload(archive))
        self.assertEqual(
            {"cpu.pc": b"\x34\x12", "cartRam": b"\xA5" * 0x2000},
            mesen_state.parse_fields(payload),
        )

    def test_truncated_and_duplicate_fields_are_rejected(self):
        with self.assertRaisesRegex(mesen_state.MesenStateError, "truncated payload"):
            mesen_state.parse_fields(b"cpu.pc\0\x04\0\0\0\x12")
        duplicate = _field("cpu.pc", b"\0\0") * 2
        with self.assertRaisesRegex(mesen_state.MesenStateError, "duplicate field"):
            mesen_state.parse_fields(duplicate)

    def test_supplied_mamel_state_contains_four_sram_banks(self):
        path = ROOT / "SaveStates" / "Mamel.mss"
        if not path.exists():
            raise unittest.SkipTest("Mamel Mesen state is not present")
        ram = mesen_state.cart_ram(path)
        self.assertEqual(0x8000, len(ram))
        self.assertEqual(b"FGB20", ram[11:16])


if __name__ == "__main__":
    unittest.main()
