-- Prepare a disposable Synthesis Pot test in Shiren GB2.
--
-- MANUAL USE
--   WARNING: this disposable helper erases the current twenty-slot inventory.
--   1. Build/load the current English ROM and load SaveStates/Mamel.mss.
--   2. Pause, open Debug > Script Window, load this file, and press Run (F5).
--   3. Resume, dismiss the existing message with B, and open Items with A.
--   4. Select Synthesis Pot > Put In > Cudgel; it is the base weapon.
--   5. Repeat Synthesis Pot > Put In > Axe of the Minotaur; the Axe is consumed
--      and donates its critical-hit seal when the Pot is broken.
--   6. Throw the Pot against a wall, recover the Cudgel, and open Info.
--      Its ability list should contain "More frequent critical hits."
--
-- This replaces the twenty live inventory pointers and writes three cleared object
-- records. It reserves a cleared run after the Pot for the native variable-length
-- contents representation. Use only with the disposable Mamel state. It changes WRAM,
-- not the ROM, but Mesen can persist a later in-game save.

local LABEL = "Synthesis Pot lab"
local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local INVENTORY_SENTINEL = 0xFF
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local POT_RUNWAY_RECORDS = 8
local IDENTIFICATION = 0x2C82
local SYNTHESIS_POT_ROOT = 0x71
local IDENTIFIED = 0xFF
local ACTION_FLAGS = 0xC12B
local ACTION_INHIBIT_MASK = 0x02

local CUDGEL =       { 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }
-- Direct object injection bypasses the native item-construction routine that seeds an
-- equipment object's inherent rune bits. Weapon ability 10 (critical hits) is byte 6,
-- bit 2. The item ID alone is not sufficient for a synthesis donor.
local MINOTAUR_AXE = { 0x0B, 0x01, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00 }
-- Byte 2 is the capacity traversal count. The native five-cell contents list is
-- sparse: its object-index/sentinel cells begin at byte offsets 5, 6, 7, 10, and
-- 11 from the Pot object. Every unused cell must start as $FF. Initializing only
-- the first cell makes an empty Pot display [5], but it collapses to [0] after
-- the first insertion because the formatter then walks into zero-filled cells.
local SYNTHESIS_POT = { 0xBE, 0x09, 0x05, 0x00, 0x00, 0xFF, 0xFF, 0xFF }
local POT_CELL_OFFSETS = { 5, 6, 7, 10, 11 }

local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local function report(message)
  print(message)
  emu.log(message)
end

local function rd(address)
  return emu.read(address, workMem)
end

local function wr(address, value)
  emu.write(address, value, workMem)
  return rd(address) == value
end

