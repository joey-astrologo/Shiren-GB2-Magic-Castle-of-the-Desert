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
DEF NativeInputAction    EQU $5215 ; bank $12
DEF NativeConfirm        EQU $50F7 ; bank $12
DEF NativeScreenRefresh  EQU $4D51 ; bank $04
DEF NativeInputPlacement EQU $4D6F ; bank $04
DEF NativeInputDraw      EQU $46C2 ; bank $11
DEF NativeCustomSlotWrapper EQU $7E98 ; bank $78 local trampoline
DEF RenderRecord         EQU $1FA0 ; fixed bank

DEF rSVBK                EQU $FF70

DEF IdentificationSlots EQU $DC83 ; second byte of each root pair, WRAM bank 2
DEF CustomNames          EQU $DD78 ; 20 slots x eight bytes, WRAM bank 2
DEF CanonicalPrefix      EQU $FF
DEF CanonicalMarker      EQU $FE
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
; native seven-byte slot. A successful Fill In result has wInputMatch set to
; its canonical root; replace the stored prefix with a compact root token.
Mode0Confirm::
    ld a,[wInputMode]
    and a
    jr z,.mode0
    ld a,$FB
    ld hl,BlankScrollConfirm
    jp FarDispatch
.mode0
    ; A recalled root can occupy 14 presentation cells, but NativeConfirm
    ; still writes an eight-byte custom-name slot. Terminate the temporary
    ; field at the native boundary after wInputMatch has retained the root.
    call RestoreNativeTail
    ld a,$12
    ld hl,NativeConfirm
    call FarDispatch
    ld a,c
    cp $F8
    ret nz
    ld a,[wInputMatch]
    inc a
    ret z
    dec a
    push bc
    ld b,a
    ldh a,[rSVBK]
    push af
    ld a,$02
    ldh [rSVBK],a
    ld a,b
    ld l,a
    ld h,$00
    add hl,hl
    ld de,IdentificationSlots
    add hl,de
    ld a,[hl]
    cp $FF
    jr z,.restore
    add a,a
    add a,a
    add a,a
    ld l,a
    ld h,$00
    ld de,CustomNames
    add hl,de
    ; Prefix the token with a native terminator. This makes the signature
    ; impossible for any old nonempty Japanese custom label; an old empty
    ; label has an all-$FF tail and therefore cannot match the $FE marker.
    ld a,CanonicalPrefix
    ld [hl+],a
    ld a,CanonicalMarker
    ld [hl+],a
    ld a,b
    ld [hl+],a
    ld a,$FF
    ld b,$05
.clearTail
    ld [hl+],a
    dec b
    jr nz,.clearTail
.restore
    pop af
    ldh [rSVBK],a
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
    ret nz
    inc hl
    ld a,[hl]
    cp CanonicalMarker
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

ASSERT @ <= Mode0Navigation
    ds Mode0Navigation-@
