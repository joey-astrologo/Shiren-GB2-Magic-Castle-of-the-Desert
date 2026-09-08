/* GB2 counterpart of wrap_en.py, layout.py and lint_en.py. The catalogue supplies
 * measured font data, runtime bounds and source contracts from those owners. */
export const EDIT_FORMAT = "shiren-gb2-prose-edits-v1";
export const MAX_TEXT = 40000;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const count = values => {
  const result = {};
  for (const value of values) result[value] = (result[value] || 0) + 1;
  return result;
};
const sameCounts = (a, b) => same(Object.entries(a).sort(), Object.entries(b).sort());
const flatten = text => text.replace(/<[^>]+>|\{[^{}]+\}/g, " ").trim().replace(/\s+/g, " ").toLowerCase();

export function tokenize(text, row, data) {
  const result = [];
  let native = false;
  for (let i = 0; i < text.length;) {
    const char = text[i];
    if (char === "<" || char === "{") {
      const match = text.slice(i).match(/^(<[^<>]+>|\{[^{}]+\})/);
      if (!match) throw new Error("Incomplete control token. Use the controls shown below the draft.");
      const raw = match[0];
      let token = {raw, composer: 0, renderer: 0, slices: []};
      if (/^<(?:page|box|br|cF3|cF8|cFE)>$/.test(raw)) token.control = raw.slice(1, -1);
      else if (/^<(?:delay|hspace):[0-9A-Fa-f]{2}>$/.test(raw) || /^<cF9:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}>$/.test(raw)) {
        token.raw = raw.replace(/:[0-9a-f]{2}/gi, part => part.toUpperCase());
        token.control = raw.slice(1, raw.indexOf(":"));
        if (token.control === "hspace") token.renderer = parseInt(raw.slice(-3, -1), 16);
      } else if (/^<(?:name(?::[0-9a-f]{2})?|copy:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}|(?:lookup|number):[0-9a-f]{2}:[0-9a-f]{2}|sourceF6:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})>$/i.test(raw)) {
        token.raw = raw.replace(/:[0-9a-f]{2}/gi, part => part.toUpperCase());
        if (token.raw === "<name:FF>") token.raw = "<name>";
        const bound = row.runtime[token.raw];
        if (!bound) throw new Error(`Unexpected runtime substitution ${raw}. Keep this entry's required substitutions.`);
        if (bound.composer == null || bound.renderer == null) throw new Error(`${raw} has no proven runtime width. It needs a project measurement before export.`);
        token = {...token, composer: bound.composer, renderer: bound.renderer, substitution: true};
      } else if (Object.hasOwn(data.glyphTokens, raw)) {
        token = {...token, ...data.glyphTokens[raw]};
        token.renderer = token.slices.reduce((a, b) => a + b, 0);
      } else throw new Error(`Unsupported token ${raw}. Use GB2 controls and the installed English glyphs.`);
      result.push(token); native = raw === "<cF8>"; i += raw.length;
    } else {
      if (native && /^[0-9a-z]$/.test(char)) {
        const glyph = data.nativeSelectors[char];
        result.push({raw: char, ...glyph, renderer: glyph.slices.reduce((a, b) => a + b, 0), selector: true});
      } else {
        native = false;
        const glyph = data.font.glyphs[char];
        if (!glyph) throw new Error(`The game font cannot encode ${JSON.stringify(char)} at character ${i + 1}. Use straight quotes, ASCII punctuation and the English glyph set.`);
        result.push({raw: char, char, composer: glyph.advance, renderer: glyph.advance, slices: [glyph.advance]});
      }
      i++;
    }
  }
  return result;
}

