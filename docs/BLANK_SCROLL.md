# Blank Scroll writing system

For the concise player-facing checklist, see [Blank Scroll input list](BLANK_SCROLL_INPUTS.md).

The English build fully localizes Blank Scroll writing while retaining GB2's native
discovery rule. The keyboard is English, accepts up to 11 characters, and includes the
hyphen needed by `Trap-eraser`. Enter the complete localized Scroll name without the word
`Scroll`, as in the other localized Shiren games.

## What the game accepts

Choose **Write**, then enter a name from the table below. Do not type the word `Scroll`.
The Scroll must already have been read and recorded in the current save's notebook.

| Root index | Enter this name |
|---:|---|
| 47 | `Identifier` |
| 48 | `Mapping` |
| 49 | `Pot-upsize` |
| 50 | `Windblade` |
| 51 | `Muzzle` |
| 52 | `Swift Foe` |
| 53 | `Slumber` |
| 54 | `Power Up` |
| 55 | `Bomber` |
| 56 | `Wall-less` |
| 57 | `Monster` |
| 58 | `Confusion` |
| 59 | `Eradication` |
| 60 | `Fear` |
| 61 | `Extraction` |
| 62 | `Carry-ban` |
| 63 | `Exorcism` |
| 64 | `Heavenly` |
| 65 | `Earthly` |
| 66 | `Plating` |
| 67 | `Escape` |
| 68 | `Trap` |
| 70 | `Sanctuary` |
| 71 | `Inaccurate` |
| 72 | `Trap-eraser` |
| 73 | `Sturdy Pot` |
| 74 | `Restock` |
| 75 | `Attraction` |
| 76 | `Altruism` |
| 77 | `Explosion` |
| 78 | `Damp` |
| 80 | `Squid Sushi` |

Capitalization matters. Enter the complete name exactly as shown. Single-letter and other
abbreviated prefixes are not part of the localized interface contract.

The Blank Scroll itself (root index 69) and Sumeragi Scroll (root index 79) are intentionally
excluded by native sentinel records. They cannot be produced by writing a Blank Scroll.

## Audited GB2-specific terminology

The names most likely to be mistranslated from their effects were checked against the
Sharksnack series references instead of being inferred from literal Japanese:

| Japanese root | Localized root | Reference convention |
|---|---|---|
| `ジバク` | `Bomber` | DS2 |
| `ゾワゾワ` | `Fear` | DS2; selected instead of the Shiren 6 `Jitters` variant |
| `へっぴりごし` | `Inaccurate` | DS2 |
| `壺われず` | `Sturdy Pot` | Shiren 2 |
| `たにんかいふく` | `Altruism` | DS2 |
| `ダイバクハツ` | `Explosion` | DS2 |
| `ふはつ` | `Damp` | DS2 |

See the [DS2 Scroll reference](https://sharksnack.github.io/shiren-ds2/items/scrolls),
[DS2 price chart](https://sharksnack.github.io/shiren-ds2/items/price-chart/), and
[Shiren 2 Scroll reference](https://sharksnack.github.io/shiren-2/items/scrolls/).

## Matching and discovery mechanism

The localized mode-1 editor passes its full presentation-layer input to the dedicated
matcher at `251:$4100`. That routine:

1. restricts the search to Scroll roots, group 12 indices 47-80;
2. considers only roots whose notebook/history bit is set in WRAM bank 2 at `$DE1C`;
3. skips records beginning with native sentinel byte `$21`;
4. compares the complete typed name against the embedded localized root table; and
5. caches the resolved root ID at `$C196` for the item-conversion routine.

The legacy matcher at `120:$4853` can accept some prefixes as an implementation detail, but
the localized Blank Scroll path no longer relies on that behavior. The English matcher
requires the complete name, avoiding collisions and matching the expected localized-series
interaction. A correct name still fails on a fresh save if that Scroll has not previously
been read and entered in the notebook.
That discovery requirement is the intended game rule and is consistent with the series'
Blank Scroll behavior documented for [Shiren 2](https://sharksnack.github.io/shiren-2/items/scrolls/)
and [Shiren 6](https://sharksnack.github.io/shiren-6/items/scrolls/).

The disabled records must begin with uppercase `X` in the English source. Uppercase `X`
encodes to `$21`, preserving the native sentinel; lowercase `x` encodes differently and
would accidentally make those entries selectable.

## English engineering

`tools/blank_scroll.py` layers five mode-specific changes over the shared English name
keyboard:

- expands only mode 1 from seven to 11 characters;
- makes the keyboard's otherwise unused `0` cell enter and display a hyphen;
- redirects the Blank Scroll screen through the English keyboard resource;
- matches the full localized name and caches its concrete root ID; and
- restores the original seven-character native field before the action engine resumes,
  then converts from the cached ID instead of reparsing the long text.

Mode 3 Big Moai input remains four characters, and mode 4 player names remain six. The
native controller graph and notebook discovery rule remain unchanged. The entered name is
not persisted to SRAM; only the resolved item identity continues through conversion.

The editor input begins at `$C16D` and safely holds the 11-character English presentation
name. However, the legacy normalized copy begins at `$C18D` and has only seven characters
plus its terminator before live input state at `$C195`. Copying an eighth or later character
there corrupts that state; for `Windblade`, its ninth encoded character overwrote the input
mode and ultimately restarted the game. The localized matcher therefore compares directly
from `$C16D`, never copies the long string into `$C18D`, and reduces the field to the native
seven-character contract only after caching the resolved root ID.

Bank 251 `$4000-$43FF` owns the Blank Scroll overlay. Its guarded call sites and reservation
are recorded in [ROM_BANK_MAP.md](ROM_BANK_MAP.md).

## Testing

For automated coverage:

```sh
python3 -m unittest tests.test_blank_scroll tests.test_pyboy_blank_scroll
```

The catalog fixture freezes all 32 accepted roots and complete inputs, including a byte-for-
byte check that the translated names match the ROM's embedded lookup table. PyBoy exercises
every localized full name with exactly one learned Scroll bit, asserts the matcher returns
the expected ID, and places canaries around the legacy scratch field to prove neither the
input mode nor adjacent state is overwritten. It also tests history-off and inexact input,
the live English tilemap, hyphen entry, the longest roots, and unchanged mode-3/mode-4 limits.

PyBoy covers emulator-level behavior. The catalog route enters accepted names through the
physical keyboard. The exact failure regression loads the self-contained,
user-supplied `blank-scroll.state` at the populated inventory and confirmation screen where
the restart occurred, presses OK, and requires the same object to become a Windblade Scroll
without a reset or inventory damage. If the supplied `blank-scroll.srm` sidecar is present,
its hash is also verified and it is loaded; the immediate regression does not depend on it.

For manual Mesen testing, enter a dungeon, pause, and run
`tools/mesen_spawn_blank_scroll.lua` through **Debug > Script Window**. Resume, reopen
**Items**, and choose **Write**. The helper adds the item only; it does not forge notebook
history, so test a Scroll already discovered on that save. Back up the save or use a
disposable state before injecting live WRAM.
