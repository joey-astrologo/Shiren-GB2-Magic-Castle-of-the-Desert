# Graphical-text audit

This is the evidence-backed inventory for player-facing text drawn as graphics rather than
ordinary translated script. It records native storage, consumers, and the implementation
state of each family. The audit command itself is read-only; design approval and insertion
remain separate, guarded production steps.

Run the machine-readable audit with:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
python3 tools/graphics_audit.py "$ROM"
python3 -m unittest tests.test_graphics_audit -v
```

The audit reads native resource headers, pointer tables, tile planes, interleaved
tile/attribute maps, and palette sources. It does not create or update framebuffer hashes.

## Scope decisions

| Content | Policy | Reason |
|---|---|---|
| Functional graphical text | Audit and localize | The player must be able to understand titles, locations, and credits |
| Japanese shop/store signs in the environment | Preserve Japanese | The setting is Japan and these signs are environmental art, consistent with the series |
| A Japanese `Fin` mark, if present | Preserve Japanese | Explicitly accepted as an end mark rather than functional instructions |
| Developer scenario/BGM labels | Preserve native | Internal identifiers do not render in a normal release; they are evidence for routes only |

No separate graphical menu-label family was found during the completed menu-action audit.
Generated Status/input assets and the cracked-Bracelet marker already have dedicated owners
listed in [GRAPHICS.md](GRAPHICS.md).

## Results

| Priority | Family | Storage | Variants / sharing | Audit state |
|---:|---|---|---|---|
| 1 | Post-Chunsoft copyright/credit card | Verbatim foreground plane plus a generated tilemap; surrounding transition resources remain native | Two private 16x2-tile name strips inside `F3:$5D00-$64FF` | English art installed, transition-tested, and visually approved |
| 1 | Main title screen logo | Stored multi-VRAM-bank tiles plus full-screen map | All three resources use title selector 0 | Fully traced; English art required |
| 1 | Save/load wait sign | Two stored 64x16 column-major 2bpp sign blocks | Two interleaved 256-byte bird-art blocks are separate and preserved | English art installed and statically pixel-tested; automated live route pending |
| 2 | Town/dungeon/floor arrival cards | Runtime composition from a dedicated 16x16 block atlas | 32 selectors; duplicate Pot Cave and `Mystery Dungeon` pairs share sequences | Approved English atlas installed and live-pixel tested |
| 3 | Ending staff roll | Unknown until the live route is captured | Native scenario and music identifiers prove the route exists | Needs main-ending and true-ending states |

The title wording shown below remains a working content transcription rather than approved
replacement art. The credit-card wording and Inter-based treatment have been approved and
installed; the title's font, capitalization, line division, and exact treatment remain visual
review decisions.

## Copyright and composer card

### Route and visible content

A clean boot reaches this card immediately after the Chunsoft splash. The approved English
screen preserves both native `© 2001` rows byte-for-byte and replaces only the two name rows
with `CHUNSOFT` and `Koichi Sugiyama`. It does not add a role such as `Music`, because the
Japanese card displays his name rather than an English role label.

### Visible native foreground and map

A live source-to-VRAM comparison corrected the initial static attribution: the stable visible
lettering is the 2,048-byte foreground plane at `F3:$5D00-$64FF`, copied verbatim to VRAM bank
1 at `$8800-$8FFF`. The boot code generates its map directly. The resource-selector family in
the following table is still part of the surrounding transition, but it is not the stable
name lettering and is not changed by the English installer.

| Part | Native contract | Production treatment |
|---|---|---|
| Foreground plane | selector 24; pointer `F0:$40EF-$40F1`; length byte `F0:$410A`; `F3:$5D00-$64FF` -> VRAM bank 1 `$8800-$8FFF` | Preserve the complete plane except the two guarded name strips |
| `CHUNSOFT` strip | tiles `$A0-$BF`; `F3:$5F00-$60FF`; screen rectangle `(16,56)-(143,71)` | Replace exactly 512 bytes |
| `Koichi Sugiyama` strip | tiles `$E0-$FF`; `F3:$6300-$64FF`; screen rectangle `(16,88)-(143,103)` | Replace exactly 512 bytes |
| Visible tilemap | producer `F0:$4057-$409E`; tile IDs `$80-$FF`; destination `$9800`; attribute fill `$08` selects VRAM bank 1 | Preserve |
| Stable scroll | `SCX=$F0`, `SCY=$D8` | Preserve |
| Palette-0 override | `F0:$409F-$40A6` | Preserve the native fade |

### Surrounding transition resources

| Part | Selector / table | ROM source | Runtime destination |
|---|---|---|---|
| Main plane | selector 58, table `05:$6F35` | `2D:$4F12-$5583`; two-byte `$0670` size header plus 1,648 bytes | VRAM bank 0 `$8800` |
| Secondary plane | selectors 57 and 58, table `3F:$4017` | `36:$614A-$626B`; two-byte `$0120` size header plus 288 bytes | VRAM bank 0 `$8000` |
| Tilemap and attributes | selector 104, descriptor `00:$3E0B-$3E0D` | `3B:$7980-$7E81`; 20 columns x 32 rows | `$9820`; interleaved tile/attribute pairs |
| Base palettes 0-6 | map attributes use IDs 0-6 | `17:$58F6-$592D` | Native palette staging/fade path |
| Palette-0 override | credit transition | `F0:$409F-$40A6` | BG palette 0 |

The 32-row map intentionally exceeds the 18 visible rows and participates in the native
transition. These resources and the secondary plane's real selector alias remain byte-exact.
The English installer does not flatten a captured frame or redirect them.

### English asset and verification

The editable four-level source is `assets/graphics/credit_screen_inter.json`, generated by
`tools/credit_screen_mockup.py` from Inter SemiBold 4.1 under the SIL Open Font License 1.1.
`tools/credit_screen.py` exact-hash guards both native strips, encodes the approved 128x16
pixel rows to 2bpp tiles, and owns no other graphical bytes. The independent production
regression first failed against the native ROM at 1,382 name-band pixels. It now compares
actual pixels at fade frames 280, 300, 320, 440, and 480, preserves every pixel before the
card and at the title handoff, and does not use or update a framebuffer hash.

## Save/load wait sign

The native sign reads `しばらく おまちください`, or “Please wait a moment.” The user-observed
route loads an in-game state, chooses `Quit` to suspend, and then reloads that save. The
existing automated `Mamel` route resumed directly instead of displaying the sign, so this
audit does not claim an emulator reproduction that has not occurred.

The supplied native screenshot nevertheless maps exactly to a stored 64x32 sign raster at
screen rectangle `(33,74)-(96,105)`. Its tiles are split across two column-major 2bpp blocks:

| Part | ROM source | Production treatment |
|---|---|---|
| Top sign rows | `56:$7A80-$7B7F` | Replace exactly 256 bytes |
| Upper bird art | `56:$7B80-$7C7F` | Preserve and exact-hash guard |
| Bottom sign rows | `56:$7C80-$7D7F` | Replace exactly 256 bytes |
| Lower bird art | `56:$7D80-$7E7F` | Preserve and exact-hash guard |

The editable four-level source is `assets/graphics/wait_screen.json`. It renders approved
Thin Pixel-7 text as `Please` / `wait...` with the native-style one-pixel gray shadow while
retaining all sign pixels outside the bounded text regions. `tools/wait_screen.py` owns only
the two sign blocks and fails closed if either sign source or either preserved bird block
changes. The independent production regression was written first and failed against the
current ROM at 330 pixels; it now decodes production tiles independently and compares the
complete sign raster without accepting or updating a framebuffer hash. A live route capture
remains the final visual check.

## Title screen

### Route and visible content

The card transitions into the main title. The functional title content is *Mystery Dungeon*,
*Shiren the Wanderer GB2*, and *Magic Castle of the Desert*. The logo, subtitle, `GB2`, desert
background, and animation share one composed screen, so the Japanese pixels cannot be treated
as a standalone line of ordinary VWF text.

### Native resources

| Part | Selector / table | ROM source | Runtime destination |
|---|---|---|---|
| `$8800` plane | selector 0, table `05:$6F35` | `1C:$4000-$5421`; `$1420` bytes after the header | First `$0420` bytes to VRAM bank 1, then `$1000` to bank 0 at `$8800` |
| `$8000` plane | selector 0, table `3F:$4017` | `31:$4000-$4B01`; `$0B00` bytes after the header | First `$0300` bytes to VRAM bank 1, then `$0800` to bank 0 at `$8000` |
| Tilemap and attributes | selector 0, descriptor `00:$3CD3-$3CD5` | `38:$4000-$42D1`; 20 columns x 18 rows | Full visible map at `$9800` |
| Palettes 0-7 | attribute IDs 0-7 | `17:$416F-$41AE` | Eight complete CGB BG palettes |

The screen is exactly 20x18 tiles. Animated birds are presentation art rather than an
additional textual variant. No alternate title-logo selector was observed: both graphics
tables and the tilemap table use selector 0 for this family. Title-menu/save-summary text is a
different ordinary/generated-text system and is already covered by its existing tests.

`tools/title_animation_vignette.py` captures every emulator frame from 600 through 659 by
default, producing a labeled 60-frame contact sheet and a nearest-neighbor one-second GIF.
This replaces the earlier eight-frame still survey, which skipped too much motion for title-art
mockups. GIF centisecond timing is distributed across frames so the full pass remains exactly
one second even though the format cannot encode 60 Hz with one constant delay.

## Arrival cards

### Proven composition model

The supplied `SaveStates/Mamel.state` route can be made deterministic with the existing stairs
setup: clear the nearby Mamel, place Shiren beside the generated stairs, choose `Proceed`, and
capture the transition. The next floor flashes `Ancient Ruins` and `2F` in Japanese before the
new floor appears.

This family is not one bitmap per floor and is not ordinary VWF text. Bank 127's renderer
loads a sequence selected by `$C12C`, copies one 64-byte 2x2-tile block per sequence element,
centers the generated row, formats the floor from `$C130`, and flashes the generated map.

| Part | ROM source | Contract |
|---|---|---|
| Renderer | `7F:$4000-$41E0` | Selects location, loads glyph blocks, centers rows, formats floor, controls flash |
| Shared block atlas | `7F:$41E1-$61E0` | 128 blocks x 64 bytes; each block is 2x2 tiles / 16x16 pixels |
| Selector pointer table | `7F:$61E9-$6228` | 32 little-endian pointers |
| Variable sequences | `7F:$6229-$62EE` | 31 unique sequences; maximum nine blocks |
| Background map | Generated | 32 columns x 18 rows are cleared; 20 columns are visible |
| Floor suffix | Generated from the same atlas | Zero-suppressed two digits plus native `F` block |

Selectors 0-29 align with the translated history-location family from Town of Ilpa through
the second Pot Cave entry. Selectors 30 and 31 point to the same nine-block sequence. Direct
2bpp decoding of those nine native blocks reads `不思議のダンジョン`, resolving both as
`Mystery Dungeon` without guessing from an unrelated script record.

The live Ancient Ruins trace proves selector 2 loads location blocks `11, 12, 13, 14`, then
floor blocks `0, 2, 10` for `2F`. The complete selector/block list is emitted by
`tools/graphics_audit.py` so future artwork can be generated without play-testing all 32
locations.

### Font audition sheet

`tools/arrival_card_audition.py` renders every selector as a native-sized 160x144 card and
assembles the results into a contact sheet. It accepts any TTF/OTF/TTC, a cap height, and
either the native-style three-shade antialiasing treatment or a solid one-bit treatment. The
layout comes from the captured Ancient Ruins 2F route: location band y=40-55, block-snapped
red underline at y=57, floor band y=73-88, and a 144-pixel label maximum.

The default command uses the bundled Inter SemiBold candidate at an 11-pixel cap only as an
immediately runnable comparison. At 12 pixels, Inter genuinely needs 17 vertical pixels for
several descender-bearing labels, and the tool flags those cells instead of clipping them.
Representative floors cycle through `1F`, `2F`, `9F`, `10F`, `19F`, `50F`, and `99F` so all
digit shapes are visible. The approved audition raises the native `F` one pixel for optical
alignment, and the bottom of the sheet magnifies `1F`-`9F`, `10F`, `11F`, and `99F` so the
shared suffix is easy to inspect. Selectors 30 and 31 both render their proven
`Mystery Dungeon` label.

```sh
python3 tools/arrival_card_audition.py
python3 tools/arrival_card_audition.py \
  --font "/path/to/Candidate.ttf" \
  --output build/arrival_cards_candidate.png
