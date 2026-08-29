# Dynamic item-row formatting

Inventory rows are composed at runtime. The translated group-4 record supplies the base
item name, while native category formatters add equipment modifiers, stack counts, charges,
capacity, amounts, monster names, and status decorators. Translating the base-name table
alone therefore cannot localize every visible row.

## Localized forms

The production build preserves the native item-record semantics and emits these English
forms:

| Item state/family | English row form |
|---|---|
| Equipped | native equip prefix + name |
| Cursed | name + native skull |
| Blessed | name + native bell |
| Plated | name + native plate mark |
| Cracked Bracelet | name + `(Cr)` |
| Synthesized equipment | native alternate name color; seals are listed on Item Info rather than appended to the inventory name |
| Weapon/shield modifier | `Name+N` or `Name-N` |
| Arrow stack | `N Name` |
| Staff charge | `Name[N]` |
| Pot capacity | `Name[N]` |
| Gitan object | `N Gitan` |
| Monster meat | `Monster Meat` |

The status flags can combine. The live gallery includes curse + plate, blessing + plate,
and equip + curse + plate rather than testing each flag only in isolation.

`tools/item_formatting.py` owns the formatter punctuation. It changes the original
Japanese arrow counter suffix to one English space, changes staff/Pot corner brackets to
`[` and `]`, and changes dynamic negative signs to the English hyphen. It does not change
the object record, item IDs, numeric conversion, translated names, or terminators.

The cracked marker is a separate bitmap concern: `tools/item_status.py` retains native
token `F2 1E` and its 14-pixel advance while replacing the Japanese `(hibi)` pixels with
`(Cr)`.

## Item-list geometry

The inventory name begins at x=7 and must not pass the exclusive right edge at x=144.
`tests.test_item_formatting` measures every translated member of each dynamic family at
its reviewed worst value:

| Family maximum | Width | Rightmost x |
|---|---:|---:|
| `Axe of the Minotaur+99` | 108 px | 115 |
| `Break-Off Shield+99` | 95 px | 102 |
| `99 Knockback Arrow` | 91 px | 98 |
| `Narrow-escape Staff[99]` | 115 px | 122 |
| `Transmutation Pot[9]` | 99 px | 106 |
| equip + `Axe of the Minotaur+99` + skull + plate | 125 px | 132 |

The last combination is the widest reviewed row and retains 12 pixels before the edge.
Changing an item name, font advance, status glyph, or formatter requires rerunning this
exhaustive family test.

## Two-page Mesen gallery

Use the gallery to inspect every currently mapped inventory-row decoration without finding
rare objects in a playthrough:

1. Build and load `build/shiren-gb2-english.gbc`.
2. Load `SaveStates/Mamel.mss`.
3. Pause emulation and load `tools/mesen_item_formatting_gallery.lua` through
   **Debug > Script Window**, then press **Run (F5)**.
4. Resume, press **B** once to dismiss the existing message, and press **A** to open Items.
5. Inspect page 1. Press **Right** to inspect page 2. Do not sort the injected inventory.

Page 1 shows normal, equipped, cursed, blessed, plated, combined status, cracked, synthesis,
and maximum combined equipment rows. Page 2 shows positive/negative equipment, a shield,
arrow quantity, staff charge, Pot capacity, Gitan, and monster meat. The script logs the
exact label and expected rendering for all twenty slots.

The helper replaces all twenty live inventory slots, consumes twenty cleared object-pool
records, and marks Strength Bracelet, Knockback Staff, and Preservation Pot identified.
Use only with this disposable state. It modifies WRAM, not the ROM, but later in-game saves
may persist the modified run.

The same script has a noninteractive test-runner mode. The fixture freezes both reviewed
framebuffers (`B9899EFF` and `EA1E7AC7`, FNV-1a) and the exact eight-byte object records in
`tests/fixtures/item_formatting.json`.

## Synthesis-seal manual route

`tools/mesen_spawn_synthesis_lab.lua` supplies the visual test that the row gallery cannot:
a real empty Synthesis Pot, a plain Club, and an Axe of the Minotaur whose native effect
donates the critical-hit seal.

1. Build and load `build/shiren-gb2-english.gbc`.
2. Load `SaveStates/Mamel.mss`.
3. Pause emulation, load `tools/mesen_spawn_synthesis_lab.lua` through
   **Debug > Script Window**, and press **Run (F5)**.
4. Resume, press **B** once to dismiss the existing message, and press **A** to open Items.
5. Select **Synthesis Pot > Put In > Club**.
6. Repeat **Synthesis Pot > Put In**, this time choosing **Axe of the Minotaur**.
7. Throw the Pot against a wall, recover the Club, and open its **Info** screen.

The Axe disappears on the second insertion and the Pot reads `[3]`. The game defers
materializing the transferred rune until the Pot breaks. The recovered Club should use
the synthesized-item name color and list `More frequent critical hits.` in Info. This is
the semantic seal display; there is no separate seal icon appended to the inventory row.

The helper must seed the Axe's inherent critical-hit rune explicitly at object byte 6,
mask `$04` (weapon rune bit 10). Direct WRAM injection bypasses the native item constructor,
so an object with only Axe item ID `$0B` looks correctly named but has no effect to donate.
That malformed version was caught during manual review; the regression now breaks the Pot
and asserts the released Club actually carries bit 10.

The helper resolves three cleared object records before writing, reserves an eight-record
cleared runway for the Pot's sparse native contents structure, and intentionally replaces
all twenty inventory pointers. Therefore every pre-existing inventory item disappears when
the helper runs; use only with the disposable Mamel state and do not save the injected run.
Its Mesen regression freezes the initial list, action menu, Put In picker, both
post-insertion screens, contained-object pointer, donor consumption, native Pot state, Pot
break, and the released weapon's critical-hit rune in `tests/fixtures/synthesis_lab.json`.

## What is outside this gallery

- Unidentified appearances, seven-character custom labels, and canonical `FILL IN` names
  use the separate routes in [UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md).
- The two-page row gallery does not create a weapon through native synthesis. Use the
  Synthesis-seal route above for that lifecycle and Info-screen check.
- Action-menu cursors and the next-page indicator are menu UI, not part of the item name.
