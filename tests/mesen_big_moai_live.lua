-- Exact live Big Moai spell regression.
--
-- Loads the user-supplied locked fixture, imports the production unlock
-- helper, speaks to the real NPC, enters WISH through the localized mode-3
-- keyboard, and requires the native reward route to add Fortune Grass.

dofile(assert(os.getenv("GB2_BIG_MOAI_HELPER")))

local frame = 0
local loaded = false
local editorAt = nil
local editorChecked = false
local wishReady = false
local wishReadyAt = nil
local deleteChecked = false
local okChecked = false
local validSpellAt = nil
local rewardDialogueAt = nil
local cooldownDialogueAt = nil
local rewardObject = nil
local rewardChecked = false
local promptChecked = false
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local EXPECTED_EDITOR_SCREEN = tonumber(
  assert(os.getenv("GB2_BIG_MOAI_EDITOR_SCREEN")), 16)
local EXPECTED_DELETE_SCREEN = tonumber(
  assert(os.getenv("GB2_BIG_MOAI_DELETE_SCREEN")), 16)
local EXPECTED_OK_SCREEN = tonumber(
  assert(os.getenv("GB2_BIG_MOAI_OK_SCREEN")), 16)
local EXPECTED_PROMPT_SCREEN = tonumber(
  assert(os.getenv("GB2_BIG_MOAI_PROMPT_SCREEN")), 16)
local EXPECTED_REWARD_SCREEN = tonumber(
  assert(os.getenv("GB2_BIG_MOAI_REWARD_SCREEN")), 16)

local INVENTORY = 0x12C1
local INVENTORY_SLOTS = 20
local OBJECTS = 0x2482
local OBJECT_SIZE = 8
local FORTUNE_GRASS = 0x70
local WISH = { 0x20, 0x12, 0x1C, 0x11, 0xFF }

-- Shortest stable paths through the installed navigation graph. After the
-- fourth character the native controller automatically selects OK, so the
-- final A submits directly.
local wishInputs = {
  "left", "left", "left", "a",               -- W
  "up", "down", "down", "left", "left", "a", -- I
  "down", "down", "a",                         -- S
  "up", "up", "left", "a",                    -- H
  "a",                                             -- auto-selected OK
}

local function report(message)
  print(message)
  emu.log(message)
end

local function loadFile(path)
  local file = assert(io.open(path, "rb"))
  local data = file:read("*all")
  file:close()
  return data
end

local function checksum()
  local hash = 2166136261
  for _, pixel in ipairs(emu.getScreenBuffer()) do
    hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
  end
  return hash
end

local function rd(address, memType)
  return emu.read(address, memType)
end

local function bufferMatches(expected)
  for offset, value in ipairs(expected) do
    if rd(0x016D + offset - 1, workMem) ~= value then return false end
  end
  return true
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_BIG_MOAI_MSS"))))
  assert(rd(0xC3EF, cpuMem) == 0x06, "fixture active story stage changed")
  assert(rd(0xC3F0, cpuMem) == 0x06, "fixture story-stage shadow changed")
  for slot = 0, INVENTORY_SLOTS - 1 do
    assert(rd(INVENTORY + slot, workMem) == 0xFF, "fixture inventory is no longer empty")
  end
  local ok, changed, oldStage = gb2UnlockBigMoai()
  assert(ok and changed and oldStage == 0x06, "production helper did not unlock fixture")
  report("Big Moai locked fixture minimally unlocked")
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
  pressAt(input, 120, "a")
  pressAt(input, 420, "a")
  pressAt(input, 720, "a")
  if editorAt ~= nil then
    -- Visit DEL from the initial A node, then return to A before entering WISH.
    pressAt(input, editorAt + 75, "up")
    pressAt(input, editorAt + 105, "down")
    for index, button in ipairs(wishInputs) do
      pressAt(input, editorAt + 135 + (index - 1) * 15, button)
    end
  end
  if rewardDialogueAt ~= nil then
    pressAt(input, rewardDialogueAt + 180, "a") -- close the reward message
    pressAt(input, rewardDialogueAt + 300, "a") -- speak to Big Moai again
  end
  emu.setInput(input, 0)
end

local function traceTextLookup()
  if not loaded then return end
  local state = emu.getState()
  local group = state["cpu.a"]
  local index = state["cpu.c"]
  if group ~= 0x6A then return end
  report(string.format("Big Moai dialogue group=%02X index=%02X frame=%d", group, index, frame))
  if index == 0x11 then validSpellAt = frame end
  if index == 0x12 then rewardDialogueAt = frame end
  if index == 0x1A then cooldownDialogueAt = frame end
end

local function findReward()
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object = rd(INVENTORY + slot, workMem)
    if object ~= 0xFF then
      local item = rd(OBJECTS + object * OBJECT_SIZE, workMem)
      assert(item == FORTUNE_GRASS, string.format(
        "Big Moai added item $%02X instead of Fortune Grass", item))
      return object
    end
  end
  return nil