python3 -m unittest tests.test_arrival_card_audition -v
```

The sheet itself does not modify the ROM. With `--asset-output`, the same renderer freezes the
approved block-aligned JSON source consumed by `arrival_cards.py`; the committed production
asset is `assets/graphics/arrival_cards_inter.json`.

### Production insertion

`arrival_cards.py` clones the guarded native `7F:$4000-$41E0` renderer at the same CPU
address in dedicated bank `$F8`. Only its same-bank atlas, pointer, sequence, and palette
operands are redirected. The native entry receives a nine-byte far-call wrapper, while
centering, zero-suppressed floor formatting, red underline, inherited middle palette colors,
fade, and new-floor handoff remain the original code.

The private atlas contains 217 blocks: ten byte-exact native Latin digit blocks, the approved
native-derived `F` raised one pixel, and 206 approved English label blocks. Thirty unique label records cover all 32 selectors; the two Pot Cave selectors and
the two Mystery Dungeon selectors intentionally share their respective sequence pointers.
Every runtime block is independently decoded back to the approved pixels, every floor from
`1F` through `99F` is recomposed, and the natural Mamel stairs route compares live
`Ancient Ruins` / `1F` and `2F` cards without a framebuffer hash. A separate live-pixel
regression compares the `1` and `F` bright-cap rows directly. The floor source at
`7F:$41E1-$44A0` is independently decoded into
`assets/graphics/arrival_floor_native.json` and re-encodes byte-for-byte before the declared
`F y=-1` production adjustment, preventing a location-font raster or neighboring digit from
contaminating the shared suffix block.

### Palette behavior

The renderer fills the background with palette 7 and uses palette 6 for the location/floor
blocks. Palette 7 is the complete eight-byte source at `7F:$61E1-$61E8`. The glyph palette
sets its first color from `00:$3AE9-$3AEA` and its last from `7F:$61E7-$61E8`, while its two
middle colors are inherited from the active route. A replacement must therefore be checked
from more than one dungeon/town palette, not only the Mamel state.

### Replacement implementation

English does not require widening a menu box here. The installed private atlas keeps every
label inside the existing 144-pixel maximum; `Training Dungeon` is widest at 131 pixels and
uses the maximum nine blocks. Any later wording or font change must regenerate the editable
asset and repeat the all-selector decoder plus live transition regression.

## Dungeon HUD font

The top dungeon status bar is a dedicated packed font, not the localized proportional text
font and not a set of independent tilemap characters. The Mamel machine state shows window
tile IDs `$10-$23` with VRAM-bank-1 attributes across the top row. The bank-3 compositor
formats 40 four-pixel slots in `$C800-$C827`, expands them into the 20-tile strip at
`$D100-$D23F`, and copies that strip to VRAM bank 1 `$9100-$923F`.

The complete guarded source is 16 8x8 2bpp tiles at `3:$5742-$5841` (SHA-256
`3ea78ca67f1364b85de7fe4971886ae3bc76bcd643837504cc22be5e839704a1`). Its first ten tiles
pack two four-pixel slots each:

- `0-9A-F` in slots `$00-$0F`;
- `L`, `v`, `H`, and `p` in slots `$10-$13` for the literal `Lv` / `Hp` labels;
- the two halves of `/` in slots `$14-$15`;
- meter fill/cap art in tiles `$FB-$FC`;
- reserved blank tiles `$FD-$FF`.

Production installs the approved player-supplied decimal and slash rasters from
`assets/fonts/hud_digits.json` into two discontiguous regions: the first five tiles and slash
tile ten. The asset freezes the SHA-256 of `hud edits.webp`, its ten-cell digit crop
(`1234567890` at x=1, y=0), and its separate 8x8 slash crop at x=0, y=7. The ten other tiles
are required to stay byte-exact native.

Normal play has only demonstrated decimal numbers, `F`, `Lv`, and `Hp`; `A-E` remain
included in the audition because they are real, distinct alphanumeric slots in the same
source. The read-only tool accepts either the verified native atlas or the exact installed
digit/native-tail combination and renders every slot, symbol, and native-width status proof:

```sh
python3 -m unittest tests.test_hud_font_audition -v
python3 tools/hud_font_audition.py
```

The default output is `build/hud_font_audition.png`. Tests freeze the source-image identity,
all ten approved digit rasters, the approved slash geometry, literal `F/L/v/H/p` pixels,
distinct nonempty alphanumeric slots, maximum proof width, sheet geometry, CLI output, exact
discontiguous ownership, and fail-closed behavior after any unapproved atlas mutation.

## Ending and credits

The ROM provides two independent native clues:

- scenario group 14 selector 27 at `C2:$7111` is labelled `Town 7 staff telop`;
- BGM group 25 selector 38 at `C3:$432C` is labelled `Staff Roll`.

Those are internal developer identifiers and must remain native. They prove a staff-roll
route exists, but they do not prove how its visible names are stored. A public full-game
walkthrough also separates a main ending and later true ending, which is useful route
corroboration but not a substitute for a ROM/VRAM trace:
[GB2 digest and ending timestamps](https://www.youtube.com/watch?v=RLu5OtIm-pM).

The ending family therefore remains `live_route_required`. The needed fixtures are disposable
save states immediately before:

1. the main ending; and
2. the true ending.

For each route, the audit must capture the complete roll, determine whether each credit is
stored art, generated tilemap text, or ordinary VWF text, trace its palettes and transitions,
and identify whether both endings share the same credit resources. A Japanese `Fin` mark may
remain unchanged by explicit project policy.

## Other reviewed categories

| Candidate | Finding | Disposition |
|---|---|---|
| Opening chase/cinematics | Existing opening tests prove ordinary dialogue rendering, but do not constitute a frame-by-frame graphical-text inventory | Keep on the visual play-test watch list; no separate asset claimed yet |
| HUD abbreviations | Dedicated packed atlas `3:$5742-$5841`; approved decimal digits and slash are installed while native labels, meter art, and reserved cells remain guarded | Digit/slash localization complete; retain the read-only audition for source and production review |
| Menus and graphical input | Status, name, gift-code, Blank Scroll, unidentified-name, Rescue, and service-menu owners already documented | Do not duplicate them in a new static-art patch |
| Shop/store signs | Japanese characters are environmental signage | Preserve |
| Postgame location cards | Covered by the installed 32-selector arrival renderer | Continue rare-route playtesting; all selectors are statically pixel-tested |
| Ending `Fin` | Explicitly accepted in Japanese | Preserve |

## Implementation order

1. Main title: larger full-screen art with two VRAM planes and eight palettes.
2. Ending credits after the two live states are available.

Each implementation remains subject to [GRAPHICS.md](GRAPHICS.md): editable source art,
licensed font provenance, exact-byte guards, collision checks, static plane/map tests, a live
transition regression, and integer-scale visual approval are required before it is complete.
