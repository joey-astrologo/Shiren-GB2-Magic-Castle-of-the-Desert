/* Navigation only: explanations do not change validation or saved-draft revisions. */
const names = new Set([
  "br", "page", "box", "cf3", "hspace", "copy", "name", "lookup", "number", "sourcef6",
  "cf8", "delay", "cf9", "cfe", "speaker", "speakerend", "quoteopen", "quoteclose",
  "cracked", "passwordleft", "passwordright", "empty",
]);
const rawCodes = {f3: "cf3", f4: "copy", f5: "name", f6: "sourcef6", f7: "hspace",
  f8: "cf8", f9: "cf9", fa: "delay", fb: "page", fc: "box", fd: "br", fe: "cfe", ff: "terminator"};
const tokenPattern = /(<[^>]+>|\{[0-9a-f]{4}(?:=[^{}])?\})/gi;

export function controlReferenceURL(token) {
  const name = token.match(/^<([^:>]+)/)?.[1].toLowerCase();
  const anchor = names.has(name) ? name : (/^[0-9a-f]{2}$/.test(name) && rawCodes[name]) ||
    (/^\{[0-9a-f]{4}(?:=[^{}])?\}$/i.test(token) ? "prefixed-glyphs" : "raw-bytes");
  return new URL(`./#${anchor}`, import.meta.url).href;
}

export function controlReferenceLink(token, className = "") {
  const link = document.createElement("a"), code = document.createElement("code");
  code.textContent = token;
  if (className) code.className = className;
  link.append(code);
  link.className = "control-reference-link";
  link.href = controlReferenceURL(token);
  link.target = "_blank";
  link.rel = "noopener";
  link.title = `Meaning of ${token} (opens in a new tab)`;
  link.setAttribute("aria-label", link.title);
  return link;
}

export function controlReferenceLinks(text) {
  const fragment = document.createDocumentFragment();
  for (const [i, part] of text.split(tokenPattern).entries()) {
    fragment.append(i % 2 ? controlReferenceLink(part) : document.createTextNode(part));
  }
  return fragment;
}

export function linkGuideControls(guide) {
  for (const code of guide.querySelectorAll("code")) {
    if (code.textContent.startsWith("<")) code.replaceWith(controlReferenceLinks(code.textContent));
  }
}
