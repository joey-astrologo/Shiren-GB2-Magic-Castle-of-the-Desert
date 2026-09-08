import {drawPreview as dialogue, glyphPixels, FONT_STYLES, PALETTE, WINDOW} from "../prose/preview.js";
export {FONT_STYLES, WINDOW};

// Dialogue uses the verified GB2 window. Other families show their text canvas,
// with the actual row step and available width, without inventing surrounding UI.
export function drawPreview(canvas, lines, page, data, style, profile) {
  if (["prose", "item_message", "notebook"].includes(profile.kind) || profile.mode === 2) {
    canvas.width = 160; canvas.height = 38;
    dialogue(canvas, lines, page, data, style); return;
  }
  const current = lines.filter(line => line.box === page);
  const step = profile.mode === 16 ? 16 : 11;
  const count = profile.mode === 8 ? 11 : Math.max(1, ...current.map(line => line.row + 1));
  canvas.width = 160; canvas.height = Math.min(144, 8 + (count - 1) * step + 8);
  canvas.dataset.fontStyle = style;
  canvas.setAttribute("aria-label", `GB2 text canvas in the ${style} font. The surrounding game screen is not shown.`);
  const c = canvas.getContext("2d");
  c.fillStyle = PALETTE.background; c.fillRect(0, 0, canvas.width, canvas.height);
  c.fillStyle = PALETTE.ink;
  c.fillRect(2, 0, 156, 1); c.fillRect(2, canvas.height - 1, 156, 1);
  c.fillRect(1, 1, 1, canvas.height - 2); c.fillRect(158, 1, 1, canvas.height - 2);
  const budget = profile.direct.length ? Math.min(...profile.direct.map(([x, , edge]) => edge - x)) : profile.right ? profile.right[1] - profile.right[0] : profile.pixels;
  c.save(); c.beginPath(); c.rect(8, 4, Math.min(144, budget), canvas.height - 8); c.clip();
  for (const line of current) for (const op of line.operations) {
    const x = 8 + op.x, y = 4 + line.row * step;
    if (op.substitution) { c.fillStyle = "#dedede"; c.fillRect(x, y, op.width, 8); continue; }
    if (op.page) continue;
    const glyph = data.font.glyphs[op.char];
    const pixels = glyph ? glyphPixels(glyph, style) : data.glyphTokens[op.symbol]?.pixels;
    if (!pixels) continue;
    for (let dy = 0; dy < pixels.length; dy++) for (let dx = 0; dx < 8; dx++) {
      const color = Number(pixels[dy][dx + (op.sliceIndex || 0) * 8]);
      if (color !== 2 && color !== 3) continue;
      c.fillStyle = color === 3 ? PALETTE.ink : PALETTE.shadow; c.fillRect(x + dx, y + dy, 1, 1);
    }
  }
  c.restore();
  if (budget < 144) { c.fillStyle = "#a8a8a8"; c.fillRect(8 + budget, 3, 1, canvas.height - 6); }
}
