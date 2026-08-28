; English Blank Scroll input support for Shiren GB2.
;
; This source is assembled at ROM bank $FB:$4000.  tools/blank_scroll.py
; contains the checked-in assembled bytes so production builds do not require
; RGBDS.  The test suite reassembles this file when RGBDS is available.

DEF FarDispatch          EQU $09AC
DEF rVBK                 EQU $FF4F
DEF rSVBK                EQU $FF70

DEF wInputMode           EQU $C195
DEF wInputMaximum        EQU $C153
DEF wInputMatch          EQU $C196

DEF Name6Maximum        EQU $407B
DEF Name6InputClean      EQU $41D9
DEF Name6ScreenClean     EQU $4232

DEF BlankMaximum        EQU $4000
DEF BlankInput           EQU $4020
DEF BlankScreen          EQU $4040
DEF BlankConfirm         EQU $4080
DEF BlankResolve         EQU $40B0
DEF BlankMatchFull       EQU $4100
DEF BlankNameTable       EQU $4180
DEF ScrollHistory        EQU $DE1C
DEF HyphenNode           EQU 52 ; the name keyboard's otherwise unused 0 cell
DEF HyphenCode           EQU $4D
DEF BlankMaximumChars    EQU 11 ; longest localized Scroll root
DEF BlankHyphenTile      EQU $998D ; keyboard row 10, column 13

SECTION "Blank Scroll runtime", ROMX[$4000], BANK[$FB]

; Extend only input mode 1 after retaining name6's six-character mode-4 hook.
BlankScrollMaximum::
    ld a,$FD
    ld hl,Name6Maximum
    call FarDispatch
    ld a,[wInputMode]
    cp 1
    ret nz
    ld a,BlankMaximumChars
    ld [wInputMaximum],a
    ret

ASSERT @ <= BlankInput
    ds BlankInput-@

; Mode 1 reuses the English name keyboard's character table, except that its
; 0 node enters the hyphen required by Trap-eraser.  Every other mode retains
; the exact name6 input behavior.
BlankScrollInput::
    ld a,[wInputMode]
    cp 1
    jr nz,.name6
    ld a,c
    cp HyphenNode
    jr nz,.name6
    ld b,HyphenCode
    ld a,$12
    ld hl,$524C
    jp FarDispatch
.name6
    ld a,$FD
    ld hl,Name6InputClean
    jp FarDispatch

ASSERT @ <= BlankScreen
    ds BlankScreen-@

; Build the proven English keyboard and glyph resources, then relabel the
; mode-1-only 0 cell as a hyphen.  The native controller/navigation graph is
; intentionally retained.
BlankScrollScreen::
    ld a,$FD
    ld hl,Name6ScreenClean
    call FarDispatch
    xor a
    ldh [rVBK],a
    ld a,HyphenCode
    ld [BlankHyphenTile],a
    xor a
    ldh [rVBK],a
    ret

ASSERT @ <= BlankConfirm
    ds BlankConfirm-@

; Resolve the full presentation-layer name while it is still intact.  The
; localized matcher caches the concrete root index at wInputMatch. Once that ID
; exists, reduce the shared native field to its original seven-byte contract
; before validation returns to the action engine.
BlankScrollConfirm::
    call BlankScrollMatchFull
    ld a,[wInputMode]
    cp 1
    jr nz,.validate
    call RestoreNativeTail
.validate
    ld a,$12
    ld hl,$50F7
    jp FarDispatch

ASSERT @ <= BlankResolve
    ds BlankResolve-@

; The Blank Scroll converter normally compares every candidate root against
; the typed string.  This replaces only that comparison call: return B=1/C=0
; when the current candidate in E is the concrete ID cached above, or B=0
; otherwise.  The native loop, stack unwinding, and continuations stay intact.
BlankScrollResolve::
    ld a,[wInputMatch]
    cp e
    jr z,.matched
    ld bc,0
    ret
.matched
    ld bc,$0100
    ret

RestoreNativeTail:
    ld a,$FF
    ld [$C174],a
    ld a,$D5
    ld [$C175],a
    ld [$C176],a
    ld [$C177],a
    ld [$C178],a
    ret

ASSERT @ <= BlankMatchFull
    ds BlankMatchFull-@

; Match the full localized presentation string directly.  Do not use the
; native $C18D scratch copy: byte 9 of that seven-character work area is the
; live input-mode variable at $C195.  Each entry contains root ID, notebook
; byte offset, notebook mask, byte length, and the encoded full name.
BlankScrollMatchFull::
    ld a,$FF
    ld [wInputMatch],a
    ldh a,[rSVBK]
    push af
    ld a,$02
    ldh [rSVBK],a
    ld hl,BlankScrollNameTable
.next
    ld a,[hl+]
    cp $FF
    jr z,.notFound
    ld c,a
    ld a,[hl+]
    ld d,a
    ld a,[hl+]
    ld e,a
    ld a,[hl+]
    ld b,a
    push de
    push bc
    push hl
    ld de,$C16D
