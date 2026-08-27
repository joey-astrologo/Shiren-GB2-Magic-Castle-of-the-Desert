#!/usr/bin/env python3
"""Fill the mechanically structured Monster Meat catalog in English.

The three Meat tables mirror the three actor-name tiers by index.  Their
descriptions use a deliberately small stock of Japanese ability sentences, so
this tool joins the already-approved English monster names to reviewed English
ability clauses, wraps them with the installed VWF, and updates only blank
Monster Meat cells.  Empty native slots are recorded explicitly as ``<empty>``.
"""
import argparse
import csv
from pathlib import Path
import re

import english_font
import extract
import layout
import wrap_en


ROOT = Path(__file__).resolve().parents[1]
MONSTERS = ROOT / "script" / "en" / "monsters.tsv"
GLOSSARY = ROOT / "script" / "organized" / "glossary.tsv"


SENTENCES = {
    "水の上を いどうできるぞ。": "Can move over water.",
    "水の上も いどうできるぞ。": "Can also move over water.",
    "ぬすめるのは 1体につき1回だけだぞ。": "Can steal only once from each monster.",
    "ときどき 会心のいちげきが 出せるぞ。": "May land a critical hit.",
    "すばやく動けるぞ。": "Can move at double speed.",
    "よびだしたモンスターは しばらく 自分のみがわりになるぞ。": "The summoned monster acts as your decoy for a while.",
    "みがわりになるのは 一度に1体だけだぞ。": "Only one decoy can exist at a time.",
    "地面にもぐって 2マス先に いどうできるぞ。": "Can burrow underground and move two tiles ahead.",
    "カベを通りぬけられるぞ。": "Can pass through walls.",
    "たいほうが うてるぞ。": "Can fire a cannon.",
    "肉を食べると 持っているアイテムの のろいが とけるぞ。": "Eating Meat removes curses from carried items.",
    "壺の中のものはダメだぞ。": "Items inside Pots are unaffected.",
    "モンスターを うしろ向きにしか こうげきできないようにするぞ。": "Can make a monster attack only backward.",
    "あいてを つきとばすぞ。": "Can knock a target backward.",
    "あいてが持っているアイテムを はじきとばすぞ。": "Can knock away a target's held item.",
    "ただし はじくのは 1体につき1回までだぞ。": "Works only once on each monster.",
    "おカネをぬすんで ワープするぞ。": "Can steal Gitan and warp away.",
    "でも こうげきできないぞ。": "Cannot attack.",
    "モンスターをねむらせるぞ。": "Can put a monster to sleep.",
    "壺にへんしんして モンスターから かくれるぞ。": "Can become a Pot and hide from monsters.",
    "いろいろな こうかがある杖が つかえるぞ。": "Can use a Staff with various effects.",
    "一度つかうと もとのすがたに もどるぞ。": "Returns to normal after one use.",
    "この肉を食べると ジバクスイッチが入るぞ。": "Eating this Meat activates self-destruct.",
    "アイテムの上にのって食べると おなかの中で合成できるぞ。": "Eat an item underfoot to Synthesize it in your stomach.",
    "ちがう しゅるいは合成できないぞ。": "Categories cannot be mixed.",
    "もとのすがたにもどると アイテムが手に入るぞ。": "Return to normal to retrieve it.",
    "足元のアイテムを投げるぞ。": "Can throw the item underfoot.",
    "モンスターのこうげきりょくを はんぶんにするぞ。": "Can halve a monster's Attack.",
    "もとのすがたに もどると おなかの中のアイテムが 手に入るぞ。": "Return to normal to retrieve the item in your stomach.",
    "しかし いどうできないぞ。": "Cannot move.",
    "ねむっているモンスターをおこすぞ。": "Can wake sleeping monsters.",
    "かいだんに向かって とっしんすると かいだんを動かすことができるぞ。": "Charge at the Stairs to move them.",
    "ときどき ねむってしまうぞ。": "May fall asleep.",
    "モンスターをたおすと ときどき 壺が手に入るぞ。": "Defeated monsters may drop a Pot.",
    "あいてが持っているアイテムを ぬすんで じめんにおくぞ。": "Can steal a target's held item and place it on the ground.",
    "ただし ぬすめるのは 1体につき1回だけだぞ。": "Can steal only once from each monster.",
    "モンスターのとくしゅこうげきを ふつうのダメージに変えるぞ。": "Converts monster special attacks into normal damage.",
    "目の前にいるモンスターに へんしんすることができるぞ。": "Can transform into the monster ahead.",
    "あいてのhpのはんぶんの ダメージをあたえるぞ。": "Can deal damage equal to half the target's HP.",
    "すばやく動けて れんぞくこうげきができるぞ。": "Can move at double speed and attack twice.",
    "鉄の矢がうてるぞ。": "Can shoot Iron Arrows.",
    "モンスターのこうげきりょくと ぼうぎょりょくを下げるぞ。": "Can lower a monster's Attack and Defense.",
    "モンスターを こんらんさせるぞ。": "Can confuse a monster.",
    "すがたを消せるぞ。": "Can become invisible.",
    "カベがほれるぞ。": "Can dig through walls.",
    "モンスターに向かって とくぎをつかうと 自分のまんぷくどを かいふくできるぞ。": "Use the ability on a monster to restore Fullness.",
    "2マス先まで こうげきできるぞ。": "Can attack up to two tiles away.",
    "目つぶしこうげきができるぞ。": "Can blind a monster.",
    "杖のまほうや ようじゅつなどの こうげきを すいとって うちけすぞ。": "Absorbs and nullifies Staff magic and similar attacks.",
    "ちょくせつこうげきを はんしゃ できるぞ。": "Can reflect direct attacks.",
    "のりうつりはできないぞ。": "Cannot possess another monster.",
    "モンスターがいなければ まっすぐ 炎を はくぞ。": "If none are nearby, breathes fire straight ahead.",
    "あいてが持っているアイテムを ぬすんでワープできるぞ。": "Can steal a target's held item and warp away.",
    "ただし おなじフロアに店があった ときは うりものになってしまうぞ。": "If the floor has a shop, the item becomes merchandise.",
    "目の前にいるモンスターを ほかのモンスターやワナに 向かって投げるぞ。": "Can throw the monster ahead toward another monster or trap.",
    "木の矢がうてるぞ。": "Can shoot Wooden Arrows.",
    "自分のhpをかいふくするぞ。": "Can restore your HP.",
    "たおされても ぼうれいむしゃに へんしんできるぞ。": "Transforms into a Ghost Warrior when defeated.",
    "モンスターに のりうつれるぞ。": "Can possess a monster.",
    "レベル1のモンスターを1匹 よびだすぞ。": "Can summon one Level 1 monster.",
    "でも動きがおそくなるぞ。": "Moves at half speed.",
    "モンスターをたおすと ときどき おにぎりが出るぞ。": "Defeated monsters may drop an Onigiri.",
    "石が投げられるぞ。": "Can throw rocks.",
    "炎のこうげきができるぞ。": "Can breathe fire.",
    "れんぞくこうげきができるぞ。": "Can attack twice.",
    "どく草が投げられるぞ。": "Can throw Poison Grass.",
    "あいてが持っているアイテムを ぬすんで ワープできるぞ。": "Can steal a target's held item and warp away.",
    "ただし おなじフロアに店がある ときは うりものになってしまうぞ。": "If the floor has a shop, the item becomes merchandise.",
    "肉を食べると ちからが1ポイント かいふくするぞ。": "Eating Meat restores 1 Strength.",
    "杖のこうげきを すいとって うちけすぞ。": "Absorbs and nullifies Staff magic.",
    "しばらくすると 自分がバクハツするぞ！": "You explode after a while!",
    "バクダンを投げられるぞ。": "Can throw bombs.",
    "モンスターを おこらせるぞ。": "Can enrage a monster.",
    "2つ食べると おなかいっぱいだ。": "Your stomach holds two items.",
    "動きが おそくなるぞ。": "Moves at half speed.",
    "目の前にいるモンスターを ほかのモンスターに向かって 投げるぞ。": "Can throw the monster ahead at another monster.",
    "でも あまり遠くには 投げられないぞ。": "Cannot throw very far.",
    "こうげきの一部を はねかえすぞ。": "Can reflect part of an attack.",
    "ばしょがえの杖がつかえるぞ。": "Can use a Switching Staff.",
    "足元にあるアイテムを食べて 草に へんかさせるぞ。": "Can eat the item underfoot and turn it into Grass.",
    "あいての手もとを くるわせて からぶりをさせる じゅつを つかうぞ。": "Can make a monster's attacks miss.",
    "ふういんの杖がつかえるぞ。": "Can use a Sealing Staff.",
    "あいてのレベルを1つ下げるぞ。": "Can lower a monster's level by 1.",
    "すばやく動けるけど とってもよわいぞ。": "Moves at double speed, but is very weak.",
    "自分と まわりにいる生物のhpを かいふくするぞ。": "Restores HP to you and nearby creatures.",
    "たおされても ぼうれいはんにゃに へんしんできるぞ。": "Transforms into a Ghost Hannya when defeated.",
    "こうげきされると ワープするぞ。": "Warps when attacked.",
    "レベル2のモンスターを1匹 よびだすぞ。": "Can summon one Level 2 monster.",
    "モンスターをたおすと ときどき 大きなおにぎりが出るぞ。": "Defeated monsters may drop a Large Onigiri.",
    "銀の矢がうてるぞ。": "Can shoot Silver Arrows.",
    "すこし遠くまで石が投げられるぞ。": "Can throw rocks a little farther.",
    "おなじ部屋にいるモンスターに 炎のこうげきができるぞ。": "Can breathe fire at a monster in the same room.",
    "こんらん草が投げられるぞ。": "Can throw Confusion Grass.",
    "肉を食べると ちからが2ポイント かいふくするぞ。": "Eating Meat restores 2 Strength.",
    "杖のこうげきを はねかえすぞ。": "Can reflect Staff magic.",
    "しばらくすると 自分が大バクハツするぞ！": "You cause a huge explosion after a while!",
    "すこし遠くまで バクダンを投げられるぞ。": "Can throw bombs a little farther.",
    "モンスターを はや足にするぞ。": "Can give a monster double speed.",
    "3つ食べると おなかいっぱいだ。": "Your stomach holds three items.",
    "すこし遠くまで投げられるぞ。": "Can throw a little farther.",
    "まほうこうげきを はねかえすぞ。": "Can reflect magic attacks.",
    "ふきとばしの杖がつかえるぞ。": "Can use a Knockback Staff.",
    "足元にあるアイテムを食べて しきべつするぞ。": "Can eat and identify the item underfoot.",
    "モンスターにせっきょうをして ねむらせるぞ。": "Can lecture a monster to sleep.",
    "動きをおそくする杖がつかえるぞ。": "Can use a Sloth Staff.",
    "たおされても しょうぐんゾンビに へんしんできるぞ。": "Transforms into a Ghost Shogun when defeated.",
    "となりにいるなかまが たおされて しまった時に よみがえらせるぞ。": "Can revive an adjacent ally when they are defeated.",
    "すばやく動けて すきな時にワープできるぞ。": "Moves at double speed and can warp at will.",
    "レベル3のモンスターを1匹 よびだすぞ。": "Can summon one Level 3 monster.",
    "モンスターをたおすと ときどき きょだいなおにぎりが 出るぞ。": "Defeated monsters may drop a Huge Onigiri.",
    "モンスターのこうげきりょくと ぼうぎょりょくをゼロにするぞ。": "Can reduce a monster's Attack and Defense to zero.",
    "遠くまで石が投げられるぞ。": "Can throw rocks a long distance.",
    "いっていはんい内のモンスターに 向かって カベをもつきぬける 炎のこうげきができるぞ。": "Breathes fire through walls at monsters in range.",
    "この場合はカベを つきぬけないぞ。": "That fire cannot pierce walls.",
    "カベも通りぬけられるぞ。": "Can also pass through walls.",
    "そのうえ カベもすりぬけられるぞ！": "Can also pass through walls!",
    "すいみん草が投げられるぞ。": "Can throw Sedating Grass.",
    "部屋にいるモンスターを こんらんさせるぞ。": "Can confuse every monster in the room.",
    "肉を食べると ちからがすべて かいふくするぞ。": "Eating Meat fully restores Strength.",
    "すがたを消せて すばやく動けるぞ。": "Can become invisible and move at double speed.",
    "そのうえ 杖のこうげきを はねかえすぞ。": "Can also reflect Staff magic.",
    "すばやく動けて カベがほれるぞ。": "Moves at double speed and can dig through walls.",
    "モンスターに向かって とくぎをつかうと 自分のさいだいまんぷくどを 上げられるぞ。": "Use the ability on a monster to raise Max Fullness.",
    "しばらくすると 自分が 大バクハツするぞ！": "You cause a huge explosion after a while!",
    "遠くまでバクダンを投げられるぞ。": "Can throw bombs a long distance.",
    "3マス先まで こうげきできるぞ。": "Can attack up to three tiles away.",
    "モンスターを おこらせた上に はや足にするぞ。": "Can enrage a monster and give it double speed.",
    "4つ食べると おなかいっぱいだ。": "Your stomach holds four items.",
    "投げたアイテムは カベやモンスターをつきぬけるぞ。": "Thrown items pierce walls and monsters.",
    "遠くまで投げられるぞ。": "Can throw a long distance.",
    "投げられたものを はねかえすぞ。": "Can reflect thrown objects.",
    "部屋の中にいるモンスターに 目つぶしこうげきができるぞ。": "Can blind every monster in the room.",
    "かなしばりの杖がつかえるぞ。": "Can use a Paralyzing Staff.",
    "足元にあるアイテムを食べて しゅくふくするぞ。": "Can eat and bless the item underfoot.",
    "モンスターが投げてきたものを しょうめつさせるぞ。": "Can erase objects thrown by monsters.",
    "ちょくせつこうげきを よけるぞ。": "Can dodge direct attacks.",
    "からだのコントロールが きかなくなるぞ。": "You lose control of your body.",
    "クオーターの杖がつかえるぞ。": "Can use a Quarter Staff.",
}


