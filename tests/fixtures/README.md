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
| Menus and patches | `main_menu_graphics.json`, `menu_text.json`, `stairs_menu.json`, `name6.json`, `blank_scroll.json`; all fourteen embedded replay diaries plus live mode-0 and Adventure navigation contracts |
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
`SaveStates/rescue-entry-japanese-editor.mss`, the exact user-reported production failure:
mode 8, navigation type 0, and the complete Japanese 320-tile editor map. Its PyBoy
regression invokes the production active-editor guard with the captured CPU register state
and requires private navigation type `$F5` plus the complete English map. The menu route
alone was insufficient because it covered only a constructor path that already worked.
Its Mesen companion resumes the broken fixture and requires the production input-loop hook
to repair it naturally, without a test-side call to the repair routine.
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
message, and freezes generated Thank-You Password `EkWsMPtHHOEE`. This closes the
requester response-input/presentation loop; physically traversing a Rescue Gate and
capturing the rescuer's own generated response remains the next two-diary fixture.

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
