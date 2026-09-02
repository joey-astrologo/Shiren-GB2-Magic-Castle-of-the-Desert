-- Exercise message-specific editing through the user-supplied death fixture.
-- This route uses controller input only and never writes emulated memory.

local frame = 0
local loaded = false
local finished = false
local rankingAt = nil
local editorAt = nil
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local cpuMem = emu.memType.gameboyMemory
local FOOTER = {0x0A, 0x24, 0x0B, 0x44, 0x43, 0x43, 0x3E, 0x3D}
local scenario = assert(os.getenv("GB2_RANKING_NOTE_SCENARIO"))
local sequences = {
  right = {"up", "right", "a"},
  space = {"up", "right", "down", "right", "a"},
}
local sequence = assert(sequences[scenario], "unknown ranking-note scenario")

local function loadFile(path)
  local file = assert(io.open(path, "rb"))
  local data = file:read("*all")
  file:close()
  return data
end

local function report(message)
  print(message)
  emu.log(message)
end

local function matches(address, pattern)
  for index, value in ipairs(pattern) do
    if emu.read(address + index - 1, workMem) ~= value then return false end
  end
  return true
end

local function find(pattern)
  for address = 0, 0x7FFF - #pattern do
    if matches(address, pattern) then return address end
  end
  return nil
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_DEATH_RANKINGS_MSS"))))
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
  if frame >= 60 and frame < 65 then input.a = true end
  if rankingAt == nil and frame >= 180 and frame % 120 < 5 then input.a = true end
  if rankingAt ~= nil and editorAt == nil and frame >= rankingAt + 30 then
    local sinceRanking = frame - rankingAt - 30
    if sinceRanking % 120 < 5 then input.start = true end
  end
  if editorAt ~= nil then
    for index, button in ipairs(sequence) do
      pressAt(input, editorAt + 60 + (index - 1) * 30, button)
    end
  end
  emu.setInput(input, 0)
end

local function finish(ok, message)
  report((ok and "PASS " or "FAIL ") .. message)
  finished = true
  emu.stop(ok and 0 or 1)
end

local function afterFrame()
  if not loaded or finished then return end
  if rankingAt == nil then
    if find(FOOTER) ~= nil then rankingAt = frame end
  elseif editorAt == nil then
    if emu.read(0xC195, cpuMem) == 2 then editorAt = frame end
  else
    local doneAt = editorAt + 60 + (#sequence - 1) * 30 + 20
    if frame == doneAt then
      local position = emu.read(0xC152, cpuMem)
      local first = emu.read(0xC16D, cpuMem)
      local cursor = emu.read(0xC14F, cpuMem)
      local navigation = emu.read(0xC14E, cpuMem)
      local graph0 = ""
      for offset = 0, 6 do
        graph0 = graph0 .. string.format("%02X", emu.read(0xC800 + offset, cpuMem))
      end
      if scenario == "right" then
        finish(
          position == 1 and first == 0x24,
          string.format(
            "mode-2 right arrow pads a space and advances " ..
            "(position=%d first=$%02X cursor=$%02X nav=$%02X graph0=%s)",
            position, first, cursor, navigation, graph0))
      else
        finish(
          position == 1 and first == 0x24,
          string.format(
            "mode-2 empty keyboard cell inserts space " ..
            "(position=%d first=$%02X cursor=$%02X nav=$%02X graph0=%s)",
            position, first, cursor, navigation, graph0))
      end
      return
    end
  end
  if frame > 1400 then finish(false, "ranking-note editing route timed out") end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
