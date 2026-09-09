# Localized title audition

Status: visual approval pending. This audition does not patch a ROM or change the
production build. The supplied source artwork remains untouched under
`assets/graphics/GB2 Title Graphics/`.

## Proposed appearance

Preserve the supplied composition and pixel positions: the top-center bat, moon,
castle silhouette, `Mystery Dungeon`, `Shiren`, `The Wanderer`, `GB2`, `Magic Castle
of the Desert`, sand, visible gap between sand and sky, and the sky gradient. The
user confirmed **Magic**, matching the supplied artwork, on September 8, 2026.

The original moon-ring animation and both native bats run at the native frame
rate. Raise only the small moon-side bat by 12 pixels, keeping its original wing
frames and horizontal movement. This puts it above the English lettering while
keeping the moon and castle in their supplied positions.

The subtitle uses all eight supplied precomposed sparkle frames. The proposed
timing holds each phase for ten native frames: a 1.339-second sweep, followed by
2.679 seconds at rest, repeating every 4.018 seconds. The first sweep starts after
about one second. The interactive preview also offers quicker and gentler timing.
The full composition is mandatory; retain the sparkle unless cartridge insertion
is demonstrated to be impossible with it.

The supplied images are 160×143 and align with rows 1–143 of the native screenshot.
Keep the authored coordinates, and repeat the bottom sand row once to fill a
160×144 screen. No rescaling or cropping of the authored composition is proposed.

## Review

```sh
python3 tools/title_localization_audition.py
open build/title-localization-audition/index.html
```

The HTML is self-contained and works directly from disk. It includes the supplied
GIF for comparison, timing choices, pause, frame step, native/integer zoom, and a
still export. It embeds 480 frames captured from an unmodified original ROM;
PyBoy exits with saving disabled. Only the original sky/moon/bat band is sampled
from those frames. All lower scenery comes from the supplied English composition.
The small bat is decoded from native OAM/VRAM, its original footprint is restored
from the underlying background, and its opaque pixels are drawn 12 pixels higher.

Open with `?verify=1` to check every captured frame for bat/title collision,
offscreen bat pixels, and changes to scenery outside the subtitle. Open with
`?export=1` to include the same checks plus PNG frame data in the
`audition-result` JSON element for lossless review exports. The ordinary interactive
view starts automatically without either parameter.

The reviewed output directory also contains `title-audition.gif`,
`title-audition.png`, `title-audition-native.png`, `review.png`, `checks.json`, and
`manifest.json`. The manifest records source hashes and proposed timing. The GIF
is encoded from browser-rendered frames with cumulative centisecond timing.

## Insertion approach after approval

1. Compile the approved composition into a title-specific combination of native
   tile planes, tilemap, palette attributes, and any needed sprite overlays.
   Replace the Japanese logo overlays as well as its background tiles; changing
   only the main background plane would leave Japanese sprite fragments.
2. Preserve the native sky-gradient routine, moon animation, and two bat
   animations. Apply the small bat's vertical adjustment in its title-only
   positioning path. Keep the castle, horizon, sand, and complete English logo.
3. Give the subtitle its own eight-phase sparkle schedule. Investigate changed
   subtitle tile uploads and sprite overlays against the actual VRAM, palette,
   sprite-per-line, and VBlank budgets before choosing the final representation.
   Keep the longer pause independent of the moon and bat clocks.
4. Guard original ROM bytes, reserve any new data/code ranges, and verify the
   actual cartridge output through startup, title idle, Start/menu handoff,
   return to title, and attract transitions. Compare emulator frames against the
   approved composition, with particular checks for gradient continuity, complete
   scenery, sparkle phases, and bat clearance.

The native resource locations are documented in
[GRAPHICS_AUDIT.md](GRAPHICS_AUDIT.md#title-screen). This canvas audition establishes
appearance and timing, not completed cartridge feasibility. Exact palette/tile
packing, sprite allocation, ROM hooks, and transition handling remain insertion
work. Some authored RGB values (such as the logo's `(3,3,3)` ink) also need an
explicit cartridge-palette mapping rather than silently assuming the PNG is
already native-format graphics.
