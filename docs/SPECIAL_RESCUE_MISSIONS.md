# Special rescue mission passwords

These three **SOS passwords work with this project's English patch**, in both font
styles. They recreate the rescue requests published for **Emergency Order! The True
Wanderer Rescue Team Mobilizes!!**, the 2001 guidebook promotion. The original Japanese
codes and their advertised floors were checked against the printed guidebook excerpts
preserved by the [Mystery Dungeon Franchise Wiki][campaign].

| Mission | Dungeon in this patch | Target | English SOS password | Original Japanese SOS password |
|---|---|---:|---|---|
| Beginner | Wanado | 20F | `qBdEtn!6EGwMi` | `ろいほおんりぶづおきぐすも` |
| Intermediate | Tonfan's Hole | 40F | `e!8myroubgO8A` | `まぶどらごわるがふむそどあ` |
| Advanced | Abyssal Depths | 98F | `AIGJ!7XWTVL!x` | `あけきこぶでねぬとにしぶげ` |

**Enter all 13 characters exactly, including capitals and `!`.** The intermediate
password contains an uppercase letter `O`, not a zero. The wiki calls Wanado “The Road
of Traps,” Tonfan's Hole “Tonfan Dungeon,” and Abyssal Depths “Edge of the Abyss.” These
are the same three destinations.

## Playing a mission

1. Visit the **Rescue Team building in Ilpa** and talk to **Good** about a new rescue.
2. Choose **Password** as the connection method. Advance his explanation to the
   **SOS Password** entry screen.
3. Enter the English code and confirm with **OK**. Filling the last cell automatically
   selects OK; press A to submit it.
4. After Good confirms the request, use the **Rescue Gate**, reach the target floor,
   and rescue the fallen Shiren as in an ordinary rescue.

The usual dungeon-access requirements still apply. If Good says **“You cannot enter
that dungeon yet!”**, the code was decoded but your diary has not unlocked that
destination. Previous-rescue checks also still apply; these are not unlimited gift
codes or a way to bypass progression.

The promotion asked players to submit their resulting **Revival Password** by mail.
Its January 10, 2002 deadline has passed; there is no active prize submission service.
The SOS missions themselves use the game's offline rescue system. Their “True Wanderer”
campaign name does not make them the six-character **True Wanderer** certificate in
Adventure History. [Campaign history and original instructions][campaign].

## Convert other Japanese rescue passwords

The [browser converter](rescue-converter/index.html) includes all three mission presets,
copyable output, reverse conversion, and checksum checking. Open that file locally with
the other files in its folder beside it; no server or ROM is needed. For GitHub hosting,
see the [Pages setup](rescue-converter/README.md).

The command-line converter also needs no ROM or third-party Python packages:

```sh
# Japanese → this English patch
python3 tools/rescue_converter.py 'ろいほおんりぶづおきぐすも'
# qBdEtn!6EGwMi

# This English patch → Japanese; single quotes protect ! in interactive shells.
python3 tools/rescue_converter.py 'qBdEtn!6EGwMi' --to japanese
# ろいほおんりぶづおきぐすも

# A pasted password, including spaces/newlines, can also come from standard input.
python3 tools/rescue_converter.py -

# Include the detected packet type and decoded payload for diagnosis.
python3 tools/rescue_converter.py 'あけきこぶでねぬとにしぶげ' --json
```

Both tools support GB2 **Training (9 symbols), Thank-You (12), SOS (13), and Revival
(15)** passwords. They ignore whitespace and normalize decomposed kana, katakana, and
full-width text. English letters remain case-sensitive. Incorrect lengths, unsupported
characters, mixed alphabets, and failing checksums produce an error.

Conversion changes only the displayed alphabet. It preserves the original packet and
even unused symbol-padding bits. It cannot unlock a dungeon, finish a rescue, generate
a matching Revival/Thank-You response, or verify which diary a response belongs to.
A valid checksum catches many copying mistakes but is not proof of those conditions.

Big Moai's four-character gifts have their own [code list](BIG_MOAI_CODES.md).
Six-character [Clear Campaign / True Wanderer certificates](CLEAR_CAMPAIGN.md) are
mail-in codes with no game input screen. Codes from other Shiren games are unsupported.

## Are there more special missions hidden in the ROM?

**No additional built-in promotional rescue list was found.** These three requests
are ordinary encoded SOS packets distributed outside the game. All three decode with
the existing native packet codec, with exactly the advertised dungeon IDs and floors:

