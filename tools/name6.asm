; Six-character English player-name runtime for Shiren GB2.
;
; This source is assembled at ROM bank $FD:$4000.  tools/name6.py contains
; the installer, fixed data tables, and the checked-in assembled code bytes so
; normal builds remain pure Python.  tests/test_name6.py reassembles this file
; with RGBDS when available and requires a byte-for-byte match.

DEF FarDispatch          EQU $09AC
DEF CopyFFString         EQU $0A50
DEF CopyBytes            EQU $0A5B
DEF CopyLinearVRAM       EQU $0A6B
DEF CopyTilemap          EQU $0ACC
DEF rVBK                 EQU $FF4F

DEF wNamePrefix          EQU $C252 ; diary + $16: four legacy characters
DEF wNameSuffix          EQU $C2A2 ; diary + $66: characters five and six
DEF wNameMarkerA         EQU $C2A4 ; diary + $68
DEF wNameMarkerB         EQU $C2A5 ; diary + $69
DEF wInputMode           EQU $C195
DEF wInputMaximum        EQU $C153
DEF wInputPosition       EQU $C152
DEF wInputBuffer         EQU $C16D
DEF wInputDirty          EQU $C196
DEF wNavigationType      EQU $C14E
DEF wRankingRecord       EQU $CF00
DEF wRankingSuffix       EQU $CFA5 ; first byte after the native $85-byte companion

DEF sRankHeader          EQU $BCD8
DEF sRankSuffixes        EQU $BCDC ; five categories * 50 physical slots * two bytes
DEF sRankSuffixCount     EQU 500

DEF EnglishCharacters   EQU $4300
DEF DefaultName          EQU $4350
DEF RankHeader           EQU $4360
DEF EnglishKeyboardMap   EQU $4400
DEF EnglishGlyphsLow     EQU $4600
DEF EnglishGlyphsHigh    EQU $4850
DEF RankingNoteNavigation EQU $4B00

DEF RankingNoteMode           EQU $02
DEF RankingNoteNavigationType EQU $F6
DEF NavigationScratch         EQU $C800

DEF NameMarkerA          EQU $A5
DEF NameMarkerB          EQU $5A

SECTION "Name6 runtime", ROMX[$4000], BANK[$FD]

; Core copier for Name6GetCompat below.  Copy the four-byte legacy prefix, then
; append the extension only when its two-byte marker proves this is a new save.
Name6Get::
    ld hl,wNamePrefix
    ld b,4
.prefix
    ld a,[hl+]
    cp $FF
    jr z,.done
    ld [de],a
    inc de
    dec b
    jr nz,.prefix

    ld a,[wNameMarkerA]
    cp NameMarkerA
    jr nz,.done
    ld a,[wNameMarkerB]
    cp NameMarkerB
    jr nz,.done
    ld hl,wNameSuffix
    ld b,2
.suffix
    ld a,[hl+]
    cp $FF
    jr z,.done
    ld [de],a
    inc de
    dec b
    jr nz,.suffix
.done
    ld a,$FF
    ld [de],a
    ret

; Replacement for 11:$4B46.  Keep the native four-byte field and terminator in
; place, put characters five and six in the unused diary tail, and mark them.
Name6Set::
    ld a,$FF
    ld hl,wNamePrefix
    ld b,5
.clear_prefix
    ld [hl+],a
    dec b
    jr nz,.clear_prefix
    ld hl,wNameSuffix
    ld b,2
.clear_suffix
    ld [hl+],a
    dec b
    jr nz,.clear_suffix
    ld a,NameMarkerA
    ld [wNameMarkerA],a
    ld a,NameMarkerB
    ld [wNameMarkerB],a

    ld hl,wNamePrefix
    ld b,4
.copy_prefix
    ld a,[de]
    cp $FF
    jr z,.return
    cp $D5
    jr z,.return
    ld [hl+],a
    inc de
    dec b
    jr nz,.copy_prefix

    ld hl,wNameSuffix
    ld b,2
.copy_suffix
    ld a,[de]
    cp $FF
    jr z,.return
    cp $D5
    jr z,.return
    ld [hl+],a
    inc de
    dec b
    jr nz,.copy_suffix
.return
    ret

; Replacement for 11:$42EB, the native Japanese default-name loader.
Name6Default::
    ld de,DefaultName
    jp Name6Set

