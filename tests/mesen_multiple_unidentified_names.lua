-- Reproduce the user-reported multi-item custom-name alias from the supplied
-- state. This route uses controller input only and never edits emulated memory.

local frame = 0
local loaded = false
local finished = false
local editorCount = 0
local editorAt = nil
local fillAt = nil
local potTokenAt = nil
local secondMenuAt = nil
local secondTokenAt = nil
local leftFirstEditor = false
local escapeSeen = false
local lastMode = nil
local lastNav = nil
local lastNode = nil

local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local POT_ROOT = 107       -- Preservation
local SCROLL_ITEM_ROOT = 50 -- Windblade Scroll presented as Rabbit Scroll
local SCROLL_NAME_ROOT = 67 -- Escape
local IDENTIFICATION = 0x2C82
local CUSTOM_NAMES = 0x2D78

local function loadFile(path)
  local file = assert(io.open(path, "rb"))
  local data = file:read("*all")
  file:close()
  return data
end

local function report(message)
  print(message)
  emu.log(message)
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_MULTIPLE_UNIDENTIFIED_MSS"))))
end

local function rd(address)
  return emu.read(address, cpuMem)
end

local function workRead(address)
  return emu.read(address, workMem)
end

local function customSlot(root)
  return workRead(IDENTIFICATION + root * 2 + 1)
end

local function pressAt(input, at, button)
  if at ~= nil and frame >= at and frame < at + 5 then
    input[button] = true
  end
end

local function actionMenu(input, at, moveUp)
  pressAt(input, at, moveUp and "up" or "a")
  pressAt(input, at + 60, "a")
  pressAt(input, at + 120, "down")
  pressAt(input, at + 180, "down")
  pressAt(input, at + 240, "down")
  pressAt(input, at + 340, "a")
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a=false, b=false, start=false, select=false,
    up=false, down=false, left=false, right=false,
  }

  -- The supplied state is already on Items with the final Pot selected.
  if editorCount == 0 then
    pressAt(input, 60, "a")
    pressAt(input, 120, "down")
    pressAt(input, 180, "down")
    pressAt(input, 240, "down")
    pressAt(input, 300, "down")
    pressAt(input, 400, "a")
  elseif editorCount == 1 and potTokenAt == nil and fillAt == nil then
    -- From A: Up -> left caret, Right -> right caret, Up -> FILL IN.
    pressAt(input, editorAt + 60, "up")
    pressAt(input, editorAt + 90, "right")
    pressAt(input, editorAt + 120, "up")
    pressAt(input, editorAt + 160, "a")
  elseif editorCount == 1 and potTokenAt == nil then
    pressAt(input, fillAt + 50, "a")
    pressAt(input, fillAt + 110, "right")
    pressAt(input, fillAt + 170, "a")
  elseif potTokenAt ~= nil and editorCount == 1 then
    -- Items returns to the Pot. Move up to the unidentified Scroll, then Name.
    actionMenu(input, secondMenuAt, true)
  elseif editorCount == 2 and fillAt == nil then
    pressAt(input, editorAt + 60, "up")
    pressAt(input, editorAt + 90, "right")
    pressAt(input, editorAt + 120, "up")
    pressAt(input, editorAt + 160, "a")
  elseif editorCount == 2 and secondTokenAt == nil then
    pressAt(input, fillAt + 50, "a")
    pressAt(input, fillAt + 110, "right")
    pressAt(input, fillAt + 170, "a")
  end
  emu.setInput(input, 0)
end

local function finish(ok, message)
  report((ok and "PASS " or "FAIL ") .. message)
  finished = true
  emu.stop(ok and 0 or 1)
end

local function afterFrame()
  if not loaded or finished then return end
  local mode = rd(0xC195)
  local nav = rd(0xC14E)
  local node = rd(0xC14F)
  if mode ~= lastMode or nav ~= lastNav or node ~= lastNode then
    report(string.format(
      "frame=%d mode=%02X nav=%02X node=%02X match=%02X pot=%02X scroll=%02X",
      frame, mode, nav, node, rd(0xC196), customSlot(POT_ROOT),
      customSlot(SCROLL_ITEM_ROOT)))
    lastMode, lastNav, lastNode = mode, nav, node
  end

  if potTokenAt ~= nil and nav ~= 0xF4 then
    leftFirstEditor = true
  end

  if nav == 0xF4 and mode == 0 and editorAt == nil
      and (editorCount == 0 or leftFirstEditor) then
    editorCount = editorCount + 1
    editorAt = frame
    fillAt = nil
    report("mode-0 editor " .. editorCount .. " opened at frame " .. frame)
  end

  if editorAt ~= nil and fillAt == nil and rd(0xC153) == 14
      and rd(0xC196) ~= 0xFF then
    local expected = editorCount == 1 and POT_ROOT or 50
    if rd(0xC196) ~= expected then
      finish(false, string.format(
        "editor %d recalled root %d, expected %d",
        editorCount, rd(0xC196), expected))
      return
    end
    fillAt = frame
    report(string.format("editor %d recalled root %d", editorCount, expected))
  end

  if editorCount == 2 and fillAt ~= nil and not escapeSeen
      and rd(0xC196) == SCROLL_NAME_ROOT then
    escapeSeen = true
    report("editor 2 cycled once to Escape root 67")
  end

  if editorCount == 1 and potTokenAt == nil and customSlot(POT_ROOT) ~= 0xFF then
    potTokenAt = frame
    secondMenuAt = frame + 150
    editorAt = nil
    fillAt = nil
    report(string.format(
      "Preservation accepted at frame %d custom-slot=%d",
      frame, customSlot(POT_ROOT)))
  elseif editorCount == 2 and secondTokenAt == nil
      and customSlot(SCROLL_ITEM_ROOT) ~= 0xFF then
    secondTokenAt = frame
    report(string.format(
      "Escape accepted at frame %d custom-slot=%d",
      frame, customSlot(SCROLL_ITEM_ROOT)))
  elseif secondTokenAt ~= nil and frame >= secondTokenAt + 30 then
    local potSlot = customSlot(POT_ROOT)
    local scrollSlot = customSlot(SCROLL_ITEM_ROOT)
    local potRoot = workRead(CUSTOM_NAMES + potSlot * 8 + 2)
    local scrollRoot = workRead(CUSTOM_NAMES + scrollSlot * 8 + 2)
    finish(
      potSlot ~= scrollSlot and potRoot == POT_ROOT
        and scrollRoot == SCROLL_NAME_ROOT,
      string.format(
        "canonical names own distinct slots " ..
        "(pot-slot=%d pot-root=%d scroll-slot=%d scroll-root=%d)",
        potSlot, potRoot, scrollSlot, scrollRoot))
    return
  end

  if frame > 2200 then
    finish(false, string.format(
      "route timed out (editors=%d pot=%02X scroll=%02X nav=%02X node=%02X)",
      editorCount, customSlot(POT_ROOT), customSlot(SCROLL_ITEM_ROOT), nav, node))
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
