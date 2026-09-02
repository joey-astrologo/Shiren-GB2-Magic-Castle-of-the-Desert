# Text reference — Shiren GB2

This is the measured reference behind translation editing: file ownership, character
encoding, controls, storage, runtime substitutions, and the checks that protect them.

Start with [`script/README.md`](../script/README.md) when you only need to know which file
to edit. Use this document when a token, renderer path, or build error needs explanation.

## 1. Record and workspace model

The authoritative extractor follows the game's 126-entry group directory and resolves
6,695 unique records through 7,163 logical references. Stable IDs use the original source
location, such as `195:$562F`; they do not change when English text is relocated.

| Layer | Role | Tracked |
|---|---|---|
| `script/script.json`, `script/script.tsv` | Raw extraction from the user's ROM | No |
| `script/organized/` | Source-rich semantic catalogs with Japanese and validation metadata | No |
| `script/en/` | Compact source-free production English | Yes |
| `script/editing/prose.tsv` | Authoritative scene-ordered story/event editor | Yes |
| `script/drafts/` | Specialized item/combat authoring and generated prose input | Yes |

The generated and compact catalogs share stable IDs. A blank English cell means no
override. `<empty>` is the only explicit request to replace a native record with zero
visible bytes.

## 2. English character set

The production English code page contains digits, uppercase, lowercase, space, and this
punctuation:

```text
.,'-?!():/[]+~%"
```

The mapping is intentionally separate from the Japanese source codec. Codes `$30-$49`,
which decode as hiragana in the source ROM, become lowercase `a-z` only after the English
font is installed. Keeping separate codecs prevents extraction from misreading Japanese
bytes through the localized font mapping.

Unencodable characters are errors; the tools never silently replace them. Use straight
ASCII apostrophes, double quotes, and punctuation. Visible dialogue attribution is
`Name: dialogue`, not Japanese corner quotes. Quoted speech, labels, passwords, and menu
names use the one-byte ASCII `"` glyph at `$59`; production lint rejects the native
`<quoteOpen>`, `<quoteClose>`, `<speaker>`, and `<speakerEnd>` artwork.

The Japanese source also contains two-byte prefixed glyphs beginning with `$F0-$F2`.
`data/kanji.tsv` maps all 281 referenced valid glyphs: 270 kanji, four symbols, and seven
named/composite tokens. Unknown bytes remain lossless raw tokens rather than guesses.

## 3. Source composer versus renderer

GB2 processes most dialogue in two stages:

1. The ROM-source composer at `0:$312B` reads a record, expands runtime substitutions,
   applies conditional wrapping, and stages bytes in WRAM.
2. The renderer consumes the staged bytes, composes proportional glyph pixels into the
   shadow canvas, and uploads tiles.

The distinction matters because `$F4-$F6` are argument-bearing substitutions in ROM source
but ordinary staged glyph slots after expansion. A parser that treats an `$FF` argument as
a record terminator will split valid records and corrupt the script graph.

The direct positioned-text path is different again: selector `0:$1FA0` copies a record to
a caller buffer, and bank-17 wrappers choose coordinates before calling `3:$5E62`. Menus
using that API have surface-specific widths rather than the dialogue box's general budget.

## 4. Runtime substitutions

These tokens are executable source data and must preserve their arguments and counts:

| Token | Source opcode | Meaning |
|---|---:|---|
| `<copy:AA:BB:CC>` | `$F4` | Copy a runtime byte-count/value form selected by three arguments |
| `<name>` | `$F5 FF` | Insert the complete player name |
| `<name:NN>` | `$F5 NN` | Insert a bounded player-name form selected by the argument |
| `<lookup:LL:HH>` | `$F6 01 LL HH` | Insert a table-selected runtime string |
| `<number:LL:HH>` | `$F6 03 LL HH` | Legacy name for a generic cached runtime string; not always numeric |
| `<sourceF6:MM:LL:HH>` | `$F6 MM LL HH` | Lossless form for another F6 mode |

`lint_en.py` verifies parity, while `runtime_terms.py` classifies producers and
`runtime_widths.py` derives bounds only from complete translated domains.

Current complete maximums under Thin Pixel-7 are:

| Runtime domain | Maximum width |
|---|---:|
| Actor/monster name | 95 px |
| Trap name | 87 px |
| Identified/composed item name | 109 px |
| Location name | 80 px |
| Seven-byte custom item-name slot | 49 px |

The localized player editor accepts six visible characters. Some legacy F5 analysis keeps
a conservative seven-byte/49-pixel reservation; that is safe headroom, not permission for
the player editor to store seven characters.

Four polymorphic debug-only consumers remain intentionally unbounded. They are not
player-facing production text and are classified by the internal audit.

## 5. Renderer controls

| Token | Byte | Behavior |
|---|---:|---|
| `<cF3>` | `$F3` | Composer soft-wrap checkpoint; renderer no-op when unused |
| `<hspace:NN>` | `$F7 NN` | Add horizontal renderer space; composer does not count it |
| `<cF8>` | `$F8` | Renderer no-op and ROM-template escape; following native 0-9/a-z selector bytes must remain byte-exact |
| `<cF9:LL:HH>` | `$F9 LL HH` | Pass a two-byte effect argument to the native handler |
| `<delay:NN>` | `$FA NN` | Set native character/timing delay |
| `<page>` | `$FB` | Wait for fresh input; does not reset pen or physical line count |
| `<box>` | `$FC` | End the renderer invocation/reset the dialogue surface; no guaranteed wait |
| `<br>` | `$FD` | Advance a line immediately and reset horizontal position |
| `<cFE>` | `$FE` | Named no-op retained losslessly |

