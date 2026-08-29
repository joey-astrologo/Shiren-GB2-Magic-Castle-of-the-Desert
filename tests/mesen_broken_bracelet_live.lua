-- Live reproduction route for the cracked-Bracelet marker.
--
-- The supplied broken-bracelet.mss starts on the Items screen with a cracked
-- Strength Bracelet selected.  Loading the state alone would retain the old
-- rendered VRAM, so this route closes and reopens Items before inspecting the
-- localized marker drawn from the current ROM.

local frame = 0
local loaded = false
local cpuMem = emu.memType.gameboyMemory
local FIXTURE_SCREEN = 0x8B2311E3
local LOCALIZED_SCREEN = 0x406EBCD1
local localizedChecksum = 0

local function report(message)
  print(message)
  emu.log(message)
end

local function screenChecksum()
  local hash = 2166136261
  for _, pixel in ipairs(emu.getScreenBuffer()) do
    hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
  end
  return hash
end

local function loadOnce()
  if loaded then return end
  loaded = true
  local file = assert(io.open(assert(os.getenv("GB2_MSS_PATH")), "rb"))
  local state = file:read("*all")
  file:close()
  emu.loadSavestate(state)
  report("broken Bracelet fixture loaded")
end

local function pressAt(input, at, button)
  if frame >= at and frame < at + 5 then input[button] = true end
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a = false, b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
  pressAt(input, 100, "b")
  pressAt(input, 220, "a")
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded then return end
  if frame == 60 or frame == 180 or frame == 360 then
    local checksum = screenChecksum()
    report(string.format(
      "broken Bracelet frame=%d screen=%08X menu=%02X cursor=%02X",
      frame, checksum, emu.read(0xC156, cpuMem),
      emu.read(0xC14F, cpuMem)
    ))
    if frame == 60 then
      assert(
        checksum == FIXTURE_SCREEN,
        string.format("unexpected supplied-state screen: %08X", checksum)
      )
    elseif frame == 360 then
      localizedChecksum = checksum
      if LOCALIZED_SCREEN ~= 0 then
        assert(
          checksum == LOCALIZED_SCREEN,
          string.format("cracked marker screen mismatch: %08X", checksum)
        )
      end
    end
  end
  if frame == 360 then
    local screenshot = os.getenv("GB2_SCREENSHOT")
    if screenshot ~= nil then
      local file = assert(io.open(screenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    report(string.format("PASS cracked marker screen=%08X", localizedChecksum))
    emu.stop(0)
  elseif frame > 600 then
    error("timed out while reproducing cracked Bracelet marker")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce,
  emu.callbackType.exec,
  0x0000,
  0xFFFF,
  emu.cpuType.gameboy
)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
