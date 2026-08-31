-- Open and dismiss the warehouse Deposit/Withdraw/Trash/Quit popup through
-- controller input from the user-provided state immediately before Kume.

local frame = 0
local loaded = false
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam
local EXPECTED_WIDE_SCREEN = tonumber(
  assert(os.getenv("GB2_WAREHOUSE_EXPECTED_WIDE_SCREEN")), 16)
local EXPECTED_CLOSED_SCREEN = tonumber(
  assert(os.getenv("GB2_WAREHOUSE_EXPECTED_CLOSED_SCREEN")), 16)
local EXPECTED_WITHDRAW_SCREEN = tonumber(
  assert(os.getenv("GB2_WAREHOUSE_EXPECTED_WITHDRAW_SCREEN")), 16)
local EXPECTED_TRASH_SCREEN = tonumber(
  assert(os.getenv("GB2_WAREHOUSE_EXPECTED_TRASH_SCREEN")), 16)
local EXPECTED_QUIT_SCREEN = tonumber(
  assert(os.getenv("GB2_WAREHOUSE_EXPECTED_QUIT_SCREEN")), 16)
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
local openedAt = nil
local dismissAt = nil
local savedDestination = nil
local savedColumn = nil
local spillTile = nil

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

local function savePpm(variable)
  local path = os.getenv(variable)
  if path == nil or path == "" then return end
  local file = assert(io.open(path, "wb"))
  file:write("P6\n160 144\n255\n")
  for _, pixel in ipairs(emu.getScreenBuffer()) do
    file:write(string.char(
      (pixel >> 16) & 0xFF, (pixel >> 8) & 0xFF, pixel & 0xFF))
  end
  file:close()
end

local function saveScreenshot(variable)
  local path = os.getenv(variable)
  if path == nil or path == "" then return end
  local file = assert(io.open(path, "wb"))
  file:write(emu.takeScreenshot())
  file:close()
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_WAREHOUSE_MENU_MSS"))))
  report("service-menu Warehouse fixture loaded")
end

local function pressAt(input, at, button)
  if frame >= at and frame < at + 5 then input[button] = true end
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

local function checkBlankSpillColumn()
  if savedDestination == nil then return check(false,
    "Warehouse spill column checked before popup destination") end
  local rows = emu.read(SAVED_ROWS, workMem)
  for row = 1, rows - 2 do
    local address = popupRowAddress(savedDestination - 1, row)
    if not check(readVram(address, 0) == SERVICE_BLANK_TILE,
      string.format("Warehouse row %d aliases another dynamic tile", row))
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
        "Warehouse spill tile graphics changed across cursor selections")
        then return false end
    end
  end
  return true
end

