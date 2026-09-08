import assert from "node:assert/strict";
import fs from "node:fs";
import {workspace, validateDraft, checkAllocation, exportEdits, importEdits, draftBackup, importBackup} from "../docs/translation-tool/workbench/rules.js";
const data = JSON.parse(fs.readFileSync(new URL("../docs/translation-tool/workbench/catalog.json", import.meta.url)));
const rows = new Map(data.records.map(r => [r.loc, r]));
const baseline = workspace(data);
assert.equal(rows.size, 6695);
assert.equal(data.subjects.reduce((n, s) => n + s.count, 0), 6695);
assert.equal(baseline.valid, true, JSON.stringify([...baseline.checked].filter(([, r]) => !r.valid)));
for (const row of data.records.filter(r => r.editable)) {
  const got = baseline.checked.get(row.loc), expected = row.expected;
  assert.equal(got.valid, expected.valid, row.loc);
  assert.equal(got.wrapped, expected.wrapped, row.loc);
  assert.equal(got.encodedBytes, expected.encodedBytes, row.loc);
  assert.deepEqual(got.lines.map(l => [l.box, l.row, l.composer, l.extent]), expected.lines, row.loc);
}
const cases = JSON.parse(fs.readFileSync(new URL("./fixtures/workbench_web_cases.json", import.meta.url)));
for (const test of cases) {
  const got = validateDraft(rows.get(test.id), test.text, data), expected = test.expected;
  assert.equal(got.valid, expected.valid, `${test.id} ${test.label}: ${got.errors}`);
  if (expected.valid) {
    assert.equal(got.wrapped, expected.wrapped, `${test.id} ${test.label}`);
    assert.equal(got.encodedBytes, expected.encodedBytes, `${test.id} ${test.label}`);
    assert.deepEqual(got.lines.map(l => [l.box, l.row, l.composer, l.extent]), expected.lines, `${test.id} ${test.label}`);
  }
}
const id = "194:$55B1", value = "But nothing happened!", edits = {[id]: value};
const tsv = exportEdits(data, edits);
assert.deepEqual(importEdits(tsv, data), edits);
assert.deepEqual(importBackup(draftBackup(data, {[id]: "Unencodable é"}), data), {[id]: "Unencodable é"});
assert.throws(() => exportEdits(data, {[id]: "Unencodable é"}));
assert.throws(() => importEdits(tsv, data, {[id]: "Conflicting text."}));
assert.throws(() => importEdits(tsv.replace(rows.get(id).base, "0".repeat(64)), data));
const fixed = data.records.find(r => !r.editable);
assert.throws(() => exportEdits(data, {[fixed.loc]: "Changed"}));
assert.equal(checkAllocation(data, {}, baseline.checked).valid, true);
// Glossary renames must reach consumers, including entries the user never edited.
const name = data.definitions.find(d => d.english === "Koppa");
assert.ok(name);
const renamed = workspace(data, {[name.record_id]: "Koppi"});
assert.equal(renamed.valid, false);
assert.ok([...renamed.checked].some(([key, result]) => key !== name.record_id && !result.valid && result.errors.some(x => x.includes("Koppi"))));
assert.throws(() => exportEdits(data, {[name.record_id]: "Koppi"}));
// Recompute composed item names rather than retaining the old catalogue maximum.
const prefix = data.records.find(r => r.refs.some(([g, i]) => g === 11 && i === 3));
const widened = workspace(data, {[prefix.loc]: "W".repeat(20)});
assert.equal(widened.valid, false);
assert.ok(Math.max(...widened.domains.item_name.map(v => v[0])) > Math.max(...baseline.domains.item_name.map(v => v[0])));
// Full-screen details and help must not inherit the three-line dialogue cap.
assert.ok(data.records.some(r => r.editable && r.profile.mode === 8 && baseline.checked.get(r.loc).lines.length > 3));
assert.ok(data.records.some(r => r.profile.kind === "notebook" && r.profile.lines === 2));
const missingDomain = {...data, domains: {...data.domains, actor_name: []}};
assert.equal(workspace(missingDomain).valid, false, "Missing runtime domains must fail closed");
console.log(`${data.records.filter(r => r.editable).length} native baselines and ${cases.length} Python mutation oracles passed; shared dependencies, storage and TSV guards passed.`);
