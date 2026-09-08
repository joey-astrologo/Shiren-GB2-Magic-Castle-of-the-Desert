// Explicit GB2 surfaces use the production source compositor, including F3
// rollback. Story prose retains the existing balanced wrapper.
import {tokenize, validateDraft as proseCheck, wrapDraft, MAX_TEXT} from "../prose/rules.js";
export {MAX_TEXT};
export const EDIT_FORMAT = "shiren-gb2-workbench-edits-v1";
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const counts = values => { const out = {}; for (const x of values) out[x] = (out[x] || 0) + 1; return Object.entries(out).sort(); };
const flat = text => text.replace(/<[^>]+>|\{[^{}]+\}/g, " ").trim().replace(/\s+/g, " ").toLowerCase();
const bytes = tokens => tokens.reduce((size, t) => size + (t.bytes || (t.substitution ? (t.raw.startsWith("<name") ? 2 : 4) : t.control === "cF9" ? 3 : ["delay", "hspace"].includes(t.control) ? 2 : 1)), 0);

export function measure(tokens, profile, data, soft = true) {
  let box = 0, row = 0, units = [], checkpoint = null, unrecoverable = false, after = false, pending = true;
  const lines = [], errors = [], endpoints = [];
  const limit = profile.lines ?? (profile.mode === 8 ? 11 : profile.mode === 2 ? 3 : null);
  const totals = () => units.reduce((v, t) => [v[0] + t.composer, v[1] + t.renderer], [0, 0]);
  function finish() {
    const [composer, extent] = totals(); let pen = 0; const operations = [];
    for (const t of units) {
      if (t.substitution) operations.push({substitution: true, x: pen, width: t.renderer, label: t.raw});
      else if (t.page) operations.push({page: true, x: pen});
      else for (const [sliceIndex, advance] of (t.slices || []).entries()) {
        if ((profile.mode === 2 && row >= 2 || profile.mode === 8 && row >= 10 || profile.kind === "notebook" && row >= 1) && pen + 8 > 144)
          errors.push(`Line ${row + 1}: an 8px glyph cell crosses the right edge at ${pen}px.`);
        operations.push({x: pen, char: t.char, symbol: t.raw, width: advance, sliceIndex}); pen += advance;
      }
      if (!t.slices?.length) pen += t.renderer;
    }
    lines.push({box, row, composer, extent, operations});
    if (composer >= 144 || extent > profile.pixels || composer > profile.pixels)
      errors.push(`Line ${row + 1}: ${composer}px composer / ${extent}px pen exceeds this surface (${Math.min(143, profile.pixels)}px composer / ${profile.pixels}px pen).`);
    if (limit != null && row >= limit) errors.push(`This surface allows ${limit} lines; line ${row + 1} does not fit.`);
  }
  function add(t) {
    units.push(t);
    if (totals()[0] < 144) return;
    if (!soft || checkpoint === null || unrecoverable) { unrecoverable = true; return; }
    const rest = units.slice(checkpoint); units = units.slice(0, checkpoint); finish();
    row++; units = rest; checkpoint = null; unrecoverable = totals()[0] >= 144;
  }
  for (const t of tokens) {
    pending = true;
    if (t.control === "br") {
      finish(); row++; units = []; checkpoint = null; unrecoverable = false; after = false; pending = false;
    } else if (t.control === "box") {
      if (!after) finish(); box++; row = 0; units = []; checkpoint = null; unrecoverable = false; after = true; pending = false;
    } else if (t.control === "page") {
      const pen = totals()[1]; endpoints.push({box, row, x: pen});
      // Mode $10 owns a streamed surface; the regular dialogue marker rule does not apply.
      if (profile.mode !== 16 && pen + data.rules.pageMarker > 144)
        errors.push(`Line ${row + 1}: leave 9px for the page marker (text must end at 135px or earlier).`);
      units.push({...t, page: true}); after = false;
    } else if (t.control === "cF3") {
      checkpoint = !unrecoverable && totals()[0] < 144 ? units.length : null; after = false;
    } else if (t.slices?.length || t.substitution || t.control === "hspace") { add(t); after = false; }
  }
  if (pending || !lines.length) finish();
  return {lines, errors: [...new Set(errors)], endpoints};
}

