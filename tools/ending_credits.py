#!/usr/bin/env python3
"""Install the approved English main-ending staff credit cards.

The native ending engine loads its title and each staff card as raw row-major
2bpp tile planes into CGB VRAM bank 1 at ``$8800``. This installer replaces the
guarded title plane and 20 guarded staff-card planes. Native scrolling/fades,
palettes, timing, and the Japanese ``終`` end mark remain byte-for-byte native.
"""

import argparse
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import sys

from cartridge import fix_checksums
import ending_credits_audition


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = ending_credits_audition.DEFAULT_FONT

BANK_SIZE = 0x4000
SCREEN_LEFT = 16
PLANE_WIDTH = 128
VRAM_DESTINATION = 0x8800
MAP_BANK = 0xF0
MAP_BLANK_INSTRUCTION = 0x4067
MAP_BLANK_ORIGINAL = bytes((0x16, 0x80))  # ld d,$80
MAP_BLANK_TILE = 0xF0
MAP_BLANK_LOCALIZED = bytes((0x16, MAP_BLANK_TILE))  # ld d,$F0

PIXEL_VALUES = {
    ending_credits_audition.BLACK: 0,
    ending_credits_audition.DARK: 1,
    ending_credits_audition.MID: 2,
    ending_credits_audition.WHITE: 3,
}


class EndingCreditsError(ValueError):
    """The approved card raster or guarded native source changed."""


@dataclass(frozen=True)
class CardPlane:
    bank: int
    address: int
    byte_count: int
    screen_top: int
    original_sha256: str

    @property
    def source(self):
        return "%02X:$%04X-$%04X" % (
            self.bank,
            self.address,
            self.address + self.byte_count - 1,
        )

    @property
    def pixel_height(self):
        # One raster row contributes two bytes to each of sixteen tiles.
        return self.byte_count // (PLANE_WIDTH // 8 * 2)


# Direct source loads observed at fixed-bank routine 0:$1F3A while replaying
# ending-one.state.  The size changes with the native number of credit lines;
# SCY centers each plane at the recorded screen origin.
CARD_PLANES = (
    CardPlane(0xF0, 0x490B, 0x0800, 40, "79ff019747dc32a1c88326922b9b316f7c01b398602c5a821727b3453a944936"),
    CardPlane(0xF0, 0x510B, 0x0800, 40, "5d046a9bb72f04a4dea6b0ef12816b6e8fbf4aab127209359ca707caea2577a0"),
    CardPlane(0xF0, 0x590B, 0x0800, 40, "481258c00340cbac57c200a9872a54540e987e359f103d040eb3af87b831ade9"),
    CardPlane(0xF0, 0x610B, 0x0800, 40, "916ddeaeb24cdf0136e6ef9f253ce0e0c3501650dd29a75d8e51e62f77b92f9e"),
    CardPlane(0xF0, 0x690B, 0x0A00, 32, "ead95b66f441e4e1737c98ff449b337b5b9f3cc15514ccb825e63e67ce83aa30"),
    CardPlane(0xF0, 0x730B, 0x0800, 40, "e08f7e7da225069891e41ce72ab0d4d910a54d7dd3ac7587c1ba1c16b2380be4"),
    CardPlane(0xF1, 0x4000, 0x0800, 40, "49068297a6c08d3eba97d0b85e114d073242c847613fe89fd03d9d373e307bf6"),
    CardPlane(0xF1, 0x4800, 0x1000, 8, "713bb854b5540bed6381a4cbc7ee191faf7398358f1aac2b4fb35eec94becee5"),
    CardPlane(0xF1, 0x5800, 0x1000, 8, "dff046effee8b96802b64906d85aabc76b2347455dd045fa8dd67241c1484c38"),
    CardPlane(0xF1, 0x6800, 0x0800, 40, "0fcd90b3a960521c2d394b5051d9004063871fe3da275e14f8dd14199bba933f"),
    CardPlane(0xF1, 0x7000, 0x1000, 8, "504e078d4768a7a83ed69358b96db696798a356b64ec03f795a94e70e640e091"),
    CardPlane(0xF2, 0x4000, 0x0800, 40, "1968a548551f00c5a536f4c840c2f828dcc50a60fc172b711bbf078675a77149"),
    CardPlane(0xF2, 0x4800, 0x0800, 40, "3400ff2eaa2a11461e8c41da3f143a3d2b4f49b2756b120fa9e1e24d74d202ac"),
    CardPlane(0xF2, 0x5000, 0x0A00, 32, "560e92b531cabdbc5915fe877067ce200fc62a2faba720de4dc52fd056257daf"),
    CardPlane(0xF2, 0x5A00, 0x0800, 40, "c6d948325e73fc5ee0a3ac8263252a75ae9c5f6bab2857363c244fa9fc58a0ce"),
    CardPlane(0xF2, 0x6200, 0x0D00, 20, "b519e521ef50287c3996a308962ffa7e279934789e1d60fbc62c13acc8b290b3"),
    CardPlane(0xF2, 0x6F00, 0x0800, 40, "5d556d6f721920d17c4196a36462889cfe703ec4ad2383d0d7f8a209eda14e4c"),
    CardPlane(0xF2, 0x7700, 0x0800, 40, "66230a2baf6fa501a3e73f711645f246c19e42fd191c98ecfc0c1e93a6b8f01f"),
    CardPlane(0xF3, 0x4000, 0x0E00, 16, "a18d72b20d0b44167513561c7fb3a1ba40aa48f1d707b0dd1ee7f60497f9dc6d"),
    CardPlane(0xF3, 0x4E00, 0x0800, 40, "4e3897cddd146ae821d2a5a362c5fe52beb2bd3df515d46c6a878084e5b50c2e"),
)

