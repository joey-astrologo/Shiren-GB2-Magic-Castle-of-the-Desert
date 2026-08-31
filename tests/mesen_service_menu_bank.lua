-- Open, traverse, and dismiss the Bank Teller Deposit/Withdraw/Balance/Quit
-- popup through controller input from the user-provided pre-conversation state.

local frame = 0
local loaded = false
local finished = false
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam
local EXPECTED_DEPOSIT_SCREEN = tonumber(
  assert(os.getenv("GB2_BANK_EXPECTED_DEPOSIT_SCREEN")), 16)
local EXPECTED_WITHDRAW_SCREEN = tonumber(
  assert(os.getenv("GB2_BANK_EXPECTED_WITHDRAW_SCREEN")), 16)
local EXPECTED_BALANCE_SCREEN = tonumber(
  assert(os.getenv("GB2_BANK_EXPECTED_BALANCE_SCREEN")), 16)
local EXPECTED_QUIT_SCREEN = tonumber(
  assert(os.getenv("GB2_BANK_EXPECTED_QUIT_SCREEN")), 16)
local EXPECTED_CLOSED_SCREEN = tonumber(
  assert(os.getenv("GB2_BANK_EXPECTED_CLOSED_SCREEN")), 16)
local EXPECTED_COLUMNS = 0x09
local SERVICE_SCRATCH_BANK = 7
local SAVED_COLUMN = SERVICE_SCRATCH_BANK * 0x1000 + 0x8C0
local SAVED_DESTINATION = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D4
local SAVED_ROWS = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D6
local SAVED_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D7
local SAVED_FLAG_END = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D8
local SERVICE_BLANK_TILE = 0xB3

local labels = {}
local topColumns = nil
local wideBottom = false
local openedAt = nil
local dismissAt = nil
local savedDestination = nil
local savedRows = nil
local savedColumn = nil
local spillTile = nil

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
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_BANK_TELLER_MSS"))))
  report("service-menu Bank Teller fixture loaded")
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
  pressAt(input, 160, "a")
  if openedAt ~= nil then
    pressAt(input, openedAt + 100, "down")
    pressAt(input, openedAt + 220, "down")
    pressAt(input, openedAt + 340, "down")
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
  return labels[0x85] and labels[0x93] and labels[0x56] and labels[0x87]
end

local function checkSpillColumn()
  if savedDestination == nil or savedRows == nil then return check(false,
    "Bank spill column checked before popup destination") end
  for row = 1, savedRows - 2 do
    local address = popupRowAddress(savedDestination - 1, row)
    if not check(readVram(address, 0) == SERVICE_BLANK_TILE,
      string.format("Bank row %d aliases another dynamic tile", row))
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
        "Bank spill tile graphics changed across cursor selections")
        then return false end
    end
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
  elseif state["cpu.b"] == 0x01 and state["cpu.h"] == 0xD8 then
    if state["cpu.c"] == EXPECTED_COLUMNS then wideBottom = true end
  end
end

local function checkScreen(label, expected)
  local checksum = screenChecksum()
  report(string.format("service-menu Bank %s screen=%08X", label, checksum))
  if expected ~= 0 then
    return check(checksum == expected,
      string.format("Bank %s cursor framebuffer changed", label))
  end
  return true
end

local function afterFrame()
  if not loaded or finished then return end
  if openedAt == nil and labelsComplete() and topColumns ~= nil then
    openedAt = frame
    dismissAt = frame + 500
    report(string.format("service-menu Bank opened frame=%d", frame))
  end
  if openedAt ~= nil and frame == openedAt + 60 then
    if not check(topColumns == EXPECTED_COLUMNS and wideBottom,
      "Bank menu did not copy a nine-column frame") then return end
    local low = emu.read(SAVED_DESTINATION, workMem)
    local high = emu.read(SAVED_DESTINATION + 1, workMem)
    savedDestination = high * 0x100 + low
    savedRows = emu.read(SAVED_ROWS, workMem)
    if not check(savedRows >= 2 and savedRows <= 10,
      "Bank saved row count is outside the popup range") then return end
    if not check(emu.read(SAVED_FLAG, workMem) == 0xA5 and
        emu.read(SAVED_FLAG_END, workMem) == 0x5A,
      "Bank saved-column lifecycle flag is not live") then return end
    savedColumn = {}
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      local expectedTile = row == 0 and 0x7E or
        (row == savedRows - 1 and 0x7E or 0x7F)
      local expectedAttribute = row == savedRows - 1 and 0xEF or 0xAF
      if not check(readVram(address, 0) == expectedTile,
        string.format("Bank right-border tile missing at row %d", row))
        then return end
      if not check(readVram(address, 1) == expectedAttribute,
        string.format("Bank right-border attribute wrong at row %d", row))
        then return end
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2, workMem)
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2 + 1, workMem)
    end
    if not checkScreen("Deposit", EXPECTED_DEPOSIT_SCREEN) then return end
    if not checkSpillColumn() then return end
    saveScreenshot("GB2_BANK_SERVICE_SCREENSHOT")
  elseif openedAt ~= nil and frame == openedAt + 180 then
    if not checkScreen("Withdraw", EXPECTED_WITHDRAW_SCREEN) then return end
    if not checkSpillColumn() then return end
  elseif openedAt ~= nil and frame == openedAt + 300 then
    if not checkScreen("Balance", EXPECTED_BALANCE_SCREEN) then return end
    if not checkSpillColumn() then return end
  elseif openedAt ~= nil and frame == openedAt + 420 then
    if not checkScreen("Quit", EXPECTED_QUIT_SCREEN) then return end
    if not checkSpillColumn() then return end
  elseif dismissAt ~= nil and frame > dismissAt + 60 and
      emu.read(SAVED_FLAG, workMem) == 0 and
      emu.read(SAVED_FLAG_END, workMem) == 0 then
    if not check(savedDestination ~= nil and savedColumn ~= nil,
      "Bank closed before its original column was recorded") then return end
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      if not check(readVram(address, 0) == savedColumn[row * 2 + 1],
        string.format("Bank tile was not restored at row %d", row))
        then return end
      if not check(readVram(address, 1) == savedColumn[row * 2 + 2],
        string.format("Bank attribute was not restored at row %d", row))
        then return end
    end
    if not checkScreen("closed", EXPECTED_CLOSED_SCREEN) then return end
    report("PASS Bank service popup widened, traversed, and dismissed")
    finished = true
    emu.stop(0)
  elseif frame > 1400 then
    local state = emu.getState()
    report(string.format(
      "Bank timeout pc=%04X mode=%02X nav=%02X node=%02X",
      state["cpu.pc"], emu.read(0xC195, cpuMem),
      emu.read(0xC14E, cpuMem), emu.read(0xC14F, cpuMem)))
    check(false, "timed out while testing Bank service popup")
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