.compare
    ld a,[de]
    cp [hl]
    jr nz,.mismatch
    inc de
    inc hl
    dec b
    jr nz,.compare
    ld a,[de]
    cp $D5
    jr z,.candidate
    cp $FF
    jr nz,.mismatch
.candidate
    pop de
    pop bc
    pop de
    push hl
    push bc
    ld hl,ScrollHistory
    ld a,l
    add d
    ld l,a
    ld a,[hl]
    and e
    pop bc
    pop hl
    jr z,.next
    ld a,c
    ld [wInputMatch],a
    pop af
    ldh [rSVBK],a
    ret
.mismatch
    pop hl
    pop bc
    ld e,b
    ld d,$00
    add hl,de
    pop de
    jr .next
.notFound
    pop af
    ldh [rSVBK],a
    ret

ASSERT @ <= BlankNameTable
    ds BlankNameTable-@

BlankScrollNameTable::
    db $2F,$05,$80,$0A,$12,$33,$34,$3D,$43,$38,$35,$38,$34,$41 ; Identifier
    db $30,$06,$01,$07,$16,$30,$3F,$3F,$38,$3D,$36 ; Mapping
    db $31,$06,$02,$0A,$19,$3E,$43,$4D,$44,$3F,$42,$38,$49,$34 ; Pot-upsize
    db $32,$06,$04,$09,$20,$38,$3D,$33,$31,$3B,$30,$33,$34 ; Windblade
    db $33,$06,$08,$06,$16,$44,$49,$49,$3B,$34 ; Muzzle
    db $34,$06,$10,$09,$1C,$46,$38,$35,$43,$24,$0F,$3E,$34 ; Swift Foe
    db $35,$06,$20,$07,$1C,$3B,$44,$3C,$31,$34,$41 ; Slumber
    db $36,$06,$40,$08,$19,$3E,$46,$34,$41,$24,$1E,$3F ; Power Up
    db $37,$06,$80,$06,$0B,$3E,$3C,$31,$34,$41 ; Bomber
    db $38,$07,$01,$09,$20,$30,$3B,$3B,$4D,$3B,$34,$42,$42 ; Wall-less
    db $39,$07,$02,$07,$16,$3E,$3D,$42,$43,$34,$41 ; Monster
    db $3A,$07,$04,$09,$0C,$3E,$3D,$35,$44,$42,$38,$3E,$3D ; Confusion
    db $3B,$07,$08,$0B,$0E,$41,$30,$33,$38,$32,$30,$43,$38,$3E,$3D ; Eradication
    db $3C,$07,$10,$04,$0F,$34,$30,$41 ; Fear
    db $3D,$07,$20,$0A,$0E,$47,$43,$41,$30,$32,$43,$38,$3E,$3D ; Extraction
    db $3E,$07,$40,$09,$0C,$30,$41,$41,$48,$4D,$31,$30,$3D ; Carry-ban
    db $3F,$07,$80,$08,$0E,$47,$3E,$41,$32,$38,$42,$3C ; Exorcism
    db $40,$08,$01,$08,$11,$34,$30,$45,$34,$3D,$3B,$48 ; Heavenly
    db $41,$08,$02,$07,$0E,$30,$41,$43,$37,$3B,$48 ; Earthly
    db $42,$08,$04,$07,$19,$3B,$30,$43,$38,$3D,$36 ; Plating
    db $43,$08,$08,$06,$0E,$42,$32,$30,$3F,$34 ; Escape
    db $44,$08,$10,$04,$1D,$41,$30,$3F ; Trap
    db $46,$08,$40,$09,$1C,$30,$3D,$32,$43,$44,$30,$41,$48 ; Sanctuary
    db $47,$08,$80,$0A,$12,$3D,$30,$32,$32,$44,$41,$30,$43,$34 ; Inaccurate
    db $48,$09,$01,$0B,$1D,$41,$30,$3F,$4D,$34,$41,$30,$42,$34,$41 ; Trap-eraser
    db $49,$09,$02,$0A,$1C,$43,$44,$41,$33,$48,$24,$19,$3E,$43 ; Sturdy Pot
    db $4A,$09,$04,$07,$1B,$34,$42,$43,$3E,$32,$3A ; Restock
    db $4B,$09,$08,$0A,$0A,$43,$43,$41,$30,$32,$43,$38,$3E,$3D ; Attraction
    db $4C,$09,$10,$08,$0A,$3B,$43,$41,$44,$38,$42,$3C ; Altruism
    db $4D,$09,$20,$09,$0E,$47,$3F,$3B,$3E,$42,$38,$3E,$3D ; Explosion
    db $4E,$09,$40,$04,$0D,$30,$3C,$3F ; Damp
    db $50,$0A,$01,$0B,$1C,$40,$44,$38,$33,$24,$1C,$44,$42,$37,$38 ; Squid Sushi
    db $FF

ASSERT @ <= $4400
    ds $4400-@