local function labelsComplete()
  return labels[0x85] and labels[0x86] and labels[0x90] and labels[0x87]
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a=false, b=false, start=false, select=false,
    up=false, down=false, left=false, right=false,
  }
  -- Advance dialogue until execution traces prove the service popup exists.
  -- This is deliberately state-based rather than tied to one captured frame.
  if openedAt == nil and frame % 70 < 5 then input.a = true end
  if openedAt ~= nil then
    pressAt(input, openedAt + 100, "down")
    pressAt(input, openedAt + 220, "down")
    pressAt(input, openedAt + 340, "down")
  end
  if dismissAt ~= nil then pressAt(input, dismissAt, "b") end
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
  if not loaded then return end
  if openedAt == nil and labelsComplete() and wideTop and wideBottom then
    openedAt = frame
    dismissAt = frame + 500
    report(string.format("service-menu Warehouse opened frame=%d", frame))
  end
  if openedAt ~= nil and frame == openedAt + 60 then
    local checksum = screenChecksum()
    report(string.format("service-menu Warehouse wide screen=%08X", checksum))
    local savedRows = emu.read(SAVED_ROWS, workMem)
    local savedFlag = emu.read(SAVED_FLAG, workMem)
    local savedFlagEnd = emu.read(SAVED_FLAG_END, workMem)
    local low = emu.read(SAVED_DESTINATION, workMem)
    local high = emu.read(SAVED_DESTINATION + 1, workMem)
    local destination = high * 0x100 + low
    report(string.format(
      "service-menu Warehouse scratch dest=%04X rows=%d flags=%02X/%02X signature=%02X/%02X/%02X extra=%02X",
      destination, savedRows, savedFlag, savedFlagEnd,
      readVram(destination - 8, 0), readVram(destination - 7, 0),
      readVram(destination - 1, 0), readVram(destination, 0)))
    if not check(savedRows >= 2 and savedRows <= 10,
      "Warehouse saved row count is outside the popup range") then return end
    if not check(emu.read(SAVED_FLAG, workMem) == 0xA5 and
        emu.read(SAVED_FLAG_END, workMem) == 0x5A,
      "Warehouse saved-column lifecycle flag is not live") then return end
    savedDestination = high * 0x100 + low
    savedColumn = {}
    for row = 0, savedRows - 1 do
      local expectedTile = row == 0 and 0x7E or
        (row == savedRows - 1 and 0x7E or 0x7F)
      local expectedAttribute = row == savedRows - 1 and 0xEF or 0xAF
      local address = popupRowAddress(savedDestination, row)
      report(string.format(
        "service-menu Warehouse border row=%d tile=%02X attr=%02X expected=%02X/%02X",
        row, readVram(address, 0), readVram(address, 1),
        expectedTile, expectedAttribute))
      if not check(readVram(address, 0) == expectedTile,
        string.format("Warehouse right-border tile missing at row %d", row))
        then return end
      if not check(readVram(address, 1) == expectedAttribute,
        string.format("Warehouse right-border attribute wrong at row %d", row))
        then return end
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2, workMem)
      savedColumn[#savedColumn + 1] = emu.read(
        SAVED_COLUMN + row * 2 + 1, workMem)
    end
    if EXPECTED_WIDE_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_WIDE_SCREEN,
        "Warehouse wide popup framebuffer changed") then return end
    end
    if not checkBlankSpillColumn() then return end
    saveScreenshot("GB2_WAREHOUSE_SERVICE_SCREENSHOT")
  elseif openedAt ~= nil and frame == openedAt + 180 then
    local checksum = screenChecksum()
    report(string.format("service-menu Warehouse Withdraw screen=%08X", checksum))
    if not check(checksum == EXPECTED_WITHDRAW_SCREEN,
      "Warehouse Withdraw cursor framebuffer changed") then return end
    if not checkBlankSpillColumn() then return end
  elseif openedAt ~= nil and frame == openedAt + 300 then
    local checksum = screenChecksum()
    report(string.format("service-menu Warehouse Trash screen=%08X", checksum))
    if not check(checksum == EXPECTED_TRASH_SCREEN,
      "Warehouse Trash cursor framebuffer changed") then return end
    if not checkBlankSpillColumn() then return end
  elseif openedAt ~= nil and frame == openedAt + 420 then
    local checksum = screenChecksum()
    report(string.format("service-menu Warehouse Quit screen=%08X", checksum))
    if not check(checksum == EXPECTED_QUIT_SCREEN,
      "Warehouse Quit cursor framebuffer changed") then return end
    if not checkBlankSpillColumn() then return end
  elseif dismissAt ~= nil and frame > dismissAt + 60 and
      emu.read(SAVED_FLAG, workMem) == 0 and
      emu.read(SAVED_FLAG_END, workMem) == 0 then
    local checksum = screenChecksum()
    report(string.format("service-menu Warehouse closed screen=%08X", checksum))
    if not check(savedDestination ~= nil and savedColumn ~= nil,
      "Warehouse closed before its original column was recorded") then return end
    local savedRows = emu.read(SAVED_ROWS, workMem)
    for row = 0, savedRows - 1 do
      local address = popupRowAddress(savedDestination, row)
      if not check(readVram(address, 0) == savedColumn[row * 2 + 1],
        string.format("Warehouse tile was not restored at row %d", row))
        then return end
      if not check(readVram(address, 1) == savedColumn[row * 2 + 2],
        string.format("Warehouse attribute was not restored at row %d", row))
        then return end
    end
    if EXPECTED_CLOSED_SCREEN ~= 0 then
      if not check(checksum == EXPECTED_CLOSED_SCREEN,
        "Warehouse popup teardown changed") then return end
    end
    saveScreenshot("GB2_WAREHOUSE_SERVICE_CLOSED_SCREENSHOT")
    report("PASS Warehouse service popup widened and dismissed")
    emu.stop(0)
  elseif frame > 2400 then
    local state = emu.getState()
    report(string.format(
      "Warehouse timeout pc=%04X mode=%02X nav=%02X node=%02X",
      state["cpu.pc"], emu.read(0xC195, cpuMem),
      emu.read(0xC14E, cpuMem), emu.read(0xC14F, cpuMem)))
    savePpm("GB2_WAREHOUSE_DEBUG_PPM")
    check(false, "timed out while testing Warehouse service popup")
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
