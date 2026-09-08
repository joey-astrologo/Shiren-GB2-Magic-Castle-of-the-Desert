import {validateDraft, exportEdits, importEdits, checkAllocation, draftBackup, importBackup, MAX_TEXT} from "./rules.js";
import {drawPreview, WINDOW, FONT_STYLES} from "./preview.js";

const $ = selector => document.querySelector(selector);
const STORAGE = "shiren-gb2-prose-studio-v1";
const FONT_STORAGE = "shiren-gb2-prose-preview-font-v1";
const PAGE_SIZE = 12;
let data, state, validation, records;
const elements = new Map();

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function notify(message, error = false) {
  const notice = $("#notice");
  notice.hidden = !message;
  notice.className = "notice" + (error ? " error" : "");
  notice.textContent = message;
}

function download(name, text, type = "text/tab-separated-values;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const anchor = node("a"); anchor.href = url; anchor.download = name;
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function save() {
  if (state.stale) return;
  const bases = {};
  for (const loc of Object.keys(state.edits)) bases[loc] = records.get(loc).base;
  try {
    localStorage.setItem(STORAGE, JSON.stringify({revision: data.revision,
      rules: data.rulesRevision, bases, edits: state.edits}));
    $("#save-state").replaceChildren(node("span"), document.createTextNode("Saved in this browser"));
  } catch {
    $("#save-state").textContent = "Browser storage unavailable";
    notify("This browser cannot save drafts locally. Keep this tab open and download your changes before leaving.", true);
  }
}

function restore() {
  let raw;
  try {
    raw = localStorage.getItem(STORAGE);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (!saved || typeof saved.edits !== "object" || saved.edits === null || saved.rules !== data.rulesRevision) throw new Error("old draft");
    for (const [loc, text] of Object.entries(saved.edits)) {
      const row = records.get(loc);
      if (!row?.editable || saved.bases?.[loc] !== row.base || typeof text !== "string" || text.length > MAX_TEXT) throw new Error("old draft");
    }
    state.edits = {...saved.edits};
  } catch {
    if (raw) {
      state.stale = raw;
      $("#recovery").hidden = false;
      $("#save-state").textContent = "Older draft kept for recovery";
    } else {
      $("#save-state").textContent = "Browser storage unavailable";
    }
  }
}

function textFor(row) { return state.edits[row.loc] ?? row.draft; }
function validateAll() {
  validation = new Map(data.records.map(row => [row.loc, validateDraft(row, textFor(row), data)]));
}

function counts() {
  const changed = Object.keys(state.edits).filter(loc => state.edits[loc] !== records.get(loc).draft);
  const errors = changed.filter(loc => !validation.get(loc).valid).length;
  const allocation = checkAllocation(data, state.edits, validation);
  $("#allocation-status").hidden = allocation.valid;
  $("#allocation-status").textContent = allocation.error || "";
  $("#edited-count").textContent = changed.length;
  $("#download-count").textContent = changed.length;
  $("#error-count").textContent = errors;
  $("#backup-draft").disabled = !changed.length || !!state.stale;
  $("#export-edits").disabled = !changed.length || !!errors || !!state.stale || !allocation.valid;
  $("#export-edits").title = errors ? "Fix the entries that need attention before downloading." : "Download edited prose as a TSV.";
}

function navigation() {
  const nav = $("#events"); nav.replaceChildren();
  for (const event of [{id: "all", name: "All dialogue", locs: data.records}, ...data.events]) {
    const button = node("button", (event.id === "all" ? "all-events " : "") + (state.event === event.id ? "active" : ""));
    button.append(document.createTextNode(event.name), node("span", "", event.locs.length));
    button.dataset.event = event.id;
    button.setAttribute("aria-current", state.event === event.id ? "page" : "false");
    button.addEventListener("click", () => {
      state.event = event.id; state.page = 0; state.query = ""; $("#search").value = "";
      navigation(); render();
    });
    nav.append(button);
  }
  $("#event-count").textContent = data.events.length;
}

function sourceContent(container, row) {
  container.replaceChildren();
  const jp = state.japanese[row.loc];
  if (jp === undefined) {
    container.className = "jp jp-placeholder";
    container.textContent = "Japanese source is not loaded yet.";
    return;
  }
  container.className = "jp";
  for (const part of jp.split(/(<[^>]+>)/g)) {
    if (part === "<br>") container.append(node("br"));
    else if (part === "<box>") {
      const divider = node("span", "source-page-break");
      divider.setAttribute("aria-label", "Page break"); container.append(divider);
    } else if (/^<[^>]+>$/.test(part)) container.append(node("span", "token", part));
    else container.append(document.createTextNode(part));
  }
}

function restoreFontStyle() {
  try {
    const style = localStorage.getItem(FONT_STORAGE);
    if (FONT_STYLES.includes(style)) return style;
  } catch { /* A preview preference does not require browser storage. */ }
  return "shadowed";
}

function changeFontStyle() {
  state.fontStyle = $("#font-style").value;
  try { localStorage.setItem(FONT_STORAGE, state.fontStyle); }
  catch { notify("Font style changed for this visit. This browser could not save the preference."); }
  for (const [loc, card] of elements) {
    const canvas = card.querySelector("canvas");
    if (canvas) drawPreview(canvas, validation.get(loc).lines,
      Number(card.querySelector(".preview").dataset.page || 0), data, state.fontStyle);
  }
}

function updateFeedback(row, card) {
  const result = validation.get(row.loc), edited = state.edits[row.loc] !== undefined;
  card.classList.toggle("edited", edited); card.classList.toggle("invalid", !result.valid);
  card.querySelector("textarea")?.setAttribute("aria-invalid", String(!result.valid));
  const badge = card.querySelector(".badge");
  badge.textContent = !row.editable ? "Reference" : !result.valid ? "Needs attention" : edited ? "Edited" : "Original draft";
  badge.className = "badge" + (!result.valid ? " invalid" : edited ? " edited" : "");
  const status = card.querySelector(".row-result"); status.replaceChildren();
  status.append(node("strong", "", result.valid ? (row.editable ? "Passes GB2 prose checks" : "Empty native slot · read-only") : "Check this entry"));
  const boxes = result.lines.length ? result.lines.at(-1).box + 1 : 0;
  status.append(node("span", "", `${boxes} ${boxes === 1 ? "box" : "boxes"}`));
  const messages = card.querySelector(".feedback-messages"); messages.replaceChildren();
  for (const [items, kind] of [[result.errors, "messages"], [result.warnings, "messages warnings"]]) {
    if (items.length) {
      const list = node("ul", kind);
      for (const message of items) list.append(node("li", "", message));
      messages.append(list);
    }
  }
  const details = card.querySelector(".preview");
  details.querySelector("summary").textContent = `GAME PREVIEW · ${boxes} ${boxes === 1 ? "BOX" : "BOXES"}`;
  const content = details.querySelector(".preview-content"); content.replaceChildren();
  if (!result.lines.length) { content.append(node("p", "preview-side", row.editable ? "Fix the token or font error to restore the preview." : "This native dialogue slot is empty.")); return; }
  const box = node("div", "game-box");
  const canvas = node("canvas"); canvas.width = WINDOW.width; canvas.height = WINDOW.height;
  canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", "Preview in the approved game font. Per-line fit measurements follow.");
  box.append(canvas);
  const side = node("div", "preview-side");
  const controls = node("div", "preview-navigation");
  const back = node("button", "", "‹"), forward = node("button", "", "›"), indicator = node("span");
  back.setAttribute("aria-label", "Previous preview box"); forward.setAttribute("aria-label", "Next preview box");
  controls.append(back, indicator, forward);
  const meters = node("div");
  let page = Math.min(Number(details.dataset.page || 0), boxes - 1);
  function paint() {
    details.dataset.page = page;
    indicator.textContent = `Box ${page + 1} of ${boxes}`;
    back.disabled = page === 0; forward.disabled = page >= boxes - 1;
    drawPreview(canvas, result.lines, page, data, state.fontStyle); meters.replaceChildren();
    for (const line of result.lines.filter(line => line.box === page)) {
      const over = line.extent > 144 || line.composer > 143;
      const meter = node("div", "line-meter" + (over ? " over" : ""));
      const bar = node("span", "bar"), fill = node("i"); fill.style.width = Math.min(100, line.extent / 144 * 100) + "%";
      bar.append(fill); meter.append(node("span", "", `L${line.row + 1}`), bar,
        node("span", "", `${line.composer}/143 composer · ${line.extent}/144 pen`)); meters.append(meter);
    }
  }
  back.addEventListener("click", () => { page--; paint(); });
  forward.addEventListener("click", () => { page++; paint(); });
  side.append(controls, meters);
  if (result.lines.some(line => line.operations.some(operation => operation.substitution))) {
    side.append(node("p", "", "Shaded spans reserve room for runtime names or values."));
  }
  content.append(box, side); paint();
}

function updateDraft(row, value, card) {
  if (value === row.draft) delete state.edits[row.loc]; else state.edits[row.loc] = value;
  validation.set(row.loc, validateDraft(row, value, data));
  save(); counts(); updateFeedback(row, card);
  card.querySelector(".preview").open = true;
}

function makeCard(row, first) {
  const card = node("article", "record"); card.id = "entry-" + row.loc.replace(":$", "-");
  card.dataset.loc = row.loc;
  const top = node("div", "record-top"), speaker = node("div", "speaker");
  speaker.append(node("span", "speaker-mark", row.speaker ? row.speaker[0] : "·"), document.createTextNode(row.speaker || "Dialogue"));
  const meta = node("div", "record-meta");
  const link = node("a", "loc", row.loc); link.href = "#" + encodeURIComponent(row.loc);
  meta.append(link, node("span", "badge")); top.append(speaker, meta);
  const body = node("div", "record-body");
  const left = node("div", "source-pane"), japanese = node("div", "jp"); japanese.lang = "ja";
  sourceContent(japanese, row); left.append(japanese);
  const right = node("div", "edit-pane");
  if (row.editable) {
    const input = node("textarea", "editor"); input.value = textFor(row); input.rows = 4;
    input.maxLength = MAX_TEXT; input.spellcheck = false;
    input.disabled = !!state.stale;
    input.setAttribute("aria-describedby", card.id + "-feedback");
    input.setAttribute("aria-label", `Translation for ${row.loc}${row.speaker ? ", " + row.speaker : ""}`);
    input.addEventListener("input", () => updateDraft(row, input.value, card));
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault(); insert(event.ctrlKey || event.metaKey ? "<page><box>" : "<br>");
      }
    });
    function insert(text) {
      const start = input.selectionStart, end = input.selectionEnd;
      if (input.value.length - (end - start) + text.length > MAX_TEXT) return;
      input.setRangeText(text, start, end, "end"); input.focus(); updateDraft(row, input.value, card);
    }
    const tools = node("div", "edit-tools"), inserts = node("div", "token-insert");
    for (const [label, value] of [["＋ Line break", "<br>"], ["＋ New box", "<page><box>"]]) {
      const button = node("button", "", label); button.addEventListener("click", () => insert(value)); inserts.append(button);
      button.disabled = !!state.stale;
    }
    const reset = node("button", "reset-row", "Reset entry");
    reset.disabled = !!state.stale;
    reset.addEventListener("click", () => {
      if (input.value !== row.draft && !confirm("Restore this entry to the current project draft?")) return;
      input.value = row.draft; updateDraft(row, input.value, card);
    });
    tools.append(inserts, reset); right.append(input, tools);
    if (row.sequence.length) {
      const required = node("div", "required", "Source controls (see guide): ");
      for (const token of row.sequence) required.append(node("code", "", token));
      right.append(required);
    }
    if (row.terms.length) {
      const terms = node("div", "required", "Project terms: ");
      for (const term of row.terms) terms.append(node("code", "", term));
      right.append(terms);
    }
    const reference = node("details", "reference");
    reference.append(node("summary", "", "Current English reference"), node("p", "", row.draft)); right.append(reference);
  } else {
    right.append(node("p", "read-only-text", row.current));
  }
  const feedback = node("div", "feedback-messages"); feedback.id = card.id + "-feedback";
  feedback.setAttribute("aria-live", "polite");
  right.append(node("div", "row-result"), feedback);
  const preview = node("details", "preview"); preview.open = first;
  preview.append(node("summary"), node("div", "preview-content"));
  body.append(left, right); card.append(top, body, preview);
  updateFeedback(row, card); elements.set(row.loc, card);
  return card;
}

