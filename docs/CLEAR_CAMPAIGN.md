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
