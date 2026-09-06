-- mesen_prepare_endgame.lua
-- Give the live Shiren actor a legitimate level-99 stat shape and endgame gear.
--
-- MANUAL USE
--   1. Back up the save RAM beside the ROM and make a separate save state.
--   2. Enter a dungeon, close every menu/message, and pause during normal control.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Confirm the READY message, resume, and reopen Status/Items.
--
-- The script edits live WRAM, not the ROM or battery SRAM directly. The game can
-- persist the result the next time it saves. Existing equipped weapon/shield records
-- are upgraded in place. If a category is absent, a cleared object record and free
-- inventory slot are used; a full inventory is never silently overwritten.

local LABEL = "Endgame Shiren prep"

local PLAYER_ACTOR_WRAM = 0x1000
local ACTOR_CACHE = 0xFF90
local ACTIVE_ACTOR = 0xFFFC
local ACTOR_SIZE = 0x20
local HIGH_RAM_CPU_BASE = 0xFF80

local CURRENT_LEVEL_OFFSET = 0x02
local NATURAL_LEVEL_OFFSET = 0x0A
local CURRENT_HP_OFFSET = 0x0B
local MAX_HP_OFFSET = 0x0C
local MAX_LEVEL = 99
local MAX_HP = 250

local EXPERIENCE = 0x12A0
-- Native level-99 threshold at Japanese ROM 126:$7C59: 6,200,000 ($5E9AC0).
local LEVEL_99_EXPERIENCE = { 0xC0, 0x9A, 0x5E }

local EQUIPPED_WEAPON = 0x12B1
local EQUIPPED_SHIELD = 0x12B2
local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local INVENTORY_SENTINEL = 0xFF
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local FLOOR_OBJECT_GRID = 0x3800
local MAP_CELLS = 0x400

local WEAPON_CLASS = 0x01
local SHIELD_CLASS = 0x02
local EQUIPPED_FLAG = 0x10

-- Kabura Sutegi and Rasen Fuuma are the strongest ordinary sword/shield bases in
-- the Japanese item-definition table. Byte 2 is their native base Atk/Def, byte 3
-- is the signed Upgrade Value, and bytes 5..7 are the synthesis-seal bitset.
-- Status $1C means equipped + blessed + plated, with the curse bit clear.
local WEAPON_RECORD = { 0x10, WEAPON_CLASS, 0x28, 0x63, 0x1C, 0xFF, 0x9F, 0x09 }
local SHIELD_RECORD = { 0x30, SHIELD_CLASS, 0x1E, 0x63, 0x1C, 0xF9, 0xFF, 0x2F }

-- Weapon exclusions: HP-draining/breaking, forced self-knockback, meat/breaking,
-- breakable wall/trap tools, and the lose-an-upgrade-on-hit seal.
-- Shield exclusions: doubled hunger, Max Fullness 0, lose-an-upgrade-on-hit, and
-- may-break-when-hit. Every other documented weapon/shield seal bit is enabled.

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

local workMem, workMemName = pick(
    emu.memType, { "gbWorkRam", "gameboyWorkRam" })
local highMem, highMemName = pick(
    emu.memType, { "gbHighRam", "gameboyHighRam" })

local function report(message)
  print(message)
  emu.log(message)
end

local function fail(message)
  report(LABEL .. ": FAILED: " .. message)
  return false
end

local function readWork(address)
  if workMem == nil then return nil end
  local ok, value = pcall(emu.read, address, workMem)
  if not ok then return nil end
  return value
end

local function readHigh(address)
  if highMem == nil or address < HIGH_RAM_CPU_BASE then return nil end
  local ok, value = pcall(emu.read, address - HIGH_RAM_CPU_BASE, highMem)
  if not ok then return nil end
  return value
end

local function writeWork(address, value)
  local ok = pcall(emu.write, address, value, workMem)
  return ok and readWork(address) == value
end

local function writeHigh(address, value)
  local ok = pcall(emu.write, address - HIGH_RAM_CPU_BASE, value, highMem)
  return ok and readHigh(address) == value
end

