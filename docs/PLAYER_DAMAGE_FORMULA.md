# Shiren's attack and damage formula

English reference for **Shiren the Wanderer GB2: Magic Castle of the Desert on
Game Boy Color**, verified against the original ROM and mgbdis on **2026-09-09**.

**Shiren's ordinary melee damage depends on his level, current Strength, effective
sword strength, the target's defense, and a random roll.** Incoming ordinary
physical damage uses the same defense and random-damage calculation, with the
monster's attack and Shiren's effective shield strength as its inputs.

This document first explains an ordinary hit, then gives the exact integer
calculation. Critical hits, equipment abilities, transformations, and attacks
with their own damage rules require additional handling; see
[modifiers and scope](#modifiers-and-scope).

- [Shiren's attack power](#shirens-attack-power)
- [Defense and damage variation](#defense-and-damage-variation)
- [Worked examples](#worked-examples)
- [Exact ordinary-hit calculation](#exact-ordinary-hit-calculation)
- [Modifiers and scope](#modifiers-and-scope)
- [ROM evidence and verification](#rom-evidence-and-verification)

## Shiren's attack power

For an ordinary melee attack before temporary attack buffs:

```text
weight = min(255, 8 + Strength + floor(sword_strength / 2))
attack = min(255, floor(level_attack × weight / 16))
```

Here, `floor` means round down. Use **current effective Strength**, including its
bonus, rather than maximum Strength. `sword_strength` is the sword's effective
total strength, including its enhancement and applicable equipment bonuses; it
is not just the `+N` written after the item name. With no sword and no equipment
attack bonus, it is zero.

`attack` is the computed combat value. It is different from the strength of the
sword itself and is capped at **255**.

The native level table is exactly described by:

| Shiren's level | `level_attack` |
|---|---:|
| 1 | 5 |
| 2–26 | `2 × level + 2` |
| 27–99 | `level + 28` |

Examples: level 2 gives 6; level 10 gives 22; level 26 gives 54; level 50 gives
78; level 99 gives 127. With Strength 8 and no sword or bonuses, `attack` equals
`level_attack`.

Practical consequences:

- **One point of Strength contributes as much to the weight as two points of
  sword strength.** Final damage can still stay the same because of rounding or
  the attack cap.
- **Sword strengths 10 and 11 contribute equally.** Going from 11 to 12 raises
  the halved sword contribution by one.
- Level gains increase the base value by two from level 2 through level 26,
  then by one per level. The gain from level 1 to 2 is one.

## Defense and damage variation

For an intuitive estimate of an ordinary hit:

```text
damage ≈ round(attack × (15/16)^floor(defense / 2) × random_factor)
random_factor ≈ 0.879 to 1.121
```

This is an **approximation**. The game actually uses integer table multipliers
and truncates intermediate results. Use the exact procedure below when a one-HP
difference matters.

Defense reduces damage multiplicatively. It is not subtracted directly from
attack. The least significant defense bit is ignored, so **defense 20 and 21
produce identical ordinary-hit results**, as do 0 and 1, 2 and 3, and so on.
Ignoring integer effects, about 22 additional defense roughly halves damage.

For **Shiren taking damage**:

```text
attack  = the monster's current attack power
defense = Shiren's effective shield strength
```

With no shield or equipment defense bonus, Shiren's defense input is zero. His
level and Strength do not directly reduce the HP lost to an ordinary hit. They
matter for his own attack calculation; shield strength supplies this defense
input. Status and equipment effects can modify the normal path.

An ordinary connected hit with positive attack deals at least **1** and at most
**255** damage. A zero-attack input returns zero through this calculation. Misses
are decided separately and are not one of the damage rolls below.

## Worked examples

### Level 10, Strength 8, sword strength 10

Against a monster with defense 10:

```text
level_attack = 2 × 10 + 2 = 22
weight       = 8 + 8 + floor(10 / 2) = 21
attack       = floor(22 × 21 / 16) = 28
```

The exact defense calculation produces the numerator **5,148**, representing
`5148 / 256 = 20.109375` before damage variation. The random adjustment is
`±20 × r`, where `r` is an integer from 0 through 31. The final ordinary damage
range is **18–23**.

The 64 possible random inputs produce this distribution:

| Damage | Random inputs out of 64 |
|---|---:|
| 18 | 11 |
| 19 | 13 |
| 20 | 13 |
| 21 | 13 |
| 22 | 13 |
| 23 | 1 |

Thus, the damage values within the range are not equally likely. These counts
describe the possible random inputs, rather than measured playthrough results.
Raising Strength to 9 raises attack to 30 and changes this matchup's damage
range to **19–24**. Changing sword strength from 10 to 11 leaves it at **18–23**.

### A monster with 50 attack hits Shiren

With no additional damage modifiers:

| Effective shield strength | Ordinary damage received |
|---|---:|
| 0 | 44–56 |
| 10 | 31–40 |
| 20 | 23–29 |
| 21 | 23–29 |
| 22 | 21–27 |
| 40 | 12–15 |
| 100 | 2 |

These are exact ranges from all 64 random inputs, not ranges calculated from
the approximate exponential formula.

## Exact ordinary-hit calculation

The following steps apply after selecting an attack value `A` and defense value
`D`, each from 0 through 255, with no additional damage modifiers.

### 1. Apply defense using integer arithmetic

Start with `Q = A × 256`. `Q` is a numerator whose denominator is 256, allowing
the game to retain a fractional part without floating-point arithmetic.

Ignore the `1` bit of `D`. For each of the following defense bits that is set,
**in ascending order**, replace:

```text
Q = floor(Q / 256) × coefficient
```

| Defense bit | Coefficient | Multiplier represented |
|---:|---:|---:|
| 2 | 240 | 240/256 |
| 4 | 225 | 225/256 |
| 8 | 198 | 198/256 |
| 16 | 153 | 153/256 |
| 32 | 91 | 91/256 |
| 64 | 32 | 32/256 |
| 128 | 4 | 4/256 |

For example, defense 10 contains bits 2 and 8. With attack 28:

```text
Q = 28 × 256              = 7168
Q = floor(7168/256) × 240 = 6720
Q = floor(6720/256) × 198 = 5148
```

The intermediate truncation matters: substituting a single power of `15/16`
will not reproduce every result. After defense, if `A > 0` and `Q < 256`, the
routine increments the low byte by one to preserve a positive result even when
defense has reduced the numerator to zero. A zero-attack input stays zero.

### 2. Apply the random adjustment

Draw one integer `R` from 0 through 63:

```text
r      = floor(R / 2)
change = floor(Q / 256) × r

if R is odd:  Q = Q + change
if R is even: Q = Q - change
```

This gives 32 possible magnitudes and two signs. Zero adjustment has two
representations (`R = 0` and `R = 1`); the other signed adjustments each have
one. The change is calculated from the **integer part** of the pre-variation
damage, which is another reason that a continuous ±12% approximation differs.

If positive addition overflows the native 16-bit accumulator, it substitutes
`Q = 255 × 256`.

### 3. Round and limit the result

```text
if Q == 0:       damage = 0
elif Q < 256:    damage = 1
elif Q >= 65280: damage = 255
else:           damage = floor((Q + 128) / 256)
```

The final step rounds halves **up**. Python's built-in `round()` uses a different
tie rule, so it should not be used as a substitute in an exact calculator.

The executable implementation is in
[`tools/audit_player_damage.py`](../tools/audit_player_damage.py), with
`player_attack`, `defense_fixed`, `ordinary_damage`, and `distribution` helpers.
For example, from the repository root:

```python
from tools.audit_player_damage import player_attack, distribution

attack = player_attack(level=10, strength=8, sword=10)
print(attack)                   # 28
print(distribution(attack, 10)) # {18: 11, 19: 13, 20: 13, 21: 13, 22: 13, 23: 1}
```

## Modifiers and scope

Two attack buffs are included in the audit's player-attack helper:

| Effect | Change before the defense calculation |
|---|---|
| Power Up Scroll | Each stack replaces attack with `min(255, attack + floor(attack/2))`. The stack counter is capped at four. Round down at each stack. |
| Enraged | Doubles the attack value after Power Up processing, capped at 255. |

For example, starting from attack 5, four Power Up stacks produce
**5 → 7 → 10 → 15 → 22**, before defense. Applying a single `1.5^4` multiplier
and rounding only at the end would give the wrong result.

The normal combat path also contains **damage modifiers after defense and before
variation/rounding**, including slayer properties, critical hits, and equipment
effects. The ordinary-hit calculator deliberately leaves those flags clear.
The complete modifier pipeline, hit/miss chances, arrows and thrown items,
monster special moves, fixed damage, shield-specific protections, and
player transformations are outside this formula's verified scope. Do not apply
the ordinary incoming-damage table to every attack that removes HP.

For enemy ability selection rather than damage amounts, see
[Monster special-move probabilities](MONSTER_SPECIAL_MOVE_RATES.md).

## ROM evidence and verification

All bank numbers and addresses below are **hexadecimal**. For example, `77:6ACB`
means bank `$77` (decimal 119), CPU address `$6ACB`. These locations use this
repository's 16 KiB bank convention; debugger bank labels on external sites may
use another convention.

| Location | Evidence |
|---|---|
| `07:7237–729A` | 100-byte level attack table, including unused level 0. All entries match the piecewise formula above. |
| `07:6A3A–6A53` | Level attack lookup; a status-dependent branch can halve the base value. The ordinary formula assumes that status is absent. |
| `07:6CC2–6D01` | Obtains effective sword strength and current Strength, halves sword strength, multiplies by level attack, divides by 16, and caps at 255. |
| `07:6C64–6CAA` | Applies Power Up stacks, Enraged, and another status override. |
| `07:4956–4967` | Caps the Power Up counter at four. |
| `78:4740–478A` | Gets equipped sword/shield strength and adds their equipment bonuses. Returns sword strength in `C`, shield strength in `B`. |
| `7A:48A0–48AD` | Reads the item's base-strength and enhancement bytes. |
| `7E:5176–5192` | Supplies current Strength plus its bonus. |
| `07:6D02–6D27` | Selects the target's defense; the ordinary Shiren branch uses effective shield strength. |
| `77:6401–6458` | Collects attack/defense and effect flags, then calls the damage routine. |
| `77:6ACB–6AF4` | Exact integer defense reduction, preserving a positive minimum for positive attack. |
| `77:6AF5–6AFB` | Seven defense coefficients: `F0 E1 C6 99 5B 20 04`. |
| `77:6AFD–6B22` | Random 6-bit draw, signed variation, and overflow handling. |
| `77:6AB5–6ACA` | Minimum, maximum, and half-up final rounding. |
| `00:0C45–0C58` | Native 8-bit multiplication helper. |

The audit checks the original source ROM with SHA-1:

```text
5264f6d0c4f12c9144de1d12fddadbadd82b3e33
```

It reconstructs bytes from **15 mgbdis spans**, checks them against that ROM,
and compares the same spans with both existing English font builds. All audited
spans match the original in both builds.

PyBoy executes the original routines using isolated inputs and a controlled RNG
result. The following **271,153 native cases** passed:

| Check | Cases |
|---|---:|
| Exact fractional defense numerator for every attack/defense byte pair | 65,536 |
| Complete ordinary damage path for every attack/defense byte pair, zero random adjustment | 65,536 |
| All 64 random inputs for every attack byte at defense 0, 2, 10, 20, 100, and 254 | 98,304 |
| Attack multiplication, division, and cap for every base 0–127 and weight 0–255 | 32,768 |
| Complete player attack getter at every level 1–99 across nine sword strengths and nine Strength values | 8,019 |
| Player attack with all five Power Up counts, with/without Enraged, at every level 1–99 | 990 |

These are native routine checks, not a claim that every equipment combination or
full combat encounter was played through. The player getter tests use empty
equipment slots and the native equipment-bonus field to supply effective sword
strength; they do not test every item's stat construction.

To reproduce, with the original ROM, its existing `build/mgbdis/` output, and
PyBoy available, run from the repository root:

```bash
python3 tools/audit_player_damage.py --emulator \
  --compare build/shiren-gb2-english-classic-font.gbc \
  --compare build/shiren-gb2-english-shadowed-font.gbc
```

Results, exact worked-example distributions, verified span hashes, and compared
ROM hashes are written to `build/player-damage/audit.json`. The audit uses a
temporary ROM copy for emulation and does not save gameplay progress.

### Related Japanese research

The [GB2 probability and damage analysis at 資料置き場](https://w.atwiki.jp/sansara_naga2_sfc/pages/144.html)
publishes the corresponding disassembly and integer algorithm. It helped locate
the routines; the addresses, formulas, and results above were then checked
against this project's original ROM and native execution.

[Irupa's damage investigation](https://irupa.jyoukamachi.com/dame-jikeisann.html)
offers a useful player-facing approximation and explicitly identifies itself as
experimental rather than disassembly-based. It defines its base attack at half
the integer value used here (2.5 rather than 5 at level 1), with compensating
factors in its formula. Do not mix the two base-value conventions.
