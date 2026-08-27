# Regression fixtures

This directory contains compact JSON/TSV contracts for extraction, translation, layout,
patch installation, and production builds. The matching Japanese ROM and complete
extracted script are never stored here. A few foundational codec/extraction fixtures keep
small reviewed Japanese anchors because those characters are the evidence for the mapping.

Fixture families include:

| Area | Representative files |
|---|---|
| Source graph and allocation | `script_directory.json`, `script_allocation.json`, `identity_insert.json` |
| Encoding and fonts | `control_dispatch.json`, `kanji_map.json`, `font_trace.json`, `english_font.json` |
| Translation workspace | `english_overlays.json`, `translation_lint.json`, `translation_build.json` |
| Runtime layout | `text_layout.json`, `runtime_terms.json`, `runtime_widths.json`, `positioned_surfaces.json` |
| Dialogue and messages | `prose_scenes.json`, `prose_wrap.json`, `item_message_wrap.json`, `combat_messages.json` |
| Menus and patches | `main_menu_graphics.json`, `menu_text.json`, `stairs_menu.json`, `name6.json` |
| Proof-of-concept route | `poc_dungeon1.json`, `prose_opening.json` |

ROM integration tests skip when the clean source ROM is absent or has the wrong SHA-1.
Emulator tests skip when PyBoy is unavailable. RGBDS source-equivalence tests skip when
`rgbasm`/`rgblink` are unavailable. A release-strength run should install all optional
dependencies so those skips disappear.

The committed `SaveStates/Mamel.mss` is the Mesen reproduction input for the nested-combat
route. Its extracted `SaveStates/Mamel.srm` is ignored. Recreate it with:

```sh
python3 tools/mesen_state.py SaveStates/Mamel.mss SaveStates/Mamel.srm
```

When intentionally updating a fixture:

1. reproduce the semantic change with the verified source ROM;
2. inspect the changed fields rather than accepting the whole diff;
3. keep bulk Japanese source and ROM payloads out of tracked fixtures; add only the
   smallest reviewed anchor required by an extraction/codec contract;
4. run the focused test and complete suite;
5. explain why the old contract is no longer correct.

A fixture hash changing is not by itself evidence that behavior remains safe.