local function readRecord(index)
  local record = {}
  for offset = 0, OBJECT_SIZE - 1 do
    record[#record + 1] = readWork(OBJECTS + index * OBJECT_SIZE + offset)
  end
  return record
end

local function recordIsZero(index)
  for _, value in ipairs(readRecord(index)) do
    if value ~= 0 then return false end
  end
  return true
end

local function prepare()
  report(LABEL .. ": workMemType=" .. tostring(workMemName))
  report(LABEL .. ": highMemType=" .. tostring(highMemName))
  if workMem == nil or highMem == nil then
    return fail("this Mesen build does not expose the required GB memory domains")
  end
  if readHigh(ACTIVE_ACTOR) ~= 0 then
    return fail("active actor is not Shiren/actor 0; return to ordinary dungeon play")
  end

  -- Actor 0 is authoritative in bank 1:$D000 and mirrored at $FF90-$FFAF while
  -- active. Never create a half-updated actor from a menu/transition state.
  for offset = 0, ACTOR_SIZE - 1 do
    local backing = readWork(PLAYER_ACTOR_WRAM + offset)
    local cached = readHigh(ACTOR_CACHE + offset)
    if backing == nil or cached == nil then
      return fail("could not read the actor record and active cache")
    end
    if backing ~= cached then
      return fail(string.format(
          "actor cache differs from bank-1 record at +$%02X; no bytes were changed",
          offset))
    end
  end

  local inventory = {}
  local inventorySlot = {}
  local occupied = {}
  local freeSlots = {}
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object = readWork(INVENTORY + slot)
    if object == nil then return fail("could not read the inventory") end
    inventory[slot + 1] = object
    if object == INVENTORY_SENTINEL then
      freeSlots[#freeSlots + 1] = slot
    elseif object >= OBJECT_COUNT then
      return fail(string.format("inventory slot %d has invalid object $%02X", slot + 1, object))
    elseif occupied[object] then
      return fail(string.format("inventory object %d is referenced more than once", object))
    else
      occupied[object] = true
      inventorySlot[object] = slot
    end
  end

  -- Floor items share the same 128-record object pool. Mark them unavailable even
  -- if their record happens to look clear while the floor is changing.
  for cell = 0, MAP_CELLS - 1 do
    local object = readWork(FLOOR_OBJECT_GRID + cell)
    if object == nil then return fail("could not read the floor-object grid") end
    if object ~= INVENTORY_SENTINEL and object < OBJECT_COUNT then occupied[object] = true end
  end

  local reserved = {}
  local nextFreeSlot = 1

  local function chooseTarget(actionClass, cacheAddress, category)
    local cached = readWork(cacheAddress)
    if cached == nil then return nil, nil, "could not read the equipped " .. category end
    if cached ~= INVENTORY_SENTINEL then
      if cached >= OBJECT_COUNT or inventorySlot[cached] == nil then
        return nil, nil, "equipped " .. category .. " is not in the live inventory"
      end
      if readWork(OBJECTS + cached * OBJECT_SIZE + 1) ~= actionClass then
        return nil, nil, "equipped " .. category .. " has the wrong object class"
      end
      reserved[cached] = true
      return cached, nil, nil
    end

    local equipped = nil
    local fallback = nil
    for _, object in ipairs(inventory) do
      if object ~= INVENTORY_SENTINEL
          and readWork(OBJECTS + object * OBJECT_SIZE + 1) == actionClass then
        if fallback == nil then fallback = object end
        local flags = readWork(OBJECTS + object * OBJECT_SIZE + 4)
        if (flags & EQUIPPED_FLAG) ~= 0 then
          if equipped ~= nil then
            return nil, nil, "multiple " .. category .. " records claim to be equipped"
          end
          equipped = object
        end
      end
    end
    local existing = equipped or fallback
    if existing ~= nil then
      reserved[existing] = true
      return existing, nil, nil
    end

    local slot = freeSlots[nextFreeSlot]
    if slot == nil then
      return nil, nil, "inventory is full and contains no " .. category
    end
    local object = nil
    for candidate = 0, OBJECT_COUNT - 1 do
      if not occupied[candidate] and not reserved[candidate] and recordIsZero(candidate) then
        object = candidate
        break
      end
    end
    if object == nil then return nil, nil, "no cleared object record is available" end
    nextFreeSlot = nextFreeSlot + 1
    reserved[object] = true
    occupied[object] = true
    return object, slot, nil
  end

  local weapon, weaponSlot, weaponError = chooseTarget(
      WEAPON_CLASS, EQUIPPED_WEAPON, "weapon")
  if weapon == nil then return fail(weaponError) end
  local shield, shieldSlot, shieldError = chooseTarget(
      SHIELD_CLASS, EQUIPPED_SHIELD, "shield")
  if shield == nil then return fail(shieldError) end

  local oldWork = {}
  local plannedWork = {}
  local oldHigh = {}
  local plannedHigh = {}

  local function planWork(address, value)
    if oldWork[address] == nil then oldWork[address] = readWork(address) end
    plannedWork[address] = value
  end

  local function planHigh(address, value)
    if oldHigh[address] == nil then oldHigh[address] = readHigh(address) end
    plannedHigh[address] = value
  end

  local function planRecord(index, record)
    for offset, value in ipairs(record) do
      planWork(OBJECTS + index * OBJECT_SIZE + offset - 1, value)
    end
  end

  if weaponSlot ~= nil then planWork(INVENTORY + weaponSlot, weapon) end
  if shieldSlot ~= nil then planWork(INVENTORY + shieldSlot, shield) end

  -- Clear stale equipped bits for other weapons/shields, then establish the two
  -- native equipped-object cache indices used by combat and status calculations.
  for _, object in ipairs(inventory) do
    if object ~= INVENTORY_SENTINEL and object ~= weapon and object ~= shield then
      local actionClass = readWork(OBJECTS + object * OBJECT_SIZE + 1)
      if actionClass == WEAPON_CLASS or actionClass == SHIELD_CLASS then
        local address = OBJECTS + object * OBJECT_SIZE + 4
        local flags = readWork(address)
        if (flags & EQUIPPED_FLAG) ~= 0 then
          planWork(address, flags & (~EQUIPPED_FLAG & 0xFF))
        end
      end
    end
  end
  planRecord(weapon, WEAPON_RECORD)
  planRecord(shield, SHIELD_RECORD)
  planWork(EQUIPPED_WEAPON, weapon)
  planWork(EQUIPPED_SHIELD, shield)

  for offset, value in ipairs(LEVEL_99_EXPERIENCE) do
    planWork(EXPERIENCE + offset - 1, value)
  end
  local actorValues = {
    [CURRENT_LEVEL_OFFSET] = MAX_LEVEL,
    [NATURAL_LEVEL_OFFSET] = MAX_LEVEL,
    [CURRENT_HP_OFFSET] = MAX_HP,
    [MAX_HP_OFFSET] = MAX_HP,
  }
  for offset, value in pairs(actorValues) do
    planWork(PLAYER_ACTOR_WRAM + offset, value)
    planHigh(ACTOR_CACHE + offset, value)
  end

  local function rollback()
    local complete = true
    for address, value in pairs(oldWork) do complete = writeWork(address, value) and complete end
    for address, value in pairs(oldHigh) do complete = writeHigh(address, value) and complete end
    return complete
  end

  for address, value in pairs(plannedWork) do
    if not writeWork(address, value) then
      local restored = rollback()
      return fail("a Work RAM write failed; rollback " .. (restored and "succeeded" or "was incomplete"))
    end
  end
  for address, value in pairs(plannedHigh) do
    if not writeHigh(address, value) then
      local restored = rollback()
      return fail("a High RAM write failed; rollback " .. (restored and "succeeded" or "was incomplete"))
    end
  end

  for offset = 0, ACTOR_SIZE - 1 do
    if readWork(PLAYER_ACTOR_WRAM + offset) ~= readHigh(ACTOR_CACHE + offset) then
      local restored = rollback()
      return fail("actor views diverged after installation; rollback " ..
          (restored and "succeeded" or "was incomplete"))
    end
  end

  report(string.format(
      "%s READY: Lv %d, HP %d/%d, Experience %d.",
      LABEL, MAX_LEVEL, MAX_HP, MAX_HP, 6200000))
  report(string.format(
      "Equipped Kabura Sutegi+99 (object %d) and Rasen Fuuma+99 (object %d).",
      weapon, shield))
  report("All conservative positive seals are installed; risky/tradeoff seals are excluded.")
  report("Resume for one turn, then reopen Status/Items. A later in-game save can persist this WRAM state.")
  return true
end

_G.gb2PrepareEndgame = prepare
prepare()