function controlErrors(tokens, row) {
  const errors = [], contract = row.controls;
  const boundaries = tokens.flatMap((t, i) => ["page", "box"].includes(t.control) ?
    [[t.control, tokens[i + 1]?.control === "br", tokens[i + 1]?.control === "box"]] : []);
  let cursor = 0;
  for (const [name, postBreak] of contract.boundaries) {
    while (cursor < boundaries.length && !(boundaries[cursor][0] === name &&
        (!postBreak || boundaries[cursor][1] || boundaries[cursor][2]))) cursor++;
    if (cursor === boundaries.length) {
      errors.push("Preserve the source <page>/<box> order. A required <page><br> must keep its <br> or replace it with <box>."); break;
    }
    cursor++;
  }
  const effects = count(tokens.filter(t => ["delay", "cF9"].includes(t.control)).map(t => t.raw));
  if (!sameCounts(effects, contract.effects)) errors.push("Keep every required <delay:NN> and <cF9:LL:HH> effect, with the same arguments and counts.");
  const runtime = count(tokens.filter(t => t.substitution).map(t => t.raw));
  if (!sameCounts(runtime, contract.runtime)) errors.push("Keep every runtime substitution exactly, including repeated occurrences.");
  const selectors = [];
  tokens.forEach((token, i) => {
    if (token.control !== "cF8") return;
    let run = "";
    while (tokens[++i]?.selector) run += tokens[i].raw;
    selectors.push(run);
  });
  if (contract.selectors.length && !same(selectors, contract.selectors)) errors.push("Keep each <cF8> selector run unchanged and in order. Its lowercase letters and digits are variable IDs.");
  if (contract.softWrap && !tokens.some(t => t.control === "cF3")) errors.push("Keep at least one <cF3> conditional wrap checkpoint from the source.");
  const unwaited = boundaries.filter(([name], i) => name === "box" && (!i || boundaries[i - 1][0] !== "page")).length;
  if (unwaited > row.policy.unwaitedBoxes) errors.push("New dialogue boxes need <page><box> to preserve reading time.");
  return errors;
}

function measure(text, row, data) {
  const tokens = tokenize(text, row, data);
  return tokens.reduce((sum, t) => ({composer: sum.composer + t.composer, renderer: sum.renderer + t.renderer}), {composer: 0, renderer: 0});
}
const fits = value => value.composer < 144 && value.renderer <= 144;

function compare(a, b) {
  if (Array.isArray(a)) {
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      const order = compare(a[i], b[i]); if (order) return order;
    }
    return a.length - b.length;
  }
  return a === b ? 0 : a < b ? -1 : 1;
}

function wrapParagraph(paragraph, row, data) {
  if (/^ | $|  |[\t\r\n]/.test(paragraph)) throw new Error("Remove leading, trailing or repeated spaces. Use <br> for line breaks.");
  const words = paragraph.split(" "), candidates = new Map();
  for (let start = 0; start < words.length; start++) {
    for (let end = start + 1; end <= words.length; end++) {
      const text = words.slice(start, end).join(" "), size = measure(text, row, data);
      if (!fits(size)) break;
      candidates.set(`${start}:${end}`, {text, width: Math.max(size.composer, size.renderer)});
    }
    if (!candidates.has(`${start}:${start + 1}`)) throw new Error("A word or control run is wider than the dialogue box. Add a safe word boundary or shorten that word.");
  }
  const best = new Map([[words.length, {lines: [], widths: []}]]);
  for (let start = words.length - 1; start >= 0; start--) {
    for (let end = start + 1; end <= words.length; end++) {
      const value = candidates.get(`${start}:${end}`), suffix = best.get(end);
      if (!value || !suffix) continue;
      const lines = [value.text, ...suffix.lines], widths = [value.width, ...suffix.widths];
      const score = [lines.length, widths.reduce((sum, w) => sum + (143 - w) ** 2, 0), widths.map(w => -w), lines];
      if (!best.has(start) || compare(score, best.get(start).score) < 0) best.set(start, {score, lines, widths});
    }
  }
  return best.get(0).lines;
}

