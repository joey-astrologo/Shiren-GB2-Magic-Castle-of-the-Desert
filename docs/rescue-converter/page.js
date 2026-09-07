(function () {
  "use strict";
  const byId = id => document.getElementById(id);
  const input = byId("password"), output = byId("result"), direction = byId("direction");
  const status = byId("status"), copy = byId("copy");
  const language = byId("language"), languageKey = "shiren-gb2-rescue-language";
  let locale = "en", result = null, error = null, copied = false, copyFallback = false;
  // Invalidate a pending clipboard result when the input or direction changes.
  let revision = 0;

  function text(key, values = {}) {
    return RescuePasswordStrings[locale][key].replace(/\{(\w+)\}/g, (_, name) => values[name]);
  }

  function missionText(mission) {
    return {
      title: text(`mission_${mission.id}`),
      dungeon: locale === "ja" ? mission.dungeon_japanese : mission.dungeon,
      floor: text("floor", {number: mission.floor})
    };
  }

  function renderFields() {
    const japaneseInput = direction.value === "english";
    byId("input-label").textContent = text(japaneseInput ? "japanesePassword" : "englishPassword");
    byId("result-label").textContent = text(japaneseInput ? "englishPassword" : "japanesePassword");
    input.placeholder = text(japaneseInput ? "japanesePlaceholder" : "englishPlaceholder");
    input.lang = japaneseInput ? "ja" : "en";
    output.lang = japaneseInput ? "en" : "ja";
    output.placeholder = text("resultPlaceholder");
    const count = Array.from(RescuePasswordConverter.normalize(input.value)).length;
    byId("count").textContent = text(count === 1 ? "oneSymbol" : "symbols", {count});
    copy.textContent = text(copied ? "copied" : "copy");
    status.className = error ? "error" : "";
    if (error) {
      const key = `error_${error.code}`;
      status.textContent = text(Object.hasOwn(RescuePasswordStrings[locale], key) ? key : "error_unknown", {
        ...error.details,
        source: text(error.details?.source === "japanese" ? "sourceJapanese" : "sourceEnglish")
      });
    } else if (copyFallback) {
      status.textContent = text("copyFallback");
    } else if (result) {
      const mission = RescuePasswordData.missions.find(row => row.english === result.english);
      status.textContent = text("success", {kind: text(`kind_${result.kind}`), count: result.length})
        + (mission ? text("missionStatus", missionText(mission)) : "");
    } else {
      status.textContent = "";
    }
  }

  function resetResult() {
    revision++;
    result = null;
    error = null;
    copied = false;
    copyFallback = false;
    output.value = "";
    copy.disabled = true;
    input.removeAttribute("aria-invalid");
    renderFields();
  }

  function convert() {
    resetResult();
    try {
      result = RescuePasswordConverter.convert(input.value, direction.value);
      output.value = result[direction.value];
      copy.disabled = false;
    } catch (failure) {
      error = failure;
      input.setAttribute("aria-invalid", "true");
    }
    renderFields();
  }

  byId("converter-form").addEventListener("submit", event => { event.preventDefault(); convert(); });
  input.addEventListener("input", resetResult);
  direction.addEventListener("change", resetResult);
  byId("clear").addEventListener("click", () => { input.value = ""; resetResult(); input.focus(); });
  copy.addEventListener("click", async () => {
    const current = revision;
    const value = output.value;
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      if (current === revision) {
        copied = true;
        copyFallback = false;
        renderFields();
      }
    } catch (_) {
      if (current !== revision) return;
      output.focus();
      output.select();
      copied = false;
      copyFallback = true;
      renderFields();
    }
  });

  function renderMissions() {
    byId("mission-list").replaceChildren();
    for (const mission of RescuePasswordData.missions) {
      const labels = missionText(mission);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mission";
      for (const [tag, className, label] of [
        ["span", "level", labels.title], ["strong", "", labels.dungeon],
        ["span", "floor", labels.floor], ["span", "load", text("loadMission")]
      ]) {
        const element = document.createElement(tag);
        element.className = className;
        element.textContent = label;
        button.appendChild(element);
      }
      button.addEventListener("click", () => {
        direction.value = "english";
        input.value = mission.japanese;
        convert();
        byId("converter-title").scrollIntoView({block: "start"});
        input.focus({preventScroll: true});
      });
      byId("mission-list").appendChild(button);
    }
  }

  function setLanguage(value) {
    locale = value === "ja" ? "ja" : "en";
    language.value = locale;
    document.documentElement.lang = locale;
    document.title = text("title");
    document.querySelector('meta[name="description"]').content = text("description");
    for (const element of document.querySelectorAll("[data-i18n]")) {
      element.textContent = text(element.dataset.i18n);
    }
    renderFields();
    renderMissions();
  }

  language.addEventListener("change", () => {
    setLanguage(language.value);
    try { localStorage.setItem(languageKey, locale); } catch (_) { /* Offline/private storage may be unavailable. */ }
  });
  let preferred = (navigator.language || "en").toLowerCase().startsWith("ja") ? "ja" : "en";
  try {
    const saved = localStorage.getItem(languageKey);
    if (saved === "en" || saved === "ja") preferred = saved;
  } catch (_) { /* Language selection still works without storage. */ }
  setLanguage(preferred);
})();