function filteredRecords() {
  const query = state.query.toLocaleLowerCase();
  return data.records.filter(row => {
    if (state.event !== "all" && row.event !== state.event) return false;
    if (state.filter === "edited" && state.edits[row.loc] === undefined) return false;
    if (state.filter === "errors" && (state.edits[row.loc] === undefined || validation.get(row.loc).valid)) return false;
    return !query || [row.loc, row.speaker, row.draft, textFor(row), state.japanese[row.loc] || ""].some(value => value.toLocaleLowerCase().includes(query));
  });
}

function render() {
  const found = filteredRecords();
  state.page = Math.min(state.page, Math.max(0, Math.ceil(found.length / PAGE_SIZE) - 1));
  const event = data.events.find(event => event.id === state.event);
  $("#event-title").textContent = state.query ? "Search results" : event?.name || "All dialogue";
  $("#event-kicker").textContent = state.query ? "SEARCH" : "EVENT";
  $("#event-description").textContent = event ? `${event.phase.replaceAll("_", " ")} · Project scene and record order` : "Japanese prose and English drafts are included.";
  $("#row-count").textContent = `${found.length} entries`;
  const container = $("#records"); container.replaceChildren(); elements.clear();
  const slice = found.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
  slice.forEach((row, index) => container.append(makeCard(row, index === 0)));
  $("#empty").hidden = !!found.length;
  $("#empty-message").textContent = state.filter === "errors" ? "Your edited entries have no blocking text errors." :
    state.filter === "edited" ? "Edit a translation to see it here." : "Try a different search or event.";
  $("#previous").disabled = !state.page;
  $("#next").disabled = (state.page + 1) * PAGE_SIZE >= found.length;
  $("#page-status").textContent = found.length ? `${state.page * PAGE_SIZE + 1}–${Math.min((state.page + 1) * PAGE_SIZE, found.length)} of ${found.length} entries` : "0 entries";
  for (const button of document.querySelectorAll("[data-filter]")) {
    const active = button.dataset.filter === state.filter;
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", active);
  }
  counts();
}