export function wrapDraft(text, row, data) {
  const output = [];
  let boundary = null;
  for (let piece of text.split(/(<(?:page|box)>)/)) {
    if (!piece) continue;
    if (piece === "<page>" || piece === "<box>") { output.push(piece); boundary = piece; continue; }
    const leadingBreak = boundary === "<page>" && piece.startsWith("<br>");
    if (leadingBreak) piece = piece.slice(4);
    const space = boundary === "<page>" && piece.startsWith(" ");
    if (space) piece = piece.slice(1);
    const paragraphs = piece.split("<br>");
    if (paragraphs.some(p => !p)) throw new Error("Remove leading, trailing or repeated <br> controls. A source <page><br> is allowed.");
    const lines = paragraphs.flatMap(paragraph => wrapParagraph(paragraph, row, data));
    if (lines.length > 3) throw new Error(`This passage needs ${lines.length} lines. Add <page><box> at a reading break and repeat the speaker label if needed.`);
    output.push((leadingBreak ? "<br>" : "") + (space ? " " : "") + lines.join("<br>"));
    boundary = null;
  }
  return output.join("");
}

export function layoutText(text, row, data) {
  const lines = [], errors = [], endpoints = [];
  let box = 0, line = 0, composer = 0, pen = 0, operations = [], afterBoundary = false, start = 0, offset = 0;
  function finish() {
    lines.push({box, row: line, composer, extent: pen, operations});
    if (composer >= 144) errors.push(`Box ${box + 1}, line ${line + 1}: composer width ${composer}px must be below 144px.`);
    if (pen > 144) errors.push(`Box ${box + 1}, line ${line + 1}: renderer pen ${pen}px exceeds 144px.`);
    if (line >= 3) errors.push(`Box ${box + 1} reaches line ${line + 1}. <page> does not reset the box; add <page><box>.`);
    operations = [];
  }
  for (const token of tokenize(text, row, data)) {
    if (token.control === "br") {
      finish(); line++; composer = pen = 0; afterBoundary = false; start = offset + token.raw.length;
    } else if (token.control === "box") {
      if (!afterBoundary) finish();
      box++; line = composer = pen = 0; afterBoundary = true; start = offset + token.raw.length;
    } else if (token.control === "page") {
      endpoints.push({box, row: line, x: pen});
      operations.push({page: true, x: pen});
      if (pen + data.rules.pageMarker > 144) errors.push(`Box ${box + 1}, line ${line + 1}: the page marker needs ${data.rules.pageMarker}px. End the text at 135px or earlier.`);
      afterBoundary = false;
    } else {
      if (token.substitution) operations.push({substitution: true, x: pen, width: token.renderer, label: token.raw});
      else if (token.slices?.length) {
        let origin = pen;
        token.slices.forEach(advance => {
          if (line >= 2 && origin + 8 > 144) errors.push(`Box ${box + 1}, line ${line + 1}: an 8px glyph cell starts at ${origin}px and crosses the right edge. Break earlier.`);
          operations.push({x: origin, char: token.char, width: advance, selector: token.selector, symbol: token.raw});
          origin += advance;
        });
      }
      composer += token.composer; pen += token.renderer;
      if (token.slices?.length || token.substitution || ["hspace", "cF3"].includes(token.control)) afterBoundary = false;
    }
    offset += token.raw.length;
  }
  if (start < offset || !lines.length) finish();
  return {lines, errors: [...new Set(errors)], endpoints};
}

