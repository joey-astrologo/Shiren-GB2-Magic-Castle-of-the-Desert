"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const converter = require("../docs/rescue-converter/converter.js");
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
console.log(`${vectors.length} browser codec checks passed, plus invalid-input checks.`);
