-- mesen_prepare_rescue_request.lua
-- Put Shiren at 1 current HP for a deterministic Wanderer Rescue requester test.
--
-- MANUAL USE
--   1. Back up the save RAM beside the ROM and use a disposable save state.
--   2. Load SaveStates/Mamel.mss with the current English ROM and pause Mesen.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Resume. Dismiss the existing message if needed, then let the adjacent Mamel
--      take one turn and hit Shiren. Do not attack the Mamel first.
--   5. After collapsing, open Rankings, press Select, and choose Await Rescue.
--   6. Save separate requester states at Rankings and at the generated SOS screen.
--
-- This helper changes only current HP in the live actor-0 record and its active cache.
-- It does not alter story flags, rescue flags, SRAM, inventory, the ROM, or Max HP.
-- Mesen can later persist changes if the game itself saves, so use a disposable state.

local LABEL = "Rescue requester prep"
local PLAYER_ACTOR_BANK = 1
local PLAYER_ACTOR_BASE = 0xD000
local PLAYER_ACTOR_WRAM = 0x1000
local ACTOR_SIZE = 0x20
local ACTOR_CACHE = 0xFF90
local ACTIVE_ACTOR = 0xFFFC
local MAX_HP_OFFSET = 0x15
local CURRENT_HP_OFFSET = 0x16
local TARGET_HP = 1
local HIGH_RAM_CPU_BASE = 0xFF80

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

local function writeVerified(address, value, memType, reader)
  local ok = pcall(emu.write, address, value, memType)
  return ok and reader(address) == value
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

  -- The engine copies the active 32-byte actor record from bank 1:$D000 to
  -- $FF90-$FFAF. Refuse to write unless both views are completely synchronized.
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

  local maxHp = readWork(PLAYER_ACTOR_WRAM + MAX_HP_OFFSET)
  local currentHp = readWork(PLAYER_ACTOR_WRAM + CURRENT_HP_OFFSET)
  if maxHp == nil or currentHp == nil or maxHp == 0 or currentHp == 0 then
    return fail("HP fields are unavailable or Shiren is already collapsed")
  end
  if currentHp > maxHp then
    return fail(string.format(
        "current HP %d exceeds Max HP %d; refusing an unknown actor state",
        currentHp, maxHp))
  end
  if currentHp == TARGET_HP then
    report(string.format(
        "%s: already prepared (Max HP %d, current HP %d)",
        LABEL, maxHp, currentHp))
    return true
  end

  local backingAddress = PLAYER_ACTOR_WRAM + CURRENT_HP_OFFSET
  local cacheAddress = ACTOR_CACHE + CURRENT_HP_OFFSET
  local oldBacking = currentHp
  local oldCache = readHigh(cacheAddress)
  if oldCache ~= oldBacking then
    return fail("current HP changed after validation; no bytes were changed")
  end

  if not writeVerified(backingAddress, TARGET_HP, workMem, readWork) then
    return fail("could not write current HP to the bank-1 actor record")
  end
  if not writeVerified(
      cacheAddress - HIGH_RAM_CPU_BASE, TARGET_HP, highMem,
      function(address) return readHigh(address + HIGH_RAM_CPU_BASE) end) then
    writeVerified(backingAddress, oldBacking, workMem, readWork)
    writeVerified(
        cacheAddress - HIGH_RAM_CPU_BASE, oldCache, highMem,
        function(address) return readHigh(address + HIGH_RAM_CPU_BASE) end)
    return fail("could not update the active actor cache; change was rolled back")
  end

  report(string.format(
      "%s: current HP %d -> %d (Max HP %d). Let the Mamel hit Shiren once.",
      LABEL, currentHp, TARGET_HP, maxHp))
  return true
end

local fixturePath = os.getenv("GB2_RESCUE_PREP_MSS")
if fixturePath == nil or fixturePath == "" then
  prepare()
else
  local loaded = false
  local prepared = false
  local frame = 0

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
    prepared = prepare()
  end

  local function afterFrame()
    if not loaded then return end
    if not prepared then error("rescue requester prep failed") end
    if frame == 1 then
      local backing = readWork(PLAYER_ACTOR_WRAM + CURRENT_HP_OFFSET)
      local cached = readHigh(ACTOR_CACHE + CURRENT_HP_OFFSET)
      assert(backing == TARGET_HP, "backing current HP did not remain at 1")
      assert(cached == TARGET_HP, "cached current HP did not remain at 1")
      assert(readWork(PLAYER_ACTOR_WRAM + MAX_HP_OFFSET) == 40,
          "Mamel fixture Max HP changed")
      report(string.format(
          "PASS rescue-requester-prep max=%d current=%d active=%d",
          readWork(PLAYER_ACTOR_WRAM + MAX_HP_OFFSET), backing,
          readHigh(ACTIVE_ACTOR)))
      emu.stop(0)
    elseif frame > 120 then
      error("timed out while checking rescue requester prep")
    end
    frame = frame + 1
  end

  emu.addMemoryCallback(
      loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
  emu.addEventCallback(afterFrame, emu.eventType.endFrame)
end