export function validateDraft(row, text, data) {
  const errors = [], warnings = [];
  let lines = [], wrapped = "", encodedBytes = 0;
  if (!row.editable && text === "<empty>") return {valid: true, lines, errors, warnings, wrapped, encodedBytes};
  try {
    if (!text || text.length > MAX_TEXT) throw new Error("Enter a nonempty draft of at most 40,000 characters.");
    const tokens = tokenize(text, row, data);
    errors.push(...controlErrors(tokens, row));
    for (const [code, count] of Object.entries(row.policy.storyCodes)) {
      if ([...text.matchAll(new RegExp(`\\b${code}\\b`, "g"))].length !== count) errors.push(`Keep the exact Big Moai story code ${code}.`);
    }
    wrapped = wrapDraft(text, row, data);
    encodedBytes = tokenize(wrapped, row, data).reduce((size, token) => size + (
      token.bytes || (token.substitution ? (token.raw.startsWith("<name") ? 2 : 4) :
        token.control === "cF9" ? 3 : ["delay", "hspace"].includes(token.control) ? 2 : 1)), 0);
    if (encodedBytes + 1 > data.allocation.bankSize) errors.push("This record exceeds a ROM bank. The project allocator needs an engineering change before export; keep your draft.");
    const measured = layoutText(wrapped, row, data); lines = measured.lines; errors.push(...measured.errors);
    const visible = wrapped.replace(/<(?!br>|box>)[^>]+>/g, "");
    if (/[?!][A-Za-z0-9]/.test(visible)) errors.push("Insert a space between ? or ! and the following word, including across <page>.");
    for (const term of row.terms) {
      if (!flatten(wrapped).includes(flatten(term))) errors.push(`Keep the project term ${JSON.stringify(term)} in this entry.`);
    }
    for (const term of row.reviewedOmissions) {
      if (flatten(wrapped).includes(flatten(term))) errors.push(`This entry has a reviewed exception for ${JSON.stringify(term)}. Including it requires a project exception review before import.`);
    }
    if (tokens.some(t => t.substitution)) warnings.push("Shaded spans reserve the full project width for runtime values. Player names allow six characters; the current checker reserves 49px of headroom.");
    if (tokens.some(t => t.control === "cF8")) warnings.push("<cF8> selectors use the project's native byte widths. The event replaces these selectors at runtime; review their final appearance in game.");
  } catch (error) { errors.push(error.message); }
  return {valid: !errors.length, errors: [...new Set(errors)], warnings, lines, wrapped, encodedBytes};
}

export function checkAllocation(data, edits, checked = null) {
  const changedSizes = new Map();
  for (const row of data.records) {
    if (edits[row.loc] === undefined || edits[row.loc] === row.draft) continue;
    const value = checked?.get(row.loc) || validateDraft(row, edits[row.loc], data);
    if (!value.valid) continue; // Per-entry errors already block export.
    changedSizes.set(row.loc, value.encodedBytes + 1);
  }
  let bank = 0, offset = 0;
  const {bankSize, banks, tables, records} = data.allocation;
  for (const size of [...tables, ...records.map(([id, size]) => changedSizes.get(id) ?? size)]) {
    if (size > bankSize) return {valid: false, error: "A record exceeds one ROM bank. Keep your draft; the project allocator needs an engineering change before export."};
    if (offset + size > bankSize) { bank++; offset = 0; }
    if (bank >= banks) return {valid: false, error: "These edits exceed the current ROM text allocation. Keep your draft; the project allocator needs more space before export. Do not remove meaning to fit storage."};
    offset += size;
  }
  return {valid: true, banksUsed: bank + 1, endOffset: offset};
}

export function exportEdits(data, edits) {
  const records = new Map(data.records.map(row => [row.loc, row]));
  const changed = Object.entries(edits).filter(([loc, text]) => text !== records.get(loc)?.draft);
  if (!changed.length) throw new Error("There are no changes to download.");
  const output = [`# format\t${EDIT_FORMAT}`, `# revision\t${data.revision}`, `# rules\t${data.rulesRevision}`];
  for (const [loc, text] of changed) {
    const row = records.get(loc);
    if (!row?.editable || !validateDraft(row, text, data).valid) throw new Error(`${loc}: fix the entry before downloading.`);
    output.push(`# base\t${loc}\t${row.base}`);
  }
  output.push("# id\tenglish");
  for (const row of data.records) if (changed.some(([loc]) => loc === row.loc)) output.push(`${row.loc}\t${edits[row.loc]}`);
  const allocation = checkAllocation(data, edits);
  if (!allocation.valid) throw new Error(allocation.error);
  return output.join("\n") + "\n";
}

