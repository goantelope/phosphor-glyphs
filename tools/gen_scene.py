#!/usr/bin/env python3
"""Writes hooks/scenes.ts: the pieces the backdrop is put together from at run time.

The glyphs are the turntable display's (home_automation/firmware/common/include/glyphs.h): dot,
small, outline, solid, dot-box, plus and x, every stroke 2 px, drawn at about 10 px. All are
four-fold symmetric, so a quarter turn returns a glyph to itself.

The field is dust in space when the session is idle, and the more work is happening the more of
it gathers into the patterns of the turntable's glyph visualizers (firmware/turntable-display,
main.cpp: Weather Map and Glyph Ring):

  BASE[0]  dust: drifting glyphs, a few pairs orbiting each other, the far layer still
  BASE[1]  gathering: part of the dust lit up along three spiral arms, a wave running out along them
  BASE[2]  Weather Map: a coarse grid of blocks in an oval, a spiral wave lighting it, the marks
           by the map's dialect
  BASE[3]  Glyph Ring: a compact ring of spokes, two arms of light winding round it
  GATHER[L]  a swarm flying from scattered dust into level L's pattern (reversed: scattering)
  AGENTS[k]  one formation per running subagent: a small turning ring travelling the edge
  OVERLAY    the event of the moment: scan row, stamping rows, chase lights, ember burst, ripple

LOW POWER, on purpose (v0.4): every looping animation changes on one shared 10 fps grid, like the
display's own refresh. Keyframe segments are stepped (steps(n)) so values move only on the grid,
and every delay sits on it, so the whole field changes together ten times a second and holds still
between: the browser paints 10 frames a second instead of 60. Nothing scales and no layer of the
field turns as a whole (a whole-field turn or size pulse repaints everything, and reads as the
screen zooming). Counts are kept to a few hundred glyphs, most of them still at any moment.

Looping animations start at `--o`, a negative delay set from the clock; one-shots start at `--e`,
minus the time since their event. So a redraw never restarts anything.

Run: python3 tools/gen_scene.py   (from the mod folder)
"""
import math, random, pathlib, json

N, S = 12, 0.8
W, H = 1920, 1200
CX, CY = W / 2, H / 2
T = 40
GRID = 0.1  # seconds between changes: the backdrop's frame rate is 1 / GRID
AMBER, EMBER = "#ffa82c", "#ff7040"
MINT, COBALT, PAPER = "#b8ffce", "#80b0ff", "#ece8dc"

def rects(g):
    m, n = N // 2, N
    out = []
    box = lambda x, y, w, h: out.append((x, y, w, h))
    def outline():
        box(0, 0, n, 2); box(0, n - 2, n, 2); box(0, 2, 2, n - 4); box(n - 2, 2, 2, n - 4)
    if g == "dot": box(m - 2, m - 2, 4, 4)
    elif g == "small": box(2, 2, n - 4, n - 4)
    elif g == "outline": outline()
    elif g == "solid": box(0, 0, n, n)
    elif g == "dotbox": outline(); box(4, 4, n - 8, n - 8)
    elif g == "plus": box(m - 2, 0, 4, n); box(0, m - 2, m - 2, 4); box(m + 2, m - 2, m - 2, 4)
    elif g == "x":
        for i in range(0, n, 2):
            box(i, i, 2, 2)
            if n - 2 - i != i: box(n - 2 - i, i, 2, 2)
    return out

GLYPHS = ["dot", "small", "outline", "solid", "dotbox", "plus", "x"]
ID = dict(zip(GLYPHS, "abcdefg"))
DEFS = "<defs>" + "".join(
    f'<path id="{ID[g]}" transform="scale({S}) translate({-N / 2} {-N / 2})" d="'
    + "".join(f"M{x} {y}h{w}v{h}h{-w}z" for x, y, w, h in rects(g)) + '"/>'
    for g in GLYPHS
) + "</defs>"

def q(sec):
    """a time on the grid"""
    return round(sec / GRID) * GRID

