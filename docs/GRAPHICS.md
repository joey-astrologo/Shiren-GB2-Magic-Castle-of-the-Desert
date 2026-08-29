# Graphics localization

Full graphics localization is a project requirement and remains active work. This document
separates what is already engineered from what still needs an inventory, translation, and
visual acceptance pass.

## Proven storage model

GB2 graphics are uncompressed. A clean PyBoy title-screen capture found 261 of 270 nonblank
VRAM tiles verbatim in the ROM. The dense high-entropy banks seen during early triage are
ordinary art, not a compressed stream, so no general decompressor is needed before editing
graphical Japanese.

This does not mean every visible screen is one stored bitmap. A route may combine raw tile
planes, a tilemap, attributes, palette selection, numbers, and text drawn by the native VWF.
Each asset still needs its producer and consumers mapped.

## Already localized or engineered

| Area | State | Owner |
|---|---|---|
| In-game proportional font | Thin Pixel-7 installed in native one-byte font slots | `english_font.py` |
| Core Status template labels | English clone generated without mutating shared native graphics | `menu_graphics.py` |
| Player-name keyboard | English A-Z/a-z/0-9 map and glyph resources | `name6.py` |
| Big Moai spell keyboard | English A-Z/0-9 map and glyph resources | `spell_input.py` |
| Blank Scroll keyboard | English A-Z/a-z/0-9 map, 11-character full-name input, and mode-specific hyphen cell | `blank_scroll.py` |
| Unidentified-item keyboard | English map, dedicated mode-0 navigation, `FILL IN` history control, and full canonical-name display aligned to the native seven-cell field | `unidentified_names.py` |
| Stairs popup geometry | Widened templates and background teardown | `stairs_menu.py` |
| Cracked-Bracelet marker | Stock Japanese `(hibi)` composite replaced by compact `(Cr)` at native token `F2 1E` | `item_status.py` |
| Item-row status gallery | Equip, curse, blessing, plate, cracked, synthesis color, and combined states reproduced on demand | `mesen_item_formatting_gallery.lua` |

These are not evidence that title art, story cards, ending art, or every graphical menu label
is localized.

## Inventory still required

The graphics pass should explicitly audit at least:

- publisher/copyright and boot cards;
- title logo and title-state variants;
- opening chase/cinematic graphical text;
- town, dungeon, floor, and arrival banners;
- HUD abbreviations or labels not drawn through the localized text font;
- menu icons, category art, status marks, and explanatory diagrams;
- spell/name editor decorative labels outside generated maps;
- ending cards, credits, and end marks;
- postgame/alternate-route graphics;
- Super Game Boy or DMG assets only if later evidence shows the CGB-only ROM consumes them
  (the cartridge header currently says CGB-only and no SGB support).

For each candidate, record the screen/route, ROM range, tile dimensions, tilemap/attribute
source, palette, sharing/aliasing, and whether the asset is stored or composed.

## Asset workflow

1. Capture the native screen and identify the exact visible Japanese pixels.
2. Trace VRAM tiles/tilemap/attributes back to ROM and native code.
3. Determine every consumer before replacing a shared asset.
4. Keep editable source artwork under `assets/graphics/` and include license/provenance notes
   for any external font or art source.
5. Build a deterministic installer with exact source hashes and collision checks.
6. Reserve its ROM range in [ROM_BANK_MAP.md](ROM_BANK_MAP.md).
7. Add a static plane/tilemap test plus a live route/screenshot regression.
8. Inspect at integer zoom in the emulator and verify every palette/state variant.

Prefer source rasters or explicit tile masks over opaque hand-edited ROM blobs. The source
asset should make the intended English artwork reviewable without opening a hex editor.

## Shared-asset rule

Do not mutate a shared native template until every consumer is mapped. The Status-menu red
window/palette regression demonstrated that visually identical entry routes can have different
redraw ownership. When only some consumers are owned, clone the asset into an exclusive bank
and redirect those consumers, as `menu_graphics.py` does.

## Font choices

Thin Pixel-7 is the approved in-game text font. Graphical title, banner, and credit artwork
may use different fonts when that better matches the native composition. Record each font's
license and keep its choice independent from the VWF metrics unless the asset truly shares the
runtime font.

## Acceptance criteria

A graphical family is complete only when:

- all native variants and routes are inventoried;
- English source artwork is committed and reproducible;
- the installer is exact-byte guarded and collision-checked;
- tile planes, maps, attributes, and palettes pass automated checks;
- live routes show no Japanese text, clipping, stale tiles, wrong palettes, or transition
  remnants;
- the result is visually approved at integer scale;
- the project status and bank map are updated.

Until that inventory is complete, project status must continue to say that graphics
localization remains unfinished.
