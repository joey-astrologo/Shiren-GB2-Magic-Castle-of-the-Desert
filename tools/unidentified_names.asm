; English mode-0 unidentified-item naming screen.
;
; This source is assembled at ROM bank $FA:$4000. The generated keyboard and
; navigation resources are placed by tools/unidentified_names.py.

DEF FarDispatch          EQU $09AC
DEF CopyInputText        EQU $0A5B
DEF CopyTilemap          EQU $0ACC
DEF rVBK                 EQU $FF4F

DEF wNavigationType      EQU $C14E
DEF wInputPosition       EQU $C152
DEF wInputMaximum        EQU $C153
DEF wInputMode           EQU $C195
DEF wInputMatch          EQU $C196
DEF NavigationScratch    EQU $C800

DEF Name6ScreenClean     EQU $4232 ; bank $FD
DEF BlankScrollInput     EQU $4020 ; bank $FB; delegates non-mode-1 to name6
DEF BlankScrollConfirm   EQU $4080 ; bank $FB; delegates non-mode-1 to native
DEF BlankStartRecall     EQU $4320 ; bank $FB; bounded mode-1 prefix
DEF NativeInputAction    EQU $5215 ; bank $12
DEF NativeStartRecall    EQU $5073 ; bank $12
DEF NativeConfirm        EQU $50F7 ; bank $12
DEF NativeScreenRefresh  EQU $4D51 ; bank $04
DEF NativeInputPlacement EQU $4D6F ; bank $04
DEF NativeInputDraw      EQU $46C2 ; bank $11
DEF NativeCustomSlotWrapper EQU $7E98 ; bank $78 local trampoline
DEF RenderRecord         EQU $1FA0 ; fixed bank

DEF rSVBK                EQU $FF70

DEF CanonicalPrefix      EQU $FE
DEF CanonicalMarker      EQU $FE
DEF PreviousCanonicalMarker EQU $FF
DEF LegacyCanonicalPrefix EQU $FF
DEF LegacyCanonicalMarker EQU $FE
DEF FreeNameMaximum      EQU 7
DEF FillInMaximum        EQU 14
DEF NativeEmpty          EQU $D5
DEF PresentationBlank    EQU $24

DEF Mode0Navigation      EQU $4240
DEF Mode0KeyboardMap     EQU $4480
; $13 is the live nine-row list used by the title-screen Adventure submenu.
; $F4 resolves through 16:$615C, the first two bytes of unreachable node 64
; in the English name-entry graph. unidentified_names.py replaces only that
; dead pair with the WRAM navigation pointer $C800.
DEF Mode0NavigationType  EQU $F4
DEF FillInNode           EQU $4C
DEF DeleteNode           EQU $50

SECTION "Unidentified item naming", ROMX[$4000], BANK[$FA]

; Replacement for the shared graphical-input hook at 16:$5B66 after the
; Blank Scroll overlay. Every non-mode-0 input remains byte-for-byte on that
; existing route. Mode 0 intercepts only the restored Fill In node; its other
; character and editing nodes use the English shared input path.
Mode0Input::
    ld a,[wInputMode]
    and a
    jp nz,.shared
    ld a,c
    cp FillInNode
    jr z,.fillIn
    cp DeleteNode
    jp z,.delete
    ; Character and SPACE insertion temporarily retain the native seven-byte
    ; persistence limit. If a canonical preview is active, typing begins a
    ; fresh free label and the typed character becomes its first character.
    cp $4D
    jp nc,.shared
    ld a,[wInputMatch]
    inc a
    jr z,.freeCharacter
    push bc
    call ResetFreeField
    pop bc
    ; The ordinary seven-cell insertion performs the only redraw in this
    ; input frame. ResetFreeField has already blanked the complete safe tail,
    ; so this first glyph replaces the canonical preview atomically.
.freeCharacter
    ; Recover an out-of-range cursor from an older editor state as well as
    ; preventing insertion beyond the native persistent field.
    ld a,[wInputPosition]
    cp FreeNameMaximum
    jr c,.boundedCursor
    ld a,FreeNameMaximum-1
    ld [wInputPosition],a
.boundedCursor
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    ld a,$FB
    ld hl,BlankScrollInput
    call FarDispatch
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    call RestoreNativeTail
    ret
.fillIn
    ; Keep the native recall routine on its seven-byte scratch contract while
    ; it advances the history-filtered root ID in wInputMatch.
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    ld a,$12
    ld hl,NativeInputAction
    call FarDispatch
