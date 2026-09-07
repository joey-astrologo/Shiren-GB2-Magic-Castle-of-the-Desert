/* GB2 packet validation mirrors tools/rescue_password.py. No packet generation. */
(function (root) {
  "use strict";
  const data = typeof module === "object" && module.exports
    ? require("./password-data.js") : root.RescuePasswordData;

  // Stable identifiers let the interface translate errors without parsing English prose.
  function invalid(code, message, details = {}) {
    const error = new Error(message);
    error.code = code;
    error.details = details;
    return error;
  }

  function normalize(text) {
    if (typeof text !== "string") throw invalid("text", "Password must be text.");
    return Array.from(text.normalize("NFKC"))
      .filter(character => !data.whitespace.includes(character))
      .map(character => {
        const code = character.codePointAt(0);
        return code >= 0x30a1 && code <= 0x30f6 ? String.fromCodePoint(code - 0x60) : character;
      }).join("");
  }

  function transpose(values) {
    const result = Array(8).fill(0);
    for (let column = 0; column < 8; column++) {
      for (let row = 0; row < 8; row++) {
        result[column] = (result[column] << 1) | ((values[row] >> (7 - column)) & 1);
      }
    }
    return result;
  }

  function decode(values, size) {
    const symbols = values.slice().reverse();
    for (let index = 0; index + 1 < symbols.length; index += 2) {
      [symbols[index], symbols[index + 1]] = [symbols[index + 1], symbols[index]];
    }
    const cumulative = symbols.slice(0, size);
    for (let index = 0; index < size; index++) {
      cumulative[index] |= ((symbols[size + Math.floor(index / 3)] >> (4 - 2 * (index % 3))) & 3) << 6;
    }
    const checksum = cumulative.reduce((sum, value, index) => sum + value * (2 * (size - index) + 1), 0) & 63;
    if (checksum !== symbols[symbols.length - 1]) {
      throw invalid("checksum", "Password checksum does not match. Check each character and its case against the source.");
    }
    const payload = cumulative.map((value, index) => (value - (index ? cumulative[index - 1] : 0)) & 255);
    if (size >= 8) {
      const extra = size - 8;
      if (extra) payload.splice(extra, 8, ...transpose(payload.slice(extra, extra + 8)));
      payload.splice(0, 8, ...transpose(payload.slice(0, 8)));
    }
    return payload;
  }

  function convert(input, to = "english") {
    if (to !== "english" && to !== "japanese") throw invalid("direction", "Output language must be english or japanese.");
    const text = normalize(input);
    if (!text) throw invalid("empty", "Enter a password first.");
    const source = to === "english" ? "Japanese" : "English";
    const alphabet = to === "english" ? data.native_alphabet : data.english_alphabet;
    const characters = Array.from(text);
    const values = characters.map((character, index) => {
      const value = alphabet.indexOf(character);
      if (value < 0) throw invalid("character",
        `Character “${character}” at position ${index + 1} is not in the ${source} rescue alphabet. Check the conversion direction.`,
        {character, position: index + 1, source: source.toLowerCase()});
      return value;
    });
    const kind = data.kinds[values.length];
    if (!kind) throw invalid("length",
      `Password has ${values.length} symbols. Expected 9 (Training), 12 (Thank-You), 13 (SOS), or 15 (Revival).`,
      {count: values.length});
    const payload = decode(values, data.payload_lengths[kind]);
    return {
      japanese: values.map(value => data.native_alphabet[value]).join(""),
      english: values.map(value => data.english_alphabet[value]).join(""),
      kind,
      length: values.length,
      payload_hex: payload.map(value => value.toString(16).padStart(2, "0")).join("")
    };
  }

  const api = Object.freeze({convert, normalize});
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.RescuePasswordConverter = api;
})(globalThis);
