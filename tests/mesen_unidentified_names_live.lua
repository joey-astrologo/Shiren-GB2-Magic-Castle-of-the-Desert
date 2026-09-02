-- Regression route for the user-reported unidentified-item naming failure.
--
-- The Python test freezes the exact supplied failure state. This live route
-- recreates its Rabbit Scroll and history conditions from the clean Mamel state
-- so Mesen can test the real menus without the supplied state's debugger-only
-- uninitialized-memory metadata flooding the test runner.

local frame = 0
local loaded = false
local reopenedFrame = nil
local fillInFrame = nil
local previewChecked = false
local alignedPreviewOriginSeen = false
local alignedResetOriginSeen = false
local tokenFrame = nil
local resolvedFrame = nil
local resetFrame = nil
local exitFrame = nil
local activeButton = nil
local lastMode = nil
local lastNode = nil
local lastNav = nil
local lastActionFlags = nil

local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local IDENTIFICATION = 0x2C82
local HISTORY = 0x2E1C
local WINDBLADE_ID = 0x7F
local WINDBLADE_ROOT = 50
local WINDBLADE_CODES = { 0x20, 0x38, 0x3D, 0x33, 0x31, 0x3B, 0x30, 0x33, 0x34 }
local APPEARANCE = 50
local TEST_ROUTE = os.getenv("GB2_UNIDENTIFIED_ROUTE") or "confirm"
local LOCALIZED_FILL_IN_CHECKSUM = 0x4D3AA93B
local LOCALIZED_TYPE_RESET_CHECKSUM = 0x1D46725B
local LOCALIZED_DELETE_RESET_CHECKSUM = 0x52CC5419
local LOCALIZED_ITEMS_SCREEN_CHECKSUM = 0xAC438159

assert(
  TEST_ROUTE == "confirm" or TEST_ROUTE == "type" or TEST_ROUTE == "delete",
  "unknown unidentified-name test route: " .. TEST_ROUTE
)

local function report(message)
  print(message)
  emu.log(message)
end

local function screenChecksum()
  local hash = 2166136261
  for _, pixel in ipairs(emu.getScreenBuffer()) do
    hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
  end
  return hash
end

local function rd(address)
  return emu.read(address, cpuMem)
end

local function workRead(address)
  return emu.read(address, workMem)
end

local function workWrite(address, value)
  emu.write(address, value, workMem)
  assert(workRead(address) == value)
end

local function injectRabbitScroll()
  assert(workMem ~= nil, "Mesen does not expose flat Game Boy Work RAM")
  local occupied = {}
  local freeSlot = nil
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object = workRead(INVENTORY + slot)
    if object == 0xFF then
      freeSlot = slot
      break
    end
    occupied[object] = true
  end
  assert(freeSlot ~= nil, "fixture inventory is full")

  local freeObject = nil
  for object = 0, OBJECT_COUNT - 1 do
    if not occupied[object] then
      local empty = true
      for offset = 0, OBJECT_SIZE - 1 do
        if workRead(OBJECTS + object * OBJECT_SIZE + offset) ~= 0 then
          empty = false
          break
        end
      end
      if empty then
        freeObject = object
        break
      end
    end
  end
  assert(freeObject ~= nil, "fixture object pool is full")

  local record = { WINDBLADE_ID, 7, 0, 0, 0, 0, 0xFF, 0 }
  for offset, value in ipairs(record) do
    workWrite(OBJECTS + freeObject * OBJECT_SIZE + offset - 1, value)
  end
  workWrite(INVENTORY + freeSlot, freeObject)
  workWrite(IDENTIFICATION + WINDBLADE_ROOT * 2, APPEARANCE)
  workWrite(IDENTIFICATION + WINDBLADE_ROOT * 2 + 1, 0xFF)
  local historyAt = HISTORY + math.floor(WINDBLADE_ROOT / 8)
  workWrite(
    historyAt,
    workRead(historyAt) | (1 << (WINDBLADE_ROOT & 7))
  )
  emu.write(0xC12B, rd(0xC12B) & 0xFD, cpuMem)
  assert((rd(0xC12B) & 0x02) == 0)
  report(string.format(
    "Rabbit Scroll injected slot=%d object=%d", freeSlot, freeObject
  ))
end

local function loadOnce()
  if loaded then return end
  loaded = true
  local file = assert(io.open(assert(os.getenv("GB2_MSS_PATH")), "rb"))
  local state = file:read("*all")
  file:close()
  emu.loadSavestate(state)
  injectRabbitScroll()
  report("clean unidentified-name fixture loaded")
end