function greedy(paragraph, row, data) {
  if (/^ | $|  |[\t\r\n]/.test(paragraph)) throw new Error("Remove leading, trailing or repeated spaces from wrapped paragraphs.");
  const lines = []; let line = "";
  for (const word of paragraph.split(" ")) {
    const candidate = line ? line + " " + word : word;
    const ts = tokenize(candidate, row, data), c = ts.reduce((n, t) => n + t.composer, 0), p = ts.reduce((n, t) => n + t.renderer, 0);
    if (c < 144 && p <= 144) { line = candidate; continue; }
    if (!line) throw new Error("A word or control run is wider than the canvas.");
    lines.push(line); line = word;
    const widths = tokenize(word, row, data);
    if (widths.reduce((n, t) => n + t.composer, 0) >= 144 || widths.reduce((n, t) => n + t.renderer, 0) > 144)
      throw new Error("A word or control run is wider than the canvas.");
  }
  if (line) lines.push(line); return lines;
}

function wrappedItem(text, row, data) {
  if (text.includes("<cF3>")) return text;
  let boundary = null;
  return text.split(/(<(?:page|box)>)/).map(piece => {
    if (!piece) return "";
    if (piece === "<page>" || piece === "<box>") { boundary = piece; return piece; }
    let prefix = "";
    if (boundary === "<page>" && piece.startsWith("<br>")) { prefix = "<br>"; piece = piece.slice(4); }
    if (boundary === "<page>" && piece.startsWith(" ")) { prefix += " "; piece = piece.slice(1); }
    const paragraphs = piece.split("<br>");
    if (paragraphs.some(x => !x)) throw new Error("Remove empty lines from this wrapped message.");
    const lines = paragraphs.flatMap(x => greedy(x, row, data));
    if (lines.length > 3) throw new Error("This passage needs another <page><box>.");
    boundary = null; return prefix + lines.join("<br>");
  }).join("");
}

function controls(tokens, row) {
  const errors = [], c = row.controls;
  if (!equal(counts(tokens.filter(t => t.substitution).map(t => t.raw)), Object.entries(c.runtime).sort())) errors.push("Keep every runtime substitution with the same arguments and counts.");
  if (!equal(counts(tokens.filter(t => ["delay", "cF9"].includes(t.control)).map(t => t.raw)), Object.entries(c.effects).sort())) errors.push("Keep every timing/effect control with the same arguments and counts.");
  const selectors = [];
  tokens.forEach((t, i) => { if (t.control === "cF8") { let run = ""; while (tokens[++i]?.selector) run += tokens[i].raw; selectors.push(run); } });
  if (c.selectors.length && !equal(selectors, c.selectors)) errors.push("Keep native <cF8> selectors unchanged and in order.");
  if (c.softWrap && !tokens.some(t => t.control === "cF3")) errors.push("Retain a source <cF3> conditional wrap checkpoint.");
  const boundaries = tokens.flatMap((t, i) => ["page", "box"].includes(t.control) ? [[t.control, ["br", "box"].includes(tokens[i + 1]?.control)]] : []);
  let cursor = 0;
  for (const [name, post] of c.boundaries) {
    while (cursor < boundaries.length && !(boundaries[cursor][0] === name && (!post || boundaries[cursor][1]))) cursor++;
    if (cursor++ === boundaries.length) { errors.push("Preserve the source page/box order and required breaks after waits."); break; }
  }
  const exact = row.profile.exactControlTokens;
  if (exact && !equal(tokens.filter(t => t.substitution || ["cF3", "page", "box"].includes(t.control)).map(t => t.raw), exact)) errors.push("Keep this help/Notebook entry's critical control sequence exactly.");
  for (const [code, count] of Object.entries(row.policy.storyCodes))
    if ([...tokens.map(t => t.raw).join("").matchAll(new RegExp(`\\b${code}\\b`, "g"))].length !== count) errors.push(`Keep the exact Big Moai code ${code}.`);
  return errors;
}

