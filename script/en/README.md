# English translation workspace

See the canonical [translation policy](../../docs/translation-policy.md) and
[build/test guide](../../docs/testing-and-build.md) before editing or applying a batch.

These tracked TSVs are the source-free editing layer for the GB2 translation. Each
row contains only a stable record `id`, one or more semantic `sections`, and an
`english` cell. Japanese source text and ROM bytes live in the ignored
`script/organized/` catalogs generated from your own ROM.

Edit only `english`. A blank cell means untranslated. Use `<empty>` only when the
finished English record must intentionally contain zero bytes. Preserve renderer
tokens such as `<lookup:...>`, `<number:...>`, `<name>`, `<speaker>`, `<br>`,
`<page>` and `<box>`.

Three families have stricter owners. Author `story_and_event_dialogue` in the
scene-ordered `../editing/prose.tsv`, and group-11 dungeon item/action results in
`../drafts/item_messages.tsv`; author group-8 combat/gameplay messages in
`../drafts/combat_messages.tsv`, rather than editing their generated cells here.
`tools/prose_editor.py --apply` and `tools/wrap_item_messages.py --apply` generate
the measured `<br>` layouts into both catalog views, while `tools/combat_messages.py --apply`
generates validated mode-specific combat text. Their hash-only states reject later manual
edits to generated cells. The 18 `ending_and_credits_text` rows remain
ordinary `english` cells here.

Synchronize before building or committing:

```sh
python3 tools/overlays.py \
  "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
```

Synchronization works in both directions, so English entered in either these files
or the rich catalogs is retained. Different nonblank translations for the same ID
are a conflict and stop the command before either workspace is rewritten.

Check runtime substitutions and glossary consistency:

```sh
python3 tools/lint_en.py "$ROM"
python3 tools/runtime_widths.py "$ROM"
```

Check or apply sentence-level story drafts:

```sh
python3 tools/prose_editor.py "$ROM"
python3 tools/prose_editor.py "$ROM" --apply
python3 tools/wrap_item_messages.py "$ROM"
python3 tools/wrap_item_messages.py "$ROM" --apply
python3 tools/combat_messages.py "$ROM"
python3 tools/combat_messages.py "$ROM" --warnings-json
python3 tools/combat_messages.py "$ROM" --apply
python3 tools/wrap_items.py "$ROM" script/en/items.tsv script/en/items.tsv
```

The wrapper owns only `<br>`. Keep source `<page>`/`<box>` order and exact
`<delay>`/`<cF9>` effects in the draft. `<page>` pauses without moving the pen, so preserve
every source `<page><br>` pair; add extra story boundaries yourself when a
surface would exceed three lines. F4/F5 substitutions are measured at conservative
English maxima. F6 rows stay blocked until their complete translated term domains
provide equivalent bounds. The runtime-width report shows each family's progress,
missing-record count and derived maximum without copying Japanese or English text.

`wrap_items.py` is the corresponding content-preserving wrapper for the mode-$08 item-detail
screen. It may replace spaces with measured `<br>` boundaries, but it must not shorten prose.
ROM storage is handled independently by the far-pointer allocator, and group 6 may span banks.

The glossary is derived from the semantic sections in these TSVs; there is no second
list of Japanese terms to maintain. `<lookup>`, `<number>`, `<name>` and `<copy>`
tokens must survive exactly. If reviewed English intentionally does not use a frozen
term, copy the reported `id`, issue `kind` and `related_id` into
`lint_exceptions.json` and add a concrete reason. Stale or malformed exceptions fail.

Build the localized ROM from this directory:

```sh
python3 tools/build.py "$ROM" script/en build/shiren-gb2-english.gbc
```

The build runs the linter automatically before writing a ROM. `manifest.json` reports
category totals, translation progress and deterministic hashes. It and
`lint_exceptions.json` contain no extracted Japanese text.

The complete translated Help, Wanderer's Secrets and Monster Notebook domains have an additional
family-level audit:

```sh
python3 tools/menu_text.py "$ROM"
```

It verifies all 395 required family records plus four positioned headings, aliases,
native empty slots, critical controls, vertical budgets, positioned-list widths and
the one- or two-line Notebook geometry inherited by each entry type.
