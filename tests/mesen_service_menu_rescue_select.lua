-- Select Password from a freshly rebuilt widened Rescue Team popup.
--
-- The native town redraw covers eight columns. The English popup is nine
-- columns wide, so this route freezes the selection transition and proves the
-- added rightmost column was restored instead of remaining as a white strip.

local frame = 0
local loaded = false
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam
local EXPECTED_TRANSITION_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_TRANSITION_SCREEN")), 16)
local SERVICE_SCRATCH_BANK = 7
local SAVED_COLUMN = SERVICE_SCRATCH_BANK * 0x1000 + 0x8C0
local SAVED_DESTINATION = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D4
local SAVED_ROWS = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D6
local SAVED_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D7
local SAVED_FLAG_END = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D8

local savedDestination = nil
local savedRows = nil
local savedColumn = nil

local function report(message)
  print(message)
  emu.log(message)
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

local function check(condition, message)
  if condition then return true end
  report("FAIL " .. message)
  emu.stop(1)
  return false
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

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_ENTRY_MSS"))))
  report("service-menu Rescue selection fixture loaded")
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
  -- Discard the stale popup in the state, then rebuild it through the complete
  -- confirmation route before selecting Password.
  pressAt(input, 60, "b")
  for at = 160, 560, 100 do pressAt(input, at, "a") end
  pressAt(input, 720, "down")
  pressAt(input, 760, "a")
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded then return end
  if frame == 700 then
    local low = emu.read(SAVED_DESTINATION, workMem)
    local high = emu.read(SAVED_DESTINATION + 1, workMem)
    savedDestination = high * 0x100 + low
    savedRows = emu.read(SAVED_ROWS, workMem)
    if not check(high == 0x99 and low == 0x50,
      "widened Rescue popup did not save BG column $9950") then return end
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
  elseif frame == 1000 then
    local checksum = screenChecksum()
    local low = emu.read(SAVED_DESTINATION, workMem)
    local high = emu.read(SAVED_DESTINATION + 1, workMem)
    local flag = emu.read(SAVED_FLAG, workMem)
    report(string.format(
      "service-menu Rescue selected screen=%08X saved=%02X%02X flag=%02X",
      checksum, high, low, flag))
    if not check(savedDestination ~= nil and savedRows ~= nil and
        savedColumn ~= nil,
      "Rescue selection occurred before the popup baseline was recorded")
      then return end
    if not check(flag == 0 and emu.read(SAVED_FLAG_END, workMem) == 0,
      "widened Rescue popup column was not restored") then return end
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      if not check(readVram(address, 0) == savedColumn[row * 2 + 1],
        string.format("Rescue tile was not restored at row %d", row))
        then return end
      if not check(readVram(address, 1) == savedColumn[row * 2 + 2],
        string.format("Rescue attribute was not restored at row %d", row))
        then return end
    end
    if EXPECTED_TRANSITION_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_TRANSITION_SCREEN,
        "Rescue Password selection transition changed") then return end
    end
    local screenshot = os.getenv("GB2_RESCUE_SELECTED_SCREENSHOT")
    if screenshot ~= nil and screenshot ~= "" then
      local file = assert(io.open(screenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    report("PASS Rescue Password selection restores widened popup column")
    emu.stop(0)
  elseif frame > 1200 then
    check(false, "timed out while selecting Rescue Password")
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
