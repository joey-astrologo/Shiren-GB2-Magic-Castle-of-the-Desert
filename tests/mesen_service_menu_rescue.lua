-- Rebuild and dismiss the Rescue Team Cable/Password/Quit popup.
--
-- The fixture itself was captured after the native seven-column popup was
-- drawn, so this route first backs out and then re-enters through controller
-- input.  The assertions therefore cover the installed constructor rather
-- than stale framebuffer state embedded in the .mss file.

local frame = 0
local loaded = false
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam
local EXPECTED_CONFIRM_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_CONFIRM_SCREEN")), 16)
local EXPECTED_WIDE_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_WIDE_SCREEN")), 16)
local EXPECTED_CLOSED_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_CLOSED_SCREEN")), 16)
local EXPECTED_PASSWORD_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_PASSWORD_SCREEN")), 16)
local EXPECTED_QUIT_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_QUIT_SCREEN")), 16)
local EXPECTED_COLUMNS = 0x09
local EXPECTED_BOTTOM = 0xD8A2
local SERVICE_SCRATCH_BANK = 7
local SAVED_COLUMN = SERVICE_SCRATCH_BANK * 0x1000 + 0x8C0
local SAVED_DESTINATION = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D4
local SAVED_ROWS = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D6
local SAVED_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D7
local SAVED_FLAG_END = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D8
local SERVICE_BLANK_TILE = 0xB3

local labels = {}
local wideTop = false
local wideBottom = false
local savedDestination = nil
local savedRows = nil
local savedColumn = nil
local spillTile = nil
local finished = false

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

local function checkSpillColumn()
  if savedDestination == nil or savedRows == nil then return check(false,
    "Rescue spill column checked before popup destination") end
  for row = 1, savedRows - 2 do
    local address = popupRowAddress(savedDestination - 1, row)
    local expectedTile = row == 2 and 0xA8 or
      (row == 3 and 0xBA or SERVICE_BLANK_TILE)
    if not check(readVram(address, 0) == expectedTile,
      string.format("Rescue row %d aliases another dynamic tile", row))
      then return false end
  end
  if spillTile == nil then
    spillTile = {}
    for byte = 0, 15 do
      spillTile[byte + 1] = readVram(
        0x8000 + SERVICE_BLANK_TILE * 16 + byte, 0)
    end
  else
    for byte = 0, 15 do
      if not check(
        readVram(0x8000 + SERVICE_BLANK_TILE * 16 + byte, 0) ==
          spillTile[byte + 1],
        "Rescue spill tile graphics changed across cursor selections")
        then return false end
    end
  end
  return true
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_ENTRY_MSS"))))
  report("service-menu Rescue fixture loaded")
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
  pressAt(input, 60, "b")
  for at = 160, 560, 100 do pressAt(input, at, "a") end
  pressAt(input, 720, "down")
  pressAt(input, 820, "down")
  pressAt(input, 980, "b")
  emu.setInput(input, 0)
end

local function traceSelector()
  local state = emu.getState()
  if state["cpu.a"] == 0x07 then labels[state["cpu.c"]] = true end
end

local function traceBgCopy()
  local state = emu.getState()
  if state["cpu.c"] ~= EXPECTED_COLUMNS then return end
  if state["cpu.h"] == 0xD8 and state["cpu.l"] == 0x00 then
    wideTop = true
  elseif state["cpu.b"] == 0x01 and state["cpu.h"] == 0xD8
      and state["cpu.l"] == (EXPECTED_BOTTOM & 0xFF) then
    wideBottom = true
  end
end

local function afterFrame()
  if not loaded or finished then return end
  if frame == 540 then
    local checksum = screenChecksum()
    report(string.format("service-menu Rescue confirmation screen=%08X", checksum))
    if not check(labels[0x88] and labels[0x89],
      "Rescue Yes/No confirmation labels were not rebuilt") then return end
    if EXPECTED_CONFIRM_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_CONFIRM_SCREEN,
        "Rescue Yes/No confirmation framebuffer changed") then return end
    end
    saveScreenshot("GB2_RESCUE_CONFIRM_SCREENSHOT")
  elseif frame == 700 then
    local checksum = screenChecksum()
    report(string.format("service-menu Rescue wide screen=%08X", checksum))
    if not check(labels[0x80] and labels[0x7F] and labels[0x87],
      "Rescue menu labels were not rebuilt") then return end
    if not check(wideTop and wideBottom,
      "Rescue menu did not copy a nine-column frame") then return end
    local low = emu.read(SAVED_DESTINATION, workMem)
    local high = emu.read(SAVED_DESTINATION + 1, workMem)
    savedDestination = high * 0x100 + low
    savedRows = emu.read(SAVED_ROWS, workMem)
    if not check(savedRows >= 2 and savedRows <= 10,
      "Rescue saved row count is outside the popup range") then return end
    if not check(emu.read(SAVED_FLAG, workMem) == 0xA5 and
        emu.read(SAVED_FLAG_END, workMem) == 0x5A,
      "Rescue saved-column lifecycle flag is not live") then return end
    savedColumn = {}
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      local expectedTile = row == 0 and 0x7E or
        (row == savedRows - 1 and 0x7E or 0x7F)
      local expectedAttribute = row == savedRows - 1 and 0xEF or 0xAF
      if not check(readVram(address, 0) == expectedTile,
        string.format("Rescue right-border tile missing at row %d", row))
        then return end
      if not check(readVram(address, 1) == expectedAttribute,
        string.format("Rescue right-border attribute wrong at row %d", row))
        then return end
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2, workMem)
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2 + 1, workMem)
    end
    if EXPECTED_WIDE_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_WIDE_SCREEN,
        "Rescue wide popup framebuffer changed") then return end
    end
    if not checkSpillColumn() then return end
    saveScreenshot("GB2_RESCUE_SERVICE_SCREENSHOT")
  elseif frame == 790 then
    local checksum = screenChecksum()
    report(string.format("service-menu Rescue Password screen=%08X", checksum))
    if EXPECTED_PASSWORD_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_PASSWORD_SCREEN,
        "Rescue Password cursor framebuffer changed") then return end
    end
    if not checkSpillColumn() then return end
  elseif frame == 890 then
    local checksum = screenChecksum()
    report(string.format("service-menu Rescue Quit screen=%08X", checksum))
    if EXPECTED_QUIT_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_QUIT_SCREEN,
        "Rescue Quit cursor framebuffer changed") then return end
    end
    if not checkSpillColumn() then return end
  elseif frame > 1040 and savedDestination ~= nil and
      emu.read(SAVED_FLAG, workMem) == 0 and
      emu.read(SAVED_FLAG_END, workMem) == 0 then
    local checksum = screenChecksum()
    report(string.format("service-menu Rescue closed screen=%08X", checksum))
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      if not check(readVram(address, 0) == savedColumn[row * 2 + 1],
        string.format("Rescue tile was not restored at row %d", row))
        then return end
      if not check(readVram(address, 1) == savedColumn[row * 2 + 2],
        string.format("Rescue attribute was not restored at row %d", row))
        then return end
    end
    if EXPECTED_CLOSED_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_CLOSED_SCREEN,
        "Rescue popup teardown changed") then return end
    end
    saveScreenshot("GB2_RESCUE_SERVICE_CLOSED_SCREENSHOT")
    report("PASS Rescue confirmation and service popup rebuilt and dismissed")
    finished = true
    emu.stop(0)
  elseif frame > 1400 then
    check(false, "timed out while testing Rescue service popup")
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