local function pressAt(input, at, button)
  if frame >= at and frame < at + 5 then
    activeButton = button
    input[button] = true
  end
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a = false, b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
  activeButton = nil

  -- Close the existing item message, open Items, choose the injected second
  -- item, and select Name from its action menu.
  pressAt(input, 120, "b")
  pressAt(input, 220, "a")
  pressAt(input, 320, "down")
  pressAt(input, 520, "a")
  pressAt(input, 620, "down")
  pressAt(input, 680, "down")
  pressAt(input, 740, "down")
  pressAt(input, 840, "a")

  if reopenedFrame ~= nil and fillInFrame == nil then
    -- From A: Up -> left-caret, Right -> right-caret, Up -> Fill In.
    local route = { "up", "right", "up", "a" }
    local elapsed = frame - reopenedFrame - 45
    if elapsed >= 0 then
      local index = math.floor(elapsed / 20) + 1
      local phase = elapsed % 20
      if index <= #route and phase < 5 then
        activeButton = route[index]
        input[route[index]] = true
      end
    end
  elseif fillInFrame ~= nil and tokenFrame == nil and resetFrame == nil then
    if TEST_ROUTE == "confirm" then
      -- Fill In returns to the keyboard with its canonical choice selected.
      -- Move once to OK and confirm so the native-slot token route runs.
      pressAt(input, fillInFrame + 90, "right")
      pressAt(input, fillInFrame + 150, "a")
    elseif TEST_ROUTE == "type" then
      -- Walk from Fill In through the lower character rows to T, then type it.
      -- The first character must atomically replace the canonical preview.
      pressAt(input, fillInFrame + 90, "up")
      pressAt(input, fillInFrame + 110, "left")
      pressAt(input, fillInFrame + 130, "up")
      pressAt(input, fillInFrame + 160, "a")
    elseif TEST_ROUTE == "delete" then
      -- Fill In -> OK -> DEL, then activate DEL. Deleting a canonical preview
      -- must restore the initial empty free-entry state in one action.
      pressAt(input, fillInFrame + 90, "right")
      pressAt(input, fillInFrame + 110, "down")
      pressAt(input, fillInFrame + 160, "a")
    end
  elseif resetFrame ~= nil and exitFrame == nil then
    -- Prove the reset field is not a trap by completing an ordinary free-name
    -- route through OK. The type route already contains T. The delete route
    -- first walks DEL -> right caret -> left caret -> A and types A.
    if TEST_ROUTE == "type" then
      pressAt(input, resetFrame + 60, "down")
      pressAt(input, resetFrame + 80, "down")
      pressAt(input, resetFrame + 100, "right")
      pressAt(input, resetFrame + 120, "right")
      pressAt(input, resetFrame + 160, "a")
    else
      pressAt(input, resetFrame + 60, "left")
      pressAt(input, resetFrame + 80, "left")
      pressAt(input, resetFrame + 100, "down")
      pressAt(input, resetFrame + 120, "a")
      pressAt(input, resetFrame + 160, "up")
      pressAt(input, resetFrame + 180, "left")
      pressAt(input, resetFrame + 200, "up")
      pressAt(input, resetFrame + 240, "a")
    end
  end
  emu.setInput(input, 0)
end

