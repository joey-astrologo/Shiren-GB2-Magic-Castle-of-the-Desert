#!/usr/bin/env python3
"""Capture isolated debug menus, optionally in a private Mesen run."""
import argparse
from hashlib import sha1
import html
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image
import capture_dialogue
import debug_room_prototype
import pyboy_route

ROOT = Path(__file__).resolve().parents[1]
MENU_BOX = (8, 16, 112, 104)
MAIN_BOX = (8, 16, 80, 72)
WEAPONS_BOX = (8, 16, 72, 88)
BRACELETS_BOX = (8, 16, 88, 72)
SCROLLS_BOX = (8, 16, 72, 88)
POTS_BOX = (8, 16, 64, 56)
MEAT1_BOX = (8, 16, 96, 104)
MEAT2_BOX = (8, 16, 96, 104)
MEAT3_BOX = (8, 16, 96, 104)
FLAGS_BOX = (8, 16, 112, 88)
MENU_BOXES = {"main": MAIN_BOX, "category": MENU_BOX, "weapons": WEAPONS_BOX,
              "bracelets": BRACELETS_BOX, "scrolls": SCROLLS_BOX, "pots": POTS_BOX, "meat1": MEAT1_BOX, "meat2": MEAT2_BOX, "meat3": MEAT3_BOX, "flags": FLAGS_BOX}
MOTION_RANGES = {
    "main": ((500, 1630), (3400, 3470), (3700, 3770), (4000, 4070), (6370, 6440), (8880, 8950), (11890, 11960), (14800, 14870), (18020, 18090), (20950, 21020), (24480, 24650), (26130, 26300), (26580, 26750), (27030, 27100)),
    "category": ((1750, 3320), (3550, 3620), (3850, 3920),
                 (4190, 4220), (5690, 5740), (5950, 6020), (6230, 6300),
                 (6560, 6690), (7960, 8090), (8350, 8480), (8740, 8810),
                 (9070, 9300), (10770, 11000), (11260, 11490), (11750, 11820),
                 (12080, 12410), (13480, 13810), (14070, 14400), (14660, 14730), (15080, 15210), (17880, 17950), (18210, 18340), (20810, 20880), (21140, 21270), (24340, 24410)),
    "weapons": ((4340, 5620), (5810, 5880), (6090, 6160)),
    "bracelets": ((6810, 7890), (8210, 8280), (8600, 8670)),
    "scrolls": ((9420, 10700), (11120, 11190), (11610, 11680)),
    "pots": ((12530, 13410), (13930, 14000), (14520, 14590)),
    "meat1": ((15330, 16810), (17330, 17410), (17730, 17810), (18460, 18540), (20660, 20740), (21390, 21470), (23390, 23470), (24190, 24270)),
    "meat2": ((16930, 17010), (17530, 17610), (18660, 20140), (20460, 20540), (21590, 21670), (23590, 23670), (23990, 24070)),
    "meat3": ((17130, 17210), (20260, 20340), (21790, 23270), (23790, 23870)),
    "flags": ((24770, 26050), (26420, 26500), (26870, 26950)),
}


def menu_hash(picture, kind="category"):
    """Match the small FNV-1a screen digest used by the Mesen callback."""
    value = 2166136261
    for r, g, b in picture.convert("RGB").crop(MENU_BOXES[kind]).getdata():
        value = ((value ^ ((r << 16) | (g << 8) | b)) * 16777619) & 0xffffffff
    return value


def capture_motion(rom, output, style):
    p = pyboy_route.start(capture_dialogue._pyboy_class(), rom, ROOT / "SaveStates/debug-room.state")
    motion = output / "cursor-motion"
    motion.mkdir(exist_ok=True)
    try:
        p.gameshark.add("019F2FC1")
        p.button("a", 5)
        p.tick(490)
        p.gameshark.remove("019F2FC1")
        p.button("a", 5)
        p.tick(90)
        p.button("down", 5)
        for frame in range(15):
            p.tick(1)
            p.screen.image.crop(MENU_BOX).save(motion / ("after-%s-%02d.png" % (style, frame)))
    finally:
        p.stop(save=False)


