-- Exact live regression for the user-reported Japanese Rescue password editor.
--
-- Unlike the ordinary controller route, this starts from the captured broken
-- machine state, lets the installed common input-loop hook execute naturally,
-- and requires the complete reviewed English framebuffer. It does not call or
-- inject the repair routine itself.

local frame = 0
local loaded = false
local repairedAt = nil
local cpuMem = emu.memType.gameboyMemory
local EXPECTED_SCREEN = tonumber(
  assert(os.getenv("GB2_RESCUE_EXPECTED_EDITOR_SCREEN")), 16)

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

local function loadOnce()
  if loaded then return end
  loaded = true
  emu.loadSavestate(loadFile(assert(os.getenv("GB2_RESCUE_FAILURE_MSS"))))
  assert(emu.read(0xC195, cpuMem) == 0x08, "fixture is not in SOS input mode")
  assert(emu.read(0xC14E, cpuMem) == 0x00, "fixture navigation is not the broken type")
  assert(emu.read(0xC152, cpuMem) == 0x00, "fixture input position changed")
  assert(emu.read(0xC153, cpuMem) == 0x0D, "fixture input maximum changed")
  report(string.format(
    "captured Japanese rescue editor loaded frame=%d screen=%08X mode=%02X nav=%02X",
    frame, checksum(), emu.read(0xC195, cpuMem), emu.read(0xC14E, cpuMem)))
end

local function afterFrame()
  if not loaded then return end
  local mode = emu.read(0xC195, cpuMem)
  local navigation = emu.read(0xC14E, cpuMem)
  local maximum = emu.read(0xC153, cpuMem)
  local screen = checksum()

  if repairedAt == nil and navigation == 0xF5 then
    repairedAt = frame
    report(string.format(
      "installed rescue loop repaired editor frame=%d screen=%08X mode=%02X nav=%02X",
      frame, screen, mode, navigation))
  end

  if repairedAt ~= nil and screen == EXPECTED_SCREEN then
    assert(mode == 0x08, "repair changed SOS input mode")
    assert(maximum == 0x0D, "repair changed SOS input maximum")
    report(string.format(
      "PASS captured rescue editor repaired naturally frame=%d screen=%08X mode=%02X nav=%02X",
      frame, screen, mode, navigation))
    emu.stop(0)
    return
  end

  if frame > 900 then
    error(string.format(
      "captured editor was not repaired: screen=%08X mode=%02X nav=%02X maximum=%02X",
      screen, mode, navigation, maximum))
  end
  frame = frame + 1
end

emu.addMemoryCallback(
  loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