function goToHash() {
  let loc;
  try { loc = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const row = records.get(loc); if (!row) return;
  state.event = row.event; state.query = ""; state.filter = "all"; $("#search").value = "";
  state.page = Math.floor(data.records.filter(item => item.event === row.event).findIndex(item => item.loc === loc) / PAGE_SIZE);
  navigation(); render(); elements.get(loc)?.scrollIntoView({block: "start"});
}

async function initialize() {
  const response = await fetch("catalog.json");
  if (!response.ok) throw new Error("The prose catalogue could not be loaded. Serve this folder over HTTP, or regenerate catalog.json.");
  data = await response.json();
  records = new Map(data.records.map(row => [row.loc, row]));
  const start = data.events.find(event => event.id === "opening_sandstorm") || data.events[0];
  state = {event: start.id, query: "", filter: "all", page: 0, edits: {}, japanese: Object.fromEntries(data.records.map(row => [row.loc, row.japanese])), stale: null, fontStyle: restoreFontStyle()};
  $("#font-style").value = state.fontStyle;
  $("#font-style").addEventListener("change", changeFontStyle);
  restore(); validateAll(); navigation(); render(); goToHash();
  window.addEventListener("hashchange", goToHash);
  $("#search").addEventListener("input", event => {
    state.query = event.target.value; state.event = "all"; state.page = 0; navigation(); render();
  });
  for (const button of document.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => { state.filter = button.dataset.filter; state.page = 0; render(); });
  }
  $("#clear-filters").addEventListener("click", () => { state.query = ""; state.event = "all"; state.filter = "all"; state.page = 0; $("#search").value = ""; navigation(); render(); });
  $("#previous").addEventListener("click", () => { state.page--; render(); $(".event-heading").scrollIntoView(); });
  $("#next").addEventListener("click", () => { state.page++; render(); $(".event-heading").scrollIntoView(); });
  $("#export-edits").addEventListener("click", () => {
    try { download("shiren-gb2-prose-changes.tsv", exportEdits(data, state.edits)); notify("Changes downloaded. The project importer will recheck them before applying."); }
    catch (error) { notify(error.message, true); }
  });
  $("#import-edits").addEventListener("click", () => $("#edits-file").click());
  $("#backup-draft").addEventListener("click", () => download("shiren-gb2-prose-draft.json", draftBackup(data, state.edits), "application/json"));
  $("#edits-file").addEventListener("change", async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (state.stale) throw new Error("Recover the older draft before importing edits.");
      if (file.size > 2_000_000) throw new Error("The file is larger than 2 MB.");
      const isBackup = file.name.toLowerCase().endsWith(".json");
      const merged = (isBackup ? importBackup : importEdits)(await file.text(), data, state.edits);
      state.edits = merged; validateAll(); save(); state.event = "all"; state.filter = "edited"; state.page = 0;
      navigation(); render(); notify(isBackup ? "Draft backup imported. Entries that need corrections are saved and marked below." : "Edits imported and checked. Your existing non-conflicting edits were kept.");
    } catch (error) { notify(error.message, true); }
    event.target.value = "";
  });
  $("#rules-open").addEventListener("click", () => $("#guide").showModal());
  $("#rules-mobile").addEventListener("click", () => $("#guide").showModal());
  $("#rules-close").addEventListener("click", () => $("#guide").close());
  $("#guide").addEventListener("click", event => { if (event.target === $("#guide")) $("#guide").close(); });
  $("#recover-draft").addEventListener("click", () => download("shiren-gb2-prose-recovery.json", state.stale, "application/json"));
  $("#fresh-draft").addEventListener("click", () => {
    if (!confirm("Start fresh? Download the recovery file first if you need the older edits.")) return;
    state.stale = null; state.edits = {}; $("#recovery").hidden = true; validateAll(); save(); render();
  });
  document.body.dataset.ready = "true";
}

initialize().catch(error => {
  notify(error.message, true); $("#event-title").textContent = "Could not load dialogue.";
  $("#event-description").textContent = "Check the catalogue and serve the editor over HTTP.";
  document.body.dataset.failed = "true";
});
