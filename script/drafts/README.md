# Sentence-level prose drafts

The canonical story procedure is in
[`../../docs/editing-workflow.md`](../../docs/editing-workflow.md). This directory
documents the generated prose input and the two message families that remain authored
as specialized drafts.

`prose.tsv` is the source-free generated input for all 1,768
`story_and_event_dialogue` records. Author prose in the scene-ordered
`../editing/prose.tsv`; `tools/prose_editor.py --apply` synchronizes this file and
runs the measured wrapper. The 18 ending/credit labels use the ordinary
`../en/prose.tsv` workflow because they are not dialogue boxes.

The scene editor enforces the same natural-English and semantic-control rules:

- preserve every `<lookup:...>`, `<number:...>`, `<name>` and `<copy:...>` exactly;
- preserve source `<page>`/`<box>` order, adding boundaries only when the English
  pacing needs them;
- preserve exact `<delay:...>` and `<cF9:...>` effects;
- use `<br>` only for an intentional forced break—the wrapper generates ordinary
  line breaks from word spaces.

Check without changing either English catalog:

```sh
python3 tools/prose_editor.py "$ROM"
```

Apply only after the check succeeds:

```sh
python3 tools/prose_editor.py "$ROM" --apply
```

The wrapper installs the approved in-game font in memory and measures every line
against both native engines: at most 143 composer pixels, 144 renderer pixels and
three lines on each dialogue surface. It never invents a new page or box. If three
lines are insufficient, author the additional pacing boundary in
`../editing/prose.tsv`. The 25
F6-bearing story records remain explicit errors until `tools/runtime_widths.py`
reports the `item_name` domain ready. Completing its 216 identified names, 123
unidentified appearances and nine unique format-fragment records supplies that bound
automatically.

`prose.generated.json` stores only ROM/partition fingerprints and hashes of wrapper-
owned cells. Do not edit it or hand-edit generated story rows in `../en/prose.tsv` or
`../organized/prose.tsv`; such divergence fails before synchronization writes.

## Narrative scene map

`prose_scenes.tsv` maps all 1,768 story/event records into 72 semantic scene families across
logical groups 33-112. Group/index selectors keep the 25 group-33 item tutorials separate from
the overlapping bad-ending record, while eight duplicate pointer-group pairs share one scene.
Validate the source-free map and current translation progress with:

```sh
python3 tools/prose_scenes.py "$ROM"
python3 tools/prose_scenes.py "$ROM" --json
```

All 1,767 nonempty narrative records are translated; the one native empty slot is tracked
explicitly. Use `../editing/prose.tsv` for the complete scene-ordered view. Its 72 scenes cover
the main story, branches, ally events, side dungeons, postgame quests, town-state dialogue and
gameplay-support scenes without duplicating aliased pointer groups.

## Dungeon item-message drafts

`item_messages.tsv` is the corresponding source-free authoring sheet for group 11
indices 20 through 169. It owns the 150 dungeon item/action result records after the
20 item-name formatter fragments. Edit only its `draft` column, then check or apply it
with:

```sh
python3 tools/wrap_item_messages.py "$ROM"
python3 tools/wrap_item_messages.py "$ROM" --apply
```

The same three-line, 143/144-pixel dialogue contract applies. All 150 rows now have
measured English drafts, including the nine actor-dependent messages unlocked by the
complete actor-name runtime domain. The hash-only `item_messages.generated.json`
protects generated cells in both message catalogs from out-of-band edits.

## Group-8 combat and gameplay messages

`combat_messages.tsv` contains all 201 group-8 records and freezes their semantic
family beside each stable ID. Indices 0-109 are the reusable streamed combat log;
110-200 are separately labeled shop dialogue, companion chatter, behavior/label and
scripted-boss families. Edit only `draft`, then run:

```sh
python3 tools/combat_messages.py "$ROM"
python3 tools/combat_messages.py "$ROM" --warnings-json
python3 tools/combat_messages.py "$ROM" --apply
```

The reusable combat rows are measured in the live-proven mode `$10`. Insert `<cF3>`
at a safe English word boundary when a runtime name can make the sentence long: the
marker is invisible for short values and becomes a native break only when necessary.
The warning report exhausts actual translated-name width combinations and separates
one-line, soft-wrapped and unsafe outcomes. Unsafe rows do not apply. The tool also
preserves substitutions, source page/box order and timing effects. English character labels use
`Name: `; unmatched Japanese `<speaker>` corner quotes are rejected. Paired
`<speaker>...<speakerEnd>` tokens remain available only for an intentionally quoted label.
`combat_messages.generated.json` protects its generated cells.

The completed reviewed batches cover indices 0-200: damage, attack outcomes, experience,
levels, resources, traps, monster abilities, theft, actor stat changes, statuses, shop/alarm
dialogue, both Nfuu families, Mamo condition chatter, Oryu condition chatter and Pekeji condition
chatter, plus the Doll/robot condition chatter, actor behavior/labels, Big Moai's interrupted
lecture and transformation lines, the short scripted reactions, the Evil God narration and
Koppa's warning. This completes all 201 records in group 8.