def capture_transitions(rom, output, style):
    """Keep every opening/closing frame along the ten repaired menus, including Meat pagination and Set Flag."""
    directory = output / "set-flag"
    directory.mkdir(exist_ok=True)
    p = pyboy_route.start(capture_dialogue._pyboy_class(), rom, ROOT / "SaveStates/debug-room.state")
    try:
        p.gameshark.add("019F2FC1")
        p.button("a", 5)
        p.tick(490)
        p.gameshark.remove("019F2FC1")
        for name, button in (("open-category", "a"), ("open-weapons", "a"),
                             ("return-category", "b"), ("open-bracelets", "a"),
                             ("return-from-bracelets", "b"), ("open-scrolls", "a"),
                             ("return-from-scrolls", "b"), ("open-pots", "a"), ("return-from-pots", "b"),
                             ("open-meat1", "a"), ("next-meat2", "a"), ("next-meat3", "a"), ("cycle-to-meat1", "a"), ("revisit-meat2", "a"),
                             ("revisit-meat3", "a"), ("back-to-meat2", "b"), ("back-to-meat1", "b"),
                             ("return-from-meat1", "b"), ("return-main", "b"), ("open-flags", "a"), ("return-from-flags", "b"), ("exit-main", "b")):
            for _ in range({"open-bracelets": 1, "open-scrolls": 2, "open-pots": 3, "open-meat1": 4, "open-flags": 1}.get(name, 0)):
                p.button("down", 5)
                p.tick(90)
            for frame in range(40):
                p.screen.image.save(directory / ("%s-%s-%02d.png" % (style, name, frame)))
                if frame == 0:
                    p.button(button, 5)
                p.tick(1)
            p.tick(50)
    finally:
        p.stop(save=False)


def capture(rom, output, prefix):
    p = pyboy_route.start(capture_dialogue._pyboy_class(), rom, ROOT / "SaveStates/debug-room.state")
    names = []

    def press(button):
        p.button(button, 5)
        p.tick(90)

    def save(name):
        name = prefix + "-" + name + ".png"
        p.screen.image.save(output / name)
        names.append(name)

    try:
        p.gameshark.add("019F2FC1")
        press("a")
        p.tick(400)
        p.gameshark.remove("019F2FC1")
        save("root")
        for i in range(1, 3):
            press("down")
            save("main-%d" % i)
        press("down")
        press("a")
        for i in range(5):
            if i:
                press("down")
            save("category-%d" % i)
        press("down")  # Wrap to Weapons/Shields.
        press("a")
        for i in range(4):
            if i:
                press("down")
            save("weapons-%d" % i)
        press("b")
        save("weapons-back")
        press("down")
        press("a")
        for i in range(3):
            if i:
                press("down")
            save("bracelets-%d" % i)
        press("b")
        save("bracelets-back")
        press("down")
        press("down")
        press("a")
        for i in range(4):
            if i:
                press("down")
            save("scrolls-%d" % i)
        press("b")
        save("scrolls-back")
        for _ in range(3):
            press("down")
        press("a")
        save("pots-0")
        press("down")
        save("pots-1")
        press("b")
        save("pots-back")
        press("up")
        press("a")
        for i in range(5):
            if i:
                press("down")
            save("meat1-%d" % i)
        press("down")
        press("a")
        save("meat2")
        for i in range(5):
            if i:
                press("down")
            save("meat2-%d" % i)
        press("down")
        press("a")
        save("meat3")
        for i in range(5):
            if i:
                press("down")
            save("meat3-%d" % i)
        press("down")
        press("a")
        save("meat1-return-1")
        press("a")
        save("meat2-return")
        press("b")
        save("meat1-return-2")
        press("b")
        save("meat1-back")
        press("b")
        save("back")
        press("down")
        press("a")
        for i in range(4):
            if i:
                press("down")
            save("flags-%d" % i)
        press("b")
        save("flags-back")
        press("b")
        save("gameplay")
        for button, name in (("b", "status"), ("a", "items"), ("a", "item-actions"),
                             ("b", "items-return"), ("b", "status-return"), ("b", "gameplay-return")):
            press(button)
            save(name)
    finally:
        p.stop(save=False)
    return names


