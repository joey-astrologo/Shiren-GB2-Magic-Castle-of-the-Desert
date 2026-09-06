# Mesen endgame helpers

These two Lua helpers prepare a disposable or backed-up run for late-game ending checks.
They change live emulator memory. They do not patch the ROM, but an ordinary in-game save
can persist the result, so back up the `.srm` beside the ROM first.

## Level 99 and equipment

Use `tools/mesen_prepare_endgame.lua` during normal dungeon control:

1. Close all menus and messages, then pause Mesen.
2. Open **Debug > Script Window**, load the Lua file, and press **Run (F5)**.
3. Require the `READY` messages in the Script Window. If it reports `FAILED`, nothing is
   intentionally retained; return to normal dungeon control and try again.
4. Resume for one turn, then reopen Status and Items.

The helper sets both live level fields to 99, Experience to the Japanese ROM's exact
level-99 threshold (`6,200,000`), and the native current/maximum HP-growth pair to its
real cap (`250/250`). Actor 0's bank-1 record must match its complete High RAM cache before
the helper writes either view.

The equipment is:

- equipped, uncursed, blessed, plated **Kabura Sutegi+99**, native base Atk 40;
- equipped, uncursed, blessed, plated **Rasen Fuuma+99**, native base Def 30.

Existing equipped weapon/shield object records are upgraded in place, preserving every
other inventory slot. If either category is absent, the helper uses a free slot and a
cleared object record. It refuses a full inventory instead of deleting an unrelated item.

### Seal policy

Every documented seal without a harmful or irreversible tradeoff is enabled. The masks
are weapon `$09_9F_FF` and shield `$2F_FF_F9` when read as the native 24-bit value.

Excluded weapon seals are: HP-draining/breaking, forced self-knockback, Meat conversion
that may break the sword, the breakable Pickaxe and trap-breaking effects, and losing one
Upgrade Value on every hit. The safe nonbreaking wall-digging seal remains enabled.

Excluded shield seals are: doubled Fullness loss, No Hunger with the irreversible
Max-Fullness-0 side effect, losing one Upgrade Value when hit, and possible breakage when
hit. The ordinary half-hunger seal remains enabled.

## Advance exactly one floor

Use `tools/mesen_advance_floor.lua` from normal dungeon control:

1. Close menus/messages and pause Mesen.
2. Load the Lua file and press **Run (F5)**. It should report `ARMED` with Shiren's setup
   coordinate, the generated staircase coordinate, and the direction it will press.
3. Resume. The helper walks onto the real staircase and accepts `Proceed` if that staircase
   uses the confirmation popup.
4. Wait until the next floor is fully controllable. Pause and press **Run (F5)** again for
   one more floor.

The helper identifies the native `$CA/$0C` staircase object through the generated floor's
object grid. It teleports Shiren only to a clear, walkable adjacent cell, synchronizes the
actor record/cache and occupancy grid, and then uses controller input. It never increments
the floor byte directly. That matters on a last floor: boss rooms, dungeon exits, item-loss
rules, story gates, and the true-ending transition still run through game code.

The script refuses zero stairs (often a boss/event floor), multiple stairs, a blocked setup
tile, a mismatched actor cache, or a non-player active actor. Once the native transition
starts, its input and frame callbacks unregister themselves. Do not rerun it during a fade,
arrival card, cutscene, boss encounter, or ending sequence.

## Japanese-ROM evidence

The helper constants were checked against the unmodified Japanese ROM with `mgbdis`:

- bank 126 `$6183-$61BB` clamps requested levels to 99 and copies the matching three-byte
  Experience threshold to bank-1 `$D2A0-$D2A2`;
- bank 126 `$64F3-$6556` is the real level-up route, writing both level representations and
  adding a random 3-7 through `$4F68`; `$4F68` caps the HP-growth maximum at 250;
- bank 7 `$5463-$54A2` proves actor offsets `$02/$0A` are the current/natural level fields;
- bank 122 `$48A0-$48AD` adds object bytes 2 and 3 for equipment power;
- the bank-119 item definitions give Kabura Sutegi base Atk 40 and Rasen Fuuma base Def 30;
- inventory pointers are bank 1 `$D2C1-$D2D4`; the shared 128-record object pool is bank 2
  `$D482-$D881`; equipment seal bits occupy object bytes 5-7.

Both committed Mesen dungeon fixtures independently locate the same staircase signature:
`SaveStates/Mamel.mss` at `(5,18)` and `SaveStates/final-gate.mss` at `(24,22)`.
