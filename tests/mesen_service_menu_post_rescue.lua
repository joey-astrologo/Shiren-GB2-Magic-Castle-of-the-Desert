-- Pixel/geometry regression for the completed-rescue delivery popup.
--
-- Starts before the rescue target is activated, uses only controller input to
-- finish the rescue and advance Good's dialogue, then requires the distinct
-- Cable / Password / Cancel / Later selector to use the reviewed wide frame.
-- No framebuffer checksum is used: Password's final `d`, the right border,
-- and every spill cell are checked directly.

local frame = 0
local loaded = false
local finished = false
local menuAt = nil
local wideTop = false
local wideBottom = false
local labels = {}
local approvedPopup = nil
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local videoMem = emu.memType.gbVideoRam

local SCREEN_WIDTH = 160
local D_X = 61
local D_Y = 39
local EXPECTED_D = {
  "...#.",
  "...#.",
  ".###.",
  "#..#.",
  "#..#.",
  "#..#.",
  ".###.",
  ".....",
}

local EXPECTED_COLUMNS = 0x09
local EXPECTED_BOTTOM = 0xD8A2
local SERVICE_SCRATCH_BANK = 7
local SAVED_DESTINATION = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D4
local SAVED_ROWS = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D6
local SAVED_FLAG = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D7
local SAVED_FLAG_END = SERVICE_SCRATCH_BANK * 0x1000 + 0x8D8
local SERVICE_BLANK_TILE = 0xB3
local CURSOR_OWNED_TILES = {0xA8, 0xBA}
local STAGED_SUFFIX_TILES = {0x9C, 0xAE}

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

local function saveScreenshot()
  local path = os.getenv("GB2_POST_RESCUE_SCREENSHOT")
  if path == nil or path == "" then return end
  local file = assert(io.open(path, "wb"))
  file:write(emu.takeScreenshot())
  file:close()
end

local function readVram(address, bank)
  return emu.read(bank * 0x2000 + address - 0x8000, videoMem)
end

local function overwriteCursorOwnedTiles()
  -- These two tiles belong to lower selector cursor rows.  Moving the cursor
  -- rewrites them, so a widened Password suffix must not reference either.
  for bank = 0, 1 do
    for _, tile in ipairs(CURSOR_OWNED_TILES) do
      local address = bank * 0x2000 + tile * 16
      for offset = 0, 15 do
        emu.write(address + offset, 0, videoMem)
      end
    end
  end
end

