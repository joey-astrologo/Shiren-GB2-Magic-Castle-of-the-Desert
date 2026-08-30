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

local function hexBytes(address, size, memType)
  local values = {}
  for offset = 0, size - 1 do
    values[#values + 1] = string.format(
      "%02X", emu.read(address + offset, memType))
  end
  return table.concat(values)
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_ENTRY_MSS"))))
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
  -- four explanatory dialogue pages and open the graphical editor.
  pressAt(input, 90, "a")
  pressAt(input, 390, "a")
  pressAt(input, 720, "a")
  pressAt(input, 1120, "a")
  pressAt(input, 1520, "a")
  if editorAt ~= nil then
    playSequence(input, editorAt + 240, characterInputs)
  end
  if confirmAt ~= nil then
    playSequence(input, confirmAt, confirmInputs)
  end
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded then return end

  if editorAt == nil and
      emu.read(0xC195, cpuMem) == 0x08 and
      emu.read(0xC14E, cpuMem) == 0xF5 and
      emu.read(0xC152, cpuMem) == 0x00 then
    editorAt = frame
    report(string.format(
      "localized rescue editor reached frame=%d screen=%08X node=%02X",
      frame, checksum(), emu.read(0xC14F, cpuMem)))
  end
  if editorAt ~= nil and characterDoneAt == nil then
    if frame == editorAt + 220 then
      local editorScreenshot = os.getenv("GB2_RESCUE_EDITOR_SCREENSHOT")
      if editorScreenshot ~= nil and editorScreenshot ~= "" then
        local file = assert(io.open(editorScreenshot, "wb"))
        file:write(emu.takeScreenshot())
        file:close()
      end
      assert(
        checksum() == EXPECTED_EDITOR_SCREEN,
        string.format("localized editor mismatch: %08X", checksum()))
      assert(
        hexBytes(0x016D, 14, workMem) ==
          "D5D5D5D5D5D5D5D5D5D5D5D5D5FF",
        "localized editor did not open with an empty native buffer")
    end
    local done = editorAt + 240 + #characterInputs * 15 + 30
    if frame >= done then
      characterDoneAt = frame
      local buffer = hexBytes(0x016D, 14, workMem)
      report(string.format(
        "rescue code entered frame=%d screen=%08X node=%02X pos=%02X buffer=%s",
        frame, checksum(), emu.read(0xC14F, cpuMem),
        emu.read(0xC152, cpuMem), buffer))
      -- The native full-field convention leaves the cursor index on the
      -- thirteenth (zero-based $0C) cell while the terminator sits after it.
      assert(
        emu.read(0xC152, cpuMem) == 0x0C,
        "localized SOS entry did not fill thirteen cells")
      assert(buffer == EXPECTED_NATIVE .. "FF", "native SOS input differs")
      confirmAt = frame + 60
    end
  end

  if confirmAt ~= nil and characterDoneAt ~= nil then
    local done = confirmAt + #confirmInputs * 15 + 420
    if frame >= done then
      local finalScreen = checksum()
      local finalBuffer = hexBytes(0x016D, 14, workMem)
      if EXPECTED_RESULT_SCREEN ~= nil then
        assert(
          finalScreen == tonumber(EXPECTED_RESULT_SCREEN, 16),
          string.format("native validation response mismatch: %08X", finalScreen))
      end
      if EXPECTED_POST_NATIVE ~= nil then
        assert(finalBuffer == EXPECTED_POST_NATIVE, "post-validation buffer changed")
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
    error("timed out while replaying Rescue Password entry")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
