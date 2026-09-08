// Check reference coverage against the native codec and both shipped catalogues.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {controlReferenceURL} from "../docs/translation-tool/controls/links.js";

const read = path => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const page = read("docs/translation-tool/controls/index.html");
const ids = [...page.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(new Set(ids).size, ids.length, "Reference anchors must be unique");
function anchor(token) {
  const url = new URL(controlReferenceURL(token));
  assert.ok(url.pathname.endsWith("/translation-tool/controls/"), token + ": hosted subdirectory");
  assert.ok(ids.includes(url.hash.slice(1)), token + ": missing reference target " + url.hash);
  return url.hash.slice(1);
}

const codec = read("tools/codec.py");
const nativeControls = codec.match(/\nCONTROLS = \{([\s\S]*?)\n\}/)[1];
for (const [, byte, name] of nativeControls.matchAll(/0x([0-9A-F]{2}): '([^']+)'/g)) {
  assert.equal(anchor(`<${name}>`), name.toLowerCase(), "Native renderer control " + byte);
  assert.equal(anchor(`<${byte}>`), name.toLowerCase(), "Raw spelling " + byte);
}
for (const token of ["<copy:01:19:C5>", "<name>", "<name:00>", "<lookup:19:C5>",
  "<number:19:C5>", "<sourceF6:07:19:C5>"]) {
  assert.equal(anchor(token), token.match(/^<([^:>]+)/)[1].toLowerCase());
}
for (const line of read("data/kanji.tsv").split("\n").slice(1).filter(Boolean)) {
  const [, token, kind] = line.split("\t");
  if (kind === "token") assert.equal(anchor(token), token.slice(1, -1).toLowerCase(), "Named glyph " + token);
}
assert.equal(anchor("<FF>"), "terminator");
assert.equal(anchor("<empty>"), "empty");
assert.equal(anchor("{F174=明}"), "prefixed-glyphs");
assert.equal(anchor("{F224}"), "prefixed-glyphs");
for (const token of ["<D2>", "<unknown>", "<constructor>", "<__proto__>"]) assert.equal(anchor(token), "raw-bytes");

let count = 0;
for (const editor of ["prose", "workbench"]) {
  const data = JSON.parse(read(`docs/translation-tool/${editor}/catalog.json`));
  for (const row of data.records) {
    for (const text of [row.japanese, row.draft, row.current, ...(row.sequence || [])].filter(Boolean)) {
      for (const token of text.match(/<[^>]+>|\{[0-9a-f]{4}(?:=[^{}])?\}/gi) || []) {
        anchor(token); count++;
      }
    }
  }
}
for (const [, href] of page.matchAll(/href="#([^"]+)"/g)) assert.ok(ids.includes(href), "Section navigation: " + href);
console.log(`PASS: codec controls, source substitutions, all named glyphs and ${count} catalogue token links resolve to reference anchors`);
