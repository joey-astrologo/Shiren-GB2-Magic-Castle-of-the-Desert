-- Open Blacksmith -> Info, traverse every explanation, and return to the
-- native Blacksmith menu. This verifies the widened frame, stable Synthesis
-- suffix tile, and restoration of both the BG column and staged tile graphics.

local frame = 0
local loaded = false
local finished = false
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam
local EXPECTED_FORGE_SCREEN = tonumber(
  assert(os.getenv("GB2_BLACKSMITH_EXPECTED_FORGE_SCREEN")), 16)
local EXPECTED_REPAIR_SCREEN = tonumber(
  assert(os.getenv("GB2_BLACKSMITH_EXPECTED_REPAIR_SCREEN")), 16)
local EXPECTED_SYNTHESIS_SCREEN = tonumber(
  assert(os.getenv("GB2_BLACKSMITH_EXPECTED_SYNTHESIS_SCREEN")), 16)
local EXPECTED_REMOVE_SCREEN = tonumber(
  assert(os.getenv("GB2_BLACKSMITH_EXPECTED_REMOVE_SCREEN")), 16)
local EXPECTED_QUIT_SCREEN = tonumber(
  assert(os.getenv("GB2_BLACKSMITH_EXPECTED_QUIT_SCREEN")), 16)
local EXPECTED_CLOSED_SCREEN = tonumber(
  assert(os.getenv("GB2_BLACKSMITH_EXPECTED_CLOSED_SCREEN")), 16)
local EXPECTED_COLUMNS = 0x09
local SERVICE_SCRATCH_BANK = 7
local SAVED_COLUMN = SERVICE_SCRATCH_BANK * 0x1000 + 0x8C0
local SAVED_DESTINATION = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D4
local SAVED_ROWS = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D6
local SAVED_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D7
local SAVED_FLAG_END = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D8
local BLACKSMITH_TILE_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8DA
local BLANK_TILE = 0xB9
local CURSOR_TILE = 0x9C
local SUFFIX_TILE = 0xB3
local EXPECTED_SUFFIX = {
  0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x70, 0xC7, 0xB8,
  0xFF, 0x60, 0xDF, 0x30, 0xF7, 0xE8, 0x8F, 0x70,
}

local labels = {}
local sawNativeMain = false
local topColumns = nil
local wideBottom = false
local openedAt = nil
local dismissAt = nil
local savedDestination = nil
local savedRows = nil
local savedColumn = nil
local activeTileBank = nil

local function report(message)
  print(message)
  emu.log(message)
end

local function check(condition, message)
  if condition then return true end
  report("FAIL " .. message)
  finished = true
  emu.stop(1)
  return false
end

local function loadFile(path)
  local file = assert(io.open(path, "rb"))
  local data = file:read("*all")
  file:close()
  return data
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_BLACKSMITH_INFO_MSS"))))
  report("service-menu Blacksmith Info fixture loaded")
end

local function pressAt(input, at, button)
  if frame >= at and frame < at + 5 then input[button] = true end
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a=false, b=false, start=false, select=false,
    up=false, down=false, left=false, right=false,
  }
  pressAt(input, 60, "a")
  pressAt(input, 150, "down")
  pressAt(input, 210, "down")
  pressAt(input, 270, "down")
  pressAt(input, 330, "a")
  if openedAt ~= nil then
    pressAt(input, openedAt + 100, "down")
    pressAt(input, openedAt + 200, "down")
    pressAt(input, openedAt + 300, "down")
    pressAt(input, openedAt + 400, "down")
  end
  if dismissAt ~= nil then pressAt(input, dismissAt, "b") end
  emu.setInput(input, 0)
end

local function screenChecksum()
  local hash = 2166136261
  for _, pixel in ipairs(emu.getScreenBuffer()) do
    hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
  end
  return hash
end

local function saveScreenshot(variable)
  local path = os.getenv(variable)
  if path == nil or path == "" then return end
  local file = assert(io.open(path, "wb"))
  file:write(emu.takeScreenshot())
  file:close()
end

local function readVram(address, bank)
  return emu.read(bank * 0x2000 + address - 0x8000, videoMem)
end

local function popupRowAddress(destination, row)
  local address = destination + row * 32
  if address >= 0x9C00 and destination < 0x9C00 then
    address = address - 0x400
  end
  return address
end

local function labelsComplete()
  return labels[0x94] and labels[0x95] and labels[0x97] and
    labels[0x96] and labels[0x87]
end

local function checkScreen(label, expected)
  local checksum = screenChecksum()
  report(string.format("service-menu Blacksmith %s screen=%08X", label, checksum))
  if expected ~= 0 then
    return check(checksum == expected,
      string.format("Blacksmith %s cursor framebuffer changed", label))
  end
  return true
end

local function checkSuffixAndSpills(quitSelected)
  for row = 1, savedRows - 2 do
    local address = popupRowAddress(savedDestination - 1, row)
    local expected = row == 4 and SUFFIX_TILE or BLANK_TILE
    if not check(readVram(address, 0) == expected,
      string.format("Blacksmith spill tile wrong at row %d", row))
      then return false end
    if not check(((readVram(address, 1) >> 3) & 1) == activeTileBank,
      string.format("Blacksmith spill tile bank wrong at row %d", row))
      then return false end
  end
  for byte = 0, 15 do
    local expectedBlank = byte % 2 == 0 and 0xFF or 0x00
    if not check(readVram(0x8000 + BLANK_TILE * 16 + byte,
        activeTileBank) == expectedBlank,
      "Blacksmith reviewed blank spill tile changed") then return false end
    if not check(readVram(0x8000 + SUFFIX_TILE * 16 + byte,
        activeTileBank) == EXPECTED_SUFFIX[byte + 1],
      "Blacksmith Synthesis suffix tile changed across cursor selections")
      then return false end
    if not quitSelected and not check(
        readVram(0x8000 + CURSOR_TILE * 16 + byte,
          activeTileBank) == expectedBlank,
        "Blacksmith stray Synthesis glyph remained left of Quit")
      then return false end
  end
  return true