| Mission | Dungeon ID | Packed nine-byte SOS payload | Unpacked ten-byte rescue record |
|---|---:|---|---|
| Beginner | `$08` | `AB32750585914C2205` | `AB32750585910C120814` |
| Intermediate | `$07` | `82D09790F6887E1F0A` | `82D09790F6881E1B0728` |
| Advanced | `$06` | `F9F29BC5BE948E9918` | `F9F29BC5BE940E0C0662` |

The verified original ROM was searched in full for each code's native display bytes,
six-bit symbols, packed packet, unpacked rescue record, and four-byte dungeon seed in
both byte orders. None occurs as a contiguous literal. The existing **mgbdis** output
was also inspected along the relevant native path:

| Native location | Finding |
|---|---|
| `11:$76CA-$76E9`, `11:$7B17-$7DF4` | Shared packet decoder/checksum and location unpacking; SOS is packet type 0. |
| `11:$76F2-$77C4` | SOS semantic checks, requester identity check, history check, diary storage, and dungeon-access/setup calls. No promotional whitelist or special mission selector was found on this path. |
| `0B:$60C7-$613A` | The apparent 35-entry comparison list reads **the player's rescue history from SRAM bank 3**, starting at `$BB57`, in 11-byte records. It is not a ROM list of special codes. |
| `05:$6443-$648A` | Destination access depends on normal story progression. Wanado requires `$1F`, Tonfan's Hole `$1C`, and Abyssal Depths `$24` in the progression byte read from `$C3EF`. These are internal progress values, not floors. |
| `11:$792D-$797A` | Normal SOS generation encodes the current dungeon seed, requester ID, player coordinates, dungeon, and floor. |

This establishes why the published requests need no additional ROM patch. It does
**not** prove that no other magazine, guidebook, or promotion ever published an SOS
password. Such externally generated requests need not leave any list in the cartridge.
The 100 [Big Moai spells](BIG_MOAI.md) are a separately confirmed promotional system,
not additional rescue missions.

Reproduce the packet search and record the reviewed code-region hashes with:

```sh
python3 tools/audit_special_rescues.py "$ROM" > build/special-rescue-audit.json
```

## Verification and provenance

The source is *Shiren the Wanderer GB2: Magic Castle of the Desert Official Perfect
Guide*, p. 206, ISBN **978-4757706071**, as preserved in these original excerpts:
[beginner][beginner], [intermediate][intermediate], [advanced][advanced]. The project's
small transcribed code/destination data lives in
[`data/special_rescue_missions.json`](../data/special_rescue_missions.json); the scans
are not bundled with the converter.

`tests.test_special_rescue_missions` enters all three English passwords using actual
controller navigation in both font builds. It checks all 13 native bytes before the
original validator, return status 0, and the exact ten-byte stored rescue record.
The hash-verified fixture is `SaveStates/rescue-entry-menu.state` (SHA-1
`8c79794a9ae28857dd51ebe343191e1796007164`). It starts early in the game, so acceptance
tests advance only `$C3EF` to `$24` in disposable emulator copies. Separate replays
leave that byte untouched and require the native locked-dungeon result 2 for each
mission. No source state, player save, or production ROM is modified.

This verifies password entry and acceptance, **not a completed playthrough of all
three rescue dungeons**. The broader rescue completion/cable limitations are recorded
in [RESCUE_SYSTEM.md](RESCUE_SYSTEM.md).

The converter tests also compare Python and browser output against the existing native
codec over every packet length, all 64 alphabet symbols, randomized payloads, preserved
padding-bit cases, and Unicode paste variants. The browser alphabet is generated from
the same constants used by the ROM's English rescue presentation.

[campaign]: https://mysterydungeonwiki.com/wiki/Meta:Emergency_Order!_The_True_Wanderer_Rescue_Team_Mobilizes!!
[beginner]: https://mysterydungeonwiki.com/images/3/35/Magic_Castle_GBC_-_Emergency_Order_Beginner_Directive.png
[intermediate]: https://mysterydungeonwiki.com/images/a/a5/Magic_Castle_GBC_-_Emergency_Order_Intermediate_Directive.png
[advanced]: https://mysterydungeonwiki.com/images/0/09/Magic_Castle_GBC_-_Emergency_Order_Advanced_Directive.png