.expandRecall
    push bc
    ld a,[wInputMatch]
    inc a
    jr z,.noCandidate
    dec a
    ld c,a
    ; Expand the selected translated root directly into the larger, safe
    ; presentation buffer. RenderRecord returns its byte length in C.
    ld hl,$C16D
    ld a,$0C
    call RenderRecord
    ; wInputPosition is the zero-based cursor cell, not the string length.
    ld a,c
    dec a
    ld [wInputPosition],a
    ; Keep the 14-cell preview visually blank after the canonical root. The
    ; native $D5 empty-cell glyph is an asterisk, so padding it here would
    ; display the unwanted trailing stars reported by playtesting.
    ld hl,$C16D
    ld b,$00
    add hl,bc
    ld a,FillInMaximum
    sub c
    ld b,a
    jr z,.tailDone
    ld a,PresentationBlank
.blankTail
    ld [hl+],a
    dec b
    jr nz,.blankTail
.tailDone
    ld a,$FF
    ld [hl],a
    ld a,FillInMaximum
    ld [wInputMaximum],a
    call AlignedPresentationRefresh
.restoreNavigation
    ; The native Fill In recall may use the ordinary $C800 staging area while
    ; cycling its history. Reinstall this mode's navigation graph before
    ; control returns to the keyboard.
    call UploadMode0Navigation
    pop bc
    ret
.delete
    ; DEL on a canonical preview means "return to free naming", not "edit a
    ; 14-cell string". That transition also prevents the native cursor from
    ; walking beyond its seven-byte persistent field.
    ld a,[wInputMatch]
    inc a
    jr z,.shared
    call ResetFreeField
    ret
.noCandidate
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    jr .restoreNavigation
.shared
    ld a,$FB
    ld hl,BlankScrollInput
    jp FarDispatch

ASSERT @ <= $40C0
    ds $40C0-@

; Wrapper for all three mode-0 call sites (inventory, shop/item context, and
; At Feet). Name6ScreenClean retains the native constructor, maximum, buffer,
; attributes, and English glyph upload. We replace the tile IDs and select a
; separate navigation graph with an active Fill In control.
Mode0Screen::
    ld a,$FD
    ld hl,Name6ScreenClean
    call FarDispatch
    call UploadMode0Navigation
    xor a
    ldh [rVBK],a
    ld hl,Mode0KeyboardMap
    ld de,$9840
    ld bc,$1014
    call CopyTilemap
    xor a
    ldh [rVBK],a
    ret

UploadMode0Navigation:
    ld hl,Mode0Navigation
    ld de,NavigationScratch
    ld bc,$0237 ; 81 records * seven bytes
.copy
    ld a,[hl+]
    ld [de],a
    inc de
    dec bc
    ld a,b
    or c
    jr nz,.copy
    ld a,Mode0NavigationType
    ld [wNavigationType],a
    ret

ASSERT @ <= $4100
    ds $4100-@

; Overlay the shared confirmation hook. Arbitrary mode-0 names retain the
; native seven-byte slot. A Fill In result has wInputMatch set to its canonical
; root, so give NativeConfirm a compact token instead of its 14-cell preview.
; NativeConfirm then writes the same token to both the WRAM slot and its SRAM
; journal entry. An internal $FF marker cannot be used here: the save journal
; is variable-length and would persist only the leading $FE byte.
Mode0Confirm::
    ld a,[wInputMode]
    and a
    jr z,.mode0
    ld a,$FB
    ld hl,BlankScrollConfirm
    jp FarDispatch
.mode0
    ld a,[wInputMatch]
    inc a
    jr z,.freeName
    dec a
    ld b,a
    ld hl,$C16D
    ld a,CanonicalPrefix
    ld [hl+],a
    ld a,CanonicalMarker
    ld [hl+],a
    ld a,b
    ld [hl+],a
    ld a,$FF
    ld b,$05
.tokenTail
    ld [hl+],a
    dec b
    jr nz,.tokenTail
    jr .native
.freeName
    call RestoreNativeTail
.native
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    ld a,$12
    ld hl,NativeConfirm
    call FarDispatch
    ld a,c
    cp $F8
    ret z
    ; A rejected confirmation leaves the editor open. Re-expand the selected
    ; root because its presentation buffer was temporarily replaced above.
    push bc
    call Mode0Input.expandRecall
    pop bc
    ret

ASSERT @ <= $4160
    ds $4160-@

RestoreNativeTail:
    ld a,$FF
    ld [$C174],a
    ld a,$D5
    ld hl,$C175
    ld b,FillInMaximum-FreeNameMaximum-1
.tail
    ld [hl+],a
    dec b
    jr nz,.tail
    ret

ASSERT @ <= $4180
    ds $4180-@

; Called only by the custom-name display path through the same-bank trampoline
; at 78:$7E90. Ordinary slots return their native WRAM pointer. Canonical
; tokens are rendered from the translated group-12 root table directly into
; the caller's destination. We then return the token's own terminator and move
; DE to the rendered end, so the caller's normal copy writes only that final
; terminator. No live WRAM input/controller field is borrowed as scratch.
ResolveCustomName::
    ld a,$78
    ld hl,NativeCustomSlotWrapper
    call FarDispatch
    ld a,[hl]
    cp CanonicalPrefix
    jr z,.current
    ; Decode the original $FF $FE token so existing English saves remain
    ; readable even though new tokens must begin with an occupied byte.
    cp LegacyCanonicalPrefix
    ret nz
    inc hl
    ld a,[hl]
    cp LegacyCanonicalMarker
    jr z,.canonical
    dec hl
    ret