; Replacement for the far call at F4:$4066.  Mode 3 shares the native
; four-byte branch, so only mode 4 is expanded.
Name6Maximum::
    ld a,$12
    ld hl,$502D
    call FarDispatch
    ld a,[wInputMode]
    cp 4
    ret nz
    ld a,6
    ld [wInputMaximum],a
    ret

; Wrapper for the mode-4 name and mode-2 Rankings-note screen call sites.
; Construct the native screen first (including its mode-specific field and
; attribute map), then replace only its tile IDs with the English keyboard.
; Mode 3 and Blank Scroll retain their independently owned maps.
Name6Screen::
    ld a,$F4
    ld hl,$4045
    call FarDispatch
    xor a
    ldh [rVBK],a
    ld hl,EnglishKeyboardMap
    ld de,$9840
    ld bc,$1014
    call CopyTilemap
    xor a
    ldh [rVBK],a
    ret

; Replacement for the shared mode-2/mode-4 character/action far call at
; 16:$5B66.
; Nodes $00-$4C are English characters.  Confirm and the three editing actions
; at $4D-$50 retain their native behavior.
Name6Input::
    ld a,c
    cp $4D
    jr nc,.native_action
    ld b,0
    ld hl,EnglishCharacters
    add hl,bc
    ld b,[hl]
    ld a,$12
    ld hl,$524C
    jp FarDispatch
.native_action
    ld a,$12
    ld hl,$5215
    jp FarDispatch

; Z is set only when the four-byte ranking-extension header is present.
RankHeaderValid:
    ld hl,sRankHeader
    ld de,RankHeader
    ld b,4
.loop
    ld a,[de]
    cp [hl]
    ret nz
    inc de
    inc hl
    dec b
    jr nz,.loop
    xor a
    ret

; The old game leaves this range outside every native structure.  Initialize
; it lazily so old saves need no migration pass merely to boot.
RankEnsureTable:
    call RankHeaderValid
    ret z
    ld hl,sRankSuffixes
    ld bc,sRankSuffixCount
    ld d,$FF
.clear
    ld a,d
    ld [hl+],a
    dec bc
    ld a,b
    or c
    jr nz,.clear
    ld hl,sRankHeader
    ld de,RankHeader
    ld b,4
.header
    ld a,[de]
    ld [hl+],a
    inc de
    dec b
    jr nz,.header
    xor a
    ret

; Input: B = category (0..4), E = physical record slot (0..49).
; Output: HL = address of its two-byte suffix in SRAM bank 3.
RankSuffixAddress:
    ld hl,sRankSuffixes
    ld a,b
    and a
    jr z,.slot
    ld bc,100
.category
    add hl,bc
    dec a
    jr nz,.category
.slot
    ld a,e
    add a,a
    ld e,a
    ld d,0
    add hl,de
    ret

; Replacement for 11:$5F1C.  Write the untouched 32-byte native record to
; SRAM bank 0, then attach the diary suffix to its physical slot in bank 3.
RankWrite::
    push bc
    push de
    ld a,$0B
    ld hl,$5F57
    call FarDispatch
    xor a
    ld [$4100],a
    ld d,h
    ld e,l
    ld hl,$DD00
    ld b,$20
    call CopyBytes
    pop de
    pop bc

    ld a,3
    ld [$4100],a
    push bc
    push de
    call RankEnsureTable
    pop de
    pop bc
    call RankSuffixAddress
    ld a,[wNameMarkerA]
    cp NameMarkerA
    jr nz,.legacy
    ld a,[wNameMarkerB]
    cp NameMarkerB
    jr nz,.legacy
    ld a,[wNameSuffix]
    ld [hl+],a
    ld a,[wNameSuffix+1]
    ld [hl],a
    ret
.legacy
    ld a,$FF
    ld [hl+],a
    ld [hl],a
    ret

; Replacement for 11:$5639.  Load the native record exactly as before and put
; its validated suffix in the two bytes immediately after the companion WRAM
; record.  Missing headers (all old saves) deliberately yield $FF,$FF.
RankLoad::
    ld a,$FF
    ld [wRankingSuffix],a
    ld [wRankingSuffix+1],a
    push bc
    ld a,$0B
    ld hl,$5525
    call FarDispatch
    pop bc
    ld a,e
    cp $FF
    ret z

    push bc
    push de
    ld a,$0B
    ld hl,$5F57
    call FarDispatch
    xor a
    ld [$4100],a
    ld de,wRankingRecord
    ld b,$20
    call CopyBytes
    pop de
    pop bc

    ld a,3
    ld [$4100],a
    push bc
    push de
    call RankHeaderValid
    pop de
    pop bc
    ret nz
    push bc
    push de
    call RankSuffixAddress
    ld a,[hl+]
    ld [wRankingSuffix],a
    ld a,[hl]
    ld [wRankingSuffix+1],a
    pop de
    pop bc
    ret

