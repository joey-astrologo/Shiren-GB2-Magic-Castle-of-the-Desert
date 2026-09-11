#!/usr/bin/env python3
"""Install readable menus for the retained dungeon debug event.

Exact event/record gates keep ordinary gameplay on its native path. The runtime
is identical to the accepted prototype; only build integration is different.
"""
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile

from cartridge import fix_checksums
import english
import english_font
import extract
import font

BANK = 254
START, END = 0x5000, 0x7F00
HOOK_BANK, HOOK = 5, 0x58E6
EXPECTED_HOOK = bytes.fromhex("3E12211D40CDAC09")
CONTROLLER_HASH = "73e5ed50653f2dd912302b87b2e4b7f7b5a064eb284cad65621956436a72989f"
NAVIGATION_HASH = "6f46ff3d669829955f8089cb47c9c4c0daf0ecc8e4abcc996a281049f8673337"
NATIVE_CURSORS_HASH = "db1de5cbe20eb9f99e49c7da4f83af1f2ff18d2530ff272d9507dc2c8944e75d"
CONSTRUCTOR_HASH = "de4100c50e5fd03b4825612a0e00b51d892b7922ed1703d30f166a6af5f38e21"
LABELS = ("Weapons/Shields", "Bracelets/Grass", "Scrolls/Staves", "Pots/Arrows", "Meat")
MAIN_LABELS = ("Give Item", "Set Flag", "Trash")
WEAPONS_LABELS = ("Weapon 1", "Weapon 2", "Shield 1", "Shield 2")
BRACELETS_LABELS = ("Bracelet 1", "Bracelet 2", "Grass")
SCROLLS_LABELS = ("Scroll 1", "Scroll 2", "Staff 1", "Staff 2")
POTS_LABELS = ("Pot", "Arrow")
MEAT1_LABELS = ("Next Page", "Batch 1 (20)", "Batch 2 (18)", "Batch 3 (18)", "Batch 4 (18)")
MEAT2_LABELS = ("Next Page", "Batch 5 (18)", "Batch 6 (20)", "Batch 7 (18)", "Batch 8 (18)")
MEAT3_LABELS = ("Next Page", "Batch 9 (18)", "Batch 10 (19)", "Batch 11 (18)", "Batch 12 (6)")
FLAGS_LABELS = ("Enable Mamo", "Enable Zenmaiger", "Open Furnace", "Moai Leaves")
SCRATCH_BANK, SCRATCH_START, SCRATCH_END = 5, 0xDA00, 0xDB22
# Explicit dependencies replace the prototype's whole-ROM digest restriction,
# allowing ordinary translation edits while rejecting changed native consumers.
NATIVE_DEPENDENCIES = (
    (3, 0x4AE2, 0x4AF2, "6a069c0d3d7676d0e0328da8594bc4beb158c5d7e60ffab183334905e532cf9c", "popup border"),
    (3, 0x6AA5, 0x6AB3, "d8e0b8d11d7b8ea7e8e3e2512a969adcdebb1196b9de2d00e35c1e5f7a3e8570", "popup layout"),
    (16, 0x6315, 0x6338, "e95a507bcf28108a611262528730646b48d0b0066efce4a5bd61f44ec519cbd8", "navigation graph"),
    (180, 0x4A92, 0x4BCB, "c08b705c329482d5f7f9104ba0a9cd869434ef6941d5de9928d18a3f92500c62", "debug event choices"),
)


class DebugMenuError(ValueError):
    pass


def owned_ranges():
    return ((offset(HOOK_BANK, HOOK), offset(HOOK_BANK, HOOK + 8)),
            (offset(BANK, START), offset(BANK, END)))


def offset(bank, address):
    return extract.file_offset(bank, address)


def tile_bytes(pixels):
    return bytes(value for row in pixels for value in (
        sum((color & 1) << (7 - x) for x, color in enumerate(row)),
        sum((color >> 1) << (7 - x) for x, color in enumerate(row)),
    ))