export function validateDraft(row, text, data) {
  if (!row.editable) return {valid: text === row.draft, errors: text === row.draft ? [] : [row.reason], warnings: [row.reason], lines: [], wrapped: row.current === "<empty>" ? "" : row.current, encodedBytes: 0};
  if (row.profile.kind === "prose") return proseCheck(row, text, data);
  const errors = [], warnings = []; let lines = [], wrapped = text, encodedBytes = 0;
  try {
    if (!text || text.length > MAX_TEXT || /[\t\r\n]/.test(text)) throw new Error("Enter nonempty text using <br> for line breaks (maximum 40,000 characters).");
    const tokens = tokenize(text, row, data);
    errors.push(...controls(tokens, row));
    if (row.profile.fixedBoundaries && !equal(tokens.filter(t => ["page", "box"].includes(t.control)).map(t => t.raw), row.profile.fixedBoundaries)) errors.push("This fixed surface must retain its page/box structure.");
    if (row.profile.fixedBreaks !== undefined && text.split("<br>").length - 1 !== row.profile.fixedBreaks) errors.push("Names must retain their single-line structure.");
    if (row.profile.exactControls && row.profile.kind !== "notebook" && text.split("<br>").length > row.profile.lines) errors.push("Help exceeds its total source line budget.");
    if (row.profile.static || row.profile.direct.length || row.profile.right) {
      if (tokens.some(t => t.control || t.substitution)) errors.push("This name or positioned label must be one static line without controls.");
    }
    if (row.profile.fixedSpaces) {
      const plain = tokens.map(t => t.char || t.raw).join("");
      if (!equal([plain.match(/^ */)[0], plain.match(/ *$/)[0]], row.profile.fixedSpaces)) errors.push("Keep the shared name fragment's leading and trailing separator spaces.");
    }
    if (row.profile.maxChars && (text.length > row.profile.maxChars || text.startsWith(row.profile.sentinel) || /[<{]/.test(text))) errors.push(`This canonical recall root allows ${row.profile.maxChars} plain characters and cannot begin with the disabled-slot sentinel ${row.profile.sentinel}.`);
    for (const [i, header] of row.profile.statHeaders || []) if (text.split("<br>")[i] !== header) errors.push(`Keep the item stat header ${JSON.stringify(header)} on line ${i + 1}.`);
    if (row.profile.kind === "item_message") wrapped = wrappedItem(text, row, data);
    // Descriptions retain explicit title/stat lines; users author body <br> boundaries.
    const ts = tokenize(wrapped, row, data); encodedBytes = bytes(ts);
    const result = measure(ts, row.profile, data); lines = result.lines; errors.push(...result.errors);
    if (row.profile.kind === "notebook" && text.split("<br>").length !== row.profile.lines) errors.push(`This Notebook entry must contain exactly ${row.profile.lines} lines.`);
    for (const [x, , edge] of row.profile.direct) {
      if (lines.some(l => l.extent > edge - x)) errors.push(`Positioned label starts at x=${x} and must end at x=${edge} (${edge - x}px).`);
    }
    if (row.profile.right) {
      const [left, anchor] = row.profile.right;
      if (lines.some(l => l.extent > anchor - left)) errors.push(`Right-aligned location has ${anchor - left}px, between x=${left} and x=${anchor}.`);
    }
    if (row.profile.inkEdge) for (const line of lines) for (const op of line.operations) {
      const glyph = data.font.glyphs[op.char];
      if (!glyph) { errors.push("Item-action labels must use the installed English glyphs."); continue; }
      const edge = Math.max(0, ...glyph.rows.flatMap(bits => Array.from({length: 8}, (_, x) => bits & (128 >> x) ? x + 1 : 0)));
      if (op.x + edge > row.profile.inkEdge) errors.push("Item-action ink enters the cursor-only tile; keep ink within 40px.");
    }
    ts.forEach((token, i) => {
      if (!["?", "!"].includes(token.char)) return;
      for (const next of ts.slice(i + 1)) {
        if (next.control) { if (["br", "box"].includes(next.control)) break; continue; }
        if (/^[A-Za-z0-9]$/.test(next.char || "")) errors.push("Insert a space after ? or ! before the following word.");
        break;
      }
    });
    if (encodedBytes + 1 > data.allocation.bankSize) errors.push("This record exceeds one ROM bank.");
    if (ts.some(t => t.substitution)) warnings.push("Shaded spans reserve the current runtime-name and number widths. <cF3> may wrap differently for shorter values.");
  } catch (error) { errors.push(error.message); }
  return {valid: !errors.length, errors: [...new Set(errors)], warnings, lines, wrapped, encodedBytes};
}

export function workspace(data, edits = {}) {
  const original = new Map(data.records.map(r => [r.loc, r]));
  const text = id => edits[id] ?? original.get(id).draft;
  const rows = new Map(data.records.map(r => [r.loc, {...r, runtime: {...r.runtime}, terms: [], reviewedOmissions: []}]));
  const failures = new Map();
  const fail = (id, message) => { if (!failures.has(id)) failures.set(id, []); failures.get(id).push(message); };
  const widths = new Map();
  function width(id) {
    if (typeof id === "number") return [id, id];
    if (widths.has(id)) return widths.get(id);
    const r = rows.get(id), value = text(id);
    let out;
    try {
      const ts = value === "<empty>" ? [] : tokenize(value, r, data);
      if (ts.some(t => t.control || t.substitution)) throw new Error("Runtime terms must be static text.");
      out = [ts.reduce((n, t) => n + t.composer, 0), ts.reduce((n, t) => n + t.renderer, 0)];
    } catch { out = [Infinity, Infinity]; fail(id, "This runtime name cannot be measured. Keep it as one static line."); }
    widths.set(id, out); return out;
  }
  const domains = {};
  for (const [name, expressions] of Object.entries(data.domains)) {
    domains[name] = [...new Map(expressions.map(expr => {
      const size = expr.reduce((v, id) => { const w = width(id); return [v[0] + w[0], v[1] + w[1]]; }, [0, 0]);
      return [size.join(":"), size];
    })).values()];
  }
  for (const row of rows.values()) for (const [token, bound] of Object.entries(row.runtime)) {
    if (bound.kind?.startsWith("f6_")) {
      const values = domains[bound.kind.slice(3)] || [];
      row.runtime[token] = {...bound, composer: values.length ? Math.max(...values.map(v => v[0])) : null,
        renderer: values.length ? Math.max(...values.map(v => v[1])) : null};
    }
  }
  const exceptions = new Map(data.exceptions.map(e => [[e.record_id, e.kind, e.related_id].join("|"), e]));
  const issues = new Set();
  function issue(a, kind, b, message) {
    const key = [a, kind, b].join("|"); issues.add(key);
    if (!exceptions.has(key)) { fail(a, message); if (kind !== "term_ignored") fail(b, message); }
  }
  const defs = data.definitions.map(d => ({...d, english: text(d.record_id) === "<empty>" ? "" : text(d.record_id)}));
  const sources = new Map(), renderings = new Map();
  for (const d of defs.filter(d => d.english)) {
    if (!sources.has(d.source)) sources.set(d.source, []); sources.get(d.source).push(d);
    for (const family of d.families) { const k = family + "|" + d.english.trim().replace(/\s+/g, " ").toLowerCase(); if (!renderings.has(k)) renderings.set(k, []); renderings.get(k).push(d); }
  }
  for (const [groups, kind] of [[sources, "glossary_split"], [renderings, "glossary_collision"]]) for (const group of groups.values())
    for (let i = 0; i < group.length; i++) for (let j = i + 1; j < group.length; j++) {
      const a = group[i], b = group[j];
      if (kind === "glossary_split" ? a.english !== b.english : a.source !== b.source) {
        const ids = [a.record_id, b.record_id].sort();
        issue(ids[0], kind, ids[1], `${kind === "glossary_split" ? "The same Japanese name has different translations" : "Different names in one family have the same translation"}: ${ids.join(" / ")}. Update the related entry too.`);
      }
    }
  const termValues = new Map();
  for (const d of data.definitions.filter(d => d.searchable && !/[<{]/.test(d.source) && d.source.replace(/\s/g, "").length >= 3)) {
    const candidates = defs.filter(x => x.searchable && x.source === d.source), values = [...new Set(candidates.map(x => x.english).filter(Boolean))];
    termValues.set(candidates.map(x => x.record_id).sort()[0], values.length === 1 ? values[0] : "");
  }
  for (const row of rows.values()) for (const id of row.termIds) {
    const term = termValues.get(id); if (!term) continue;
    const key = [row.loc, "term_ignored", id].join("|");
    if (row.editable && row.profile.kind === "prose") (exceptions.has(key) ? row.reviewedOmissions : row.terms).push(term);
    if (text(row.loc) !== "<empty>" && text(row.loc) && !flat(text(row.loc)).includes(flat(term)))
      issue(row.loc, "term_ignored", id, `Keep the current project term ${JSON.stringify(term)} from ${id}.`);
  }
  for (const [key, e] of exceptions) if (!issues.has(key)) fail(e.record_id, `The reviewed ${e.kind} exception involving ${e.related_id} no longer applies. Update the project's exception file before importing.`);
  const checked = new Map([...rows].map(([id, row]) => [id, validateDraft(row, text(id), data)]));
  // Exhaust layout-distinct F6 combinations for the combat owner's templates.
  for (const row of rows.values()) {
    if (row.profile.kind !== "combat" || !checked.get(row.loc).valid) continue;
    const substitutions = Object.entries(row.runtime).filter(([, b]) => b.kind?.startsWith("f6_"));
    if (!substitutions.length) continue;
    let unsafe = false;
    const visit = (index, runtime) => {
      if (unsafe) return;
      if (index === substitutions.length) {
        const ts = tokenize(text(row.loc), {...row, runtime}, data);
        if (measure(ts, row.profile, data).errors.length) unsafe = true;
        return;
      }
      const [token, bound] = substitutions[index];
      for (const [composer, renderer] of domains[bound.kind.slice(3)] || []) visit(index + 1, {...runtime, [token]: {...bound, composer, renderer}});
    };
    visit(0, row.runtime);
    if (unsafe) fail(row.loc, "A shorter runtime-name combination fails this combat layout. Move the <cF3> checkpoints or explicit breaks.");
  }
  for (const [name, description] of data.notebook) {
    try {
      const row = rows.get(description), ts = tokenize(text(name) + "<br>" + text(description), row, data);
      const result = measure(ts, {...row.profile, kind: "explicit", mode: 2, lines: 3}, data, false);
      if (result.errors.length) fail(description, `Monster Notebook name + description does not fit (${name}): ${result.errors[0]}`);
    } catch { fail(description, `Monster Notebook name ${name} cannot be composed.`); }
  }
  for (const [id, errors] of failures) {
    const result = checked.get(id); if (result) { result.errors.push(...errors); result.errors = [...new Set(result.errors)]; result.valid = false; }
  }
  return {checked, rows, domains, valid: [...checked.values()].every(r => r.valid)};
}

export function checkAllocation(data, edits, checked = null) {
  checked ||= workspace(data, edits).checked;
  const sizes = new Map();
  for (const row of data.records) {
    const value = checked.get(row.loc);
    // A renamed runtime term can change the wrapper's output in an unchanged prose draft.
    if (row.editable && value.valid) sizes.set(row.loc, value.encodedBytes + 1);
  }
  let bank = 0, offset = 0;
  for (const size of [...data.allocation.tables, ...data.allocation.records.map(([id, n]) => sizes.get(id) ?? n)]) {
    if (size > data.allocation.bankSize) return {valid: false, error: "A record exceeds one ROM bank."};
    if (offset + size > data.allocation.bankSize) { bank++; offset = 0; }
    if (bank >= data.allocation.banks) return {valid: false, error: "These edits exceed the ROM text allocation. Keep the draft; allocation needs a project change."};
    offset += size;
  }
  return {valid: true, banksUsed: bank + 1, endOffset: offset};
}

export function exportEdits(data, edits) {
  const records = new Map(data.records.map(row => [row.loc, row]));
  const changed = Object.entries(edits).filter(([loc, text]) => text !== records.get(loc)?.draft);
  if (!changed.length) throw new Error("There are no changes to download.");
  const merged = workspace(data, edits);
  const bad = [...merged.checked].find(([, result]) => !result.valid);
  if (bad) throw new Error(`${bad[0]}: ${bad[1].errors[0]}`);
  const output = [`# format\t${EDIT_FORMAT}`, `# revision\t${data.revision}`, `# rules\t${data.rulesRevision}`];
  for (const [loc, text] of changed) {
    const row = records.get(loc);
    if (!row?.editable || !merged.checked.get(loc).valid) throw new Error(`${loc}: fix the entry before downloading.`);
    output.push(`# base\t${loc}\t${row.base}`);
  }
  output.push("# id\tenglish");
  for (const row of data.records) if (changed.some(([loc]) => loc === row.loc)) output.push(`${row.loc}\t${edits[row.loc]}`);
  const allocation = checkAllocation(data, edits);
  if (!allocation.valid) throw new Error(allocation.error);
  const file = output.join("\n") + "\n";
  if (new TextEncoder().encode(file).length > 2_000_000) throw new Error("This changes TSV exceeds the importer's 2 MB limit. Keep a draft backup and import a smaller batch.");
  return file;
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
      } else if (!equal(fields, ["id", "english"])) throw new Error("Unknown changes metadata.");
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
    if (existing[loc] !== undefined && existing[loc] !== row.draft && existing[loc] !== value) throw new Error(`${loc}: this import conflicts with a saved edit. Download or reset that entry first.`);
    if (value === row.draft) delete merged[loc]; else merged[loc] = value;
  }
  return merged;
}

export function draftBackup(data, edits) {
  const bases = {};
  for (const row of data.records) if (Object.hasOwn(edits, row.loc)) bases[row.loc] = row.base;
  return JSON.stringify({format: "shiren-gb2-workbench-draft-v1", revision: data.revision,
    rules: data.rulesRevision, bases, edits}, null, 2);
}

export function importBackup(text, data, existing = {}) {
  const saved = JSON.parse(text), rows = new Map(data.records.map(row => [row.loc, row]));
  if (!saved || saved.format !== "shiren-gb2-workbench-draft-v1" || saved.rules !== data.rulesRevision ||
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
