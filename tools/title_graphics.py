"""Compile the approved title art into lossless CGB palette bands and sprites.

The checked-in packing recipe records a solved palette/sprite allocation. Normal
builds need Pillow, not a constraint solver or an emulator. Native moon and castle
pixels are decoded from the input cartridge, using the same layering as the
approved browser audition.
"""

from hashlib import sha256
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/graphics/GB2 Title Graphics"
RECIPE = ROOT / "assets/graphics/title_screen/packing.json"
SCENE = "2 English title static with mask/2.GB2TitleStaticExample.png"
LOGO = "2 English title static with mask/1b.GB2TitleStaticTransparent.png"
SUBTITLE = "3 English subtitle animation components/1b.GB2TitleSubtitleTransparent.png"
SHINE = "4 English subtitle precomposed 8 frames/GB2TitleExampleFrame%d.png"
KEY = (197, 0, 254)
GLINT = ((248, 240, 128), (248, 248, 248), (224, 216, 104))


class TitleScreenError(ValueError):
    """The approved artwork, native resource, or hardware allocation changed."""


def offset(bank, address):
    return bank * 0x4000 + address - 0x4000 if bank else address


def recipe():
    data = json.loads(RECIPE.read_text())
    if data["version"] != 1:
        raise TitleScreenError("unsupported title packing recipe")
    return data


def validate_sources(rom, plan):
    if len(rom) != 0x400000:
        raise TitleScreenError("title installer requires the supported 4 MiB cartridge")
    for relative, expected in plan["asset_sha256"].items():
        if sha256((ART / relative).read_bytes()).hexdigest() != expected:
            raise TitleScreenError("approved title artwork changed: " + relative)
    for resource in plan["native_resources"]:
        start = offset(resource["bank"], resource["address"])
        data = rom[start : start + resource["size"]]
        if sha256(data).hexdigest() != resource["sha256"]:
            raise TitleScreenError(
                "native title resource changed at %02X:%04X"
                % (resource["bank"], resource["address"])
            )


def native_palette(plan, address):
    data = next(
        bytes.fromhex(h["bytes"])
        for h in plan["native_hooks"]
        if h["bank"] == 23 and h["address"] == address
    )
    return [
        tuple(
            ((int.from_bytes(data[i : i + 2], "little") >> bit) & 31) * 8
            for bit in (0, 5, 10)
        )
        for i in range(0, 64, 2)
    ]


def normalize(color):
    # The supplied almost-black ink maps to the native bat/outline black.
    if tuple(color) == (3, 3, 3):
        return (8, 8, 8)
    return tuple(min(31, round(value / 8)) * 8 for value in color)