def artwork(rom, labels=LABELS, label_columns=10):
    """Pack one menu's labels and cursor into the native 48-tile pool."""
    width = label_columns * 8
    blank = tile_bytes([[1] * 8 for _ in range(8)])
    cursor = tile_bytes([[3 if 1 <= x <= min(y, 6 - y) + 1 and y < 7 else 1
                          for x in range(8)] for y in range(8)])
    tiles = [blank, cursor]
    rows = []
    for label in labels:
        pixels = [[1] * width for _ in range(8)]
        pen = 0
        for character in label:
            glyph = font.read_glyph(rom, bytes((english.ENGLISH_CODES[character],)))
            for y, row in enumerate(glyph.pixels):
                for x, color in enumerate(row):
                    if color != 1 and pen + x < width:
                        pixels[y][pen + x] = color
            pen += glyph.width
        if pen > width:
            raise DebugMenuError("debug label exceeds its %d-pixel area" % width)
        row = []
        for column in range(label_columns):
            tile = tile_bytes([line[column * 8:column * 8 + 8] for line in pixels])
            if tile not in tiles:
                tiles.append(tile)
            row.append(0x90 + tiles.index(tile))
        rows.append(row)
    if len(tiles) > 48:
        raise DebugMenuError("category artwork exceeds the native popup tile pool")
    count = len(tiles)
    tiles += [blank] * (48 - len(tiles))
    # Native palette/flip bits, with bank 0 (dungeon-only gate).
    frame = [(0x7E, 0x8F)] + [(0xC0, 0x87)] * (label_columns + 1) + [(0x7E, 0xAF)]
    for index, row in enumerate(rows):
        frame += [(0x7F, 0x8F), (0x90, 0x87)]
        frame += [(tile, 0x87) for tile in row] + [(0x7F, 0xAF)]
        if index < len(labels) - 1:
            frame += [(0x7F, 0x8F)] + [(0x90, 0x87)] * (label_columns + 1) + [(0x7F, 0xAF)]
    frame += [(0x7E, 0xCF)] + [(0xC0, 0xC7)] * (label_columns + 1) + [(0x7E, 0xEF)]
    # The native overflowing category renderer also damages its border cache.
    # Reload the original border tile explicitly; it is the pool's 49th tile.
    border = rom[offset(3, 0x4AE2):offset(3, 0x4AF2)]
    return b"".join(tiles) + border, bytes(v for cell in frame for v in cell), count


def _symbols(path):
    return {line.split()[1]: int(line.split()[0].split(":")[1], 16)
            for line in path.read_text().splitlines()
            if line and not line.startswith(";")}


