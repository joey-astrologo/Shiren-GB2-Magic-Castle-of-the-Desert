# Dialogue Page-Cursor Audit

## Purpose

The dialogue page marker is nine pixels wide. When a page ends on the third
physical line, the final text pen must be at pixel 135 or earlier. A final pen
of 136-143 makes the marker wrap outside the dialogue surface and can leave its
graphic in all four corners of the window.

This audit found 15 unsafe endpoints representing 14 distinct English texts.
The two rescue-award records contain the same text and can share one decision.

All 14 wording decisions were approved and inserted on 2026-09-02. The final
versions preserve the existing number of lines, page waits, and box resets.
Widths are listed in pixels as `line 1 / line 2 / line 3`. Only the third line
has a page marker in these cases; earlier lines may therefore use the normal
143-pixel text budget.

## Decision summary

| # | Record | Scene | Before | After | Decision |
|---:|---|---|---:|---:|---|
| 1 | `196:$4424` | Ilpa crisis — Amokachi | 143 | 94 | Approved |
| 2 | `196:$5789` | Jahannam opens — Oryu | 141 | 113 | Approved |
| 3 | `196:$5C17` | Final-dungeon council — Oryu | 136 | 119 | Approved |
| 4 | `197:$497D` | Evil God finale — Koppa | 136 | 130 | Approved |
| 5 | `197:$5315` | Main ending — Rai | 138 | 104 | Approved |
| 6 | `197:$5ED3` | Postgame begins — rustling | 140 | 131 | Approved |
| 7 | `198:$4D72` | Blacksmith side quest | 139 | 101 | Approved |
| 8 | `199:$6C88` | Rescue explanation — Good | 142 | 109 | Approved |
| 9 | `199:$6F39`, `199:$6F85` | Rescue reward — Good | 139 | 110 | Approved |
| 10 | `199:$7817` | Warehouse explanation — Kame | 138 | 123 | Approved |
| 11 | `203:$4C71` | Training grounds — Bubuyaro | 139 | 133 | Approved |
| 12 | `203:$52CE` | Rescue NPC — Hachi | 137 | 120 | Approved |
| 13 | `205:$4EA6` | Revival Password tutorial | 139 | 133 | Approved |
| 14 | `193:$5203` | Dungeon message — Nag-Mo speech | 139 | 117 | Approved |

## 1. Amokachi — Ilpa crisis

Record: `196:$4424`  
Widths before: `106 / 104 / 143`  
Widths after: `113 / 111 / 94`

Before:

```text
Amokachi: Is this town
eventually going to be
swallowed by the desert too...?
```

After:

```text
Amokachi: Will this town
eventually be swallowed
by the desert too...?
```

- [X] Approve this wording
- [ ] Request another wording

## 2. Oryu — Jahannam opens

Record: `196:$5789`  
Widths before: `82 / 122 / 141`  
Widths after: `82 / 94 / 113`

The first line waits for input, then the next two lines appear in the same
physical dialogue box.

Before:

```text
Oryu: <name>...                 [page wait]
I'll be waiting on the hill
overlooking the Magic Castle...
```

After:

```text
Oryu: <name>...                 [page wait]
I'll wait on the hill
above the Magic Castle...
```

- [X] Approve this wording
- [ ] Request another wording

## 3. Oryu — final-dungeon council

Record: `196:$5C17`  
Widths before: `114 / 92 / 136`  
Widths after: `114 / 92 / 119`

Before:

```text
Oryu: I disguised myself
as an attendant and
infiltrated the Magic Castle.
```

After:

```text
Oryu: I disguised myself
as an attendant and
entered the Magic Castle.
```

The disguise still communicates the covert entry, while `entered` creates
enough room for the marker.

- [X] Approve this wording
- [ ] Request another wording

## 4. Koppa — Evil God finale

Record: `197:$497D`  
Widths before: `60 / 83 / 136`  
Widths after: `60 / 83 / 130`

Before:

```text
Koppa: That's
great, <name>.
Everyone is ready to rebuild.
```

After:

```text
Koppa: That's
great, <name>.
Everyone's ready to rebuild.
```

- [X] Approve this wording
- [ ] Request another wording

## 5. Rai — main ending

Record: `197:$5315`  
Widths before: `124 / 107 / 138`  
Widths after: `124 / 107 / 104`

Before:

```text
Rai: I'm surprised there've
been so many Collapsed
Wanderers around here lately.
```

After:

```text
Rai: I'm surprised there've
been so many Collapsed
Wanderers here lately.
```

- [X] Approve this wording
- [ ] Request another wording

## 6. Postgame rustling

