# Detached Dialogue Page-Marker Audit

## Purpose

The native page marker is nine pixels wide. When translated text ends at
pixel 136-143, the marker wraps alone to the start of the following line.
This produces the solid-marker/partly flashing appearance reported in game.
This audit covers both line-one to line-two and line-two to line-three wraps.

All changes in this document were approved and applied on 2026-09-02. The
tables preserve the reviewed before/after record. A post-application scan finds
zero detached page markers.

## Summary

- 185 detached marker endpoints across 175 translated records.
- 104 wrap from line one; 81 wrap from line two.
- 180 approved changes move only the final word to the next line.
- 5 approved pacing-sensitive `<page><br>` changes shorten wording instead.
- Every proposal was remeasured: no detached marker, third-line marker
  overflow, fourth line, ordinary width overflow, or unresolved runtime
  substitution remains.

Sections: combat_and_dungeon_messages (3), floor_and_system_messages (2), item_and_action_messages (1), story_and_event_dialogue (179)

## Pacing-sensitive wording changes

These five waits are immediately followed by an existing line break. Adding
another line would alter dialogue timing, so concise wording is proposed.

| # | Record | Current | Proposed |
|---:|---|---|---|
| 1 | `195:$6290` | `Sachi: You passed out playing<br>five-in-a-row in the desert?` | `Sachi: You passed out playing<br>five-in-a-row in a desert?` |
| 2 | `195:$66BA` | `<delay:1E>Hooded Man: Heh heh.<br>The Lord will be most pleased.` | `<delay:1E>Hooded Man: Heh heh.<br>The Lord will be so pleased.` |
| 3 | `195:$6A49` | `Pekeji: ...But I took it anyway.` | `Pekeji: ...But I took it.` |
| 4 | `195:$6E7D` | `???: Shh... Someone is coming.` | `???: Shh... Someone's coming.` |
| 5 | `196:$6333` | `Oro: I ask this of you as well.` | `Oro: I ask this of you too.` |

## Final-word reflow changes

Each proposal below preserves the words, page wait, box reset, and ordering;
only the final space before the page wait becomes a line break.

