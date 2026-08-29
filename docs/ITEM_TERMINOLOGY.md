# Item terminology audit

This document records the series-name audit for the identified item catalog. It applies
the source hierarchy in [translation-policy.md](translation-policy.md): Shiren 6, then
Shiren 2, Shiren 5, the local GB1 project, and DS2 for GB2-specific material. A later
official localization wins when it names the same item.

## Result

The first complete pass reviewed 198 usable item identities and corrected 50 names:

| Category | Corrections |
|---|---:|
| Weapons | 5 |
| Shields | 18 |
| Bracelets | 15 |
| Projectiles | 1 |
| Grass | 1 |
| Staves | 8 |
| Pots | 2 |
| **Total** | **50** |

The exact machine-readable contract is
[`tests/fixtures/item_terminology.json`](../tests/fixtures/item_terminology.json).
`tests.test_item_terminology` requires every corrected group-4 name to match its group-6
description heading. It also checks every identified description heading in the complete
1-215 item domain, not only the corrected subset.

The unidentified-item `FILL IN` screen reads category-stripped group-12 roots instead of
the group-4 full names. Twenty-five affected roots were corrected in the same pass, and
the already-correct `Ranzan` root is frozen with them. Root 114 remains deliberately
prefixed as `XImprison`: uppercase `X` is the native disabled-record sentinel and is not
visible player text.

Literal appearances in Help, adventure history, and story dialogue were synchronized too.
The scene editor regenerated dialogue wraps while preserving the original page-control
stream. In particular, Wanda's Club/Wooden Shield explanation keeps its reader-controlled
`<page><box>` boundary. The fixture freezes those reviewed layouts and controls.

## Approved corrections

### Weapons

| Previous | Series name |
|---|---|
| Cudgel | Club |
| Adamant Pickaxe | Wonder Pick |
| Ookabuto Axe | Beetle Axe |
| Air Slayer | Sky Splitter |
| Hidamari's Sword | Hidamari Sword |

### Shields

| Previous | Series name |
|---|---|
| Ration Shield | Shield of Sating |
| Bronzeward | Bronze Shield |
| Wood Shield | Wooden Shield |
| Dragonward | Dragon Shield |
| Windshield | Fuuma Shield |
| Spiked Ward | Counter Shield |
| Armor Ward | Heavy Shield |
| Evasive Shield | Watchful Shield |
| Fragile Shield | Break-Off Shield |
| Stormward | Rasen Fuuma |
| Kabra's Armor | Kabura's Guard |
| Missile Shield | Dodge Shield |
| Deflect Shield | Reflect Shield |
| Curseless Shield | Holy Shield |
| Karakuroid Shield | Traproid Shield |
| Pickpocket Shield | Froggo Shield |
| Satori Shield | Nirvana Shield |
| Ookabuto Shield | Beetle Shield |

### Bracelets

| Previous | Series name |
|---|---|
| Passage Bracelet | Waterwalk Bracelet |
| Diet Bracelet | No Hunger Bracelet |
| Binge Bracelet | Hunger Bracelet |
| Search Bracelet | Vision Bracelet |
| Antidrain Bracelet | No Drain Bracelet |
| Loud Bracelet | Alarm Bracelet |
| Turn Bracelet | Bend Bracelet |
| Paper Bracelet | Paper Thin Bracelet |
| Explosive Bracelet | Blasting Bracelet |
| Miss Bracelet | Bad-aim Bracelet |
| Swipe Bracelet | Critical Bracelet |
| No-Control Bracelet | No Control Bracelet |
| Anti-Feeble Bracelet | Cleansing Bracelet |
| Golden Bracelet | Gold Bracelet |
| Nfu Bracelet | Nfuu Bracelet |

### Other item families

| Category | Previous | Series name |
|---|---|---|
| Projectile | Fatal Arrow | Killer Arrow |
| Grass | Ranzan Herb | Ranzan Grass |
| Staff | Skull Staff | Skull Mage's Staff |
| Staff | Change Staff | Presto Staff |
| Staff | Failure Staff | Miss Staff |
| Staff | Herb Effect Staff | Grass Tosser |
| Staff | Herb Reception Staff | Grass Gainer |
| Staff | Attract Staff | Pull Staff |
| Staff | Raging Staff | Rage Staff |
| Staff | Accelerating Staff | Swift Staff |
| Pot | Healing Pot | Heal Pot |
| Pot | Sealing Pot | Imprison Pot |

The Critical Bracelet description now states that attacks become critical hits. The prior
“heavy damage” wording described the result but obscured the actual series mechanic.

## Layout verification

Storage length was not used to shorten any name or description. The production build
relocates expanded text. Visible geometry was remeasured with Thin Pixel-7:

- the widest changed static names are 94 px and fit the 144 px text canvas;
- the shield-family maximum is `Break-Off Shield+99` at 95 px, ending at x=102;
- the staff-family maximum is `Narrow-escape Staff[99]` at 115 px, ending at x=122;
- the overall equip + modifier + curse + plate maximum still ends at x=132, leaving 12 px;
- the longest active unidentified-name roots are `Narrow-escape` and `Transmutation` at
  13 cells inside the 14-cell canonical preview.

The full item-description wrapper, positioned-surface validator, dynamic item-family test,
two-page Mesen gallery, native Synthesis Pot route, unidentified-item route, production
build, and complete suite are the acceptance gates for terminology changes.

## Names awaiting review

No direct established English precedent was found for these three GB2-specific names. They
remain unchanged and are explicitly provisional instead of being silently presented as
canonical:

| Japanese | Current English | Current effect and review question |
|---|---|---|
| `わなあてのうでわ` | Trap Seek Bracelet | Thrown items seek nearby traps. Is there a later localized equivalent under another name? |
| `せんこうだんのつえ` | Flash Bomb Staff | Illuminates an unentered room. The item was removed from DS2; no direct series name was located. |
| `ゆうじょうのつえ` | Friendship Staff | Turns a monster into an ally. The item was removed from DS2; no direct series name was located. |

When a source resolves one of these, update the group-4 name, group-6 description heading,
group-12 root where applicable, this catalogue, and `item_terminology.json` together.
