# Shiren's natural HP regeneration

English reference for **Shiren the Wanderer GB2: Magic Castle of the Desert on
Game Boy Color**, checked against the original ROM and mgbdis on **2026-09-09**.

**Normal regeneration is based on maximum HP / 200 per eligible turn, with a
limit of one HP per update.** Fractions carry forward in a hidden counter. There
is no random healing roll, and the rate is not based directly on Shiren's level,
Strength, weapon, or current HP.

The **Healing Bracelet** replaces this with **five HP per eligible update**.
Both forms of recovery require positive Fullness and a living, injured Shiren.
Other action, map, and status gates can prevent an eligible update.

## What this means while playing

At **40 maximum HP**, natural regeneration restores **one HP every five eligible
turns**. At **100 maximum HP**, it restores **one HP every two**. Larger maximum
HP therefore improves recovery, until the ordinary one-HP-per-update limit.

| Maximum HP | Normal recovery pattern from a zero counter |
|---:|---|
| 15 | First HP on update 14, then updates 27, 40, 54, 67, 80… |
| 20 | One HP every 10 updates |
| 40 | One HP every 5 updates |
| 50 | One HP every 4 updates |
| 100 | One HP every 2 updates |
| 150 | Three HP per four updates: `0, 1, 1, 1`, repeating |
| 200 | One HP every update |
| 250 | At most one HP per update; a rare counter wrap can skip an update, as explained below |

The initial game state gives Shiren **15 maximum HP** and a zero regeneration
counter. Taking damage later does not imply that the counter is zero: it keeps
cycling even while HP is full.

The pattern is deterministic. For example, the alternating 13- and 14-update
gaps at 15 maximum HP are the result of carried fractions, not a probability
check.

### Waiting and walking

Walking and waiting advance the player-turn processing that calls regeneration.
The game's **hold B and press A** recovery command passes turns quickly. It does
not increase the amount healed per eligible update; enemies also continue acting.
See the localized [Recovering HP controls](../script/en/help.tsv), rows
`193:$5760` and `193:$5B3F`.

Simply leaving the game idle without taking an action does not heal Shiren.
These are game-turn updates, not seconds or emulator frames. The audit verified
idle versus B+A waiting in a real dungeon fixture. Speed statuses, every item
action, and every menu route have not been individually measured here, so the
exact algorithm below is stated per **eligible regeneration update**.

## Exact formula and carried progress

The ordinary routine maintains a **16-bit unsigned counter** `R`, initially zero.
Each time it runs, it adds **five times maximum HP**, then compares against 1,000.

With `M = maximum HP`:

```text
R = (R + 5 × M) modulo 65536

if R >= 1000:
    R = R - 1000       # Subtract exactly once.
    natural_heal_due = true
else:
    natural_heal_due = false
```

If Shiren can recover HP, a due natural-healing event restores one HP. Because
`5 × M / 1000 = M / 200`, this is the source of the familiar **maximum HP / 200**
rule. It does **not** round `M / 200` down separately every turn: that would
incorrectly prevent all natural healing below 200 maximum HP.

For maximum HP at or below 200, a starting counter `R₀` below 1,000, constant
maximum HP, and uninterrupted eligible updates, the number of natural healing
events after `T` updates is:

```text
events = floor((R₀ + 5 × M × T) / 1000)
```

Actual HP gained is limited by missing HP and the recovery conditions below.
Starting at **1/15 HP** with a zero counter, positive Fullness, and no incoming
damage or suppressing effects, reaching **15/15 HP** takes **187 updates**:

```text
missing HP = 14
updates    = ceil(14 × 200 / 15) = 187
```

### The limit above 200 maximum HP

The routine only handles **one natural healing event per call**, even if enough
counter points remain for another. Therefore 250 maximum HP does not provide
1.25 HP per turn. It normally heals one per update, and excess counter points
accumulate.

There is also a native overflow quirk. With maximum HP fixed at 250 and a starting
counter of zero, each successful update adds 1,250 and subtracts 1,000, leaving
250 extra counter points. After update 258, the counter is 64,500. Update 259
does this:

```text
64500 + 1250 = 65750
65750 modulo 65536 = 214
214 < 1000, so no natural healing event occurs on this update.
```

The exact algorithm retains this behavior. “At most one HP per update” is more
accurate than promising one on every turn above 200 maximum HP. The timing of
the skipped event depends on the existing counter and changes in maximum HP.

## Hunger, full HP, and the Healing Bracelet

The normal counter update happens **before** the routine checks whether Shiren
can actually gain HP.

| Condition | Result |
|---|---|
| Fullness is zero | No HP recovery, including from the Healing Bracelet. The counter still advances and due natural events are consumed. |
| HP is already full | No extra HP is stored. The counter continues cycling. |
| HP is zero | This routine does not revive Shiren. |
| Healing Bracelet effect is active | Restore up to five HP on every eligible update, whether or not a natural event is due. |
| Map flag `$C12B` bit 2 is set | Return before advancing the counter or healing. |
| The caller selects its alternate status-effect branch | Ordinary regeneration is skipped entirely. |

