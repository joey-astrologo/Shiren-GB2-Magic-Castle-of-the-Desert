-- mesen_advance_floor.lua
-- Find the live floor's real staircase, move Shiren beside it, step onto it, and
-- accept the native Proceed prompt when one appears.
--
-- MANUAL USE
--   1. During ordinary dungeon control, close messages/menus and pause Mesen.
--   2. Open Debug > Script Window, load this file, and press Run (F5).
--   3. Resume. The helper advances through exactly one native staircase.
--   4. Once the next floor is controllable, pause and press Run (F5) again.
--
-- This deliberately uses the generated staircase object and the game's own floor
-- transition. It does not increment the displayed floor byte, so final-floor events,
-- dungeon exits, inventory rules, and ending gates remain under native control.

local LABEL = "Advance one floor"
local PLAYER_ACTOR_WRAM = 0x1000
local ACTOR_CACHE = 0xFF90
local ACTIVE_ACTOR = 0xFFFC
local ACTOR_SIZE = 0x20
local X_OFFSET = 0x03
local Y_OFFSET = 0x04
local HIGH_RAM_CPU_BASE = 0xFF80

local DUNGEON = 0x012C
local FLOOR = 0x0130
local TERRAIN_GRID = 0x3000
local ACTOR_GRID = 0x3400
local FLOOR_OBJECT_GRID = 0x3800
local TRAP_GRID = 0x3C00
local MAP_WIDTH = 32
local MAP_CELLS = 0x400
local EMPTY = 0xFF

local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local STAIR_ITEM = 0xCA
local STAIR_CLASS = 0x0C

local MOVE_PRESS_POLLS = 5
local PROMPT_WAIT_FRAMES = 180
local CONFIRM_PRESS_POLLS = 5
local MOVE_TIMEOUT_FRAMES = 300
local TRANSITION_TIMEOUT_FRAMES = 900

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

local workMem, workMemName = pick(
    emu.memType, { "gbWorkRam", "gameboyWorkRam" })
local highMem, highMemName = pick(
    emu.memType, { "gbHighRam", "gameboyHighRam" })

local function report(message)
  print(message)
  emu.log(message)
end

local function fail(message)
  report(LABEL .. ": FAILED: " .. message)
  return false
end

local function readWork(address)
  if workMem == nil then return nil end
  local ok, value = pcall(emu.read, address, workMem)
  if not ok then return nil end
  return value
end

local function readHigh(address)
  if highMem == nil or address < HIGH_RAM_CPU_BASE then return nil end
  local ok, value = pcall(emu.read, address - HIGH_RAM_CPU_BASE, highMem)
  if not ok then return nil end
  return value
end

local function writeWork(address, value)
  local ok = pcall(emu.write, address, value, workMem)
  return ok and readWork(address) == value
end

local function writeHigh(address, value)
  local ok = pcall(emu.write, address - HIGH_RAM_CPU_BASE, value, highMem)
  return ok and readHigh(address) == value
end

local function cellAddress(base, x, y)
  return base + y * MAP_WIDTH + x
end

local function isStairAt(x, y)
  if x < 0 or x >= MAP_WIDTH or y < 0 or y >= MAP_WIDTH then return false end
  local object = readWork(cellAddress(FLOOR_OBJECT_GRID, x, y))
  if object == nil or object == EMPTY or object >= OBJECT_COUNT then return false end
  local base = OBJECTS + object * OBJECT_SIZE
  return readWork(base) == STAIR_ITEM and readWork(base + 1) == STAIR_CLASS
end

