-- Headless companion for title_screen_mesen.py. No Lua file or network access.
local frame = 0
local played = false
local returnedAt = nil
local pressAt = nil
local memory = emu.memType.gameboyMemory

local function emit(kind)
  local pixels = {}
  for i, color in ipairs(emu.getScreenBuffer()) do
    -- Mesen expands RGB555 to eight bits; preserve the original five-bit value.
    pixels[i] = string.format("%06x", color & 0xf8f8f8)
  end
  print(kind .. " " .. frame .. " " .. emu.read(0xc880, memory)
    .. " " .. emu.read(0xc881, memory) .. " " .. emu.read(0xc883, memory)
    .. " " .. table.concat(pixels))
end

emu.addEventCallback(function()
  frame = frame + 1
  local scene = emu.read(0xc3b4, memory)
  local mode = emu.read(0xc0e5, memory)
  if frame >= 600 and frame < 1080 then
    if scene ~= 0x9d or mode ~= 9 then emu.stop(2); return end
    emit("TITLE_FRAME")
  end
  if frame >= 1080 then
    if scene ~= 0x9d and mode == 6 then played = true end
    if played and returnedAt == nil and scene == 0x9d and mode == 9 then
      returnedAt = frame
    end
    if returnedAt and frame == returnedAt + 120 then
      emit("TITLE_RETURN")
      pressAt = frame + 1
    end
    if pressAt and frame == pressAt + 120 then
      if mode ~= 7 then emu.stop(3); return end
      emit("TITLE_MENU")
      emu.stop(0)
    end
  end
  if frame >= 18000 then emu.stop(4) end
end, emu.eventType.endFrame)

emu.addEventCallback(function()
  emu.setInput({start = not not (pressAt and frame >= pressAt and frame < pressAt + 5)}, 0)
end, emu.eventType.inputPolled)
