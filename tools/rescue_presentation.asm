; English presentation and input layer for Shiren GB2 Wanderer Rescue passwords.
;
; The packet codec, diary records, and Link Cable data remain native. Generated
; codes are mapped to the English font only while the dynamic-text cache reads
; them. Input modes 5-8 reuse the approved player-name keyboard resources, add
; ? and !, and translate each selected English node back to the corresponding
; native password symbol before the original validator runs.

DEF FarDispatch           EQU $09AC
DEF CopyTilemap           EQU $0ACC
DEF rVBK                  EQU $FF4F

DEF wNavigationType       EQU $C14E
DEF wInputMode            EQU $C195
DEF PasswordBuffer        EQU $C16D
DEF NavigationScratch     EQU $C800
DEF MaximumPasswordLength EQU 15
DEF NativeEmpty           EQU $D5

DEF Mode0Input            EQU $4000 ; bank $FA; delegates every non-mode-0 mode
DEF Name6ScreenClean      EQU $4232 ; bank $FD
DEF NativeInsert          EQU $524C ; bank $12, character in B
DEF NativeHardwareB       EQU $53B0 ; bank $12
DEF NativeInputRefresh    EQU $4D51 ; bank $04
DEF NativeScreen          EQU $4045 ; bank $F4

DEF RescueInputAddress           EQU $4100
DEF RescueScreenAddress          EQU $4160
DEF RefreshLocalizedInputAddress EQU $41B0
DEF UploadNavigationAddress      EQU $41C0
DEF NativeAlphabetCodesAddress   EQU $4200
DEF RescueHardwareBAddress       EQU $4260
DEF RescuePreModeScreenAddress   EQU $4280
DEF RescueNavigation             EQU $4300
DEF RescueKeyboardMap            EQU $4600

DEF FirstRescueMode       EQU 5
DEF LastRescueModePlusOne EQU 9
DEF RescueNavigationType  EQU $F5
DEF RescueCharacterCount  EQU 64
DEF OkNode                EQU $4D
DEF LeftNode              EQU $4E
DEF RightNode             EQU $4F
DEF DeleteNode            EQU $50

SECTION "Rescue password presentation", ROMX[$4000], BANK[$F9]

CacheLocalizedPassword::
    call LocalizePasswordBuffer
    ld bc,PasswordBuffer
    ld a,$03
    ld hl,$5B1B
    call FarDispatch
    call RestorePasswordBuffer
    ret

; Map a native password in place. $D5 is retained for input-screen empty cells;
; generated output never contains it, but sharing this bounded primitive keeps
; the display and editor contracts identical.
LocalizePasswordBuffer::
    ld hl,PasswordBuffer
    ld b,MaximumPasswordLength
.loop
    ld a,[hl]
    cp $FF
    ret z
    cp NativeEmpty
    jr z,.next
    cp $5E
    jr c,.low
    sub $39
    jr .mapped
.low
    sub $30
.mapped
    ld e,a
    ld d,$00
    push hl
    ld hl,EnglishAlphabetCodes
    add hl,de
    ld a,[hl]
    pop hl
    ld [hl],a
.next
    inc hl
    dec b
    jr nz,.loop
    ret

RestorePasswordBuffer::
    ld hl,PasswordBuffer
    ld b,MaximumPasswordLength
.loop
    ld a,[hl]
    cp $FF
    ret z
    cp NativeEmpty
    jr z,.next
    cp $0A
    jr c,.digit
    cp $24
    jr c,.uppercase
    cp $4A
    jr c,.lowercase
    sub $10
    jr .compact
.digit
    add $34
    jr .compact
.uppercase
    sub $0A
    jr .compact
.lowercase
    sub $16
.compact
    add $30
    cp $5E
    jr c,.store
    add $09
.store
    ld [hl],a
.next
    inc hl
    dec b
    jr nz,.loop
    ret

ASSERT @ <= $4080
    ds $4080-@

EnglishAlphabetCodes:
    ; A-Z, a-z, 0-9, ?, ! in the English VWF code page.
    db $0A,$0B,$0C,$0D,$0E,$0F,$10,$11,$12,$13,$14,$15,$16
    db $17,$18,$19,$1A,$1B,$1C,$1D,$1E,$1F,$20,$21,$22,$23
    db $30,$31,$32,$33,$34,$35,$36,$37,$38,$39,$3A,$3B,$3C
    db $3D,$3E,$3F,$40,$41,$42,$43,$44,$45,$46,$47,$48,$49
    db $00,$01,$02,$03,$04,$05,$06,$07,$08,$09,$4E,$4F

ASSERT @ <= RescueInputAddress
    ds RescueInputAddress-@

