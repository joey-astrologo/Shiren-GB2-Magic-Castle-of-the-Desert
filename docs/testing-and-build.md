# Testing and build

The prescriptive change gates are in [ENGINEERING_RULES.md](ENGINEERING_RULES.md), and the
tracked fixture conventions are documented in
[`tests/fixtures/README.md`](../tests/fixtures/README.md).

All tools expect a user-supplied matching Japanese ROM. A convenient shell variable is:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
```

The expected clean source is a 4 MiB, CGB-only MBC5 ROM with SHA-1
`5264f6d0c4f12c9144de1d12fddadbadd82b3e33` and MD5
`9e3d4ff0ba3d6deec5080f6dbed4fef8`.

## Normal validation

For a story edit, check and apply the authoritative scene document first:

```sh
python3 tools/prose_editor.py "$ROM"
python3 tools/prose_editor.py "$ROM" --apply
```

Then run the cross-catalog and runtime checks:

```sh
python3 tools/overlays.py "$ROM"
python3 tools/internal_audit.py "$ROM"
python3 tools/lint_en.py "$ROM"
python3 tools/runtime_widths.py "$ROM"
python3 tools/menu_text.py "$ROM"
```

The production build installs and validates the player-name, spell-input, Blank Scroll, and
unidentified-item naming patches. Their focused contracts can also be run directly through
`tests.test_name6`, `tests.test_spell_input`, `tests.test_blank_scroll`,
`tests.test_mesen_blank_scroll`, `tests.test_unidentified_names`, and
`tests.test_mesen_unidentified_item`.

When their owned files change, also run the relevant family check before applying:

```sh
python3 tools/wrap_item_messages.py "$ROM"
python3 tools/wrap_item_messages.py "$ROM" --apply
python3 tools/combat_messages.py "$ROM"
python3 tools/combat_messages.py "$ROM" --warnings-json
python3 tools/combat_messages.py "$ROM" --apply
python3 tools/wrap_items.py "$ROM" script/en/items.tsv script/en/items.tsv
```

Do not use `tools/wrap_en.py --apply` as the normal story-authoring entry point. The
scene editor owns that workflow and invokes the measured wrapper itself.

## Build

```sh
python3 tools/build.py "$ROM" script/en build/shiren-gb2-english.gbc
```

The production builder reruns required safety checks before writing the output. Text is
relocated through far pointers, so storage growth does not justify shortening visible
English.

## Tests

```sh
python3 -m unittest discover -s tests
```

For a focused graphical-input check:

```sh
python3 -m unittest \
  tests.test_save_summary \
  tests.test_name6 \
  tests.test_spell_input \
  tests.test_blank_scroll \
  tests.test_mesen_blank_scroll \
  tests.test_unidentified_names \
  tests.test_mesen_unidentified_item \
  tests.test_item_status \
  tests.test_item_formatting \
  tests.test_item_terminology \
  tests.test_synthesis_lab
