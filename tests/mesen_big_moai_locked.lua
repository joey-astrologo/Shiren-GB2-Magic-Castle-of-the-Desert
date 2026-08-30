-- Preserve the exact user-reported Big Moai lock as a live regression.
-- The fixture must select dialogue group $6A index $0D and must not reach the
-- mode-3 spell editor without the explicit test helper.

local frame = 0
local loaded = false
local lockedDialogueSeen = false
local cpuMem = emu.memType.gameboyMemory
local EXPECTED_PROMPT_SCREEN = tonumber(
  assert(os.getenv("GB2_BIG_MOAI_PROMPT_SCREEN")), 16)

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

local function checksum()
  local hash = 2166136261
  for _, pixel in ipairs(emu.getScreenBuffer()) do
    hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
  end
  return hash
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_BIG_MOAI_MSS"))))
  assert(emu.read(0xC3EF, cpuMem) == 0x06, "fixture active story stage changed")
  assert(emu.read(0xC3F0, cpuMem) == 0x06, "fixture story-stage shadow changed")
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a = frame >= 120 and frame < 125,
    b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
  emu.setInput(input, 0)
end

local function traceTextLookup()
  if not loaded then return end
  local state = emu.getState()
  if state["cpu.a"] == 0x6A and state["cpu.c"] == 0x0D then
    lockedDialogueSeen = true
    report("locked Big Moai dialogue group=6A index=0D")
  end
end

local function afterFrame()
  if not loaded then return end
  if frame == 150 then
    assert(lockedDialogueSeen, "fixture did not select the locked Big Moai branch")
    assert(emu.read(0xC195, cpuMem) ~= 0x03, "locked fixture reached spell input")
    local screen = checksum()
    assert(screen == EXPECTED_PROMPT_SCREEN, string.format(
      "locked Big Moai prompt mismatch: %08X", screen))
    report(string.format(
      "PASS big-moai-locked stage=06/06 dialogue=6A:0D screen=%08X", screen))
    emu.stop(0)
  elseif frame > 300 then
    error("timed out before reaching locked Big Moai dialogue")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addMemoryCallback(
  traceTextLookup, emu.callbackType.exec, 0x1F58, 0x1F58, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