With the Healing Bracelet, the amount is **five total**, not five plus the normal
one on a natural-healing turn. HP is capped at the current maximum: at 38/40 HP,
it heals two. At 20/40 HP it heals five, even on an update when the ordinary
counter has not reached its threshold.

The bracelet's description also warns that Fullness is lost faster. This document
verifies HP recovery; it does not calculate the complete hunger system or its
equipment interactions.

The routine also contains companion-related handling. The formula and audit
here cover **Shiren**, with that companion branch disabled in isolated tests.
Herbs, healing from attacks, recovery abilities, traps, and other direct healing
effects have their own routines and are outside this natural-regeneration formula.

## ROM evidence

All bank numbers and CPU addresses below are **hexadecimal**, using this
repository's 16 KiB ROM-bank convention.

| Location | Evidence |
|---|---|
| `01:59C1–59D4` | Player action-completion path; an action flag can divert processing before the regeneration call. |
| `01:674A–6764` | Checks actor status `$10`; dispatches to either the alternate effect at `07:4CC4` or natural regeneration at `07:4C27`. |
| `07:4C27–4C2C` | Map flag gate, before any counter change. |
| `07:4BCF–4BE3` | Reads Shiren's current and maximum HP. For the active Shiren cache these are `$FF9B` and `$FF9C`. |
| `07:4C31–4C49` | Reads maximum HP, multiplies by five through `00:0C20`, and adds to the 16-bit counter. |
| WRAM bank 1, `$D2A3–D2A4` | Little-endian regeneration counter: low byte then high byte. |
| `07:4C4C–4C6D` | Compares against `$03E8` (1,000) and subtracts it once. |
| `07:4C91–4CB7` | Checks Fullness, full HP, and zero HP; selects one or five HP and applies capped recovery. |
| `07:4CB8–4CC3` | Gives the Healing Bracelet its five-HP recovery even without a due natural event. |
| `00:038D–0397` | Tests the equipment-effect bits beginning at WRAM bank 1 `$D2BB`. Effect index 5 (`$20`) controls accelerated recovery. |
| `07:5641–564D` | Reads current Fullness from WRAM bank 1 `$D2AD`. |
| `07:4BE4–4C26` | Adds HP without exceeding maximum HP. |
| `7E:5825–5858` | Initial state: zero regeneration counter and 15 current/maximum HP. |

The complete regeneration routine is `07:4C27–4CC3` in
`build/mgbdis/bank_007.asm`. It makes no RNG call.

## Verification and reproduction

[`tools/audit_hp_regeneration.py`](../tools/audit_hp_regeneration.py) provides the
exact `regen_step` model and reproducible native checks. It uses the original ROM
with SHA-1:

```text
5264f6d0c4f12c9144de1d12fddadbadd82b3e33
```

Verification checks **10 mgbdis spans** against the ROM's bytes and compares the
same spans with both existing English font builds. It also executes the original
regeneration routine in PyBoy, without replacing or hooking its calculations:

| Native check | Cases |
|---|---:|
| Every maximum HP value 1–250 with every counter value 0–999 | 250,000 |
| Every 16-bit counter value at maximum HP 201 and 250, including overflow | 131,072 |
| Hunger, full/zero/injured HP, accelerated healing, and the map gate | 640 |
| **Total** | **381,712** |

All cases passed. The 10 audited spans also match the original in both English
builds. This verifies the selected routines, rather than every map, status,
equipment setup, or save/load transition in the game.

The separate live check loads the Mamel dungeon fixture, sets HP to 39/40 and the
counter to zero, and leaves its enemy active. It verifies no regeneration during
120 idle frames, then observes **six** regeneration updates while holding B+A.
Each update's HP and counter writes match the formula; the fifth update heals
one HP. Enemy damage occurs separately between these updates.

Run from the repository root with the original ROM, its existing mgbdis output,
PyBoy, and the fixture available:

```bash
python3 tools/audit_hp_regeneration.py --emulator \
  --live-state SaveStates/Mamel.state \
  --compare build/shiren-gb2-english-classic-font.gbc \
  --compare build/shiren-gb2-english-shadowed-font.gbc
```

The report is written to `build/hp-regeneration/audit.json`, including verified
span/build hashes, native test counts, and the live HP/counter trace. Omit
`--live-state` to run without that fixture. Emulation uses temporary ROM copies
and does not save gameplay progress.

For a small calculation without emulation:

```python
from tools.audit_hp_regeneration import regen_step

hp, counter = 20, 0
for turn in range(1, 6):
    hp, counter = regen_step(hp, maximum=40, counter=counter)
    print(turn, hp, counter)
# 1 20 200
# 2 20 400
# 3 20 600
# 4 20 800
# 5 21 0
```

Related: [Shiren's damage formula](PLAYER_DAMAGE_FORMULA.md) and
[monster special-move probabilities](MONSTER_SPECIAL_MOVE_RATES.md).
The Japanese [Irupa player notes](https://irupa.jyoukamachi.com/endrta/majouhigasisyoutennsyu.html)
describe the familiar 200-turn baseline and five-HP bracelet recovery. The exact
counter behavior, limits, and overflow case above come from the native ROM audit.
