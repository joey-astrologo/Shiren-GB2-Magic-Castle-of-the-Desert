-- mesen_unlock_monster_log.lua
-- Unlock every entry present in Shiren GB2's native 209-entry Monster Notebook
-- catalog. The helper preserves all existing history and all reserved/omitted bits.
-- It edits the Notebook's transient live WRAM workspace only, never battery SRAM.
--
-- HOW TO USE
--   1. Open Monster Notebook and remain on its graphical catalog grid.
--   2. Pause Mesen, open Debug > Script Window, load this file, and press Run (F5).
--   3. Resume and change pages. Return to the initial page to refresh it as well.
--   4. Inspect all eight pages before exiting Monster Notebook. Exiting rebuilds and
--      clears this temporary unlock from the current save's actual encounter history.
--
-- The native availability predicate at bank 11:$7941 maps a catalog pair to bit
--     (tier - 1) * 73 + one_based_monster_index
-- in WRAM bank 2 starting at $DE48. The masks below are derived from the 209
-- two-byte (tier, monster) pairs at bank 11:$7CBD. Ten internal Undefined (Bug)
-- records are absent from that table and are intentionally not enabled.

local LABEL = "Monster Notebook unlock"
local HISTORY_WRAM = 0x2E48

local REQUIRED_MASKS = {
  0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0xFD, 0xFF, 0xFF, 0xD7, 0xAF, 0xFF, 0xFB,
  0xFF, 0xFF, 0xFB, 0xFF, 0xFF, 0x8F, 0x0F,
}

local workMem = emu.memType.gbWorkRam or emu.memType.gameboyWorkRam

local function report(message)
  print(message)
  emu.log(message)
end

local function fail(message)
  report(LABEL .. ": FAILED: " .. message)
  return false, 0, 0
end

local function rd(address)
  if workMem == nil then return nil end
  local ok, value = pcall(emu.read, address, workMem)
  if not ok then return nil end
  return value
end

local function wr(address, value)
  if workMem == nil then return false end
  local ok = pcall(emu.write, address, value, workMem)
  return ok and rd(address) == value
end

local function bitCount(value)
  local count = 0
  while value ~= 0 do
    count = count + (value & 1)
    value = value >> 1
  end
  return count
end

local function unlockMonsterNotebook()
  if workMem == nil then
    return fail("this Mesen build does not expose flat Game Boy Work RAM")
  end

  local original = {}
  local updated = {}
  local changedBytes = 0
  local newlyUnlocked = 0
  for index, mask in ipairs(REQUIRED_MASKS) do
    local address = HISTORY_WRAM + index - 1
    local oldValue = rd(address)
    if oldValue == nil then
      return fail(string.format("could not read history byte $%04X", address))
    end
    local newValue = oldValue | mask
    original[index] = oldValue
    updated[index] = newValue
    if newValue ~= oldValue then
      changedBytes = changedBytes + 1
      newlyUnlocked = newlyUnlocked + bitCount(newValue ~ oldValue)
    end
  end

  for index, newValue in ipairs(updated) do
    if newValue ~= original[index] then
      local address = HISTORY_WRAM + index - 1
      if not wr(address, newValue) then
        for rollback = index, 1, -1 do
          if updated[rollback] ~= original[rollback] then
            wr(HISTORY_WRAM + rollback - 1, original[rollback])
          end
        end
        return fail(string.format(
          "could not verify history byte $%04X; earlier writes were rolled back",
          address))
      end
    end
  end

  if changedBytes == 0 then
    report(LABEL .. ": all 209 native entries were already available")
  else
    report(string.format(
      "%s: unlocked %d new entr%s across %d history byte%s",
      LABEL,
      newlyUnlocked,
      newlyUnlocked == 1 and "y" or "ies",
      changedBytes,
      changedBytes == 1 and "" or "s"))
  end
  report(LABEL .. ": change pages to refresh the catalog; do not exit the Notebook")
  return true, changedBytes, newlyUnlocked
end

_G.gb2UnlockMonsterNotebook = unlockMonsterNotebook
unlockMonsterNotebook()
