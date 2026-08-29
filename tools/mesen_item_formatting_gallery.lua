-- Item-formatting visual gallery for the Shiren GB2 English build.
--
-- MANUAL USE
--   1. Build/load the current English ROM in Mesen.
--   2. Load the committed SaveStates/Mamel.mss disposable state.
--   3. Pause, open Debug > Script Window, load this file, and press Run (F5).
--   4. Resume, dismiss the existing message with B, and open Items with A.
--   5. Inspect page 1, then press Right for page 2. Do not sort the gallery.
--
-- This deliberately replaces the live inventory and marks three fixture item
-- families identified. Use only with a disposable save state. It does not alter
-- the ROM, but Mesen can persist later in-game saves.

local LABEL = "Item formatting gallery"
local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local OBJECT_COUNT = 128
local IDENTIFICATION = 0x2C82
local IDENTIFIED = 0xFF
local ACTION_FLAGS = 0xC12B
local ACTION_INHIBIT_MASK = 0x02

local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

-- Byte 4 status flags: $02 cursed, $04 plated, $08 blessed, $10 equipped.
-- Equipment modifier/cracked value is byte 3. Equipment synthesis occupies
-- bytes 5..7. Arrow/staff count is byte 2. A Pot's byte 2 is its capacity
-- traversal count and byte 5 begins the contained-object list; $FF represents
-- the first unused cell. Gitan and Meat use bytes 2..3.
local GALLERY = {
  -- Page 1: name-row status markers and their supported combinations.
  { "Normal",                "Club",                    { 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 } },
  { "Equipped",              "<equip>Club",             { 0x01, 0x01, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00 } },
  { "Cursed",                "Club<skull>",             { 0x01, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00 } },
  { "Blessed",               "Club<bell>",              { 0x01, 0x01, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00 } },
  { "Plated",                "Club<plate>",             { 0x01, 0x01, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00 } },
  { "Cursed + plated",       "Club<skull><plate>",      { 0x01, 0x01, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00 } },
  { "Blessed + plated",      "Club<plate><bell>",       { 0x01, 0x01, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00 } },
  { "Cracked Bracelet",      "Strength Bracelet(Cr)",     { 0x48, 0x03, 0x00, 0x01, 0x00, 0x00, 0x10, 0x00 } },
  { "One synthesis rune",    "Club (alternate color)",  { 0x01, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00 } },
  { "Equip + curse + plate", "<equip>Club+99<skull><plate>", { 0x01, 0x01, 0x00, 0x63, 0x16, 0x00, 0x00, 0x00 } },

  -- Page 2: numeric and dynamically composed item names.
  { "Positive shield",       "Bronze Shield+99",             { 0x23, 0x02, 0x00, 0x63, 0x00, 0x00, 0x00, 0x00 } },
  { "Arrow quantity",        "99 Wooden Arrow",           { 0x5A, 0x04, 0x63, 0x00, 0x00, 0x00, 0x00, 0x00 } },
  { "Gitan amount",          "999 Gitan",                 { 0xC8, 0x0A, 0xE7, 0x03, 0x00, 0x00, 0x00, 0x00 } },
  { "Monster Meat",          "Mamel Meat",                { 0xC9, 0x0B, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00 } },
  { "Positive weapon",       "Club+99",                 { 0x01, 0x01, 0x00, 0x63, 0x00, 0x00, 0x00, 0x00 } },
  { "Negative weapon",       "Club-99",                 { 0x01, 0x01, 0x00, 0x9D, 0x00, 0x00, 0x00, 0x00 } },
  { "Staff zero charges",    "Knockback Staff[0]",        { 0x9E, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 } },
  { "Staff seven charges",   "Knockback Staff[7]",        { 0x9E, 0x08, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00 } },
  { "Empty Pot",             "Preservation Pot[0]",       { 0xB8, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 } },
  { "Pot capacity",          "Preservation Pot[5]",       { 0xB8, 0x09, 0x05, 0x00, 0x00, 0xFF, 0x00, 0x00 } },
}

local function report(message)
  print(message)
  emu.log(message)
end

local function rd(address)
  return emu.read(address, workMem)
end

local function wr(address, value)
  emu.write(address, value, workMem)
  assert(rd(address) == value, string.format("write failed at $%04X", address))
