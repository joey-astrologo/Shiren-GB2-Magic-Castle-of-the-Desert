# Big Moai spell system

For the concise player-facing catalog, see [Big Moai code list](BIG_MOAI_CODES.md).

Big Moai accepts four-character promotional gift codes, which the game calls
“spells.” This is an item-reward system and is completely separate from Wanderer
Rescue. The production ROM already localizes its A-Z/0-9 keyboard, all 100 runtime
comparison records, their matching diagnostic labels, and the seven codes taught in
story dialogue.

This document records the first real-NPC fixture, the progression gate that kept the
user from reaching the editor, and the safe manual test route.

## Native availability gate

The supplied `SaveStates/big-moai-locked.state` is the native PyBoy reproduction of Big Moai saying
he is not ready. Its SHA-1 is
`df8c3d11bd92251ee9b76c3e7cde2106b3e0d211`.

The event at `74:$5CEF` begins:

```text
60 09 F7 5C   branch to $5CF7 when story stage $C3EF >= $09
16 0D 6A      otherwise display group $6A, index $0D (not ready)
```

The fixture has `$C3EF=$06` and `$C3F0=$06`. `$C3EF` is the active story stage;
`$C3F0` is its saved shadow. Native save code at `05:$4553-$4562` serializes that
two-byte pair, and native load code at `05:$4585-$458F` restores it. In this captured
save, the two native SRAM mirrors contain `06 06` at flat `cartRam` offsets `$2517`
and `$4517`, followed by their checksum byte `$0C`.

The exact narrative event that normally advances stage 6 to stage 9 has not yet been
named. We do not need to guess at or set a broad collection of story flags to test the
system: stage 9 is the complete gate used by this NPC route.

## Safe Mesen unlock helper

`tools/mesen_unlock_big_moai.lua` changes only flat Work RAM offsets `$03EF-$03F0`,
the Mesen view of CPU `$C3EF-$C3F0`, to `$09 $09`. It requires the active value and
saved shadow to agree, verifies both writes, and rolls back the first write if the
second fails. It does not write ROM, inventory, Big Moai usage bits, or battery SRAM.
If the game later performs an ordinary save, its native save path may persist the new
stage, so use a disposable state or back up the save beside the ROM.

Manual route:

1. Build and load the current English ROM.
2. Load `SaveStates/big-moai-locked.mss` in Mesen and pause.
3. Open **Debug > Script Window**, load `tools/mesen_unlock_big_moai.lua`, and run it.
4. Resume and speak to Big Moai.
5. Enter `WISH`. The fourth character automatically moves the cursor to `OK`; press A
   without moving the cursor.
6. Big Moai should accept the spell and place **Fortune Grass** in the empty inventory.

The helper reports:

```text
Big Moai unlock: story stage $06 -> $09. Resume and speak to Big Moai.
```

## Proven WISH route

The runtime comparison table is script group 23. Entry 93 is localized to `WISH`, whose
exact English bytes are `20 12 1C 11`. Its proven native route is:

| Step | Contract |
|---|---|
| Available prompt | group `$6A`, index `$0F` |
| Graphical editor | mode 3, four bytes, shadowed A-Z/0-9 atlas, framebuffer `459513B9` |
| `DEL` cursor | framebuffer `4F03BBAA`; underline sits below the label |
| Auto-selected `OK` cursor | framebuffer `28BFAA00`; underline sits below the label |
| Full field | buffer `20 12 1C 11 FF`, position 3, node `$33` (`OK`) |
| Accepted effect | group `$6A`, index `$11` |
| Reward message lookup | group `$6A`, index `$12` |
| Reward framebuffer | `7AEE87A8`: `<name> received` / `Fortune Grass!` |
| Inventory result | item ID `$70` / 112, **Fortune Grass** |
| Stable follow-up | group `$6A`, index `$1A` after starting a second conversation |

The mode-3 controller owns a hard four-byte backend. The A-Z/0-9 presentation and the
100 four-byte English codes were designed around that contract; this screen should not
be expanded like player names or Blank Scroll input.

The approved keyboard presentation is:

```text
DEL                         OK

ABCDE        UVWXY
FGHIJ        Z
KLMNO        01234
PQRST        56789
```

The two character blocks retain the measured native screen columns; the spaces above are
only a plain-text approximation. Both controls use cursor Y coordinate `$39` / 57. The
previous `$31` / 49 value drew the underline through the `DEL` and `OK` glyphs instead of
below them. The navigation graph is regenerated from the visible four-row layout, skips
all inactive native nodes, and keeps every character and both controls reachable.

## Automated coverage

Run:

```sh
python3 -m unittest tests.test_big_moai -v
```

The test family:

- hash-freezes the supplied Mesen state and its stage pair;
- freezes both observed native SRAM mirrors and checksums;
- verifies the exact event opcode, threshold, and locked dialogue packet;
- runs the production helper and requires only the two measured stage bytes to change;
- replays the unmodified fixture and requires the real locked NPC branch;
- builds a fresh English ROM, reaches the real localized editor using controller input,
  visits and framebuffer-freezes `DEL`, enters `WISH`, framebuffer-freezes the native
  auto-selected `OK`, requires Fortune Grass in inventory, freezes the localized reward
  framebuffer, and starts a second conversation.

The last condition is essential. The original regression stopped when Fortune Grass
appeared in inventory, but the game subsequently froze while executing graphics data at
`03:$4F0E`. `<cF8>g` is a native dynamic reward selector: it must encode as `F8 10`.
Encoding its apparent `g` through the English lowercase page produced `F8 36` and corrupted
the formatter. The source codec now preserves all F8-prefixed native selector runs, lint
checks all 114 selector runs across 67 translated records, and this live route cannot pass
until group `$6A` index `$1A` proves normal NPC interaction resumed.

This closes the feature-unlock and first accepted-code route. Still worth capturing in
future playtesting are an unknown code, an already-used code, inventory-full handling,
and any native time/cooldown branch. Those should become separate live fixtures rather
than test-side assumptions.