local function readRecord(index)
  local record = {}
  for offset = 0, OBJECT_SIZE - 1 do
    record[#record + 1] = rd(OBJECTS + index * OBJECT_SIZE + offset)
  end
  return record
end

local function writeRecord(index, record)
  for offset, value in ipairs(record) do
    if not wr(OBJECTS + index * OBJECT_SIZE + offset - 1, value) then return false end
  end
  return true
end

local function recordIsZero(index)
  for _, value in ipairs(readRecord(index)) do
    if value ~= 0 then return false end
  end
  return true
end

local function writeEmptyPot(index)
  if not writeRecord(index, SYNTHESIS_POT) then return false end
  local base = OBJECTS + index * OBJECT_SIZE
  for _, offset in ipairs(POT_CELL_OFFSETS) do
    if not wr(base + offset, 0xFF) then return false end
  end
  return true
end

local function inject()
  assert(workMem ~= nil, "Mesen does not expose flat Game Boy Work RAM")

  local occupied = {}
  local oldInventory = {}
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object = rd(INVENTORY + slot)
    oldInventory[#oldInventory + 1] = object
    if object ~= INVENTORY_SENTINEL then occupied[object] = true end
  end

  -- The Pot's contents are a native variable-length structure beginning at byte 5.
  -- Reserve a large consecutive cleared run and keep both standalone weapons outside it.
  local potObject = nil
  for candidate = OBJECT_COUNT - POT_RUNWAY_RECORDS, 0, -1 do
    local clean = true
    for object = candidate, candidate + POT_RUNWAY_RECORDS - 1 do
      if occupied[object] or not recordIsZero(object) then
        clean = false
        break
      end
    end
    if clean then
      potObject = candidate
      break
    end
  end
  assert(potObject ~= nil, "no cleared eight-record runway is available for the Pot")

  local weapons = {}
  for object = 0, OBJECT_COUNT - 1 do
    local inRunway = object >= potObject and object < potObject + POT_RUNWAY_RECORDS
    if not inRunway and not occupied[object] and recordIsZero(object) then
      weapons[#weapons + 1] = object
      if #weapons == 2 then break end
    end
  end
  assert(#weapons == 2, "fewer than two cleared weapon records are available")

  local oldAppearance = rd(IDENTIFICATION + SYNTHESIS_POT_ROOT * 2)
  local oldCustom = rd(IDENTIFICATION + SYNTHESIS_POT_ROOT * 2 + 1)
  local oldAction = emu.read(ACTION_FLAGS, cpuMem)

  local function rollback()
    writeRecord(weapons[1], { 0, 0, 0, 0, 0, 0, 0, 0 })
    writeRecord(weapons[2], { 0, 0, 0, 0, 0, 0, 0, 0 })
    for object = potObject, potObject + POT_RUNWAY_RECORDS - 1 do
      writeRecord(object, { 0, 0, 0, 0, 0, 0, 0, 0 })
    end
    for slot, value in ipairs(oldInventory) do wr(INVENTORY + slot - 1, value) end
    wr(IDENTIFICATION + SYNTHESIS_POT_ROOT * 2, oldAppearance)
    wr(IDENTIFICATION + SYNTHESIS_POT_ROOT * 2 + 1, oldCustom)
    emu.write(ACTION_FLAGS, oldAction, cpuMem)
  end

  local installed = writeRecord(weapons[1], CUDGEL)
      and writeRecord(weapons[2], MINOTAUR_AXE)
      and writeEmptyPot(potObject)
  if installed then
    for slot = 0, INVENTORY_SLOTS - 1 do
      local value = INVENTORY_SENTINEL
      if slot == 0 then value = weapons[1]
      elseif slot == 1 then value = weapons[2]
      elseif slot == 2 then value = potObject end
      installed = installed and wr(INVENTORY + slot, value)
    end
  end
  installed = installed
      and wr(IDENTIFICATION + SYNTHESIS_POT_ROOT * 2, IDENTIFIED)
      and wr(IDENTIFICATION + SYNTHESIS_POT_ROOT * 2 + 1, oldCustom)
  if installed then
    local action = oldAction & (~ACTION_INHIBIT_MASK & 0xFF)
    emu.write(ACTION_FLAGS, action, cpuMem)
    installed = emu.read(ACTION_FLAGS, cpuMem) == action
  end
  if not installed then
    rollback()
    error("could not install the Synthesis Pot lab; changes were rolled back")
  end

  report(string.format(
      "%s READY: Cudgel object=%d, Axe object=%d, Synthesis Pot object=%d.",
      LABEL, weapons[1], weapons[2], potObject))
  report("WARNING: the previous inventory was intentionally replaced; do not save this run.")
  report("Use Synthesis Pot > Put In > Cudgel, then repeat with Axe of the Minotaur.")
  report("Throw the Pot at a wall; the recovered Cudgel should list the critical-hit seal in Info.")
  return weapons[1], weapons[2], potObject
end

local fixturePath = os.getenv("GB2_SYNTHESIS_LAB_MSS")
if fixturePath == nil or fixturePath == "" then
  inject()
else
  local frame = 0
  local loaded = false
  local objects = nil
  local ITEM_LIST_SCREEN = 0xA6555144
  local ACTION_SCREEN = 0x443462AC
  local PUT_PICKER_SCREEN = 0xAF86C0BC
  local FIRST_PUT_SCREEN = 0x64B86E47
  local SECOND_PUT_SCREEN = 0xE0AC69E2

  local function loadFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*all")
    file:close()
    return data
  end

  local function screenChecksum()
    local hash = 2166136261
    for _, pixel in ipairs(emu.getScreenBuffer()) do
      hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
    end
    return hash
  end

  local function saveScreenshot(variable)
    local path = os.getenv(variable)
    if path == nil or path == "" then return end
    local file = assert(io.open(path, "wb"))
    file:write(emu.takeScreenshot())
    file:close()
  end

  local function loadOnce()
    if loaded then return end
    loaded = true
    emu.loadSavestate(loadFile(fixturePath))
    objects = { inject() }
    assert(rd(INVENTORY) == objects[1], "Cudgel inventory pointer changed")
    assert(rd(INVENTORY + 1) == objects[2], "Axe inventory pointer changed")
    assert(rd(INVENTORY + 2) == objects[3], "Pot inventory pointer changed")
    assert(rd(INVENTORY + 3) == INVENTORY_SENTINEL, "gallery did not end after three items")
    assert(readRecord(objects[1])[1] == CUDGEL[1], "Cudgel record changed")
    assert(readRecord(objects[2])[1] == MINOTAUR_AXE[1], "Axe record changed")
    local pot = readRecord(objects[3])
    assert(pot[1] == SYNTHESIS_POT[1] and pot[3] == 5 and pot[6] == 0xFF,
        "Synthesis Pot record changed")
    local potBase = OBJECTS + objects[3] * OBJECT_SIZE
    for _, offset in ipairs(POT_CELL_OFFSETS) do
      assert(rd(potBase + offset) == 0xFF, "Pot unused-cell sentinel changed")
    end
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
    pressAt(input, 120, "b")
    pressAt(input, 220, "a")
    pressAt(input, 450, "down")
    pressAt(input, 480, "down")
    pressAt(input, 520, "a")
    pressAt(input, 720, "down")
    pressAt(input, 760, "a")
    pressAt(input, 1020, "a")
    pressAt(input, 1400, "a")
    pressAt(input, 1600, "down")
    pressAt(input, 1640, "a")
    pressAt(input, 1880, "a")
    pressAt(input, 2320, "a")
    pressAt(input, 2500, "down")
    pressAt(input, 2540, "down")
    pressAt(input, 2580, "a")
    emu.setInput(input, 0)
  end

  local function afterFrame()
    if not loaded then return end
    if frame == 400 then
      local checksum = screenChecksum()
      report(string.format("synthesis lab item list screen=%08X", checksum))
      if ITEM_LIST_SCREEN ~= 0 then assert(checksum == ITEM_LIST_SCREEN, "item list screen changed") end
      saveScreenshot("GB2_SYNTHESIS_LAB_SCREENSHOT")
    elseif frame == 700 then
      local checksum = screenChecksum()
      report(string.format("synthesis lab action screen=%08X", checksum))
      if ACTION_SCREEN ~= 0 then assert(checksum == ACTION_SCREEN, "action screen changed") end
      saveScreenshot("GB2_SYNTHESIS_LAB_ACTION_SCREENSHOT")
    elseif frame == 1000 then
      local checksum = screenChecksum()
      report(string.format("synthesis lab Put In picker screen=%08X", checksum))
      if PUT_PICKER_SCREEN ~= 0 then assert(checksum == PUT_PICKER_SCREEN, "Put In picker changed") end
      saveScreenshot("GB2_SYNTHESIS_LAB_PICKER_SCREENSHOT")
    elseif frame == 1300 then
      local checksum = screenChecksum()
      local potBase = OBJECTS + objects[3] * OBJECT_SIZE
      assert(rd(INVENTORY) == objects[2], "Axe was not retained after the base insertion")
      assert(rd(INVENTORY + 1) == objects[3], "Pot was not retained after the base insertion")
      assert(rd(INVENTORY + 2) == INVENTORY_SENTINEL, "unexpected item after the first insertion")
      assert(rd(potBase + 2) == 5, "Pot traversal count changed after the base insertion")
      assert(rd(potBase + POT_CELL_OFFSETS[1]) == objects[1], "Pot did not retain the Cudgel")
      for cell = 2, #POT_CELL_OFFSETS do
        assert(rd(potBase + POT_CELL_OFFSETS[cell]) == 0xFF, "unused Pot cell lost its sentinel")
      end
      report(string.format("synthesis lab first Put In screen=%08X", checksum))
      if FIRST_PUT_SCREEN ~= 0 then assert(checksum == FIRST_PUT_SCREEN, "first Put In screen changed") end
      saveScreenshot("GB2_SYNTHESIS_LAB_FIRST_PUT_SCREENSHOT")
    elseif frame == 2200 then
      local checksum = screenChecksum()
      local baseWeapon = readRecord(objects[1])
      local donorWeapon = readRecord(objects[2])
      local potBase = OBJECTS + objects[3] * OBJECT_SIZE
      assert(rd(INVENTORY) == objects[3], "Pot was not retained after synthesis")
      assert(rd(INVENTORY + 1) == INVENTORY_SENTINEL, "donor was not removed from inventory")
      assert(baseWeapon[1] == CUDGEL[1], "base weapon was not retained inside the Pot")
      for _, value in ipairs(donorWeapon) do assert(value == 0, "donor object was not consumed") end
      assert(rd(potBase + 2) == 4, "native synthesis state was not recorded")
      assert(rd(potBase + POT_CELL_OFFSETS[1]) == objects[1], "synthesized base pointer changed")
      report(string.format("synthesis lab second Put In screen=%08X", checksum))
      if SECOND_PUT_SCREEN ~= 0 then assert(checksum == SECOND_PUT_SCREEN, "second Put In screen changed") end
      saveScreenshot("GB2_SYNTHESIS_LAB_SECOND_PUT_SCREENSHOT")
    elseif frame == 3400 then
      local baseWeapon = readRecord(objects[1])
      assert(rd(INVENTORY) == INVENTORY_SENTINEL, "thrown Pot remained in inventory")
      assert(baseWeapon[1] == CUDGEL[1], "released base is no longer a Cudgel")
      assert((baseWeapon[7] & 0x04) ~= 0, "released Cudgel lacks the critical-hit seal")
      report("synthesis lab post-break seal=weapon-bit-10")
      saveScreenshot("GB2_SYNTHESIS_LAB_POST_THROW_SCREENSHOT")
      report(string.format(
          "PASS synthesis-lab item=%08X action=%08X picker=%08X first=%08X second=%08X break=weapon-bit-10",
          ITEM_LIST_SCREEN, ACTION_SCREEN, PUT_PICKER_SCREEN,
          FIRST_PUT_SCREEN, SECOND_PUT_SCREEN))
      emu.stop(0)
    elseif frame > 3600 then
      error("timed out while opening the Synthesis Pot lab")
    end
    frame = frame + 1
  end

  emu.addMemoryCallback(loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
  emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
  emu.addEventCallback(afterFrame, emu.eventType.endFrame)
end
