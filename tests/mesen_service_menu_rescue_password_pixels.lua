-- Pixel-level regression for the final `d` in Rescue Team -> Password.
--
-- This deliberately does not consume a framebuffer checksum.  The expected
-- five-pixel-wide raster below is the approved lowercase-d glyph itself, and
-- the route rebuilds the popup from controller input so stale savestate tiles
-- cannot satisfy the assertion.

local frame = 0
local loaded = false
local finished = false
local SCREEN_WIDTH = 160
local D_X = 61
local D_Y = 37
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
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_ENTRY_MSS"))))
  report("service-menu Rescue final-d fixture loaded")
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
  emu.setInput(input, 0)
end

local function isInk(pixel)
  return (pixel & 0x00FFFFFF) == 0
end

local function afterFrame()
  if not loaded or finished then return end
  if frame == 790 then
    local screen = emu.getScreenBuffer()
    for row, expectedRow in ipairs(EXPECTED_D) do
      for column = 1, #expectedRow do
        local x = D_X + column - 1
        local y = D_Y + row - 1
        local expectedInk = expectedRow:sub(column, column) == "#"
        local actualInk = isInk(screen[y * SCREEN_WIDTH + x + 1])
        if not check(actualInk == expectedInk, string.format(
          "Rescue Password final d pixel (%d,%d) expected %s, got %s",
          x, y, expectedInk and "ink" or "background",
          actualInk and "ink" or "background")) then return end
      end
    end
    report("PASS Rescue Password final d matches the approved raster")
    finished = true
    emu.stop(0)
  elseif frame > 900 then
    check(false, "timed out while checking Rescue Password final d")
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