def kf(name, dur, frames, step=GRID):
    """Stepped keyframes: frames are (seconds, declarations); each segment moves in steps of `step`.

    The animation may run at a whole multiple of `dur` too: its steps are then that multiple of `step`."""
    out = []
    for i, (t, decl) in enumerate(frames):
        pct = t / dur * 100
        if i + 1 < len(frames):
            seg = frames[i + 1][0] - t
            n = max(1, round(seg / step))
            # every step must land on the shared grid, or the field stops changing all at once
            assert abs(seg - n * step) < 1e-6 and abs(t / GRID - round(t / GRID)) < 1e-6, (name, t, seg)
            out.append(f"{pct:.3g}%{{{decl};animation-timing-function:steps({n},end)}}")
        else:
            out.append(f"{pct:.3g}%{{{decl}}}")
    return f"@keyframes {name}{{{''.join(out)}}}"

def spin_kf(name, period, deg=360):
    return kf(name, period, [(0, "rotate:0deg"), (period, f"rotate:{deg}deg")])

BASE_CSS = (
    f"svg{{fill:var(--g,{AMBER})}}use{{transform-box:fill-box;transform-origin:center}}"
    "@media (prefers-reduced-motion:reduce){*{animation-play-state:paused!important}}"
)

def use(g, x=0, y=0, cls="", style="", fill=""):
    c = f' class="{cls}"' if cls else ""
    s = f' style="{style}"' if style else ""
    f = f' fill="{fill}"' if fill else ""
    xy = f' x="{x:.0f}" y="{y:.0f}"' if (x or y) else ""
    return f'<use href="#{ID[g]}"{xy}{c}{s}{f}/>'

def lp(sec):
    """a looping animation's delay on the shared clock, on the grid"""
    return f"calc(var(--o) - {q(sec % T):.1f}s)"

def piece(css, body):
    return {"css": css, "body": body}

def phase_classes(prefix, nb, period):
    """classes p0..p{nb-1} giving a wave's phase as a delay on the grid"""
    return "".join(f".{prefix}{b}{{animation-delay:{lp(b / nb * period)}}}" for b in range(nb))

# ---------- dust ----------
# wander loops: 8 points round a lumpy ellipse; 20 s or 40 s a lap, so each point is 2.5 s or 5 s
def wander_css(tag):
    css = ""
    for k in range(4):
        frames = []
        for j in range(9):
            a = j / 8 * math.tau
            r = 1 + 0.35 * math.sin(3 * a + k)
            x, y = math.cos(a) * r * (1 if k % 2 else -1), math.sin(a) * r * (0.6 + 0.2 * k)
            frames.append((j * 2.5, f"translate:calc({x:.2f}*var(--r)) calc({y:.2f}*var(--r))"))
        css += kf(f"{tag}w{k}", 20, frames)
    # a twinkle that rests most of the time: the glyph holds still between flashes
    css += kf(f"{tag}t", 4, [(0, "opacity:.35"), (2.4, "opacity:.35"), (2.8, "opacity:1"), (3.2, "opacity:.35"), (4, "opacity:.35")])
    # orbiting pairs: two glyphs on one small circle, half a lap apart, so they circle each other
    frames = [(j * 1.5, f"translate:calc({math.cos(j / 16 * math.tau):.2f}*var(--r)) calc({math.sin(j / 16 * math.tau):.2f}*var(--r))") for j in range(17)]
    css += kf(f"{tag}o", 24, frames)
    css += f".{tag}m{{animation-timing-function:linear;animation-iteration-count:infinite}}"
    css += "".join(f".{tag}k{k}{{animation-name:{tag}w{k},{tag}t}}" for k in range(4))
    css += f".{tag}p{{animation:{tag}o 24s infinite}}"
    return css

def scatter(rng):
    return rng.uniform(-20, W + 20), rng.uniform(-20, H + 20)

