# Sword and shield seals

English reference for **Shiren GB2: Magic Castle of the Desert on Game Boy Color**,
using this patch's item and dungeon names. There are **21 obtainable sword abilities
and 19 obtainable shield abilities**. Five additional description entries have no
donor or rescue source in the audited tables; they are listed separately below.

A seal is an equipment ability that synthesis can transfer. GB2's Item Info lists
abilities in words. The `W00`/`S00` identifiers below are reference numbers for this
document and the audit script, not names or symbols displayed by the game.

## How to put a seal on your equipment

1. Get a weapon or shield carrying the ability you want.
2. Put the equipment you want to **keep first** into a **Synthesis Pot**.
3. Put the donor in afterward: **weapon into weapon, shield into shield**.
4. Throw the Pot against a wall, recover the resulting equipment, and check **Info**.

The donor is consumed. You can also throw the base and then the donor to a
**Mini Mixer-family monster**, then defeat it to recover the result. It becomes
stronger after swallowing equipment. These are the methods described by
[Chunsoft's GB2 synthesis guide](https://www.spike-chunsoft.co.jp/pages/games/shirengb2/system03.html).

Equipment has limited **extra ability slots**. The base item's inherent ability does
not consume one: a Dragonkiller has its Dragon ability plus room for six added
abilities. That Dragon ability does use a slot when transferred onto a different
base that does not inherently have it. A duplicate ability does not stack.

Check the base's remaining space before feeding it a donor with several abilities.
If the new abilities will not all fit, the game randomly discards some of the donor's
new abilities until they fit; the base's existing abilities remain. A high attack or
defense value does not itself create a transferable ability.

GB2 does **not** support cross-category synthesis recipes: adding herbs, Scrolls,
Onigiri, or a shield to a sword will not create extra sword seals. Bracelets can be
synthesized with other Bracelets, but their abilities cannot be moved onto a sword
or shield. The game explains this in the Synthesis Pot description and the
Blacksmith's Synthesis dialogue (`202:$72D5`, `199:$54E7`).

The **Blacksmith's Remove service costs 1,000 Gitan** and removes an added ability
from synthesized equipment.
He explains synthesis but does not perform it for you (`199:$5701`, `199:$54E7`).

## Reading the acquisition columns

- **AD floor / AD shop:** find or buy the named donor in **Abyssal Depths**. These
  identify a source, not a guaranteed item or an assertion that every floor has it.
- **Forge shop:** buy the donor in **Smith's Forge**, in the stated floor range.
- **Rescue:** obtain a reward weapon/shield already carrying the ability, then use
  that equipment as the donor. The reward need not have the source item's name.
- **AD 5–89**, for example, means the **Abyssal Depths rescue reward tables for
  5–89F** can add that seal. It does not mean ordinary floor loot has that seal.

The donor-item locations are practical examples from the
[GB2 item-generation reference](https://w.atwiki.jp/sansara_naga2_sfc/pages/141.html).
They are not a complete list of every shop, monster drop, promotional gift, or
Training reward. Rescue ranges below are independently extracted from the original
ROM. See [how rescue rewards work](#getting-seals-through-rescue) for the limits.

## Sword seals

“Sword” includes axes, sickles, spears, and other items in the weapon category.
Effects here describe the ability, without claiming an exact activation probability.

| ID | Ability and effect | Inherent donor / example source | Rescue alternative |
|---|---|---|---|
| W00 | Dragon damage: stronger attacks against Dragon-type monsters. | **Dragonkiller** — AD shop. | AD 1–89 |
| W01 | Ghost damage: stronger attacks against Ghost-type monsters. | **Sickle of Salvation** — AD floor/shop. | AD 1–89 |
| W02 | Drain damage: stronger attacks against Drain-type monsters. | **Drain Slayer** — AD floor/shop. | AD 1–89 |
| W03 | Cyclops damage: stronger attacks against one-eyed monsters. | **Cyclops Bane** — AD floor/shop. | AD 1–89 |
| W04 | Exploding damage: stronger attacks against Exploding-type monsters. | **Crescent Blade** — AD shop. | AD 1–89 |
| W05 | Floating damage: stronger attacks against Floating-type monsters. | **Sky Splitter** — AD floor/shop. | AD 1–89 |
| W07 | Guaranteed hit: normal attacks always connect. | **Accurate Sword** exists in the item data, but use a rescue weapon carrying its ability; the named sword is not ordinarily obtainable in GB2. | AD 90–98; Tonfan's Hole or Wanado 85–98 |
| W08 | Three directions: attack the three spaces in front of Shiren. | **Kama Itachi** exists in the item data, but use a rescue weapon carrying its ability; the named sword is not ordinarily obtainable in GB2. | AD 30–98; Tonfan's Hole or Wanado 85–98 |
| W09 | Piercing reach: attack through two tiles straight ahead. | **Aura Spear**; the rescue alternative obtains the ability without finding the rare spear. | AD 5–89 |
| W10 | Critical hits: increases the frequency of critical attacks. | **Axe of the Minotaur** — Forge shop, 80–98F. | AD 30–89 |
| W11 | Attack healing: restore some HP by dealing attack damage. | **Healing Sword**; the rescue alternative obtains its ability directly. | AD 5–89 |
| W12 | Miss charge: missed attacks build toward a guaranteed critical attack. | **Jagged Sword** — AD shop. | AD 30–89 |
| W13 | Soul absorption: reduces a monster to 1 HP and adds drained HP to the weapon's Upgrade Value; misses weaken it and excessive strengthening breaks it. | **Soul Sickle** — Forge shop, 40–79F. | AD 30–59 |
| W14 | Recoil: hitting a monster or wall moves Shiren back one tile. | **Power Pole** — Forge shop, 40–79F. | AD 30–89 |
| W15 | Disarm: may knock an item away from the target. | **Cell Armor Sword**; use a deep rescue reward to obtain the ability. | AD 90–98; Tonfan's Hole or Wanado 85–98 |
| W16 | Sleep/confusion: an attack may inflict either status. | **Chaos Axe** — Forge shop, 40–79F. | AD 90–98; Tonfan's Hole or Wanado 85–98 |
| W17 | Meat: defeated monsters may become Meat; the weapon can break. | **Bufu's Cleaver** — Tonfan's Hole floor loot, 6–98F. | AD 30–59 |
| W18 | Digging, breakable: dig walls, with a risk of breaking the weapon. | **Pickaxe** — AD floor. | AD 30–59 |
| W19 | Digging, durable: dig walls without the digging-breakage drawback. | **Wonder Pick** — Forge shop, 30–59F. | AD 30–89 |
| W20 | Trap breaking: destroy traps, with a risk of breaking the weapon. | **Wooden Mallet** — AD floor/shop. | AD 30–59 |
| W21 | Deterioration: attacks lower the weapon's Upgrade Value. | **Break-Off Blade** — AD floor/shop. | AD 30–59 |

The effects and inherent donors come from the game's item descriptions and definition
table, matched to the English catalog. The distinction between the named Accurate
Sword/Kama Itachi and their obtainable rescue abilities is also documented in the
[GB2/DS2 comparison](https://w.atwiki.jp/shiren_ds2/pages/17.html).

Transferring a breakable tool's ability can make your main weapon break too. Wonder
Pick's digging ability avoids that particular drawback; it does not promise immunity
to other harmful abilities you also synthesize onto the weapon.

Soul Sickle absorbs **the monster's HP**. Its short English ability description,
“Costs HP to grow, may break,” should not be read as a cost to Shiren's HP: the
full item description explains the target-HP drain (`202:$4A87`).

Cell Armor Sword and Chaos Axe have another drawback: when their special effect
activates, it replaces the normal damaging attack. This behavior is reported in
the [player-tested equipment guide](https://irupa.jyoukamachi.com/saikyousoubi.html).

## Shield seals

| ID | Ability and effect | Inherent donor / example source | Rescue alternative |
|---|---|---|---|
| S00 | Slow hunger: halves ordinary Fullness depletion. | **Shield of Sating** — AD floor/shop. | AD 1–89 |
| S01 | Fast hunger: doubles ordinary Fullness depletion. | **Heavy Shield** — AD floor/shop. | AD 30–89 |
| S02 | No hunger: stops Fullness depletion, but equipping it reduces **Max Fullness to 0**. Removing the shield does not undo that loss. | **Nirvana Shield** — Forge shop, 70–98F. | AD 30–89 |
| S03 | Fire resistance: reduces Dragon-fire damage. | **Dragon Shield** — AD shop. | AD 5–89 |
| S04 | Explosion resistance: reduces explosion damage. | **Blast Shield** — AD floor/shop. | AD 1–89 |
| S08 | Counter: returns part of direct attack damage to the attacker. | **Counter Shield** — AD floor/shop. | AD 1–89 |
| S09 | Evasion: makes enemy attacks miss more often. | **Watchful Shield** — Forge shop, 1–39F. | AD 30–89 |
| S10 | Rust protection: prevents rusting. | **Wooden Shield** — AD floor/shop. | AD 30–89 |
| S11 | Theft protection: prevents theft of items and Gitan. | **Walrus Shield**; the rescue alternative obtains its ability directly. | AD 30–89 |
| S12 | Curse protection: protects against curses. | **Holy Shield** — AD floor/shop. | AD 30–89 |
| S13 | Trap protection: prevents triggering traps by stepping on them. | **Traproid Shield** — Wanado floor loot, 90–98F. | Wanado 85–98 |
| S14 | Projectile evasion: dodges incoming items; some projectiles are exceptions. | **Dodge Shield** — Forge shop, 70–98F. | AD 90–98 |
| S15 | Magic reflection: reflects applicable magic, including Staff magic. | **Echo Shield** — Forge shop, 1–39F. | AD 30–89 |
| S16 | Projectile reflection: reflects incoming items; some projectiles are exceptions. | **Reflect Shield** — Forge shop, 70–98F. | Tonfan's Hole 85–98 |
| S17 | Experience on damage: gain Experience when a monster deals direct damage. | **Happy Shield** — AD floor/shop. | AD 30–89 |
| S18 | Gitan on damage: gain Gitan when a monster deals direct damage. | **Froggo Shield**; the rescue alternative obtains its ability directly. | AD 30–89 |
| S19 | Prism: converts applicable monster special abilities into 10 damage. Some abilities bypass this protection. | **Prism Shield** — Forge shop, 80–98F. | AD 30–89 |
| S20 | Deterioration: taking attacks lowers the shield's Upgrade Value. | **Break-Off Shield** — AD floor/shop. | AD 30–59 |
| S21 | Attack boost: adds an attack benefit from your shield as well as its normal defense. | **Power Shield** — AD floor/shop. | AD 1–89 |

Fire resistance, magic reflection, projectile reflection, and Prism are different
abilities. None means blanket immunity to every special move. The individual effects
are described in the English item catalog (`202:$4C68` through `202:$541E`) and
ability catalog (`194:$73C2` through `194:$74E7`).
Prism's 10-damage conversion is also described in the
[player-tested equipment guide](https://irupa.jyoukamachi.com/saikyousoubi.html);
that number has not been independently traced in this audit.

## Getting seals through rescue

Complete a **Wanderer Rescue**, provide the Revival Password, and finish the exchange
with the rescued player's **Thank-You Password** to receive your reward. This is the
rescuer's generated reward equipment, separate from the optional item the rescuer sends
to the fallen player. See [the rescue system reference](RESCUE_SYSTEM.md).

The reward generator chooses an equipment category, creates a base item, and attempts
to add abilities or item statuses from a table determined by the dungeon and rescued
floor. Getting a listed seal is random. A slot-capacity check can reject an addition;
duplicate rolls also do not give duplicate copies of an ability.

**The main tables give one useful rescue alternative per seal**, with extra routes for
the rare abilities. Their range endpoints matter: going deeper can change the pool
and remove ordinary abilities from it. For example, AD 90–98F has a special reward
pool; it is not simply the AD 30–89F pool with more choices.

These are the principal rare-seal targets, confirmed from the native reward weights:

| Wanted ability | Rescue dungeon and floor |
|---|---|
| Guaranteed hit | Abyssal Depths 90–98F; Tonfan's Hole or Wanado 85–98F |
| Three directions | Abyssal Depths 30–98F; Tonfan's Hole or Wanado 85–98F |
| Projectile evasion | Abyssal Depths 90–98F |
| Projectile reflection | Tonfan's Hole 85–98F |
| Trap protection | Wanado 85–98F |

The [Japanese rescue-reward disassembly reference](https://w.atwiki.jp/sansara_naga2_sfc/pages/146.html)
was used to locate the native code, then the tables were read independently from this
project's original ROM. Its per-selection percentages should not be treated as the
chance of receiving that seal per completed rescue: category selection, number of
attempts, existing abilities, and capacity also matter.

## Plating, doubled slots, and other equipment properties

**Plating** is separate from the three-byte ability bitset. Use a **Plating Scroll**
on a weapon or shield to prevent rust. A plated sword does not need a transferable
sword rust seal: GB2 has no such sword ability entry. The shield ability from Wooden
Shield is a separate rust-protection source. Plating does not consume an ability slot.

**Doubled slots** is also a separate item flag. It doubles the base item's capacity:
for example, a five-slot Katana becomes a ten-slot Katana. It does not make each ability
twice as strong, and two copies of the flag cannot create four times the slots.
Reward tables can grant it in these ranges:

| Equipment | Rescue sources for doubled capacity |
|---|---|
| Sword or shield | Abyssal Depths 30–98F; Tonfan's Hole or Wanado 40–98F; Smith's Forge 30–98F; Pot Cave 30–99F |

The native flag is object byte 4, bit 7. Ordinary ability slots are stored in each
item definition; the capacity getter doubles that value when this flag is set.

Blessing, curse, enhancement values, and equipment **resonance** are also distinct
from seals. A strong base such as **Kabura Sutegi**, **Kajin Fuuma**, **Mamel Sword**,
or **Rasen Fuuma** does not supply a special seal merely because it is rare. The
inherent ability masks of those four items are zero. Their base stats and any paired
equipment effects are separate considerations.

## Additional entries with no identified acquisition route

These account for the rest of the ROM's sword/shield ability-description lists.
**No sword/shield definition grants them, and no rescue reward table selects them.**
They are not entries to hunt for in normal play. Their descriptions alone do not
establish a working combat effect.

| ID | English description in the patch | Acquisition status |
|---|---|---|
| W06 | Damages monsters | No donor or rescue source found. |
| S05 | Reduces damage received | No donor or rescue source found. |
| S06 | You take less damage | No donor or rescue source found. |
| S07 | You take less damage | No donor or rescue source found. |
| S22 | May break when hit | No donor or rescue source found. |

This distinction matters for cheat-generated equipment: setting every positive-looking
bit can enable entries that are absent from legitimate equipment generation.

## ROM verification and limits

The read-only audit is [audit_equipment_seals.py](../tools/audit_equipment_seals.py):

```sh
python3 tools/audit_equipment_seals.py --check-doc \
  --compare build/shiren-gb2-english-classic-font.gbc \
  --compare build/shiren-gb2-english-shadowed-font.gbc
```

It checks the original ROM SHA-1
`5264f6d0c4f12c9144de1d12fddadbadd82b3e33`, verifies **13 spans against mgbdis**, and
compares those same spans with both English builds. It reads **62 sword/shield item
definitions, 45 ability descriptions, and all 20 rescue tiers**. It also checks that
this document lists every ability exactly once, names the correct inherent donor,
and gives eligible rescue ranges.
Evidence, including every dungeon's rescue eligibility ranges, is written to
`build/equipment-seals/audit.json`.

All bank/address values below are **hexadecimal**:

| Native location | What it establishes |
|---|---|
| `11:4CA4` | Ability display offsets: weapon 0, shield 22, bracelet 45 within text group 15. |
| `77:552E` | Item-ID-to-definition pointer table. |
| `77:56BE–5A9D` | Definitions for IDs 1–62; bytes 8–10 are the inherent ability mask and byte 11 is capacity. This includes unused item definitions. |
| `77:6113`, `7A:47FF–4822` | Definition lookup and constructor copying inherent bits into item bytes 5–7. |
| `78:467B–469D` | Reads an existing object's actual ability bits. Synthesis donors need those bits, not merely the corresponding item ID. |
| `78:46D2–473F` | Looks up inherent abilities, then masks them out of the added-ability count. |
| `7A:4A04–4A96`, `7A:4AF7–4B30` | Synthesis merges new bits, counts available slots, and randomly discards excess incoming abilities. Existing base abilities are preserved. |
| `04:53B5–5566` | Rescue reward construction, capacity guard, category and ability selection. |
| `04:5567`, `04:55A1` | Dungeon/floor-to-tier mapping and tier-to-weight-table pointers. Reward indices 0–7 are statuses; indices 8 onward map to ability bit `index − 8`. |
| `7A:42C9`, `7A:4954–4990` | Doubled-capacity flag and capacity getter. |

This is **data and disassembly verification**, not a new playthrough of every seal.
Donor shop/floor locations come from the linked generation reference and have not all
been visited in an emulator for this document. Exact damage multipliers, activation
rates, conflicting-seal priority, and every special-attack exception are outside this
audit. The existing [Synthesis Pot fixture](ITEM_FORMATTING.md#synthesis-seal-manual-route)
separately exercises a real Club + Axe of the Minotaur synthesis and verifies the
released critical-hit ability.

Related references: [player damage](PLAYER_DAMAGE_FORMULA.md),
[HP regeneration](HP_REGENERATION.md), and [Big Moai codes](BIG_MOAI_CODES.md).
