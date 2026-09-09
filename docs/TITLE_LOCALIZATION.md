# Installed localized title

The approved [audition](TITLE_LOCALIZATION_AUDITION.md) is installed by the normal
production build in both font variants. The supplied artwork remains unchanged in
`assets/graphics/GB2 Title Graphics/`. The title reads **Magic Castle of the Desert**,
as confirmed by the user.

The composition includes the complete English logo, castle, circular moon animation,
top-center bat, moon-side bat, sky gradient, horizon gap, and sand. The small bat is
raised 12 pixels above its original position so it clears `Mystery Dungeon`. All eight
supplied subtitle sparkle frames are retained.

## Appearance and timing

The source is 160×143, aligned with native screenshot rows 1–143. Preserve its authored
coordinates and repeat its final sand row to fill the 160×144 display. Native moon and
bat coordinates therefore move up one row; the small bat receives the additional
12-pixel adjustment. No authored scenery is cropped or rescaled.

CGB palettes use five bits per channel. The source ink `(3,3,3)` is explicitly mapped
to native `(8,8,8)`, and white `(255,255,255)` to `(248,248,248)`. Other source colors
are already representable. These are the only palette normalizations.

| Animation | Native frames | Approximate time |
|---|---:|---:|
| Each of four moon phases | 6 | 0.100 s |
| Full original bat cycle, 24 states | 96 | 1.607 s |
| Each of eight sparkle phases | 10 | 0.167 s |
| Complete sparkle sweep | 80 | 1.339 s |
| Rest after the sweep | 160 | 2.679 s |
| Complete sparkle cycle | 240 | 4.018 s |

The first sparkle begins after 60 native frames. Moon, bats, and sparkle have independent
VBlank clocks. Native bat descriptors use a countdown of three, meaning four displayed
frames per state; the inserted motion is compared against an independently captured
96-frame original-ROM cycle.

## Build and review

```sh
python3 tools/build.py \
  'Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc' \
  script/en build/shiren-gb2-english.gbc --font-style both
python3 tools/title_screen_capture.py \
  --rom build/shiren-gb2-english-shadowed-font.gbc
open build/title-screen/index.html
python3 -m unittest tests.test_title_screen -v
python3 tools/title_screen_mesen.py \
  --rom build/shiren-gb2-english-shadowed-font.gbc \
  --mesen /Applications/Mesen.app/Contents/MacOS/Mesen
```

The capture command cold-boots a temporary copy of the actual production ROM, verifies
480 consecutive frames against the source composition, then presses Start and checks
the menu handoff. It writes a lossless-color GIF, title and menu PNGs, a self-contained
HTML preview, and a manifest with the ROM digest. The GIF uses cumulative centisecond
timing: its 480 native frames occupy 8.04 seconds. PyBoy saving is disabled.

The optional Mesen command independently checks 480 frames, follows a natural attract
replay back to the title, checks the returned pixels, and presses Start to reach the menu.
It uses a temporary portable copy of the emulator and ROM, so settings and incidental
save files stay isolated. Its manifest and PNG checkpoints are in `build/title-screen/mesen/`.
The companion Lua script uses the installed emulator's `emu.stop(0)` exit API and needs
no Lua file or network access. Mesen is not a dependency of the production build or suite.

For an isolated title patch, `tools/title_screen.py --rom INPUT --output OUTPUT` uses
the same installer as the production build.

## Graphics compiler and renderer

`tools/title_graphics.py` combines source PNGs with the guarded native moon, castle
overlays, and gradient. `assets/graphics/title_screen/packing.json` records the approved
source hashes and solved palette/sprite allocation. The normal build is deterministic
and needs Pillow; it does not run an optimization solver or require an assembler.

The compiler uses 326 background tiles, 43 correction sprites, and 150 object tiles
including native bats and sparkle. It proves every reconstructed pixel against the
normalized source. Horizontal palette bands allow the original 8×8 tile geometry to
represent the supplied artwork without reducing its colors. The runtime uses 61 STAT
events per frame: a short sky handler in fixed WRAM, HBlank attribute transfers and
palette changes, and reuse of retired OAM slots for lower artwork and sparkle. At most
40 objects are resident and no scanline exceeds the CGB limit of ten objects. Two
sprites reproduce each sparkle frame, including the small yellow change in phase six.

Palette writes are split into four-byte transfers on lines 108–113, and the two sparkle
OAM records are replaced on lines 34 and 37, which have no attribute DMA. Mesen exposed
late writes when an eight-byte palette transfer or a four-byte OAM update shared too much
HBlank time with DMA. The final schedule matches both emulators exactly. VBlank copies
the static OAM template directly from ROM using the original HRAM DMA routine at `$FF82`,
then writes the bats to OAM. This removes a 148-byte CPU copy and keeps the earliest sky
interrupts on time even when moon and sparkle updates coincide.

`tools/title_screen_runtime.py` emits the LR35902 code and tables. Banks 245–247
(`$F5–$F7`) are reserved exclusively. Original title graphics remain read-only source
evidence; only their selector-zero pointers, title palettes, and guarded runtime hooks
are redirected. The installer rejects altered source resources, unexpected hook bytes,
or any occupied byte in the three reserved banks. Reinstallation is byte-identical.
See [ROM_BANK_MAP.md](ROM_BANK_MAP.md) for exact ownership.

## Scene lifetime and transition checks

The renderer is active only when display mode `$C0E5` is 9 **and** scene `$C3B4` is `$9D`.
Attract startup briefly retains mode 9 after releasing title scratch, so mode alone is
insufficient. That interval uses a ROM-resident copy of the original gradient handler.
All other display modes delegate to the native interrupt dispatcher. The shared return
at `0:$081C-$081E` is preserved because another raster mode also uses it.

Title state uses fixed WRAM `$C800-$C805`, `$C880-$C8DF`, and `$C900-$C9DF`. This aliases
the localized keyboard navigation buffer only while the title owns the scene. Entry
clears state and stages the fast handler again; departure stops accessing it. The native
mode setter's BC/DE/HL preservation is retained, including the script cursor used by
attract recordings. No persistent save layout or SRAM is changed.

Seven focused tests cover source composition, guarded/idempotent installation, mutation
ownership, graphics budgets, 480 exact rendered frames, original bat motion, moon/sparkle
timing, Start/menu handoff, and a natural attract replay followed by return to the title.
The native menu comparison excludes only its blinking selection arrow. Attract recordings
have different durations and may be selected differently because initialization changes
RNG timing; the regression follows the selected recording through its natural return.

The production copyright test preserves every original fade checkpoint and compares its
title handoff with an isolated title installation at the same frame. The production diary
menu test retains its original framebuffer hash on a control with the title restored,
compares all surrounding pixels, and requires the shifted selection arrow to match a
captured native animation phase. No existing menu framebuffer fixture was rewritten.

Both exact font ROMs have live pixel and transition evidence from PyBoy and Mesen.
Physical-cartridge behavior still benefits from playtesting, particularly the HBlank
palette and OAM timing.
