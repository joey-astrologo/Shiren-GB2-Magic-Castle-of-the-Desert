# Unidentified item naming

GB2 has a third graphical text-entry route beyond player names and Blank Scroll writing:
the **Name** action for unidentified Bracelets, Grasses, Scrolls, Staffs, and Pots. The
English build now gives mode 0 its own keyboard, navigation graph, history control, and
canonical-name display resolver.

**Select** does nothing on the English entry screen. The original Japanese shortcut
cycles kana voicing marks, such as は → ば → ぱ, by modifying the current or preceding
character. Its byte table overlaps English lowercase letters: Select could turn the final
`n` in `Preservation` into `ぜ`. The shared English input controller now routes Select to
its native idle handler, preserving the buffer, cursor, and canonical recall selection.

## What `FILL IN` means

`FILL IN` is the localized native history recall. It does not open a list or a second
free-entry field. Each activation advances to the next previously learned canonical name
for the current item category and places that name in the entry field. The player may
activate the visible control with **A** or use the native **Start** shortcut; both now
finish through the same full-name presentation path. The original shared
English keyboard rewrite accidentally made this node unreachable. Mode 0 now owns a
separate graph, so the control is both visible and selectable.

The private graph does not replace a native navigation type. Type `$13` belongs to the
ordinary nine-row list at `16:$6625` and is used by the title-screen Adventure submenu.
Mode 0 uses type `$F4`: the generic pointer resolver lands on the first two bytes of
unreachable node 64 in the English name-entry graph (`16:$615C`), where this patch stores
the private `$C800` pointer. Both English name graphs prove nodes 62-74 unreachable. This
keeps `FILL IN` independent without hiding the Continue-menu cursor or redirecting its
Up/Down movement.

From the initial `A` cell, the shortest frozen route to `FILL IN` is **Up, Right, Up**.
Selecting it invokes the original bank-12 history routine and then restores the English
mode-0 graph.

## Manual Mesen test route

The user-supplied fixture `SaveStates/unidentified-item-naming.state` contains a Rabbit Scroll
in inventory and freezes the exact reported route. Its SHA-1 is
`537c360d4a7745700e7d8864b4c2fb0389a701f0`.

Because that machine state was captured after the old keyboard had already been drawn,
load it with the latest English ROM, back out once, and reopen **Name**. This makes the new
constructor redraw the screen. Verify:

1. The controls read `SPACE`, `FILL IN`, `OK`, the two cursor symbols, and `DEL`.
2. `FILL IN` is reachable with **Up, Right, Up** from the initial `A` cell.
3. Press `FILL IN` until the field reads `Windblade`. The remaining cells must be visually
   blank; no trailing `*****` may appear. The recalled name must begin at the same horizontal
   position as the original seven-star field.
4. Move to `OK` and confirm. Back in Items, the entry reads `Scroll: Windblade` in full and
   the game remains responsive.
5. Repeat the recall, then type a character. The recalled name must disappear atomically,
   and that character must become byte one of a fresh seven-cell free label.
6. Repeat once more and activate `DEL`. The recalled name must become the original empty
   seven-star field. Enter a new free label and confirm it to prove the editor can exit.
7. Reopen **Name** and press **Start**. The shortcut must show the same complete canonical
   root as `FILL IN`, including roots longer than seven characters; `Preservation` in
   `SaveStates/multiple-unidentified-items.state` is the automated long-name probe.

Free labels retain the native seven-character storage contract. A history recall instead
expands the presentation field to 14 cells, so `Windblade` and every current translated
canonical root appear in full before confirmation. Confirmation stores a compact canonical
token, and ordinary item-name rendering expands that token to the complete translated name.

A recalled canonical name is a distinct editor state, not a long editable free label. Its
unused presentation cells use the ordinary space glyph, so only the translated name is
visible. Rendering copies all 14 safe cells but calculates the horizontal origin from the
native seven-cell field, so short recalls do not drift left and long recalls retain their
full capacity. The first subsequent character, `DEL`, or physical **B** atomically demotes
that state back to the native seven-cell free editor. **B** clears the preview and resets
the cursor to the first cell. Character entry supplies the one redraw for that input frame;
deletion supplies its own redraw. After the redraw, the presentation-only tail is restored
to the native terminator/filler form before confirmation or cancellation code can consume
it. This ordering prevents invisible appends, off-screen cursors, double-refresh deadlocks,
and the formerly trapped delete state. Character insertion also bounds the cursor before
writing, including when an older editor state retains a cursor beyond the seventh cell.

The native physical-B event clears the canonical-match byte before calling deletion, so
the localized helper recognizes the preview by its 14-cell maximum, mode 0, and private
navigation type `$F4`. It wraps only the native deletion call and retains ordinary B
behavior in other modes, including the Rescue presentation wrapper layered over it.

### Disposable early-dungeon route

To repeat the test without relying on progression:

1. Load `SaveStates/Mamel.mss` with the latest English ROM and pause emulation.
2. Open **Debug > Script Window**, load `tools/mesen_spawn_unidentified_item.lua`, and press
   **Run (F5)** once.
3. Confirm the log contains `Unidentified item lab: READY`.
4. Resume, close and reopen **Items**, select the injected Rabbit Scroll, and choose
   **Name**.

The helper creates a real Windblade Scroll, presents it through the Rabbit Scroll
appearance, enables only Windblade's learned-name bit, and clears the one measured tutorial
flag that otherwise suppresses ordinary item actions in the Mamel fixture. It validates its
writes and rolls the complete preparation back on failure.

Reload the original state and rerun the helper between the two independent tests below:

- **Free name:** enter any label up to seven characters, confirm it, and verify the label in
  Items, At Feet, Info, and dungeon messages.
