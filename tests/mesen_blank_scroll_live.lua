-- Mesen regression route for English Blank Scroll writing.
--
-- Run with Mesen's headless test runner. The script loads the checked-in Mamel
-- state, injects one Blank Scroll plus the Windblade notebook bit, enters the
-- full name through the physical English keyboard, confirms it, and requires
-- the live inventory object to become a Windblade Scroll.

local frame = 0
local loaded = false
local editorFrame = nil
local confirmedFrame = nil
local convertedFrame = nil
local activeButton = nil
local lastInputLength = nil
local lastInputNode = nil
local lastInputMatch = nil

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

local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local HISTORY = 0x2E1C
local BLANK_ID = 0x92
local WINDBLADE_ID = 0x7F
local WINDBLADE_ROOT = 50
local GAMEPLAY_SCREEN_CHECKSUM = 0xA99BBFF6
local expectMatch = os.getenv("GB2_EXPECT_MATCH") ~= "0"

local opening = {
  { 100, "b" },
  { 200, "a" },
  { 300, "down" },
  { 500, "a" },
  { 600, "down" },
  { 700, "a" },
}

-- Shortest paths through the actual native navigation graph, starting at A,
-- followed by A on each character and on the OK node. This spells Windblade.
local keyboard = {
  "up", "up", "up", "right", "right", "a",
  "down", "up", "left", "up", "up", "left", "a",
  "down", "a",
  "up", "up", "a",
  "left", "left", "a",
  "down", "down", "a",
  "up", "up", "left", "a",
  "right", "right", "right", "a",
  "right", "a",
  "up", "up", "a",
}

local function rd(address, memType)
  return emu.read(address, memType)
end

local function wr(address, value, memType)
  emu.write(address, value, memType)
  assert(rd(address, memType) == value)
end

local function inject()
  assert(workMem ~= nil, "Mesen does not expose flat Game Boy Work RAM")
  local occupied = {}
  local freeSlot = nil
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object = rd(INVENTORY + slot, workMem)
    if object == 0xFF then
      freeSlot = slot
      break
    end
    occupied[object] = true
  end
  assert(freeSlot ~= nil, "fixture inventory is full")

  local freeObject = nil
  for object = 0, OBJECT_COUNT - 1 do
    if not occupied[object] then
      local empty = true
      for offset = 0, OBJECT_SIZE - 1 do
        if rd(OBJECTS + object * OBJECT_SIZE + offset, workMem) ~= 0 then
          empty = false
          break
        end
      end
      if empty then
        freeObject = object
        break
      end
    end
  end
  assert(freeObject ~= nil, "fixture object pool is full")

  local record = { BLANK_ID, 7, 0, 0, 0, 0, 0, 0 }
  for offset, value in ipairs(record) do
    wr(OBJECTS + freeObject * OBJECT_SIZE + offset - 1, value, workMem)
  end
  wr(INVENTORY + freeSlot, freeObject, workMem)

  local historyAt = HISTORY + math.floor(WINDBLADE_ROOT / 8)
  local history = rd(historyAt, workMem)
  local historyMask = 1 << (WINDBLADE_ROOT & 7)
  if expectMatch then
    wr(historyAt, history | historyMask, workMem)
  else
    wr(historyAt, history & (~historyMask & 0xFF), workMem)
  end
  return freeObject
end

local blankObject = nil

local function loadOnce()
  if loaded then return end
  loaded = true
  local file = assert(io.open(assert(os.getenv("GB2_MSS_PATH")), "rb"))
  local state = file:read("*all")
  file:close()
  emu.loadSavestate(state)
  blankObject = inject()
  report(string.format("blank scroll object=%d", blankObject))
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a = false, b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
  activeButton = nil
  for _, press in ipairs(opening) do
    if frame >= press[1] and frame < press[1] + 5 then
      activeButton = press[2]
    end
  end

  if editorFrame ~= nil then
    local elapsed = frame - editorFrame - 30
    if elapsed >= 0 then
      local index = math.floor(elapsed / 15) + 1
      local phase = elapsed % 15
      if index <= #keyboard and phase < 5 then
        activeButton = keyboard[index]
      elseif index > #keyboard and confirmedFrame == nil then
        confirmedFrame = frame
        report("Windblade confirmed at frame " .. frame)
      end
    end
  end
  if activeButton ~= nil then input[activeButton] = true end
  emu.setInput(input, 0)
end

local function afterFrame()
  if loaded and editorFrame == nil and
      rd(0xC195, cpuMem) == 1 and rd(0xC153, cpuMem) == 11 then
    editorFrame = frame
    report("Blank Scroll editor reached at frame " .. frame)
  end

  if editorFrame ~= nil then
    local length = rd(0xC152, cpuMem)
    local node = rd(0xC14F, cpuMem)
    local match = rd(0xC196, cpuMem)
    if length ~= lastInputLength or node ~= lastInputNode or match ~= lastInputMatch then
      report(string.format(
        "editor frame=%d length=%02X node=%02X match=%02X",
        frame, length, node, match
      ))
      lastInputLength = length
      lastInputNode = node
      lastInputMatch = match
    end
  end

  if loaded and blankObject ~= nil then
    local item = rd(OBJECTS + blankObject * OBJECT_SIZE, workMem)
    if item == WINDBLADE_ID and convertedFrame == nil then
      convertedFrame = frame
      report("Blank Scroll converted at frame " .. frame)
    end
  end

  if confirmedFrame ~= nil and frame >= confirmedFrame + 600 then
    if expectMatch then
      assert(convertedFrame ~= nil, "Windblade confirmation did not convert the item")
    else
      assert(convertedFrame == nil, "unlearned Windblade unexpectedly converted the item")
    end
    local checksum = screenChecksum()
    assert(
      checksum == GAMEPLAY_SCREEN_CHECKSUM,
      string.format(
        "Blank Scroll confirmation did not return to gameplay: screen=%08X",
        checksum
      )
    )
    report(string.format(
      "PASS converted=%s mode=%02X node=%02X length=%02X menu=%02X screen=%08X",
      tostring(convertedFrame),
      rd(0xC195, cpuMem), rd(0xC14F, cpuMem),
      rd(0xC152, cpuMem), rd(0xC156, cpuMem), checksum
    ))
    local screenshot = os.getenv("GB2_SCREENSHOT")
    if screenshot ~= nil then
      local file = assert(io.open(screenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    emu.stop(0)
  elseif frame >= 5000 then
    error("timed out before completing the Blank Scroll route")
  end
  frame = frame + 1
end

local function traceExec(label)
  return function()
    if not loaded then return end
    local state = emu.getState()
    report(string.format(
      "exec=%s frame=%d bank=%02X pc=%04X sp=%04X match=%02X selected=%02X",
      label, frame, state["cart.prgBank"], state["cpu.pc"], state["cpu.sp"],
      rd(0xC196, cpuMem), rd(0xC156, cpuMem)
    ))
  end
end

emu.addMemoryCallback(
  loadOnce,
  emu.callbackType.exec,
  0x0000,
  0xFFFF,
  emu.cpuType.gameboy
)
for address, label in pairs({
  [0x50F7] = "validate-entry",
  [0x513A] = "validate-accept",
  [0x5F3E] = "convert-write",
}) do
  emu.addMemoryCallback(
    traceExec(label), emu.callbackType.exec, address, address,
    emu.cpuType.gameboy
  )
end
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