end

local function recordIsZero(index)
  for offset = 0, OBJECT_SIZE - 1 do
    if rd(OBJECTS + index * OBJECT_SIZE + offset) ~= 0 then return false end
  end
  return true
end

local function identifyRoot(root)
  wr(IDENTIFICATION + root * 2, IDENTIFIED)
  -- Keep any existing custom-name mapping. Only the appearance byte controls
  -- whether the formatter chooses the translated identified name.
end

local function injectGallery()
  assert(workMem ~= nil, "Mesen does not expose flat Game Boy Work RAM")
  assert(#GALLERY == INVENTORY_SLOTS, "gallery must fill exactly twenty slots")

  -- Resolve every target before writing anything. A partially installed gallery
  -- would be harder to recognize and could overwrite a live dungeon object.
  local targets = {}
  for object = 0, OBJECT_COUNT - 1 do
    if recordIsZero(object) then
      table.insert(targets, object)
      if #targets == #GALLERY then break end
    end
  end
  assert(#targets == #GALLERY, "fewer than twenty cleared object records are available")

  for slot, row in ipairs(GALLERY) do
    local object = targets[slot]
    for offset, value in ipairs(row[3]) do
      wr(OBJECTS + object * OBJECT_SIZE + offset - 1, value)
    end
    wr(INVENTORY + slot - 1, object)
  end

  -- Strength Bracelet, Knockback Staff, and Preservation Pot roots.
  identifyRoot(0x09)
  identifyRoot(0x51)
  identifyRoot(0x6B)
  emu.write(ACTION_FLAGS, emu.read(ACTION_FLAGS, cpuMem) & (~ACTION_INHIBIT_MASK & 0xFF), cpuMem)

  report("Item formatting gallery installed. Page 1:")
  for index = 1, 10 do
    report(string.format("  %2d. %-22s -> %s", index, GALLERY[index][1], GALLERY[index][2]))
  end
  report("Page 2 (press Right):")
  for index = 11, 20 do
    report(string.format("  %2d. %-22s -> %s", index - 10, GALLERY[index][1], GALLERY[index][2]))
  end
  report("Do not sort. Close/reopen Items if it was already visible.")
end

local fixturePath = os.getenv("GB2_ITEM_GALLERY_MSS")
if fixturePath == nil or fixturePath == "" then
  injectGallery()
else
  local frame = 0
  local loaded = false
  local PAGE_1_SCREEN = 0xB9899EFF
  local PAGE_2_SCREEN = 0xEA1E7AC7
  local page1Checksum = 0

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

  local function loadOnce()
    if loaded then return end
    loaded = true
    emu.loadSavestate(loadFile(fixturePath))
    injectGallery()
    report("gallery fixture loaded")
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
    pressAt(input, 480, "right")
    emu.setInput(input, 0)
  end

  local function saveScreenshot(variable)
    local path = os.getenv(variable)
    if path == nil or path == "" then return end
    local file = assert(io.open(path, "wb"))
    file:write(emu.takeScreenshot())
    file:close()
  end

  local function afterFrame()
    if not loaded then return end
    if frame == 400 then
      local checksum = screenChecksum()
      page1Checksum = checksum
      report(string.format("gallery page 1 screen=%08X", checksum))
      if PAGE_1_SCREEN ~= 0 then assert(checksum == PAGE_1_SCREEN, "page 1 screen changed") end
      saveScreenshot("GB2_ITEM_GALLERY_PAGE1_SCREENSHOT")
    elseif frame == 700 then
      local checksum = screenChecksum()
      report(string.format("gallery page 2 screen=%08X", checksum))
      if PAGE_2_SCREEN ~= 0 then assert(checksum == PAGE_2_SCREEN, "page 2 screen changed") end
      saveScreenshot("GB2_ITEM_GALLERY_PAGE2_SCREENSHOT")
      report(string.format("PASS item-formatting-gallery page1=%08X page2=%08X", page1Checksum, checksum))
      emu.stop(0)
    elseif frame > 1000 then
      error("timed out while rendering the item-formatting gallery")
    end
    frame = frame + 1
  end

  emu.addMemoryCallback(loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
  emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
  emu.addEventCallback(afterFrame, emu.eventType.endFrame)
end
