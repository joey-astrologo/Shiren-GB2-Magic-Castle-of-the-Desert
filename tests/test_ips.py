from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ips


class IpsPatchTests(unittest.TestCase):
    def test_patch_has_deterministic_raw_records_and_round_trips(self):
        source = bytes(16)
        target = bytearray(source)
        target[2:4] = bytes.fromhex("AABB")
        target[7] = 0xCC
        target = bytes(target)

        patch = ips.create_patch(source, target)

        self.assertEqual(
            b"PATCH"
            + bytes.fromhex("0000020002AABB")
            + bytes.fromhex("0000070001CC")
            + b"EOF",
            patch,
        )
        self.assertEqual(target, ips.apply_patch(source, patch))

    def test_patch_splits_a_changed_run_larger_than_one_ips_record(self):
        source = bytes(70_000)
        target = bytes([0xA5]) * len(source)

        patch = ips.create_patch(source, target)

        self.assertEqual(target, ips.apply_patch(source, patch))
        self.assertEqual(2, ips.record_count(patch))

    def test_patch_never_starts_a_record_at_the_reserved_eof_offset(self):
        source = bytes(ips.EOF_OFFSET + 2)
        target = bytearray(source)
        target[ips.EOF_OFFSET] = 0x7F
        target = bytes(target)

        patch = ips.create_patch(source, target)

        self.assertEqual(target, ips.apply_patch(source, patch))
        self.assertNotEqual(
            b"EOF",
            patch[len(ips.HEADER):len(ips.HEADER) + 3],
        )

    def test_release_patches_require_roms_of_the_same_size(self):
        with self.assertRaisesRegex(ips.IpsError, "same size"):
            ips.create_patch(b"original", b"longer output")

    def test_apply_supports_standard_ips_rle_records(self):
        patch = (
            b"PATCH"
            + bytes.fromhex("00000300000004AB")
            + b"EOF"
        )
        self.assertEqual(
            bytes.fromhex("000000ABABABAB00"),
            ips.apply_patch(bytes(8), patch),
        )


if __name__ == "__main__":
    unittest.main()
