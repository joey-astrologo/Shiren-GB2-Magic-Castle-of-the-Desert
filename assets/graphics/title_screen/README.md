# Title packing recipe

`packing.json` is the solved, deterministic palette and sprite allocation for the
approved artwork in `../GB2 Title Graphics/`. It also freezes source PNGs, original ROM
resources, and native hook bytes. The original artwork is never rewritten by the build.

`tools/title_graphics.py` validates the recipe, compiles tile planes and palette bands,
and checks the reconstructed pixels. `tools/title_screen.py` installs those assets and
the generated title renderer. Normal builds require Pillow, with no solver dependency.

Appearance, timing, ownership, and emulator verification are documented in
[TITLE_LOCALIZATION.md](../../../docs/TITLE_LOCALIZATION.md).