The controls are not interchangeable:

- Preserve at least one `<cF3>` when the Japanese source contains it. It remains invisible
  if the expanded English fits and becomes a break only when the native composer reaches
  its threshold.
- `<br>` does not wait. It is appropriate for a measured line break, not pagination.
- `<page>` waits but does not start a fresh physical box. Line occupancy continues across
  it until `<box>`.
- `<box>` resets the surface but does not itself protect reading time. For a new readable
  dialogue box, use `<page><box>`.
- A native `<page><br>` means wait and then advance a line. Preserve both while the
  cumulative box remains safe.
- Do not edit lowercase/digit selector runs immediately following `<cF8>`. The English
  source codec deliberately keeps those bytes in the native Latin domain rather than the
  localized font domain. For example, `<cF8>g` must encode as `F8 10`, not `F8 36`; Big
  Moai's reward formatter consumes that selector before ordinary rendering.
- Controls have zero horizontal width. Write `?<page> Next` or `!<page> Next`, not
  `?<page>Next` or `!<page>Next`.

The production patch clears the game's global automatic-text bypass whenever an explicit
`<page>` is encountered. Cinematic records without `<page>` retain native delay-driven
automatic behavior.

## 6. Speaker tokens and named glyphs

`<speaker>` and `<speakerEnd>` are named prefixed glyphs from the Japanese font, not the
same thing as `<page>` or `<box>`. An unmatched opening `<speaker>` after a Japanese name
is a dialogue separator and must become `: ` in English. A paired form may remain only
when it intentionally quotes a visible in-game label.

Other named prefixed tokens represent composite symbols whose identity is preserved in
`data/kanji.tsv`. Do not convert one into punctuation based only on its appearance in a
single screenshot. `<cracked>` remains the lossless source token `F2 1E`; the production
graphics pass localizes that token's stock Japanese `(hibi)` bitmap to `(Cr)` without
changing script records or renderer width metadata.

### Dynamic item-name producers

Translated item roots are only one input to the inventory row. Native formatter code adds
signed weapon/shield modifiers, arrow stack counts, staff charges, Pot capacities, Gitan
amounts, monster-meat roots, and status decorators. `item_formatting.py` changes the
language-bearing producer punctuation to `N Name`, `Name[N]`, and the English `-`; it does
not encode those additions into group-4 translations. The exact object fields, row budget,
and visual gallery are documented in [ITEM_FORMATTING.md](ITEM_FORMATTING.md).

The town shop's multiple-sale count is another runtime-produced value. Native code appends
the Japanese item counter `ko` to the decimal count; `shop_sale_count.py` terminates that
cached value after its digits so the translated `<cF8>5 items` sentence supplies the noun.

## 7. Storage model

The original script occupies banks 192-205. The production build reconstructs every
pointer table and record in a far-pointer arena at banks 215-239, then rewrites the group
directory. The current complete English payload uses banks 215-233 and leaves six arena
banks untouched.

Translation length is therefore constrained by total arena capacity, not the original
record or bank. Storage pressure is an engineering problem. Do not abbreviate or delete
meaning to preserve the Japanese byte count.

Display geometry remains real. A record can have unlimited relocated storage and still be
unsafe for its dialogue box, item page, action column, or positioned menu row. See
[VWF_BUDGETS.md](VWF_BUDGETS.md).

## 8. Authoring ownership

| Text type | Edit here | Apply/check with |
|---|---|---|
| Story and event dialogue | `script/editing/prose.tsv` | `tools/prose_editor.py` |
| Item/action results | `script/drafts/item_messages.tsv` | `tools/wrap_item_messages.py` |
| Combat/gameplay messages | `script/drafts/combat_messages.tsv` | `tools/combat_messages.py` |
| Item descriptions | `script/en/items.tsv` | `tools/wrap_items.py` |
| Glossary, menus, Help, monsters, endings | corresponding `script/en/*.tsv` | `tools/overlays.py` plus global checks |

Do not hand-edit a generated prose cell. The editor and wrapper state hashes reject
out-of-band changes so one view cannot silently overwrite another.

## 9. What the build checks

The production builder checks:

- source-ROM identity and expected native patch bytes;
- stable IDs and source metadata;
- encodability and control/substitution parity;
- glossary consistency and reviewed exceptions;
- complete runtime-width domains where required;
- dialogue and positioned-surface geometry;
- deterministic far-pointer allocation and all 7,163 references;
- font, name, Big Moai gift-code, menu, stairs, and pacing patch installation;
- dynamic item formatter anchors, punctuation, and item-row geometry;
- header and global cartridge checksums.

## 10. What the build cannot prove

The build does not prove:

- that a sentence is natural, accurate, or in the correct character voice;
- that every optional event route has been reached;
- that a page break feels well paced at native typewriter speed;
- that an unknown event never enters an interior state not represented by known selectors;
- that graphical Japanese outside the text systems has been localized;
- that every menu transition is visually clean after arbitrary navigation history.

Those require editorial review, playtesting, route fixtures, and visual inspection.