Record: `197:$5ED3`  
Widths before: `140 / 140 / 140`  
Widths after: `131 / 131 / 131`

Before:

```text
Rustle, rustle, rustle, rustle.
Rustle, rustle, rustle, rustle.
Rustle, rustle, rustle, rustle.
```

After:

```text
Rustle rustle rustle rustle.
Rustle rustle rustle rustle.
Rustle rustle rustle rustle.
```

This keeps all twelve repetitions and changes only their cadence punctuation.

- [X] Approve this wording
- [ ] Request another wording

## 7. Blacksmith side quest

Record: `198:$4D72`, third dialogue box  
Widths before: `135 / 114 / 139`  
Widths after: `135 / 114 / 101`

Before:

```text
Blacksmith: He forged mighty
swords and shields, then
challenged this place himself.
```

After:

```text
Blacksmith: He forged mighty
swords and shields, then
challenged it himself.
```

- [X] Approve this wording
- [ ] Request another wording

## 8. Good — rescue questions

Record: `199:$6C88`  
Widths before: `100 / 115 / 142`  
Widths after: `100 / 115 / 109`

Before:

```text
Good: If you have any
questions about rescues,
please ask the Pigeon Handler!
```

After:

```text
Good: If you have any
questions about rescues,
ask the Pigeon Handler!
```

- [X] Approve this wording
- [ ] Request another wording

## 9. Good — completed-rescue reward

Records: `199:$6F39` and `199:$6F85`  
Widths before: `123 / 130 / 139`  
Widths after: `123 / 142 / 110`

This is the text reproduced by `SaveStates/long-text-in-window-rescue.state`.

Before:

```text
Good: The Wanderer Rescue
Federation will award you a
Revival Password and an item!
```

After:

```text
Good: The Wanderer Rescue
Federation awards you an item
and a Revival Password!
```

- [X] Approve this wording
- [ ] Request another wording

## 10. Kame — warehouse explanation

Record: `199:$7817`, tenth dialogue box  
Widths before: `136 / 133 / 138`  
Widths after: `136 / 133 / 123`

Before:

```text
Kame: Maybe a Pot gets cross
when you leave it behind and
makes its contents disappear.
```

After:

```text
Kame: Maybe a Pot gets cross
when you leave it behind and
makes its contents vanish.
```

- [X] Approve this wording
- [ ] Request another wording

## 11. Bubuyaro — training grounds

Record: `203:$4C71`  
Widths before: `123 / 137 / 139`  
Widths after: `123 / 137 / 133`

Before:

```text
Bubuyaro: Levels gained in
the training grounds will not
matter in the Abyssal Depths.
```

After:

```text
Bubuyaro: Levels gained in
the training grounds will not
count in the Abyssal Depths.
```

- [X] Approve this wording
- [ ] Request another wording

## 12. Hachi — rescue NPC

Record: `203:$52CE`, second dialogue box  
Widths before: `106 / 130 / 137`  
Widths after: `106 / 130 / 120`

Before:

```text
Hachi the Wanderer: He
must have risked himself to
rescue others time and again.
```

After:

```text
Hachi the Wanderer: He
must have risked himself to
rescue others many times.
```

- [X] Approve this wording
- [ ] Request another wording

## 13. Pigeon Handler — Revival Password tutorial

Record: `205:$4EA6`, second dialogue box  
Widths before: `118 / 141 / 139`  
Widths after: `118 / 141 / 133`

Before:

```text
Pigeon Handler: It is the
Password that lets you revive
after collapsing in a dungeon.
```

After:

```text
Pigeon Handler: It is the
Password that lets you revive
if you collapse in a dungeon.
```

- [X] Approve this wording
- [ ] Request another wording

## 14. Nag-Mo dungeon speech

Record: `193:$5203`  
Widths before: `77 / 102 / 139`  
Widths after: `77 / 102 / 117`

Before:

```text
Hey! Listen when
someone's talking! Why
leave it in a place like that...
```

After:

```text
Hey! Listen when
someone's talking! Why
leave it in such a place...
```

- [X] Approve this wording
- [ ] Request another wording

## Automated rule

For dialogue surfaces:

1. Continue rejecting any physical box longer than three lines.
2. At every third-line `<page>`, reserve the native marker's nine-pixel advance.
3. Reject a third-line final pen greater than 135 pixels.
4. Reject earlier-line marker wraps too: although they remain inside the box,
   they leave a detached, improperly animated marker at the following line's
   origin. See `DETACHED_PAGE_MARKER_AUDIT.md` for the complete approved audit.
5. Never repair a violation by creating an empty fourth line or a line that
   contains only the page marker.