| # | Record | Section | Chunk | Wrap | Width | Current | Proposed |
|---:|---|---|---:|---|---:|---|---|
| 1 | `193:$4F62` | combat_and_dungeon_messages | 1 | line 1 → 2 | 139 px | `<lookup:19:C5>: BWOFFO!` | `<lookup:19:C5>:<br>BWOFFO!` |
| 2 | `193:$4F70` | combat_and_dungeon_messages | 1 | line 1 → 2 | 139 px | `<lookup:19:C5>: BWOFFO!` | `<lookup:19:C5>:<br>BWOFFO!` |
| 3 | `193:$4FD5` | combat_and_dungeon_messages | 1 | line 2 → 3 | 139 px | `<lookup:19:C5>: BWOFFO!<br><lookup:1B:C5>... TOUGH!!` | `<lookup:19:C5>: BWOFFO!<br><lookup:1B:C5>...<br>TOUGH!!` |
| 4 | `194:$52A8` | floor_and_system_messages | 1 | line 1 → 2 | 136 px | `No! You are being blown away!` | `No! You are being blown<br>away!` |
| 5 | `194:$534E` | floor_and_system_messages | 1 | line 1 → 2 | 139 px | `No! You are about to collapse!` | `No! You are about to<br>collapse!` |
| 6 | `194:$5DE5` | item_and_action_messages | 1 | line 1 → 2 | 136 px | `<number:19:C5> <cF3>broke.` | `<number:19:C5><br><cF3>broke.` |
| 7 | `195:$5893` | story_and_event_dialogue | 2 | line 2 → 3 | 140 px | `Wanda: That's when monsters<br>began moving into the castle...` | `Wanda: That's when monsters<br>began moving into the<br>castle...` |
| 8 | `195:$5B4A` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Sachi: You two take your time.` | `Sachi: You two take your<br>time.` |
| 9 | `195:$5BA8` | story_and_event_dialogue | 1 | line 2 → 3 | 139 px | `Pekeji: You always leave me<br>behind and run off somewhere!` | `Pekeji: You always leave me<br>behind and run off<br>somewhere!` |
| 10 | `195:$5D43` | story_and_event_dialogue | 2 | line 1 → 2 | 142 px | `Pekeji: Well?<page> Tempting, right?` | `Pekeji: Well?<page> Tempting,<br>right?` |
| 11 | `195:$6370` | story_and_event_dialogue | 2 | line 2 → 3 | 137 px | `Koppa: She caught me off<br>guard, so I blurted out a lie.` | `Koppa: She caught me off<br>guard, so I blurted out a<br>lie.` |
| 12 | `195:$640C` | story_and_event_dialogue | 1 | line 1 → 2 | 138 px | `Koppa: <name>, wait a sec.` | `Koppa: <name>, wait a<br>sec.` |
| 13 | `195:$65BE` | story_and_event_dialogue | 1 | line 1 → 2 | 142 px | `Pekeji: W-Whoa! I-It's shaking!` | `Pekeji: W-Whoa! I-It's<br>shaking!` |
| 14 | `195:$67DF` | story_and_event_dialogue | 3 | line 1 → 2 | 143 px | `<delay:1E>Pekeji: ...<page> This is all his fault.` | `<delay:1E>Pekeji: ...<page> This is all his<br>fault.` |
| 15 | `195:$6854` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Could that have been Zagan...?` | `Could that have been<br>Zagan...?` |
| 16 | `195:$6996` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Pekeji: C-Could taking that<br>statue be what caused this...?` | `Pekeji: C-Could taking that<br>statue be what caused<br>this...?` |
| 17 | `195:$6CF2` | story_and_event_dialogue | 2 | line 2 → 3 | 138 px | `Koppa: It really was the Evil<br>God Statue that caused this...` | `Koppa: It really was the Evil<br>God Statue that caused<br>this...` |
| 18 | `195:$6FA8` | story_and_event_dialogue | 3 | line 2 → 3 | 139 px | `Zagan: By the way, how has<br>the Lord been feeling lately?` | `Zagan: By the way, how has<br>the Lord been feeling<br>lately?` |
| 19 | `195:$7297` | story_and_event_dialogue | 3 | line 1 → 2 | 136 px | `extremely dangerous...<page> Please.` | `extremely dangerous...<page><br>Please.` |
| 20 | `195:$76FD` | story_and_event_dialogue | 2 | line 1 → 2 | 136 px | `Koppa: Come on, move! Please!!` | `Koppa: Come on, move!<br>Please!!` |
| 21 | `196:$444D` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `<delay:1E>Shizu: There's nowhere to run.` | `<delay:1E>Shizu: There's nowhere to<br>run.` |
| 22 | `196:$44B8` | story_and_event_dialogue | 3 | line 1 → 2 | 141 px | `Shizu: I heard something once.` | `Shizu: I heard something<br>once.` |
| 23 | `196:$44B8` | story_and_event_dialogue | 10 | line 1 → 2 | 141 px | `<delay:1E>Nuwanko: What are you saying?` | `<delay:1E>Nuwanko: What are you<br>saying?` |
| 24 | `196:$45F2` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Amokachi: You say 'do<br>something,' but what exactly?` | `Amokachi: You say 'do<br>something,' but what<br>exactly?` |
| 25 | `196:$48E4` | story_and_event_dialogue | 6 | line 2 → 3 | 138 px | `Lord: Heh heh... I know you are<br>waiting for that moment too...` | `Lord: Heh heh... I know you are<br>waiting for that moment<br>too...` |
| 26 | `196:$4A40` | story_and_event_dialogue | 5 | line 1 → 2 | 137 px | `Pekeji: That's why I'm coming!` | `Pekeji: That's why I'm<br>coming!` |
| 27 | `196:$4B29` | story_and_event_dialogue | 2 | line 2 → 3 | 141 px | `Pekeji: I may not look it, but<br>I'm built tough! See you later!` | `Pekeji: I may not look it, but<br>I'm built tough! See you<br>later!` |
| 28 | `196:$4B29` | story_and_event_dialogue | 3 | line 2 → 3 | 142 px | `Pekeji: The monsters in this<br>castle will be a piece of cake.` | `Pekeji: The monsters in this<br>castle will be a piece of<br>cake.` |
| 29 | `196:$4C76` | story_and_event_dialogue | 1 | line 2 → 3 | 142 px | `Ateka: Once the ritual begins,<br>I think I will lose my memory.` | `Ateka: Once the ritual begins,<br>I think I will lose my<br>memory.` |
| 30 | `196:$4C76` | story_and_event_dialogue | 10 | line 2 → 3 | 136 px | `Oryu: When it matters most, he<br>has incredible determination.` | `Oryu: When it matters most, he<br>has incredible<br>determination.` |
| 31 | `196:$4DF6` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `Ateka: Ah... Someone is coming!` | `Ateka: Ah... Someone is<br>coming!` |
| 32 | `196:$51CC` | story_and_event_dialogue | 1 | line 1 → 2 | 142 px | `Lord: That Jewel you possess...` | `Lord: That Jewel you<br>possess...` |
| 33 | `196:$5988` | story_and_event_dialogue | 2 | line 2 → 3 | 136 px | `Ateka: That was turning the<br>surrounding land into desert.` | `Ateka: That was turning the<br>surrounding land into<br>desert.` |
| 34 | `196:$5A8F` | story_and_event_dialogue | 3 | line 2 → 3 | 136 px | `Oryu: Curas needed Princess<br>Ateka's power as a priestess.` | `Oryu: Curas needed Princess<br>Ateka's power as a<br>priestess.` |
| 35 | `196:$63E5` | story_and_event_dialogue | 4 | line 1 → 2 | 137 px | `Koppa: It was pathetic of me.` | `Koppa: It was pathetic of<br>me.` |
| 36 | `196:$63E5` | story_and_event_dialogue | 10 | line 2 → 3 | 137 px | `Koppa: Curas is the one<br>monster I will never forgive!` | `Koppa: Curas is the one<br>monster I will never<br>forgive!` |
| 37 | `196:$6D18` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Gaibara: Until I am satisfied!!` | `Gaibara: Until I am<br>satisfied!!` |
| 38 | `196:$7234` | story_and_event_dialogue | 1 | line 2 → 3 | 142 px | `Koppa: You saw the Magic<br>Castle too, right, <name>?` | `Koppa: You saw the Magic<br>Castle too, right,<br><name>?` |
| 39 | `196:$73AB` | story_and_event_dialogue | 2 | line 1 → 2 | 137 px | `Koppa: Tonfan put up flowers.` | `Koppa: Tonfan put up<br>flowers.` |
| 40 | `196:$74FA` | story_and_event_dialogue | 2 | line 1 → 2 | 142 px | `Mamo: Take it off! Take it off!` | `Mamo: Take it off! Take it<br>off!` |
| 41 | `196:$7CB1` | story_and_event_dialogue | 2 | line 2 → 3 | 136 px | `Nfuu: Will you take me on<br>your adventures, <name>?` | `Nfuu: Will you take me on<br>your adventures,<br><name>?` |
| 42 | `197:$4312` | story_and_event_dialogue | 4 | line 2 → 3 | 141 px | `Koppa: And the Evil God was<br>on the verge of resurrection...` | `Koppa: And the Evil God was<br>on the verge of<br>resurrection...` |
| 43 | `197:$4429` | story_and_event_dialogue | 2 | line 1 → 2 | 143 px | `Tao: Th-The ground is shaking!!` | `Tao: Th-The ground is<br>shaking!!` |
| 44 | `197:$468E` | story_and_event_dialogue | 1 | line 2 → 3 | 139 px | `Lord: Ateka...<br>I have caused you such worry.` | `Lord: Ateka...<br>I have caused you such<br>worry.` |
| 45 | `197:$489E` | story_and_event_dialogue | 3 | line 1 → 2 | 142 px | `Wanda: No one else could do it.` | `Wanda: No one else could do<br>it.` |
| 46 | `197:$4A25` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Koppa: It really is wonderful.` | `Koppa: It really is<br>wonderful.` |
| 47 | `197:$4F02` | story_and_event_dialogue | 3 | line 1 → 2 | 140 px | `Koppa: <name>! Keep going!!` | `Koppa: <name>! Keep<br>going!!` |
| 48 | `197:$5002` | story_and_event_dialogue | 3 | line 1 → 2 | 138 px | `Koppa: This is Ilpa, isn't it?!` | `Koppa: This is Ilpa, isn't<br>it?!` |
| 49 | `197:$5207` | story_and_event_dialogue | 1 | line 1 → 2 | 142 px | `Koppa: What will you do, Oryu?` | `Koppa: What will you do,<br>Oryu?` |
| 50 | `197:$5287` | story_and_event_dialogue | 1 | line 2 → 3 | 136 px | `Sachi: Besides, someone will<br>be happy if <name> stays.` | `Sachi: Besides, someone will<br>be happy if <name><br>stays.` |
| 51 | `197:$536C` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Oro: Yeah. Yesterday we found<br>two men buried in the desert.` | `Oro: Yeah. Yesterday we found<br>two men buried in the<br>desert.` |
| 52 | `197:$5391` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Oro: They were unconscious,<br>so we carried them upstairs...` | `Oro: They were unconscious,<br>so we carried them<br>upstairs...` |
| 53 | `197:$53E8` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `Rai: That came from upstairs!!` | `Rai: That came from<br>upstairs!!` |
| 54 | `197:$5480` | story_and_event_dialogue | 1 | line 1 → 2 | 138 px | `Rihipishi: What do you think?!` | `Rihipishi: What do you<br>think?!` |
| 55 | `197:$55F1` | story_and_event_dialogue | 1 | line 1 → 2 | 142 px | `Gaibara: Wh-What did you say?!` | `Gaibara: Wh-What did you<br>say?!` |
| 56 | `197:$56AE` | story_and_event_dialogue | 3 | line 2 → 3 | 137 px | `Koppa: Searching for clay<br>here doesn't make much sense.` | `Koppa: Searching for clay<br>here doesn't make much<br>sense.` |
| 57 | `197:$59AD` | story_and_event_dialogue | 1 | line 1 → 2 | 140 px | `Koppa: Huh? Where's your dad?` | `Koppa: Huh? Where's your<br>dad?` |
| 58 | `197:$5AC0` | story_and_event_dialogue | 3 | line 2 → 3 | 137 px | `Pekeji: Leave that to me! I'll<br>bring you armfuls of flowers.` | `Pekeji: Leave that to me! I'll<br>bring you armfuls of<br>flowers.` |
| 59 | `197:$5C10` | story_and_event_dialogue | 2 | line 1 → 2 | 141 px | `Sachi: I didn't serve any eggs.` | `Sachi: I didn't serve any<br>eggs.` |
| 60 | `197:$5D86` | story_and_event_dialogue | 3 | line 1 → 2 | 141 px | `Koppa: Wh-What is this thing?!` | `Koppa: Wh-What is this<br>thing?!` |
| 61 | `197:$60CA` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Koppa: Then how about "Nfuu"?` | `Koppa: Then how about<br>"Nfuu"?` |
| 62 | `197:$690C` | story_and_event_dialogue | 4 | line 2 → 3 | 139 px | `Flower: Pick me and take me<br>to someone who loves flowers.` | `Flower: Pick me and take me<br>to someone who loves<br>flowers.` |
| 63 | `197:$6C8F` | story_and_event_dialogue | 3 | line 1 → 2 | 143 px | `Koppa: What a time to be alive!` | `Koppa: What a time to be<br>alive!` |
| 64 | `197:$6D1C` | story_and_event_dialogue | 2 | line 2 → 3 | 139 px | `Nfuu: It's blooming<br>beautifully. What a relief, fu.` | `Nfuu: It's blooming<br>beautifully. What a relief,<br>fu.` |
| 65 | `197:$6E00` | story_and_event_dialogue | 1 | line 1 → 2 | 140 px | `Koppa: We'll go with you again.` | `Koppa: We'll go with you<br>again.` |
| 66 | `197:$708B` | story_and_event_dialogue | 4 | line 2 → 3 | 137 px | `Oro: Keep challenging and<br>give it everything you've got!` | `Oro: Keep challenging and<br>give it everything you've<br>got!` |
| 67 | `197:$7371` | story_and_event_dialogue | 1 | line 2 → 3 | 143 px | `Oro: In this dungeon, traps<br>catch monsters instead of you.` | `Oro: In this dungeon, traps<br>catch monsters instead of<br>you.` |
| 68 | `197:$75F2` | story_and_event_dialogue | 1 | line 1 → 2 | 137 px | `Koppa: Wh-What's the record?!` | `Koppa: Wh-What's the<br>record?!` |
| 69 | `197:$7683` | story_and_event_dialogue | 1 | line 1 → 2 | 137 px | `Koppa: Wh-What's the record?!` | `Koppa: Wh-What's the<br>record?!` |
| 70 | `197:$77F0` | story_and_event_dialogue | 2 | line 1 → 2 | 142 px | `Ateka: This is our gift to you.` | `Ateka: This is our gift to<br>you.` |
| 71 | `198:$408D` | story_and_event_dialogue | 3 | line 1 → 2 | 136 px | `Koppa: Did something happen?` | `Koppa: Did something<br>happen?` |
| 72 | `198:$4236` | story_and_event_dialogue | 1 | line 2 → 3 | 142 px | `Nuwanko: Hey, you! You're still<br>helping yourself to my house?!` | `Nuwanko: Hey, you! You're still<br>helping yourself to my<br>house?!` |
| 73 | `198:$43EB` | story_and_event_dialogue | 2 | line 1 → 2 | 140 px | `Gaibara: I let my guard down...` | `Gaibara: I let my guard<br>down...` |
| 74 | `198:$48B4` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Gaibara: Good! Now I shall<br>use this clay to make my Pot.` | `Gaibara: Good! Now I shall<br>use this clay to make my<br>Pot.` |
| 75 | `198:$48DB` | story_and_event_dialogue | 3 | line 1 → 2 | 138 px | `Gaibara: Back to my workshop!` | `Gaibara: Back to my<br>workshop!` |
| 76 | `198:$49F0` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `Koppa: I'll read it. Let's see...` | `Koppa: I'll read it. Let's<br>see...` |
| 77 | `198:$4CAB` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Oryu: So where is this forge?` | `Oryu: So where is this<br>forge?` |
| 78 | `198:$4F60` | story_and_event_dialogue | 2 | line 1 → 2 | 136 px | `Mamo: Let's de-part together!` | `Mamo: Let's de-part<br>together!` |
| 79 | `198:$500E` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Koppa: <name>! Isn't that<br>a treasure chest over there?` | `Koppa: <name>! Isn't that<br>a treasure chest over<br>there?` |
| 80 | `198:$5126` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Blacksmith: Though I don't<br>know how it ended up so deep.` | `Blacksmith: Though I don't<br>know how it ended up so<br>deep.` |
| 81 | `198:$518E` | story_and_event_dialogue | 1 | line 2 → 3 | 136 px | `Blacksmith: <name>, I'd<br>like you to have this shield...` | `Blacksmith: <name>, I'd<br>like you to have this<br>shield...` |
| 82 | `198:$527D` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Koppa: <name>! Isn't that<br>a treasure chest over there?` | `Koppa: <name>! Isn't that<br>a treasure chest over<br>there?` |
| 83 | `198:$5504` | story_and_event_dialogue | 1 | line 1 → 2 | 140 px | `Pekeji: I didn't hear anything.` | `Pekeji: I didn't hear<br>anything.` |
| 84 | `198:$5504` | story_and_event_dialogue | 2 | line 1 → 2 | 142 px | `Pekeji: Maybe you imagined it...` | `Pekeji: Maybe you imagined<br>it...` |
| 85 | `198:$59CD` | story_and_event_dialogue | 2 | line 1 → 2 | 142 px | `Oryu: What happened to Ateka?` | `Oryu: What happened to<br>Ateka?` |
| 86 | `198:$5B72` | story_and_event_dialogue | 1 | line 2 → 3 | 141 px | `Lord: Heh heh... In the<br>labyrinth beneath the desert...` | `Lord: Heh heh... In the<br>labyrinth beneath the<br>desert...` |
| 87 | `198:$5D9B` | story_and_event_dialogue | 1 | line 2 → 3 | 140 px | `Zagan: I-Impossible... A human<br>reached the Abyssal Depths...?` | `Zagan: I-Impossible... A human<br>reached the Abyssal<br>Depths...?` |
| 88 | `198:$5E94` | story_and_event_dialogue | 2 | line 1 → 2 | 137 px | `Koppa: We came to rescue you.` | `Koppa: We came to rescue<br>you.` |
| 89 | `198:$61BA` | story_and_event_dialogue | 1 | line 1 → 2 | 136 px | `Ateka: Oh! I just remembered!` | `Ateka: Oh! I just<br>remembered!` |
| 90 | `198:$61BA` | story_and_event_dialogue | 5 | line 1 → 2 | 137 px | `Ateka: and spoke these words.` | `Ateka: and spoke these<br>words.` |
| 91 | `198:$639F` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Wanda: Hey, old man! You here?` | `Wanda: Hey, old man! You<br>here?` |
| 92 | `198:$668B` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `???: Grrrr... Wh-Where am I...?` | `???: Grrrr... Wh-Where am<br>I...?` |
| 93 | `198:$699C` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Mamo: You don't remember me?!` | `Mamo: You don't remember<br>me?!` |
| 94 | `198:$6AEB` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `Mamo the Wardrobe joined you!<delay:96>` | `Mamo the Wardrobe joined<br>you!<delay:96>` |
| 95 | `198:$6D4E` | story_and_event_dialogue | 2 | line 2 → 3 | 140 px | `Ohagi: How could we forget<br>the most important question?!` | `Ohagi: How could we forget<br>the most important<br>question?!` |
| 96 | `198:$6F89` | story_and_event_dialogue | 4 | line 1 → 2 | 136 px | `Ohagi and Kinako: Come again!` | `Ohagi and Kinako: Come<br>again!` |
| 97 | `198:$6FF1` | story_and_event_dialogue | 8 | line 1 → 2 | 139 px | `Kinako: Prepare to be amazed!!` | `Kinako: Prepare to be<br>amazed!!` |
| 98 | `198:$72F8` | story_and_event_dialogue | 2 | line 2 → 3 | 138 px | `Ohagi: You won't find a doll<br>this glamorous anywhere else!` | `Ohagi: You won't find a doll<br>this glamorous anywhere<br>else!` |
| 99 | `198:$742B` | story_and_event_dialogue | 6 | line 1 → 2 | 140 px | `Kinako: Aren't we thoughtful?!` | `Kinako: Aren't we<br>thoughtful?!` |
| 100 | `198:$75E5` | story_and_event_dialogue | 3 | line 1 → 2 | 141 px | `Kinako: We made you a new one.` | `Kinako: We made you a new<br>one.` |
| 101 | `198:$79A0` | story_and_event_dialogue | 1 | line 1 → 2 | 136 px | `Ohagi and Kinako: Come again!` | `Ohagi and Kinako: Come<br>again!` |
| 102 | `198:$79B4` | story_and_event_dialogue | 4 | line 2 → 3 | 136 px | `Ohagi: Well, <name>, you're<br>a man. You have your reasons.` | `Ohagi: Well, <name>, you're<br>a man. You have your<br>reasons.` |
| 103 | `198:$7A7A` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Ohagi: Don't make it cry again!` | `Ohagi: Don't make it cry<br>again!` |
| 104 | `199:$419C` | story_and_event_dialogue | 1 | line 1 → 2 | 143 px | `Bank Teller: I love this town...` | `Bank Teller: I love this<br>town...` |
| 105 | `199:$4280` | story_and_event_dialogue | 4 | line 1 → 2 | 141 px | `Bank Teller: The vault is full!` | `Bank Teller: The vault is<br>full!` |
| 106 | `199:$4400` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `Bank Teller: This is the Bank.` | `Bank Teller: This is the<br>Bank.` |
| 107 | `199:$448E` | story_and_event_dialogue | 2 | line 1 → 2 | 143 px | `Big Moai: You finally found me!` | `Big Moai: You finally found<br>me!` |
| 108 | `199:$4569` | story_and_event_dialogue | 2 | line 1 → 2 | 141 px | `Big Moai: Until then, farewell.` | `Big Moai: Until then,<br>farewell.` |
| 109 | `199:$4BBC` | story_and_event_dialogue | 2 | line 2 → 3 | 138 px | `Blacksmith: Come back<br>anytime you change your mind.` | `Blacksmith: Come back<br>anytime you change your<br>mind.` |
| 110 | `199:$53BD` | story_and_event_dialogue | 9 | line 1 → 2 | 140 px | `Blacksmith: Please be careful.` | `Blacksmith: Please be<br>careful.` |
| 111 | `199:$54E7` | story_and_event_dialogue | 5 | line 2 → 3 | 137 px | `Blacksmith: Unfortunately, I<br>don't perform Synthesis here.` | `Blacksmith: Unfortunately, I<br>don't perform Synthesis<br>here.` |
| 112 | `199:$5C78` | story_and_event_dialogue | 9 | line 2 → 3 | 140 px | `Good: After they send the<br>SOS data, press the A Button.` | `Good: After they send the<br>SOS data, press the A<br>Button.` |
| 113 | `199:$605E` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Setsu: Just like the Captain...` | `Setsu: Just like the<br>Captain...` |
| 114 | `199:$6106` | story_and_event_dialogue | 4 | line 2 → 3 | 140 px | `Setsu: All of them are working<br>hard and taking on challenges.` | `Setsu: All of them are working<br>hard and taking on<br>challenges.` |
| 115 | `199:$62F0` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Setsu: Just like the Captain...` | `Setsu: Just like the<br>Captain...` |
| 116 | `199:$6636` | story_and_event_dialogue | 3 | line 1 → 2 | 139 px | `Good: I prepared a small gift!` | `Good: I prepared a small<br>gift!` |
| 117 | `199:$66FD` | story_and_event_dialogue | 3 | line 1 → 2 | 139 px | `Good: I prepared a small gift!` | `Good: I prepared a small<br>gift!` |
| 118 | `199:$6FCD` | story_and_event_dialogue | 3 | line 2 → 3 | 142 px | `Good: They may send you a<br>Thank-You Password in return!` | `Good: They may send you a<br>Thank-You Password in<br>return!` |
| 119 | `199:$756B` | story_and_event_dialogue | 2 | line 1 → 2 | 140 px | `Kame: But Kume is so diligent.` | `Kame: But Kume is so<br>diligent.` |
| 120 | `199:$76A8` | story_and_event_dialogue | 1 | line 2 → 3 | 140 px | `Kame: When it comes to the<br>warehouse, leave it to Auntie.` | `Kame: When it comes to the<br>warehouse, leave it to<br>Auntie.` |
| 121 | `199:$7817` | story_and_event_dialogue | 19 | line 2 → 3 | 142 px | `Kame: The world would never<br>allow such cheating, would it?` | `Kame: The world would never<br>allow such cheating, would<br>it?` |
| 122 | `199:$7817` | story_and_event_dialogue | 20 | line 2 → 3 | 138 px | `Kame: Auntie will not let<br>anyone take the easy way out.` | `Kame: Auntie will not let<br>anyone take the easy way<br>out.` |
| 123 | `200:$41AD` | story_and_event_dialogue | 1 | line 1 → 2 | 136 px | `Debug: Ilpa Town, upper area.` | `Debug: Ilpa Town, upper<br>area.` |
| 124 | `200:$41BF` | story_and_event_dialogue | 1 | line 1 → 2 | 136 px | `Debug: Ilpa Town, lower area.` | `Debug: Ilpa Town, lower<br>area.` |
| 125 | `200:$429A` | story_and_event_dialogue | 1 | line 1 → 2 | 139 px | `Debug: Parted from companion.` | `Debug: Parted from<br>companion.` |
| 126 | `200:$43CD` | story_and_event_dialogue | 4 | line 1 → 2 | 141 px | `Good: I felt it loud and clear!` | `Good: I felt it loud and<br>clear!` |
| 127 | `200:$445A` | story_and_event_dialogue | 4 | line 2 → 3 | 137 px | `Higechiyo: Ho ho ho.<br>You are only getting started.` | `Higechiyo: Ho ho ho.<br>You are only getting<br>started.` |
| 128 | `200:$49C7` | story_and_event_dialogue | 3 | line 2 → 3 | 138 px | `Higechiyo: Sometimes one<br>needs the courage to retreat.` | `Higechiyo: Sometimes one<br>needs the courage to<br>retreat.` |
| 129 | `200:$4C0C` | story_and_event_dialogue | 3 | line 1 → 2 | 139 px | `Koppa: Keep going, <name>!` | `Koppa: Keep going,<br><name>!` |
| 130 | `200:$4CA6` | story_and_event_dialogue | 4 | line 1 → 2 | 138 px | `<delay:1E>Dragon Guard: Hm. That's bad...` | `<delay:1E>Dragon Guard: Hm. That's<br>bad...` |
| 131 | `200:$4DE1` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Dragon Guard: Drive them<br>into the Sleep Trap corridor!` | `Dragon Guard: Drive them<br>into the Sleep Trap<br>corridor!` |
| 132 | `203:$42AA` | story_and_event_dialogue | 7 | line 2 → 3 | 137 px | `Obaba: I still sense something<br>from the fallen Magic Castle.` | `Obaba: I still sense something<br>from the fallen Magic<br>Castle.` |
| 133 | `203:$4683` | story_and_event_dialogue | 2 | line 2 → 3 | 140 px | `Obaba: No matter how I<br>consider it, this is very bad...` | `Obaba: No matter how I<br>consider it, this is very<br>bad...` |
| 134 | `203:$4722` | story_and_event_dialogue | 1 | line 2 → 3 | 137 px | `Obaba: Events are always<br>unfolding where none can see.` | `Obaba: Events are always<br>unfolding where none can<br>see.` |
| 135 | `203:$4A8C` | story_and_event_dialogue | 2 | line 2 → 3 | 137 px | `Bibingida: By the way,<br>someone gave me this Scroll...` | `Bibingida: By the way,<br>someone gave me this<br>Scroll...` |
| 136 | `203:$4ADC` | story_and_event_dialogue | 2 | line 2 → 3 | 137 px | `Bibingida: By the way,<br>someone gave me this Scroll...` | `Bibingida: By the way,<br>someone gave me this<br>Scroll...` |
| 137 | `203:$4C71` | story_and_event_dialogue | 2 | line 2 → 3 | 137 px | `Bubuyaro: But I know you can<br>rescue the Princess, big bro!!` | `Bubuyaro: But I know you can<br>rescue the Princess, big<br>bro!!` |
| 138 | `203:$506C` | story_and_event_dialogue | 1 | line 1 → 2 | 138 px | `Goto: We will do our best too!` | `Goto: We will do our best<br>too!` |
| 139 | `203:$507E` | story_and_event_dialogue | 1 | line 1 → 2 | 137 px | `Goto: We are counting on you!!` | `Goto: We are counting on<br>you!!` |
| 140 | `203:$5279` | story_and_event_dialogue | 2 | line 2 → 3 | 139 px | `Hachi the Wanderer: He said he<br>expects great things from me!` | `Hachi the Wanderer: He said he<br>expects great things from<br>me!` |
| 141 | `203:$5279` | story_and_event_dialogue | 3 | line 2 → 3 | 142 px | `Hachi the Wanderer: I was so<br>happy my legs started shaking!` | `Hachi the Wanderer: I was so<br>happy my legs started<br>shaking!` |
| 142 | `203:$54EA` | story_and_event_dialogue | 5 | line 1 → 2 | 139 px | `Higechiyo: You have fine eyes.` | `Higechiyo: You have fine<br>eyes.` |
| 143 | `203:$589F` | story_and_event_dialogue | 9 | line 1 → 2 | 140 px | `Higechiyo: Do you understand?` | `Higechiyo: Do you<br>understand?` |
| 144 | `203:$5A4B` | story_and_event_dialogue | 6 | line 2 → 3 | 139 px | `Higechiyo: In other words, the<br>dungeon layout is remembered.` | `Higechiyo: In other words, the<br>dungeon layout is<br>remembered.` |
| 145 | `203:$5CBF` | story_and_event_dialogue | 1 | line 1 → 2 | 143 px | `Ichipeba: Th-The Magic Castle!` | `Ichipeba: Th-The Magic<br>Castle!` |
| 146 | `203:$5CEF` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Ichipeba: These are the dunes.` | `Ichipeba: These are the<br>dunes.` |
| 147 | `203:$5F3A` | story_and_event_dialogue | 11 | line 2 → 3 | 138 px | `Komaru: Only the inside of<br>the dungeon will be identical.` | `Komaru: Only the inside of<br>the dungeon will be<br>identical.` |
| 148 | `203:$60C5` | story_and_event_dialogue | 12 | line 2 → 3 | 138 px | `Komaru: Only the inside of<br>the dungeon will be identical.` | `Komaru: Only the inside of<br>the dungeon will be<br>identical.` |
| 149 | `203:$6687` | story_and_event_dialogue | 2 | line 1 → 2 | 142 px | `Komaru: That dungeon is "<cF8>9<cF8>af".` | `Komaru: That dungeon is<br>"<cF8>9<cF8>af".` |
| 150 | `203:$68C9` | story_and_event_dialogue | 1 | line 1 → 2 | 136 px | `Now is not the time to fight!` | `Now is not the time to<br>fight!` |
| 151 | `203:$68C9` | story_and_event_dialogue | 2 | line 2 → 3 | 137 px | `Oryu is waiting on the hill<br>overlooking the Magic Castle!` | `Oryu is waiting on the hill<br>overlooking the Magic<br>Castle!` |
| 152 | `203:$6A85` | story_and_event_dialogue | 3 | line 2 → 3 | 141 px | `Sachi: He becomes a different<br>person when he is announcing...` | `Sachi: He becomes a different<br>person when he is<br>announcing...` |
| 153 | `203:$6AF8` | story_and_event_dialogue | 1 | line 2 → 3 | 139 px | `Sachi: I love having flowers<br>decorating the shop. La-la-la.` | `Sachi: I love having flowers<br>decorating the shop.<br>La-la-la.` |
| 154 | `203:$6B19` | story_and_event_dialogue | 2 | line 2 → 3 | 142 px | `Sachi: Has he ever considered<br>doing some work for a change?` | `Sachi: Has he ever considered<br>doing some work for a<br>change?` |
| 155 | `203:$6CB9` | story_and_event_dialogue | 1 | line 1 → 2 | 137 px | `Sanpeba: The Trap Paaaaarts!!` | `Sanpeba: The Trap<br>Paaaaarts!!` |
| 156 | `203:$6E49` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Sara: I must thank the<br>Princess next time I see her.` | `Sara: I must thank the<br>Princess next time I see<br>her.` |
| 157 | `203:$6E67` | story_and_event_dialogue | 1 | line 1 → 2 | 143 px | `Sara: What a cute little puppy.` | `Sara: What a cute little<br>puppy.` |
| 158 | `203:$729F` | story_and_event_dialogue | 2 | line 2 → 3 | 142 px | `Shiro the Wanderer: Pushing<br>yourself is exhausting, right?` | `Shiro the Wanderer: Pushing<br>yourself is exhausting,<br>right?` |
| 159 | `203:$761D` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Shizu: This is only a thought...` | `Shizu: This is only a<br>thought...` |
| 160 | `203:$76C7` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Shizu: This is only a thought...` | `Shizu: This is only a<br>thought...` |
| 161 | `203:$7919` | story_and_event_dialogue | 1 | line 1 → 2 | 140 px | `Tao: You are amazing, big bro!!` | `Tao: You are amazing, big<br>bro!!` |
| 162 | `203:$79C4` | story_and_event_dialogue | 1 | line 2 → 3 | 136 px | `Tao: Master Gaibara<br>currently holds the top spot.` | `Tao: Master Gaibara<br>currently holds the top<br>spot.` |
| 163 | `205:$40E6` | story_and_event_dialogue | 1 | line 1 → 2 | 143 px | `Mekerere: Truly, what a relief!` | `Mekerere: Truly, what a<br>relief!` |
| 164 | `205:$445E` | story_and_event_dialogue | 1 | line 1 → 2 | 141 px | `Minai: An oasis in the desert...` | `Minai: An oasis in the<br>desert...` |
| 165 | `205:$45BC` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Nipeba: The Magic Castle<br>looks as though it is burning.` | `Nipeba: The Magic Castle<br>looks as though it is<br>burning.` |
| 166 | `205:$45F3` | story_and_event_dialogue | 1 | line 2 → 3 | 139 px | `Nipeba: We are all fat. There<br>is nothing we can do about it.` | `Nipeba: We are all fat. There<br>is nothing we can do about<br>it.` |
| 167 | `205:$462B` | story_and_event_dialogue | 2 | line 2 → 3 | 141 px | `Nuwanko: Honestly, do<br>something about them already!!` | `Nuwanko: Honestly, do<br>something about them<br>already!!` |
| 168 | `205:$49C3` | story_and_event_dialogue | 1 | line 2 → 3 | 143 px | `Oro: In this dungeon, traps<br>catch monsters instead of you.` | `Oro: In this dungeon, traps<br>catch monsters instead of<br>you.` |
| 169 | `205:$4EA6` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Pigeon Handler: Now, I shall<br>explain the Revival Password.` | `Pigeon Handler: Now, I shall<br>explain the Revival<br>Password.` |
| 170 | `205:$50D5` | story_and_event_dialogue | 5 | line 2 → 3 | 136 px | `Ateka: For that alone, I<br>thank Kron, god of travelers.` | `Ateka: For that alone, I<br>thank Kron, god of<br>travelers.` |
| 171 | `205:$53DE` | story_and_event_dialogue | 1 | line 1 → 2 | 138 px | `Rai: What should we do first?` | `Rai: What should we do<br>first?` |
| 172 | `205:$54B4` | story_and_event_dialogue | 2 | line 2 → 3 | 141 px | `Rai: What in the world<br>happened inside that castle...?` | `Rai: What in the world<br>happened inside that<br>castle...?` |
| 173 | `205:$557D` | story_and_event_dialogue | 7 | line 1 → 2 | 138 px | `Rihipishi: I created Big Moai.` | `Rihipishi: I created Big<br>Moai.` |
| 174 | `205:$557D` | story_and_event_dialogue | 9 | line 2 → 3 | 137 px | `Rihipishi: Then I installed<br>rocket thrusters on its back.` | `Rihipishi: Then I installed<br>rocket thrusters on its<br>back.` |
| 175 | `205:$5EE2` | story_and_event_dialogue | 4 | line 1 → 2 | 141 px | `Higechiyo: Come again anytime.` | `Higechiyo: Come again<br>anytime.` |
| 176 | `205:$5F29` | story_and_event_dialogue | 2 | line 1 → 2 | 139 px | `Torepan: Warrior Hall...<page>...what?` | `Torepan: Warrior<br>Hall...<page>...what?` |
| 177 | `205:$63E3` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Torepan: No! What a shame...<br>You do not have enough Gitan!` | `Torepan: No! What a shame...<br>You do not have enough<br>Gitan!` |
| 178 | `205:$671D` | story_and_event_dialogue | 1 | line 2 → 3 | 138 px | `Wanda: We bought a Club and a<br>Wooden Shield for protection.` | `Wanda: We bought a Club and a<br>Wooden Shield for<br>protection.` |
| 179 | `205:$67E9` | story_and_event_dialogue | 1 | line 1 → 2 | 138 px | `Wanda: I may be imagining it...` | `Wanda: I may be imagining<br>it...` |
| 180 | `205:$6E60` | story_and_event_dialogue | 2 | line 1 → 2 | 140 px | `It restores a little Fullness.` | `It restores a little<br>Fullness.` |

## Automated rule

For three-line dialogue surfaces, reject any page marker that would wrap
from line one or line two. Keep the existing stricter rejection for markers
that would wrap below line three. A repair must keep the marker beside text;
it may not create a marker-only line or alter a pacing-sensitive `<page><br>`
sequence without explicit wording review. This rule is enforced by the shared
production layout validator and the complete-catalog regression.
