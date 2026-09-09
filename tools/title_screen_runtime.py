"""Generate the title-only LR35902 renderer and native resource redirects.

The sky ISR runs from fixed WRAM. The remaining palette bands use CGB GDMA
inside HBlank. Retired OAM slots are reused for lower overlays and sparkle;
all animation clocks count VBlanks. No emulator or assembler executable is
required by the build.
"""

from PIL import Image

from title_graphics import ART, offset as off


class Asm:
    def __init__(self, base):
        self.base = base
        self.data = bytearray()
        self.labels = {}
        self.fix = []

    def emit(self, s):
        self.data.extend(bytes.fromhex(s) if isinstance(s, str) else s)
        return self

    def label(self, n):
        self.labels[n] = self.base + len(self.data)
        return self

    def addr(self, op, n):
        self.emit(op)
        self.fix.append((len(self.data), n, False))
        self.emit(b"\0\0")
        return self

    def jr(self, op, n):
        self.emit(op)
        self.fix.append((len(self.data), n, True))
        self.emit(b"\0")
        return self

    def finish(self):
        for at, n, rel in self.fix:
            target = self.labels[n] if isinstance(n, str) else n
            if rel:
                d = target - (self.base + at + 1)
                assert -128 <= d <= 127, (n, d)
                self.data[at] = d & 255
            else:
                self.data[at : at + 2] = target.to_bytes(2, "little")
        return bytes(self.data)


