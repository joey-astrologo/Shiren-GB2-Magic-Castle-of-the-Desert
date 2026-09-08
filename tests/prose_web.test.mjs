import fs from "node:fs";
import assert from "node:assert/strict";
import {validateDraft, exportEdits, importEdits, checkAllocation, draftBackup, importBackup} from "../docs/translation-tool/prose/rules.js";

const data = JSON.parse(fs.readFileSync(new URL("../docs/translation-tool/prose/catalog.json", import.meta.url)));
const cases = JSON.parse(fs.readFileSync(new URL("fixtures/prose_web_cases.json", import.meta.url)));
const records = new Map(data.records.map(row => [row.loc, row]));
function compare(row, text, expected, label) {
  const value = validateDraft(row, text, data);
  assert.equal(value.valid, expected.valid, `${label}: ${JSON.stringify(value.errors)}; Python: ${expected.error || "valid"}`);
  if (value.valid) {
    assert.equal(value.wrapped, expected.wrapped, label + ": wrapping differs");
    assert.equal(value.encodedBytes, expected.encodedBytes, label + ": encoded size differs");
    assert.deepEqual(value.lines.map(line => [line.box, line.row, line.composer, line.extent]), expected.lines, label + ": geometry differs");
  }
}
for (const row of data.records) compare(row, row.draft, row.expected, row.loc);
for (const test of cases) compare(test.row || records.get(test.id), test.text, test.expected, `${test.id || "synthetic"}: ${test.label}`);

const valid = cases.find(test => test.id && test.expected.valid && test.text !== records.get(test.id).draft);
const edits = {[valid.id]: valid.text}, row = records.get(valid.id);
const download = exportEdits(data, edits);
assert.deepEqual(importEdits(download, data), edits);
assert.deepEqual(importEdits("\uFEFF" + download.replaceAll("\n", "\r\n"), data), edits);
assert.deepEqual(importEdits(download, data, edits), edits);
assert.throws(() => importEdits(download, data, {[valid.id]: "conflicting draft"}));
assert.throws(() => importEdits(download.replace(row.base, "0".repeat(64)), data));
assert.throws(() => importEdits(download.replace(data.rulesRevision, "0".repeat(64)), data));
assert.throws(() => importEdits(download + valid.id + "\tduplicate\n", data));
assert.throws(() => importEdits(download.replace(valid.id, "999:$FFFF"), data));
assert.throws(() => importEdits(download.replace("shiren-gb2-prose", "shiren-prose"), data));
assert.throws(() => exportEdits(data, {[valid.id]: "bad\ttext"}));
assert.throws(() => exportEdits(data, {[valid.id]: "bad\ntext"}));
assert.throws(() => exportEdits(data, {[valid.id]: ""}));
assert.throws(() => exportEdits(data, {[data.records.find(r => !r.editable).loc]: "New text."}));
assert.throws(() => exportEdits(data, {}));
const synthetic = cases.find(test => test.row).row;
const bankFits = validateDraft(synthetic, ("A".repeat(22) + "<page><box>").repeat(682), data);
assert.equal(bankFits.valid, true, "A 16,368-byte record fits a ROM bank");
assert.equal(bankFits.encodedBytes, 16368);
const bankOver = validateDraft(synthetic, ("A".repeat(22) + "<page><box>").repeat(683), data);
assert.equal(bankOver.valid, false, "A 16,392-byte record must be blocked before download");
assert.ok(bankOver.errors.some(message => message.includes("ROM bank")));
const invalidDraft = {[valid.id]: "Unfinished ☃"};
assert.deepEqual(importBackup(draftBackup(data, invalidDraft), data), invalidDraft);
assert.throws(() => importBackup(draftBackup(data, invalidDraft).replace(row.base, "0".repeat(64)), data));
assert.throws(() => importBackup(draftBackup(data, invalidDraft), data, edits));
const allocations = JSON.parse(fs.readFileSync(new URL("fixtures/prose_web_allocation.json", import.meta.url)));
for (const test of allocations) {
  const edits = Object.fromEntries(Object.keys(test.sizes).map(id => [id, "changed"]));
  const checked = new Map(Object.entries(test.sizes).map(([id, encodedBytes]) => [id, {valid: true, encodedBytes}]));
  const actual = checkAllocation(data, edits, checked);
  assert.equal(actual.valid, test.expected.valid, "Allocation verdict differs from Python");
  if (actual.valid) assert.deepEqual(actual, test.expected, "Bank packing differs from Python");
}
if (process.argv.includes("--download-fixture")) fs.writeFileSync(new URL("../build/prose-web-roundtrip.tsv", import.meta.url), download);
console.log(`${data.records.length} baselines, ${cases.length} Python mutation oracles, ${allocations.length} allocation cases, and TSV/backup round trips passed.`);