def install(rom):
    rom = bytes(rom)
    if len(rom) != 0x400000:
        raise DebugMenuError("debug menus require the reviewed 4 MiB cartridge layout")
    for bank, first, last, expected, name in NATIVE_DEPENDENCIES:
        if sha256(rom[offset(bank, first):offset(bank, last)]).hexdigest() != expected:
            raise DebugMenuError("unreviewed native " + name)
    hook = offset(HOOK_BANK, HOOK)
    start, end = offset(BANK, START), offset(BANK, END)
    controller = bytearray(rom[offset(18, 0x4000):offset(18, 0x413A)])
    if sha256(controller).hexdigest() != CONTROLLER_HASH:
        raise DebugMenuError("unreviewed production popup controller")
    if rom[hook:hook + 8] != EXPECTED_HOOK:
        raise DebugMenuError("event choice entry bytes changed")
    if rom[start:end] != bytes(end - start):
        raise DebugMenuError("debug popup reservation is occupied")
    # Glyphs and advances must match one of the approved installed English fonts.
    matched = False
    for style in english_font.FONT_STYLES:
        approved = english_font.load_approved(style=style)
        matched |= all(
            font.read_glyph(rom, bytes((english.ENGLISH_CODES[c],))).pixels
            == english_font.glyph_pixels(approved.rows[c], style)
            and font.read_glyph(rom, bytes((english.ENGLISH_CODES[c],))).width
            == approved.advances[c]
            for c in set("".join(LABELS + MAIN_LABELS + WEAPONS_LABELS + BRACELETS_LABELS + SCROLLS_LABELS + POTS_LABELS + MEAT1_LABELS + MEAT2_LABELS + MEAT3_LABELS + FLAGS_LABELS))
        )
    if not matched:
        raise DebugMenuError("debug artwork requires an approved English font")
    # These are the complete local absolute references in $4000-$4139. All
    # relative branches and fixed-bank calls retain their original operands.
    for address in (0x4001, 0x4057, 0x40B6, *range(0x40C0, 0x40D2, 2)):
        i = address - 0x4000
        value = int.from_bytes(controller[i:i + 2], "little") + 0x1000
        controller[i:i + 2] = value.to_bytes(2, "little")
    tiles, frame, count = artwork(rom)
    main_tiles, main_frame, main_count = artwork(rom, MAIN_LABELS, 6)
    weapons_tiles, weapons_frame, weapons_count = artwork(rom, WEAPONS_LABELS, 5)
    bracelets_tiles, bracelets_frame, bracelets_count = artwork(rom, BRACELETS_LABELS, 7)
    scrolls_tiles, scrolls_frame, scrolls_count = artwork(rom, SCROLLS_LABELS, 5)
    pots_tiles, pots_frame, pots_count = artwork(rom, POTS_LABELS, 4)
    meat1_tiles, meat1_frame, meat1_count = artwork(rom, MEAT1_LABELS, 8)
    meat2_tiles, meat2_frame, meat2_count = artwork(rom, MEAT2_LABELS, 8)
    meat3_tiles, meat3_frame, meat3_count = artwork(rom, MEAT3_LABELS, 8)
    flags_tiles, flags_frame, flags_count = artwork(rom, FLAGS_LABELS, 10)
    navigation = bytearray(rom[offset(16, 0x5D1A):offset(16, 0x5D6D)])
    native_cursors = bytearray(rom[offset(16, 0x5E38):offset(16, 0x5E93)])
    if sha256(navigation).hexdigest() != NAVIGATION_HASH or sha256(native_cursors).hexdigest() != NATIVE_CURSORS_HASH:
        raise DebugMenuError("unreviewed native cursor navigation")
    graph_pointer = rom[offset(16, 0x5F86):offset(16, 0x5F88)]
    if graph_pointer != bytes.fromhex("1563"):
        raise DebugMenuError("native popup navigation graph moved")
    graph = rom[offset(16, 0x6315):offset(16, 0x6338)]
    constructor = bytearray(rom[offset(3, 0x69E9):offset(3, 0x6AA5)])
    if sha256(constructor).hexdigest() != CONSTRUCTOR_HASH:
        raise DebugMenuError("unreviewed native popup constructor")
    native_layout = rom[offset(3, 0x6AA5):offset(3, 0x6AB3)]
    with tempfile.TemporaryDirectory(prefix="gb2-debug-menus-") as tmp:
        tmp = Path(tmp)
        (tmp / "tiles.bin").write_bytes(tiles)
        (tmp / "frame.bin").write_bytes(frame)
        (tmp / "main-tiles.bin").write_bytes(main_tiles)
        (tmp / "main-frame.bin").write_bytes(main_frame)
        (tmp / "weapons-tiles.bin").write_bytes(weapons_tiles)
        (tmp / "weapons-frame.bin").write_bytes(weapons_frame)
        (tmp / "bracelets-tiles.bin").write_bytes(bracelets_tiles)
        (tmp / "bracelets-frame.bin").write_bytes(bracelets_frame)
        (tmp / "scrolls-tiles.bin").write_bytes(scrolls_tiles)
        (tmp / "scrolls-frame.bin").write_bytes(scrolls_frame)
        (tmp / "pots-tiles.bin").write_bytes(pots_tiles)
        (tmp / "pots-frame.bin").write_bytes(pots_frame)
        (tmp / "meat1-tiles.bin").write_bytes(meat1_tiles)
        (tmp / "meat1-frame.bin").write_bytes(meat1_frame)
        (tmp / "meat2-tiles.bin").write_bytes(meat2_tiles)
        (tmp / "meat2-frame.bin").write_bytes(meat2_frame)
        (tmp / "meat3-tiles.bin").write_bytes(meat3_tiles)
        (tmp / "meat3-frame.bin").write_bytes(meat3_frame)
        (tmp / "flags-tiles.bin").write_bytes(flags_tiles)
        (tmp / "flags-frame.bin").write_bytes(flags_frame)
        (tmp / "navigation-graph.bin").write_bytes(graph)
        (tmp / "native-layout.bin").write_bytes(native_layout)
        asm = Path(__file__).with_suffix(".asm").resolve()

        def assemble():
            (tmp / "controller.bin").write_bytes(controller)
            (tmp / "navigation.bin").write_bytes(navigation)
            (tmp / "native-cursors.bin").write_bytes(native_cursors)
            (tmp / "constructor.bin").write_bytes(constructor)
            subprocess.run(["rgbasm", "-o", "patch.o", str(asm)], cwd=tmp, check=True,
                           capture_output=True, text=True)
            subprocess.run(["rgblink", "-o", "patch.gb", "-n", "patch.sym", "patch.o"],
                           cwd=tmp, check=True, capture_output=True, text=True)
            return _symbols(tmp / "patch.sym")

        symbols = assemble()
        # Keep native text/cache/template preparation, but never expose its
        # cramped map. Private artwork is uploaded before its own map appears.
        # The only local ROM operands are these three table pointers; all
        # relative branches and fixed/far calls retain their original targets.
        for original, target in ((bytes.fromhex("21E24A"), symbols["Tiles"] + 0x300),
                                 (bytes.fromhex("21A56A"), symbols["NativeLayoutData"]),
                                 (bytes.fromhex("21AD6A"), symbols["NativeLayoutData"] + 8)):
            if constructor.count(original) != 1:
                raise DebugMenuError("unexpected native constructor table reference")
            i = constructor.index(original)
            constructor[i:i + 3] = b"\x21" + target.to_bytes(2, "little")
        map_call = bytes.fromhex("3EFE213440CDAC09")
        if constructor.count(map_call) != 1:
            raise DebugMenuError("unexpected production constructor map call")
        i = constructor.index(map_call)
        constructor[i:i + 8] = bytes(8)
        # Relocate the three type-9 graph lookups and the cursor draw calls.
        # Relative branches, input polling, wrap/repeat and sound remain native.
        for payload, origin, addresses in (
            (navigation, 0x5D1A, (0x5D33,)),
            (native_cursors, 0x5E38, (0x5E40, 0x5E6D)),
        ):
            for address in addresses:
                i = address - origin
                if payload[i:i + 9] != bytes.fromhex("FA4EC121745FCDD309"):
                    raise DebugMenuError("unexpected native navigation graph lookup")
                payload[i:i + 9] = b"\x21" + symbols["NavigationGraph"].to_bytes(2, "little") + bytes(6)
        i = 0x5D5B - 0x5D1A
        if navigation[i:i + 3] != bytes.fromhex("CD385E"):
            raise DebugMenuError("unexpected native cursor draw call")
        navigation[i:i + 3] = b"\xCD" + symbols["CacheNativeCursors"].to_bytes(2, "little")
        for address in (0x5E5D, 0x5E8A):
            i = address - 0x5E38
            if native_cursors[i:i + 8] != bytes.fromhex("3E11217F47CDAC09"):
                raise DebugMenuError("unexpected native cursor glyph wrapper")
            native_cursors[i:i + 8] = b"\xCD" + symbols["CacheGlyph"].to_bytes(2, "little") + bytes(5)
        for address, name in ((0x406A, "Constructor"), (0x4078, "CursorInit"),
                              (0x40D9, "CursorMove"), (0x4126, "Restore")):
            i = address - 0x4000
            controller[i:i + 8] = bytes((0xCD,)) + symbols[name].to_bytes(2, "little") + bytes(5)
        symbols = assemble()
        assembled = (tmp / "patch.gb").read_bytes()
        result = bytearray(rom)
        result[start:end] = assembled[start:end].ljust(end - start, b"\0")
        result[hook:hook + 8] = bytes((0x3E, BANK, 0x21)) + symbols["Gate"].to_bytes(2, "little") + bytes.fromhex("CDAC09")
    fix_checksums(result)
    return bytes(result), {"tiles_used": count, "main_tiles_used": main_count,
                           "weapons_tiles_used": weapons_count,
                           "bracelets_tiles_used": bracelets_count,
                           "scrolls_tiles_used": scrolls_count,
                           "pots_tiles_used": pots_count,
                           "meat1_tiles_used": meat1_count, "meat2_tiles_used": meat2_count, "meat3_tiles_used": meat3_count, "flags_tiles_used": flags_count, "symbols": symbols}

