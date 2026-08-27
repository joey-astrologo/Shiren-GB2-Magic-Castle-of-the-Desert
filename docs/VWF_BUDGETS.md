# VWF budget register

This is the canonical answer to “does this text fit?” for the Thin Pixel-7 GB2 build.
A single character count is never a sufficient verdict.

Every consumer can impose several independent constraints:

1. **ROM storage** — handled by far-pointer relocation.
2. **Composer width** — the source composer wraps when a prospective glyph reaches 144 px.
3. **Renderer width** — the renderer accepts a final pen at 144 px and rejects a slice that
   would reach 145 px.
4. **Vertical geometry** — line count, starting baseline, and line advance depend on mode.
5. **Runtime values** — names, items, locations, counters, and player input expand after
   the literal template is read.
6. **Caller geometry** — positioned menus may expose only part of the 144 px canvas.

## Core renderer profiles

| Profile | Representative mode | Horizontal contract | Vertical contract | Owner |
|---|---:|---|---|---|
| Dialogue | `$02` | `<144` composer px and `<=144` renderer px | 3 physical lines per `<box>`; y=21; `<br>` +11 | `prose_editor.py`, `wrap_en.py`, `wrap_item_messages.py` |
| Full-screen item detail | `$08` | Same 143/144 px limits | 11 composer lines; y=1; `<br>` +11 | `wrap_items.py` |
| Stepped combat window | `$10` | Same 143/144 px limits with native `<cF3>` rollback | y=24; break step +16; context controls lifetime | `combat_messages.py` |
| Positioned/direct | `$04` representative | Surface-specific subrange of the 144 px canvas | One row unless the caller proves otherwise | `surfaces.py`, `build.py` |

“143 composer pixels” means the source line must remain strictly below the `$90` wrap
threshold. “144 renderer pixels” means a final pen position at the right edge is legal.
The two totals can differ for wide prefixed glyph slices and for `<hspace>`, which the
renderer applies without adding it to the composer's width counter.

## Dialogue box accounting

The three-line limit is physical, not textual. `<page>` waits but does not reset the line
cursor, so these two fragments do not have the same occupancy:

```text
Line 1<br>Line 2<page>Line 3
Line 1<br>Line 2<page><box>Line 1 in a new box
```

The first consumes three cumulative lines in one box. The second waits, resets the box,
and begins again. If English needs a fourth cumulative line, add `<page><box>` and repeat
the visible speaker label where appropriate.

`wrap_en.py` uses the fewest safe lines and balances word spaces, but it never invents a
reader-controlled page/box decision. The editor owns pacing.

## Positioned surfaces

The build has explicit contracts for known direct-rendered rows:

| Surface | Start/right edge | Available width | Notes |
|---|---:|---:|---|
| Synthesis-rune description | x=3 to 144 | 141 px | One direct row |
| Item-action command | x=8 to 56 | 48 px | Fixed command column |
| Status condition body | x=1 to 144 | 143 px | Heading fields have separate contracts |
| Diary/front-end hub | x=6 to 80 | 74 px | Conditional rows |
| Start Adventure submenu | x=56 to 144 | 88 px | Up to eight enabled rows |
| Stairs popup labels | x=8 to 64 | 56 px | Both floor and Status routes use widened geometry |
| Main-menu left slots | caller-specific | 50 px typical | Exact slot domains live in `build.py`/`surfaces.py` |
| Main-menu location | right-aligned to x=142 | 83 px from x=59 | Uses the native alignment wrapper |

The status-menu graphical overlay has its own measured label coordinates. Two suffixes
intentionally end exactly at x=144: `%` and `G`. Their exact edge fit is accepted and
fixture-tested.

`surfaces.py` assigns all 120 discovered direct-renderer call sites to known owners. The
positioned audit validates 143 records statically and validates the remaining dynamic row
against its runtime domain.

## Runtime domains

`runtime_widths.py` refuses a bound until every member of the relevant translated family
is explicit. Current maxima are:

| Domain | Maximum |
|---|---:|
| Actor/monster names | 95 px |
| Trap names | 87 px |
| Item names and composed item forms | 109 px |
| Locations | 80 px |
| Seven-byte custom item-name slot | 49 px |

The warning audit for combat templates enumerates actual translated values rather than
substituting one universal worst-case string. A short value may remain on one line while a
long value activates `<cF3>` at the authored word boundary.

The player editor itself is capped at six visible characters. A separate conservative
49-pixel F5 reservation remains in the runtime analyzer for legacy producer shapes; it is
not the name-entry limit.

## Family-specific rules

### Story and ordinary dialogue

- Maximum three cumulative physical lines per `<box>`.
- Keep source pages, boxes, delays, and effect controls in order.
- Use `<page><box>` when a new readable surface is required.
- Allow the measured wrapper to generate normal `<br>` placement from spaces.

### Dungeon item/action messages

- Preserve every source `<cF3>`; all 57 source-bearing rows retain at least one.
- Additional `<cF3>` markers may be added at safe English word boundaries.
- Validate against actual item, actor, trap, and player-name domains before applying.

### Combat/gameplay messages

- Indices 0-109 use the live-proven stepped mode `$10` policy.
- Indices 110-200 include shop, companion, behavior, and scripted families with their own
  modes; do not apply one combat-window assumption to all 201 rows.
- Run `combat_messages.py --warnings-json` after a template or glossary change.

### Item descriptions

- Mode `$08`, 144 px, 11 composer lines.
- Title/stat headers are preserved.
- The wrapper may change only body spaces and `<br>` boundaries; visible wording must
  remain identical.
- Storage expansion is handled by relocation, never by shortening the description.

### Menus and graphical input

- Measure the actual interior, not the overall box width or screen width.
- A cursor or page marker may occupy cells outside the text payload.
- Mode 3 spell input has a four-byte buffer; mode 4 player input has six visible
  characters; the Blank Scroll path remains independent.

## Acceptance policy

Accept an exact edge fit when both composer and renderer models prove it. Do not add
speculative padding by shortening established terminology. Conversely, do not extend a
budget from one surface to another because both happen to use the same font.

After any font-metric change, invalidate every stored width assumption and rerun the full
layout, runtime-domain, menu, build, and emulator test matrix.
