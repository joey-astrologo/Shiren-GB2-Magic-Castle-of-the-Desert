# Menu action audit

This audit replaces save-state-by-save-state discovery for action-label overflow. It scans
the original ROM for native event-choice opcode `$1E`, resolves every referenced record
through the translated group-7 table, and measures the staged bytes with the installed
Thin Pixel-7 advances.

Run it from the repository root:

```sh
python3 tools/menu_action_audit.py \
  "Fushigi no Dungeon - Fuurai no Shiren GB2 - Sabaku no Majou (Japan).gbc" \
  --translations script/en
```

The current ROM contains 65 exact 13-byte choice records and 29 unique choice sets. Of
those, 55 records / 19 sets are player-facing event menus in banks 116-117. The ten sets
in bank 180 belong to the developer event menu and are reported separately.

The ordinary event popup has five interior tiles. Its first eight pixels belong to the
cursor, leaving a 32-pixel text budget. The reviewed nine-column service frame has seven
interior tiles and a 48-pixel text budget. Width is the exact direct-renderer advance, not
a character-count estimate.

## Player-facing result

No player-facing action-menu set currently exceeds its selected geometry. The final
confirmed overflow retained the established `Password` terminology and now uses the
reviewed 48-pixel service frame:

| Event record | In-game context | Choice set | Widest label / selected budget |
|---|---|---|---:|
| `116:$6C00` | Good at the Rescue Team, processing a completed rescue | Cable / Password / Cancel / Later | Password: 42 / 48 px |

The approved wording changes all fit without geometry changes:

| Context | Final choice wording | Widest changed label / native budget |
|---|---|---:|
| Training Ground | Train / Info / Quit | Train: 25 / 32 px |
| Training House | Train+ / Info / Quit | Train+: 30 / 32 px |
| Rescue Team rescued-player item prompt | Yes / No / Info / Later | Info: 21 / 32 px |
| Training House dungeon-data exchange | Send / Get / Quit | Get: 16 / 32 px |
| Pigeon Handler password explanations | SOS / Revive / Thanks / Quit | Thanks: 31 / 32 px |

## Manual visual acceptance

The following player-facing menus were visually accepted in the rebuilt ROM on
2026-08-31:

- Training Ground: `Train / Info / Quit`;
- Training House: `Train+ / Info / Quit`;
- Pigeon Handler: `SOS / Revive / Thanks / Quit`;
- Rescue Team rescued-player prompt: `Yes / No / Info / Later`.

The separate Training House dungeon-data exchange (`Send / Get / Quit`) remains covered
by the complete static action audit and its measured native-popup budget.

## Post-rescue live regression

The localized SOS password `I3CqdGY6iuyws` was accepted by the game and is frozen as a
semantic regression fixture. It targets Ancient Ruins 1F with diary ID `$1234`, avoiding
the native self-rescue check in the supplied Rescue Team state.

The shorter `SaveStates/at-rescue.state` fixture starts immediately before completion. The
live regression faces down, completes the rescue, advances Good's dialogue, and detects
the exact four-record selector without relying on timing alone. It requires a nine-column
copy and the complete right border in both CGB VRAM tile and attribute banks. The
constructor stages `Password`'s suffix in off-frame tiles `$9C/$AE` and clears the live
cursor aliases `$A8/$BA`. The regression deliberately overwrites those source aliases,
then uses real Down inputs through Cable, Password, Cancel, and Later while requiring the
literal final-`d` raster, exactly one cursor in the left column, and no graphic in the
right spill column. The corrected result was manually accepted on 2026-08-31. It does not
accept or update a framebuffer hash.

## Confirmed safe coverage

- Fourteen player-facing event choice sets fit their native 32-pixel text budget. This includes
  both `<passwordLeft><passwordRight>` graphic rows, which measure exactly 32 pixels.
- Five event choice sets are safe in the reviewed 48-pixel service frame: Bank Teller,
  both Rescue Team Password selectors, Blacksmith Info, and Warehouse.
- All 24 item-action commands fit their independent 48-pixel columns. `Take Out` is widest
  at 41 pixels.
- Both stairs actions fit their dedicated widened overlay. `Stay Here` is widest at 46 of
  56 pixels.
- The separate positioned-text inventory still assigns all 120 discovered call sites to
  exactly one geometry owner. Its existing family tests remain the authority for main-menu,
  Help, diary, ranking, item-list, and dungeon-selector surfaces.

## Developer-only findings

Bank 180 contains ten developer event-menu sets. Nine overflow the native 32-pixel popup
after translation; only Pot / Arrow fits. They are kept separate from release blockers so
debug tooling does not get mistaken for player-facing game coverage. The audit still lists
them and will fail if these records move into an unclassified bank.

## Regression contract

`tests/test_menu_action_audit.py` freezes the opcode size, complete ROM occurrence and set
counts, player/developer partition, every confirmed release overflow and pixel width, each
review recommendation, the approved `Train` and `Train+` labels, the five widened sets,
the 24 item actions, both stairs labels, and the 120-call-site positioned-text coverage. A
new menu record or changed translation cannot silently inherit an assumed budget.
