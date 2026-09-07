# Clear Campaign passwords

The **Clear Campaign** password is not entered anywhere in Shiren GB2. It was an
authentication code for Chunsoft's original real-world mail-in promotion.

The certificate is reached from **Adventure → History → Clear Campaign** after the
corresponding clear condition is available. The adjacent campaign instructions tell the
player to write their postal details, Wanderer Points, Diary ID, and Password on a postcard
and mail it to Chunsoft. The advertised reward was Shiren merchandise for the first 100
applicants. The separate **True Wanderer** certificate refers to the same postal address
and likewise has no in-game password-entry screen.

This system is independent of both other code families:

- Big Moai's four-character promotional “spells” are entered at the Big Moai NPC.
- Wanderer Rescue uses 12-, 13-, and 15-character Thank-You, SOS, and Revival passwords.
- Clear Campaign and True Wanderer each display a six-character mail-in authentication
  code only.

## Localization contract

The field labels use an ordinary English colon immediately after the label and one
space before its value: `Wanderer Points: 41191`, `Diary ID: 34656`, and
`Password: QVZ9Ee`. The former fixed `<hspace>` padding and native `<27>` colon glyph
have been removed from both the Clear Campaign (`193:$7594`) and True Wanderer
(`193:$7678`) records. The True Wanderer record retains its `ID Number` wording.
These are text-only changes in `script/en/ui_system.tsv`; the certificate generators
and display-only alphabet conversion are unchanged.

Both certificate generators use the same native 64-symbol display alphabet already
proven for Wanderer Rescue. The English presentation therefore uses the established
one-to-one alphabet `A-Z a-z 0-9 ? !`. Only the six-byte display copy at `$FFB0` is mapped;
the native value at `$C16D` is never changed.

| Certificate | Text selector | Native generator | Display hook |
|---|---|---|---|
| Clear Campaign | group 16 index 40, `<cF8>d` | `17:$7E3B` | `0:$3573` |
| True Wanderer | group 16 index 42, `<cF8>b` | `17:$7E01` | `0:$355F` |

`SaveStates/clear-campaign-password.state` opens the first certificate directly. After
returning to the Adventure menu, choose **History**, move down to **Clear Campaign**, and
confirm to force a fresh render. The fixture's six native bytes are
`40 45 49 76 34 4E`, which must display as `QVZ9Ee` while remaining byte-exact in
`$C16D`.

`tests.test_clear_campaign_password` performs that controller replay in PyBoy. Its
pixel-level oracle reruns the same route with only the six expected display bytes injected
at the full-renderer boundary, compares the resulting pixels, and separately verifies the
native buffer. It does not approve or update a framebuffer hash from the defective output.

`SaveStates/clear-campaign.state` is the additional spacing-report fixture, converted
with `../mesen-to-pyboy/mss_to_pyboy.py` from the user's original capture. Its SHA-1 is
`219e5b935870abb03f68ce74be9801b73ed62c2b`; the preserved source's SHA-1 is
`c96b781ddc7c664968a91f0a3709425b01651054`. It displays 41191 points, Diary ID 34656,
and native password bytes `40 45 49 76 34 4E`. Reopening the certificate through
History exercises the current ROM text instead of retaining the state's old pixels.

The spacing comparison under `build/clear-campaign-spacing/` replays that real route
before and after the text edit in both fonts. A separate disposable template preview
substitutes group 16 index 42 for index 40 to render the True Wanderer record in the
same certificate window. It exercises the original True Wanderer substitutions and
checks unchanged native password bytes, but does not claim to unlock or traverse the
True Wanderer menu on this diary.
