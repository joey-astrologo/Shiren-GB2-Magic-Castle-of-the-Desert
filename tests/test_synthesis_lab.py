from hashlib import sha1, sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import capture_dialogue
import extract
import pyboy_fixtures
import pyboy_route


ROM_NAME = "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "synthesis_lab.json").read_text(
        encoding="utf-8"
    )
)
class SynthesisLabContractTests(unittest.TestCase):
    def test_fixture_uses_reviewed_native_objects_and_sparse_pot_cells(self):
        objects = FIXTURE["objects"]
        self.assertEqual("0101000000000000", objects["base"]["record_hex"])
        self.assertEqual("0B01000000000400", objects["donor"]["record_hex"])
        self.assertEqual("BE09050000FFFFFF", objects["pot"]["record_hex"])
        self.assertEqual(
            list(pyboy_fixtures.SYNTHESIS_POT_CELL_OFFSETS),
            objects["pot"]["cell_offsets"],
        )
        self.assertEqual(
            pyboy_fixtures.SYNTHESIS_POT_ROOT, objects["pot"]["root"]
        )


class PyBoySynthesisLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / ROM_NAME
        cls.state = ROOT / FIXTURE["pyboy_state"]["path"]
        if not cls.source.is_file() or not cls.state.is_file():
            raise unittest.SkipTest("matching ROM and Mamel state are required")
        if sha1(cls.source.read_bytes()).hexdigest() != extract.ROM_SHA1:
            raise AssertionError("source ROM SHA-1 mismatch")
        raw = cls.state.read_bytes()
        if sha1(raw).hexdigest() != FIXTURE["pyboy_state"]["sha1"]:
            raise AssertionError("synthesis-lab PyBoy state SHA-1 mismatch")
        if sha256(raw).hexdigest() != FIXTURE["pyboy_state"]["sha256"]:
            raise AssertionError("synthesis-lab PyBoy state SHA-256 mismatch")
        try:
            cls.PyBoy = capture_dialogue._pyboy_class()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        cls.temporary = tempfile.TemporaryDirectory()
        cls.localized = Path(cls.temporary.name) / "synthesis-lab.gbc"
        built = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build.py"),
                str(cls.source),
                str(ROOT / "script" / "en"),
                str(cls.localized),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if built.returncode:
            cls.temporary.cleanup()
            raise AssertionError("could not build synthesis-lab fixture:\n" + built.stdout + built.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def test_native_pot_accepts_the_base_and_consumes_the_donor(self):
        pyboy = pyboy_route.start(self.PyBoy, self.localized, self.state)
        objects = FIXTURE["objects"]
        base_record = bytes.fromhex(objects["base"]["record_hex"])
        donor_record = bytes.fromhex(objects["donor"]["record_hex"])
        pot_record = bytes.fromhex(objects["pot"]["record_hex"])
        actions = {
            120: "b", 220: "a", 450: "down", 480: "down", 520: "a",
            720: "down", 760: "a", 1020: "a", 1400: "a",
            1600: "down", 1640: "a", 1880: "a", 2320: "a",
            2500: "down", 2540: "down", 2580: "a",
        }
        try:
            base, donor, pot = pyboy_fixtures.install_synthesis_lab(
                pyboy, base_record, donor_record, pot_record
            )
            self.assertEqual(
                bytes((base, donor, pot, 0xFF)),
                pyboy_route.work_read(pyboy, pyboy_fixtures.INVENTORY, 4),
            )
            pot_base = pyboy_fixtures.OBJECTS + pot * pyboy_fixtures.OBJECT_SIZE
            for frame in range(3401):
                if frame in actions:
                    pyboy_route.press(pyboy, actions[frame])
                pyboy.tick()
                if frame == 1300:
                    self.assertEqual(
                        bytes((donor, pot, 0xFF)),
                        pyboy_route.work_read(pyboy, pyboy_fixtures.INVENTORY, 3),
                    )
                    self.assertEqual(5, pyboy_route.work_read_byte(pyboy, pot_base + 2))
                    self.assertEqual(
                        base,
                        pyboy_route.work_read_byte(
                            pyboy, pot_base + objects["pot"]["cell_offsets"][0]
                        ),
                    )
                elif frame == 2200:
                    self.assertEqual(
                        bytes((pot, 0xFF)),
                        pyboy_route.work_read(pyboy, pyboy_fixtures.INVENTORY, 2),
                    )
                    self.assertEqual(
                        bytes(8),
                        pyboy_route.work_read(
                            pyboy,
                            pyboy_fixtures.OBJECTS
                            + donor * pyboy_fixtures.OBJECT_SIZE,
                            8,
                        ),
                    )
                    self.assertEqual(4, pyboy_route.work_read_byte(pyboy, pot_base + 2))

            released = pyboy_route.work_read(
                pyboy,
                pyboy_fixtures.OBJECTS + base * pyboy_fixtures.OBJECT_SIZE,
                8,
            )
            self.assertEqual(0xFF, pyboy_route.work_read_byte(pyboy, pyboy_fixtures.INVENTORY))
            self.assertEqual(objects["base"]["item_id"], released[0])
            self.assertTrue(
                released[objects["donor"]["natural_seal_object_byte"]]
                & objects["donor"]["natural_seal_mask"]
            )
            self.assertEqual(
                bytes.fromhex(FIXTURE["native_lifecycle"]["after_break"]["released_base_record_hex"]),
                released,
            )
        finally:
            pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
