# Internal text audit

See [Project status](project-status.md) for overall coverage and
[Testing and build](testing-and-build.md) for the full validation sequence.

The extracted script contains 1,228 records in the internal directory. They are
not a backlog of ordinary dialogue. The production-facing boundary is fully
classified and checked by `tools/internal_audit.py`:

| Family | Records | Policy | Reason |
|---|---:|---|---|
| Big Moai promotional gift codes ("spells") | 100 | English | The independent mode-3 reward-code screen compares these exact four bytes; these are not rescue passwords. |
| Matching gift-code diagnostic labels | 100 | English | Keeps all indexed diagnostic labels synchronized with the runtime codes. |
| Runtime Monster House/room labels | 12 | English | Group 125 indices 1-12 are composed into the visible `It's <room>!` dungeon alert. |
| Developer event selectors | 126 | Native | Debug event names and placeholder controls, not release dialogue. |
| Debug/engine labels | 197 | Native | Assertion, key-scan, object, animation and engine-development names. |
| Scenario debug labels | 39 | Native | Developer scenario-state selector names. |
| Animation/effect dispatch names | 629 | Native | BGM, event, actor-animation and effect identifiers used by engine tables. This includes the separate group-25 `Monster House` music/effect selector, which is not rendered as dialogue. |
| Internal object null/IDs | 25 | Native | The null entry and remaining dungeon-generation object identifiers are not rendered. |

Thus 212 internal records deliberately receive English overrides and 1,016
retain their original bytes. The audit fails if a required gift-code or room-label record is
blank, an engine-only record gains an override, a record changes family, or the
partition ceases to cover all 1,228 records. The `spell` wording retained in tool and
record identifiers is the game's name for this promotional system, not a rescue category.

This boundary means “translation complete” covers every extracted player-facing
record plus every internal record required by localized runtime behavior. It
does not mean rewriting developer-only identifiers that a normal release build
never renders for the player.

Run the audit with:

```sh
ROM="Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc"
python3 tools/internal_audit.py "$ROM"
```