def dust(rng, far=50, mid=20, near=10, pairs=4, tag="d"):
    css = wander_css(tag)
    body = ""
    # far: still, faint; they cost nothing to keep
    grp = "".join(use("dot", *scatter(rng)) for _ in range(far))
    body += f'<g opacity=".28">{grp}</g>'
    # mid and near: drifting on their loops, near ones twinkling
    for count, glyphs, op, wander in [(mid, ["dot", "dot", "small"], 0.55, 22), (near, ["small", "outline", "plus", "x"], 0.85, 40)]:
        grp = ""
        for _ in range(count):
            dur = rng.choice([20, 40])
            grp += use(rng.choice(glyphs), *scatter(rng), f"{tag}m {tag}k{rng.randrange(4)}",
                       f"--r:{wander * rng.uniform(.6, 1.4):.0f}px;animation-delay:{lp(rng.uniform(0, T))},{lp(rng.uniform(0, 4))};animation-duration:{dur}s,4s")
        body += f'<g opacity="{op}">{grp}</g>'
    # pairs circling each other
    grp = ""
    for _ in range(pairs):
        x, y = scatter(rng)
        r = rng.uniform(12, 26)
        g = rng.choice(["small", "plus", "x"])
        start = rng.uniform(0, 24)
        for half in (0, 12):
            grp += use(g, x, y, f"{tag}p", f"--r:{r:.0f}px;animation-delay:{lp(start + half)}")
    body += f'<g opacity=".8">{grp}</g>'
    return css, body

def base_dust():
    return piece(*dust(random.Random(1)))

# ---------- level 1: gathering into spiral arms ----------
def spiral_points(rng, n, arms=3, r0=260, r1=900, wind=0.004, jitter=20):
    out = []
    for i in range(n):
        arm = i % arms
        r = r0 + (r1 - r0) * (rng.random() ** 0.8)
        a = arm / arms * math.tau + (r - r0) * wind + rng.gauss(0, 0.05)
        out.append((CX + math.cos(a) * r + rng.gauss(0, jitter), CY + math.sin(a) * r * 0.75 + rng.gauss(0, jitter)))
    return out

def base_gather():
    rng = random.Random(2)
    css, body = dust(rng, far=30, mid=18, near=8, pairs=3)
    nb, period = 40, 8
    css += phase_classes("sp", nb, period)
    css += kf("sa", period, [(0, "opacity:.3"), (4.8, "opacity:.3"), (5.6, "opacity:1"), (6.8, "opacity:.45"), (8, "opacity:.3")])
    css += f".sa{{animation-name:sa;animation-duration:{period}s;animation-iteration-count:infinite}}"
    arms = ""
    pts = spiral_points(rng, 96)
    for x, y in pts:
        r = math.hypot(x - CX, y - CY)
        g = "plus" if r > 700 else "outline" if r > 480 else "small"
        g = rng.choice([g, g, "dot"])
        # the wave runs outward along the arms
        arms += use(g, x, y, f"sa sp{int(r / 900 * nb) % nb}")
    body += f"<g>{arms}</g>"
    return piece(css, body), pts

# ---------- level 2: Weather Map ----------
WM_STEP = 76

