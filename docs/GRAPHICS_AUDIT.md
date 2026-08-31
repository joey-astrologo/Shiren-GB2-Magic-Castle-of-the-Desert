# Graphical-text audit

This is the evidence-backed inventory for player-facing text drawn as graphics rather than
ordinary translated script. It records native storage and consumers before any replacement
art is designed. The audit does **not** modify the ROM, choose final fonts, or approve final
English layouts.

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
| 1 | Post-Chunsoft copyright/credit card | Stored tiles plus interleaved tile/attribute map | `$8000` plane is aliased by resource selectors 57 and 58 | Fully traced; English art required |
| 1 | Main title screen logo | Stored multi-VRAM-bank tiles plus full-screen map | All three resources use title selector 0 | Fully traced; English art required |
| 2 | Town/dungeon/floor arrival cards | Runtime composition from a dedicated 16x16 block atlas | 32 selectors, 31 unique sequences; selectors 30/31 alias | Fully traced; English atlas/sequences required |
| 3 | Ending staff roll | Unknown until the live route is captured | Native scenario and music identifiers prove the route exists | Needs main-ending and true-ending states |

The title and credit wording shown below is a working content transcription, not approved
replacement art. Font, capitalization, line division, and exact title treatment remain visual
review decisions.

## Copyright and composer card

### Route and visible content

A clean boot reaches this card immediately after the Chunsoft splash. The native screen reads
as two copyright lines: `© 2001 CHUNSOFT` and a second `© 2001` credit for Koichi Sugiyama.
Whether the English art adds a role such as `Music` must be approved separately; the Japanese
card itself displays his name rather than an English role label.

### Native resources

| Part | Selector / table | ROM source | Runtime destination |
|---|---|---|---|
| Main plane | selector 58, table `05:$6F35` | `2D:$4F12-$5583`; two-byte `$0670` size header plus 1,648 bytes | VRAM bank 0 `$8800` |
| Secondary plane | selectors 57 and 58, table `3F:$4017` | `36:$614A-$626B`; two-byte `$0120` size header plus 288 bytes | VRAM bank 0 `$8000` |
| Tilemap and attributes | selector 104, descriptor `00:$3E0B-$3E0D` | `3B:$7980-$7E81`; 20 columns x 32 rows | `$9820`; interleaved tile/attribute pairs |
| Base palettes 0-6 | map attributes use IDs 0-6 | `17:$58F6-$592D` | Native palette staging/fade path |
| Palette-0 override | credit transition | `F0:$409F-$40A6` | BG palette 0 |

The 32-row map intentionally exceeds the 18 visible rows and participates in the native
transition. Replacement work must retain the fade/scroll behavior instead of flattening only
one captured frame. The secondary plane's duplicate selectors are a real alias; an installer
must either preserve both consumers or prove that it redirects both.

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

## Arrival cards

### Proven composition model

The supplied `SaveStates/Mamel.mss` route can be made deterministic with the existing stairs
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
the second Pot Cave entry. Selectors 30 and 31 point to the same nine-block sequence and have
no matching extracted player-facing location record; they remain explicitly unresolved rather
than being assigned guessed names.

The live Ancient Ruins trace proves selector 2 loads location blocks `11, 12, 13, 14`, then
floor blocks `0, 2, 10` for `2F`. The complete selector/block list is emitted by
`tools/graphics_audit.py` so future artwork can be generated without play-testing all 32
locations.

### Palette behavior

The renderer fills the background with palette 7 and uses palette 6 for the location/floor
blocks. Palette 7 is the complete eight-byte source at `7F:$61E1-$61E8`. The glyph palette
sets its first color from `00:$3AE9-$3AEA` and its last from `7F:$61E7-$61E8`, while its two
middle colors are inherited from the active route. A replacement must therefore be checked
from more than one dungeon/town palette, not only the Mamel state.

### Replacement implications

English does not require widening a menu box here. A future generator can build a private
English block atlas and selector sequences inside the existing 144-pixel maximum location
row, then redirect or replace this exclusive family. It must retain centering, one- and
two-digit floors, palette inheritance, and the flashing transition. Final abbreviations, if
any location exceeds the art budget, require review before insertion.

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
| HUD abbreviations | Observed dungeon HUD uses existing Latin `Lv`/`Hp` and numbers | No new localization target from current evidence |
| Menus and graphical input | Status, name, gift-code, Blank Scroll, unidentified-name, Rescue, and service-menu owners already documented | Do not duplicate them in a new static-art patch |
| Shop/store signs | Japanese characters are environmental signage | Preserve |
| Postgame location cards | Covered structurally by the same 32-selector arrival renderer | Generate/test all selectors when the English atlas is implemented |
| Ending `Fin` | Explicitly accepted in Japanese | Preserve |

## Implementation order

1. Credit/composer card: small, isolated, clean-boot route with exact resources.
2. Main title: larger full-screen art with two VRAM planes and eight palettes.
3. Arrival-card English atlas and 32-selector gallery.
4. Ending credits after the two live states are available.

Each implementation remains subject to [GRAPHICS.md](GRAPHICS.md): editable source art,
licensed font provenance, exact-byte guards, collision checks, static plane/map tests, a live
transition regression, and integer-scale visual approval are required before it is complete.