; Overlay the existing mode-0 -> Blank Scroll -> player-name input chain.
; Only rescue modes 5-8 are intercepted. Their 64 character nodes write native
; password values, while the proven editing controls retain native behavior.
RescueInput::
    ld a,[wInputMode]
    cp FirstRescueMode
    jr c,.shared
    cp LastRescueModePlusOne
    jr nc,.shared
    ld a,c
    cp RescueCharacterCount
    jr nc,.action
    ld b,$00
    ld hl,NativeAlphabetCodes
    add hl,bc
    ld b,[hl]
    ld a,$12
    ld hl,NativeInsert
    call FarDispatch
    call RefreshLocalizedInput
    ret
.action
    cp OkNode
    jr z,.sharedNoRefresh
    cp LeftNode
    jr z,.sharedAction
    cp RightNode
    jr z,.sharedAction
    cp DeleteNode
    ret nz
.sharedAction
    ld a,$FA
    ld hl,Mode0Input
    call FarDispatch
    call RefreshLocalizedInput
    ret
.sharedNoRefresh
    ld a,$FA
    ld hl,Mode0Input
    jp FarDispatch
.shared
    ld a,$FA
    ld hl,Mode0Input
    jp FarDispatch

ASSERT @ <= RescueScreenAddress
    ds RescueScreenAddress-@

; Keep every non-rescue graphical editor on its original constructor. Rescue
; modes reuse the reviewed name-entry glyph upload, then install their own map
; and private WRAM navigation graph.
RescueScreen::
    ; The graphical-input caller carries the requested mode in C. Do not trust
    ; wInputMode here: a retained-password visit can still contain whichever
    ; editor ran previously until this constructor publishes the new mode.
    ld a,c
    cp FirstRescueMode
    jr c,.native
    cp LastRescueModePlusOne
    jr nc,.native
    ld [wInputMode],a
    push bc
    ld a,$FD
    ld hl,Name6ScreenClean
    call FarDispatch
    call UploadNavigation
    xor a
    ldh [rVBK],a
    ld hl,RescueKeyboardMap
    ld de,$9840
    ld bc,$1014
    call CopyTilemap
    xor a
    ldh [rVBK],a
    call RefreshLocalizedInput
    pop bc
    ret
.native
    ld a,$F4
    ld hl,NativeScreen
    jp FarDispatch

ASSERT @ <= RefreshLocalizedInputAddress
    ds RefreshLocalizedInputAddress-@

RefreshLocalizedInput::
    call LocalizePasswordBuffer
    ld a,$04
    ld hl,NativeInputRefresh
    call FarDispatch
    call RestorePasswordBuffer
    ret

ASSERT @ <= UploadNavigationAddress
    ds UploadNavigationAddress-@

UploadNavigation::
    ld hl,RescueNavigation
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
    ld a,RescueNavigationType
    ld [wNavigationType],a
    ret

ASSERT @ <= NativeAlphabetCodesAddress
    ds NativeAlphabetCodesAddress-@

NativeAlphabetCodes:
    ; Native 64-symbol display codes in six-bit value order.
    db $30,$31,$32,$33,$34,$35,$36,$37,$38,$39,$3A,$3B,$3C,$3D,$3E,$3F
    db $40,$41,$42,$43,$44,$45,$46,$47,$48,$49,$4A,$4B,$4C,$4D,$4E,$4F
    db $50,$51,$52,$53,$54,$55,$56,$57,$58,$59,$5A,$5B,$5C,$5D
    db $67,$68,$69,$6A,$6B,$6C,$6D,$6E,$6F,$70,$71,$72,$73,$74,$75,$76,$77,$78

ASSERT @ <= RescueHardwareBAddress
    ds RescueHardwareBAddress-@

; Hardware B has a dedicated native table handler. Run that deletion first,
; then refresh only an active Rescue editor so the remaining native password
; symbols are presented through the English mapping. The rest of the native
; handler, including its empty-field result and $FF return value, stays intact.
RescueHardwareB::
    ld a,$12
    ld hl,NativeHardwareB
    call FarDispatch
    ld a,[wInputMode]
    cp FirstRescueMode
    jr c,.done
    cp LastRescueModePlusOne
    jr nc,.done
    ld a,[wNavigationType]
    cp RescueNavigationType
    jr nz,.done
    call RefreshLocalizedInput
.done
    ret

ASSERT @ <= RescuePreModeScreenAddress
    ds RescuePreModeScreenAddress-@

; Some rescue routes call the shared constructor before copying C into
; wInputMode. Guard those by the incoming mode in C instead. This covers the
; requester-side Revival path without altering the common input loop or any
; non-rescue constructor user.
RescuePreModeScreen::
    ld a,c
    cp FirstRescueMode
    jr c,.native
    cp LastRescueModePlusOne
    jr nc,.native
    ; This call site precedes the native `ld [wInputMode],c`. Publish the
    ; incoming mode before constructing the shared English screen so its
    ; initialization and the first input tick agree about the active editor.
    ld [wInputMode],a
    push bc
    ld a,$FD
    ld hl,Name6ScreenClean
    call FarDispatch
    call UploadNavigation
    pop bc
    ret
.native
    ld a,$F4
    ld hl,NativeScreen
    jp FarDispatch

RescuePresentationCodeEnd::