export function importEdits(text, data, existing = {}) {
  if (new TextEncoder().encode(text).length > 2_000_000) throw new Error("Changes TSV is larger than 2 MB.");
  const metadata = new Map(), bases = new Map(), incoming = new Map();
  for (const line of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    if (!line) continue;
    if (line.startsWith("# ")) {
      const fields = line.slice(2).split("\t");
      if (fields[0] === "base" && fields.length === 3) {
        if (bases.has(fields[1])) throw new Error("Duplicate baseline ID.");
        bases.set(fields[1], fields[2]);
      } else if (["format", "revision", "rules"].includes(fields[0]) && fields.length === 2) {
        if (metadata.has(fields[0])) throw new Error("Duplicate metadata.");
        metadata.set(fields[0], fields[1]);
      } else if (!same(fields, ["id", "english"])) throw new Error("Unknown changes metadata.");
      continue;
    }
    const fields = line.split("\t");
    if (fields.length !== 2 || incoming.has(fields[0])) throw new Error("Malformed or duplicate changes row.");
    incoming.set(fields[0], fields[1]);
  }
  if (metadata.get("format") !== EDIT_FORMAT || metadata.get("rules") !== data.rulesRevision ||
      !/^[a-f0-9]{64}$/.test(metadata.get("revision") || "") || !incoming.size || incoming.size !== bases.size ||
      [...bases.keys()].some(loc => !incoming.has(loc))) throw new Error("Use a GB2 changes TSV with matching rules and baselines.");
  const records = new Map(data.records.map(row => [row.loc, row])), merged = {...existing};
  for (const [loc, value] of incoming) {
    const row = records.get(loc);
    if (!row?.editable || bases.get(loc) !== row.base) throw new Error(`${loc}: unknown, read-only, or changed project baseline.`);
    if (!validateDraft(row, value, data).valid) throw new Error(`${loc}: imported text fails the GB2 rules.`);
    if (existing[loc] !== undefined && existing[loc] !== row.draft && existing[loc] !== value) throw new Error(`${loc}: this import conflicts with a saved edit. Download or reset that entry first.`);
    if (value === row.draft) delete merged[loc]; else merged[loc] = value;
  }
  const allocation = checkAllocation(data, merged);
  if (!allocation.valid) throw new Error(allocation.error);
  return merged;
}

export function draftBackup(data, edits) {
  const bases = {};
  for (const row of data.records) if (Object.hasOwn(edits, row.loc)) bases[row.loc] = row.base;
  return JSON.stringify({format: "shiren-gb2-prose-draft-v1", revision: data.revision,
    rules: data.rulesRevision, bases, edits}, null, 2);
}

export function importBackup(text, data, existing = {}) {
  const saved = JSON.parse(text), rows = new Map(data.records.map(row => [row.loc, row]));
  if (!saved || saved.format !== "shiren-gb2-prose-draft-v1" || saved.rules !== data.rulesRevision ||
      !saved.edits || typeof saved.edits !== "object" || Array.isArray(saved.edits)) throw new Error("This draft backup uses a different format or rule revision. Keep it for recovery.");
  const merged = {...existing};
  for (const [loc, value] of Object.entries(saved.edits)) {
    const row = rows.get(loc);
    if (!row?.editable || saved.bases?.[loc] !== row.base || typeof value !== "string" || value.length > MAX_TEXT) throw new Error(`${loc}: unknown or changed draft baseline.`);
    if (existing[loc] !== undefined && existing[loc] !== row.draft && existing[loc] !== value) throw new Error(`${loc}: this backup conflicts with a local edit.`);
    if (value === row.draft) delete merged[loc]; else merged[loc] = value;
  }
  return merged;
}
