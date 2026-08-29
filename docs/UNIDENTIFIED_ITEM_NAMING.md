# Unidentified item naming

GB2 has a third graphical text-entry route beyond player names and Blank Scroll writing:
the **Name** action for unidentified Bracelets, Grasses, Scrolls, Staffs, and Pots. The
English build now gives mode 0 its own keyboard, navigation graph, history control, and
canonical-name display resolver.

## What `FILL IN` means

`FILL IN` is the localized native history recall. It does not open a list or a second
free-entry field. Each press advances to the next previously learned canonical name for
the current item category and places that name in the entry field. The original shared
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

The user-supplied fixture `SaveStates/unidentified-item-naming.mss` contains a Rabbit Scroll
in inventory and freezes the exact reported route. Its SHA-1 is
`2db915b2283fb9e0d831df2a0fe0d3e5beaf3c76`.

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

Free labels retain the native seven-character storage contract. A history recall instead
expands the presentation field to 14 cells, so `Windblade` and every current translated
canonical root appear in full before confirmation. Confirmation stores a compact canonical
token, and ordinary item-name rendering expands that token to the complete translated name.

A recalled canonical name is a distinct editor state, not a long editable free label. Its
unused presentation cells use the ordinary space glyph, so only the translated name is
visible. Rendering copies all 14 safe cells but calculates the horizontal origin from the
native seven-cell field, so short recalls do not drift left and long recalls retain their
full capacity. The first subsequent character or `DEL` atomically demotes that state back to the
native seven-cell free editor. Character entry supplies the one redraw for that input frame;
`DEL` supplies its own redraw. After either redraw, the presentation-only tail is restored
to the native terminator/filler form before confirmation or cancellation code can consume
it. This ordering prevents invisible appends, off-screen cursors, double-refresh deadlocks,
and the formerly trapped delete state.

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

Persistent custom labels occupy 20 slots beginning at bank 2 `$DD78`. Each slot is eight
bytes. Free labels retain the native contract of at most seven glyph bytes followed by
`$FF`.

Canonical history selections use the same eight-byte slot without expanding save data:

```text
FF FE <root-index> FF FF FF FF FF
```

The leading `$FF` is a native string terminator. A valid nonempty Japanese or English free
label therefore cannot begin with this signature, while an old empty slot contains
`FF FF ...` and cannot contain the `$FE` marker in byte two. The display resolver
recognizes only `FF FE <valid-root>`, maps the root to the translated item table, renders
the complete English name, and then returns to the native caller. All existing native/free
labels follow the original path unchanged.

## Automated regressions

Run both the patch/route fixture and the distributable helper fixture:

```sh
python3 -m unittest \
  tests.test_unidentified_names \
  tests.test_mesen_unidentified_item -v
```

The coverage includes exact-state hashing, RGBDS source equivalence, owned-range and
fail-closed installation, the dedicated connected navigation graph, isolation from native
navigation type `$13` plus a live four-row Adventure-submenu cursor route, seven-cell free-name
setup, the 14-cell recall catalog, `FILL IN` cycling, a pixel-frozen full `Windblade`
preview without star padding, an asserted native seven-cell draw origin, pixel-frozen
type/delete reset states, successful free-name
confirmation after both resets, canonical-token persistence, full-name expansion, return to
Items, helper injection, and its object/mapping/history contracts.
