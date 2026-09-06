# Item-name source precedence audit

Audit date: 2026-09-06  
Status: audit only; no production translation, tool, fixture, or policy changes have
been applied.

## Proposed rule

This audit models the requested item-name priority as:

1. Shiren 2
2. Shiren 4
3. Shiren 6

The comparison is by item identity, not merely by similar mechanics or an English
substring. An older game's name is selected only when its Japanese item identity matches
the GB2 item. For example, GB2's `ハラモチの盾` falls through to Shiren 4's `Diet Shield`;
Shiren 2's mechanically similar `Leather Shield` is a different Japanese item and is not
substituted. The local GB2 wording remains the fallback when none of the three sources has
the item.

This is intentionally a literal source-precedence model. It therefore selects source
forms such as `Crescent Arm`, `Dragon Tile Bracelet`, and `Mon House Scroll`, even where the
current name may be more immediately descriptive or follows a newer category convention.

## Source snapshots

The public wiki repositories were pinned so the result can be reproduced even if a live
page changes later.

| Priority | Source | Audited revision |
|---:|---|---|
| 1 | [Shiren 2 items](https://github.com/SharkSnack/shiren-2/tree/ff87dda6424c0466e09bcf50cc92fe164c6ae9e6/content/items) | `ff87dda6424c0466e09bcf50cc92fe164c6ae9e6` |
| 2 | [Shiren 4 items](https://github.com/SharkSnack/shiren-4/tree/4b92b02a28e8ccaaa4970e3f8297c9631400ac7f/content/items) | `4b92b02a28e8ccaaa4970e3f8297c9631400ac7f` |
| 3 | [Shiren 6 items](https://github.com/SharkSnack/shiren-6/tree/fc63a3e621909cf98377da0e584a10eab513bd1d/content/items) | `fc63a3e621909cf98377da0e584a10eab513bd1d` |

## Result

The existing catalog contains 198 usable item identities. Under the proposed order, 70
names change and 128 remain unchanged.

| Category | Reviewed | Renamed |
|---|---:|---:|
| Weapons | 33 | 15 |
| Shields | 28 | 4 |
| Bracelets | 27 | 12 |
| Projectiles | 7 | 1 |
| Food | 7 | 1 |
| Grass | 20 | 8 |
| Scrolls | 34 | 14 |
| Staves | 26 | 10 |
| Pots | 16 | 5 |
| **Total** | **198** | **70** |

Of the 70 changes, 49 come from Shiren 2 and 21 from Shiren 4. Shiren 4 is also the
winning source for `Ordinary Pot`, but that spelling already matches the current name, so
it creates no rename. No changed item reaches Shiren 6 after the first two layers.

The three precedent-free GB2 names remain unchanged and provisional: `Trap Seek
Bracelet`, `Flash Bomb Staff`, and `Friendship Staff`.

### Effect of removing DS2

Twenty of the 23 names formerly selected from DS2 are also present in Shiren 4 with the
same English wording. Only these three results change:

| Current name | With DS2 second | With Shiren 4 second | Result |
|---|---|---|---|
| Bufu's Riceball | Bufu's Onigiri | Bufu's Riceball | No rename; no matching Shiren 4 or Shiren 6 item |
| Swift Foe Scroll | Swift Scroll | Swift Foe Scroll | No rename; Shiren 4 retains the current name |
| Monstercall Scroll | Monster Scroll | Mon House Scroll | Still renamed, but now to the Shiren 4 form |

### Interaction with the existing terminology audit

Eight of the 70 changes supersede a decision currently frozen in
`tests/fixtures/item_terminology.json`:

| ID | Earlier history | Proposed now |
|---:|---|---|
| 34 | Ration Shield -> Shield of Sating | Diet Shield |
| 43 | Evasive Shield -> Watchful Shield | Evasive Shield |
| 45 | Fragile Shield -> Break-Off Shield | Disposable Shield |
| 48 | Stormward -> Rasen Fuuma | Helix Shield |
| 63 | Passage Bracelet -> Waterwalk Bracelet | Strider Bracelet |
| 81 | Explosive Bracelet -> Blasting Bracelet | Explosion Bracelet |
| 82 | Miss Bracelet -> Bad-aim Bracelet | Dragon Tile Bracelet |
| 163 | Skull Staff -> Skull Mage's Staff | Mage Staff |

The other 62 proposed changes are new relative to that approved-corrections list. The 42
earlier corrections not listed above remain in force, so the eventual fixture migration
must not discard them.

## Exact proposed changes

### Weapons

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 4 | `どうたぬき` | Doutanuki | Dotanuki | Shiren 2 |
| 5 | `ドラゴンキラー` | Dragonkiller | Dragon Killer | Shiren 2 |
| 6 | `剛剣マンジカブラ` | Manji Kabura | Kabura's Blade | Shiren 2 |
| 7 | `じょうぶつのカマ` | Sickle of Salvation | Ghost Sickle | Shiren 2 |
| 10 | `必中の剣` | Accurate Sword | Homing Blade | Shiren 2 |
| 11 | `ミノタウロスの斧` | Axe of the Minotaur | Minotaur's Axe | Shiren 2 |
| 12 | `妖刀かまいたち` | Kama Itachi | Razor Wind | Shiren 2 |
| 13 | `1ツ目ゴロシ` | Cyclops Bane | Cyclops Killer | Shiren 2 |
| 14 | `ドレインバスター` | Drain Slayer | Drain Buster | Shiren 2 |
| 15 | `火迅風魔刀` | Kajin Fuuma | Fiery Fuuma | Shiren 2 |
| 16 | `秘剣カブラステギ` | Kabura Sutegi | Kaburasutegi | Shiren 2 |
| 20 | `つかいすての剣` | Break-Off Blade | Disposable Sword | Shiren 2 |
| 21 | `木づち` | Wooden Mallet | Mallet | Shiren 2 |
| 22 | `スパークソード` | Jagged Sword | Spark Sword | Shiren 2 |
| 31 | `三日月刀` | Crescent Blade | Crescent Arm | Shiren 2 |

### Shields

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 34 | `ハラモチの盾` | Shield of Sating | Diet Shield | Shiren 4 |
| 43 | `見切りの盾` | Watchful Shield | Evasive Shield | Shiren 2 |
| 45 | `つかいすての盾` | Break-Off Shield | Disposable Shield | Shiren 2 |
| 48 | `ラセン風魔の盾` | Rasen Fuuma | Helix Shield | Shiren 2 |

### Bracelets

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 63 | `つうかの腕輪` | Waterwalk Bracelet | Strider Bracelet | Shiren 4 |
| 64 | `ワナしの腕輪` | Trapper's Bracelet | Trapper Bracelet | Shiren 2 |
| 65 | `回復の腕輪` | Healing Bracelet | Heal Bracelet | Shiren 2 |
| 66 | `つうこんの腕輪` | Dreaded Bracelet | Regret Bracelet | Shiren 4 |
| 67 | `のろいよけの腕輪` | Cursebreak Bracelet | Holy Bracelet | Shiren 4 |
| 68 | `えんとうの腕輪` | Far-throwing Bracelet | Pierce Bracelet | Shiren 2 |
| 69 | `たれながしの腕輪` | Item-losing Bracelet | Breadcrumb Bracelet | Shiren 2 |
| 70 | `とうしの腕輪` | Clairvoyant Bracelet | Scout Bracelet | Shiren 2 |
| 71 | `こんらんよけの腕輪` | Focusing Bracelet | Calm Bracelet | Shiren 4 |
| 73 | `たかとびの腕輪` | Leaping Bracelet | Warp Bracelet | Shiren 4 |
| 81 | `バクハツの腕輪` | Blasting Bracelet | Explosion Bracelet | Shiren 4 |
| 82 | `あたらずの腕輪` | Bad-aim Bracelet | Dragon Tile Bracelet | Shiren 2 |

### Projectiles and food

| ID | Category | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|---|
| 93 | Projectile | `ふきとばしの矢` | Knockback Arrow | Force Arrow | Shiren 4 |
| 99 | Food | `まずそうなおにぎり` | Rotten Onigiri | Spoiled Onigiri | Shiren 2 |

### Grass

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 105 | `おとぎり草` | Otogirisou | Otogiriso | Shiren 2 |
| 106 | `めぐすり草` | Seewell Grass | Sight Grass | Shiren 2 |
| 110 | `いかくちょうのたね` | Bellyexpand Seed | Expand Seed | Shiren 2 |
| 111 | `いしゅくしょうのたね` | Bellyshrink Seed | Shrink Seed | Shiren 2 |
| 112 | `しあわせ草` | Fortune Grass | Happy Grass | Shiren 2 |
| 118 | `こんらん草` | Confusion Grass | Dizzy Grass | Shiren 4 |
| 119 | `すいみん草` | Sedating Grass | Sleep Grass | Shiren 4 |
| 121 | `たかとび草` | Leaping Grass | Warp Grass | Shiren 2 |

### Scrolls

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 124 | `しきべつの巻物` | Identifier Scroll | Identify Scroll | Shiren 2 |
| 125 | `あかりの巻物` | Mapping Scroll | Navigation Scroll | Shiren 4 |
| 126 | `壺ぞうだいの巻物` | Pot-upsize Scroll | Pot Expand Scroll | Shiren 2 |
| 127 | `しんくうぎりの巻物` | Windblade Scroll | Air Slash Scroll | Shiren 4 |
| 128 | `くちなしの巻物` | Muzzle Scroll | Muzzled Scroll | Shiren 4 |
| 133 | `大部屋の巻物` | Wall-less Scroll | Great Hall Scroll | Shiren 2 |
| 134 | `モンスターの巻物` | Monstercall Scroll | Mon House Scroll | Shiren 4 |
| 136 | `ねだやしの巻物` | Eradication Scroll | Extinction Scroll | Shiren 2 |
| 138 | `すいだしの巻物` | Extraction Scroll | Suction Scroll | Shiren 2 |
| 139 | `ひろえずの巻物` | Carry-ban Scroll | Grounded Scroll | Shiren 4 |
| 140 | `おはらいの巻物` | Exorcism Scroll | Purify Scroll | Shiren 2 |
| 141 | `天のめぐみの巻物` | Heavenly Scroll | Heaven Scroll | Shiren 2 |
| 142 | `地のめぐみの巻物` | Earthly Scroll | Earth Scroll | Shiren 2 |
| 149 | `ワナけしの巻物` | Trap-eraser Scroll | Trap Remove Scroll | Shiren 2 |

`Escape Scroll` remains unchanged. Shiren 2 has both `Escape Scroll` and `Retreat
Scroll`, but GB2's `もちかえり` behavior keeps all carried items and corresponds to the
former. This audit does not select the merely similar Shiren 2 retreat item, which keeps
only equipped items.

### Staves

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 159 | `しあわせの杖` | Fortune Staff | Happy Staff | Shiren 2 |
| 161 | `みがわりの杖` | Disguising Staff | Decoy Staff | Shiren 4 |
| 162 | `ばしょがえの杖` | Switching Staff | Swap Staff | Shiren 2 |
| 163 | `まどうの杖` | Skull Mage's Staff | Mage Staff | Shiren 4 |
| 164 | `かなしばりの杖` | Paralyzing Staff | Paralysis Staff | Shiren 4 |
| 165 | `いちじしのぎの杖` | Narrow-escape Staff | Transient Staff | Shiren 4 |
| 166 | `いたみわけの杖` | Empathetic Staff | Empathy Staff | Shiren 4 |
| 167 | `ふういんの杖` | Sealing Staff | Seal Staff | Shiren 2 |
| 172 | `トンネルの杖` | Burrowing Staff | Tunnel Staff | Shiren 2 |
| 180 | `とびつきの杖` | Vaulting Staff | Pinning Staff | Shiren 4 |

### Pots

| ID | Japanese | Current | Proposed | Winning source |
|---:|---|---|---|---|
| 184 | `ほぞんの壺` | Preservation Pot | Storage Pot | Shiren 2 |
| 185 | `きょうかの壺` | Upgrading Pot | Upgrade Pot | Shiren 2 |
| 186 | `しきべつの壺` | Identifier Pot | Identify Pot | Shiren 2 |
| 188 | `じゃっかの壺` | Degrading Pot | Degrade Pot | Shiren 2 |
| 189 | `へんげの壺` | Transmutation Pot | Presto Pot | Shiren 2 |

## Required synchronization

### Catalog and descriptions

All 70 group-4 names in `script/en/glossary.tsv` require the proposed value, and the
matching 70 group-6 headings in `script/en/items.tsv` must change with them. A fixed-string
scan found no use of these 70 full old names in the description bodies; their explanatory
prose remains semantically valid. The heading is the only description edit identified by
this audit.

The corresponding English mirrors in `script/organized/glossary.tsv` and
`script/organized/items.tsv` must be regenerated or synchronized by their owning workflow.

### Unidentified-item roots

Forty-nine renamed items belong to families with group-12 recall roots: bracelets, grass,
scrolls, staves, and pots. All 49 root records change. Each becomes the proposed name with
its category suffix removed, such as:

- `Waterwalk` -> `Strider`
- `Bad-aim` -> `Dragon Tile`
- `Fortune` -> `Happy` for both Grass and Staff
- `Identifier` -> `Identify` for both Scroll and Pot
- `Windblade` -> `Air Slash`
- `Monster` -> `Mon House`
- `Narrow-escape` -> `Transient`
- `Transmutation` -> `Presto`

The disabled `XBlank`, `XSumeragi`, and `XImprison` sentinels are unaffected.

These root changes also require a review of `docs/BLANK_SCROLL_INPUTS.md` and the
unidentified-item helper/fixture route; they are functional input mappings, not merely
documentation labels.

### Literal player-facing records

Beyond the catalog and description headings, 27 production records contain a literal old
name and must be updated. Records sharing a row all receive the same rename.

| Current -> proposed | Production records |
|---|---|
| Otogirisou -> Otogiriso | `script/en/messages.tsv` `193:$4C61` |
| Seewell Grass -> Sight Grass | `script/en/messages.tsv` `194:$6057` |
| Identifier Scroll -> Identify Scroll | `script/en/help.tsv` `193:$65DA` |
| Fortune Grass -> Happy Grass | `script/en/help.tsv` `200:$7179` |
| Paralyzing Staff -> Paralysis Staff | `script/en/help.tsv` `200:$73E2`; `script/en/monsters.tsv` `201:$7434` |
| Switching Staff -> Swap Staff | `script/en/help.tsv` `200:$7475`, `200:$74DC`, `200:$75A1`; `script/en/monsters.tsv` `201:$4D15` |
| Windblade Scroll -> Air Slash Scroll | `script/en/help.tsv` `200:$779E` |
| Rasen Fuuma -> Helix Shield | `script/en/ui_system.tsv` `193:$7348`; `script/en/prose.tsv` `198:$5257`, `198:$52C8` |
| Kabura Sutegi -> Kaburasutegi | `script/en/ui_system.tsv` `193:$7509`; `script/en/prose.tsv` `200:$48FD`, `200:$4951` |
| Kajin Fuuma -> Fiery Fuuma | `script/en/ui_system.tsv` `193:$751C`; `script/en/prose.tsv` `197:$7885` |
| Rotten Onigiri -> Spoiled Onigiri | `script/en/ui_system.tsv` `194:$4DEC` |
| Sealing Staff -> Seal Staff | `script/en/monsters.tsv` `200:$584A`, `201:$5124` |
| Confusion Grass -> Dizzy Grass | `script/en/monsters.tsv` `200:$5D2D`, `201:$5A37` |
| Sedating Grass -> Sleep Grass | `script/en/monsters.tsv` `200:$6742`, `201:$6D40` |
| Preservation Pot -> Storage Pot | `script/en/prose.tsv` `194:$5058` |

Where an editor or generator owns a record, update the owner and regenerate. In
particular, story prose must originate in `script/editing/prose.tsv`, monster ability text
must stay synchronized with `tools/translate_meat.py`, and the affected message drafts
must agree with the production TSVs. Do not patch only a generated output.

Two current lint exceptions become obsolete because the proposed order makes the paired
roots agree: `Presto Staff`/`Presto Pot` and `Heal Bracelet`/`Heal Pot`. The existing
`Swift Foe Scroll`/`Swift Staff` exception remains necessary under the Shiren 4 wording.

## Repository footprint

Before this audit document was added, exact old-name matching flagged 47 existing files
for review. Some are generated mirrors or historical documentation and should be handled
according to ownership rather than by blind replacement.

| Area | Files requiring review or regeneration |
|---|---|
| Production and policy | `script/en/glossary.tsv`, `script/en/items.tsv`, `script/en/help.tsv`, `script/en/messages.tsv`, `script/en/monsters.tsv`, `script/en/prose.tsv`, `script/en/ui_system.tsv`, `script/en/lint_exceptions.json` |
| Editors, drafts, and mirrors | `script/editing/prose.tsv`, `script/drafts/combat_messages.tsv`, `script/drafts/item_messages.tsv`, `script/drafts/prose.tsv`, `script/organized/glossary.tsv`, `script/organized/help.tsv`, `script/organized/items.tsv`, `script/organized/messages.tsv`, `script/organized/monsters.tsv`, `script/organized/prose.tsv`, `script/organized/ui_system.tsv` |
| Tools | `tools/mesen_item_formatting_gallery.lua`, `tools/mesen_prepare_endgame.lua`, `tools/mesen_spawn_synthesis_lab.lua`, `tools/mesen_spawn_unidentified_item.lua`, `tools/mesen_unlock_big_moai.lua`, `tools/translate_meat.py` |
| Tests and fixtures | `tests/fixtures/README.md`, `tests/fixtures/big_moai.json`, `tests/fixtures/item_formatting.json`, `tests/fixtures/item_terminology.json`, `tests/fixtures/synthesis_lab.json`, `tests/test_combat_messages.py`, `tests/test_item_formatting.py`, `tests/test_monster_house_labels.py` |
| Documentation | `docs/BIG_MOAI.md`, `docs/BIG_MOAI_CODES.md`, `docs/BLANK_SCROLL.md`, `docs/BLANK_SCROLL_INPUTS.md`, `docs/ITEM_FORMATTING.md`, `docs/ITEM_TERMINOLOGY.md`, `docs/MESEN_ENDGAME_HELPERS.md`, `docs/ROM_BANK_MAP.md`, `docs/TRAPS.md`, `docs/UNIDENTIFIED_ITEM_NAMING.md`, `docs/engineering-overview.md`, `docs/project-status.md`, `docs/testing-and-build.md`, `docs/translation-policy.md` |

`tests/fixtures/item_terminology.json` and `tests/test_item_terminology.py` need a policy
revision rather than simple string substitution: the current fixture freezes 50 earlier
corrections and the test hard-codes that count. The replacement contract should freeze the
70 source-order changes, retain the 42 still-current earlier corrections, preserve the
eight superseded name histories, and cover the 49 changed roots, 27 reviewed literal
surfaces, and three source revisions used here.

## Layout risk

The proposed strings were measured with the installed Thin Pixel-7 GB Compact advances.
Including the normal dynamic suffix/prefix for each item family, the widest changed shape
is `Dragon Tile Bracelet` at 98 px. `Disposable Shield+99` is 97 px and `Disposable
Sword+99` is 95 px. All are below the 144 px item-row text canvas.

The largest increase is `Bad-aim Bracelet` -> `Dragon Tile Bracelet`, from 80 px to 98 px.
The longest proposed unidentified roots are 11 cells, below the established 14-cell input
limit. No static width blocker was found, but the implementation should still rerun the
dynamic item gallery and rewrap/review all 27 literal surfaces because equipment/status
markers and dialogue geometry are separate runtime concerns.

## Recommended implementation order

1. Approve the literal old-source naming model, including opaque forms such as `Dragon
   Tile Bracelet`, or record explicit exceptions before editing production text.
2. Update `docs/translation-policy.md` and freeze the three source revisions.
3. Change all 70 group-4 names and matching group-6 headings.
4. Change the 49 group-12 roots and regenerate the Blank Scroll/unidentified-name maps.
5. Update the owning sources for the 27 literal records, regenerate their outputs, and
   remove the two obsolete lint exceptions while retaining the Swift exception.
6. Refresh fixtures, tools, and documentation listed above.
7. Run the catalog owner, scene owner, overlay synchronization, translation lint, item
   wrapper and dynamic-width checks, Mesen/PyBoy item routes, production build, and full
   test suite.
