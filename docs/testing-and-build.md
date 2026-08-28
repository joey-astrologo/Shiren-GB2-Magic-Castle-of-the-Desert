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

The production build installs and validates the name, spell-input, and Blank Scroll
patches. Their focused contracts can also be run directly through `tests.test_name6`,
`tests.test_spell_input`, `tests.test_blank_scroll`, and
`tests.test_mesen_blank_scroll`.

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
  tests.test_name6 \
  tests.test_spell_input \
  tests.test_blank_scroll \
  tests.test_mesen_blank_scroll
```

The suite covers extraction and catalogs, translation fixtures, control preservation, VWF
widths, wrapping, menus, save/name expansion, spell input, Blank Scroll input, runtime text
domains, scene ownership, internal classification, and deterministic production builds.
User-reported regressions should receive a focused fixture or behavioral test whenever the
mechanism is reproducible.

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
