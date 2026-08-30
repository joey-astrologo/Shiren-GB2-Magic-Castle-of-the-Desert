-- Requester-side Revival Password regression.
--
-- Starts from the captured SOS guide, opens Adventure -> Revive! -> Password,
-- enters a deterministic no-gift Revival Password through the localized
-- 15-character editor, and observes the native success/Thank-You route.

local frame = 0
local loaded = false
local editorAt = nil
local enteredAt = nil
local confirmAt = nil
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local EXPECTED_NATIVE = assert(os.getenv("GB2_REVIVAL_EXPECTED_NATIVE"))
local EXPECTED_EDITOR_SCREEN = tonumber(
  assert(os.getenv("GB2_REVIVAL_EXPECTED_EDITOR_SCREEN")), 16)
local EXPECTED_ENTERED_SCREEN = tonumber(
  assert(os.getenv("GB2_REVIVAL_EXPECTED_ENTERED_SCREEN")), 16)
local EXPECTED_SUCCESS_SCREEN = tonumber(
  assert(os.getenv("GB2_REVIVAL_EXPECTED_SUCCESS_SCREEN")), 16)
local EXPECTED_THANK_YOU_SCREEN = tonumber(
  assert(os.getenv("GB2_REVIVAL_EXPECTED_THANK_YOU_SCREEN")), 16)
local EXPECTED_THANK_YOU_NATIVE = assert(
  os.getenv("GB2_REVIVAL_EXPECTED_THANK_YOU_NATIVE"))

local function splitButtons(value)
  local result = {}
  for button in string.gmatch(value or "", "[^,]+") do
    result[#result + 1] = button
  end
  return result
end

local characterInputs = splitButtons(
  assert(os.getenv("GB2_REVIVAL_CHARACTER_INPUTS")))
local confirmInputs = splitButtons(
  assert(os.getenv("GB2_REVIVAL_CONFIRM_INPUTS")))

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

local function report(message)
  print(message)
  emu.log(message)
end

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_REVIVAL_REQUESTER_MSS"))))
  report("rescue requester SOS fixture loaded")
end

local function pressAt(input, at, button)
  if frame >= at and frame < at + 2 then input[button] = true end
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

  -- Close the SOS guide, open Adventure, open its action menu, select
  -- Revive!, and choose Password.
  pressAt(input, 120, "a")
  pressAt(input, 360, "a")
  pressAt(input, 600, "down")
  pressAt(input, 660, "a")
  pressAt(input, 780, "a")
  pressAt(input, 1140, "a")

  if editorAt ~= nil then
    playSequence(input, editorAt + 180, characterInputs)
  end
  if confirmAt ~= nil then
    playSequence(input, confirmAt, confirmInputs)
    -- Advance from the Revival-complete notice to the Thank-You Password.
    pressAt(input, confirmAt + #confirmInputs * 15 + 480, "a")
  end
  emu.setInput(input, 0)
end

local function saveScreenshot(suffix)
  local root = os.getenv("GB2_REVIVAL_SCREENSHOTS")
  if root == nil or root == "" then return end
  local file = assert(io.open(root .. "-" .. suffix .. ".png", "wb"))
  file:write(emu.takeScreenshot())
  file:close()
end

local function afterFrame()
  if not loaded then return end

  if editorAt == nil and
      emu.read(0xC195, cpuMem) == 0x07 and
      emu.read(0xC14E, cpuMem) == 0xF5 and
      emu.read(0xC152, cpuMem) == 0x00 then
    editorAt = frame
    assert(checksum() == EXPECTED_EDITOR_SCREEN, "localized Revival editor changed")
    report(string.format(
      "localized Revival editor reached frame=%d screen=%08X",
      frame, checksum()))
    saveScreenshot("editor")
  end

  if editorAt ~= nil and enteredAt == nil then
    local done = editorAt + 180 + #characterInputs * 15 + 30
    if frame >= done then
      enteredAt = frame
      local buffer = hexBytes(0x016D, 16, workMem)
      assert(
        emu.read(0xC152, cpuMem) == 0x0E,
        "localized Revival entry did not fill fifteen cells")
      assert(
        emu.read(0xC14F, cpuMem) == 0x4D,
        "full Revival field did not move the cursor to OK")
      assert(buffer == EXPECTED_NATIVE .. "FF", "native Revival input differs")
      assert(checksum() == EXPECTED_ENTERED_SCREEN, "entered Revival screen changed")
      report(string.format(
        "Revival code entered frame=%d screen=%08X buffer=%s",
        frame, checksum(), buffer))
      saveScreenshot("entered")
      confirmAt = frame + 60
    end
  end

  if confirmAt ~= nil then
    local submitted = confirmAt + #confirmInputs * 15 + 300
    local thankYou = confirmAt + #confirmInputs * 15 + 780
    if frame == submitted then
      assert(checksum() == EXPECTED_SUCCESS_SCREEN, "Revival success screen changed")
      report(string.format(
        "Revival submitted frame=%d screen=%08X mode=%02X buffer=%s",
        frame, checksum(), emu.read(0xC195, cpuMem),
        hexBytes(0x016D, 16, workMem)))
      saveScreenshot("submitted")
    elseif frame == thankYou then
      assert(
        checksum() == EXPECTED_THANK_YOU_SCREEN,
        "Thank-You Password screen changed")
      assert(
        hexBytes(0x016D, 13, workMem) == EXPECTED_THANK_YOU_NATIVE .. "FF",
        "generated Thank-You Password changed")
      report(string.format(
        "Revival result frame=%d screen=%08X mode=%02X buffer=%s",
        frame, checksum(), emu.read(0xC195, cpuMem),
        hexBytes(0x016D, 16, workMem)))
      saveScreenshot("result")
      report("PASS Revival response accepted and Thank-You Password generated")
      emu.stop(0)
    end
  elseif frame > 5000 then
    error("timed out before entering the localized Revival editor")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
