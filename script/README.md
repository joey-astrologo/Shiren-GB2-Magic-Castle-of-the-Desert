# Editing the GB2 script

Project-wide policy and commands are maintained in [`../docs/`](../docs/README.md).
Use the [scene editing workflow](../docs/editing-workflow.md) for dialogue and the
[build/test guide](../docs/testing-and-build.md) before committing generated changes.
The detailed control/storage rules are in
[`../docs/TEXT_REFERENCE.md`](../docs/TEXT_REFERENCE.md), with pixel budgets in
[`../docs/VWF_BUDGETS.md`](../docs/VWF_BUDGETS.md).

The raw `script.json` and `script.tsv` are generated from your own original ROM and
are the authoritative extraction. The files under `organized/` are the same 6,695
stable records divided into translator-facing categories, including Japanese source
and validation metadata. The tracked files under `en/` are their compact,
source-free English editing layer. Sentence-level story translation is authored
in the scene-ordered `editing/prose.tsv`; dungeon item/action messages live in
the tracked drafts under `drafts/`. Their measured `<br>` controls are generated
into both catalog views.

## Generate or refresh the files

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
python3 tools/extract.py "$ROM" --out script
python3 tools/organize.py "$ROM"
python3 tools/overlays.py "$ROM"
python3 tools/lint_en.py "$ROM"
python3 tools/runtime_widths.py "$ROM"
python3 tools/prose_editor.py "$ROM"
python3 tools/wrap_item_messages.py "$ROM"
python3 tools/wrap_items.py "$ROM" script/en/items.tsv script/en/items.tsv
```

Regenerating `organized/` preserves existing `english` cells by stable record ID.
It refuses stale source metadata, duplicate IDs, and malformed rows rather than
discarding work. `overlays.py` then synchronizes those cells with `en/` in both
directions. A blank cell on either side cannot erase a nonblank translation. If both
sides have different nonblank text for one ID, synchronization stops before writing
and reports the conflict.

The raw and organized files contain extracted game text and are ignored by git.
`en/` contains only stable IDs, semantic section names and English cells, so it is
the translation workspace committed to the repository.

The scene editor is the normal prose entry point. Use its `--init` option only when
deliberately creating the editor from an already approved draft; use `--apply` after
the ordinary check succeeds.

## Which file to open

| File | Contents | Records |
|---|---|---:|
| `organized/glossary.tsv` | Actor/monster names, item names and appearances, item abilities, traps, locations and numbered monster variants | 1,938 |
| `organized/items.tsv` | All identified-item descriptions | 216 |
| `organized/monsters.tsv` | Monster Notebook and monster-meat descriptions | 459 |
| `organized/ui_system.tsv` | Menus, labels, status conditions, rankings and positioned system text | 493 |
| `organized/help.tsv` | Wanderer's Guide, controls, techniques and Wanderer's Secrets pages | 176 |
| `organized/messages.tsv` | Combat, dungeon, item-action and runtime gameplay messages | 399 |
| `organized/prose.tsv` | Story, event, ending and character dialogue | 1,786 |
| `editing/prose.tsv` | Authoritative scene-ordered story/event editing document | 1,768 |
| `drafts/prose.tsv` | Generated record-order input to the measured prose wrapper | 1,768 |
| `drafts/item_messages.tsv` | Source-free group-11 dungeon item/action message drafts | 150 |
| `drafts/combat_messages.tsv` | Source-free, partitioned group-8 combat/gameplay message drafts | 201 |
| `organized/internal.tsv` | Debug, scenario, password, animation and engine-facing labels | 1,228 |
| `organized/review.tsv` | Unknown or conflicting classifications | 0 |

`organized/manifest.json` freezes the counts, sections and assignment hashes. The
current partition covers all 6,695 records and 7,163 logical references exactly
once. The review file is intentionally present even while empty: any future group
that lacks one unambiguous rule lands there instead of being guessed.

## Columns and editing rules

Each TSV row contains:

```text
id  sections  length  original_hex  references  interior_of  review_reasons  japanese  english
```

Only edit `english`. The stable `bank:$address` ID is the build key; the length,
original bytes and Japanese columns protect against stale extraction. A blank
English cell means untranslated. Use the explicit `<empty>` sentinel only when a
source record genuinely needs to become empty.

The compact `en/*.tsv` files contain only:

```text
id  sections  english
```

Normally edit `en/` and consult `organized/` for Japanese context. It is also safe
to enter English directly beside the Japanese in `organized/`; run `overlays.py`
afterward to copy it into the tracked workspace. `en/manifest.json` records progress
counts and deterministic fingerprints without embedding source text.

The exception is the 1,768 `story_and_event_dialogue` rows. Author their natural
English in `editing/prose.tsv`, retaining required runtime and story controls,
then run:

```sh
python3 tools/prose_editor.py "$ROM"          # check only
python3 tools/prose_editor.py "$ROM" --apply  # sync, wrap and update catalogs
```

Do not hand-edit the generated draft or catalog English for those rows. The
hash-only editor and wrapper states detect that conflict before catalog files are
rewritten.
The wrapper uses the installed Thin Pixel-7 advances and both native limits: at most
143 composer pixels, 144 renderer pixels and three lines per dialogue surface. It
balances safe word spaces across the minimum number of prose lines; translators still author
`<page>` and `<box>` pacing. `<page>` only pauses and does not move the pen, so a source
`<page><br>` pair has a mandatory line advance and cannot be reduced to `<page>`. Source
boundaries may not be dropped or reordered, exact
`<delay>`/`<cF9>` effects must survive, and runtime substitutions remain exact.
The 25 story records with F6 cached strings fail closed until the report from
`runtime_widths.py` marks `item_name` ready. That happened automatically after all
216 identified names, 123 unidentified appearances and nine unique group-11 format
fragments received explicit English cells. The bound uses the widest of an
identified name, an appearance, or a fragment plus the structurally capped
seven-byte custom name. All 25 are now translated as the first-discovery item tutorials and
generated through this measured prose workflow.

The 150 group-11 dungeon item/action results use the same ownership model through
`drafts/item_messages.tsv` and `tools/wrap_item_messages.py`. All 150 are translated and
measured, including the nine actor-dependent rows unlocked by the completed actor-name
domain. Authored `<cF3>` checkpoints use the real conditional rollback path and are validated
against the widest runtime values without being converted to fixed `<br>` controls. All 57
records whose Japanese source has F3 retain at least one checkpoint; English uses 64 across
those records because seven long sentences need a second safe boundary.
`drafts/item_messages.generated.json` protects the generated message cells.

Group 8 uses `drafts/combat_messages.tsv` and `tools/combat_messages.py`. The table contains
201 records but is frozen into 16 semantic families: indices 0-109 are reusable combat-log
messages, while the rest include shop dialogue, companion chatter, behavior labels and boss
scenes. Do not apply the combat-log layout policy to all 201 rows indiscriminately. Check or
apply authored cells with:

```sh
python3 tools/combat_messages.py "$ROM"
python3 tools/combat_messages.py "$ROM" --warnings-json
python3 tools/combat_messages.py "$ROM" --apply
```

The combat-log validator uses the live-proven stepped-window mode `$10` (y=24, 16-pixel line
steps). Translators own `<cF3>` soft-wrap checkpoints: they remain invisible when the expanded
message fits and become a native line break only when the composer reaches 144 pixels. The
warning report enumerates every distinct translated actor, trap or item value as applicable;
any unsafe combination fails before synchronization. Runtime substitutions, page/box order,
timing effects and `<speaker>` separators remain protected. Generated cells are owned by
`drafts/combat_messages.generated.json` and must not be hand-edited in either catalog.

Item descriptions use their separate proven full-screen surface. `wrap_items.py` preserves the
title/stat header and every visible body character, changing only spaces versus `<br>` boundaries.
It enforces the 144-pixel canvas and 11-line composer limit. Do not shorten descriptions for ROM
storage: relocated far pointers allow group 6 records to occupy multiple empty banks.

Do not remove or casually reorder control tokens such as `<lookup:...>`,
`<number:...>`, `<name>`, `<speaker>`, `<br>`, `<page>` or `<box>`. They describe
runtime substitutions and renderer behavior, not translator notes. `lint_en.py`
requires every `<lookup>`, `<number>`, `<name>` and `<copy>` substitution to survive
with the same arguments and count. It also requires every translated record whose Japanese
source contains `<cF3>` to retain at least one native conditional checkpoint. English may add
checkpoints when its word order or expansion needs them.

The same linter derives 1,869 glossary definitions directly from the semantic
partition. It rejects one Japanese definition translated two ways, distinct terms
in the same family collapsed to one English name, and translated records that ignore
an already translated actor, item, appearance, trap or location name in their source.
Longer terms mask nested shorter terms even while the longer definition is blank, so
incremental glossary work does not create false failures.

Run it directly for a report:

```sh
python3 tools/lint_en.py "$ROM"
python3 tools/lint_en.py "$ROM" --tsv
```

The production build runs the same check automatically before writing its output.
Deliberate terminology exceptions belong in `en/lint_exceptions.json` and require the
exact reported stable-ID pair plus a written reason. Stale exceptions fail instead of
silently accumulating.

Once at least one English cell is populated, build directly from the tracked
workspace:

```sh
python3 tools/build.py "$ROM" script/en build/shiren-gb2-english.gbc
```

The build also accepts `script/organized` for local inspection. All category TSVs
are loaded in filename order, duplicate translated IDs fail the build, and any lint
problem stops it before an output ROM is written.