; Replacement for 11:$56E2.  Short legacy names stop at their original $FF;
; a full four-byte prefix may append the validated two-byte ranking suffix.
RankRenderName::
    ld hl,wRankingRecord+$0F
    ld b,4
.prefix
    ld a,[hl+]
    cp $FF
    jr z,.done
    ld [de],a
    inc de
    dec b
    jr nz,.prefix
    ld hl,wRankingSuffix
    ld b,2
.suffix
    ld a,[hl+]
    cp $FF
    jr z,.done
    ld [de],a
    inc de
    dec b
    jr nz,.suffix
.done
    ld a,$FF
    ld [de],a
    ret

; Replacement for 11:$4B2F.  The native getter wraps CopyFFString.  Besides the
; copied bytes, callers therefore receive BC = visible character count and
; HL/DE = one byte past the legacy source terminator.  The combat formatter at
; 00:$3307 explicitly compares against C.  Preserve that incidental ABI even
; though the six-character source is now split across two fields.
Name6GetCompat::
    push de
    call Name6Get
    pop hl
    ld bc,$FFFF
.length
    ld a,[hl+]
    inc bc
    inc a
    jr nz,.length
    ld hl,wNamePrefix
.source_end
    ld a,[hl+]
    inc a
    jr nz,.source_end
    ld d,h
    ld e,l
    ret

; Shared name/message input wrapper. Grid nodes $00-$3D contain both alphabets
; and the digits. Mode 4 keeps $3E-$4A/$4C unreachable; mode 2 treats those
; fourteen empty cells as spaces. $4B is the labeled SPACE action. $4E/$4F
; are swapped so their left-to-right symbols move the caret left/right. At the
; end of a mode-2 message, right pads a space instead of refusing to advance.
Name6InputClean::
    ld a,c
    cp $3E
    jp c,Name6Input
    cp $4B
    jr c,.mode2_space
    jr z,.space
    cp $4C
    jr z,.mode2_space
    cp $4E
    jr z,.buffer_left
    cp $4F
    jr nz,.native_action
    ld a,[wInputMode]
    cp RankingNoteMode
    jr nz,.buffer_right
    push bc
    ld a,[wInputPosition]
    ld e,a
    ld d,0
    ld hl,wInputBuffer
    add hl,de
    ld a,[hl]
    pop bc
    cp $D5
    jr z,.space
.buffer_right
    ld c,$4E
    jr .native_action
.buffer_left
    ld c,$4F
.native_action
    ld a,$12
    ld hl,$5215
    jp FarDispatch
.mode2_space
    ld a,[wInputMode]
    cp RankingNoteMode
    ret nz
.space
    ld b,$24
    ld a,$12
    ld hl,$524C
    jp FarDispatch

; Keep the public screen-wrapper address stable while leaving the removed
; CLEAR implementation genuinely absent from the runtime.
ASSERT @ <= $4232
    ds $4232-@

; The native constructor uploads raw Japanese keyboard tiles after the normal
; font loader.  Restore the two English code-page spans actually used here,
; then retain Name6Screen's exact English tile-ID map.
Name6ScreenClean::
    push bc
    call Name6Screen
    xor a
    ldh [rVBK],a
    ld hl,EnglishGlyphsLow
    ld de,$9000
    ld bc,$0250
    call CopyLinearVRAM
    ld hl,EnglishGlyphsHigh
    ld de,$9300
    ld bc,$0280
    call CopyLinearVRAM
    pop bc
    ld a,c
    cp RankingNoteMode
    ret nz
    ld hl,RankingNoteNavigation
    ld de,NavigationScratch
    ld bc,$0237
.copy_navigation
    ld a,[hl+]
    ld [de],a
    inc de
    dec bc
    ld a,b
    or c
    jr nz,.copy_navigation
    ld a,RankingNoteNavigationType
    ld [wNavigationType],a
    ret

ASSERT @ <= $4280
    ds $4280-@

ASSERT @ <= EnglishCharacters