end

local function afterFrame()
  if not loaded then return end
  if editorAt == nil and rd(0xC195, cpuMem) == 0x03 and
      rd(0xC14F, cpuMem) == 0x00 and rd(0xC152, cpuMem) == 0x00 then
    editorAt = frame
    report("localized Big Moai editor reached at frame " .. frame)
  end
  if not promptChecked and frame == 150 then
    local screen = checksum()
    assert(screen == EXPECTED_PROMPT_SCREEN, string.format(
      "localized Big Moai prompt mismatch: %08X", screen))
    promptChecked = true
    report(string.format("localized Big Moai prompt screen=%08X", screen))
  end
  if editorAt ~= nil and not editorChecked and frame >= editorAt + 60 then
    local screen = checksum()
    report(string.format("localized Big Moai editor screen=%08X", screen))
    local editorScreenshot = os.getenv("GB2_EDITOR_SCREENSHOT")
    if editorScreenshot ~= nil and editorScreenshot ~= "" then
      local file = assert(io.open(editorScreenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    if screen ~= EXPECTED_EDITOR_SCREEN then
      report(string.format("localized Big Moai editor mismatch: %08X", screen))
      emu.stop(1)
      return
    end
    editorChecked = true
  end
  if editorAt ~= nil and not deleteChecked and frame >= editorAt + 90 then
    local screen = checksum()
    report(string.format("localized Big Moai DEL screen=%08X", screen))
    local deleteScreenshot = os.getenv("GB2_DELETE_SCREENSHOT")
    if deleteScreenshot ~= nil and deleteScreenshot ~= "" then
      local file = assert(io.open(deleteScreenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    if screen ~= EXPECTED_DELETE_SCREEN then
      report(string.format("localized Big Moai DEL mismatch: %08X", screen))
      emu.stop(1)
      return
    end
    deleteChecked = true
  end
  if editorAt ~= nil and not wishReady and
      rd(0xC14F, cpuMem) == 0x33 and rd(0xC152, cpuMem) == 0x03 and
      bufferMatches(WISH) then
    wishReady = true
    wishReadyAt = frame
    report("WISH entered and native OK node auto-selected")
  end
  if wishReadyAt ~= nil and not okChecked and frame >= wishReadyAt + 8 then
    local screen = checksum()
    report(string.format("localized Big Moai OK screen=%08X", screen))
    local okScreenshot = os.getenv("GB2_OK_SCREENSHOT")
    if okScreenshot ~= nil and okScreenshot ~= "" then
      local file = assert(io.open(okScreenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    if screen ~= EXPECTED_OK_SCREEN then
      report(string.format("localized Big Moai OK mismatch: %08X", screen))
      emu.stop(1)
      return
    end
    okChecked = true
  end
  if rewardObject == nil then rewardObject = findReward() end
  if rewardDialogueAt ~= nil and not rewardChecked and
      frame == rewardDialogueAt + 150 then
    local screen = checksum()
    assert(screen == EXPECTED_REWARD_SCREEN, string.format(
      "localized Big Moai reward mismatch: %08X", screen))
    rewardChecked = true
    report(string.format("localized Big Moai reward screen=%08X", screen))
    local screenshot = os.getenv("GB2_SCREENSHOT")
    if screenshot ~= nil and screenshot ~= "" then
      local file = assert(io.open(screenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
  end

  -- Inventory insertion alone is not success. The original broken regression
  -- passed here while the CPU was stuck executing graphics data at 03:$4F0E.
  -- Reaching a fresh follow-up conversation proves that the reward message
  -- returned cleanly to normal NPC interaction.
  if cooldownDialogueAt ~= nil and frame >= cooldownDialogueAt + 60 then
    assert(promptChecked, "localized Big Moai prompt framebuffer was not checked")
    assert(editorChecked, "localized editor framebuffer was not checked")
    assert(deleteChecked, "localized DEL cursor framebuffer was not checked")
    assert(okChecked, "localized OK cursor framebuffer was not checked")
    assert(rewardChecked, "localized reward framebuffer was not checked")
    assert(wishReady, "WISH was not present before submission")
    assert(validSpellAt ~= nil, "native valid-spell branch was not reached")
    assert(rewardObject ~= nil, "Fortune Grass was not added to inventory")
    report(string.format(
      "PASS big-moai-live code=WISH item=%02X object=%02X post=1A prompt=%08X editor=%08X del=%08X ok=%08X reward=%08X",
      FORTUNE_GRASS, rewardObject, EXPECTED_PROMPT_SCREEN,
      EXPECTED_EDITOR_SCREEN, EXPECTED_DELETE_SCREEN, EXPECTED_OK_SCREEN,
      EXPECTED_REWARD_SCREEN))
    emu.stop(0)
  elseif frame > 3000 then
    error("timed out before Big Moai awarded Fortune Grass")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addMemoryCallback(
  traceTextLookup, emu.callbackType.exec, 0x1F58, 0x1F58, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