def mesen(executable, rom, output, prefix, allowed_hashes):
    """Use the native source state; no dependency on it is introduced in tests."""
    state = (ROOT / "SaveStates/debug-room.mss").read_bytes().hex()
    script = """
local state = ("STATE_HEX"):gsub('..', function(c) return string.char(tonumber(c, 16)) end)
local mem = emu.memType.gameboyMemory
local frame, loaded = 0, false
local actions = {[30]='a', [530]='down', [630]='down', [730]='down',
  [830]='up', [930]='up', [1030]='up', [1630]='a',
  [1780]='down', [1880]='down', [1980]='down', [2080]='down', [2180]='down',
  [2280]='up', [2380]='up', [2480]='up', [2580]='up', [2680]='up',
  [3320]='b', [3470]='a', [3620]='b', [3770]='a', [3920]='b', [4070]='a',
  [4220]='a', [4370]='down', [4470]='down', [4570]='down', [4670]='down',
  [4770]='up', [4870]='up', [4970]='up', [5070]='up',
  [5620]='b', [5740]='a', [5880]='b', [6020]='a', [6160]='b', [6300]='b', [6440]='a',
  [6590]='down', [6690]='a', [6840]='down', [6940]='down', [7040]='down',
  [7140]='up', [7240]='up', [7340]='up', [7890]='b', [7990]='down', [8090]='a',
  [8280]='b', [8380]='down', [8480]='a', [8670]='b', [8810]='b', [8950]='a',
  [9100]='down', [9200]='down', [9300]='a',
  [9450]='down', [9550]='down', [9650]='down', [9750]='down',
  [9850]='up', [9950]='up', [10050]='up', [10150]='up',
  [10700]='b', [10800]='down', [10900]='down', [11000]='a',
  [11190]='b', [11290]='down', [11390]='down', [11490]='a',
  [11680]='b', [11820]='b', [11960]='a',
  [12110]='down', [12210]='down', [12310]='down', [12410]='a',
  [12560]='down', [12660]='down', [12760]='up', [12860]='up',
  [13410]='b', [13510]='down', [13610]='down', [13710]='down', [13810]='a',
  [14000]='b', [14100]='down', [14200]='down', [14300]='down', [14400]='a',
  [14590]='b', [14730]='b', [14870]='a', [15110]='up', [15210]='a',
  [15360]='down', [15460]='down', [15560]='down', [15660]='down', [15760]='down',
  [15860]='up', [15960]='up', [16060]='up', [16160]='up', [16260]='up',
  [16810]='a', [17010]='a', [17210]='a', [17410]='a', [17610]='b',
  [17810]='b', [17950]='b', [18090]='a', [18240]='up', [18340]='a', [18540]='a',
  [18690]='down', [18790]='down', [18890]='down', [18990]='down', [19090]='down',
  [19190]='up', [19290]='up', [19390]='up', [19490]='up', [19590]='up',
  [20140]='a', [20340]='b', [20540]='b', [20740]='b', [20880]='b', [21020]='a',
  [21170]='up', [21270]='a', [21470]='a', [21670]='a',
  [21820]='down', [21920]='down', [22020]='down', [22120]='down', [22220]='down',
  [22320]='up', [22420]='up', [22520]='up', [22620]='up', [22720]='up',
  [23270]='a', [23470]='a', [23670]='a', [23870]='b', [24070]='b', [24270]='b', [24410]='b', [24550]='down', [24650]='a',
  [24800]='down', [24900]='down', [25000]='down', [25100]='down',
  [25200]='up', [25300]='up', [25400]='up', [25500]='up',
  [26050]='b', [26200]='down', [26300]='a', [26500]='b',
  [26650]='down', [26750]='a', [26950]='b', [27100]='b'}
local captures = {[500]='root', [600]='main-1', [700]='main-2',
  [1750]='category-0', [1850]='category-1', [1950]='category-2',
  [2050]='category-3', [2150]='category-4', [3400]='back',
  [3550]='category-return-1', [3700]='main-return-1',
  [3850]='category-return-2', [4000]='main-return-2', [4190]='category-for-weapons',
  [4340]='weapons-0', [4440]='weapons-1', [4540]='weapons-2', [4640]='weapons-3',
  [5690]='weapons-back', [5810]='weapons-return-1', [5950]='category-return-3',
  [6090]='weapons-return-2', [6230]='category-return-4', [6370]='main-return-3',
  [6560]='category-for-bracelets', [6810]='bracelets-0', [6910]='bracelets-1', [7010]='bracelets-2',
  [7960]='bracelets-back', [8210]='bracelets-return-1', [8350]='category-return-5',
  [8600]='bracelets-return-2', [8740]='category-return-6', [8880]='main-return-4',
  [9070]='category-for-scrolls', [9420]='scrolls-0', [9520]='scrolls-1',
  [9620]='scrolls-2', [9720]='scrolls-3', [10770]='scrolls-back',
  [11120]='scrolls-return-1', [11260]='category-return-7', [11610]='scrolls-return-2',
  [11750]='category-return-8', [11890]='main-return-5',
  [12080]='category-for-pots', [12530]='pots-0', [12630]='pots-1', [13480]='pots-back',
  [13930]='pots-return-1', [14070]='category-return-9', [14520]='pots-return-2',
  [14660]='category-return-10', [14800]='main-return-6',
  [15080]='category-for-meat1', [15330]='meat1-0', [15430]='meat1-1', [15530]='meat1-2',
  [15630]='meat1-3', [15730]='meat1-4', [16930]='meat2', [17130]='meat3',
  [17330]='meat1-return-1', [17530]='meat2-return', [17730]='meat1-return-2',
  [17880]='meat1-back', [18020]='main-return-7',
  [18210]='category-for-meat2', [18460]='meat1-for-meat2',
  [18660]='meat2-0', [18760]='meat2-1', [18860]='meat2-2', [18960]='meat2-3', [19060]='meat2-4',
  [20260]='meat3-return', [20460]='meat2-return-2', [20660]='meat1-return-3',
  [20810]='category-return-11', [20950]='main-return-8',
  [21140]='category-for-meat3', [21390]='meat1-for-meat3', [21590]='meat2-for-meat3',
  [21790]='meat3-0', [21890]='meat3-1', [21990]='meat3-2', [22090]='meat3-3', [22190]='meat3-4',
  [23390]='meat1-return-4', [23590]='meat2-return-3', [23790]='meat3-return-2',
  [23990]='meat2-return-4', [24190]='meat1-return-5', [24340]='category-return-12',
  [24480]='main-return-9', [24770]='flags-0', [24870]='flags-1', [24970]='flags-2', [25070]='flags-3',
  [26130]='flags-back', [26420]='flags-return-1', [26580]='main-return-10',
  [26870]='flags-return-2', [27030]='main-return-11', [27200]='gameplay'}
local ranges = MOTION_RANGES
emu.addMemoryCallback(function()
  if not loaded then loaded = true; emu.loadSavestate(state) end
end, emu.callbackType.exec, 0, 0xffff, emu.cpuType.gameboy)
emu.addEventCallback(function()
  if not loaded then return end
  local input = {a=false,b=false,up=false,down=false,left=false,right=false,start=false,select=false}
  for at, button in pairs(actions) do
    if frame >= at and frame < at + 5 then input[button] = true end
  end
  if (frame >= 1130 and frame < 1280) or (frame >= 2780 and frame < 2930) then input.down = true end
  if (frame >= 1330 and frame < 1480) or (frame >= 2980 and frame < 3130) then input.up = true end
  if frame >= 5170 and frame < 5320 then input.down = true end
  if frame >= 5370 and frame < 5520 then input.up = true end
  if frame >= 7440 and frame < 7590 then input.down = true end
  if frame >= 7640 and frame < 7790 then input.up = true end
  if frame >= 10250 and frame < 10400 then input.down = true end
  if frame >= 10450 and frame < 10600 then input.up = true end
  if frame >= 12960 and frame < 13110 then input.down = true end
  if frame >= 13160 and frame < 13310 then input.up = true end
  if frame >= 16360 and frame < 16510 then input.down = true end
  if frame >= 16560 and frame < 16710 then input.up = true end
  if frame >= 19690 and frame < 19840 then input.down = true end
  if frame >= 19890 and frame < 20040 then input.up = true end
  if frame >= 22820 and frame < 22970 then input.down = true end
  if frame >= 23020 and frame < 23170 then input.up = true end
  if frame >= 25600 and frame < 25750 then input.down = true end
  if frame >= 25800 and frame < 25950 then input.up = true end
  emu.setInput(input, 0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  if not loaded then return end
  if frame < 500 then emu.write(0xc12f, 0x9f, mem) end
  for kind, intervals in pairs(ranges) do
    for _, interval in ipairs(intervals) do
      if frame >= interval[1] and frame < interval[2] then
        local screen, hash = emu.getScreenBuffer(), 2166136261
        local xmax, ymax = 111, 103
        if kind == 'main' then xmax, ymax = 79, 71 end
        if kind == 'weapons' then xmax, ymax = 71, 87 end
        if kind == 'bracelets' then xmax, ymax = 87, 71 end
        if kind == 'scrolls' then xmax, ymax = 71, 87 end
        if kind == 'pots' then xmax, ymax = 63, 55 end
        if kind == 'flags' then xmax, ymax = 111, 87 end
        if kind == 'meat1' or kind == 'meat2' or kind == 'meat3' then xmax, ymax = 95, 103 end
        for y = 16, ymax do
          for x = 8, xmax do
            hash = ((hash ~ (screen[y * 160 + x + 1] & 0xf8f8f8)) * 16777619) & 0xffffffff
          end
        end
        print('DEBUG_MOTION ' .. kind .. ' ' .. frame .. ' ' .. emu.read(0xc14f, mem) .. ' ' .. hash)
      end
    end
  end
  if captures[frame] then
    local pixels = {}
    for i, color in ipairs(emu.getScreenBuffer()) do
      pixels[i] = string.format('%06x', color & 0xf8f8f8)
    end
    print('DEBUG_FRAME ' .. captures[frame] .. ' ' .. emu.read(0xc14f, mem) .. ' ' .. table.concat(pixels))
  end
  if frame == 27200 then emu.stop(0) end
  frame = frame + 1
end, emu.eventType.endFrame)
""".replace("STATE_HEX", state).replace("MOTION_RANGES", "{" + ",".join(
        kind + "={" + ",".join("{%d,%d}" % pair for pair in intervals) + "}"
        for kind, intervals in MOTION_RANGES.items()) + "}")
    names = []
    motion_frames = {kind: [] for kind in MOTION_RANGES}
    seen = {kind: set() for kind in MOTION_RANGES}
    with tempfile.TemporaryDirectory(prefix="gb2-debug-mesen-") as tmp:
        tmp = Path(tmp)
        local_exe = tmp / executable.name
        shutil.copy2(executable, local_exe)
        for file in executable.parent.iterdir():
            if file.is_file() and (file.suffix in (".dll", ".dylib", ".so") or ".so." in file.name):
                shutil.copy2(file, tmp / file.name)
        (tmp / "settings.json").write_text("{}\n")
        shutil.copy2(rom, tmp / "experiment.gbc")
        (tmp / "capture.lua").write_text(script)
        result = subprocess.run(
            [str(local_exe), "--testRunner", "--timeout=500", "--gameBoy.gbcAdjustColors=false",
             "--gameBoy.blendFrames=false", str(tmp / "capture.lua"), str(tmp / "experiment.gbc")],
            cwd=tmp, capture_output=True, text=True, timeout=510,
        )
        (output / (prefix + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Mesen failed; see %s.log" % prefix)
        for line in result.stdout.splitlines():
            if line.startswith("DEBUG_MOTION "):
                _, kind, frame, selection, digest = line.split()
                if int(digest) not in allowed_hashes[kind]:
                    raise AssertionError("Mesen %s cursor/text flicker at frame %s; see %s.log" % (kind, frame, prefix))
                motion_frames[kind].append(int(frame))
                seen[kind].add(allowed_hashes[kind][int(digest)])
            if line.startswith("DEBUG_FRAME "):
                _, checkpoint, selection, pixels = line.split()
                positions = {"root": 0, "main-1": 1, "main-2": 2,
                             **{"category-%d" % i: i for i in range(5)},
                             **{"weapons-%d" % i: i for i in range(4)},
                             **{"bracelets-%d" % i: i for i in range(3)},
                             **{"scrolls-%d" % i: i for i in range(4)},
                             **{"pots-%d" % i: i for i in range(2)},
                             **{"meat1-%d" % i: i for i in range(5)},
                             **{"meat2-%d" % i: i for i in range(5)},
                             **{"meat3-%d" % i: i for i in range(5)},
                             **{"flags-%d" % i: i for i in range(4)}}
                if checkpoint in positions and int(selection) != positions[checkpoint]:
                    raise AssertionError("Mesen selection did not reach " + checkpoint)
                name = prefix + "-" + checkpoint + ".png"
                Image.frombytes("RGB", (160, 144), bytes.fromhex(pixels)).save(output / name)
                names.append(name)
        if len(names) != 104:
            raise AssertionError("Mesen did not produce all 104 checkpoints")
        for kind, intervals in MOTION_RANGES.items():
            expected = [frame for first, last in intervals for frame in range(first, last)]
            if motion_frames[kind] != expected or seen[kind] != set(range({"main": 3, "category": 5, "weapons": 4, "bracelets": 3, "scrolls": 4, "pots": 2, "meat1": 5, "meat2": 5, "meat3": 5, "flags": 4}[kind])):
                raise AssertionError("Mesen did not cover every %s motion frame and cursor position" % kind)
    return names, {kind: len(frames) for kind, frames in motion_frames.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="directory containing baseline-{classic,shadowed}-font.gbc")
    parser.add_argument("--mesen", type=Path, help="optional Mesen executable")
    args = parser.parse_args()
    output = args.directory.resolve()
    report = {"roms": {}, "captures": []}
    for style in ("classic", "shadowed"):
        baseline = output / ("baseline-%s-font.gbc" % style)
        experimental = output / ("experiment-%s-font.gbc" % style)
        patched, details = debug_room_prototype.install(baseline.read_bytes())
        experimental.write_bytes(patched)
        report["roms"][style] = {
            "baseline_sha1": sha1(baseline.read_bytes()).hexdigest(),
            "experimental_sha1": sha1(patched).hexdigest(), "tiles_used": details["tiles_used"],
            "main_tiles_used": details["main_tiles_used"],
            "weapons_tiles_used": details["weapons_tiles_used"],
            "bracelets_tiles_used": details["bracelets_tiles_used"],
            "scrolls_tiles_used": details["scrolls_tiles_used"],
            "pots_tiles_used": details["pots_tiles_used"],
            "meat1_tiles_used": details["meat1_tiles_used"],
            "meat2_tiles_used": details["meat2_tiles_used"],
            "meat3_tiles_used": details["meat3_tiles_used"],
            "flags_tiles_used": details["flags_tiles_used"],
        }
        for label, rom in (("baseline", baseline), ("experiment", experimental)):
            report["captures"] += capture(rom, output, label + "-" + style)
        capture_motion(experimental, output, style)
        capture_transitions(experimental, output, style)
        if args.mesen:
            allowed = {}
            for kind, checkpoints in (("main", ("root", "main-1", "main-2")),
                                      ("category", tuple("category-%d" % i for i in range(5))),
                                      ("weapons", tuple("weapons-%d" % i for i in range(4))),
                                      ("bracelets", tuple("bracelets-%d" % i for i in range(3))),
                                      ("scrolls", tuple("scrolls-%d" % i for i in range(4))),
                                      ("pots", tuple("pots-%d" % i for i in range(2))),
                                      ("meat1", tuple("meat1-%d" % i for i in range(5))),
                                      ("meat2", tuple("meat2-%d" % i for i in range(5))),
                                      ("meat3", tuple("meat3-%d" % i for i in range(5))),
                                      ("flags", tuple("flags-%d" % i for i in range(4)))):
                allowed[kind] = {menu_hash(Image.open(output / ("experiment-%s-%s.png" % (style, name))), kind): i
                                 for i, name in enumerate(checkpoints)}
                if len(allowed[kind]) != len(checkpoints):
                    raise AssertionError("Cursor position oracles must be distinct")
            names, frames = mesen(args.mesen.resolve(), experimental, output, "mesen-" + style, allowed)
            report["captures"] += names
            report["roms"][style]["mesen_motion_frames_without_flicker"] = frames
            # Compare the complete menu, including every border/cursor pixel.
            # The independently timed dungeon actors outside it may animate.
            for checkpoint in ("flags-back", *("flags-%d" % i for i in range(4)), "root", "main-1", "main-2", "back", "weapons-back", "bracelets-back", "scrolls-back", "pots-back", "meat1-back", "meat1-return-1", "meat1-return-2",
                               *("category-%d" % i for i in range(5)), *("weapons-%d" % i for i in range(4)),
                               *("bracelets-%d" % i for i in range(3)), *("scrolls-%d" % i for i in range(4)),
                               *("pots-%d" % i for i in range(2)), *("meat1-%d" % i for i in range(5)), *("meat2-%d" % i for i in range(5)), *("meat3-%d" % i for i in range(5)), "meat2", "meat2-return", "meat3"):
                paths = [output / ("%s-%s-%s.png" % (engine, style, checkpoint))
                         for engine in ("experiment", "mesen")]
                box = (MENU_BOX if checkpoint.startswith("category") or checkpoint in ("weapons-back", "bracelets-back", "scrolls-back", "pots-back", "meat1-back")
                       else WEAPONS_BOX if checkpoint.startswith("weapons")
                       else BRACELETS_BOX if checkpoint.startswith("bracelets")
                       else SCROLLS_BOX if checkpoint.startswith("scrolls")
                       else POTS_BOX if checkpoint.startswith("pots")
                       else MEAT1_BOX if checkpoint.startswith("meat1")
                       else MEAT2_BOX if checkpoint.startswith("meat2")
                       else MEAT3_BOX if checkpoint.startswith("meat3")
                       else FLAGS_BOX if checkpoint.startswith("flags-") and checkpoint != "flags-back" else MAIN_BOX)
                crops = [Image.open(path).convert("RGB").crop(box) for path in paths]
                if crops[0].tobytes() != crops[1].tobytes():
                    raise AssertionError("Mesen/PyBoy menu raster differs: " + checkpoint)
            report["roms"][style]["mesen_category_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_main_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_weapons_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_bracelets_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_scrolls_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_pots_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_meat1_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_meat2_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_meat3_pixels_match_pyboy"] = True
            report["roms"][style]["mesen_flags_pixels_match_pyboy"] = True
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    motion_rows = []
    for style in ("classic", "shadowed"):
        cells = []
        for version in ("before", "after"):
            if (output / "cursor-motion" / ("%s-%s-00.png" % (version, style))).exists():
                cells.append('<td><img class="motion" data-prefix="cursor-motion/%s-%s-" '
                             'width="416" height="352" src="cursor-motion/%s-%s-00.png"></td>'
                             % (version, style, version, style))
            else:
                cells.append('<td>Earlier ROM capture unavailable</td>')
        motion_rows.append('<tr><th>%s</th>%s</tr>' % (style, ''.join(cells)))
    rows = []
    for style in ("classic", "shadowed"):
        for checkpoint in ("flags-0", "flags-1", "flags-2", "flags-3", "flags-back", "meat3-0", "meat3-1", "meat3-2", "meat3-3", "meat3-4", "meat2-0", "meat2-1", "meat2-2", "meat2-3", "meat2-4", "meat2-return", "meat1-0", "meat1-1", "meat1-2", "meat1-3", "meat1-4",
                           "meat2", "meat3", "meat1-return-1", "meat1-return-2", "meat1-back", "pots-0", "pots-1", "pots-back",
                           "scrolls-0", "scrolls-1", "scrolls-2", "scrolls-3", "scrolls-back",
                           "bracelets-0", "bracelets-1", "bracelets-2", "bracelets-back",
                           "weapons-0", "weapons-1", "weapons-2", "weapons-3", "weapons-back",
                           "root", "main-1", "main-2", "category-0", "category-4", "back", "gameplay", "status", "items", "item-actions"):
            cells = "".join('<td><img width="480" height="432" src="%s-%s-%s.png"></td>'
                            % (label, style, checkpoint) for label in ("baseline", "experiment"))
            rows.append("<tr><th>%s<br>%s</th>%s</tr>" % (html.escape(style), html.escape(checkpoint), cells))
    transitions, weapons_transitions, bracelets_transitions, scrolls_transitions, pots_transitions, meat_transitions, meat2_transitions, meat3_transitions, flags_transitions = [], [], [], [], [], [], [], [], []
    for style in ("classic", "shadowed"):
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-category", "return-main", "exit-main"))
        transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-weapons", "return-category"))
        weapons_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-bracelets", "return-from-bracelets"))
        bracelets_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-scrolls", "return-from-scrolls"))
        scrolls_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-pots", "return-from-pots"))
        pots_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-meat1", "next-meat2", "back-to-meat1", "return-from-meat1"))
        meat_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("next-meat3", "back-to-meat2"))
        meat2_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("cycle-to-meat1", "revisit-meat2", "revisit-meat3"))
        meat3_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
        cells = ''.join('<td><img class="transition" data-prefix="set-flag/%s-%s-" '
                        'src="set-flag/%s-%s-00.png" width="480" height="432"></td>'
                        % (style, name, style, name) for name in ("open-flags", "return-from-flags"))
        flags_transitions.append('<tr><th>%s</th>%s</tr>' % (style, cells))
    batches = [batch for page in (1, 2, 3) for batch in json.loads(
        (ROOT / ("tests/fixtures/debug_meat_page_%d.json" % page)).read_text())["batches"]]
    batch_legend = ''.join('<details><summary>%s — formerly %s</summary><p>%s</p></details>' % (
        html.escape(batch["label"]), html.escape(batch["original_label"]),
        '; '.join(html.escape(item["name"]) for item in batch["items"])) for batch in batches)
    flag_actions = json.loads((ROOT / "tests/fixtures/debug_flags.json").read_text())["actions"]
    flag_legend = '<table><tr><th>Choice</th><th>Native result message</th></tr>' + ''.join(
        '<tr><td>%s</td><td>%s</td></tr>' % (html.escape(action["label"]),
        html.escape(action["message"].replace('<br>', ' ').replace('<page>', ''))) for action in flag_actions) + '</table>'
    page = ('<!doctype html><meta charset="utf-8"><title>Debug menu prototype</title>'
            '<style>body{font:16px system-ui;background:#eee}table{border-collapse:collapse}'
            'td,th{padding:12px}img{image-rendering:pixelated}</style>'
            '<h1>Debug menu prototype</h1><p>Separate experimental ROM. Production build is unchanged. '
            'Main: 72×56 pixels. Categories: 104×88 pixels. Weapons/Shields: 64×72 pixels. Bracelets/Grass: 80×56 pixels. Scrolls/Staves: 64×72 pixels. Pots/Arrows: 56×40 pixels. All three Meat pages: 88×88 pixels each. Set Flag: 104×72 pixels.</p>'
            '<p>ROMs: <a href="experiment-classic-font.gbc">Classic</a> · '
            '<a href="experiment-shadowed-font.gbc">Shadowed</a></p>'
            '<h2>Set Flag</h2><p>Choose Set Flag from the main debug menu. A runs the selected progression preset; B returns to the main menu. '
            'The result messages below explain each action. Moai Leaves changes several progression fields; it is separate from the gift-code unlock helper.</p>'
            + flag_legend + '<h2>All three Meat pages</h2><p>Choose Give Item → Meat, then Next Page twice to reach page 3. Batch counts assume an empty inventory. '
            'Existing items stay in place; each batch fills only the remaining space, in the order shown. '
            'The former range labels follow Japanese names; Batch 12 was labeled Evil Types. Next Page cycles 1 → 2 → 3 → 1. B returns to the preceding page, or from page 1 to categories.</p>'
            + batch_legend + '<h2>Menu transitions</h2><p>Opening and closing all repaired submenus. Playback is slowed to 10 fps.</p>'
            '<button id="transition-play">Play</button> <label>Frame <input id="transition-frame" type="range" '
            'min="0" max="39" value="0"><output id="transition-number">0</output></label>'
            '<table><tr><th>Font</th><th>Main → categories</th><th>Categories → main</th><th>Main → gameplay</th></tr>'
            + ''.join(transitions) + '</table>'
            '<table><tr><th>Font</th><th>Categories → Weapons/Shields</th><th>Weapons/Shields → categories</th></tr>'
            + ''.join(weapons_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Categories → Bracelets/Grass</th><th>Bracelets/Grass → categories</th></tr>'
            + ''.join(bracelets_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Categories → Scrolls/Staves</th><th>Scrolls/Staves → categories</th></tr>'
            + ''.join(scrolls_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Categories → Pots/Arrows</th><th>Pots/Arrows → categories</th></tr>'
            + ''.join(pots_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Categories → Meat 1</th><th>Meat 1 → Meat 2</th><th>Meat 2 → Meat 1</th><th>Meat 1 → categories</th></tr>'
            + ''.join(meat_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Meat 2 → Meat 3</th><th>Meat 3 → Meat 2</th></tr>'
            + ''.join(meat2_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Meat 3 → Meat 1</th><th>Meat 1 → Meat 2</th><th>Meat 2 → Meat 3</th></tr>'
            + ''.join(meat3_transitions) + '</table>'
            '<table><tr><th>Font</th><th>Main → Set Flag</th><th>Set Flag → main</th></tr>'
            + ''.join(flags_transitions) + '</table>'
            '<script>{const slider=document.getElementById("transition-frame"),button=document.getElementById("transition-play");'
            'let timer;function show(){document.getElementById("transition-number").value=slider.value;'
            'document.querySelectorAll(".transition").forEach(img=>img.src=img.dataset.prefix+'
            'String(slider.value).padStart(2,"0")+".png")}slider.oninput=show;button.onclick=()=>{'
            'if(timer){clearInterval(timer);timer=null;button.textContent="Play"}else{'
            'button.textContent="Pause";timer=setInterval(()=>{slider.value=(Number(slider.value)+1)%40;show()},100)}}}'
            '</script>'
            '<h2>Cursor movement, one frame at a time</h2><p>The same Down input in the earlier prototype '
            'and the repaired prototype. Frame 1 exposes the earlier text corruption. Playback is slowed to 10 fps.</p>'
            '<button id="play">Play</button> <label>Frame <input id="frame" type="range" min="0" max="14" '
            'value="0"><output id="number">0</output></label>'
            '<table><tr><th>Font</th><th>Before fix</th><th>After fix</th></tr>' + ''.join(motion_rows) + '</table>'
            '<script>const slider=document.getElementById("frame"),button=document.getElementById("play");'
            'let timer;function show(){document.getElementById("number").value=slider.value;'
            'document.querySelectorAll(".motion").forEach(img=>img.src=img.dataset.prefix+'
            'String(slider.value).padStart(2,"0")+".png")}slider.oninput=show;button.onclick=()=>{'
            'if(timer){clearInterval(timer);timer=null;button.textContent="Play"}else{'
            'button.textContent="Pause";timer=setInterval(()=>{slider.value=(Number(slider.value)+1)%15;show()},100)}};'
            '</script><h2>Settled screens and cleanup</h2>'
            '<table><tr><th>Checkpoint</th><th>Baseline</th><th>Experiment</th></tr>' + ''.join(rows) + '</table>')
    (output / "comparison.html").write_text(page)
    print(output / "comparison.html")


if __name__ == "__main__":
    main()
