# Story editing workflow

`script/editing/prose.tsv` is the authoritative editor for story and event dialogue.
It contains 1,768 stable records in 72 named scenes, ordered by narrative progression
where ROM selectors prove an order. Branches, town states, optional events, and postgame
scenes are grouped by phase rather than forced into a false single chronology.

The columns are:

```text
scene_order  scene_id  phase  scene_title  record_order  id  english
```

Edit only `english`. Do not change the stable ID or scene/order metadata. Use `<empty>`
only for the one genuinely empty native dialogue slot. Follow the control and terminology
rules in [Translation policy](translation-policy.md).

## Check an edit

From the repository root:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
python3 tools/prose_editor.py "$ROM"
```

The check converts the scene document into a prospective generated draft, runs the real
Thin Pixel-7 wrapper, validates substitutions and pacing, and runs translation lint without
changing the workspace.

## Apply and build

After the check succeeds:

```sh
python3 tools/prose_editor.py "$ROM" --apply
python3 tools/internal_audit.py "$ROM"
python3 tools/lint_en.py "$ROM"
python3 tools/build.py "$ROM" script/en build/shiren-gb2-english.gbc
```

`--apply` synchronizes the editor into `script/drafts/prose.tsv`, generates measured
`<br>` placement, and updates `script/en/prose.tsv` plus the rich local
`script/organized/prose.tsv`. Those are generated views for this family; do not hand-edit
their prose cells.

`script/editing/prose.generated.json` and the wrapper state store hashes only. They reject
conflicting edits between the authoritative editor, generated draft, and generated catalogs.
Reconcile the competing text if divergence is reported instead of deleting state files.

Use `python3 tools/prose_editor.py "$ROM" --init` only to create or deliberately refresh
the scene editor from an already approved draft. It is not part of the normal edit/build
loop.

Other text families keep their specialized owners:

- `script/drafts/item_messages.tsv` with `tools/wrap_item_messages.py`
- `script/drafts/combat_messages.tsv` with `tools/combat_messages.py`
- `script/en/items.tsv` with `tools/wrap_items.py`
- the ordinary compact `script/en/*.tsv` catalogs for unowned UI, glossary, Help,
  monster, and ending/credit rows
