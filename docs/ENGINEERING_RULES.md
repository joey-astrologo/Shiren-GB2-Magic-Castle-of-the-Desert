# Engineering rules

These are the standing rules for changing the GB2 localization. They are
prescriptive: a change is not complete merely because it assembles, builds, or looks
correct in one screenshot.

For the failure modes behind these rules, see [TRAPS.md](TRAPS.md). For exact ROM
ownership, see [ROM_BANK_MAP.md](ROM_BANK_MAP.md).

## Gates

### Translation-only changes

A translation change must pass its owning editor or wrapper before it reaches the
production catalogs:

| Family | Owner |
|---|---|
| Story/event dialogue | `tools/prose_editor.py` |
| Dungeon item/action messages | `tools/wrap_item_messages.py` |
| Combat/gameplay messages | `tools/combat_messages.py` |
| Item descriptions | `tools/wrap_items.py` |
| Other catalog text | `tools/overlays.py`, then the global validators |

After applying the family change, run the internal-text audit, translation lint,
runtime-width analysis, production build, and relevant tests. The complete command set
is in [testing-and-build.md](testing-and-build.md).

The build being green proves structural safety, not writing quality. Read the text in
context and inspect the real screen before accepting player-facing wording or pacing.

### ROM-layout and renderer changes

Any change that patches native code, moves data, changes a font metric, alters a menu
template, or consumes a new ROM/SRAM range must also satisfy all of these:

1. Resolve the exact native bytes and consumers before writing.
2. Add an expected-byte or cryptographic guard to the owning installer.
3. Add the new range to [ROM_BANK_MAP.md](ROM_BANK_MAP.md).
4. Prove that no existing owner overlaps it.
5. Add a semantic regression for the behavior at risk—not only a byte-difference test.
6. Run the complete 311-test suite with the matching source ROM and PyBoy available.
7. Exercise a real route in an emulator when the change affects rendering, input,
   banking, saving, rankings, or transitions.

A zero-filled range is not sufficient evidence that a native span is free. The currently
allocated high banks were selected only after a whole-ROM free-space audit, and every
dedicated installer verifies its reservation before writing.

### Release claims

GB2 does not yet have GB1's mature release-battery runner or full route fixture library.
Until those exist, do not describe a build as release-complete. A release candidate needs,
at minimum:

- a clean production build from the verified ROM;
- the complete automated suite with no dependency-related skips;
- a clean-clone reproducibility check;
- a full playthrough plus optional allies, endings, postgame, rankings, save/resume, and
  rare menu routes;
- a completed graphics-localization inventory and visual acceptance pass;
- recorded final artifact hashes.

## Fixtures and regressions

Turn every reproducible defect into a fixture or focused behavioral test before—or in the
same change as—the fix. A test should freeze the mechanism that failed, not only the final
English string.

Examples already in the suite include:

- nested far-pointer lookup preserving the outer combat-text bank;
- explicit `<page>` controls requiring a fresh button press;
- cumulative dialogue lines across `<page>` until `<box>` resets the surface;
- question- and exclamation-mark spacing across zero-width controls;
- stairs-popup width and teardown on both floor and Status routes;
- status-menu overlay ownership without mutating the shared Japanese template;
- six-character diary and ranking-name persistence;
- the four-character spell keyboard, navigation graph, and synchronized spell tables;
- generated prose ownership and conflicts between editor, draft, and catalogs.

Tracked JSON fixtures belong under `tests/fixtures/`. Prefer hashes, counts, geometry,
stable IDs, and source-free English. A small reviewed Japanese anchor is acceptable when
it is the evidence for a codec or extraction contract; bulk extracted script is not. See
the local [fixture guide](../tests/fixtures/README.md).

## Playtesting is the discovery mechanism

Static extraction proves known references; it cannot prove that no event enters an
unexpected state, that every branch is reachable, or that dialogue feels natural at native
speed. Automated models also cannot judge whether a menu transition, cursor, palette, or
line break looks good.

When playtesting finds a problem:

1. Record the route, save/state provenance, and visible symptom.
2. Identify whether the failure belongs to storage, composition, rendering, menu ownership,
   input, SRAM, or translation.
3. Reproduce it with the smallest deterministic route available.
4. Freeze the failure in a focused test.
5. Fix it without weakening an unrelated invariant.

Save and ranking screens deserve special attention after banking or name changes because
they exercise persistent data and multiple save layouts. Item Info, action menus, Help,
and nested Status routes deserve special attention after menu-template changes because
they redraw shared surfaces in different orders.

## Generated-file ownership

Do not edit a generated view because it is convenient:

- `script/editing/prose.tsv` owns story/event English.
- `script/drafts/prose.tsv`, `script/en/prose.tsv` story rows, and
  `script/organized/prose.tsv` story rows are generated from that editor.
- `script/drafts/item_messages.tsv` and `script/drafts/combat_messages.tsv` own their
  specialized families.
- `script/script.*` and `script/organized/` are generated from the user's ROM.
- `script/en/*.tsv` is tracked production input, except for cells owned by a specialized
  editor or draft.

The hash-only state files are safety devices. If they report competing edits, reconcile
the text; do not delete the state to silence the conflict.

## Translation and storage

Storage capacity and visible layout are independent. The far-pointer allocator has ample
ROM headroom, so storage is an engineering responsibility. Never remove meaning merely to
fit an original byte slot.

Visible text must still fit its measured consumer. Use pixel widths, native controls, and
complete runtime-value domains; never substitute a character-count guess. The canonical
contracts are in [VWF_BUDGETS.md](VWF_BUDGETS.md).

## Save-state handling

ROMs, ordinary SRAM files, PyBoy states, and personal saves stay untracked. The committed
Mesen reproduction state is an explicit project fixture; its extracted `.srm` remains
ignored. Convert Mesen 2's named `cartRam` field with:

```sh
python3 tools/mesen_state.py SaveStates/Mamel.mss SaveStates/Mamel.srm
```

A state that loads is not proof that it represents the intended route. Tests must assert
the relevant WRAM payload, hook, screen, actor, or control-flow event after loading it.

## Documentation changes

Update documentation with the implementation:

- current progress and remaining work belong in [project-status.md](project-status.md);
- memory ownership belongs in [ROM_BANK_MAP.md](ROM_BANK_MAP.md);
- text/control behavior belongs in [TEXT_REFERENCE.md](TEXT_REFERENCE.md);
- renderer limits belong in [VWF_BUDGETS.md](VWF_BUDGETS.md);
- menu navigation and redraw ownership belong in [MENU_STRUCTURE.md](MENU_STRUCTURE.md);
- a disproved but tempting assumption belongs in [TRAPS.md](TRAPS.md).

Do not leave dated session milestones in a durable reference. Record the stable conclusion,
the evidence, and the rule it creates.
