# Monster special-move probabilities

English reference for **Shiren the Wanderer GB2: Magic Castle of the Desert on
Game Boy Color**, verified against the original ROM on **2026-09-09**. Names follow
this localization. These values do not describe the DS remake.

**The chance varies by monster family and tier.** There is no single special-move
percentage shared by every enemy. The monster must also have a suitable target and
satisfy its ability's conditions. A chance such as 25% applies to an eligible action
opportunity under normal conditions; it does not mean the monster uses its ability
on 25% of all turns, including turns spent walking toward you.

- [Examples and exact percentages](#examples-and-exact-percentages)
- [Exceptions to the normal roll](#exceptions-to-the-normal-roll)
- [All 209 Monster Notebook forms](#all-209-monster-notebook-forms)
- [How the ROM implements the check](#how-the-rom-implements-the-check)
- [Verification and reproduction](#verification-and-reproduction)

For the separate scroll question, the [blessed Windblade Scroll reference](testing-and-build.md#blessed-windblade-scroll-manual-route)
records blessing retention, blessing loss, and the Mesen testing helper.

## Examples and exact percentages

The normal check compares a random byte, from 0 through 255, with a threshold
stored in that monster tier's stats. For thresholds 0 through 254, the chance of
passing is **threshold / 256**. The value 255 is a special case that always passes.
These percentages count the successful possible RNG-byte values; they are not
estimates from watching a small number of turns.

| Monster | Threshold | Exact base chance | Approximate chance |
|---|---:|---:|---:|
| Gazer | 77 | 30.078125% | 30% |
| Super Gazer | 64 | 25% | 25% |
| Hyper Gazer | 51 | 19.921875% | 20% |
| Nigiri Morph | 64 | 25% | 25% |
| Nigiri Master | 77 | 30.078125% | 30% |
| Curse Girl | 51 | 19.921875% | 20% |
| Dragon | 102 | 39.84375% | 40% |
| Sky Dragon | 77 | 30.078125% | 30% |
| Archdragon | 51 | 19.921875% | 20% |
| Menbell | 56 | 21.875% | 22% |

The Japanese [Irupa monster reference](https://irupa.jyoukamachi.com/kyarakuta-/)
explicitly reports special-move rates in 5% increments. Its Gazer / Super Gazer /
Hyper Gazer values of 30% / 25% / 20% agree with the rounded native thresholds.
Its 20% entry for Menbell is coarser than the ROM's 21.875%; the exact value here
comes from the ROM, rather than treating the guide's rounded figure as exact.

The shared check makes a new random comparison when called. It has no counter
that forces an ability every fourth action at 25%, so repeated uses and long gaps
are possible. Individual abilities can have additional state or conditions.

## Exceptions to the normal roll

**A stored percentage alone is not a complete description of an ability.** Read
the **Rule** column in the full table together with these definitions:

| Rule | Meaning |
|---|---|
| ordinary | The usual action-selection path tests the stored threshold, then checks whether the ability can be used. Status effects and target conditions can alter that path. |
| bypass | This family is initialized with a flag that skips the shared probability check. Its own handler decides what happens, and may make a separate roll. The stored percentage is not necessarily its effective use rate. |
| no ordinary special | The family's ordinary special-action eligibility handler always rejects the action. Its stored byte does not describe passive traits, reactions, transformations, or other behavior implemented elsewhere. |

In particular:

- **Bow Boy / Crossbow Boy:** their handler makes its own roll using the stored
  30.078125% threshold. Passing allows the ranged targeting path. If that roll
  fails, the handler can still accept an adjacent target, so an eligible adjacent
  shot does not require a successful roll.
- **Pop Tank / Grampa Tank / Ornery Tank:** similarly, the stored 50% roll controls
  access to the ranged targeting path, with an adjacency fallback on failure.
- **Boy Tank / Mini Tank:** their stored byte represents 50%, but the shared roll
  is bypassed and their targeting handler does not make a replacement probability
  roll. Eligible shooting is checked automatically. This explains why a player
  reference can correctly describe them as 100% shooters despite the 50% stat byte.
- **Scurry Egg, Death Reaper, Teaser Monkey, and Master Chicken families** also
  bypass the shared roll. Their table values must not be read as unconditional
  per-action probabilities; their full individual behavior is outside this audit.
- **Demon Warrior and Explochin families** have no ordinary selected special
  action through this dispatcher. A 0% entry therefore does not establish that
  all their distinctive abilities are disabled or impossible.

A 100% ordinary entry means the probability gate always passes. It does not remove
range, target, terrain, status, or other eligibility requirements. The action
selector also has status-dependent paths that skip or prevent the normal check.
The table describes normal enemy action selection, not Nfuu's learned moves,
player-controlled meat transformations, allied AI, or boss-specific behavior.

## All 209 Monster Notebook forms

These are **stored base chances**, with the exceptions above marked explicitly.
Tier means the form's position within its monster family. Rows follow native
family order and include every form listed in the Monster Notebook.

**Address notation:** bank numbers, CPU addresses, and bytes prefixed with `$` are
hexadecimal throughout this document. For example, `0A:4B65` means bank `$0A`
(decimal 10), CPU address `$4B65`. The ROM address is the threshold byte, not the
start of the monster's stat record.

<!-- BEGIN GENERATED MONSTER RATES -->
| Monster | Tier | Stored base chance | Byte | ROM address | Rule |
|---|---:|---:|---|---|---|
| Mamel | 1 | 0% | `$00` | `0A:48BE` | no ordinary special |
| Pit Mamel | 2 | 0% | `$00` | `0A:48D0` | no ordinary special |
| Cave Mamel | 3 | 0% | `$00` | `0A:48E2` | no ordinary special |
| Bow Boy | 1 | 30.078125% | `$4D` | `0A:48F5` | bypass |
| Crossbow Boy | 2 | 30.078125% | `$4D` | `0A:4907` | bypass |
| Taur | 1 | 25% | `$40` | `0A:491A` | ordinary |
| Minotaur | 2 | 25% | `$40` | `0A:492C` | ordinary |
| Megataur | 3 | 30.078125% | `$4D` | `0A:493E` | ordinary |
| Healer Rabbit | 1 | 50% | `$80` | `0A:4951` | ordinary |
| Life Rabbit | 2 | 50% | `$80` | `0A:4963` | ordinary |
| Demon Warrior | 1 | 0% | `$00` | `0A:4976` | no ordinary special |
| Hannya Warrior | 2 | 0% | `$00` | `0A:4988` | no ordinary special |
| Shogun | 3 | 0% | `$00` | `0A:499A` | no ordinary special |
| Ghost Warrior | 1 | 100% | `$FF` | `0A:49AD` | ordinary |
| Ghost Hannya | 2 | 100% | `$FF` | `0A:49BF` | ordinary |
| Ghost Shogun | 3 | 100% | `$FF` | `0A:49D1` | ordinary |
| Scurry Egg | 1 | 0% | `$00` | `0A:49E4` | bypass |
| Scamper Egg | 2 | 0% | `$00` | `0A:49F6` | bypass |
| Leaping Egg | 3 | 100% | `$FF` | `0A:4A08` | bypass |
| Schubell | 1 | 19.921875% | `$33` | `0A:4A1B` | ordinary |
| Menbell | 2 | 21.875% | `$38` | `0A:4A2D` | ordinary |
| Bellthoven | 3 | 25% | `$40` | `0A:4A3F` | ordinary |
| Floor Dragon | 1 | 100% | `$FF` | `0A:4A52` | ordinary |
| Dragon Head | 2 | 100% | `$FF` | `0A:4A64` | ordinary |
| Tunnel Dragon | 3 | 100% | `$FF` | `0A:4A76` | ordinary |
| Pumphantasm | 1 | 0% | `$00` | `0A:4A89` | no ordinary special |
| Pumphantom | 2 | 0% | `$00` | `0A:4A9B` | no ordinary special |
| Pumpanshee | 3 | 0% | `$00` | `0A:4AAD` | no ordinary special |
| Pop Tank | 1 | 50% | `$80` | `0A:4AC0` | bypass |
| Grampa Tank | 2 | 50% | `$80` | `0A:4AD2` | bypass |
| Ornery Tank | 3 | 50% | `$80` | `0A:4AE4` | bypass |
| Nigiri Morph | 1 | 25% | `$40` | `0A:4AF7` | ordinary |
| Nigiri Boss | 2 | 25% | `$40` | `0A:4B09` | ordinary |
| Nigiri Master | 3 | 30.078125% | `$4D` | `0A:4B1B` | ordinary |
| Curse Girl | 1 | 19.921875% | `$33` | `0A:4B2E` | ordinary |
| Curse Sister | 2 | 19.921875% | `$33` | `0A:4B40` | ordinary |
| Curse Mom | 3 | 19.921875% | `$33` | `0A:4B52` | ordinary |
| Gazer | 1 | 30.078125% | `$4D` | `0A:4B65` | ordinary |
| Super Gazer | 2 | 25% | `$40` | `0A:4B77` | ordinary |
| Hyper Gazer | 3 | 19.921875% | `$33` | `0A:4B89` | ordinary |
| Impact Boar | 1 | 50% | `$80` | `0A:4B9C` | ordinary |
| Crash Boar | 2 | 44.921875% | `$73` | `0A:4BAE` | ordinary |
| Wrecker Boar | 3 | 44.921875% | `$73` | `0A:4BC0` | ordinary |
| Boy Tank | 1 | 50% | `$80` | `0A:4BD3` | bypass |
| Mini Tank | 2 | 50% | `$80` | `0A:4BE5` | bypass |
| Slime | 1 | 50% | `$80` | `0A:4BF8` | ordinary |
| Grime | 2 | 30.078125% | `$4D` | `0A:4C0A` | ordinary |
| Ooze | 3 | 30.078125% | `$4D` | `0A:4C1C` | ordinary |
| Porky | 1 | 34.765625% | `$59` | `0A:4C2F` | ordinary |
| Porko | 2 | 30.078125% | `$4D` | `0A:4C41` | ordinary |
| Porkon | 3 | 44.921875% | `$73` | `0A:4C53` | ordinary |
| Dragon | 1 | 39.84375% | `$66` | `0A:4C66` | ordinary |
| Sky Dragon | 2 | 30.078125% | `$4D` | `0A:4C78` | ordinary |
| Archdragon | 3 | 19.921875% | `$33` | `0A:4C8A` | ordinary |
| Cell Armor | 1 | 30.078125% | `$4D` | `0A:4C9D` | ordinary |
| Chrome Armor | 2 | 19.921875% | `$33` | `0A:4CAF` | ordinary |
| Titanium Armor | 3 | 19.921875% | `$33` | `0A:4CC1` | ordinary |
| Death Reaper | 1 | 0% | `$00` | `0A:4CD4` | bypass |
| Hell Reaper | 2 | 0% | `$00` | `0A:4CE6` | bypass |
| Grim Reaper | 3 | 0% | `$00` | `0A:4CF8` | bypass |
| Bad Froggo | 1 | 44.921875% | `$73` | `0A:4D0B` | ordinary |
| Bad Froggucci | 2 | 34.765625% | `$59` | `0A:4D1D` | ordinary |
| Bad Froggon | 3 | 34.765625% | `$59` | `0A:4D2F` | ordinary |
| Mutaikon | 1 | 30.078125% | `$4D` | `0A:4D42` | ordinary |
| Dazikon | 2 | 30.078125% | `$4D` | `0A:4D54` | ordinary |
| Dozikon | 3 | 30.078125% | `$4D` | `0A:4D66` | ordinary |
| Gawkulus | 1 | 30.078125% | `$4D` | `0A:4D79` | ordinary |
| Lockulus | 2 | 30.078125% | `$4D` | `0A:4D8B` | ordinary |
| Hawkulus | 3 | 25% | `$40` | `0A:4D9D` | ordinary |
| Doze Mage | 1 | 39.84375% | `$66` | `0A:4DB0` | ordinary |
| Sleep Warlock | 2 | 25% | `$40` | `0A:4DC2` | ordinary |
| Slumber Wizard | 3 | 23.828125% | `$3D` | `0A:4DD4` | ordinary |
| Bad Zalokleft | 1 | 39.84375% | `$66` | `0A:4DE7` | ordinary |
| Gang Zalokleft | 2 | 30.078125% | `$4D` | `0A:4DF9` | ordinary |
| Mob Zalokleft | 3 | 19.921875% | `$33` | `0A:4E0B` | ordinary |
| Sip Leech | 1 | 34.765625% | `$59` | `0A:4E1E` | ordinary |
| Slurp Leech | 2 | 25% | `$40` | `0A:4E30` | ordinary |
| Gulp Leech | 3 | 25% | `$40` | `0A:4E42` | ordinary |
| Wily Tanuki | 1 | 100% | `$FF` | `0A:4E55` | no ordinary special |
| Tricky Tanuki | 2 | 100% | `$FF` | `0A:4E67` | no ordinary special |
| Crafty Tanuki | 3 | 100% | `$FF` | `0A:4E79` | no ordinary special |
| Ether Devil | 1 | 0% | `$00` | `0A:4E8C` | no ordinary special |
| Phantom Devil | 2 | 0% | `$00` | `0A:4E9E` | no ordinary special |
| Mirage Devil | 3 | 0% | `$00` | `0A:4EB0` | no ordinary special |
| Soldier Ant | 1 | 100% | `$FF` | `0A:4EC3` | ordinary |
| Captain Ant | 2 | 100% | `$FF` | `0A:4ED5` | ordinary |
| General Ant | 3 | 100% | `$FF` | `0A:4EE7` | ordinary |
| Skull Mage | 1 | 30.078125% | `$4D` | `0A:4EFA` | ordinary |
| Skull Wizard | 2 | 25% | `$40` | `0A:4F0C` | ordinary |
| Skull Wraith | 3 | 25% | `$40` | `0A:4F1E` | ordinary |
| Rock Head | 1 | 100% | `$FF` | `0A:4F31` | ordinary |
| Ogre Rock | 2 | 100% | `$FF` | `0A:4F43` | ordinary |
| Demon Rock | 3 | 100% | `$FF` | `0A:4F55` | ordinary |
| Lamp Puffer | 1 | 25% | `$40` | `0A:4F68` | ordinary |
| Lantern Puffer | 2 | 25% | `$40` | `0A:4F7A` | ordinary |
| Beacon Puffer | 3 | 25% | `$40` | `0A:4F8C` | ordinary |
| Explochin | 1 | 0% | `$00` | `0A:4F9F` | no ordinary special |
| Concusschin | 2 | 0% | `$00` | `0A:4FB1` | no ordinary special |
| Fulminachin | 3 | 0% | `$00` | `0A:4FC3` | no ordinary special |
| Crow Tengu | 1 | 100% | `$FF` | `0A:4FD6` | ordinary |
| Falcon Tengu | 2 | 100% | `$FF` | `0A:4FE8` | ordinary |
| Eagle Tengu | 3 | 100% | `$FF` | `0A:4FFA` | ordinary |
| Wolf Droid | 1 | 19.921875% | `$33` | `0A:500D` | ordinary |
| Gorilla Bot | 2 | 25% | `$40` | `0A:501F` | ordinary |
| Bear Borg | 3 | 25% | `$40` | `0A:5031` | ordinary |
| Ironhead | 1 | 100% | `$FF` | `0A:5044` | ordinary |
| Chainhead | 2 | 100% | `$FF` | `0A:5056` | ordinary |
| Gigahead | 3 | 100% | `$FF` | `0A:5068` | ordinary |
| Bat Kangaroo | 1 | 25% | `$40` | `0A:507B` | ordinary |
| Evil Kangaroo | 2 | 25% | `$40` | `0A:508D` | ordinary |
| Devil Kangaroo | 3 | 25% | `$40` | `0A:509F` | ordinary |
| Mini Mixer | 1 | 0% | `$00` | `0A:50B2` | no ordinary special |
| Mini Mixermon | 2 | 0% | `$00` | `0A:50C4` | no ordinary special |
| Mini Mixergon | 3 | 0% | `$00` | `0A:50D6` | no ordinary special |
| Snacky | 1 | 0% | `$00` | `0A:50E9` | no ordinary special |
| Trap Genin | 1 | 100% | `$FF` | `0A:50FC` | no ordinary special |
| Trap Chunin | 2 | 100% | `$FF` | `0A:510E` | no ordinary special |
| Trap Jonin | 3 | 100% | `$FF` | `0A:5120` | no ordinary special |
| Bored Kappa | 1 | 100% | `$FF` | `0A:5133` | ordinary |
| Kappa Pest | 2 | 100% | `$FF` | `0A:5145` | ordinary |
| Vexing Kappa | 3 | 100% | `$FF` | `0A:5157` | ordinary |
| Sheep Priest | 1 | 34.765625% | `$59` | `0A:516A` | ordinary |
| Goat Pastor | 2 | 30.078125% | `$4D` | `0A:517C` | ordinary |
| Gazelle Pope | 3 | 30.078125% | `$4D` | `0A:518E` | ordinary |
| Punter Scarab | 1 | 69.921875% | `$B3` | `0A:51A1` | ordinary |
| Striker Scarab | 2 | 69.921875% | `$B3` | `0A:51B3` | ordinary |
| Kicker Scarab | 3 | 69.921875% | `$B3` | `0A:51C5` | ordinary |
| Gyadon | 1 | 25% | `$40` | `0A:51D8` | ordinary |
| Gyairas | 2 | 25% | `$40` | `0A:51EA` | ordinary |
| Gyandora | 3 | 19.921875% | `$33` | `0A:51FC` | ordinary |
| Samuraidon | 1 | 0% | `$00` | `0A:520F` | ordinary |
| Taishodon | 2 | 0% | `$00` | `0A:5221` | ordinary |
| Tonosamadon | 3 | 0% | `$00` | `0A:5233` | ordinary |
| Squid King | 1 | 25% | `$40` | `0A:5246` | ordinary |
| Squid Lord | 2 | 25% | `$40` | `0A:5258` | ordinary |
| Squid Emperor | 3 | 25% | `$40` | `0A:526A` | ordinary |
| Baby Mage | 1 | 39.84375% | `$66` | `0A:527D` | ordinary |
| Boy Mage | 2 | 39.84375% | `$66` | `0A:528F` | ordinary |
| Brat Mage | 3 | 30.078125% | `$4D` | `0A:52A1` | ordinary |
| Pitcher Plant | 1 | 0% | `$00` | `0A:52B4` | no ordinary special |
| Identify Plant | 2 | 0% | `$00` | `0A:52C6` | no ordinary special |
| Blessing Plant | 3 | 0% | `$00` | `0A:52D8` | no ordinary special |
| Alert Fly | 1 | 39.84375% | `$66` | `0A:52EB` | ordinary |
| Fink Fly | 2 | 39.84375% | `$66` | `0A:52FD` | ordinary |
| Nark Fly | 3 | 39.84375% | `$66` | `0A:530F` | ordinary |
| Lobber Beetle | 1 | 100% | `$FF` | `0A:5322` | ordinary |
| Heaver Beetle | 2 | 100% | `$FF` | `0A:5334` | ordinary |
| Slinger Beetle | 3 | 100% | `$FF` | `0A:5346` | ordinary |
| Goggler | 1 | 0% | `$00` | `0A:5359` | no ordinary special |
| Worth Goggler | 2 | 0% | `$00` | `0A:536B` | no ordinary special |
| Glenn Goggler | 3 | 0% | `$00` | `0A:537D` | no ordinary special |
| Dark Slasher | 1 | 0% | `$00` | `0A:5390` | no ordinary special |
| Sneaky Slasher | 2 | 0% | `$00` | `0A:53A2` | no ordinary special |
| Shadow Slasher | 3 | 0% | `$00` | `0A:53B4` | no ordinary special |
| Daze Hermit | 1 | 25% | `$40` | `0A:53C7` | ordinary |
| Scold Hermit | 2 | 25% | `$40` | `0A:53D9` | ordinary |
| Spry Hermit | 3 | 0% | `$00` | `0A:53EB` | ordinary |
| Dozy Genie | 1 | 30.078125% | `$4D` | `0A:53FE` | no ordinary special |
| Groggy Genie | 2 | 30.078125% | `$4D` | `0A:5410` | no ordinary special |
| Sleepy Genie | 3 | 30.078125% | `$4D` | `0A:5422` | no ordinary special |
| Pot Fisher | 1 | 50% | `$80` | `0A:5435` | ordinary |
| Pot Angler | 2 | 30.078125% | `$4D` | `0A:5447` | ordinary |
| Pot Giller | 3 | 30.078125% | `$4D` | `0A:5459` | ordinary |
| Jungarian | 1 | 50% | `$80` | `0A:546C` | ordinary |
| Campbellan | 2 | 50% | `$80` | `0A:547E` | ordinary |
| Blackbelly | 3 | 50% | `$80` | `0A:5490` | ordinary |
| Gyaza | 1 | 0% | `$00` | `0A:54A3` | no ordinary special |
| Killer Gyaza | 2 | 0% | `$00` | `0A:54B5` | no ordinary special |
| Hell Gyaza | 3 | 0% | `$00` | `0A:54C7` | no ordinary special |
| Dark Vassal | 1 | 0% | `$00` | `0A:54DA` | ordinary |
| Demon Vassal | 2 | 100% | `$FF` | `0A:54EC` | ordinary |
| Sable Vassal | 3 | 0% | `$00` | `0A:54FE` | ordinary |
| Morabi | 1 | 0% | `$00` | `0A:5511` | no ordinary special |
| Warabi | 2 | 0% | `$00` | `0A:5523` | no ordinary special |
| Takabi | 3 | 0% | `$00` | `0A:5535` | no ordinary special |
| Glare Snake | 1 | 0% | `$00` | `0A:5548` | no ordinary special |
| Leer Snake | 2 | 0% | `$00` | `0A:555A` | no ordinary special |
| Ogle Snake | 3 | 0% | `$00` | `0A:556C` | no ordinary special |
| Minion Mouse | 1 | 0% | `$00` | `0A:557F` | no ordinary special |
| Mobster Mouse | 2 | 0% | `$00` | `0A:5591` | no ordinary special |
| Skipper Mouse | 3 | 0% | `$00` | `0A:55A3` | no ordinary special |
| Teaser Monkey | 1 | 0% | `$00` | `0A:55B6` | bypass |
| Derider Monkey | 2 | 0% | `$00` | `0A:55C8` | bypass |
| Mocker Monkey | 3 | 0% | `$00` | `0A:55DA` | bypass |
| Chintala | 1 | 0% | `$00` | `0A:55ED` | no ordinary special |
| Mid Chintala | 2 | 0% | `$00` | `0A:55FF` | no ordinary special |
| Big Chintala | 3 | 0% | `$00` | `0A:5611` | no ordinary special |
| King Tusker | 1 | 21.875% | `$38` | `0A:5624` | ordinary |
| Monarch Tusker | 2 | 30.078125% | `$4D` | `0A:5636` | ordinary |
| Emperor Tusker | 3 | 17.96875% | `$2E` | `0A:5648` | ordinary |
| Twisty Hani | 1 | 34.765625% | `$59` | `0A:565B` | ordinary |
| Master Chicken | 1 | 0% | `$00` | `0A:566E` | bypass |
| Great Chicken | 2 | 0% | `$00` | `0A:5680` | bypass |
| Chicken | 1 | 0% | `$00` | `0A:5693` | no ordinary special |
| Vampire Baron | 1 | 50% | `$80` | `0A:56A6` | ordinary |
| Vampire Duke | 2 | 34.765625% | `$59` | `0A:56B8` | ordinary |
| Vampire Tyrant | 3 | 34.765625% | `$59` | `0A:56CA` | ordinary |
| Dagyan | 1 | 0% | `$00` | `0A:56DD` | no ordinary special |
| Dagyagan | 2 | 0% | `$00` | `0A:56EF` | no ordinary special |
| Dagyagyagan | 3 | 0% | `$00` | `0A:5701` | no ordinary special |
| Zen Guru | 1 | 0% | `$00` | `0A:5714` | no ordinary special |
| Zen Monk | 2 | 0% | `$00` | `0A:5726` | no ordinary special |
| Zen Priest | 3 | 0% | `$00` | `0A:5738` | no ordinary special |
| Shady Wisp | 1 | 0% | `$00` | `0A:574B` | no ordinary special |
| Fearful Wisp | 2 | 0% | `$00` | `0A:575D` | no ordinary special |
| Wailing Wisp | 3 | 0% | `$00` | `0A:576F` | no ordinary special |
| Fog Hermit | 1 | 30.078125% | `$4D` | `0A:5782` | ordinary |
| Haze Hermit | 2 | 30.078125% | `$4D` | `0A:5794` | ordinary |
| Mist Hermit | 3 | 30.078125% | `$4D` | `0A:57A6` | ordinary |
<!-- END GENERATED MONSTER RATES -->

## How the ROM implements the check

The following trace uses the existing original-ROM disassembly in
`build/mgbdis/`. Its filenames also use hexadecimal bank numbers, such as
`bank_00a.asm`. Stat and pointer tables are data: mgbdis may display their bytes
as meaningless instructions unless they are annotated as data.

| Native location | Role |
|---|---|
| `0A:4778` | Family-indexed table of two-byte stat pointers. Each pointed-to block starts with a tier count, followed by 18-byte tier records. |
| `0A:41CF–41E8` | Looks up the family, skips the count, adds `(tier - 1) × 18`, and copies the tier record to `$D312`. |
| `0A:42D2–42D6` | Copies the threshold at record offset `+6`, now `$D318`, into the active actor cache at `$FFA8`. |
| `07:4213–4239` | Sets the probability-bypass flag for family IDs `$02`, `$07`, `$0B`, `$10`, `$15`, `$3F`, and `$43`. |
| `01:4312–43C2` | Applies actor/target/status gates, normally loads `$FFA8` into `E`, and calls `00:1939`. A zero threshold skips the ordinary special attempt. |
| `00:1939–1943` | Returns carry set when the probability check passes. `$FF` takes the always-pass shortcut. |
| `08:42F6–4302` | Calls the family's eligibility handler through the pointer table at `08:4000`. A successful result permits special-action selection. |
| `01:443A–449D` | Dispatches the selected action; the special path calls `08:435A`, which selects an effect through `08:40CE`. |

The probability helper is small enough to show completely. The local label and
comments below are explanatory; the instructions are the original sequence:

```asm
; 00:1939; E = threshold
    inc e
    jr z, .always       ; $FF wrapped to zero
    dec e
    call $1806          ; random byte in A
    cp e                ; carry iff A < E
    ret
.always:
    scf
    ret
```

For example, Gazer's byte is `$4D` at `0A:4B65`. Successful values of `A` are
0 through 76: **77 out of 256**. Super Gazer uses `$40` at `0A:4B77`; Hyper Gazer
uses `$33` at `0A:4B89`.

The shared selector can roll before checking the move's geometry. Therefore a
successful roll can still lead to a normal attack or another fallback action if
the eligibility handler rejects it. The RNG byte generator is at `00:1806–182F`;
the audit controls its returned byte when testing the comparison, rather than
claiming to measure its statistical distribution during a playthrough.

The projectile exceptions are visible in `08:4441–44CB`: Bow Boy's additional
roll is at `08:4448–444F`, Pop Tank's at `08:447C–4483`, and Boy Tank's handler
begins at `08:44A1`. The always-reject eligibility stub is `08:44CC` (`or a; ret`).

## Verification and reproduction

[`tools/audit_monster_special_rates.py`](../tools/audit_monster_special_rates.py)
extracts the table directly from the original ROM. It uses the native 209-entry
Notebook catalog at `0B:7CBD` to choose forms and joins native name IDs to
[`script/en/glossary.tsv`](../script/en/glossary.tsv) for English names.

Verified source ROM SHA-1:

```text
5264f6d0c4f12c9144de1d12fddadbadd82b3e33
```

The 2026-09-09 verification established:

- All **209 forms** have valid native family/tier records and English names.
- **12 disassembly spans** covering the relevant tables, stat lookup, probability
  helper, selection code, and the traced exceptions reconstruct to the exact
  original ROM bytes. This checks that the cited mgbdis output matches the ROM.
- The original probability helper passed **all 65,536 combinations** of the
  256 thresholds and 256 controlled random-byte values in PyBoy, including the
  zero case, strict `<` comparison, and `$FF` shortcut.
- All 12 audited spans are **byte-for-byte unchanged** in both existing English
  builds, `shiren-gb2-english-classic-font.gbc` and
  `shiren-gb2-english-shadowed-font.gbc`. Their complete SHA-256 hashes are recorded
  by the audit in `audit.json`.

This verifies the stored values and shared probability mechanism, plus the
specific branches described above. It does not simulate every monster in every
map/status situation, or audit every special effect and passive ability.

Run from the repository root with the original ROM and its existing mgbdis output
available. The emulator check additionally requires PyBoy:

```bash
python3 tools/audit_monster_special_rates.py \
  --emulator --check-doc \
  --compare build/shiren-gb2-english-classic-font.gbc \
  --compare build/shiren-gb2-english-shadowed-font.gbc
```

Outputs go to `build/monster-special-rates/`:

| File | Contents |
|---|---|
| `audit.json` | Entries, eligibility/effect handler addresses, verified span hashes, compared build hashes, and native test results. |
| `rates.tsv` | The complete English table in spreadsheet-friendly form. |
| `rates.md` | The generated Markdown table used above. |

`--check-doc` requires the tracked table to match the fresh ROM extraction. To
refresh it after English name changes, replace only the section between the
`BEGIN GENERATED MONSTER RATES` and `END GENERATED MONSTER RATES` markers with
`rates.md`, then rerun with `--check-doc`. The tool never patches a ROM; its PyBoy
check uses a temporary copy and does not save gameplay progress.
