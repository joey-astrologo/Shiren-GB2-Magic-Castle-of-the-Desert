-- Pixel-level regression for Blacksmith -> Info -> Synthesis.
--
-- This deliberately does not consume a framebuffer checksum. The expected
-- 45x8 raster below is the approved Thin Pixel-7 word itself. The route opens
-- both menus through controller input, so pixels embedded in the savestate
-- cannot satisfy the assertion.

local frame = 0
local loaded = false
local finished = false
local SCREEN_WIDTH = 160
local SYNTHESIS_X = 24
local SYNTHESIS_Y = 48
local QUIT_Y = 72
local QUIT_CURSOR_X = 16
local QUIT_SPILL_X = 64
local EXPECTED_SYNTHESIS = {
  ".####............#...#...............#.......",
  "#................#...#.......................",
  "#.....#..#.###..###..###...##...###.##...###.",
  ".###..#..#.#..#..#...#..#.#..#.#.....#..#....",
  "....#.#..#.#..#..#...#..#.####..##...#...##..",
  "....#..###.#..#..#...#..#.#.......#..#.....#.",
  "####.....#.#..#...##.#..#..###.###..###.###..",
  ".......##....................................",
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
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_BLACKSMITH_INFO_MSS"))))
  report("service-menu Blacksmith Info pixel fixture loaded")
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
  emu.setInput(input, 0)
end

local function isInk(pixel)
  return (pixel & 0x00FFFFFF) == 0
end

local function afterFrame()
  if not loaded or finished then return end
  if frame == 480 then
    local screen = emu.getScreenBuffer()
    for row, expectedRow in ipairs(EXPECTED_SYNTHESIS) do
      for column = 1, #expectedRow do
        local x = SYNTHESIS_X + column - 1
        local y = SYNTHESIS_Y + row - 1
        local expectedInk = expectedRow:sub(column, column) == "#"
        local actualInk = isInk(screen[y * SCREEN_WIDTH + x + 1])
        if not check(actualInk == expectedInk, string.format(
          "Blacksmith Info Synthesis pixel (%d,%d) expected %s, got %s",
          x, y, expectedInk and "ink" or "background",
          actualInk and "ink" or "background")) then return end
      end
    end
    for y = QUIT_Y, QUIT_Y + 7 do
      for x = QUIT_CURSOR_X, QUIT_CURSOR_X + 7 do
        if not check(not isInk(screen[y * SCREEN_WIDTH + x + 1]),
          string.format("Blacksmith Info stray glyph in Quit cursor cell at (%d,%d)",
            x, y)) then return end
      end
      for x = QUIT_SPILL_X, QUIT_SPILL_X + 7 do
        if not check(not isInk(screen[y * SCREEN_WIDTH + x + 1]),
          string.format("Blacksmith Info garbage right of Quit at (%d,%d)",
            x, y)) then return end
      end
    end
    report("PASS Blacksmith Info Synthesis and clean Quit row match approved pixels")
    finished = true
    emu.stop(0)
  elseif frame > 600 then
    check(false, "timed out while checking Blacksmith Info pixels")
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