local function capturePopup()
  local screen = emu.getScreenBuffer()
  local pixels = {}
  for y = 16, 79 do
    for x = 8, 79 do
      pixels[#pixels + 1] = screen[y * SCREEN_WIDTH + x + 1]
    end
  end
  return pixels
end

local function checkPopupUnchanged()
  local actual = capturePopup()
  for index, expected in ipairs(approvedPopup) do
    if actual[index] ~= expected then
      local zeroBased = index - 1
      local x = 8 + zeroBased % 72
      local y = 16 + math.floor(zeroBased / 72)
      return check(false, string.format(
        "post-rescue popup changed at pixel (%d,%d) after cursor tile redraw",
        x, y))
    end
  end
  return true
end

local function popupRowAddress(destination, row)
  local address = destination + row * 32
  if address >= 0x9C00 and destination < 0x9C00 then
    address = address - 0x400
  end
  return address
end

local function targetMenuActive()
  return emu.read(0xFFB0, cpuMem) == 4 and
    emu.read(0xFFB2, cpuMem) == 0x80 and
    emu.read(0xFFB3, cpuMem) == 0x07 and
    emu.read(0xFFB4, cpuMem) == 0x7F and
    emu.read(0xFFB5, cpuMem) == 0x07 and
    emu.read(0xFFB6, cpuMem) == 0x92 and
    emu.read(0xFFB7, cpuMem) == 0x07 and
    emu.read(0xFFB8, cpuMem) == 0x9E and
    emu.read(0xFFB9, cpuMem) == 0x07
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_AT_RESCUE_MSS"))))
  report("post-rescue delivery fixture loaded")
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
  pressAt(input, 60, "down")
  pressAt(input, 120, "a")
  if menuAt == nil and frame >= 240 and frame % 90 < 5 then
    input.a = true
  end
  if menuAt ~= nil then
    pressAt(input, menuAt + 130, "down")
    pressAt(input, menuAt + 160, "down")
    pressAt(input, menuAt + 190, "down")
  end
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
  elseif state["cpu.b"] == 0x01 and state["cpu.h"] == 0xD8 and
      state["cpu.l"] == (EXPECTED_BOTTOM & 0xFF) then
    wideBottom = true
  end
end

local function isInk(pixel)
  return (pixel & 0x00FFFFFF) == 0
end

local function checkFinalD()
  local screen = emu.getScreenBuffer()
  for row, expectedRow in ipairs(EXPECTED_D) do
    for column = 1, #expectedRow do
      local x = D_X + column - 1
      local y = D_Y + row - 1
      local expectedInk = expectedRow:sub(column, column) == "#"
      local actualInk = isInk(screen[y * SCREEN_WIDTH + x + 1])
      if not check(actualInk == expectedInk, string.format(
        "post-rescue Password final d pixel (%d,%d) expected %s, got %s",
        x, y, expectedInk and "ink" or "background",
        actualInk and "ink" or "background")) then return false end
    end
  end
  return true
end

local function countInk(left, top, right, bottom)
  local screen = emu.getScreenBuffer()
  local count = 0
  for y = top, bottom do
    for x = left, right do
      if isInk(screen[y * SCREEN_WIDTH + x + 1]) then count = count + 1 end
    end
  end
  return count
end

local function checkCursor(selected)
  local cursorRows = {
    {24, 33},
    {36, 45},
    {48, 57},
    {60, 69},
  }
  for index, range in ipairs(cursorRows) do
    local ink = countInk(16, range[1], 22, range[2])
    if index == selected then
      if not check(ink >= 8, string.format(
        "post-rescue cursor is missing from left row %d", index))
        then return false end
    elseif not check(ink == 0, string.format(
      "post-rescue stray cursor/graphic in left row %d", index))
      then return false end
  end
  return check(countInk(66, 22, 71, 69) == 0,
    "post-rescue cursor/garbage appeared in the right spill column")
end

local function checkWideFrame()
  if not check(wideTop and wideBottom,
    "post-rescue menu did not copy a nine-column frame") then return false end
  if not check(labels[0x80] and labels[0x7F] and labels[0x92] and labels[0x9E],
    "post-rescue menu labels were not rebuilt") then return false end
  if not check(emu.read(SAVED_FLAG, workMem) == 0xA5 and
      emu.read(SAVED_FLAG_END, workMem) == 0x5A,
    "post-rescue saved-column lifecycle flag is not live") then return false end

  local low = emu.read(SAVED_DESTINATION, workMem)
  local high = emu.read(SAVED_DESTINATION + 1, workMem)
  local destination = high * 0x100 + low
  local rows = emu.read(SAVED_ROWS, workMem)
  if not check(rows >= 2 and rows <= 10,
    "post-rescue saved row count is outside the popup range") then return false end
  for row = 0, rows - 1 do
    local address = popupRowAddress(destination, row)
    local expectedTile = row == 0 and 0x7E or
      (row == rows - 1 and 0x7E or 0x7F)
    local expectedAttribute = row == rows - 1 and 0xEF or 0xAF
    if not check(readVram(address, 0) == expectedTile,
      string.format("post-rescue right-border tile missing at row %d", row))
      then return false end
    if not check(readVram(address, 1) == expectedAttribute,
      string.format("post-rescue right-border attribute wrong at row %d", row))
      then return false end
  end
  for row = 1, rows - 2 do
    local address = popupRowAddress(destination - 1, row)
    local expectedTile = row == 2 and STAGED_SUFFIX_TILES[1] or
      (row == 3 and STAGED_SUFFIX_TILES[2] or SERVICE_BLANK_TILE)
    if not check(readVram(address, 0) == expectedTile,
      string.format("post-rescue spill row %d uses garbage tile", row))
      then return false end
  end
  local spillAddress = popupRowAddress(destination - 1, 1)
  local rendererBank = (readVram(spillAddress, 1) & 0x08) ~= 0 and 1 or 0
  local blankAddress = 0x8000 + SERVICE_BLANK_TILE * 16
  for _, tile in ipairs(CURSOR_OWNED_TILES) do
    local tileAddress = 0x8000 + tile * 16
    for offset = 0, 15 do
      if not check(
        readVram(tileAddress + offset, rendererBank) ==
          readVram(blankAddress + offset, rendererBank),
        string.format(
          "post-rescue cursor tile $%02X was not cleared at byte %d",
          tile, offset)) then return false end
    end
  end
  return checkFinalD()
end

local function afterFrame()
  if not loaded or finished then return end
  if menuAt == nil and targetMenuActive() then
    menuAt = frame
    report(string.format("post-rescue delivery menu reached at frame %d", frame))
  elseif menuAt ~= nil and frame == menuAt + 120 then
    saveScreenshot()
    if not checkWideFrame() then return end
    if not checkCursor(1) then return end
    approvedPopup = capturePopup()
    overwriteCursorOwnedTiles()
    report("post-rescue cursor-owned tiles overwritten after approved render")
  elseif menuAt ~= nil and frame == menuAt + 125 then
    if not checkFinalD() then return end
    if not checkPopupUnchanged() then return end
  elseif menuAt ~= nil and frame == menuAt + 155 then
    if not checkFinalD() then return end
    if not checkCursor(2) then return end
  elseif menuAt ~= nil and frame == menuAt + 185 then
    if not checkFinalD() then return end
    if not checkCursor(3) then return end
  elseif menuAt ~= nil and frame == menuAt + 215 then
    if not checkFinalD() then return end
    if not checkCursor(4) then return end
    report("PASS post-rescue popup survives every live cursor position")
    finished = true
    emu.stop(0)
  elseif frame > 5000 then
    check(false, "timed out before post-rescue delivery menu")
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