local function neutralInput()
  return {
    a = false, b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
end

local function beginAdvance()
  if _G.GB2_FLOOR_ADVANCE_ACTIVE then
    return fail("an earlier one-floor transition is still active")
  end
  if workMem == nil or highMem == nil then
    return fail("this Mesen build does not expose the required GB memory domains")
  end
  if emu.eventType == nil or emu.eventType.inputPolled == nil
      or emu.eventType.endFrame == nil then
    return fail("this Mesen build does not expose the required input/frame callbacks")
  end
  if readHigh(ACTIVE_ACTOR) ~= 0 then
    return fail("active actor is not Shiren/actor 0; return to ordinary dungeon play")
  end
  for offset = 0, ACTOR_SIZE - 1 do
    local backing = readWork(PLAYER_ACTOR_WRAM + offset)
    local cached = readHigh(ACTOR_CACHE + offset)
    if backing == nil or cached == nil or backing ~= cached then
      return fail(string.format(
          "actor cache is unavailable or differs from bank-1 record at +$%02X", offset))
    end
  end

  local stairs = {}
  for cell = 0, MAP_CELLS - 1 do
    local x = cell % MAP_WIDTH
    local y = math.floor(cell / MAP_WIDTH)
    if isStairAt(x, y) then stairs[#stairs + 1] = { x = x, y = y } end
  end
  if #stairs == 0 then
    return fail("no native staircase object is present (this may be a boss/event floor)")
  end
  if #stairs > 1 then
    return fail("more than one native staircase is present; refusing to choose a route")
  end

  local stairX = stairs[1].x
  local stairY = stairs[1].y
  local oldX = readHigh(ACTOR_CACHE + X_OFFSET)
  local oldY = readHigh(ACTOR_CACHE + Y_OFFSET)
  if oldX == nil or oldY == nil or oldX >= MAP_WIDTH or oldY >= MAP_WIDTH then
    return fail("Shiren's live map position is invalid")
  end
  if readWork(cellAddress(ACTOR_GRID, oldX, oldY)) ~= 0 then
    return fail("the actor grid does not identify Shiren at his cached position")
  end

  local candidates = {
    { x = stairX,     y = stairY - 1, button = "down"  },
    { x = stairX,     y = stairY + 1, button = "up"    },
    { x = stairX - 1, y = stairY,     button = "right" },
    { x = stairX + 1, y = stairY,     button = "left"  },
  }

  local function candidateIsSafe(candidate)
    local x, y = candidate.x, candidate.y
    if x <= 0 or x >= MAP_WIDTH - 1 or y <= 0 or y >= MAP_WIDTH - 1 then return false end
    local terrain = readWork(cellAddress(TERRAIN_GRID, x, y))
    local actor = readWork(cellAddress(ACTOR_GRID, x, y))
    local object = readWork(cellAddress(FLOOR_OBJECT_GRID, x, y))
    local trap = readWork(cellAddress(TRAP_GRID, x, y))
    if terrain == nil or (terrain & 0x80) == 0 then return false end
    local isCurrent = x == oldX and y == oldY
    if (isCurrent and actor ~= 0) or (not isCurrent and actor ~= EMPTY) then return false end
    return object == EMPTY and trap == EMPTY
  end

  local source = nil
  for _, candidate in ipairs(candidates) do
    if candidate.x == oldX and candidate.y == oldY and candidateIsSafe(candidate) then
      source = candidate
      break
    end
  end
  if source == nil then
    for _, candidate in ipairs(candidates) do
      if candidateIsSafe(candidate) then source = candidate break end
    end
  end
  if source == nil then
    return fail("the staircase has no clear, walkable adjacent setup tile")
  end

  if source.x ~= oldX or source.y ~= oldY then
    local oldCell = cellAddress(ACTOR_GRID, oldX, oldY)
    local newCell = cellAddress(ACTOR_GRID, source.x, source.y)
    local writes = {
      { "work", oldCell, EMPTY, 0 },
      { "work", newCell, 0, EMPTY },
      { "work", PLAYER_ACTOR_WRAM + X_OFFSET, source.x, oldX },
      { "work", PLAYER_ACTOR_WRAM + Y_OFFSET, source.y, oldY },
      { "high", ACTOR_CACHE + X_OFFSET, source.x, oldX },
      { "high", ACTOR_CACHE + Y_OFFSET, source.y, oldY },
    }
    local applied = 0
    for index, row in ipairs(writes) do
      local ok
      if row[1] == "work" then ok = writeWork(row[2], row[3])
      else ok = writeHigh(row[2], row[3]) end
      if not ok then
        for rollback = applied, 1, -1 do
          local old = writes[rollback]
          if old[1] == "work" then writeWork(old[2], old[4])
          else writeHigh(old[2], old[4]) end
        end
        return fail("could not synchronize the staircase setup position; changes were rolled back")
      end
      applied = index
    end
  end

  local oldDungeon = readWork(DUNGEON)
  local oldFloor = readWork(FLOOR)
  local polls = 0
  local frames = 0
  local confirmAt = nil
  local confirmSent = false
  local finished = false
  local inputReference = nil
  local frameReference = nil

  local function cleanup()
    pcall(emu.setInput, neutralInput(), 0)
    if inputReference ~= nil then
      pcall(emu.removeEventCallback, inputReference, emu.eventType.inputPolled)
      inputReference = nil
    end
    if frameReference ~= nil then
      pcall(emu.removeEventCallback, frameReference, emu.eventType.endFrame)
      frameReference = nil
    end
    _G.GB2_FLOOR_ADVANCE_ACTIVE = false
  end

  local function finish(message)
    if finished then return end
    finished = true
    report(LABEL .. ": " .. message)
    cleanup()
  end

  local function inputForFrame()
    if finished then return end
    local input = neutralInput()
    if polls < MOVE_PRESS_POLLS then
      input[source.button] = true
    elseif confirmAt ~= nil and polls >= confirmAt
        and polls < confirmAt + CONFIRM_PRESS_POLLS then
      input.a = true
      confirmSent = true
    end
    emu.setInput(input, 0)
    polls = polls + 1
  end

  local function afterFrame()
    if finished then return end
    frames = frames + 1
    local x = readHigh(ACTOR_CACHE + X_OFFSET)
    local y = readHigh(ACTOR_CACHE + Y_OFFSET)
    local dungeon = readWork(DUNGEON)
    local floor = readWork(FLOOR)

    if dungeon ~= oldDungeon or floor ~= oldFloor then
      finish(string.format(
          "native transition completed (dungeon $%02X, floor byte $%02X -> $%02X).",
          dungeon or 0, oldFloor or 0, floor or 0))
      return
    end

    if confirmAt == nil and frames >= PROMPT_WAIT_FRAMES
        and (x ~= source.x or y ~= source.y or not isStairAt(stairX, stairY)) then
      confirmAt = polls
      -- The native stairs route can preload the next spawn coordinates before its
      -- Proceed popup is accepted, so a changed actor position is not completion.
      report(LABEL .. ": staircase entered; sending A for Proceed if required.")
      return
    end

    if confirmAt == nil and frames >= MOVE_TIMEOUT_FRAMES
        and x == source.x and y == source.y then
      finish("FAILED: movement did not enter the staircase; close menus/messages and try again.")
      return
    end

    if confirmSent and frames >= TRANSITION_TIMEOUT_FRAMES then
      if not isStairAt(stairX, stairY) then
        finish("native staircase was consumed; an event/ending transition is in progress.")
      else
        finish("confirmation was sent; wait for the current native event before running again.")
      end
    end
  end

  _G.GB2_FLOOR_ADVANCE_ACTIVE = true
  inputReference = emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
  frameReference = emu.addEventCallback(afterFrame, emu.eventType.endFrame)
  report(string.format(
      "%s ARMED: Shiren (%d,%d), stairs (%d,%d), input=%s. Resume now.",
      LABEL, source.x, source.y, stairX, stairY, source.button))
  return true
end

_G.gb2AdvanceOneFloor = beginAdvance
beginAdvance()
