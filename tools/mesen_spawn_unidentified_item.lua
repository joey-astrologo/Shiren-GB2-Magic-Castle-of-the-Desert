-- mesen_spawn_unidentified_item.lua
-- Prepare one deterministic unidentified-item Name / Fill In test in Shiren GB2.
--
-- HOW TO USE
--   1. Back up the save RAM beside the ROM, or load a disposable in-dungeon save state.
--   2. Pause Mesen, open Debug > Script Window, load this file, and press Run (F5).
--   3. Resume emulation, close/reopen Items, and select the injected Rabbit Scroll.
--   4. Choose Name to test free entry. Reload the state and rerun this helper before
--      separately testing Name > Fill In.
--
-- The default probe is a real Windblade Scroll presented as an unidentified Rabbit
-- Scroll. Only Windblade's notebook/history bit is enabled by the helper. This makes
-- Fill In deterministic without identifying the item or populating unrelated history.
--
-- To exercise another category, change TARGET_KEY to one of:
--   passage_bracelet, herb, windblade_scroll, knockback_staff, preservation_pot
--
-- Run this only once per state reload. Naming the item allocates persistent custom-name
-- state, and this helper deliberately refuses to overwrite an existing custom mapping.
-- It modifies live WRAM, not the ROM. Mesen may later persist those changes to SRAM.

local TARGET_KEY = "windblade_scroll"

local INVENTORY_BANK = 1
local INVENTORY_BASE = 0xD2C1
local INVENTORY_WRAM = 0x12C1
local INVENTORY_SLOTS = 20
local INVENTORY_SENTINEL = 0xFF
local OBJECT_BANK = 2
local OBJECT_BASE = 0xD482
local OBJECT_WRAM = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local UNIDENTIFIED_OBJECT_MARKER = 0xFF

-- WRAM bank 2. Each identification-map pair is:
--   byte 0: unidentified appearance index ($FF means identified)
--   byte 1: custom-name slot index ($FF means no custom name)
local IDENTIFICATION_BANK = 2
local IDENTIFICATION_BASE = 0xDC82
local IDENTIFICATION_WRAM = 0x2C82
local HISTORY_BASE = 0xDE1C
local HISTORY_WRAM = 0x2E1C
local CUSTOM_NAME_BASE = 0xDD78
local CUSTOM_NAME_WRAM = 0x2D78
local CUSTOM_NAME_SLOTS = 20
local CUSTOM_NAME_SLOT_BYTES = 8
local CUSTOM_NAME_SENTINEL = 0xFF
local ACTION_INHIBIT_ADDRESS = 0xC12B
local ACTION_INHIBIT_MASK = 0x02

local function target(label, itemId, actionClass, rootIndex, appearanceIndex)
  return {
    label = label,
    itemId = itemId,
    actionClass = actionClass,
    rootIndex = rootIndex,
    appearanceIndex = appearanceIndex,
  }
end

-- One valid representative of every natively unidentified category. Item IDs and root
-- indices follow the category partitions proven in tools/surfaces.py.
local TARGETS = {
  passage_bracelet = target("Waterwalk Bracelet", 0x3F, 0x03, 0x00, 0x00),
  herb = target("Herb", 0x68, 0x06, 0x1B, 0x1B),
  windblade_scroll = target("Windblade Scroll", 0x7F, 0x07, 0x32, 0x32),
  knockback_staff = target("Knockback Staff", 0x9E, 0x08, 0x51, 0x51),
  preservation_pot = target("Preservation Pot", 0xB8, 0x09, 0x6B, 0x6B),
}

local selected = TARGETS[TARGET_KEY]
local LABEL = "Unidentified item lab"

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

-- Access Mesen's flat 32 KiB CGB Work RAM domain. This does not change the emulated
-- CPU's currently selected SVBK bank.
local memT, memName = pick(
    emu.memType, { "gbWorkRam", "gameboyWorkRam" })
local cpuMemT = emu.memType.gameboyMemory
emu.log(LABEL .. ": workMemType=" .. tostring(memName))

local function rd(address)
  if memT == nil then return nil end
  local ok, value = pcall(emu.read, address, memT)
  if ok and value ~= nil then return value end
  return nil
end

local function wr_raw(address, value)
  if memT == nil then return false end
  return pcall(emu.write, address, value, memT)
end

local function wr_verified(address, value)
  if not wr_raw(address, value) then return false end
  return rd(address) == value
end

local function fail(message)
  emu.log(LABEL .. ": FAILED: " .. message)
  return false
end

