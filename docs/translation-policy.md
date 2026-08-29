# Translation policy

The byte/control reference is [TEXT_REFERENCE.md](TEXT_REFERENCE.md); measured renderer
limits are maintained separately in [VWF_BUDGETS.md](VWF_BUDGETS.md).

Translation decisions use these priorities, in order:

1. Text must fit its proven runtime surface. Dynamic combinations may carry an
   explicit warning until their complete value domain is measured.
2. English must read naturally in context.
3. Terminology must follow established Shiren localization conventions.

ROM storage is not a reason to shorten, simplify, or omit meaning. The far-pointer
allocator owns storage pressure; rendering and line layout are separate constraints.
Safe line breaks are welcome when the surface has been measured.

## Terminology sources

For terminology shared with later games, prefer the English used by Sharksnack's
Mystery Dungeon Franchise Wiki in this order:

1. Shiren 6
2. Shiren 2
3. Shiren 5
4. The local `../shiren-gb-public` translation

The unfinished DS2 / *Magic Castle DS* localization is the closest mechanical and
contextual reference for GB2-exclusive items, effects, characters, and locations.
Cross-check incomplete or unofficial wording against the Japanese source and choose
natural English. The *Magic Castle GBC* pages may supply names absent from DS2. A later
official localization takes precedence for a shared series term.

Use modern category nouns consistently: `Bracelet`, `Grass`, `Scroll`, `Staff`, and
`Pot`. Established individual names such as `Herb`, `Otogirisou`, and `Bufu's
Riceball` retain their series wording even when their category noun differs.

The approved item-name mapping and unresolved GB2-only terms are maintained in
[ITEM_TERMINOLOGY.md](ITEM_TERMINOLOGY.md). An item rename is incomplete until its group-4
name, group-6 description heading, applicable group-12 unidentified-item root, literal
Help/UI/dialogue references, and terminology fixture agree.

## Dialogue and control rules

- Author story/event prose in `script/editing/prose.tsv`; see the
  [editing workflow](editing-workflow.md).
- Preserve every runtime substitution and semantic control unless its owning tool
  explicitly transforms it.
- Use visible speaker labels in the form `Name: dialogue`. Do not retain the unmatched
  Japanese corner-quote `<speaker>` separator in translated dialogue.
- Measure names and lines with the installed Thin Pixel-7 advances, not character counts.
- Keep distinct unidentified item appearances distinguishable.
- Add a lint exception only when identical or divergent English is semantically required,
  and document the reason.

The dialogue controls are not interchangeable:

- `<cF3>` is the native conditional soft-wrap checkpoint. Preserve at least one when
  the Japanese record contains it. It is invisible while the expanded text fits and
  becomes a break only when needed. English may add checkpoints at safe word boundaries.
- `<br>` advances to the next line immediately and does not wait for input. Use it only
  for an intentional measured break or let the owning wrapper generate it.
- `<page>` waits for player input but does not reset the physical box or line cursor.
- `<box>` resets the dialogue surface but does not itself guarantee a reader-controlled
  wait.

Count visible lines cumulatively from one `<box>` boundary to the next. If English would
push a three-line box onto a fourth cumulative line, use `<page><box>` and repeat the
speaker label when dialogue continues. Do not replace the wait with `<box>` alone. Preserve
a native `<page><br>` when the cumulative English surface still fits, because the pair
means wait and then advance a line.

Controls have zero horizontal width. Preserve ordinary sentence spacing across them:
write `?<page> Next` and `!<page> Next`, not `?<page>Next` or `!<page>Next`.

## Fixed runtime contracts

Player names have a six-character visible limit and default to `Shiren`. Big Moai's
promotional gift codes (called "spells" in game) use four-byte input and comparison buffers
and are not rescue passwords. Their keyboard, 100 codes, diagnostic labels, and seven story
clues must remain synchronized. The story codes are
`WISH`, `RANU`, `BADE`, `SUGI`, `TSUB`, `MAMA`, and `HOYO`.

Before completing an edit batch, run the scene/catalog owner, overlay synchronization,
translation lint, runtime-width checks, internal audit, production build, and tests
described in [Testing and build](testing-and-build.md).
