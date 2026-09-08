// GB2's standard English dialogue window. Geometry and RGB5 colors were checked
// against the classic/shadowed Training arrival captures: x=0..159, y=104..141,
// text at (8,108), and an 11px line step. The last two screen rows are outside it.
export const WINDOW = {width: 160, height: 38, textX: 8, textY: 4, textWidth: 144, textHeight: 30};
export const PALETTE = {background: "#f8f8f8", shadow: "#a8a8a8", ink: "#000000"};
export const FONT_STYLES = ["classic", "shadowed"];

// Native glyph $2F is shared by both font builds; its advance remains 9px.
const PAGE_MARKER = ["11111111", "11111111", "33333331", "33333332",
                     "13333322", "11333221", "11132211", "11112111"];

export function glyphPixels(glyph, style) {
  return style === "classic" ? glyph.rows.map(bits =>
    Array.from({length: 8}, (_, x) => bits & (0x80 >> x) ? 3 : 1)) : glyph.pixels;
}

function drawFrame(context) {
  const {width, height} = WINDOW;
  context.fillStyle = PALETTE.background;
  context.fillRect(0, 0, width, height);
  context.fillStyle = PALETTE.shadow;
  context.fillRect(1, 0, width - 2, height);
  context.fillStyle = PALETTE.ink;
  context.fillRect(2, 0, width - 4, 1);
  context.fillRect(2, height - 1, width - 4, 1);
  context.fillRect(1, 1, 1, height - 2);
  context.fillRect(width - 2, 1, 1, height - 2);
  for (const x of [2, width - 3]) {
    context.fillRect(x, 1, 1, 1);
    context.fillRect(x, height - 2, 1, 1);
  }
  context.fillStyle = PALETTE.background;
  context.fillRect(3, 2, width - 6, height - 4);
}

export function drawPreview(canvas, lines, page, data, style = "shadowed") {
  style = FONT_STYLES.includes(style) ? style : "shadowed";
  const context = canvas.getContext("2d");
  canvas.dataset.fontStyle = style;
  canvas.setAttribute("aria-label", `GB2 dialogue window with the ${style} font. Per-line fit measurements follow.`);
  drawFrame(context);
  context.save();
  // An invalid line must not paint the frame or an imaginary fourth row.
  context.beginPath();
  context.rect(WINDOW.textX, WINDOW.textY, WINDOW.textWidth, WINDOW.textHeight);
  context.clip();
  const boxLines = lines.filter(line => line.box === page);
  const lastOperation = boxLines.flatMap(line => line.operations).at(-1);
  function paintGlyph(pixels, x, y) {
    pixels.forEach((row, dy) => Array.from(row).forEach((color, dx) => {
      if (Number(color) === 3 || Number(color) === 2) {
        context.fillStyle = Number(color) === 3 ? PALETTE.ink : PALETTE.shadow;
        context.fillRect(x + dx, y + dy, 1, 1);
      }
    }));
  }
  for (const line of boxLines) {
    const y = WINDOW.textY + line.row * data.rules.lineAdvance;
    for (const operation of line.operations) {
      const x = WINDOW.textX + operation.x;
      if (operation.substitution) {
        context.fillStyle = "#dedede";
        context.fillRect(x, y, operation.width, 8);
        context.fillStyle = "#999999";
        for (let dx = 0; dx < operation.width; dx += 3) context.fillRect(x + dx, y + 7, 1, 1);
      } else if (operation.page) {
        if (operation === lastOperation) paintGlyph(PAGE_MARKER, x, y);
      } else if (data.font.glyphs[operation.char]) {
        paintGlyph(glyphPixels(data.font.glyphs[operation.char], style), x, y);
      } else if (data.glyphTokens[operation.symbol]?.pixels) {
        // Native symbols have the same bitmap in both builds.
        paintGlyph(data.glyphTokens[operation.symbol].pixels, x, y);
      } else {
        context.strokeStyle = "#999999";
        context.strokeRect(x + .5, y + .5, 6, 6);
      }
    }
    if (line.extent > data.rules.pixelLimit || line.composer > data.rules.composerLimit) {
      context.fillStyle = "#a44032";
      context.fillRect(WINDOW.textX + WINDOW.textWidth - 2, y, 2, 8);
    }
  }
  context.restore();
}