```

The suite covers extraction and catalogs, translation fixtures, control preservation, VWF
widths, wrapping, menus, save/name expansion, spell input, Blank Scroll input,
unidentified-item free/history naming, runtime text domains, scene ownership, internal
classification, and deterministic production builds.
User-reported regressions should receive a focused fixture or behavioral test whenever the
mechanism is reproducible.

`tests.test_item_terminology` freezes all 50 approved series-name corrections, all affected
unidentified-item roots, every identified description-title/name pair, and the reviewed
Help/UI/dialogue layouts whose literal item references changed. The Wanda equipment lesson
fixture also preserves its `<page><box>` reader wait.

The current complete run is **371 tests** with the matching ROM, PyBoy, RGBDS, and Mesen
available. Treat that number as a status snapshot; the required gate is always discovery
of the complete `tests/` directory, not a hard-coded subset.

`tests.test_save_summary` also replays the exact title-screen Adventure -> save-file route
with `SaveStates/Mamel.mss`. It freezes native navigation type `$13`, all four
Continue/Secrets/Reset/Recap cursor positions, the cursor OAM coordinates, and a
cursor-masked framebuffer hash. This guards against input-editor navigation patches
stealing a live menu graph or corrupting the submenu during Up/Down movement.

`tests.test_name6` freezes the title and Secrets event selectors, the complete fourteen-row
replay pointer table, and the SHA-1 of every original 106-byte embedded diary. It proves
that installation changes only each snapshot's five-byte native name field and four-byte
suffix/marker tail. A PyBoy-backed getter check then loads the patched title-family event 0
and the first/last Secrets events 4 and 13 and requires the complete `Shiren` result.

`tests.test_item_status` freezes the exact `SaveStates/broken-bracelet.mss` supplied for the
bad cracked-marker report. Because a machine state retains already-rendered VRAM, the live
Mesen route closes and reopens Items before asserting the `(Cr)` screen. Static checks also
guard the original 40-byte `F2 1E` bitmap, native `0F 06` width pair, reviewed replacement
raster, exclusive ROM ownership, and the 18-pixel worst-case item-row margin.

`tests.test_item_formatting` guards all nine native producer/cave patches, measures every
translated weapon/shield/arrow/staff/Pot dynamic row, and replays the two-page item gallery
from `SaveStates/Mamel.mss`. Its widest combined status row ends at x=132 against the
x=144 item-list edge. Manual gallery instructions and the twenty expected rows are in
[ITEM_FORMATTING.md](ITEM_FORMATTING.md).

`tests.test_synthesis_lab` drives a real Synthesis Pot through both `Put In` operations
from the same disposable state. It freezes all five intervening screens and asserts that
the Club becomes the contained base, the Axe donor is consumed, the sparse Pot sentinels
remain valid, and the native deferred-synthesis state is reached. It then throws and breaks
the Pot and asserts that the released Club carries weapon rune bit 10. The manual route
reviews the recovered weapon's seal description; see
[ITEM_FORMATTING.md](ITEM_FORMATTING.md#synthesis-seal-manual-route).

The committed fixtures are deliberate contracts. If an intentional change updates one,
review the semantic difference rather than accepting fixture churn blindly.

## Diagnostic and recovery tools

These are not required for an ordinary text edit, but remain useful when investigating
ROM or emulator behavior:

```sh
python3 tools/codec.py "$ROM"
python3 tools/textdump.py "$ROM" --space
python3 tools/font.py "$ROM" --info
python3 tools/allocate.py "$ROM" --output build/script-allocation.json
python3 tools/layout.py "$ROM"
python3 tools/surfaces.py "$ROM"
python3 tools/mesen_state.py SaveStates/Mamel.mss SaveStates/Mamel.srm
```

`mesen_state.py` extracts Mesen 2's named `cartRam` field as an ordinary 32 KiB battery
SRAM file that PyBoy can reuse. This is the supported bridge for reproducing a live route
from a Mesen save state.

### Dynamic item-row gallery

`tools/mesen_item_formatting_gallery.lua` injects a disposable twenty-item inventory into
`SaveStates/Mamel.mss`. It presents status symbols and combinations on page 1, then numeric
and category-specific formats on page 2. See [ITEM_FORMATTING.md](ITEM_FORMATTING.md) for
the exact route and checklist. Do not sort or save the injected run.

### Synthesis Pot manual route

`tools/mesen_spawn_synthesis_lab.lua` replaces the disposable Mamel inventory with a
Synthesis Pot, a Club base, and an Axe of the Minotaur donor. Use **Synthesis Pot > Put
In > Club**, repeat with the Axe, break the Pot against a wall, recover the Club, and
inspect Info for `More frequent critical hits.` The exact route and native structure are
documented in [ITEM_FORMATTING.md](ITEM_FORMATTING.md#synthesis-seal-manual-route). This
helper deliberately erases the prior inventory; never run it against a save you intend to
keep.

### Blank Scroll manual route

`tools/mesen_spawn_blank_scroll.lua` safely adds one real Blank Scroll to the first free
inventory slot for manual Mesen testing. Enter a dungeon, pause emulation, load the helper
through **Debug > Script Window**, and press **Run (F5)**. Resume and reopen Items.

The item name, description, `Write` action, and 11-character full-name keyboard are
translated. The `0` cell enters the hyphen required by `Trap-eraser`. Recognition retains
the native notebook rule: only a Scroll already discovered on that save can be written.
The complete accepted-name table and mechanism are in
[BLANK_SCROLL.md](BLANK_SCROLL.md).

Back up the save or use a disposable state because Mesen may persist later in-game saves
after the live WRAM injection.

### Unidentified item naming manual route

`SaveStates/unidentified-item-naming.mss` freezes the exact reported Rabbit Scroll route.
Because it was captured after the old screen was drawn, back out and reopen **Name** after
loading it with the latest ROM. From the initial `A` cell, **Up, Right, Up** reaches the
localized `FILL IN` history control. Each activation cycles to the next learned name; it
does not open a separate list.

`tools/mesen_spawn_unidentified_item.lua` provides a second disposable route from
`Mamel.mss`: it creates a real item, presents it through a chosen unidentified appearance,
and enables exactly its learned-name/history bit. Reload the state between free-name and
`FILL IN` tests. Canonical recalls use a build-guarded 14-character preview and render their
full translated root after confirmation; free labels retain the native seven-character
maximum. The live regression also freezes the no-star `Windblade` preview, typing-after-fill
reset, `DEL`-after-fill reset, and successful return to Items after a new free name. The
complete checklist, token contract, alternate categories, and regression command are in
[UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md).
