-- Exact regression for the user-supplied Blank Scroll confirmation failure.
--
-- The fixture is already on the English naming screen with Windblade entered,
-- its notebook bit learned, and a populated live inventory. Confirming used to
-- overwrite wInputMode with the ninth character and restart the game.

local frame = 0
local loaded = false
local resetObserved = false
local matchObserved = false
local nativeTailObserved = false
local convertedFrame = nil
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local cartMem = emu.memType.gbCartRam

local INPUT = 0xC16D
local INPUT_LENGTH = 0xC152
local INPUT_MAXIMUM = 0xC153
local INPUT_MODE = 0xC195
local MATCH_CACHE = 0xC196
local SELECTED_SLOT = 0xC156
local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local BLANK_SCROLL = 0x92
local WINDBLADE_SCROLL = 0x7F
local WINDBLADE_ROOT = 0x32
local WINDBLADE_HISTORY = 0x2E22
local WINDBLADE_HISTORY_MASK = 0x04
local WINDBLADE = { 0x20, 0x38, 0x3D, 0x33, 0x31, 0x3B, 0x30, 0x33, 0x34 }

local fixtureObject = nil
local inventoryBefore = {}
local objectBefore = {}

local function report(message)
  print(message)
  emu.log(message)
end

local function rd(address, memType)
  return emu.read(address, memType)
end

local function loadFile(path)
  local file = assert(io.open(path, "rb"))
  local data = file:read("*all")
  file:close()
  return data
end

local function assertInventoryUnchanged()
  for slot = 0, INVENTORY_SLOTS - 1 do
    assert(
      rd(INVENTORY + slot, workMem) == inventoryBefore[slot + 1],
      string.format("inventory slot %d changed", slot)
    )
  end
end

local function loadFixture()
  if loaded then return end
  loaded = true
  assert(workMem ~= nil, "Mesen does not expose flat Game Boy Work RAM")
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_MSS_PATH"))))

  local srmPath = os.getenv("GB2_SRM_PATH")
  if srmPath ~= nil and srmPath ~= "" then
    assert(cartMem ~= nil, "Mesen does not expose Game Boy cartridge RAM")
    local srm = loadFile(srmPath)
    assert(#srm == emu.getMemorySize(cartMem), "unexpected SRAM fixture size")
    for address = 0, #srm - 1 do
      emu.write(address, string.byte(srm, address + 1), cartMem)
    end
  end

  assert(rd(INPUT_MODE, cpuMem) == 1, "fixture is not in Blank Scroll mode")
  assert(rd(INPUT_LENGTH, cpuMem) == #WINDBLADE, "fixture input length changed")
  assert(rd(INPUT_MAXIMUM, cpuMem) == 11, "fixture input maximum changed")
  for offset, value in ipairs(WINDBLADE) do
    assert(rd(INPUT + offset - 1, cpuMem) == value, "fixture text is not Windblade")
  end
  local endByte = rd(INPUT + #WINDBLADE, cpuMem)
  assert(
    endByte == 0xD5 or endByte == 0xFF,
    "fixture has an unexpected byte after Windblade"
  )
  assert(
    (rd(WINDBLADE_HISTORY, workMem) & WINDBLADE_HISTORY_MASK) ~= 0,
    "Windblade is not learned in fixture"
  )

  local selected = rd(SELECTED_SLOT, cpuMem)
  fixtureObject = rd(INVENTORY + selected, workMem)
  assert(fixtureObject ~= 0xFF, "selected inventory slot is empty")
  assert(
    rd(OBJECTS + fixtureObject * OBJECT_SIZE, workMem) == BLANK_SCROLL,
    "selected object is not a Blank Scroll"
  )
  for slot = 0, INVENTORY_SLOTS - 1 do
    inventoryBefore[slot + 1] = rd(INVENTORY + slot, workMem)
  end
  for offset = 0, OBJECT_SIZE - 1 do
    objectBefore[offset + 1] = rd(
      OBJECTS + fixtureObject * OBJECT_SIZE + offset, workMem
    )
  end
  report(string.format(
    "fixture loaded object=%02X slot=%02X mode=%02X length=%02X maximum=%02X",
    fixtureObject, selected, rd(INPUT_MODE, cpuMem),
    rd(INPUT_LENGTH, cpuMem), rd(INPUT_MAXIMUM, cpuMem)
  ))
end

local function loadOnce()
  if loaded then return end
  local ok, message = pcall(loadFixture)
  if not ok then
    report("FAIL fixture setup: " .. tostring(message))
    emu.stop(1)
  end
end

local function traceReset()
  if loaded and frame >= 55 then resetObserved = true end
end

local function inputForFrame()
  if not loaded then return end
  emu.setInput({
    a = frame >= 60 and frame < 65,
    b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }, 0)
end

local function checkAfterFrame()
  if loaded and rd(MATCH_CACHE, cpuMem) == WINDBLADE_ROOT and not matchObserved then
    matchObserved = true
    assert(rd(INPUT_MODE, cpuMem) == 1, "full-name match corrupted wInputMode")
  end
  if loaded and rd(MATCH_CACHE, cpuMem) == WINDBLADE_ROOT and
      not nativeTailObserved and rd(INPUT + 7, cpuMem) == 0xFF then
    for offset = 0, 6 do
      assert(rd(INPUT + offset, cpuMem) == WINDBLADE[offset + 1])
    end
    assert(
      rd(INPUT + 8, cpuMem) == 0xD5 or rd(INPUT + 8, cpuMem) == 0xFF,
      "native validation produced an unexpected second terminator"
    )
    for offset = 9, 11 do
      assert(rd(INPUT + offset, cpuMem) == 0xD5, "native tail padding changed")
    end
    nativeTailObserved = true
  end

  if loaded and fixtureObject ~= nil then
    local item = rd(OBJECTS + fixtureObject * OBJECT_SIZE, workMem)
    if item == WINDBLADE_SCROLL and convertedFrame == nil then
      convertedFrame = frame
      assertInventoryUnchanged()
      for offset = 1, OBJECT_SIZE - 1 do
        assert(
          rd(OBJECTS + fixtureObject * OBJECT_SIZE + offset, workMem)
            == objectBefore[offset + 1],
          string.format("object metadata byte %d changed", offset)
        )
      end
      report("fixture converted at frame " .. frame)
    end
  end

  if loaded and frame >= 100 then
    assert(not resetObserved, "Blank Scroll confirmation restarted the game")
    assert(matchObserved, "localized matcher did not resolve Windblade")
    assert(nativeTailObserved, "native seven-byte tail was not restored")
    assert(convertedFrame ~= nil, "Blank Scroll did not become Windblade Scroll")
    assertInventoryUnchanged()
    report(string.format(
      "PASS fixture match=%02X object=%02X item=%02X reset=%s",
      rd(MATCH_CACHE, cpuMem), fixtureObject,
      rd(OBJECTS + fixtureObject * OBJECT_SIZE, workMem),
      tostring(resetObserved)
    ))
    emu.stop(0)
  elseif frame >= 600 then
    error("timed out before exact Blank Scroll fixture completed")
  end
  frame = frame + 1
end

local function afterFrame()
  local ok, message = pcall(checkAfterFrame)
  if not ok then
    report("FAIL fixture route: " .. tostring(message))
    emu.stop(1)
  end
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy
)
emu.addMemoryCallback(
  traceReset, emu.callbackType.exec, 0x01C1, 0x01C1, emu.cpuType.gameboy
)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