local function afterFrame()
  if loaded then
    if frame < 260 then
      emu.write(0xC12B, rd(0xC12B) & 0xFD, cpuMem)
    end
    local mode = rd(0xC195)
    local node = rd(0xC14F)
    local nav = rd(0xC14E)
    local actionFlags = rd(0xC12B)
    if mode ~= lastMode or node ~= lastNode or nav ~= lastNav
        or actionFlags ~= lastActionFlags then
      report(string.format(
        "frame=%d mode=%02X node=%02X nav=%02X flags=%02X input=%s",
        frame, mode, node, nav, actionFlags, tostring(activeButton)
      ))
      lastMode = mode
      lastNode = node
      lastNav = nav
      lastActionFlags = actionFlags
    end
  end

  local actionScreenshot = os.getenv("GB2_ACTION_SCREENSHOT")
  if actionScreenshot ~= nil and frame == 580 then
    local file = assert(io.open(actionScreenshot, "wb"))
    file:write(emu.takeScreenshot())
    file:close()
    emu.stop(0)
    return
  end

  if fillInFrame ~= nil and not previewChecked
      and frame >= fillInFrame + 60 then
    local previewBytes = {}
    for offset = 0, #WINDBLADE_CODES do
      table.insert(previewBytes, string.format("%02X", rd(0xC16D + offset)))
    end
    report(string.format(
      "Fill In preview frame=%d max=%02X pos=%02X bytes=%s screen=%08X",
      frame, rd(0xC153), rd(0xC152), table.concat(previewBytes, " "),
      screenChecksum()
    ))
    assert(rd(0xC153) == 14, "Fill In did not expand to fourteen cells")
    assert(
      rd(0xC152) == #WINDBLADE_CODES - 1,
      "full Windblade cursor position was not retained"
    )
    for offset, value in ipairs(WINDBLADE_CODES) do
      assert(
        rd(0xC16D + offset - 1) == value,
        string.format("Windblade preview differs at byte %d", offset)
      )
    end
    assert(
      rd(0xC16D + #WINDBLADE_CODES) == 0x24,
      "Windblade preview is not followed by a blank presentation cell"
    )
    assert(
      rd(0xC16D + 14) == 0xFF,
      "fourteen-cell Fill In field is not terminated"
    )
    assert(
      alignedPreviewOriginSeen,
      "Fill In preview did not use the native seven-cell screen origin"
    )
    if LOCALIZED_FILL_IN_CHECKSUM ~= 0 then
      assert(
        screenChecksum() == LOCALIZED_FILL_IN_CHECKSUM,
        "full Windblade Fill In preview changed visually"
      )
    end
    previewChecked = true
    report("full Windblade Fill In preview retained in fourteen-cell field")
    local previewScreenshot = os.getenv("GB2_FILLIN_SCREENSHOT")
    if previewScreenshot ~= nil then
      local file = assert(io.open(previewScreenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
  end

  if TEST_ROUTE ~= "confirm" and previewChecked and resetFrame == nil
      and frame >= fillInFrame + 190 then
    assert(rd(0xC196) == 0xFF, "canonical match survived the edit reset")
    assert(rd(0xC153) == 7, "edit reset did not restore the seven-cell maximum")
    if TEST_ROUTE == "type" then
      assert(rd(0xC16D) == 0x1D, "typed T was not retained as the first glyph")
      for offset = 1, 6 do
        assert(rd(0xC16D + offset) == 0xD5, "typed field lost an empty cell")
      end
    else
      assert(
        alignedResetOriginSeen,
        "DEL reset did not use the native seven-cell screen origin"
      )
      assert(rd(0xC152) == 0, "DEL reset did not restore the initial cursor")
      for offset = 0, 6 do
        assert(rd(0xC16D + offset) == 0xD5, "DEL reset lost an empty cell")
      end
    end
    assert(rd(0xC174) == 0xFF, "free-entry field is not terminated at seven")
    for offset = 8, 13 do
      assert(
        rd(0xC16D + offset) == 0xD5,
        "presentation tail was not restored to native filler bytes"
      )
    end
    local resetChecksum = screenChecksum()
    local expectedChecksum = TEST_ROUTE == "type"
      and LOCALIZED_TYPE_RESET_CHECKSUM or LOCALIZED_DELETE_RESET_CHECKSUM
    if expectedChecksum ~= 0 then
      assert(
        resetChecksum == expectedChecksum,
        string.format("%s reset screen changed: %08X", TEST_ROUTE, resetChecksum)
      )
    end
    resetFrame = frame
    report(string.format(
      "%s-after-fill reset frame=%d pos=%02X max=%02X screen=%08X",
      TEST_ROUTE, frame, rd(0xC152), rd(0xC153), resetChecksum
    ))
    local resetScreenshot = os.getenv("GB2_RESET_SCREENSHOT")
    if resetScreenshot ~= nil then
      local file = assert(io.open(resetScreenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
  end

  if TEST_ROUTE == "confirm" and loaded and tokenFrame == nil then
    local slot = workRead(IDENTIFICATION + WINDBLADE_ROOT * 2 + 1)
    if slot ~= 0xFF then
      local custom = 0x2D78 + slot * 8
      assert(workRead(custom) == 0xFE, "canonical custom-name prefix is absent")
      assert(
        workRead(custom + 1) == 0xFF,
        "canonical custom-name marker is absent"
      )
      assert(
        workRead(custom + 2) == WINDBLADE_ROOT,
        "canonical custom-name token has the wrong root"
      )
      assert(
        workRead(custom + 3) == 0xFF,
        "canonical custom-name token is not terminated"
      )
      tokenFrame = frame
      report(string.format(
        "canonical token stored at frame %d slot=%d", frame, slot
      ))
    end
  end

  if TEST_ROUTE ~= "confirm" and resetFrame ~= nil and exitFrame == nil
      and frame >= resetFrame + 180 and rd(0xC14E) ~= 0x13 then
    exitFrame = frame
    report(string.format(
      "PASS route=%s reset-frame=%d exit-frame=%d node=%02X nav=%02X",
      TEST_ROUTE, resetFrame, exitFrame, rd(0xC14F), rd(0xC14E)
    ))
    emu.stop(0)
  elseif TEST_ROUTE ~= "confirm" and resetFrame ~= nil
      and frame >= resetFrame + 360 then
    error(TEST_ROUTE .. " reset remained trapped in the naming screen")
  elseif TEST_ROUTE == "confirm" and tokenFrame ~= nil and frame >= tokenFrame + 240 then
    assert(resolvedFrame ~= nil, "canonical token was not expanded for display")
    assert(rd(0xC195) == 0x00, "mode-0 confirmation corrupted the menu state")
    assert(rd(0xC14E) == 0x01, "mode-0 confirmation did not return to Items")
    local checksum = screenChecksum()
    if LOCALIZED_ITEMS_SCREEN_CHECKSUM ~= 0 then
      assert(
        checksum == LOCALIZED_ITEMS_SCREEN_CHECKSUM,
        string.format("canonical name screen changed: %08X", checksum)
      )
    end
    report(string.format(
      "PASS mode=%02X node=%02X nav=%02X maximum=%02X " ..
      "fill-frame=%d token-frame=%d resolved-frame=%d screen=%08X",
      rd(0xC195), rd(0xC14F), rd(0xC14E), rd(0xC153),
      fillInFrame, tokenFrame, resolvedFrame, checksum
    ))
    local screenshot = os.getenv("GB2_SCREENSHOT")
    if screenshot ~= nil then
      local file = assert(io.open(screenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    emu.stop(0)
  elseif frame >= 1800 then
    error("timed out before opening the Fill In history cycle")
  end
  frame = frame + 1
end

local function traceScreen()
  local state = emu.getState()
  if loaded and state["cart.prgBank"] == 0xFA then
    reopenedFrame = frame
    report("localized mode-0 constructor reached at frame " .. frame)
  end
end

local function traceFillIn()
  local state = emu.getState()
  if loaded and state["cart.prgBank"] == 0x12 then
    fillInFrame = frame
    report("native Fill In cycle reached at frame " .. frame)
  end
end

local function traceResolve()
  local state = emu.getState()
  if loaded and state["cart.prgBank"] == 0xFA then
    resolvedFrame = frame
    report(string.format(
      "canonical token resolver reached at frame %d bc=%02X%02X de=%02X%02X hl=%02X%02X sp=%04X",
      frame, state["cpu.b"], state["cpu.c"], state["cpu.d"], state["cpu.e"],
      state["cpu.h"], state["cpu.l"], state["cpu.sp"]
    ))
  end
end

local function traceResolveReturn()
  local state = emu.getState()
  if loaded and state["cart.prgBank"] == 0x78 and tokenFrame ~= nil then
    report(string.format(
      "canonical token resolver returned at frame %d bc=%02X%02X de=%02X%02X hl=%02X%02X sp=%04X",
      frame, state["cpu.b"], state["cpu.c"], state["cpu.d"], state["cpu.e"],
      state["cpu.h"], state["cpu.l"], state["cpu.sp"]
    ))
  end
end

local function traceInputDraw()
  local state = emu.getState()
  if not loaded or state["cart.prgBank"] ~= 0x11
      or rd(0xC195) ~= 0x00 or rd(0xC153) ~= 0x0E then
    return
  end
  assert(
    state["cpu.b"] == 0x28 and state["cpu.c"] == 0x08,
    string.format(
      "fourteen-cell presentation origin moved: bc=%02X%02X",
      state["cpu.b"], state["cpu.c"]
    )
  )
  if rd(0xC196) == 0xFF then
    if not alignedResetOriginSeen then
      alignedResetOriginSeen = true
      report("empty free field aligned to native seven-cell origin")
    end
  elseif not alignedPreviewOriginSeen then
    alignedPreviewOriginSeen = true
    report("canonical preview aligned to native seven-cell origin")
  end
end

emu.addMemoryCallback(
  loadOnce,
  emu.callbackType.exec,
  0x0000,
  0xFFFF,
  emu.cpuType.gameboy
)
emu.addMemoryCallback(
  traceScreen, emu.callbackType.exec, 0x40C0, 0x40C0,
  emu.cpuType.gameboy
)
emu.addMemoryCallback(
  traceFillIn, emu.callbackType.exec, 0x5215, 0x5215,
  emu.cpuType.gameboy
)
emu.addMemoryCallback(
  traceResolve, emu.callbackType.exec, 0x4180, 0x4180,
  emu.cpuType.gameboy
)
emu.addMemoryCallback(
  traceResolveReturn, emu.callbackType.exec, 0x480E, 0x480E,
  emu.cpuType.gameboy
)
emu.addMemoryCallback(
  traceInputDraw, emu.callbackType.exec, 0x46C2, 0x46C2,
  emu.cpuType.gameboy
)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
