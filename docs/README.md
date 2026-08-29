# Documentation

Subject-organized reference for the Shiren GB2 localization. The repository
[README](../README.md) is sufficient to build and test. If you are editing text, start
with [`script/README.md`](../script/README.md). The files here explain the measured rules
behind those workflows.

| Document | Subject | Read it when |
|---|---|---|
| [project-status.md](project-status.md) | Current status | You need authoritative coverage, completed engineering, or remaining work |
| [translation-policy.md](translation-policy.md) | Translation policy | You are choosing terminology, voice, pacing, or line-break policy |
| [editing-workflow.md](editing-workflow.md) | Scene editor | You are editing story/event prose or synchronizing it into a build |
| [testing-and-build.md](testing-and-build.md) | Commands | You need the normal validation, build, test, or diagnostic commands |
| [TEXT_REFERENCE.md](TEXT_REFERENCE.md) | Text system | You need encoding, control tokens, runtime substitutions, storage, or authoring ownership |
| [VWF_BUDGETS.md](VWF_BUDGETS.md) | Renderer contracts | You are deciding whether text fits or changing font/layout behavior |
| [ROM_BANK_MAP.md](ROM_BANK_MAP.md) | Memory ownership | **Before** placing or moving ROM, font, menu, name, spell, graphics, or save data |
| [MENU_STRUCTURE.md](MENU_STRUCTURE.md) | Menu architecture | You are changing a menu constructor, template, navigation graph, cursor, or return path |
| [BLANK_SCROLL.md](BLANK_SCROLL.md) | Blank Scroll writing | You need the valid English inputs, native matching rules, patch design, or manual test route |
| [UNIDENTIFIED_ITEM_NAMING.md](UNIDENTIFIED_ITEM_NAMING.md) | Unidentified item Name / Fill In | You need the mode-0 screen, canonical-token storage/history contract, or deterministic Mesen routes |
| [ENGINEERING_RULES.md](ENGINEERING_RULES.md) | Change gates | Before changing code or claiming a fix complete |
| [TRAPS.md](TRAPS.md) | Disproved assumptions | You are about to generalize a control, renderer, menu, state, or storage behavior |
| [GRAPHICS.md](GRAPHICS.md) | Graphics localization | You are inventorying or replacing graphical Japanese |
| [engineering-overview.md](engineering-overview.md) | Architecture overview | You need the concise explanation of how the ROM and localization fit together |
| [internal-text-audit.md](internal-text-audit.md) | Internal text boundary | You need to understand why 1,028 extracted engine identifiers remain native |

The READMEs within `script/` and `tests/fixtures/` document the files beside them. They
point back to these canonical project rules rather than carrying their own status claims.

## Provenance and authority

These references absorbed the durable conclusions from the project's early findings and
handoff files. Those session-oriented files were removed because their dated milestones
contradicted current progress and made settled rules difficult to find.

Current status and artifact hashes belong in [project-status.md](project-status.md) and the
root README. Byte-level constants and executable tests remain authoritative if prose and
implementation ever disagree. A corrected assumption that is likely to recur should be
recorded in [TRAPS.md](TRAPS.md), not silently erased from institutional memory.