local function read_record(index)
  local record = {}
  local address = OBJECT_WRAM + index * OBJECT_SIZE
  for offset = 0, OBJECT_SIZE - 1 do
    local value = rd(address + offset)
    if value == nil then return nil end
    record[#record + 1] = value
  end
  return record
end

local function record_is_zero(record)
  if record == nil then return false end
  for _, value in ipairs(record) do
    if value ~= 0 then return false end
  end
  return true
end

local function write_record(index, record)
  local address = OBJECT_WRAM + index * OBJECT_SIZE
  for offset = 0, OBJECT_SIZE - 1 do
    if not wr_verified(address + offset, record[offset + 1]) then
      return false
    end
  end
  return true
end

local function set_history_bit(rootIndex, oldValue)
  local mask = 2 ^ (rootIndex % 8)
  if oldValue % (mask * 2) >= mask then return oldValue end
  return oldValue + mask
end

local function inject()
  if memT == nil then
    fail("this Mesen build does not expose emu.memType.gbWorkRam")
    return
  end
  if selected == nil then
    fail("unknown TARGET_KEY: " .. tostring(TARGET_KEY))
    return
  end

  local mapAddress = IDENTIFICATION_WRAM + selected.rootIndex * 2
  local oldAppearance = rd(mapAddress)
  local oldCustom = rd(mapAddress + 1)
  local historyAddress = HISTORY_WRAM + math.floor(selected.rootIndex / 8)
  local oldHistory = rd(historyAddress)
  if oldAppearance == nil or oldCustom == nil or oldHistory == nil then
    fail("could not read identification/history state")
    return
  end
  if oldCustom ~= CUSTOM_NAME_SENTINEL then
    fail(string.format(
        "%s already uses custom-name slot %d; reload the disposable state first",
        selected.label, oldCustom))
    return
  end

  -- Check the entire slot area before relying on it. Existing names are allowed, but every
  -- slot byte must be readable and the selected root must not already reference one.
  for offset = 0, CUSTOM_NAME_SLOTS * CUSTOM_NAME_SLOT_BYTES - 1 do
    if rd(CUSTOM_NAME_WRAM + offset) == nil then
      fail("could not read the custom-name slot table")
      return
    end
  end

  local inventory = {}
  local occupied = {}
  local freeSlot = nil
  local selectedObject = nil
  for slot = 0, INVENTORY_SLOTS - 1 do
    local objectIndex = rd(INVENTORY_WRAM + slot)
    if objectIndex == nil then
      fail("could not read the inventory")
      return
    end
    if objectIndex == INVENTORY_SENTINEL then
      if freeSlot == nil then freeSlot = slot end
    else
      if objectIndex >= OBJECT_COUNT then
        fail(string.format(
            "inventory slot %d contains invalid object $%02X", slot + 1, objectIndex))
        return
      end
      inventory[#inventory + 1] = objectIndex
      occupied[objectIndex] = true
      local record = read_record(objectIndex)
      if record == nil then
        fail("could not read an inventory object")
        return
      end
      if record[1] == selected.itemId then selectedObject = objectIndex end
    end
  end

  local createdObject = nil
  if selectedObject == nil then
    if freeSlot == nil then
      fail("inventory is full; nothing was overwritten")
      return
    end
    for objectIndex = 0, OBJECT_COUNT - 1 do
      if not occupied[objectIndex] then
        local record = read_record(objectIndex)
        if record == nil then
          fail("could not read the object pool")
          return
        end
        if record_is_zero(record) then
          createdObject = objectIndex
          break
        end
      end
    end
    if createdObject == nil then
      fail("no cleared dungeon object record is available")
      return
    end

    local itemRecord = {
      selected.itemId, selected.actionClass, 0x00, 0x00,
      0x00, 0x00, UNIDENTIFIED_OBJECT_MARKER, 0x00,
    }
    if not write_record(createdObject, itemRecord) then
      write_record(createdObject, { 0, 0, 0, 0, 0, 0, 0, 0 })
      fail("could not create the target item object")
      return
    end
    if rd(INVENTORY_WRAM + freeSlot) ~= INVENTORY_SENTINEL
        or not wr_verified(INVENTORY_WRAM + freeSlot, createdObject) then
      write_record(createdObject, { 0, 0, 0, 0, 0, 0, 0, 0 })
      fail("the inventory changed; item injection was rolled back")
      return
    end
    selectedObject = createdObject
  end

  -- The early Mamel fixture keeps the global ordinary-item-action inhibit bit
  -- set after its tutorial message. Name cannot appear while this bit is set,
  -- so clear only that measured flag for this disposable test route. Treat it
  -- as part of the same transaction as the item/mapping preparation.
  local oldActionFlags = emu.read(ACTION_INHIBIT_ADDRESS, cpuMemT)
  local newActionFlags = oldActionFlags & (~ACTION_INHIBIT_MASK & 0xFF)

  local newHistory = set_history_bit(selected.rootIndex, oldHistory)
  local prepared = wr_verified(mapAddress, selected.appearanceIndex)
      and wr_verified(mapAddress + 1, CUSTOM_NAME_SENTINEL)
      and wr_verified(historyAddress, newHistory)
      and pcall(emu.write, ACTION_INHIBIT_ADDRESS, newActionFlags, cpuMemT)
      and emu.read(ACTION_INHIBIT_ADDRESS, cpuMemT) == newActionFlags
  if not prepared then
    wr_verified(mapAddress, oldAppearance)
    wr_verified(mapAddress + 1, oldCustom)
    wr_verified(historyAddress, oldHistory)
    pcall(emu.write, ACTION_INHIBIT_ADDRESS, oldActionFlags, cpuMemT)
    if createdObject ~= nil then
      wr_verified(INVENTORY_WRAM + freeSlot, INVENTORY_SENTINEL)
      write_record(createdObject, { 0, 0, 0, 0, 0, 0, 0, 0 })
    end
    fail("could not prepare identification state; changes were rolled back")
    return
  end

  local placement
  if createdObject ~= nil then
    placement = string.format("added to inventory slot %d", freeSlot + 1)
  else
    placement = "already present in inventory"
  end
  emu.log(string.format(
      "%s: READY: %s %s as root %d / appearance %d using object %d.",
      LABEL, selected.label, placement, selected.rootIndex,
      selected.appearanceIndex, selectedObject))
  emu.log(
      LABEL .. ": close/reopen Items; choose the unidentified item, then Name.")
  emu.log(
      LABEL .. ": reload this state before separately testing Name > Fill In.")
end

-- The ordinary Script Window route applies immediately to the already loaded game. The
-- opt-in test-runner route loads the checked-in state first, then exercises this exact
-- helper rather than a Python reimplementation of it.
local fixturePath = os.getenv("GB2_UNIDENTIFIED_HELPER_FIXTURE")
if fixturePath == nil or fixturePath == "" then
  inject()
else
  local fixtureLoaded = false
  local function runFixture()
    if fixtureLoaded then return end
    fixtureLoaded = true
    local file = assert(io.open(fixturePath, "rb"))
    local state = file:read("*all")
    file:close()
    emu.loadSavestate(state)

    inject()

    local mapAddress = IDENTIFICATION_WRAM + selected.rootIndex * 2
    assert(rd(mapAddress) == selected.appearanceIndex, "appearance was not prepared")
    assert(rd(mapAddress + 1) == CUSTOM_NAME_SENTINEL, "custom mapping changed")
    local historyAddress = HISTORY_WRAM + math.floor(selected.rootIndex / 8)
    local historyMask = 2 ^ (selected.rootIndex % 8)
    assert(
        rd(historyAddress) % (historyMask * 2) >= historyMask,
        "learned-name bit was not prepared")

    local foundObject = nil
    local foundSlot = nil
    for slot = 0, INVENTORY_SLOTS - 1 do
      local objectIndex = rd(INVENTORY_WRAM + slot)
      if objectIndex ~= INVENTORY_SENTINEL then
        local record = read_record(objectIndex)
        if record ~= nil and record[1] == selected.itemId then
          foundObject = objectIndex
          foundSlot = slot
          break
        end
      end
    end
    assert(foundObject ~= nil, "target item was not present after injection")
    local foundRecord = read_record(foundObject)
    assert(
        foundRecord[7] == UNIDENTIFIED_OBJECT_MARKER,
        "target item was not marked unidentified")
    assert(
        emu.read(ACTION_INHIBIT_ADDRESS, cpuMemT) & ACTION_INHIBIT_MASK == 0,
        "ordinary item actions remain inhibited")
    print(string.format(
        "PASS unidentified-helper target=%s slot=%d object=%d root=%d appearance=%d",
        TARGET_KEY, foundSlot, foundObject, selected.rootIndex, selected.appearanceIndex))
    emu.stop(0)
  end
  emu.addMemoryCallback(
      runFixture,
      emu.callbackType.exec,
      0x0000,
      0xFFFF,
      emu.cpuType.gameboy)
end