def palette_bytes(palettes):
    return b"".join(
        ((r // 8) | ((g // 8) << 5) | ((b // 8) << 10)).to_bytes(2, "little")
        for palette in palettes
        for r, g, b in palette
    )


def gradient_color(y):
    """Native 32-step ramp, cropped by one row as in the supplied composition."""
    return tuple((value * min(y + 1, 31) // 32) * 8 for value in (1, 4, 11))


def compose(rom, phase=0, sparkle=-1, gradient=False, plan=None):
    plan = plan or recipe()

    def word(index):
        return int.from_bytes(rom[index : index + 2], "little")

    palettes = native_palette(plan, 0x416F)
    palettes[0] = gradient_color(31)
    source = offset(28, 0x4000)
    count = word(source)
    extra = count - 4096
    vram = (
        bytes(2048) + rom[source + 2 + extra : source + 2 + count],
        bytes(2048) + rom[source + 2 : source + 2 + extra] + bytes(4096 - extra),
    )
    source = offset(56, 0x4000)
    width, height = rom[source : source + 2]
    mapping = bytearray(rom[source + 2 : source + 2 + width * height * 2])
    descriptor = offset(24, word(offset(24, 0x4014) + phase * 2))
    destination = word(descriptor) - 0x9800
    moon_width, moon_height = rom[descriptor + 2 : descriptor + 4]
    for y in range(moon_height):
        for x in range(moon_width):
            target = ((destination // 32 + y) * width + destination % 32 + x) * 2
            source = descriptor + 4 + (y * moon_width + x) * 2
            mapping[target : target + 2] = rom[source : source + 2]

    base = Image.open(ART / SCENE).convert("RGB")
    image = Image.new("RGB", (160, 144))
    image.paste(base, (0, 0))
    image.paste(base.crop((0, 142, 160, 143)), (0, 143))
    for y in range(43):
        for x in range(160):
            source_y = y + 1
            index = ((source_y // 8) * 20 + x // 8) * 2
            tile, attributes = mapping[index : index + 2]
            tile = (tile ^ 128) + 128
            row = 7 - source_y % 8 if attributes & 64 else source_y % 8
            bit = x % 8 if attributes & 32 else 7 - x % 8
            address = tile * 16 + row * 2
            low, high = vram[(attributes >> 3) & 1][address : address + 2]
            color = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
            image.putpixel((x, y), palettes[(attributes & 7) * 4 + color])

    # The audition samples the original static overlay plane in this band too.
    # Its surviving black pixels form part of the approved castle silhouette.
    source = offset(49, 0x4000)
    count = word(source)
    obj_vram = (
        rom[source + 2 + count - 2048 : source + 2 + count],
        rom[source + 2 : source + 2 + count - 2048].ljust(2048, b"\0"),
    )
    obj_palettes = native_palette(plan, 0x5D75)
    records = [
        rom[offset(25, 0x43A5) + i * 4 : offset(25, 0x43A5) + i * 4 + 4]
        for i in range(29)
    ]
    for sprite_y, sprite_x, tile, attributes in reversed(records):
        sprite_y = (sprite_y + 144) & 255
        sprite_x = (sprite_x + 136) & 255
        for dy in range(16):
            y = sprite_y - 17 + dy
            if not 0 <= y < 43:
                continue
            row = 15 - dy if attributes & 64 else dy
            address = (tile & 254) * 16 + row * 2
            low, high = obj_vram[(attributes >> 3) & 1][address : address + 2]
            for dx in range(8):
                x = sprite_x - 8 + dx
                if not 0 <= x < 160:
                    continue
                bit = dx if attributes & 32 else 7 - dx
                color = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
                if color:
                    image.putpixel((x, y), obj_palettes[(attributes & 7) * 4 + color])
    for relative in (LOGO, SUBTITLE):
        layer = Image.open(ART / relative).convert("RGBA")
        image.paste(layer, (0, 0), layer)
    if sparkle >= 0:
        layer = Image.open(ART / (SHINE % (sparkle + 1))).convert("RGB")
        for y in range(143):
            for x in range(160):
                color = layer.getpixel((x, y))
                if color != KEY:
                    image.putpixel((x, y), color)
    image.putdata([normalize(color) for color in image.getdata()])
    if gradient:
        for y in range(32):
            for x in range(160):
                if image.getpixel((x, y)) == gradient_color(31):
                    image.putpixel((x, y), gradient_color(y))
    return image


def encode_pixels(values):
    data = bytearray()
    for row in range(len(values) // 8):
        low = high = 0
        for x, value in enumerate(values[row * 8 : row * 8 + 8]):
            low |= (value & 1) << (7 - x)
            high |= (value >> 1) << (7 - x)
        data.extend((low, high))
    return bytes(data)


def compile_graphics(rom, plan=None):
    plan = plan or recipe()
    validate_sources(rom, plan)
    scenes = [list(compose(rom, phase, plan=plan).getdata()) for phase in range(4)]
    bg, lower, obj = (
        [[tuple(color) for color in palette] for palette in plan[key]]
        for key in ("bg_palettes", "lower_palettes", "obj_palettes")
    )
    rects = [dict(x=r["x"], y=r["y"], pal=r["palette"]) for r in plan["sprites"]]
    cover = [[[] for _ in range(160)] for _ in range(144)]
    for index, rect in enumerate(rects):
        for y in range(rect["y"], min(rect["y"] + 16, 144)):
            for x in range(rect["x"], min(rect["x"] + 8, 160)):
                cover[y][x].append(index)

    allowed, costs = [], []
    for y in range(144):
        for tile_x in range(20):
            options = {}
            for index, palette in enumerate(bg if y < 112 else lower):
                if y < 32 and index > 1:
                    continue
                missing = cost = 0
                for scene in scenes:
                    for x in range(tile_x * 8, tile_x * 8 + 8):
                        color = scene[y * 160 + x]
                        if color not in palette:
                            cost += 1
                            if not any(
                                color in obj[rects[r]["pal"]] for r in cover[y][x]
                            ):
                                missing += 1
                if not missing and not (108 <= y < 115 and cost):
                    options[index] = cost
            if not options:
                raise TitleScreenError(
                    "title pixel allocation failed at %d,%d" % (tile_x * 8, y)
                )
            allowed.append(set(options))
            costs.append(options)

    # Longest common horizontal bands minimize required attribute interrupts.
    choices = [0] * (144 * 20)
    for tile_y in range(18):
        start = tile_y * 8
        while start < tile_y * 8 + 8:
            common = [set(allowed[start * 20 + x]) for x in range(20)]
            end = start + 1
            while end < tile_y * 8 + 8:
                following = [
                    colors & allowed[end * 20 + x] for x, colors in enumerate(common)
                ]
                if not all(following):
                    break
                common = following
                end += 1
            for x, options in enumerate(common):
                pick = min(
                    options,
                    key=lambda p: (
                        sum(costs[y * 20 + x][p] for y in range(start, end)),
                        p,
                    ),
                )
                for y in range(start, end):
                    choices[y * 20 + x] = pick
            start = end

    bodies, backgrounds, used = [], [], set()
    for scene in scenes:
        sprites = [[0] * 128 for _ in rects]
        background = []
        for y in range(144):
            palettes = bg if y < 112 else lower
            for x in range(160):
                color = scene[y * 160 + x]
                palette = palettes[choices[y * 20 + x // 8]]
                if color in palette:
                    background.append(palette.index(color))
                else:
                    background.append(0)
                    index = next(
                        r for r in cover[y][x] if color in obj[rects[r]["pal"]]
                    )
                    rect = rects[index]
                    sprites[index][(y - rect["y"]) * 8 + x - rect["x"]] = (
                        obj[rect["pal"]].index(color) + 1
                    )
                    used.add(index)
        backgrounds.append(background)
        bodies.append(sprites)
    retained = sorted(used)
    rects = [rects[index] for index in retained]
    bodies = [[phase[index] for index in retained] for phase in bodies]

    patterns = []
    for background in backgrounds:
        patterns.append(
            [
                encode_pixels(
                    [
                        background[(ty * 8 + y) * 160 + tx * 8 + x]
                        for y in range(8)
                        for x in range(8)
                    ]
                )
                for ty in range(18)
                for tx in range(20)
            ]
        )
    tiles, tile_ids, maps, dynamic = [], {}, [], []

    def tile_id(tile):
        if tile not in tile_ids:
            tile_ids[tile] = len(tiles)
            tiles.append(tile)
        return tile_ids[tile]

    # All moving moon tiles use bank zero, so attributes are phase-independent.
    for index in range(360):
        if len({phase[index] for phase in patterns}) > 1:
            dynamic.append(index)
            for phase in patterns:
                tile_id(phase[index])
    for phase in patterns:
        maps.append([tile_id(tile) for tile in phase])
    if len(tiles) > 511 or any(
        maps[0][i] // 256 != maps[p][i] // 256 for i in range(360) for p in range(4)
    ):
        raise TitleScreenError("title exceeds its VRAM allocation")
    attributes = bytes(
        choices[y * 20 + x] | (8 if maps[0][(y // 8) * 20 + x] >= 256 else 0)
        for y in range(144)
        for x in range(20)
    )

    # Decode the assembled background and sparse corrections as an independent
    # final composition check before any ROM is patched.
    for phase, scene in enumerate(scenes):
        for y in range(144):
            for x in range(160):
                palette = (bg if y < 112 else lower)[choices[y * 20 + x // 8]]
                color = palette[backgrounds[phase][y * 160 + x]]
                for index, rect in enumerate(rects):
                    if (
                        rect["x"] <= x < rect["x"] + 8
                        and rect["y"] <= y < rect["y"] + 16
                    ):
                        value = bodies[phase][index][
                            (y - rect["y"]) * 8 + x - rect["x"]
                        ]
                        if value:
                            color = obj[rect["pal"]][value - 1]
                            break
                if color != scene[y * 160 + x]:
                    raise TitleScreenError(
                        "compiled title differs from the approved composition"
                    )
    return dict(
        bg_palettes=bg,
        lower_palettes=lower,
        obj_palettes=obj,
        rects=rects,
        body=bodies,
        tiles=[t.hex() for t in tiles],
        maps=maps,
        attributes=attributes.hex(),
        dynamic_cells=dynamic,
    )