- **History:** press `FILL IN` until it recalls Windblade, confirm `OK`, and verify the full
  `Scroll: Windblade` label in Items and later consumers.

To probe another category, edit `TARGET_KEY` near the top of the Lua file. Valid values are
`passage_bracelet`, `herb`, `windblade_scroll`, `knockback_staff`, and
`preservation_pot`. Reload the state before each probe.

## Measured native mechanism

The per-root identification map begins at WRAM bank 2 `$DC82`. Every two-byte entry holds
an unidentified appearance index followed by a custom-name slot index; `$FF` means absent.
The five root partitions are:

| Category | Root indices | Identified item indices |
|---|---:|---:|
| Bracelet | 0-26 | 63-89 |
| Grass | 27-46 | 104-123 |
| Scroll | 47-80 | 124-157 |
| Staff | 81-106 | 158-183 |
| Pot | 107-122 | 184-199 |

The learned-name/history bitset begins at bank 2 `$DE1C`. `FILL IN` searches only roots
whose corresponding bit is set. Four native sentinel roots are excluded: 69, 79, 114,
and 121. Repeated activations cycle the matching roots in the native order; there is no
separate selection menu.

The native recall routine must run with its original seven-cell maximum because it copies
through a legacy scratch area beginning at `$C18D`; increasing that native copy length
would overwrite adjacent live input state. The English hook therefore lets the native
routine choose the next root ID at seven cells, then renders that translated root directly
into the safe `$C16D` presentation buffer. Its redraw copies 14 cells while reusing the
native seven-cell x origin (`B=$28`, `C=$08`) instead of centering the larger capacity. The build
validates all 123 translated root entries and rejects any active root longer than 14 cells.
The current longest roots are `Narrow-escape` and `Transmutation` at 13 characters,
leaving one cell of measured headroom inside the 14-cell field.

The editor controller handles **Start** before its selected-grid-node dispatch, through the
far call at `16:$5B36` to native `12:$5073`. That bypass originally left the native
seven-character preview (`Preserv`) even though the root ID was correct. A mode-checked
wrapper now preserves the shortcut's native return value and sends mode 0 through the same
14-cell expansion, aligned redraw, and private-navigation restoration as `FILL IN`. Every
other graphical-input mode delegates through the
[Blank Scroll Start wrapper](BLANK_SCROLL.md#english-engineering) at `251:$4320`:
mode 1 uses a bounded eleven-character prefix, while the remaining modes retain
the native routine in bank `$12` at `$5073`.

Persistent custom labels occupy 20 slots beginning at bank 2 `$DD78`. Each slot is eight
bytes. Free labels retain the native contract of at most seven glyph bytes followed by
`$FF`.

Canonical history selections use the same eight-byte slot without expanding save data:

```text
FE FE <root-index> FF FF FF FF FF
```

Both `$FE` bytes are unavailable on the localized keyboard. The first is not the native
allocator's `$FF` free-slot sentinel; the second is not the `$FF` terminator used by the
variable-length SRAM journal. The display resolver recognizes `FE FE <valid-root>`, maps
the root to the translated item table, renders the complete English name, and then returns
to the native caller.

The first long-name implementation confirmed the seven-cell `Preserv` field natively and
only afterward changed its WRAM slot to `FE FF <root>`. That made the current session look
correct, but the native confirmation had already journaled `Preserv` to SRAM. On reload,
the game correctly reconstructed the truncated literal. The repaired confirmation instead
temporarily puts `FE FE <root> FF...` in the input buffer before calling the native routine,
so the SRAM journal and the item-owned WRAM slot receive the same compact value. The
resolver still accepts the interim `FE FF <root>` form and the original English-patch
`FF FE <root>` form when they exist in a live state. Existing SRAM that has already become
a literal such as `Preserv` has lost the selected root ID and must be named with **FILL IN**
once more after updating.

This does not enlarge the save or runtime tables. There are 20 native custom-name slots,
each eight bytes, and the new value uses only three non-terminator bytes. Allocation belongs
to an unidentified item root, not to each physical inventory object: an inventory containing
20 copies of the same Preservation Pot uses one root mapping and one custom-name slot. Even
20 different custom-named roots fit the native table exactly. If all 20 slots are already
occupied, the native allocator's bounded 20-entry scan returns `$FF`; it does not write a
21st slot or overrun adjacent WRAM. The attempted additional name can fail to stick, but it
does not create memory corruption.

## Automated regressions

Run both the patch/route fixture and the distributable helper fixture:

```sh
python3 -m unittest \
  tests.test_multiple_unidentified_names \
  tests.test_unidentified_names \
  tests.test_pyboy_unidentified_item -v
```

The coverage includes exact-state hashing, RGBDS source equivalence, owned-range and
fail-closed installation, the dedicated connected navigation graph, isolation from native
navigation type `$13` plus a live four-row Adventure-submenu cursor route, seven-cell free-name
setup, the 14-cell recall catalog, `FILL IN` cycling, a pixel-frozen full `Windblade`
preview without star padding, an asserted native seven-cell draw origin, pixel-frozen
type/delete reset states, successful free-name
confirmation after both resets, canonical-token persistence through a real suspend and fresh
SRAM reload, current/interim/legacy token expansion,
the live **Start** shortcut's final 14-cell `Preservation` draw, repeated physical **Select**
preserving empty, typed, and recalled fields at byte and pixel level, physical **B** clearing
that preview followed by forty controller-driven character entries with unchanged adjacent
memory and successful seven-character confirmation, two-item slot-allocation
independence, full-name expansion, return to Items, helper
injection, and its object/mapping/history contracts.