def normalized_sentences(tail):
    text = re.sub(r"\s+", " ", tail.replace("<br>", " ")).strip()
    return tuple(
        part.strip()
        for part in re.findall(r".*?(?:[。！]|\Z)", text)
        if part.strip()
    )


def actor_names():
    names = {}
    with GLOSSARY.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if not row["sections"].startswith("actor_names_tier_"):
                continue
            for reference in row["references"].split(";"):
                match = re.match(r"g00([1-3])\[(\d+)\]", reference)
                if match:
                    names[(int(match.group(1)), int(match.group(2)))] = row["english"]
    return names


def wrap_paragraph(font_rom, text, record_id):
    return "<br>".join(
        wrap_en._wrap_paragraph_balanced(
            font_rom, text, record_id, layout.english_runtime_width_contract()
        )
    )


def make_description(font_rom, record, name):
    source = record.source
    header = wrap_paragraph(font_rom, f"<26>{name} Meat<26>", record.id)
    transform = wrap_paragraph(
        font_rom, f"Eat it to transform into {name}.", record.id
    )
    pieces = [header, transform]
    marker = "「とくぎ」<br>"
    if marker in source:
        tail = source.split(marker, 1)[1]
        translated = []
        for sentence in normalized_sentences(tail):
            if sentence not in SENTENCES:
                raise SystemExit(f"missing ability sentence for {record.id}: {sentence}")
            translated.append(SENTENCES[sentence])
        pieces.append("<26>Ability<26>")
        pieces.append(wrap_paragraph(font_rom, " ".join(translated), record.id))
    result = "<br>".join(pieces)
    if result.count("<br>") + 1 > 10:
        raise SystemExit(f"{record.id} needs more than 10 full-screen lines")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rom")
    args = parser.parse_args()
    rom = Path(args.rom).read_bytes()
    extracted = extract.extract(rom)
    records = {record.id: record for record in extracted["records"]}
    names = actor_names()
    font_rom = english_font.install(rom)

    with MONSTERS.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    changed = 0
    for row in rows:
        if row["english"] or row["sections"] not in {
            "monster_meat_descriptions",
            "monster_notebook_descriptions",
        }:
            continue
        record = records[row["id"]]
        if not record.source:
            row["english"] = "<empty>"
            changed += 1
            continue
        if row["sections"] != "monster_meat_descriptions":
            continue
        reference = next(
            ref for ref in record.references if ref.group in (113, 114, 115)
        )
        key = (reference.group - 112, reference.index)
        name = names.get(key)
        if not name:
            raise SystemExit(f"missing actor name for {record.id}: {key}")
        row["english"] = make_description(font_rom, record, name)
        changed += 1

    with MONSTERS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"translated {changed} blank monster records")


if __name__ == "__main__":
    main()
