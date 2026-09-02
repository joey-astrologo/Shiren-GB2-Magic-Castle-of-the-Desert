-- Replay the user-supplied one-HP state through death, then open the
-- Rankings note editor with Start.  The Python regression owns the expected
-- English pixels; this helper deliberately contains no framebuffer hash.

local frame = 0
local loaded = false
local finished = false
local rankingAt = nil
local editorAt = nil
local lastMode = nil
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local cpuMem = emu.memType.gameboyMemory
local FOOTER = {0x0A, 0x24, 0x0B, 0x44, 0x43, 0x43, 0x3E, 0x3D}

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
  report("death-Rankings fixture loaded")
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a=false, b=false, start=false, select=false,
    up=false, down=false, left=false, right=false,
  }
  -- Attack the adjacent Mamel at one HP.  Thereafter advance only the death
  -- dialogue, stopping as soon as the footer is detected.
  if frame >= 60 and frame < 65 then input.a = true end
  if rankingAt == nil and frame >= 180 and frame % 120 < 5 then input.a = true end
  if rankingAt ~= nil and editorAt == nil and frame >= rankingAt + 30 then
    local sinceRanking = frame - rankingAt - 30
    if sinceRanking % 120 < 5 then input.start = true end
  end
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded or finished then return end
  if rankingAt == nil then
    local address = find(FOOTER)
    if address ~= nil then
      rankingAt = frame
      report(string.format("death Rankings footer found at frame %d", frame))
    end
  elseif editorAt == nil then
    local mode = emu.read(0xC195, cpuMem)
    if mode ~= lastMode then
      lastMode = mode
      report(string.format("post-Rankings input mode is %d at frame %d", mode, frame))
    end
    if mode == 2 then
      local maximum = emu.read(0xC153, cpuMem)
      if maximum ~= 13 then
        error(string.format(
          "ranking-note maximum changed: got %d, expected 13", maximum))
      end
      editorAt = frame
      report(string.format(
        "ranking-note input mode 2 found at frame %d with 13-character maximum",
        frame))
    end
  elseif editorAt ~= nil and frame == editorAt + 120 then
    local path = assert(os.getenv("GB2_RANKING_NOTE_SCREENSHOT"))
    local file = assert(io.open(path, "wb"))
    file:write(emu.takeScreenshot())
    file:close()
    report("PASS captured live ranking-note editor")
    finished = true
    emu.stop(0)
    return
  end
  if frame > 1200 then
    error("timed out before the ranking-note editor opened")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
