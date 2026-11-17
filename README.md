# Phosphor Glyphs

A Claude desktop and mobile theme based on the turntable display's glyph visualizer
(Home Automation project, `firmware/turntable-display`).

- **Colors**: the display's phosphor palette from `firmware/common/include/dial_core.h`.
  Amber (P3) is the accent, ember (P12) is danger, mint (P1) is success, and cobalt (P7) marks
  literals and "pro" items. Dark mode is warm CRT black with amber-white text. Light mode is
  P4 "paper" phosphor.
- **Backdrop**: the firmware's seven glyphs at about 10 px. Idle, they are dust in space: a still
  far layer, glyphs drifting on slow loops, and a few pairs circling each other. The more work the session is doing
  (output tokens and tool calls over the last 90 s, plus running subagents), the more the dust
  gathers into the turntable's glyph visualizers:

  | Level | When | Pattern |
  |---|---|---|
  | 0 | Idle | Dust |
  | 1 | Light work | Part of the dust lit along three spiral arms, a wave running outward |
  | 2 | Busy | Weather Map: an oval grid of blocks, a spiral wave lighting it |
  | 3 | Intense | Glyph Ring: a compact ring of spokes, two arms of light winding round it |

  A change of level sends a swarm from scattered dust into the new pattern (or out of the old one).
  Each running subagent adds a small ring of glyphs travelling the edge (up to six). Events draw
  over the field: a row of glyphs steps down the sides while reading, a stamp runs along the top
  and bottom while editing, chase lights circle the edge while commands run, an ember burst on an
  error, and a ripple when a turn finishes.

  It holds still when the system asks for reduced motion.

## Low power (since 0.4)

Every looping animation changes on one shared 10 fps grid, like the display's own refresh, and
holds still in between. So the app paints 10 frames a second, not 60. Nothing scales, and no layer
turns as a whole: a whole-screen turn or size pulse repaints everything, and it reads as zooming.
Each scene is a few hundred glyphs at most, most of them still at any moment.

Measured in headless Chrome with software rendering, at 1728×1117 @2x with the glass panel on
(this overstates real GPU cost, so use it to compare versions):

| Scene | 0.3 | 0.4 |
|---|---|---|
| Idle dust | 40% of a core | 9% |
| Spiral arms | 152% | 9% |
| Weather Map | 326% | 4% |
| Glyph Ring | 316% | 12% |
| Glyph Ring + 3 subagents + editing | 336% | 21% |

`tools/archive/gen_scene_v0.3.py` is the previous generator, kept for reference.

The terminal draws no theme; this only changes the desktop and mobile apps.

## Changing the backdrop

`hooks/scenes.ts` is generated. Edit `tools/gen_scene.py`, then run it from this folder:

```
python3 tools/gen_scene.py
```

## Previewing the animations

`tools/preview/` is a page that plays every level, subagent ring and event, with a scripted tour.

```
sh tools/preview/build.sh
python3 -m http.server 8765 -d tools/preview
```

Then open http://localhost:8765. With that server running, `tools/preview/measure.sh "level=2"`
measures a scene's CPU use in headless Chrome.

## Installing

On this Mac it is installed from this folder (a local marketplace), so an edit here reaches a
session after `/reload-plugins`:

```
claude plugin marketplace add ~/Code/tools/phosphor-glyphs
claude plugin install phosphor-glyphs@phosphor-glyphs --scope user
```

From GitHub, on another machine with access to the private repository:

```
/plugin install phosphor-glyphs --marketplace goantelope/phosphor-glyphs
```
