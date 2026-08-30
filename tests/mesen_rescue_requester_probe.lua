-- Read-only Mesen probe for captured Wanderer Rescue requester states.
-- The Python fixture test supplies GB2_RESCUE_REQUESTER_MSS and optionally
-- GB2_RESCUE_REQUESTER_SCREENSHOT. No emulated memory is modified.

local LABEL = "Rescue requester probe"
local statePath = assert(os.getenv("GB2_RESCUE_REQUESTER_MSS"))
local screenshotPath = os.getenv("GB2_RESCUE_REQUESTER_SCREENSHOT")
local cpuMem = emu.memType.gameboyMemory
local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam
local loaded = false
local frame = 0

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
  emu.loadSavestate(loadFile(statePath))
end

local function afterFrame()
  if not loaded then return end
  if frame == 2 then
    local checksum = screenChecksum()
    report(string.format(
        "%s: mode=%02X pos=%02X max=%02X buffer=%s sos=%s screen=%08X",
        LABEL,
        emu.read(0xC195, cpuMem),
        emu.read(0xC152, cpuMem),
        emu.read(0xC153, cpuMem),
        hexBytes(0x016D, 14, workMem),
        hexBytes(0x027D, 10, workMem),
        checksum))
    if screenshotPath ~= nil and screenshotPath ~= "" then
      local file = assert(io.open(screenshotPath, "wb"))
      file:write(emu.takeScreenshot())
      file:close()
    end
    emu.stop(0)
  elseif frame > 120 then
    error("timed out while probing requester state")
  end
  frame = frame + 1
end

emu.addMemoryCallback(
    loadOnce, emu.callbackType.exec, 0x0000, 0xFFFF, emu.cpuType.gameboy)
emu.addEventCallback(afterFrame, emu.eventType.endFrame)
