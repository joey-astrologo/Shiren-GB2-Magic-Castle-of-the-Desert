-- Pixel-level regression for the Warehouse popup after items were placed in
-- the room without leaving. The camera position makes the widened frame cross
-- the 32-tile BG-map row boundary horizontally.
--
-- This deliberately does not consume a framebuffer checksum. The expected
-- 8x64 raster is the literal native right edge of the popup, and the route
-- rebuilds the popup through controller input from the supplied savestate.

local frame = 0
local loaded = false
local finished = false
local openedAt = nil
local labels = {}
local wideTop = false
local wideBottom = false
local savedColumn = nil
local savedDestination = nil
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam
local SCREEN_WIDTH = 160
local RIGHT_EDGE_X = 72
local RIGHT_EDGE_Y = 16
local TALK_AT = 180
local SERVICE_SCRATCH_BANK = 7
local SAVED_COLUMN = SERVICE_SCRATCH_BANK * 0x1000 + 0x8C0
local SAVED_DESTINATION = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D4
local SAVED_ROWS = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D6
local SAVED_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D7
local SAVED_FLAG_END = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D8
local EXPECTED_DESTINATION = tonumber(
  assert(os.getenv("GB2_WAREHOUSE_EXPECTED_DESTINATION")), 16)
local EXPECTED_RIGHT_EDGE = {
  "........",
  "######d.",
  "ddddd##.",
}
for _ = 1, 58 do
  EXPECTED_RIGHT_EDGE[#EXPECTED_RIGHT_EDGE + 1] = ".....d#."
end
EXPECTED_RIGHT_EDGE[#EXPECTED_RIGHT_EDGE + 1] = "ddddd##."
EXPECTED_RIGHT_EDGE[#EXPECTED_RIGHT_EDGE + 1] = "######d."
EXPECTED_RIGHT_EDGE[#EXPECTED_RIGHT_EDGE + 1] = "........"

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
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_WAREHOUSE_ITEMS_MSS"))))
  report("service-menu Warehouse floor-items fixture loaded")
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
  pressAt(input, TALK_AT, "a")
  if openedAt ~= nil then
    pressAt(input, openedAt + 100, "down")
    pressAt(input, openedAt + 220, "down")
    pressAt(input, openedAt + 340, "down")
    pressAt(input, openedAt + 500, "b")
  end
  emu.setInput(input, 0)
end

local function traceSelector()
  if frame < TALK_AT then return end
  local state = emu.getState()
  if state["cpu.a"] == 0x07 then labels[state["cpu.c"]] = true end
end

local function traceBgCopy()
  if frame < TALK_AT then return end
  local state = emu.getState()
  if state["cpu.c"] ~= 0x09 then return end
  if state["cpu.h"] == 0xD8 and state["cpu.l"] == 0x00 then
    wideTop = true
  elseif state["cpu.b"] == 0x01 and state["cpu.h"] == 0xD8
      and state["cpu.l"] == 0xA2 then
    wideBottom = true
  end
end

local function labelsComplete()
  return labels[0x85] and labels[0x86] and labels[0x90] and labels[0x87]
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

local function checkRightEdge()
  local screen = emu.getScreenBuffer()
  for row, expectedRow in ipairs(EXPECTED_RIGHT_EDGE) do
    for column = 1, #expectedRow do
      local x = RIGHT_EDGE_X + column - 1
      local y = RIGHT_EDGE_Y + row - 1
      local expectedInk = expectedRow:sub(column, column) == "#"
      local actualInk =
        (screen[y * SCREEN_WIDTH + x + 1] & 0x00FFFFFF) == 0
      if not check(actualInk == expectedInk, string.format(
        "Warehouse right-edge pixel (%d,%d) expected %s, got %s",
        x, y, expectedInk and "ink" or "background",
        actualInk and "ink" or "background")) then return false end
    end
  end
  return true
end

local function captureSavedColumn()
  local low = emu.read(SAVED_DESTINATION, workMem)
  local high = emu.read(SAVED_DESTINATION + 1, workMem)
  savedDestination = high * 0x100 + low
  if not check(savedDestination == EXPECTED_DESTINATION, string.format(
    "Warehouse saved destination expected %04X, got %04X",
    EXPECTED_DESTINATION, savedDestination)) then return false end
  if not check(emu.read(SAVED_FLAG, workMem) == 0xA5 and
      emu.read(SAVED_FLAG_END, workMem) == 0x5A,
    "Warehouse saved-column lifecycle marker was cleared while open")
    then return false end
  local rows = emu.read(SAVED_ROWS, workMem)
  if not check(rows == 8, string.format(
    "Warehouse saved row count expected 8, got %d", rows)) then return false end
  savedColumn = {}
  for row = 0, rows - 1 do
    savedColumn[#savedColumn + 1] = emu.read(
      SAVED_COLUMN + row * 2, workMem)
    savedColumn[#savedColumn + 1] = emu.read(
      SAVED_COLUMN + row * 2 + 1, workMem)
  end
  return true
end

local function afterFrame()
  if not loaded or finished then return end
  if openedAt == nil and labelsComplete() and wideTop and wideBottom then
    openedAt = frame
    report(string.format("service-menu Warehouse floor-items opened frame=%d", frame))
  elseif openedAt ~= nil and frame == openedAt + 60 then
    if not checkRightEdge() then return end
    if not captureSavedColumn() then return end
  elseif openedAt ~= nil and (frame == openedAt + 180 or
      frame == openedAt + 300 or frame == openedAt + 420) then
    if not checkRightEdge() then return end
  elseif openedAt ~= nil and frame > openedAt + 560 and
      emu.read(SAVED_FLAG, workMem) == 0 and
      emu.read(SAVED_FLAG_END, workMem) == 0 then
    if not check(savedDestination ~= nil and savedColumn ~= nil,
      "Warehouse popup closed before its column was captured") then return end
    for row = 0, 7 do
      local address = popupRowAddress(savedDestination, row)
      if not check(readVram(address, 0) == savedColumn[row * 2 + 1],
        string.format("Warehouse tile was not restored at row %d", row))
        then return end
      if not check(readVram(address, 1) == savedColumn[row * 2 + 2],
        string.format("Warehouse attribute was not restored at row %d", row))
        then return end
    end
    report("PASS Warehouse floor-items popup keeps and restores its literal right edge")
    finished = true
    emu.stop(0)
  elseif frame > 1200 then
    check(false, "timed out while checking the Warehouse floor-items popup")
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