.current
    inc hl
    ld a,[hl]
    cp CanonicalMarker
    jr z,.canonical
    ; Compatibility with the first English long-name build. Its internal $FF
    ; marker works in live WRAM but is truncated by the native save journal.
    cp PreviousCanonicalMarker
    jr z,.canonical
    dec hl
    ret
.canonical
    inc hl
    ld c,[hl]
    ld a,c
    cp 123
    jr c,.validRoot
    dec hl
    dec hl
    ret
.validRoot
    inc hl
    push hl
    push de
    ld h,d
    ld l,e
    ld a,$0C
    call RenderRecord
    pop hl
    add hl,bc
    ld d,h
    ld e,l
    ld a,$02
    ldh [rSVBK],a
    pop hl
    ret

; Leave a canonical preview and rebuild the native seven-cell free-label
; state. Character insertion (C < $4D) uses its own seven-cell redraw, avoiding
; two refreshes in one input frame.
; DEL (C = $50) redraws here because no insertion follows it. Both paths then
; restore the seven-cell persistence contract.
ResetFreeField:
    xor a
    ld [wInputPosition],a
    ld a,$FF
    ld [wInputMatch],a
    ld hl,$C16D
    ld b,FreeNameMaximum
    ld a,NativeEmpty
.stars
    ld [hl+],a
    dec b
    jr nz,.stars
    ld b,FillInMaximum-FreeNameMaximum
    ld a,PresentationBlank
.blanks
    ld [hl+],a
    dec b
    jr nz,.blanks
    ld a,$FF
    ld [hl],a
    ld [$C174],a
    ld a,c
    cp DeleteNode
    ret nz
RefreshFreeField:
    call AlignedPresentationRefresh
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    call RestoreNativeTail
    ret

; The native refresh uses wInputMaximum for two unrelated jobs: how many
; bytes to copy and where to place the rendered field. A fourteen-cell Fill In
; preview therefore drifted left even when its visible name was short. Copy
; all fourteen safe presentation cells, but ask the native placement helper
; for the original seven-cell origin before drawing the complete copied text.
; Canonical roots and the restored seven-star free field now share one left
; edge while long translated roots retain their full display capacity.
AlignedPresentationRefresh:
    ld de,$FFB0
    ld hl,$C16D
    ld b,FillInMaximum
    ld a,$04
    call CopyInputText
    ld a,$FF
    ld [de],a
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    ld a,$04
    ld hl,NativeInputPlacement
    call FarDispatch
    ld a,FillInMaximum
    ld [wInputMaximum],a
    ld a,$11
    ld hl,NativeInputDraw
    jp FarDispatch

ASSERT @ <= $4220
    ds $4220-@

; The shared editor controller handles START before dispatching the selected
; grid node, so it bypasses Mode0Input. Delegate other modes through the Blank
; Scroll wrapper; mode 0 runs the native history selection at its required
; seven-cell limit and then reuses the same full canonical-preview finisher as
; the visible FILL IN control. The controller consumes C after this call, so
; retain the native routine's return value across rendering and navigation
; restoration.
Mode0StartRecall::
    ld a,[wInputMode]
    and a
    jr z,.mode0
    ld a,$FB
    ld hl,BlankStartRecall
    jp FarDispatch
.mode0
    ld a,FreeNameMaximum
    ld [wInputMaximum],a
    ld a,$12
    ld hl,NativeStartRecall
    call FarDispatch
    jp Mode0Input.expandRecall

ASSERT @ <= Mode0Navigation
    ds Mode0Navigation-@

SECTION "Unidentified hardware B", ROMX[$45C0], BANK[$FA]

; Hardware B bypasses the keyboard node dispatcher. Clear a canonical preview
; before native deletion can retain a cursor beyond seven cells. The event
; handler has already cleared wInputMatch, so the 14-cell maximum identifies
; the preview here. Ordinary free labels and every other input mode
; keep their native single-character deletion behavior.
Mode0HardwareB::
    ld a,[wInputMode]
    and a
    jr nz,.native
    ld a,[wNavigationType]
    cp Mode0NavigationType
    jr nz,.native
    ld a,[wInputMaximum]
    cp FillInMaximum
    jr nz,.native
    ld c,DeleteNode
    call ResetFreeField
    ; Match the native handler's caret redraw after moving to cell zero.
    ld c,0
    ld a,$10
    ld hl,$5EE8
    jp FarDispatch
.native
    ld a,$12
    ld hl,$53B0
    jp FarDispatch

ASSERT @ <= $4600
    ds $4600-@
