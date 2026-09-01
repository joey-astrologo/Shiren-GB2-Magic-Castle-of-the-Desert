# Regression fixtures

This directory contains compact JSON/TSV contracts for extraction, translation, layout,
patch installation, and production builds. The matching Japanese ROM and complete
extracted script are never stored here. A few foundational codec/extraction fixtures keep
small reviewed Japanese anchors because those characters are the evidence for the mapping.

Fixture families include:

| Area | Representative files |
|---|---|
| Source graph and allocation | `script_directory.json`, `script_allocation.json`, `identity_insert.json` |
| Encoding and fonts | `control_dispatch.json`, `kanji_map.json`, `font_trace.json`, `english_font.json`, `item_status.json`, `item_formatting.json`, `synthesis_lab.json` |
| Translation workspace | `english_overlays.json`, `translation_lint.json`, `translation_build.json` |
| Item terminology | `item_terminology.json` |
| Runtime layout | `text_layout.json`, `runtime_terms.json`, `runtime_widths.json`, `positioned_surfaces.json` |
| Dialogue and messages | `prose_scenes.json`, `prose_wrap.json`, `item_message_wrap.json`, `combat_messages.json` |
| Menus and patches | `main_menu_graphics.json`, `menu_text.json`, `stairs_menu.json`, `service_menus.json`, `name6.json`, `blank_scroll.json`; all fourteen embedded replay diaries plus live mode-0 and Adventure navigation contracts |
| Proof-of-concept route | `poc_dungeon1.json`, `prose_opening.json` |

ROM integration tests skip when the clean source ROM is absent or has the wrong SHA-1.
Emulator tests skip when PyBoy is unavailable. RGBDS source-equivalence tests skip when
`rgbasm`/`rgblink` are unavailable. A release-strength run should install all optional
dependencies so those skips disappear.

The committed `SaveStates/Mamel.mss` is the Mesen reproduction input for the nested-combat
route. Its extracted `SaveStates/Mamel.srm` is ignored. Recreate it with:

```sh
python3 tools/mesen_state.py SaveStates/Mamel.mss SaveStates/Mamel.srm
```

`SaveStates/blank-scroll.mss` is the self-contained, exact populated-inventory confirmation
state for the Blank Scroll restart regression. `tests.test_mesen_blank_scroll` verifies its
SHA-1, confirms `Windblade` through Mesen, and requires conversion without a reset or
inventory damage. When the user-supplied ignored `blank-scroll.srm` sidecar is present, the
test also verifies its SHA-1 and loads it; the immediate regression does not depend on it.

`SaveStates/unidentified-item-naming.mss` freezes the Rabbit Scroll Name / `FILL IN`
editor route. `tests.test_unidentified_names` verifies its SHA-1, the private type `$F4`
navigation graph, canonical preview/free-entry transitions, and return to Items. The
separate Adventure submenu regression reuses `Mamel.mss` so the same patch must also prove
that native type `$13` still drives Continue/Secrets/Reset/Recap.

`SaveStates/broken-bracelet.mss` freezes the item-list report where the native `F2 1E`
suffix appeared as corrupt mixed-language graphics. `tests.test_item_status` verifies the
state's SHA-1/SHA-256, forces a fresh Items redraw in Mesen, and freezes the localized `(Cr)`
framebuffer. Its static companion proves the replacement remains inside the original
14-pixel advance and every translated item-name shape remains within the 144-pixel row.

`SaveStates/big-moai-locked.mss` freezes the real NPC before his spell system becomes
available. `tests/fixtures/big_moai.json` records the state hash, active/shadow stage pair,
both observed native SRAM mirrors, dialogue selectors, reviewed localized prompt/editor
framebuffers, `WISH` bytes, and Fortune Grass item ID. `tests.test_big_moai` preserves the
locked route, proves the distributable helper changes only the two measured progression
bytes, and replays the accepted code through controller input. The fixture freezes the
approved four-row keyboard plus separate `DEL`-selected and auto-`OK` framebuffers, proving
both underlines remain below their labels. It also freezes the two-line Fortune Grass reward
framebuffer and requires a subsequent group `$6A`/`$1A` conversation, preventing inventory
insertion from masking a post-reward engine lock.

`tests/fixtures/rescue_requester.json` freezes the Rankings and generated-SOS requester
states. `tests/fixtures/rescue_entry.json` freezes
`SaveStates/rescue-entry-menu.mss`, the localized mode-8 keyboard, the published
`OEN936H9n!FVv` vector, its exact native input bytes, and the deterministic native-validator
return for this nonmatching diary. It also freezes
the physical hardware-B path: the route enters `AB`, deletes `B`, and requires both native
`30 D5...FF` and an unchanged uppercase-`A` glyph band. This covers the dedicated native
event handler rather than inferring behavior from the on-screen `DEL` node. The obsolete
already-active Japanese-editor repair state is not a test input.
The captured state happens to retain `$C195=$08`; the controller route intentionally writes
mode 0 to that previous-mode byte before opening Password. The actual constructor must use
incoming register C and publish mode 8 itself. This prevents the fixture from making the
old, production-broken `$C195`-based screen wrapper pass.
The native-validator result is an input/submission regression, not a complete accepted
rescue; the two-diary Revival/Thank-You fixture remains separate work.

