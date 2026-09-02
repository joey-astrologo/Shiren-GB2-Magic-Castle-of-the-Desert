-- Rescue Team -> Password entry regression.
--
-- Starts from SaveStates/rescue-entry-menu.mss, reaches the editor using only
-- controller input, enters a complete localized SOS password, proves that the
-- buffer contains its exact native symbols, and submits it to the original
-- validator.

local frame = 0
local loaded = false
local editorAt = nil
local characterDoneAt = nil
local confirmAt = nil
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local EXPECTED_EDITOR_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_EDITOR_SCREEN")), 16)
local EXPECTED_NATIVE = assert(os.getenv("GB2_RESCUE_EXPECTED_NATIVE"))
local EXPECTED_RESULT_SCREEN = os.getenv("GB2_RESCUE_EXPECTED_RESULT_SCREEN")
local EXPECTED_POST_NATIVE = os.getenv("GB2_RESCUE_EXPECTED_POST_NATIVE")
local EXPECTED_HARDWARE_B_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_HARDWARE_B_SCREEN")), 16)
local uppercasePrefixField = nil
local interactionAt = nil

local function splitButtons(value)
  local result = {}
  for button in string.gmatch(value or "", "[^,]+") do
    result[#result + 1] = button
  end
  return result
end

local characterInputs = splitButtons(
  assert(os.getenv("GB2_RESCUE_CHARACTER_INPUTS")))
local confirmInputs = splitButtons(
  assert(os.getenv("GB2_RESCUE_CONFIRM_INPUTS")))

local function report(message)
  print(message)
  emu.log(message)
end

local function check(condition, message)
  if condition then return true end
  report("FAIL " .. message)
  emu.stop(1)
  return false
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

local function fieldChecksum()
  local hash = 2166136261
  local pixels = emu.getScreenBuffer()
  -- Compare only the password glyph band. The insertion underline blinks and
  -- changes position during deletion, so including its scanlines would make a
  -- correct uppercase glyph appear different for an unrelated cursor reason.
  for y = 0, 15 do
    for x = 0, 159 do
      local pixel = pixels[y * 160 + x + 1]
      hash = ((hash ~ pixel) * 16777619) & 0xFFFFFFFF
    end
  end
  return hash
end

local function hexBytes(address, size, memType)
  local values = {}
  for offset = 0, size - 1 do
    values[#values + 1] = string.format(
      "%02X", emu.read(address + offset, memType))
  end
  return table.concat(values)
end

local function expectedBuffer(prefix, blank)
  return prefix .. string.rep(string.format("%02X", blank), 13 - #prefix / 2)
    .. "FF"
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_ENTRY_MSS"))))
  -- The supplied capture happened to retain mode 8 from an earlier Password
  -- visit. A normal town route may carry any previous graphical-input mode in
  -- WRAM until this constructor receives the requested mode in register C.
  -- Force that real boundary condition so a hook that trusts stale $C195 must
  -- display Japanese and fail this route.
  emu.write(0xC195, 0x00, cpuMem)
  report("rescue Password-menu fixture loaded")
end

local function pressAt(input, at, button)
  if frame >= at and frame < at + 5 then input[button] = true end
end

local function playSequence(input, startAt, sequence)
  if startAt == nil then return end
  for index, button in ipairs(sequence) do
    pressAt(input, startAt + (index - 1) * 15, button)
  end
end

local function inputForFrame()
  if not loaded then return end
  local input = {
    a = false, b = false, start = false, select = false,
    up = false, down = false, left = false, right = false,
  }
  -- Password is already selected in the fixture. These presses advance its
  -- explanatory dialogue and open the graphical editor. The final press is
  -- intentionally delayed until the complete English prompt has finished;
  -- pressing through the drawing text is not equivalent to a player's tap.
  pressAt(input, 90, "a")
  pressAt(input, 390, "a")
  pressAt(input, 720, "a")
  pressAt(input, 1120, "a")
  if frame == 3200 then input.a = true end
  if editorAt ~= nil then
    -- Allow the constructor transition and the dialogue-confirm release latch
    -- to settle before the first character input.
    interactionAt = editorAt + 400
    -- Exercise the hardware-B path that bypasses the selected-node handler:
    -- enter AB, delete B, and leave A for the frozen localized redraw check.
    pressAt(input, interactionAt + 20, "a")
    pressAt(input, interactionAt + 50, "right")
    pressAt(input, interactionAt + 80, "a")
    pressAt(input, interactionAt + 120, "b")
    -- Clear A and return the keyboard cursor from B to A before entering the
    -- complete public fixture vector.
    pressAt(input, interactionAt + 220, "b")
    pressAt(input, interactionAt + 260, "left")
    playSequence(input, interactionAt + 380, characterInputs)
  end
  if confirmAt ~= nil then
    playSequence(input, confirmAt, confirmInputs)
  end
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded then return end

  if editorAt == nil and emu.read(0xC195, cpuMem) == 0x08 and
      emu.read(0xC14E, cpuMem) == 0xF5 then
    editorAt = frame
    report(string.format(
      "localized rescue editor reached frame=%d screen=%08X node=%02X",
      frame, checksum(), emu.read(0xC14F, cpuMem)))
  end
  if editorAt ~= nil and characterDoneAt == nil then
    if frame == interactionAt then
      local editorScreenshot = os.getenv("GB2_RESCUE_EDITOR_SCREENSHOT")
      if editorScreenshot ~= nil and editorScreenshot ~= "" then
        local file = assert(io.open(editorScreenshot, "wb"))
        file:write(emu.takeScreenshot())
        file:close()
      end
      if EXPECTED_EDITOR_SCREEN ~= 0 then
        if not check(checksum() == EXPECTED_EDITOR_SCREEN,
          string.format("localized editor mismatch: %08X", checksum()))
          then return end
      end
      local emptyBuffer = hexBytes(0x016D, 14, workMem)
      if not check(emptyBuffer == expectedBuffer("", 0xD5),
        "native constructor did not initialize the rescue buffer: " .. emptyBuffer)
        then return end
      report(string.format(
        "localized rescue editor ready node=%02X pos=%02X buffer=%s",
        emu.read(0xC14F, cpuMem), emu.read(0xC152, cpuMem), emptyBuffer))
    end
    if frame == interactionAt + 60 then
      uppercasePrefixField = fieldChecksum()
      local uppercaseBuffer = hexBytes(0x016D, 14, workMem)
      if not check(uppercaseBuffer == expectedBuffer("30", 0xD5),
        "uppercase reference field does not contain exactly native A: " ..
          uppercaseBuffer)
        then return end
    end
    if frame == interactionAt + 180 then
      local buffer = hexBytes(0x016D, 14, workMem)
      local hardwareBScreen = checksum()
      report(string.format(
        "localized hardware-B redraw screen=%08X pos=%02X buffer=%s",
        hardwareBScreen, emu.read(0xC152, cpuMem), buffer))
      local hardwareBScreenshot = os.getenv(
        "GB2_RESCUE_HARDWARE_B_SCREENSHOT")
      if hardwareBScreenshot ~= nil and hardwareBScreenshot ~= "" then
        local file = assert(io.open(hardwareBScreenshot, "wb"))
        file:write(emu.takeScreenshot())
        file:close()
      end
      if not check(emu.read(0xC152, cpuMem) == 0x01,
        "hardware B did not delete exactly one rescue character")
        then return end
      if not check(buffer == expectedBuffer("30", 0xD5),
        "hardware B changed the native rescue buffer incorrectly")
        then return end
      if not check(uppercasePrefixField ~= nil and
          fieldChecksum() == uppercasePrefixField,
        "hardware B changed the visible uppercase A field")
        then return end
      if EXPECTED_HARDWARE_B_SCREEN ~= 0 then
        if not check(hardwareBScreen == EXPECTED_HARDWARE_B_SCREEN,
          "hardware B did not redraw the remaining character in English")
          then return end
      end
    end
    if frame == interactionAt + 320 then
      if not check(
          hexBytes(0x016D, 14, workMem) == expectedBuffer("", 0xD5),
        "hardware-B setup did not restore an empty rescue buffer")
        then return end
      if not check(emu.read(0xC14F, cpuMem) == 0x00,
        "hardware-B setup did not return the cursor to A") then return end
    end
    local done = interactionAt + 380 + #characterInputs * 15 + 30
    if frame >= done then
      characterDoneAt = frame
      local buffer = hexBytes(0x016D, 14, workMem)
      report(string.format(
        "rescue code entered frame=%d screen=%08X node=%02X pos=%02X buffer=%s",
        frame, checksum(), emu.read(0xC14F, cpuMem),
        emu.read(0xC152, cpuMem), buffer))
      -- The native full-field convention leaves the cursor index on the
      -- thirteenth (zero-based $0C) cell while the terminator sits after it.
      if not check(emu.read(0xC152, cpuMem) == 0x0C,
        "localized SOS entry did not fill thirteen cells") then return end
      if not check(buffer == EXPECTED_NATIVE .. "FF",
        "native SOS input differs") then return end
      confirmAt = frame + 60
    end
  end

  if confirmAt ~= nil and characterDoneAt ~= nil then
    local done = confirmAt + #confirmInputs * 15 + 420
    if frame >= done then
      local finalScreen = checksum()
      local finalBuffer = hexBytes(0x016D, 14, workMem)
      if EXPECTED_RESULT_SCREEN ~= nil and
          tonumber(EXPECTED_RESULT_SCREEN, 16) ~= 0 then
        if not check(finalScreen == tonumber(EXPECTED_RESULT_SCREEN, 16),
          string.format("native validation response mismatch: %08X", finalScreen))
          then return end
      end
      if EXPECTED_POST_NATIVE ~= nil then
        if not check(finalBuffer == EXPECTED_POST_NATIVE,
          "post-validation buffer changed") then return end
      end
      local message = string.format(
        "PASS rescue input submitted frame=%d screen=%08X mode=%02X node=%02X pos=%02X buffer=%s",
        frame, finalScreen, emu.read(0xC195, cpuMem),
        emu.read(0xC14F, cpuMem), emu.read(0xC152, cpuMem),
        finalBuffer)
      local screenshot = os.getenv("GB2_SCREENSHOT")
      if screenshot ~= nil and screenshot ~= "" then
        local file = assert(io.open(screenshot, "wb"))
        file:write(emu.takeScreenshot())
        file:close()
      end
      report(message)
      emu.stop(0)
    end
  elseif frame > 5000 then
    check(false, "timed out while replaying Rescue Password entry")
    return
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
