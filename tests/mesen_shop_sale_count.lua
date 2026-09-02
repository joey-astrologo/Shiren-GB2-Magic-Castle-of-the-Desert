-- Multiple-item shop-sale formatter regression.
--
-- Starts from the user-supplied four-item selection, confirms it through the
-- real controller path, and inspects the live expanded dialogue buffer.  The
-- native formatter appends hiragana `ko` ($39) as an item counter; after the
-- English font patch that byte paints as `j`.

local frame = 0
local loaded = false
local finished = false
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local LEAKED = {0x04, 0x39, 0x4F} -- `4j!`
local ENGLISH = {
  0x04, 0x24, 0x38, 0x43, 0x34, 0x3C, 0x42, 0x4B, 0x24,
  0x41, 0x38, 0x36, 0x37, 0x43, 0x4E, -- `4 items, right?`
}

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
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_MULTIPLE_SALE_MSS"))))
  report("multiple-sale fixture loaded")
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a = frame >= 60 and frame < 65,
    b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded or finished then return end
  if frame >= 60 then
    local english = find(ENGLISH)
    if english ~= nil then
      report(string.format(
        "PASS multiple sale renders 4 items, right? at WRAM+$%04X", english))
      finished = true
      emu.stop(0)
      return
    end
    local leaked = find(LEAKED)
    if leaked ~= nil then
      report(string.format(
        "FAIL Japanese item counter leaked as 4j! at WRAM+$%04X", leaked))
      finished = true
      emu.stop(1)
      return
    end
  end
  if frame > 900 then
    report("FAIL multiple-sale dialogue was not found in live WRAM")
    finished = true
    emu.stop(1)
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
