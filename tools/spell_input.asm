; Four-character English spell-entry screen for Shiren GB2.
;
; This source is assembled at ROM bank $FC:$4000.  tools/spell_input.py
; contains the generated resources and checked-in assembled code so normal
; builds do not require RGBDS.  The test suite reassembles this source when
; RGBDS is available and requires a byte-for-byte match.

DEF FarDispatch          EQU $09AC
DEF CopyLinearVRAM       EQU $0A6B
DEF CopyTilemap          EQU $0ACC
DEF ClearVRAMSpan        EQU $0A28
DEF rVBK                 EQU $FF4F

DEF EnglishKeyboardMap  EQU $4100
DEF EnglishGlyphsLow    EQU $4300
DEF EnglishGlyphsHigh   EQU $4600

SECTION "English spell input", ROMX[$4000], BANK[$FC]

SpellInputScreen::
    ; Reproduce the native mode-3 screen constructor through the point where
    ; it has uploaded the shared Japanese keyboard and attribute map.
    call $0831
    call $2560
    ld a,$03
    ld hl,$5EA7
    call FarDispatch
    ld a,$12
    ld hl,$4F59
    call FarDispatch
    ld a,$04
    ld hl,$49A4
    call FarDispatch

    ; Replace only the tile IDs and the two English code-page glyph spans.
    xor a
    ldh [rVBK],a
    ld hl,EnglishKeyboardMap
    ld de,$9840
    ld bc,$1014
    call CopyTilemap
    ld hl,EnglishGlyphsLow
    ld de,$9000
    ld bc,$0250
    call CopyLinearVRAM
    ld hl,EnglishGlyphsHigh
    ld de,$9300
    ld bc,$0280
    call CopyLinearVRAM

    ; Finish the native constructor: draw the current four-byte buffer, clear
    ; the cursor strip, commit VRAM, and return to the mode-3 controller.
    ld a,$04
    ld hl,$4D51
    call FarDispatch
    xor a
    ldh [rVBK],a
    ld hl,$97F0
    ld de,$00FF
    ld bc,$0008
    call ClearVRAMSpan
    call $0857
    ret

ASSERT @ <= EnglishKeyboardMap