TITLE_PLANE = CardPlane(
    0xF0,
    0x410B,
    0x0800,
    40,
    "f84edc2ca3785152651092694cdc4cc003ac63ef0db9350b4fd203b7add5f062",
)


def _offset(bank, address):
    if not 0x4000 <= address < 0x8000:
        raise EndingCreditsError("ending-credit source is outside ROMX")
    return bank * BANK_SIZE + address - 0x4000


def encode_card(image, plane):
    """Encode one approved screen card into its native row-major tile plane."""
    if image.size != ending_credits_audition.SCREEN_SIZE:
        raise EndingCreditsError("ending-credit card must be 160x144 pixels")
    unknown = set(image.getdata()) - set(PIXEL_VALUES)
    if unknown:
        raise EndingCreditsError("ending-credit card uses colors outside the native palette")
    if plane.byte_count % 0x100:
        raise EndingCreditsError("ending-credit plane size is not tile-row aligned")

    bottom = plane.screen_top + plane.pixel_height
    outside_ink = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if image.getpixel((x, y)) != ending_credits_audition.BLACK
        and not (
            SCREEN_LEFT <= x < SCREEN_LEFT + PLANE_WIDTH
            and plane.screen_top <= y < bottom
        )
    ]
    if outside_ink:
        raise EndingCreditsError(
            "ending-credit card has %d pixels outside its native plane"
            % len(outside_ink)
        )

    encoded = bytearray()
    for tile_y in range(plane.pixel_height // 8):
        for tile_x in range(PLANE_WIDTH // 8):
            for row in range(8):
                low = high = 0
                y = plane.screen_top + tile_y * 8 + row
                for column in range(8):
                    x = SCREEN_LEFT + tile_x * 8 + column
                    value = PIXEL_VALUES[image.getpixel((x, y))]
                    bit = 7 - column
                    low |= (value & 1) << bit
                    high |= ((value >> 1) & 1) << bit
                encoded.extend((low, high))
    if len(encoded) != plane.byte_count:
        raise AssertionError((len(encoded), plane.byte_count))
    return bytes(encoded)


@lru_cache(maxsize=None)
def _localized_planes(font_path):
    if len(CARD_PLANES) != len(ending_credits_audition.CREDITS):
        raise EndingCreditsError("ending-credit plane/card count changed")
    face = ending_credits_audition.load_font(Path(font_path))
    result = []
    for credit, plane in zip(ending_credits_audition.CREDITS, CARD_PLANES):
        image, metrics = ending_credits_audition.render_card(face, credit)
        if metrics["overflows"]:
            raise EndingCreditsError("approved ending-credit card overflows")
        result.append(encode_card(image, plane))
    return tuple(result)


def localized_planes(font_path=DEFAULT_FONT):
    """Return the 20 deterministic approved native-format tile planes."""
    return _localized_planes(str(Path(font_path).resolve()))


@lru_cache(maxsize=None)
def _localized_title_plane(font_path):
    face = ending_credits_audition.load_font(Path(font_path))
    image, metrics = ending_credits_audition.render_staff_title(face)
    if metrics["overflows"]:
        raise EndingCreditsError("approved ending-credit title overflows")
    return encode_card(image, TITLE_PLANE)


def localized_title_plane(font_path=DEFAULT_FONT):
    """Return the deterministic approved native-format staff-title plane."""
    return _localized_title_plane(str(Path(font_path).resolve()))


def card_ranges():
    """Return the 20 non-overlapping native staff-card source ranges."""
    return tuple(
        (
            _offset(plane.bank, plane.address),
            _offset(plane.bank, plane.address) + plane.byte_count,
        )
        for plane in CARD_PLANES
    )


def title_range():
    start = _offset(TITLE_PLANE.bank, TITLE_PLANE.address)
    return start, start + TITLE_PLANE.byte_count


def owned_ranges():
    """Return the map operand, title plane, and all 20 staff-card planes."""
    patch = _offset(MAP_BANK, MAP_BLANK_INSTRUCTION)
    return (
        ((patch, patch + len(MAP_BLANK_ORIGINAL)), title_range())
        + card_ranges()
    )


def install(rom, font_path=DEFAULT_FONT, checksums=True):
    """Return ``rom`` with the approved title and staff cards installed."""
    out = bytearray(rom)
    localized_title = localized_title_plane(font_path)
    localized = localized_planes(font_path)
    patch_start, patch_end = owned_ranges()[0]
    current_patch = bytes(out[patch_start:patch_end])
    if current_patch == MAP_BLANK_ORIGINAL:
        out[patch_start:patch_end] = MAP_BLANK_LOCALIZED
    elif current_patch != MAP_BLANK_LOCALIZED:
        raise EndingCreditsError("ending-credit blank-map instruction changed")

    title_start, title_end = title_range()
    current_title = bytes(out[title_start:title_end])
    current_title_sha = sha256(current_title).hexdigest()
    localized_title_sha = sha256(localized_title).hexdigest()
    if current_title_sha == TITLE_PLANE.original_sha256:
        out[title_start:title_end] = localized_title
    elif current_title_sha != localized_title_sha:
        raise EndingCreditsError(
            "ending-credit title plane %s changed unexpectedly: %s"
            % (TITLE_PLANE.source, current_title_sha)
        )

    # The map's off-plane cells use tile $F0 rather than tile $80. $F0 is
    # black in the localized title, every localized staff card, and both
    # native/localized opening-credit planes. The short end-mark load inherits
    # the same black tile from card 20.
    blank_offset = (MAP_BLANK_TILE - 0x80) * 16
    if any(localized_title[blank_offset:blank_offset + 16]):
        raise EndingCreditsError("ending-credit title blank tile is not blank")
    for plane, pixels, (start, end) in zip(CARD_PLANES, localized, card_ranges()):
        if any(pixels[blank_offset:blank_offset + 16]):
            raise EndingCreditsError("ending-credit reserved blank tile is not blank")
        current = bytes(out[start:end])
        current_sha = sha256(current).hexdigest()
        localized_sha = sha256(pixels).hexdigest()
        if current_sha == plane.original_sha256:
            out[start:end] = pixels
        elif current_sha != localized_sha:
            raise EndingCreditsError(
                "ending-credit plane %s changed unexpectedly: %s"
                % (plane.source, current_sha)
            )
    if checksums:
        fix_checksums(out)
    return bytes(out)


def summary(rom, font_path=DEFAULT_FONT):
    face = ending_credits_audition.load_font(Path(font_path))
    localized = localized_planes(font_path)
    cards = []
    for credit, plane, pixels, (start, end) in zip(
        ending_credits_audition.CREDITS,
        CARD_PLANES,
        localized,
        card_ranges(),
    ):
        native = bytes(rom[start:end])
        cards.append(
            {
                "role": credit.role,
                "names": list(credit.names),
                "source": plane.source,
                "bytes": plane.byte_count,
                "screen_top": plane.screen_top,
                "original_sha256": plane.original_sha256,
                "localized_sha256": sha256(pixels).hexdigest(),
                "source_matches": sha256(native).hexdigest() == plane.original_sha256,
            }
        )
    return {
        "title": {
            "lines": list(ending_credits_audition.STAFF_TITLE_LINES),
            "source": TITLE_PLANE.source,
            "bytes": TITLE_PLANE.byte_count,
            "screen_top": TITLE_PLANE.screen_top,
            "original_sha256": TITLE_PLANE.original_sha256,
            "localized_sha256": sha256(localized_title_plane(font_path)).hexdigest(),
        },
        "cards": cards,
        "card_count": len(cards),
        "font": face.name,
        "font_sha256": face.sha256,
        "destination": "VRAM bank 1 $8800",
        "map_blank_tile": "$%02X" % MAP_BLANK_TILE,
        "preserved": [
            "native fades, scrolling, palettes, and timing",
            "Japanese end mark",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    args = parser.parse_args(argv)
    try:
        source = args.rom.read_bytes()
        output = install(source, args.font)
        report = summary(source, args.font)
    except (OSError, EndingCreditsError) as exc:
        parser.exit(1, "error: %s\n" % exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print("cards       : %d" % report["card_count"])
    print("font        : %s" % report["font"])
    print("output      : %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