def wm_cells():
    cells = []
    for y in range(WM_STEP // 2, H, WM_STEP):
        for x in range(WM_STEP // 2, W, WM_STEP):
            # an oval, not the whole screen: the map is the display's round face
            if ((x - CX) / 900) ** 2 + ((y - CY) / 560) ** 2 <= 1:
                cells.append((x, y))
    return cells

def base_weather():
    # each block rests dim and lights as a 3-armed spiral wave passes; the marks by the map's dialect
    nb, period = 40, 8
    css = phase_classes("w", nb, period)
    css += kf("ws", period, [(0, "opacity:.14"), (4.4, "opacity:.14"), (5.2, "opacity:.95"), (6.4, "opacity:.4"), (8, "opacity:.14")])
    css += f".wm{{animation-name:ws;animation-duration:{period}s;animation-iteration-count:infinite}}"
    body = ""
    cells = wm_cells()
    for x, y in cells:
        dx, dy = x - CX, y - CY
        r = math.hypot(dx, dy)
        th = math.atan2(dy, dx)
        ph = ((3 * th + 5.5 * math.log(r + 18)) / math.tau) % 1
        band = 0 if r < 300 else 1 if r < 560 else 2
        g = [["solid", "x"], ["outline", "dotbox"], ["dot", "plus"]][band][((x // WM_STEP) + (y // WM_STEP)) & 1]
        body += use(g, x, y, f"wm w{int(ph * nb) % nb}")
    dcss, dbody = dust(random.Random(4), far=25, mid=0, near=0, pairs=0, tag="e")
    return piece(css + dcss, dbody + body), cells

# ---------- level 3: Glyph Ring ----------
GR_SPOKES, GR_CELLS, GR_R0, GR_R1 = 32, 6, 190, 500
GR_TABLE = [["dot", "plus"], ["outline", "dotbox"], ["solid", "solid"], ["x", "x"]]

def gr_cells():
    cells = []
    for i in range(GR_SPOKES):
        a = (i + 0.5) / GR_SPOKES * math.tau
        for k in range(GR_CELLS):
            r = GR_R0 + k * (GR_R1 - GR_R0) / (GR_CELLS - 1)
            cells.append((i, k, CX + r * math.sin(a), CY - r * math.cos(a) * 0.82))
    return cells

def base_ring():
    # a compact ring, the size of the turntable's face: two arms of light wind round it, slowly.
    # Light goes round, never in and out, so the ring never seems to breathe or zoom.
    nb, period = 50, 10
    css = phase_classes("z", nb, period)
    css += kf("gz", period, [(0, "opacity:.14"), (6, "opacity:.14"), (6.8, "opacity:1"), (8.4, "opacity:.14"), (10, "opacity:.14")])
    css += f".gc{{animation-name:gz;animation-duration:{period}s;animation-iteration-count:infinite}}"
    css += spin_kf("cr", 30) + f".cr{{transform-box:view-box;transform-origin:{CX:.0f}px {CY:.0f}px;animation:cr 30s infinite reverse;animation-delay:var(--o)}}"
    body = ""
    for i, k, x, y in gr_cells():
        g = GR_TABLE[min(3, k * 4 // GR_CELLS)][(i + k) & 1]
        # two arms: the spoke's angle sets the phase, wound a little by depth
        ph = (2 * i / GR_SPOKES - k * 0.04) % 1
        body += use(g, x, y, f"gc z{int(ph * nb) % nb}")
    core = "".join(use("dot" if j & 1 else "small", CX + 110 * math.sin(j / 8 * math.tau), CY + 110 * math.cos(j / 8 * math.tau) * 0.82) for j in range(8))
    dcss, dbody = dust(random.Random(5), far=30, mid=8, near=4, pairs=2, tag="e")
    return piece(css + dcss, dbody + f"<g>{body}</g><g class=\"cr\" opacity=\".8\">{core}</g>"), [(x, y) for *_, x, y in gr_cells()]

# ---------- gathering: a swarm into a pattern ----------
def gather(targets, seed, n=60):
    rng = random.Random(seed)
    picks = rng.sample(targets, min(n, len(targets)))
    body = ""
    for x, y in picks:
        while True:
            sx, sy = rng.uniform(0, W), rng.uniform(0, H)
            if math.hypot(sx - x, sy - y) > 200: break
        body += use(rng.choice(["dot", "small", "dot", "x"]), x, y, "ga",
                    f"--x:{sx - x:.0f}px;--y:{sy - y:.0f}px;animation-delay:calc(var(--e) + {q(rng.uniform(0, .4)):.1f}s)")
    return piece("", body)

GATHER_CSS = (
    kf("ga", 1.8, [(0, "translate:var(--x) var(--y);opacity:.5"), (0.4, "translate:calc(var(--x)*.55) calc(var(--y)*.55);opacity:.8"),
                   (0.9, "translate:calc(var(--x)*.15) calc(var(--y)*.15);opacity:1"), (1.4, "translate:0 0;opacity:1"), (1.8, "translate:0 0;opacity:0")])
    + ".ga{opacity:0;animation:ga 1.8s both}"
    ".gs .ga{animation-direction:reverse}"
    # the pattern arriving fades in as the swarm lands; the one leaving fades out under the scatter
    + kf("fi", 1.2, [(0, "opacity:0"), (1.2, "opacity:1")])
    + ".fi{animation:fi 1.2s both;animation-delay:calc(var(--e) + 1.1s)}"
)

# ---------- subagent formations ----------
AGENT_GLYPHS = ["solid", "dotbox", "plus", "outline", "x", "small"]
AGENT_COLORS = [MINT, COBALT, PAPER, MINT, COBALT, PAPER]
AGENT_LAP = 120

def squircle(a, b, u, n=4):
    c, s = math.cos(u), math.sin(u)
    return CX + a * math.copysign(abs(c) ** (2 / n), c), CY + b * math.copysign(abs(s) ** (2 / n), s)

def path_kf(name, lap, a, b, pts, sign=1, offset=0.0):
    frames = [(k * lap / pts, "translate:{:.0f}px {:.0f}px".format(*squircle(a, b, sign * k / pts * math.tau + offset))) for k in range(pts + 1)]
    return kf(name, lap, frames)

def agents():
    shared = (
        path_kf("am", AGENT_LAP, 800, 480, 60, -1, 0.4) + f".am{{animation:am {AGENT_LAP}s infinite}}"
        + spin_kf("ar", 20) + ".ar{transform-box:view-box;transform-origin:0 0;animation:ar 20s infinite}"
        + kf("ao", 3, [(0, "opacity:.25"), (1.8, "opacity:.25"), (2.2, "opacity:1"), (3, "opacity:.25")])
        + ".c0,.c1{animation:ao 3s infinite}"
        + f".c0{{animation-delay:{lp(0)}}}.c1{{animation-delay:{lp(.4)}}}"
    )
    out = []
    for k in range(6):
        g, col = AGENT_GLYPHS[k], AGENT_COLORS[k]
        spokes = ""
        for j in range(8):
            a = j / 8 * math.tau
            for c in range(2):
                r = 18 + c * 14
                spokes += use(g if c == 0 else "x", math.cos(a) * r, math.sin(a) * r, f"c{c}")
        body = (
            f'<g class="am" style="fill:var(--k{k % 3},{col});animation-delay:{lp(k / 6 * AGENT_LAP)}">'
            f'<g class="ar" style="animation-delay:{lp(k * 3)}">{spokes}</g>{use("dotbox")}</g>'
        )
        out.append(piece(shared if k == 0 else "", body))
    return out

# ---------- overlays ----------
def overlay_scan():
    # reading: a row of glyphs stepping down the sides, like the display's own refresh line
    css = kf("sl", 8, [(0, "translate:0 -40px"), (8, f"translate:0 {H + 40}px")]) + ".sl{animation:sl 8s infinite;animation-delay:var(--o)}"
    body = '<g class="sl">'
    rng = random.Random(41)
    for x in range(20, W, 30):
        if abs(x - CX) < 600 or rng.random() < 0.35: continue
        body += use(rng.choice(["dot", "small", "x", "plus"]), x, 0)
    return piece(css, body + "</g>")

def overlay_write():
    # editing: a row of glyphs along the top and bottom; a stamp runs along them, each mark
    # flashing and turning a quarter as it passes
    nb, period = 24, 2.4
    css = phase_classes("y", nb, period)
    css += kf("yw", period, [(0, "opacity:.15;rotate:0deg"), (1.6, "opacity:.15;rotate:0deg"), (1.7, "opacity:1;rotate:90deg"),
                             (2.1, "opacity:.5;rotate:90deg"), (2.4, "opacity:.15;rotate:90deg")])
    css += f".yw{{animation-name:yw;animation-duration:{period}s;animation-iteration-count:infinite}}"
    body = ""
    for row, y in enumerate([30, H - 30]):
        for x in range(24, W, 48):
            ph = (x / W) % 1
            g = ["outline", "dotbox", "solid", "plus"][(x // 48 + row) % 4]
            body += use(g, x, y, f"yw y{int(ph * nb) % nb}")
    return piece(css, body)

def overlay_run():
    # running: chase lights round the edge, each step one glyph along, like a marquee
    lap, pts = 12, 60
    css = path_kf("rm", lap, 915, 560, pts) + f".rm{{animation:rm {lap}s infinite}}"
    body = ""
    for train in range(2):
        for i in range(10):
            d = train * lap / 2 + i * 0.2
            op = max(0.15, 1 - i / 10)
            g = "solid" if i == 0 else ["x", "plus", "small"][i % 3]
            body += f'<g class="rm" opacity="{op:.2f}" style="animation-delay:{lp(-d)}">{use(g)}</g>'
    return piece(css, body)

def overlay_error():
    rng = random.Random(16)
    burst = ""
    for _ in range(50):
        a = rng.uniform(0, math.tau)
        r0 = rng.uniform(380, 760)
        x, y = CX + math.cos(a) * r0, CY + math.sin(a) * r0 * 0.7
        dx, dy = math.cos(a) * rng.uniform(80, 220), math.sin(a) * rng.uniform(60, 160)
        burst += use(rng.choice(["x", "x", "solid", "plus", "small"]), x, y, "eb", f"--x:{dx:.0f}px;--y:{dy:.0f}px", EMBER)
    css = (
        kf("ex", 2.8, [(0, "opacity:0;translate:0 0"), (0.2, "opacity:1;translate:0 0"), (1.5, "opacity:.85;translate:0 0"),
                       (2.8, "opacity:0;translate:var(--x) var(--y)")])
        + "@keyframes jt{0%,100%{rotate:0deg}50%{rotate:90deg}}"
        ".eb{opacity:0;animation:ex 2.8s both,jt .4s steps(1) 4;animation-delay:var(--e),var(--e)}"
    )
    return piece(css, burst)

def overlay_done():
    rng = random.Random(11)
    cells = ""
    for i in range(48):
        a = i / 48 * math.tau
        cells += use(rng.choice(["dot", "small", "x", "plus"]), CX, CY, "rp", f"--x:{math.cos(a) * 1000:.0f}px;--y:{math.sin(a) * 640:.0f}px")
    css = (
        kf("rp", 2.6, [(0, "translate:0 0;opacity:0"), (0.2, "translate:calc(var(--x)*.1) calc(var(--y)*.1);opacity:.9"),
                       (2.6, "translate:var(--x) var(--y);opacity:0")])
        + ".rp{opacity:0;animation:rp 2.6s both;animation-delay:calc(var(--e) + .1s)}"
    )
    return piece(css, cells)

# ---------- write ----------
b0 = base_dust()
b1, t1 = base_gather()
b2, t2 = base_weather()
b3, t3 = base_ring()
BASE = [b0, b1, b2, b3]
GATHER = [piece("", ""), gather(t1, 21), gather(t2, 22), gather(t3, 23)]
AGENTS = agents()
OVERLAY = {
    "none": piece("", ""), "scan": overlay_scan(), "write": overlay_write(), "run": overlay_run(),
    "error": overlay_error(), "done": overlay_done(),
}

size = lambda p: len(p["css"]) + len(p["body"])
glyphs = lambda p: p["body"].count("<use")
worst = max(size(b) for b in BASE) + max(size(g) for g in GATHER) + sum(size(p) for p in AGENTS) + max(size(p) for p in OVERLAY.values()) \
    + len(BASE_CSS) + len(DEFS) + len(GATHER_CSS) + 600
for i, p in enumerate(BASE): print(f"base {i}: {size(p)} chars, {glyphs(p)} glyphs")
for i, p in enumerate(GATHER): print(f"gather {i}: {glyphs(p)} glyphs")
for k, p in OVERLAY.items(): print(f"overlay {k}: {glyphs(p)} glyphs")
print(f"agents (all 6): {sum(glyphs(p) for p in AGENTS)} glyphs")
print(f"largest whole scene: {worst} of 131072")
assert worst < 131072

js = lambda v: json.dumps(v, separators=(",", ":"))
out = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "scenes.ts"
out.write_text(
    "// Generated by tools/gen_scene.py: edit that, not this.\n"
    "import type { Overlay } from '../types'\n\n"
    "export type Piece = { css: string; body: string }\n\n"
    f"export const W = {W}\nexport const H = {H}\nexport const CYCLE = {T}\n"
    f"export const BASE_CSS = {js(BASE_CSS + GATHER_CSS)}\n"
    f"export const DEFS = {js(DEFS)}\n"
    f"export const BASE: Piece[] = {js(BASE)}\n"
    f"export const GATHER: Piece[] = {js(GATHER)}\n"
    f"export const AGENTS: Piece[] = {js(AGENTS)}\n"
    f"export const OVERLAY: Record<Overlay, Piece> = {js(OVERLAY)}\n"
)
