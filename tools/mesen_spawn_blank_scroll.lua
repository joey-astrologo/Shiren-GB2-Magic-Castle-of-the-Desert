-- mesen_spawn_blank_scroll.lua
-- Add one real Blank Scroll to Shiren's in-dungeon inventory in Shiren GB2.
--
-- HOW TO USE
--   1. Back up the save RAM beside the ROM, or use a disposable save state. Mesen may
--      persist live memory changes when the game later saves.
--   2. Load the translated ROM, enter a dungeon, and pause emulation.
--   3. In Mesen, open Debug > Script Window, load this file, and press Run (F5).
--   4. Resume emulation and open Items. If Items was visible, close and reopen it.
--
-- Run the script only once. It leaves an existing Blank Scroll alone and refuses to
-- overwrite a full inventory, an occupied object record, or a slot which changes during
-- injection. The helper modifies live WRAM, not the ROM or the temporary rendered list.
--
-- CURRENT LOCALIZATION EXPECTATION
--   The item name, description, Write action, and writing keyboard are English. The editor
--   accepts full localized names up to 11 characters; its 0 cell is a hyphen for
--   Trap-eraser.
--   Recognition
--   remains faithful to the game: only Scrolls already recorded in this save's notebook can
--   be written. See docs/BLANK_SCROLL.md for the complete accepted-name table.
--
-- MEASURED GB2 FORMAT
--   tools/surfaces.py and its live route fixture prove:
--
--     WRAM bank 1 $D2C1-$D2D4   twenty inventory object indices; $FF is free
--     WRAM bank 2 $D482+8*index 128 eight-byte dungeon object records
--     flat GB Work RAM $12C1     physical address of bank 1:$D2C1 in Mesen
--     flat GB Work RAM $2482     physical address of bank 2:$D482 in Mesen
--     item index $92             Blank Scroll (group 4, index 146)
--     action class $07           Scroll actions, with Blank Scroll's native Write branch
--
--   The canonical object record used by the proven route is:
--
--     92 07 00 00 00 00 00 00

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
local ITEM_ID = 0x92
local ITEM_RECORD = { 0x92, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }
local LABEL = "Blank Scroll"

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

-- Access Mesen's flat 32 KiB CGB Work RAM domain directly. Writing SVBK through the CPU
-- memory domain is version-sensitive while paused and was observed to leave bank 1 mapped.
-- gbWorkRam addresses every physical bank without changing the emulated CPU's bank state.
local memT, memName = pick(
    emu.memType, { "gbWorkRam", "gameboyWorkRam" })
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

local function inject()
  if memT == nil then
    fail("this Mesen build does not expose emu.memType.gbWorkRam")
    return
  end

  local inventory = {}
  local occupied = {}
  local free_slot = nil
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object_index = rd(INVENTORY_WRAM + slot)
    if object_index == nil then
      fail("could not read the inventory")
      return
    end
    if object_index == INVENTORY_SENTINEL then
      free_slot = slot
      break
    end
    if object_index >= OBJECT_COUNT then
      fail(string.format(
          "inventory slot %d contains invalid object $%02X", slot + 1, object_index))
      return
    end
    inventory[#inventory + 1] = object_index
    occupied[object_index] = true
  end

  if free_slot == nil then
    fail("inventory is full; nothing was overwritten")
    return
  end

  for slot, object_index in ipairs(inventory) do
    local record = read_record(object_index)
    if record == nil then
      fail("could not read an inventory object")
      return
    end
    if record[1] == ITEM_ID then
      emu.log(string.format(
          "%s: already present in inventory slot %d", LABEL, slot))
      return
    end
  end

  -- GB2 clears released object records to eight zero bytes. Require that exact state and
  -- also reject any record already referenced by the canonical inventory.
  local free_object = nil
  for object_index = 0, OBJECT_COUNT - 1 do
    if not occupied[object_index] then
      local record = read_record(object_index)
      if record == nil then
        fail("could not read the object pool")
        return
      end
      if record_is_zero(record) then
        free_object = object_index
        break
      end
    end
  end

  if free_object == nil then
    fail("no cleared dungeon object record is available")
    return
  end
  if not write_record(free_object, ITEM_RECORD) then
    write_record(free_object, { 0, 0, 0, 0, 0, 0, 0, 0 })
    fail("could not create the Blank Scroll object")
    return
  end

  if rd(INVENTORY_WRAM + free_slot) ~= INVENTORY_SENTINEL then
    write_record(free_object, { 0, 0, 0, 0, 0, 0, 0, 0 })
    fail("the free inventory slot changed; injection was rolled back")
    return
  end
  if not wr_verified(INVENTORY_WRAM + free_slot, free_object) then
    write_record(free_object, { 0, 0, 0, 0, 0, 0, 0, 0 })
    fail("could not append the object index; injection was rolled back")
    return
  end

  emu.log(string.format(
      "%s: added as inventory slot %d using object %d. Close/reopen Items.",
      LABEL, free_slot + 1, free_object))
end

inject()
