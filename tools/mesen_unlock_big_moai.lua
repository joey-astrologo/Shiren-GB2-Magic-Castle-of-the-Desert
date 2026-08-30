-- mesen_unlock_big_moai.lua
-- Raise only the minimum story-stage gate needed to test Big Moai's spell
-- editor. The game will serialize the two changed progression bytes normally
-- on its next save; this helper never writes battery SRAM directly.
--
-- MANUAL USE
--   1. Back up the save RAM beside the ROM and use a disposable save state.
--   2. Stand in front of Big Moai in town and pause Mesen.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Resume and speak to Big Moai. Enter WISH to receive Fortune Grass.
--
-- The helper changes only WRAM $C3EF and its saved shadow at $C3F0, setting
-- each to the native minimum stage $09. It refuses an inconsistent pair.

local LABEL = "Big Moai unlock"
local STAGE_OFFSET = 0x03EF
local STAGE_SHADOW_OFFSET = 0x03F0
local MINIMUM_STAGE = 0x09

local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local function report(message)
  print(message)
  emu.log(message)
end

local function fail(message)
  report(LABEL .. ": FAILED: " .. message)
  return false, false
end

local function rd(address)
  if workMem == nil then return nil end
  local ok, value = pcall(emu.read, address, workMem)
  if not ok then return nil end
  return value
end

local function wr(address, value)
  if workMem == nil then return false end
  local ok = pcall(emu.write, address, value, workMem)
  return ok and rd(address) == value
end

local function unlockBigMoai()
  if workMem == nil then
    return fail("this Mesen build does not expose flat Game Boy Work RAM")
  end
  local stage = rd(STAGE_OFFSET)
  local shadow = rd(STAGE_SHADOW_OFFSET)
  if stage == nil or shadow == nil then
    return fail("could not read the story-stage pair")
  end
  if stage ~= shadow then
    return fail(string.format(
      "story stage $%02X and saved shadow $%02X differ; no bytes were changed",
      stage, shadow))
  end
  if stage >= MINIMUM_STAGE then
    report(string.format(
      "%s: already available (story stage $%02X)", LABEL, stage))
    return true, false, stage
  end

  if not wr(STAGE_OFFSET, MINIMUM_STAGE) then
    return fail("could not update the active story stage")
  end
  if not wr(STAGE_SHADOW_OFFSET, MINIMUM_STAGE) then
    wr(STAGE_OFFSET, stage)
    return fail("could not update the saved stage shadow; change was rolled back")
  end
  report(string.format(
    "%s: story stage $%02X -> $%02X. Resume and speak to Big Moai.",
    LABEL, stage, MINIMUM_STAGE))
  return true, true, stage
end

_G.gb2UnlockBigMoai = unlockBigMoai

local fixturePath = os.getenv("GB2_BIG_MOAI_MSS")
local libraryMode = os.getenv("GB2_BIG_MOAI_LIBRARY") == "1"
if libraryMode then
  -- The live route below imports this exact implementation.
elseif fixturePath == nil or fixturePath == "" then
  unlockBigMoai()
else
  local loaded = false
  local checked = false

  local function loadFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*all")
    file:close()
    return data
  end

  local function loadOnce()
    if loaded then return end
    loaded = true
    emu.loadSavestate(loadFile(fixturePath))

    local before = {}
    for address = 0x03E0, 0x03FF do before[address] = rd(address) end
    local ok, changed, oldStage = unlockBigMoai()
    assert(ok and changed, "locked fixture was not minimally unlocked")
    assert(oldStage == 0x06, "locked fixture story stage changed")

    local differences = {}
    for address = 0x03E0, 0x03FF do
      if rd(address) ~= before[address] then
        differences[#differences + 1] = address
      end
    end
    assert(#differences == 2, "unlock changed an unexpected number of WRAM bytes")
    assert(differences[1] == STAGE_OFFSET, "active-stage byte was not the first change")
    assert(differences[2] == STAGE_SHADOW_OFFSET, "stage shadow was not the second change")
    checked = true
  end

  local function afterFrame()
    if not loaded then return end
    assert(checked, "Big Moai fixture check did not run")
    report(string.format(
      "PASS big-moai-unlock stage=%02X/%02X changed=%04X,%04X",
      rd(STAGE_OFFSET), rd(STAGE_SHADOW_OFFSET),
      STAGE_OFFSET, STAGE_SHADOW_OFFSET))
    emu.stop(0)
  end

  emu.addMemoryCallback(
    loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
  emu.addEventCallback(afterFrame, emu.eventType.endFrame)
end
