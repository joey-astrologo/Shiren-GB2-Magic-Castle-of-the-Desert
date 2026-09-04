# Gender Reference Audit

## Result

Princess Ateka's parent, the Lord of Ilpa, is her **father**. The inconsistent
English references came from one incorrect character-table entry: source code
`F13C` was decoded as `母` (mother), but the glyph and its eleven story contexts
are `父` (father).

The source mapping and every affected English line have been corrected. A
second contextual pass found three feminine pronouns later in the Lord's
recovery scene; those have also been corrected. No unresolved gender-reference
decisions remain from this audit.

This conclusion agrees with the original dialogue (`父上`, `お父さま`, and
`父子` after the corrected decode), the Lord's line identifying Ateka as his
daughter, and Chunsoft's official character description of Ateka worrying
about her transformed father:

- [Official Shiren GB2 character page](https://www.spike-chunsoft.co.jp/pages/games/shirengb2/stage02.html)
- [Shiren DS2 character introduction](https://www.inside-games.jp/news/298/29842.html)

## Corrected English records

| Record | Before | After |
| --- | --- | --- |
| `195:$5AF9` | `I help my mom here.` | `I help my father here.` |
| `195:$6EF3` | `Mother...?` / `She asks that you...` | `Father...?` / `He asks that you...` |
| `195:$705F` | `Ateka: Mother...` | `Ateka: Father...` |
| `196:$4C76` | `both you and your mother` | `both you and your father` |
| `196:$4F45` | `your role and your mother's` | `Your roles as father and daughter` |
| `196:$548D` | `separating her from ... Curas` | `separating him from ... Curas` |
| `196:$54B7` | `Mother will...` | `Father will...` |
| `196:$54E1` | `She won't recover?` | `He won't recover?` |
| `196:$54F2` | `She looks like she's ...` / `Mother...` | `He looks like he's ...` / `Father...` |
| `196:$558F` | `She is certainly cursed.` / `possessed her` | `He is certainly cursed.` / `possessed him` |
| `196:$5B2A` | `Mother ... she ... her` | `Father ... he ... him` |
| `197:$468E` | `Ateka: Mother!` | `Ateka: Father!` |
| `197:$4B1B` | `For saving Mother...` | `For saving Father...` |

Record `196:$5C17` also contains the corrected source glyph (`父子`, the
father-child pair), but its existing English, `save them both too`, was already
accurate and did not need rewriting.

## Audit scope

The review covered:

- all eleven prose records containing source code `F13C`;
- all 70 production prose records containing English personal pronouns;
- all 18 production prose records containing English family terms;
- all Japanese family terms visible through the decoded prose catalog;
- the surrounding Lord, Ateka, Sachi, Oryu, and Curas scenes for references
  whose Japanese omits the subject.

The pronoun and family-term sets overlap; they are counts of candidate records,
not a combined total.

## Reviewed references that remain unchanged

- `203:$6ECE`: Sara says not to speak that way in front of `おかあさん`—her
  own mother. This is unrelated to Ateka and the Lord.
- `Curse Mom` and `Curse Sister`: established monster names in the glossary and
  monster descriptions, not character-reference mistakes.
- Sachi's father, Oro, was already correctly identified in the other restaurant
  and tournament dialogue.
- Feminine pronouns referring to Ateka, Oryu, Obaba, Sachi, and other women,
  and masculine pronouns referring to the Lord, Curas, Zagan, Pekeji, and other
  men, were consistent in the remaining candidate records.

## Regression coverage

Focused tests now verify both the `F13C` decode and all affected Lord/Ateka
story references. The tests reject a future return of `mother`, `mom`, `she`,
or `her` in the corrected records.
