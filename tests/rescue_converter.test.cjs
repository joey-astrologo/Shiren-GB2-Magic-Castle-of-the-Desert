"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const converter = require("../docs/rescue-converter/converter.js");
const strings = require("../docs/rescue-converter/i18n.js");
const vectors = JSON.parse(fs.readFileSync(0, "utf8"));
for (const vector of vectors) {
  assert.deepEqual(converter.convert(vector.input, vector.to), vector.expected, vector.input);
}
for (const [input, to, error] of [
  ["", "english", /Enter a password/],
  ["あ".repeat(6), "english", /6 symbols/],
  ["WISH", "japanese", /4 symbols/],
  ["ろいほおんりぶづおきぐすA", "english", /not in the Japanese/],
  ["qBdEtn!6EGwMi", "english", /not in the Japanese/],
  ["ろいほおんりぶづおきぐすも", "japanese", /not in the English/],
  ["qBdEtn!6EGwMA", "japanese", /checksum/],
  ["qBdEtn!6EGwMi", "invalid", /Output language/],
  ["qBdEtn!6EGwMi\u200b", "japanese", /not in the English/],
  ["😀".repeat(13), "english", /not in the Japanese/],
]) assert.throws(() => converter.convert(input, to), error);

// The UI needs structured errors to explain the same invalid packet in either language.
for (const [input, to, code, details] of [
  [null, "english", "text", {}],
  ["", "english", "empty", {}],
  ["qBdEtn!6EGwMi", "invalid", "direction", {}],
  ["あ".repeat(6), "english", "length", {count: 6}],
  ["ろいほおんりぶづおきぐすA", "english", "character", {character: "A", position: 13, source: "japanese"}],
  ["qBdEtn!6EGwMi😀", "japanese", "character", {character: "😀", position: 14, source: "english"}],
  ["qBdEtn!6EGwMA", "japanese", "checksum", {}]
]) assert.throws(() => converter.convert(input, to), error => {
  assert.equal(error.code, code);
  assert.deepEqual(error.details, details);
  for (const language of ["en", "ja"]) assert.ok(strings[language][`error_${code}`]);
  return true;
});

assert.deepEqual(Object.keys(strings.en).sort(), Object.keys(strings.ja).sort());
for (const key of Object.keys(strings.en)) {
  const placeholders = value => (value.match(/\{\w+\}/g) || []).sort();
  assert.deepEqual(placeholders(strings.en[key]), placeholders(strings.ja[key]), key);
  assert.ok(strings.en[key] && strings.ja[key], key);
}
const html = fs.readFileSync(require("node:path").join(__dirname, "../docs/rescue-converter/index.html"), "utf8");
for (const [, key] of html.matchAll(/data-i18n="([^"]+)"/g)) assert.ok(strings.en[key], key);
console.log(`${vectors.length} browser codec checks passed, plus invalid-input checks.`);
