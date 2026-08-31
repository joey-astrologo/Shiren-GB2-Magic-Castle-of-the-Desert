-- Live Rankings -> Await Rescue -> SOS guide regression.
--
-- This route starts from the captured requester Rankings state.  It drives
-- only controller input, proves that the generated native password and diary
-- record remain byte-exact, and freezes the rendered localized SOS screen.

local frame = 0
local loaded = false
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local STATE_SCREEN = 0x70EB86CD
local CONFIRMATION_SCREEN = 0x17D77035
local LOCALIZED_SCREEN = 0x7F6D7FB9
local EXPECTED_NATIVE = "6F7359324D4E6932506F73716DFF"
local EXPECTED_DIARY = "3EC1C2C48F7F09080201"

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

local function screenChecksum()
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
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_RANKINGS_MSS"))))
  report("rescue requester Rankings fixture loaded")
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
  pressAt(input, 100, "select")
  pressAt(input, 240, "a")
  pressAt(input, 400, "left")
  pressAt(input, 460, "a")
  emu.setInput(input, 0)
end

local function afterFrame()
  if not loaded then return end
  if frame == 60 or frame == 180 or frame == 360 or
      frame == 540 or frame == 720 then
    local checksum = screenChecksum()
    report(string.format(
      "rescue requester frame=%d screen=%08X mode=%02X node=%02X buffer=%s diary=%s",
      frame, checksum, emu.read(0xC195, cpuMem), emu.read(0xC14F, cpuMem),
      hexBytes(0x016D, 14, workMem), hexBytes(0x027D, 10, workMem)
    ))
    if frame == 60 then
      assert(checksum == STATE_SCREEN, "unexpected Rankings fixture screen")
    elseif frame == 360 then
      assert(
        checksum == CONFIRMATION_SCREEN,
        string.format("localized rescue confirmation mismatch: %08X", checksum)
      )
      local confirmationScreenshot = os.getenv("GB2_RESCUE_CONFIRMATION_SCREENSHOT")
      if confirmationScreenshot ~= nil and confirmationScreenshot ~= "" then
        local file = assert(io.open(confirmationScreenshot, "wb"))
        file:write(emu.takeScreenshot())
        file:close()
      end
    end
  end
  if frame == 720 then
    local checksum = screenChecksum()
    local buffer = hexBytes(0x016D, 14, workMem)
    local diary = hexBytes(0x027D, 10, workMem)
    assert(
      checksum == LOCALIZED_SCREEN,
      string.format("localized SOS screen mismatch: %08X", checksum)
    )
    assert(buffer == EXPECTED_NATIVE, "native SOS buffer was not restored")
    assert(diary == EXPECTED_DIARY, "SOS diary record changed")
    local screenshot = os.getenv("GB2_SCREENSHOT")
    if screenshot ~= nil and screenshot ~= "" then
      local file = assert(io.open(screenshot, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    report(string.format(
      "PASS localized SOS screen=%08X buffer=%s diary=%s",
      checksum, buffer, diary
    ))
    emu.stop(0)
  elseif frame > 900 then
    error("timed out while replaying requester route")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(inputForFrame, emu.eventType.inputPolled)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