def pals(v):
    return b"".join(
        ((r // 8) | ((g // 8) << 5) | ((b // 8) << 10)).to_bytes(2, "little")
        for p in v
        for r, g, b in p
    )


def enc(v):
    d = bytearray()
    for y in range(len(v) // 8):
        l = h = 0
        for x, n in enumerate(v[y * 8 : y * 8 + 8]):
            l |= (n & 1) << (7 - x)
            h |= (n >> 1) << (7 - x)
        d.extend((l, h))
    return bytes(d)


def build(source, C):
    original = bytes(source)
    rom = bytearray(source)

    def put(bank, address, data):
        assert bank == 0 or 0x4000 <= address and address + len(data) <= 0x8000
        start = off(bank, address)
        rom[start : start + len(data)] = data

    bg = C["bg_palettes"]
    obj = C["obj_palettes"]
    lower = C["lower_palettes"]
    tiles = [bytes.fromhex(t) for t in C["tiles"]]
    rects = C["rects"]
    attrs = bytes.fromhex(C["attributes"])
    # Full normal-sized tile cells; attributes change at selected HBlank boundaries.
    put(
        246,
        0x4000,
        (0x1FF0).to_bytes(2, "little")
        + b"".join(tiles[256:]).ljust(4080, b"\0")
        + b"".join(tiles[:256]).ljust(4096, b"\0"),
    )
    put(5, 0x6F35, bytes.fromhex("0040f6"))
    maps = []
    for mapping in C["maps"]:
        m = bytearray()
        for i, n in enumerate(mapping):
            m.extend(((n % 256 + 128) & 255, attrs[(i // 20) * 8 * 20 + i % 20]))
        maps.append(bytes(m))
    put(246, 0x6000, bytes([20, 18]) + maps[0])
    put(0, 0x3CD3, bytes.fromhex("0060f6"))
    put(23, 0x416F, pals(bg))
    # Native OBJ palette selector zero is a length-prefixed record.
    ptable = off(23, 0x5C94)
    optr = int.from_bytes(original[ptable : ptable + 2], "little")
    assert original[off(23, optr)] == 64
    put(23, optr + 1, pals([[(0, 0, 0)] + p for p in obj]))
    # Native bat tile numbers stay in bank zero. All localized correction/shine tiles use bank one.
    body = [enc(v) for v in C["body"][0]]
    assert all([enc(v) for v in p] == body for p in C["body"])
    plane1 = bytearray(b"".join(body))
    shine_oam = [bytes(8)]
    base = Image.open(
        ART / "2 English title static with mask/2.GB2TitleStaticExample.png"
    ).convert("RGB")
    sub = Image.open(
        ART
        / "3 English subtitle animation components/1b.GB2TitleSubtitleTransparent.png"
    )
    base.paste(sub, (0, 0), sub)
    glint = [(248, 240, 128), (248, 248, 248), (224, 216, 104)]
    for phase in range(8):
        im = Image.open(
            ART
            / "4 English subtitle precomposed 8 frames"
            / ("GB2TitleExampleFrame%d.png" % (phase + 1))
        ).convert("RGB")
        pixels = {}
        for y in range(143):
            for x in range(160):
                c = im.getpixel((x, y))
                if c != (197, 0, 254) and c != base.getpixel((x, y)):
                    assert c in glint
                    pixels[x, y] = glint.index(c) + 1
        x0 = min(x for x, y in pixels)
        y0 = min(y for x, y in pixels)
        oam = bytearray()
        for part in range(2):
            tile = len(plane1) // 16
            v = [
                pixels.get((x0 + part * 8 + x, y0 + y), 0)
                for y in range(16)
                for x in range(8)
            ]
            plane1.extend(enc(v))
            oam.extend((y0 + 16, x0 + part * 8 + 8, tile, 15))
        shine_oam.append(bytes(oam))
    assert len(plane1) <= 2048, len(plane1)
    plane0 = bytearray(2048)
    src = off(49, 0x4000) + 2 + 0x300
    plane0[0x540:0x740] = original[src + 0x540 : src + 0x740]
    put(247, 0x4000, (4096).to_bytes(2, "little") + plane1.ljust(2048, b"\0") + plane0)
    put(63, 0x4017, bytes.fromhex("0040f7"))
    # Every scanline starts with its native-size tile row; no scaling or scroll strips.
    put(
        245,
        0x6000,
        b"".join(attrs[y * 20 : y * 20 + 20] + bytes(12) for y in range(144)),
    )
    # Main native moon selector wrapper returns a WRAM descriptor for the native copier.
    put(245, 0x5600, original[off(24, 0x4014) : off(24, 0x4214)])
    for phase, m in enumerate(maps):
        desc = (
            bytes.fromhex("0c98")
            + bytes([6, 6])
            + b"".join(m[(y * 20 + 12) * 2 : (y * 20 + 18) * 2] for y in range(6))
        )
        put(245, 0x5400 + phase * 76, desc)
    put(24, 0x4000, bytes.fromhex("3ef5210044cdac09"))
    put(245, 0x53F0, bytes.fromhex("149801018000"))
    a = Asm(0x4400)
    a.emit("c5d5f0b0fe04").jr("30", "generic").emit("fae5c0fe09").jr(
        "20", "generic"
    ).emit("fab4c3fe9d").jr("20", "generic").emit(
        "21f0531100c8010600cd620a2100c8d1c1c9"
    )
    a.label("generic").emit("f0b0210056cdd309d1c1c9")
    put(245, a.base, a.finish())
    for phase, m in enumerate(maps):
        put(
            245,
            0x5800 + phase * 192,
            b"".join(
                bytes(m[(y * 20 + x) * 2] for x in range(20)) + bytes(12)
                for y in range(6)
            ),
        )
    # The private raster renderer owns title objects; retain other selectors verbatim.
    put(245, 0x5E00, original[off(25, 0x4025) : off(25, 0x4225)])
    put(25, 0x4000, bytes.fromhex("3ef5210045cdac097cb5c8c310400000"))
    a = Asm(0x4500)
    a.emit("f0b0fe03").jr("30", "generic").emit("fae5c0fe09").jr("20", "generic").emit(
        "fab4c3fe9d"
    ).jr("20", "generic").emit("210000c9")
    a.label("generic").emit("f0b021005ecdd3097dea45c47cea46c4c9")
    put(245, a.base, a.finish())
    # During attract startup the native engine retains raster mode 9 after
    # releasing the title's scratch memory. Reproduce its original sky handler
    # entirely in ROM for that interval; never enter the staged WRAM code.
    a = Asm(0x4580)
    a.label("wait").emit("f041e602").jr("20", "wait")
    a.emit("fae7c03cfe20").jr("38", "color").emit("afeae7c0e045e0f9c9")
    a.label("color").emit(
        "eae7c0e045e0f9875f1600faf5c0a7c0f070f53e01e0702180df193e80e0682ae0692ae069f1e070c9"
    )
    put(245, a.base, a.finish())
    # Title entry clears private transient state before the first title VBlank.
    # The native mode setter preserves BC/DE/HL. In particular, demo scripts
    # retain their source cursor in HL across this call.
    put(5, 0x5E13, bytes.fromhex("e53ef5210046cdac09e1afc90000"))
    a = Asm(0x4600)
    a.emit("c5d5f0b0fe09").jr("20", "native").emit("fab4c3fe9d").jr(
        "20", "native"
    ).emit("2180c80660af")
    a.label("clear").emit("2205").jr("20", "clear").emit("21007d1100c901e000cd620a")
    a.label("native").emit("f0b0eae5c0cd6025afe045e0f9d1c1c9")
    put(245, a.base, a.finish())
    bat_frames = []
    counts = list(original[off(25, 0x42C7) : off(25, 0x42D9)])
    offsets = [sum(counts[:i]) * 4 for i in range(18)]
    for i in range(24):
        f, xbase, ybase, duration = original[
            off(25, 0x4266) + i * 4 : off(25, 0x4266) + i * 4 + 4
        ]
        assert duration == 3
        descs = bytearray()
        for j in range(counts[f]):
            yy, xx, t, attr = original[
                off(25, 0x42D9)
                + offsets[f]
                + j * 4 : off(25, 0x42D9)
                + offsets[f]
                + j * 4
                + 4
            ]
            yy = (yy + ybase) & 255
            descs.extend((yy - (13 if yy == 45 else 1), (xx + xbase) & 255, t, attr))
        bat_frames.append(bytes(descs).ljust(16, b"\0"))
    put(245, 0x5C00, b"".join(bat_frames))
    # At most 40 OAM entries are resident. Six later body entries reuse retired
    # slots, with two more replacements for the subtitle sparkle.
    body_oam = [
        bytes((r["y"] + 16, r["x"] + 8, i * 2, 8 + r["pal"]))
        for i, r in enumerate(rects)
    ]
    initial = bytes(12) + b"".join(body_oam[:37])
    put(245, 0x5000, initial.ljust(160, b"\0"))
    put(245, 0x5200, b"".join(v + bytes(8) for v in shine_oam))
    # These two HBlanks have no attribute DMA. Combining a four-byte OAM
    # update with DMA can push its final attribute write into the next mode 2.
    actions = {34: ("glint", 0), 37: ("glint", 1)}
    for j, o in enumerate(body_oam[37:]):
        slot = 2 + j
        previous_end = 33 if slot == 2 else rects[slot - 3]["y"] + 16
        line = max(previous_end, 36 if slot == 2 else 48)
        while line in actions:
            line += 1
        assert line < rects[37 + j]["y"]
        actions[line] = ("body", slot, o)
    # All correction sprites are transparent in the inter-title gap.
    assert all(
        not C["body"][0][i][(y - r["y"]) * 8 + x]
        for i, r in enumerate(rects)
        for y in range(max(108, r["y"]), min(115, r["y"] + 16))
        for x in range(8)
    )
    actions[107] = ("obj_enable", False)
    # Four bytes per HBlank leave time for attribute DMA. Eight-byte writes
    # overrun on Mesen's CGB timing even though PyBoy accepts those accesses.
    actions[108] = ("palette", 0, pals([lower[0]])[:4])
    actions[109] = ("palette", 4, pals([lower[0]])[4:])
    actions[110] = ("palette", 8, pals([lower[1]])[:4])
    actions[111] = ("palette", 12, pals([lower[1]])[4:])
    actions[112] = ("obj_palette", 56, pals([[(0, 0, 0)] + glint])[:4])
    actions[113] = ("obj_palette", 60, pals([[(0, 0, 0)] + glint])[4:])
    actions[114] = ("obj_enable", True)
    initial_attrs = b"".join(
        attrs[y * 20 : y * 20 + 20] + bytes(12) for y in range(0, 144, 8)
    )
    put(245, 0x7300, initial_attrs)
    attribute_events = {
        y - 1
        for y in range(1, 144)
        if y % 8 and attrs[y * 20 : y * 20 + 20] != attrs[(y - 1) * 20 : y * 20]
    }
    assert all(
        y not in attribute_events
        for y, action in actions.items()
        if action[0] == "glint"
    )

    def grad(y):
        return tuple((v * (min(y + 1, 31)) // 32) * 8 for v in (1, 4, 11))

    gradient_events = {y for y in range(31) if grad(y) != grad(y + 1)} | {0}
    events = sorted(attribute_events | gradient_events | set(actions))
    next_event = [next((e for e in events if e > y), 0) for y in range(144)]
    put(245, 0x7540, bytes(next_event))
    # VBlank creates next frame's OAM, restores the upper palettes, and seeds line zero attributes.
    a = Asm(0x4000)
    a.emit("fab4c3fe9dc0")
    a.emit("fa85c83cfe06").jr("38", "mooncount").emit("affa81c83ce603ea81c8af")
    a.label("mooncount").emit("ea85c8")
    a.emit("fa81c847fa82c8b8").jr("28", "template").emit("78ea82c85f21005801c000")
    a.label("phase_map").emit("7bb7").jr("28", "map_selected").emit("091d").jr(
        "18", "phase_map"
    )
    a.label("map_selected").emit("f04ff5afe04f7ce0517de0523e98e053afe0543e0be055f1e04f")
    # Native HRAM $FF82 accepts the DMA source page in A. Copy the ROM OAM
    # template directly, then set the bats in OAM. Avoiding the 148-byte WRAM
    # copy leaves VBlank headroom for simultaneous moon and sparkle updates.
    a.label("template").emit("3e50cd82ff")
    a.emit("fa84c83cfe04").jr("38", "batcount").emit("affa83c83cfe18").jr(
        "38", "batphase"
    ).emit("af")
    a.label("batphase").emit("ea83c8af")
    a.label("batcount").emit("ea84c8")
    a.emit("fa83c8cb37e6f06ffa83c8cb37e60fc65c671100fe").emit("2a1213" * 12)
    # The private transfer supersedes native shadow DMA and subtitle palettes.
    a.emit("afeaebc0eaecc0")
    # A 240-frame clock, ten frames per shine phase, first sweep at frame sixty.
    a.emit("fa80c83cfeF0").jr("38", "clock").emit("af")
    a.label("clock").emit("ea80c8d63c").jr("38", "rest").emit("fe50").jr(
        "30", "rest"
    ).emit("0601")
    a.label("phase").emit("fe0a").jr("38", "gotphase").emit("d60a04").jr("18", "phase")
    a.label("rest").emit("0600")
    a.label("gotphase").emit("78cb376f265211d0c8").emit("2a1213" * 8)
    # Restore palettes only outside the native fade writer.
    a.emit("faf5c0a7").jr("20", "seed")
    for index, data, reg in [
        (0, pals(bg[:2]), 0x68),
        (56, pals([[(0, 0, 0)] + obj[7]]), 0x6A),
    ]:
        a.emit(bytes((0x3E, 0x80 | index, 0xE0, reg)))
        for byte in data:
            a.emit(bytes((0x3E, byte, 0xE0, reg + 1)))
    a.emit("3e80e068afe069e069")
    a.label("seed").emit("f04ff53e01e04f3e73e051afe0523e98e053afe0543e23e055f1e04fc9")
    code = a.finish()
    assert len(code) < 0x400
    put(245, a.base, code)
    # STAT schedules its next interrupt before waiting for HBlank.
    a = Asm(0x4700)
    a.emit("fab4c3fe9d").addr("c2", 0x4580)
    a.emit("f04447c6406f26757ee045f04ff53e01e04f78fe1f").addr("da", 0x4900)
    # LY * 8 indexes an aligned record of the four DMA registers and handler address.
    a.emit(
        "788787876f78cb3fcb3fcb3fcb3fcb3fc676672ae0512ae0522ae0532ae0542a5f7e576b62e9"
    )
    put(245, a.base, a.finish())
    # Handlers are chosen before the wait, leaving only DMA and a short write sequence in HBlank.
    handlers = {}
    cursor = 0x4900
    for key in ["gradient", "plain"] + sorted(set(actions) | attribute_events):
        a = Asm(cursor)
        if key == "gradient":
            a.emit("78fe1d").jr("30", "solid").emit("876f26722a4f7e57").jr("18", "wait")
            a.label("solid").emit("0e601628")
        a.label("wait").emit("f041e602").jr("20", "wait")
        if key in attribute_events:
            a.emit("3e01e055")
        if key == "gradient":
            a.emit("faf5c0a7").jr("20", "done").emit("3e80e06879e0697ae069")
        elif key in actions:
            action = actions[key]
            if action[0] == "glint":
                part = action[1]
                for k in range(4):
                    a.emit(
                        b"\xfa"
                        + (0xC8D0 + part * 4 + k).to_bytes(2, "little")
                        + b"\xea"
                        + (0xFE00 + part * 4 + k).to_bytes(2, "little")
                    )
            elif action[0] == "body":
                _, slot, desc = action
                for k, byte in enumerate(desc):
                    a.emit(
                        bytes((0x3E, byte, 0xEA))
                        + (0xFE00 + slot * 4 + k).to_bytes(2, "little")
                    )
            elif action[0] == "obj_enable":
                a.emit("f040f602e040" if action[1] else "f040e6fde040")
            elif action[0] in ("palette", "obj_palette"):
                _, index, data = action
                assert len(data) <= 4
                reg = 0x68 if action[0] == "palette" else 0x6A
                a.emit("faf5c0a7").jr("20", "done").emit(
                    bytes((0x3E, 0x80 | index, 0xE0, reg))
                )
                for byte in data:
                    a.emit(bytes((0x3E, byte, 0xE0, reg + 1)))
        a.label("done").emit("f1e04fc9")
        code = a.finish()
        put(245, cursor, code)
        handlers[key] = cursor
        cursor += len(code)
    assert cursor <= 0x5000, hex(cursor)
    records = bytearray()
    for y in range(144):
        n = y + 1
        handler = handlers[y if y in actions or y in attribute_events else "plain"]
        records.extend(
            bytes((0x60 + n // 8, (n * 32) & 255, 0x98 + n // 64, (n * 4) & 0xE0))
            + handler.to_bytes(2, "little")
            + bytes(2)
        )
    put(245, 0x7600, records)
    # Native gradient bytes, captured once from the unmodified cartridge.
    put(
        245,
        0x7200,
        pals(
            [
                [
                    tuple((value * i // 32) * 8 for value in (1, 4, 11))
                    for i in range(2, 32)
                ]
            ]
        ),
    )
    # A short sky ISR in fixed WRAM avoids a ROM-bank switch on the tightest lines.
    a = Asm(0xC900)
    a.emit("f04447c6c06f26c97ee045faf5c0a7").addr("c2", 0x0061).emit(
        "7887c6806f26c92a4f7e57"
    )
    a.label("wait").emit("f041e602").jr("20", "wait").emit("3e80e06879e0697ae069").addr(
        "c3", 0x0061
    )
    fast = bytearray(224)
    fast[: len(a.finish())] = a.finish()
    fast[128:188] = rom[off(245, 0x7200) : off(245, 0x7200) + 60]
    fast[192:224] = bytes(next_event[:32])
    put(245, 0x7D00, fast)
    # IRQ gates are title-only and keep interrupts disabled while switching ROM banks.
    a = Asm(0x07D9)
    a.emit("fae5c0fe09").addr("c2", 0x057A).emit("3ef5ea0021cd0040f0f7ea0021").addr(
        "c3", 0x057A
    )
    sg = a.base + len(a.data)
    a.emit("fae5c0fe09").addr("c2", 0x062D).emit("fab4c3fe9d").jr("20", "far").emit(
        "f044fe1f"
    ).addr("da", 0xC900)
    a.label("far").emit("3ef5ea0021cd0047f0f7ea0021").addr("c3", 0x0061)
    code = a.finish()
    # $081C is also raster mode 10's shared return stub.
    assert len(code) <= 67
    put(0, a.base, code.ljust(67, b"\0"))
    put(0, 0x0044, b"\xc3" + a.base.to_bytes(2, "little"))
    put(0, 0x004C, b"\xc3" + sg.to_bytes(2, "little"))
    return bytes(rom), dict(
        body_sprites=len(rects),
        background_tiles=len(tiles),
        stat_events=len(events),
        object_tiles=len(plane1) // 16 + 32,
    )