end

local function traceSelector()
  local state = emu.getState()
  if state["cpu.a"] == 0x07 then labels[state["cpu.c"]] = true end
end

local function traceBgCopy()
  local state = emu.getState()
  if state["cpu.h"] == 0xD8 and state["cpu.l"] == 0x00 then
    topColumns = state["cpu.c"]
    if state["cpu.c"] == 0x07 then sawNativeMain = true end
  elseif state["cpu.b"] == 0x01 and state["cpu.h"] == 0xD8 then
    if state["cpu.c"] == EXPECTED_COLUMNS then wideBottom = true end
  end
end

local function afterFrame()
  if not loaded or finished then return end
  if openedAt == nil and labelsComplete() and topColumns == EXPECTED_COLUMNS then
    openedAt = frame
    dismissAt = frame + 520
    report(string.format("service-menu Blacksmith Info opened frame=%d", frame))
  end
  if openedAt ~= nil and frame == openedAt + 60 then
    if not check(sawNativeMain and wideBottom,
      "Blacksmith Info did not replace the native main menu with a wide frame")
      then return end
    local low = emu.read(SAVED_DESTINATION, workMem)
    local high = emu.read(SAVED_DESTINATION + 1, workMem)
    savedDestination = high * 0x100 + low
    savedRows = emu.read(SAVED_ROWS, workMem)
    if not check(savedRows == 9, "Blacksmith saved row count is not nine")
      then return end
    if not check(emu.read(SAVED_FLAG, workMem) == 0xA5 and
        emu.read(SAVED_FLAG_END, workMem) == 0x5A and
        emu.read(BLACKSMITH_TILE_FLAG, workMem) == 0xA6,
      "Blacksmith widened-popup lifecycle markers are not live") then return end
    savedColumn = {}
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      local expectedTile = row == 0 and 0x7E or
        (row == savedRows - 1 and 0x7E or 0x7F)
      local expectedAttribute = row == savedRows - 1 and 0xEF or 0xAF
      if not check(readVram(address, 0) == expectedTile,
        string.format("Blacksmith right-border tile missing at row %d", row))
        then return end
      if not check(readVram(address, 1) == expectedAttribute,
        string.format("Blacksmith right-border attribute wrong at row %d", row))
        then return end
      savedColumn[#savedColumn + 1] = emu.read(SAVED_COLUMN + row * 2, workMem)
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2 + 1, workMem)
    end
    local suffixAddress = popupRowAddress(savedDestination - 1, 4)
    activeTileBank = (readVram(suffixAddress, 1) >> 3) & 1
    if not checkScreen("Forge", EXPECTED_FORGE_SCREEN) then return end
    if not checkSuffixAndSpills(false) then return end
    saveScreenshot("GB2_BLACKSMITH_INFO_SCREENSHOT")
  elseif openedAt ~= nil and frame == openedAt + 160 then
    if not checkScreen("Repair", EXPECTED_REPAIR_SCREEN) then return end
    if not checkSuffixAndSpills(false) then return end
  elseif openedAt ~= nil and frame == openedAt + 260 then
    if not checkScreen("Synthesis", EXPECTED_SYNTHESIS_SCREEN) then return end
    if not checkSuffixAndSpills(false) then return end
  elseif openedAt ~= nil and frame == openedAt + 360 then
    if not checkScreen("Remove", EXPECTED_REMOVE_SCREEN) then return end
    if not checkSuffixAndSpills(false) then return end
  elseif openedAt ~= nil and frame == openedAt + 460 then
    if not checkScreen("Quit", EXPECTED_QUIT_SCREEN) then return end
    if not checkSuffixAndSpills(true) then return end
  elseif dismissAt ~= nil and frame > dismissAt + 60 and
      emu.read(SAVED_FLAG, workMem) == 0 and
      emu.read(SAVED_FLAG_END, workMem) == 0 and
      emu.read(BLACKSMITH_TILE_FLAG, workMem) == 0 then
    if not check(savedDestination ~= nil and savedColumn ~= nil,
      "Blacksmith Info closed before its original column was recorded")
      then return end
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      if not check(readVram(address, 0) == savedColumn[row * 2 + 1],
        string.format("Blacksmith tile was not restored at row %d", row))
        then return end
      if not check(readVram(address, 1) == savedColumn[row * 2 + 2],
        string.format("Blacksmith attribute was not restored at row %d", row))
        then return end
    end
    for byte = 0, 15 do
      local expectedBlank = byte % 2 == 0 and 0xFF or 0x00
      if not check(readVram(0x8000 + SUFFIX_TILE * 16 + byte,
          activeTileBank) == expectedBlank,
        "Blacksmith suffix tile was not restored after dismissal") then return end
    end
    if not checkScreen("closed", EXPECTED_CLOSED_SCREEN) then return end
    report("PASS Blacksmith Info widened, traversed, and dismissed")
    finished = true
    emu.stop(0)
  elseif frame > 1500 then
    check(false, "timed out while testing Blacksmith Info")
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addMemoryCallback(
  traceSelector, emu.callbackType.exec, 0x1FA0, 0x1FA0, emu.cpuType.gameboy)
emu.addMemoryCallback(
  traceBgCopy, emu.callbackType.exec, 0x0AEA, 0x0AEA, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
