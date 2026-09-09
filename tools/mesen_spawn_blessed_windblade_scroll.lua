-- Add one blessed, identified Windblade Scroll to Shiren GB2 in Mesen.
--
-- HOW TO USE
--   1. Enter a dungeon, close menus/messages, and pause Mesen.
--   2. Open Debug > Script Window, load this file, and press Run (F5).
--   3. Resume and open Items > Windblade Scroll > Read.
--
-- Each run adds one NEW scroll to a free slot. Existing items are left alone;
-- a full inventory or occupied object pool is never overwritten. The script
-- identifies the Windblade family while preserving its custom-name/history data.
-- It applies the blessing ONCE, with no callbacks, cheats, or automatic refresh.
-- Read the scroll normally to investigate whether its blessing wears off.
-- Use a disposable state for testing: a later in-game save can persist this item.

local LABEL = "Blessed Windblade Scroll"
local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local EMPTY = 0xFF
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local FLOOR_OBJECT_GRID = 0x3800
local MAP_CELLS = 0x400
local WINDBLADE_MAP = 0x2C82 + 0x32 * 2

-- Native item $7F, Scroll action class $07, byte-4 blessing flag $04.
-- Native 78:4D20 sets bit 2; 78:4D67 tests/clears it after use.
-- Curse ($02) and plating ($08) are clear. This is the real item object.
local ITEM_RECORD = { 0x7F, 0x07, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00 }
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local cpuMem = emu.memType.gameboyMemory

local function report(message)
  print(LABEL .. ": " .. message)
  emu.log(LABEL .. ": " .. message)
end

local function rd(address)
  return emu.read(address, workMem)
end

local function inject()
  if workMem == nil or cpuMem == nil then
    report("FAILED: this Mesen build does not expose Game Boy Work RAM.")
    return
  end
  for i = 1, #"SIREN GB2" do
    if emu.read(0x133 + i, cpuMem) ~= string.byte("SIREN GB2", i) then
      report("FAILED: load the Shiren GB2 ROM first.")
      return
    end
  end
  if emu.read(0xC0E5, cpuMem) ~= 6 then
    report("FAILED: enter a dungeon before running this script.")
    return
  end

  local occupied = {}
  local freeSlot = nil
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object = rd(INVENTORY + slot)
    if object == EMPTY then
      if freeSlot == nil then freeSlot = slot end
    elseif object < 0 or object >= OBJECT_COUNT or occupied[object] then
      report("FAILED: invalid inventory; no changes made.")
      return
    else
      occupied[object] = true
    end
  end
  if freeSlot == nil then
    report("FAILED: inventory full. Make room for one item and run again.")
    return
  end

  -- Floor items share the pool. Require an unreferenced, fully cleared record.
  for cell = 0, MAP_CELLS - 1 do
    local object = rd(FLOOR_OBJECT_GRID + cell)
    if object < OBJECT_COUNT then occupied[object] = true end
  end
  local freeObject = nil
  for object = 0, OBJECT_COUNT - 1 do
    if not occupied[object] then
      local clear = true
      for offset = 0, OBJECT_SIZE - 1 do
        if rd(OBJECTS + object * OBJECT_SIZE + offset) ~= 0 then clear = false; break end
      end
      if clear then freeObject = object; break end
    end
  end
  if freeObject == nil then
    report("FAILED: no cleared item object is available; no changes made.")
    return
  end

  local writes = {}
  for offset, value in ipairs(ITEM_RECORD) do
    writes[#writes + 1] = { OBJECTS + freeObject * OBJECT_SIZE + offset - 1, value }
  end
  writes[#writes + 1] = { WINDBLADE_MAP, EMPTY }
  writes[#writes + 1] = { INVENTORY + freeSlot, freeObject }
  for _, change in ipairs(writes) do change[3] = rd(change[1]) end

  local ok, reason = pcall(function()
    for _, change in ipairs(writes) do
      assert(rd(change[1]) == change[3], "item state changed during injection")
      emu.write(change[1], change[2], workMem)
      assert(rd(change[1]) == change[2], "item write did not persist")
    end
  end)
  if not ok then
    for _, change in ipairs(writes) do emu.write(change[1], change[3], workMem) end
    report("FAILED: changes rolled back: " .. tostring(reason))
    return
  end

  report(string.format("READY: added to slot %d (object %d). Resume and reopen Items.",
      freeSlot + 1, freeObject))
  report("Blessing applied once. Stop this script or leave it loaded; no further writes occur.")
  return freeObject, freeSlot
end

return inject()
