# Scene-ordered prose editing workflow

The canonical instructions are maintained in
[`../../docs/editing-workflow.md`](../../docs/editing-workflow.md), with shared control
rules in [`../../docs/translation-policy.md`](../../docs/translation-policy.md). This
local file records the editor's immediate contract so it is visible beside `prose.tsv`.

`prose.tsv` is the authoritative editing document for story and event dialogue.
It contains all 1,768 dialogue records, grouped into 72 named scenes and ordered
by narrative/event progression as far as the ROM's selectors prove. Within each
scene, `record_order` follows the game's logical selector order. Branching town
states and optional postgame scenes are grouped by phase rather than pretending
that the game enforces one linear playthrough.

The columns are:

```text
scene_order  scene_id  phase  scene_title  record_order  id  english
```

Edit only `english`. The two order fields, scene metadata and stable record ID
are validated and must not be changed. `<empty>` marks the one genuinely empty
native dialogue slot; it is not visible text.

## Editing rules

- Keep every `<lookup:...>`, `<number:...>`, `<name>` and `<copy:...>` token
  exactly.
- Keep source `<page>` and `<box>` boundaries in order. Add `<page><box>` when a
  new readable box is needed; `<page>` alone waits but does not reset the line.
- Keep exact `<delay:...>` and `<cF9:...>` effects.
- Use `Name: ` for speaker labels, not Japanese corner quotes.
- Write natural, complete English. ROM storage is handled by relocation; line
  wrapping is handled separately by the measured wrapper.
- Big Moai spells are four-character codes because the native save/input
  contract is four bytes: `WISH`, `RANU`, `BADE`, `SUGI`, `TSUB`, `MAMA`, and
  `HOYO` for the seven story clues.

## Check an edit

From the repository root:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
python3 tools/prose_editor.py "$ROM"
```

This converts the scene document to a prospective draft, runs the real
Thin Pixel-7 wrapper, checks runtime substitutions and pacing, and runs the
translation linter without changing the workspace.

## Apply and build

After the check succeeds:

```sh
python3 tools/prose_editor.py "$ROM" --apply
python3 tools/internal_audit.py "$ROM"
python3 tools/lint_en.py "$ROM"
python3 tools/build.py "$ROM" script/en build/shiren-gb2-english.gbc
```

`--apply` synchronizes the scene document into `../drafts/prose.tsv`, generates
measured `<br>` placement, and updates both `../en/prose.tsv` and the rich local
`../organized/prose.tsv`. The normal production build then inserts that text.
Do not hand-edit those three generated prose views after adopting this workflow.

`prose.generated.json` stores only hashes. It rejects simultaneous edits in the
scene document and generated draft, while the wrapper's own state rejects edits
made directly to generated catalog cells. If it reports divergence, reconcile
the competing English edits rather than deleting either state file.

Use `--init` only to create the scene document from an already approved draft:

```sh
python3 tools/prose_editor.py "$ROM" --init
```

It is not part of the normal edit/build loop.
