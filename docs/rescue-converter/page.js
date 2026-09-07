(function () {
  "use strict";
  const byId = id => document.getElementById(id);
  const input = byId("password"), output = byId("result"), direction = byId("direction");
  const status = byId("status"), copy = byId("copy");
  const kinds = {sos: "SOS", revival: "Revival", thank_you: "Thank-You", training: "Training"};
  // Invalidate a pending clipboard result when the input or direction changes.
  let revision = 0;

  function resetResult() {
    revision++;
    output.value = "";
    copy.disabled = true;
    copy.textContent = "Copy";
    status.textContent = "";
    status.className = "";
    input.removeAttribute("aria-invalid");
    byId("count").textContent = `${Array.from(RescuePasswordConverter.normalize(input.value)).length} symbols`;
  }

  function updateDirection() {
    const japaneseInput = direction.value === "english";
    byId("input-label").textContent = japaneseInput ? "Japanese password" : "English password";
    byId("result-label").textContent = japaneseInput ? "English password" : "Japanese password";
    input.placeholder = japaneseInput ? "Paste a Japanese password here" : "Paste an English password here";
    resetResult();
  }

  function convert() {
    resetResult();
    try {
      const result = RescuePasswordConverter.convert(input.value, direction.value);
      output.value = result[direction.value];
      copy.disabled = false;
      const mission = RescuePasswordData.missions.find(row => row.english === result.english);
      status.textContent = `${kinds[result.kind]} · ${result.length} symbols · Checksum passed.`
        + (mission ? ` ${mission.title}: ${mission.dungeon}, ${mission.floor}F.` : "");
    } catch (error) {
      status.textContent = error.message;
      status.className = "error";
      input.setAttribute("aria-invalid", "true");
    }
  }

  byId("converter-form").addEventListener("submit", event => { event.preventDefault(); convert(); });
  input.addEventListener("input", resetResult);
  direction.addEventListener("change", updateDirection);
  byId("clear").addEventListener("click", () => { input.value = ""; resetResult(); input.focus(); });
  copy.addEventListener("click", async () => {
    const current = revision;
    const value = output.value;
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      if (current === revision) copy.textContent = "Copied!";
    } catch (_) {
      if (current !== revision) return;
      output.focus();
      output.select();
      status.textContent = "Password selected. Use your device’s Copy command to copy it.";
    }
  });

  for (const mission of RescuePasswordData.missions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mission";
    for (const [tag, className, text] of [
      ["span", "level", mission.title], ["strong", "", mission.dungeon],
      ["span", "floor", `${mission.floor}F`], ["span", "load", "Convert this mission →"]
    ]) {
      const element = document.createElement(tag);
      element.className = className;
      element.textContent = text;
      button.appendChild(element);
    }
    button.addEventListener("click", () => {
      direction.value = "english";
      input.value = mission.japanese;
      updateDirection();
      convert();
      byId("converter-title").scrollIntoView({block: "start"});
      input.focus({preventScroll: true});
    });
    byId("mission-list").appendChild(button);
  }
  updateDirection();
})();