The requester fixture also records the manually accepted localized SOS
`I3CqdGY6iuyws`. It decodes to Ancient Ruins 1F with diary ID `$1234`, distinct from the
test rescuer diary, and was accepted through the localized 13-character editor on
2026-08-29. The static regression freezes the English/native mapping, payload, checksum,
and semantic fields. This is evidence of an accepted SOS input, but it is not yet a
controller-replayed end-to-end rescue completion fixture.

The same fixture freezes requester-side Revival response `SVgaVwAhmUmoM3u`, which is
bound to captured SOS `26pCdewCg2640`. The Mesen route reaches the mode-7 English editor
without direct memory writes, enters all 15 characters, confirms the native success
message, and freezes generated Thank-You Password `EkWsMPtHHOEE`. The route also freezes
the early mode-7 constructor ordering: bank 16 calls its screen before native `$C195` is
initialized, so the guarded English wrapper must consume and preserve incoming register C.
This closes the
requester response-input/presentation loop; physically traversing a Rescue Gate and
capturing the rescuer's own generated response remains the next two-diary fixture.

`tests/fixtures/service_menus.json` freezes the ordered bank-254 service-menu extension,
all label widths, and all five live menu routes. `SaveStates/rescue-entry-menu.mss` is backed
out and rebuilt before checking the native Yes/No confirmation, the clean 56-pixel Rescue
Team interior (48 pixels of label space after its cursor column) in the
confirmation-selected VRAM bank, and the dismissed framebuffer;
`SaveStates/warehouse-menu.mss` (SHA-1
`fffcb9be39418f23e85ae275de6cb86e898afec7`) opens the warehouse conversation and popup
from gameplay. `SaveStates/bank-teller.mss` (SHA-1
`6c3624401afda7107da79247ca6e67cf6a471e9a`) opens the Bank Teller conversation and its
Deposit/Withdraw/Balance/Quit popup.
`SaveStates/blacksmith-info.mss` (SHA-1
`ca57bccc502776a878a1901c2ddfd8479ed0afc1`) opens the native Blacksmith menu, selects
Info, and rebuilds the Forge/Repair/Synthesis/Remove/Quit submenu. All routes capture every
original tile/attribute pair under the added right column, require each border cell while
open, and require exact restoration after B.
They also traverse every menu option and freeze every cursor framebuffer. Warehouse and Bank
keep tile `$B3` in every seventh interior cell. Blacksmith Info stages the last `Synthesis`
tile in `$B3`, clears the aliased unselected Quit cursor tile, maps every spill through the
active VRAM bank, keeps `$B9` blank in the other spills, and restores `$B3` after B. Rescue
uses `$A8/$BA` only in the two physical rows containing `Password`'s final pixel column in
its shorter three-entry frame. The completed-rescue selector instead stages those fragments
in off-frame `$9C/$AE`, clears `$A8/$BA`, overwrites them in the regression, and then visits
all four live cursor positions. Its dedicated 5x8 raster check requires the final `d` at the
original coordinates and rejects cursor graphics in either wrong column; Blacksmith has an
independent 45x8 raster check for `Synthesis` plus literal blank 8x8 cells to the left and
right of unselected `Quit`. This specifically guards clipping, cursor aliasing, and a stale
VRAM-bank attribute selecting garbage for the spill tile.
The warehouse route explicitly crosses the hardware BG-map boundary `$9BFF -> $9800`.
`SaveStates/warehouse-floor-items.mss` (SHA-1
`4822a0e49a0d85d597fb1337ddb4136131df7342`) preserves the reported same-room camera
position after items were placed; its added right column wraps horizontally from row 14,
x=28 to row 14, x=4. `SaveStates/warehouse-floor-items-reenter.mss` (SHA-1
`145065ce2a940cf84229dcab17d326585e8a01d9`) is the clean re-entry control. Their shared
pixel regression uses a literal right-edge raster rather than a framebuffer hash and
requires exact column restoration after dismissal.
Framebuffer hashes are secondary presentation checks. A third Rescue checkpoint selects
`Password`, requires saved BG destination `$9950` and a consumed two-byte live marker, and
freezes the immediate transition so the added ninth column cannot remain as a vertical
strip.

The Rescue entry fixture also freezes a hardware-B edit after entering `AB`: the rendered
field must retain uppercase `A` and the native buffer must be `30 D5...FF`. This is separate
from the on-screen `DEL` control because the physical button uses its own native event-table
handler.

`tests/fixtures/item_formatting.json` freezes the native producer anchors, English
punctuation bytes, exhaustive family-width maxima, the twenty exact object records injected
from `SaveStates/Mamel.mss`, and two reviewed Mesen framebuffers. Unlike ordinary category
fixtures, its arrow, staff, and Pot rows deliberately carry nonzero dynamic values.

`tests/fixtures/synthesis_lab.json` freezes the complementary native Pot lifecycle. It
records the Club base, explicitly seeded critical-hit rune on the Minotaur Axe donor,
five sparse Pot cell offsets, five Mesen framebuffers, post-insertion capacities, retained
base pointer, consumed donor record, and released Club rune bit after the Pot breaks.
The final Info-screen reading remains the explicit manual visual check.

When intentionally updating a fixture:

1. reproduce the semantic change with the verified source ROM;
2. inspect the changed fields rather than accepting the whole diff;
3. keep bulk Japanese source and ROM payloads out of tracked fixtures; add only the
   smallest reviewed anchor required by an extraction/codec contract;
4. run the focused test and complete suite;
5. explain why the old contract is no longer correct.

A fixture hash changing is not by itself evidence that behavior remains safe.
