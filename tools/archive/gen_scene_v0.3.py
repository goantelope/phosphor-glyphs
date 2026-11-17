#!/usr/bin/env python3
"""Writes hooks/scenes.ts: the pieces the backdrop is put together from at run time.

The glyphs are the turntable display's (home_automation/firmware/common/include/glyphs.h): dot,
small, outline, solid, dot-box, plus and x, every stroke 2 px, drawn at about 10 px. All are
four-fold symmetric, so a quarter turn returns a glyph to itself.

The field is dust in space when the session is idle, and the more work is happening the more of
it gathers into the patterns of the turntable's glyph visualizers (firmware/turntable-display,
main.cpp: Weather Map and Glyph Ring):

  BASE[0]  dust: three depths of glyphs drifting and slowly wheeling at different speeds
  BASE[1]  gathering: part of the dust drawn into turning spiral arms, the rest still drifting
  BASE[2]  Weather Map: a fixed grid of blocks, a spiral and rings travelling through it, each
           block growing dot > square > outline > solid as the wave passes, by the map's dialect
  BASE[3]  Glyph Ring: 40 mirrored spokes of 10 cells pumping like a spectrum, peaks held as a
           cross, the table of marks by depth, the ring slowly turning, eight marks at its core
  GATHER[L]  a swarm flying from scattered dust into level L's pattern (reversed: scattering)
  AGENTS[k]  one formation per running subagent: a small turning ring travelling the edge
  OVERLAY    the event of the moment: scan line, bars, ember burst, ripple

Looping animations share one 40 s cycle and start at `--o`, a negative delay set from the clock;
one-shots start at `--e`, minus the time since their event. So a redraw never restarts anything.

Run: python3 tools/gen_scene.py   (from the mod folder)
"""
import math, random, pathlib, json

N, S = 12, 0.8
W, H = 1920, 1200
CX, CY = W / 2, H / 2
T = 40
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

BASE_CSS = (
    f"svg{{fill:{AMBER}}}use{{transform-box:fill-box;transform-origin:center}}"
    f".rot{{transform-box:view-box;transform-origin:{CX:.0f}px {CY:.0f}px}}"
    "@keyframes spin{to{rotate:360deg}}"
    "@media (prefers-reduced-motion:reduce){*{animation-play-state:paused!important}}"
)

def use(g, x=0, y=0, cls="", style="", fill=""):
    c = f' class="{cls}"' if cls else ""
    s = f' style="{style}"' if style else ""
    f = f' fill="{fill}"' if fill else ""
    xy = f' x="{x:.0f}" y="{y:.0f}"' if (x or y) else ""
    return f'<use href="#{ID[g]}"{xy}{c}{s}{f}/>'

def lp(sec):
    """a looping animation's delay on the shared clock"""
    return f"calc(var(--o) - {sec % T:.2f}s)"

def piece(css, body):
    return {"css": css, "body": body}

def spin(cls, period, reverse=False):
    return f".{cls}{{animation:spin {period}s linear infinite{' reverse' if reverse else ''};animation-delay:var(--o)}}"

# ---------- dust ----------
DEPTHS = [  # count, glyphs, opacity, wander size, wheel period (a divisor of the cycle or a multiple)
    (90, ["dot"], 0.32, 18, 400, False),
    (60, ["dot", "dot", "small"], 0.55, 32, 200, True),
    (30, ["small", "outline", "plus", "x"], 0.85, 55, 120, False),
]

def dust(rng, scale=1.0, tag="d"):
    css, body = "", ""
    # wanders: small closed loops, each particle on one with its own phase; twinkles
    for k in range(4):
        pts = []
        for j in range(9):
            a = j / 8 * math.tau
            r = 1 + 0.35 * math.sin(3 * a + k)
            pts.append((math.cos(a) * r * (1 if k % 2 else -1), math.sin(a) * r * (0.6 + 0.2 * k)))
        frames = "".join(f"{j / 8 * 100:.1f}%{{translate:calc({x:.2f}*var(--r)) calc({y:.2f}*var(--r))}}" for j, (x, y) in enumerate(pts))
        css += f"@keyframes {tag}w{k}{{{frames}}}"
    css += f"@keyframes {tag}t{{0%,100%{{opacity:.25}}50%{{opacity:1}}}}"
    for di, (count, glyphs, op, wander, wheel, rev) in enumerate(DEPTHS):
        n = int(count * scale)
        grp = ""
        for i in range(n):
            # spread over a disc a little larger than the window, so a turn never shows an empty corner
            while True:
                x, y = rng.uniform(-200, W + 200), rng.uniform(-350, H + 350)
                if math.hypot(x - CX, y - CY) < 1180: break
            k = rng.randrange(4)
            dur = rng.choice([20, 40])
            tw = rng.choice([4, 5, 8, 10])
            grp += use(rng.choice(glyphs), x, y, f"{tag}{di} {tag}k{k}",
                       f"--r:{wander * rng.uniform(.6, 1.4):.0f}px;animation-delay:{lp(rng.uniform(0, T))},{lp(rng.uniform(0, T))};animation-duration:{dur}s,{tw}s")
        css += f".{tag}{di}{{animation-timing-function:ease-in-out;animation-iteration-count:infinite}}"
        css += spin(f"{tag}r{di}", wheel, rev)
        body += f'<g class="rot {tag}r{di}" opacity="{op}">{grp}</g>'
    css += "".join(f".{tag}k{k}{{animation-name:{tag}w{k},{tag}t}}" for k in range(4))
    return css, body

def base_dust():
    css, body = dust(random.Random(1))
    return piece(css, body)

# ---------- level 1: gathering into spiral arms ----------
def spiral_points(rng, n, arms=3, r0=300, r1=1100, wind=0.0034, jitter=26):
    out = []
    for i in range(n):
        arm = i % arms
        r = r0 + (r1 - r0) * (rng.random() ** 0.8)
        a = arm / arms * math.tau + (r - r0) * wind + rng.gauss(0, 0.05)
        out.append((CX + math.cos(a) * r + rng.gauss(0, jitter), CY + math.sin(a) * r * 0.85 + rng.gauss(0, jitter)))
    return out

def base_gather():
    rng = random.Random(2)
    css, body = dust(rng, scale=0.55)
    arms = ""
    pts = spiral_points(rng, 170)
    for i, (x, y) in enumerate(pts):
        r = math.hypot(x - CX, y - CY)
        g = "plus" if r > 850 else "outline" if r > 600 else "small"
        g = rng.choice([g, g, "dot"])
        arms += use(g, x, y, "sa", f"animation-delay:{lp(r / 1100 * 6)}")
    css += "@keyframes sa{0%,100%{opacity:.35;scale:.8}20%{opacity:1;scale:1.25}}"
    css += ".sa{animation:sa 6s ease-in-out infinite}"
    css += spin("sr", 80)
    body += f'<g class="rot sr">{arms}</g>'
    return piece(css, body), pts

# ---------- level 2: Weather Map ----------
WM_STEP = 44

def wm_cells():
    cells = []
    for y in range(WM_STEP // 2, H, WM_STEP):
        for x in range(WM_STEP // 2, W, WM_STEP):
            cells.append((x, y))
    return cells

def base_weather():
    # each block carries two waves: a 3-armed spiral (its opacity, the block lighting) and rings
    # (its size, the block growing dot > solid). Delays, in classes, are the waves' phases.
    css, body = "", ""
    SP, RG = 6.0, 4.0     # spiral and ring periods, divisors of the cycle... 40/6 is not: ok, they run off --o
    nb = 24
    for b in range(nb):
        css += f".s{b}{{--a:{-b / nb * SP:.2f}s}}.q{b}{{--b:{-b / nb * RG:.2f}s}}"
    css += (
        "@keyframes ws{0%,100%{opacity:.12}35%{opacity:.95}60%{opacity:.4}}"
        "@keyframes wr{0%,100%{scale:.35}30%{scale:1.15}55%{scale:.8}}"
        f".wm{{animation:ws {SP}s ease-in-out infinite,wr {RG}s ease-in-out infinite;"
        "animation-delay:calc(var(--o) + var(--a)),calc(var(--o) + var(--b))}"
    )
    rng = random.Random(3)
    cells = wm_cells()
    for x, y in cells:
        dx, dy = x - CX, y - CY * 1.0
        r = math.hypot(dx, dy)
        th = math.atan2(dy, dx)
        ph_s = ((3 * th + 5.5 * math.log(r + 18)) / math.tau) % 1
        ph_r = (r / 260) % 1
        # the dialect by distance: solids and crosses at the core, boxes between, dots and pluses out
        band = 0 if r < 420 else 1 if r < 760 else 2
        g = [["solid", "x"], ["outline", "dotbox"], ["dot", "plus"]][band][((x // WM_STEP) + (y // WM_STEP)) & 1]
        body += use(g, x, y, f"wm s{int(ph_s * nb) % nb} q{int(ph_r * nb) % nb}")
    return piece(css, body), cells

# ---------- level 3: Glyph Ring ----------
GR_HALF, GR_CELLS, GR_R0, GR_R1 = 20, 10, 330, 1060
GR_TABLE = [["dot", "plus"], ["outline", "dotbox"], ["solid", "solid"], ["x", "x"]]

def gr_class(k):
    return 0 if k <= 2 else 1 if k <= 5 else 2 if k <= 7 else 3

def gr_cells():
    cells = []
    for i in range(GR_HALF):
        for side in (0, 1):
            a = (1 if side else -1) * (i + 0.5) / (GR_HALF * 2) * math.tau
            for k in range(GR_CELLS):
                r = GR_R0 + k * (GR_R1 - GR_R0) / (GR_CELLS - 1)
                cells.append((i, side, k, CX + r * math.sin(a), CY + r * math.cos(a) * 0.82))
    return cells

def base_ring():
    # a pinwheel of glyphs, not a meter: waves pop outward along the spokes, offset spoke by
    # spoke so they wind into turning arms, and the marks by depth come from the ring's table
    nb = 20
    css = "".join(f".z{b}{{animation-delay:{lp(b / nb * 2.5)}}}" for b in range(nb))
    css += (
        "@keyframes gz{0%,100%{opacity:.12;scale:.5}18%{opacity:1;scale:1.3}40%{opacity:.45;scale:1}}"
        ".gc{animation:gz 2.5s ease-in-out infinite}"
        + spin("grs", 160)
        + spin("grc", 20, True)
    )
    body = ""
    for i, side, k, x, y in gr_cells():
        g = GR_TABLE[gr_class(k)][(i + k) & 1]
        # the phase: outward along a spoke, and wound by the spoke's angle (mirrored halves meet)
        ph = (k / GR_CELLS * 0.8 + i / GR_HALF * 1.5) % 1
        body += use(g, x, y, f"gc z{int(ph * nb) % nb}")
    core = "".join(use("dot" if j & 1 else "small", CX + 120 * math.sin(j / 8 * math.tau), CY + 120 * math.cos(j / 8 * math.tau)) for j in range(8))
    # a little dust stays, far back
    dcss, dbody = dust(random.Random(5), scale=0.3, tag="e")
    return piece(css + dcss, dbody + f'<g class="rot grs">{body}</g><g class="rot grc" opacity=".8">{core}</g>'), [(x, y) for *_, x, y in gr_cells()]

# ---------- gathering: a swarm into a pattern ----------
def gather(targets, seed, n=150):
    rng = random.Random(seed)
    picks = rng.sample(targets, min(n, len(targets)))
    body = ""
    for x, y in picks:
        while True:
            sx, sy = rng.uniform(0, W), rng.uniform(0, H)
            if math.hypot(sx - x, sy - y) > 200: break
        body += use(rng.choice(["dot", "small", "dot", "x"]), x, y, "ga",
                    f"--x:{sx - x:.0f}px;--y:{sy - y:.0f}px;animation-delay:calc(var(--e) + {rng.uniform(0, .35):.2f}s)")
    return piece("", body)

GATHER_CSS = (
    "@keyframes ga{0%{translate:var(--x) var(--y);opacity:.5;scale:.6}70%{opacity:1;scale:1.3}"
    "85%{translate:0 0;opacity:1;scale:1}100%{translate:0 0;opacity:0}}"
    ".ga{opacity:0;animation:ga 1.8s cubic-bezier(.5,0,.2,1) both}"
    ".gs .ga{animation-direction:reverse}"
    # the pattern arriving fades in as the swarm lands; the one leaving fades out under the scatter
    "@keyframes fi{from{opacity:0}to{opacity:1}}"
    ".fi{animation:fi 1.2s ease-in 1.1s both;animation-delay:calc(var(--e) + 1.1s)}"
)

# ---------- subagent formations ----------
AGENT_GLYPHS = ["solid", "dotbox", "plus", "outline", "x", "small"]
AGENT_COLORS = [MINT, COBALT, PAPER, MINT, COBALT, PAPER]

def squircle(a, b, u, n=4):
    c, s = math.cos(u), math.sin(u)
    return CX + a * math.copysign(abs(c) ** (2 / n), c), CY + b * math.copysign(abs(s) ** (2 / n), s)

def agents():
    pts = 72
    frames = "".join(
        f"{k / pts * 100:.2f}%{{translate:{x:.0f}px {y:.0f}px}}"
        for k in range(pts + 1) for x, y in [squircle(800, 480, -k / pts * math.tau + 0.4)]
    )
    shared = (
        f"@keyframes am{{{frames}}}.am{{animation:am 40s linear infinite}}"
        ".ar{transform-box:view-box;transform-origin:0 0;animation:spin 5s linear infinite}"
        ".ar2{transform-box:view-box;transform-origin:0 0;animation:spin 10s linear infinite reverse}"
        "@keyframes ap{0%,100%{scale:1}50%{scale:1.6}}.ap{animation:ap 1.25s ease-in-out infinite}"
        "@keyframes ao{0%,100%{opacity:.2;scale:.7}30%{opacity:1;scale:1.2}}"
        ".c0,.c1,.c2{animation:ao 1.5s ease-in-out infinite}"
        f".c0{{animation-delay:{lp(0)}}}.c1{{animation-delay:{lp(.25)}}}.c2{{animation-delay:{lp(.5)}}}"
    )
    out = []
    for k in range(6):
        g, col = AGENT_GLYPHS[k], AGENT_COLORS[k]
        # a little ring of its own: 8 spokes of 3 cells, a ripple running outward
        spokes = ""
        for j in range(8):
            a = j / 8 * math.tau
            for c in range(3):
                r = 18 + c * 12
                spokes += use(g if c < 2 else "x", math.cos(a) * r, math.sin(a) * r, f"c{c}")
        core = use("dotbox", cls="ap", style=f"animation-delay:{lp(k * 0.2)}")
        body = (
            f'<g class="am" fill="{col}" style="animation-delay:{lp(k / 6 * 40)}">'
            f'<g class="ar" style="animation-delay:{lp(k)}">{spokes}</g>{core}</g>'
        )
        out.append(piece(shared if k == 0 else "", body))
    return out

# ---------- overlays ----------
def overlay_scan():
    # reading: a row of glyphs sweeping down the sides, each turning as it goes
    css = (
        f"@keyframes sl{{from{{translate:0 -40px}}to{{translate:0 {H + 40}px}}}}.sl{{animation:sl 4s linear infinite;animation-delay:var(--o)}}"
        "@keyframes st{0%,100%{rotate:0deg;opacity:.5}50%{rotate:90deg;opacity:1}}.st{animation:st .8s ease-in-out infinite}"
    )
    body = '<g class="sl">'
    rng = random.Random(41)
    for x in range(20, W, 22):
        if abs(x - CX) < 560 or rng.random() < 0.35: continue
        body += use(rng.choice(["dot", "small", "x", "plus"]), x, 0, "st", f"animation-delay:{lp(x / W * 0.8)}")
        if rng.random() < 0.5:
            body += f'<g opacity=".35">{use("dot", x, -16)}</g>'
    return piece(css, body + "</g>")

def overlay_write():
    # editing: rows of glyphs along the top and bottom; a stamping wave runs along them,
    # each mark popping and stepping to its next shape as the wave passes, like a dialect change
    nb = 24
    css = "".join(f".y{b}{{animation-delay:{lp(b / nb * 2.4)}}}" for b in range(nb))
    css += (
        "@keyframes yw{0%,100%{opacity:.15;scale:.7;rotate:0deg}10%{opacity:1;scale:1.6;rotate:90deg}30%{opacity:.5;scale:1;rotate:90deg}}"
        ".yw{animation:yw 2.4s ease-out infinite}"
    )
    body = ""
    rng = random.Random(42)
    for row, y in enumerate([28, 52, H - 52, H - 28]):
        for x in range(16, W, 26):
            ph = (x / W + row * 0.13) % 1
            g = ["outline", "dotbox", "solid", "plus"][(x // 26 + row) % 4]
            body += use(g, x, y, f"yw y{int(ph * nb) % nb}")
    return piece(css, body)

def overlay_run():
    # running: a train of glyphs racing round the edge, spinning, a bright head and a fading tail
    pts = 72
    frames = "".join(
        f"{k / pts * 100:.2f}%{{translate:{x:.0f}px {y:.0f}px}}"
        for k in range(pts + 1) for x, y in [squircle(915, 560, k / pts * math.tau)]
    )
    css = (
        f"@keyframes rm{{{frames}}}"
        ".rm{animation:rm 8s linear infinite}"
        "@keyframes rs{to{rotate:90deg}}.rs{animation:rs .5s linear infinite}"
    )
    body = ""
    for train in range(3):
        for i in range(26):
            d = train * 8 / 3 + i * 0.07
            op = max(0.12, 1 - i / 26)
            g = "solid" if i == 0 else ["x", "plus", "small"][i % 3]
            body += f'<g class="rm" opacity="{op:.2f}" style="animation-delay:{lp(-d)}">{use(g, cls="rs")}</g>'
    return piece(css, body)

def overlay_error():
    rng = random.Random(16)
    burst = ""
    for _ in range(110):
        a = rng.uniform(0, math.tau)
        r0 = rng.uniform(420, 900)
        x, y = CX + math.cos(a) * r0, CY + math.sin(a) * r0 * 0.7
        dx, dy = math.cos(a) * rng.uniform(80, 260), math.sin(a) * rng.uniform(60, 200)
        burst += use(rng.choice(["x", "x", "solid", "plus", "small"]), x, y, "eb", f"--x:{dx:.0f}px;--y:{dy:.0f}px", EMBER)
    css = (
        "@keyframes ex{0%{opacity:0;translate:0 0;scale:1.6}6%{opacity:1}55%{opacity:.85;translate:0 0;scale:1}"
        "100%{opacity:0;translate:var(--x) var(--y);scale:.4}}"
        "@keyframes jt{0%,100%{rotate:0deg}50%{rotate:90deg}}"
        ".eb{opacity:0;animation:ex 2.8s ease-in 1 both,jt .2s steps(1) 14;animation-delay:var(--e),var(--e)}"
    )
    return piece(css, burst)

def overlay_done():
    rng = random.Random(11)
    cells = ""
    for i in range(96):
        a = i / 96 * math.tau
        cells += use(rng.choice(["dot", "small", "x", "plus"]), CX, CY, "rp", f"--x:{math.cos(a) * 1150:.0f}px;--y:{math.sin(a) * 780:.0f}px")
    css = (
        "@keyframes rp{0%{translate:0 0;scale:.4;opacity:0}8%{opacity:.95}100%{translate:var(--x) var(--y);scale:1.4;opacity:0}}"
        ".rp{opacity:0;animation:rp 2.6s cubic-bezier(.2,.6,.3,1) both;animation-delay:calc(var(--e) + .1s)}"
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
# the largest scene: a base, a swarm, every agent, an overlay
worst = max(size(b) for b in BASE) + max(size(g) for g in GATHER) + sum(size(p) for p in AGENTS) + max(size(p) for p in OVERLAY.values()) \
    + len(BASE_CSS) + len(DEFS) + len(GATHER_CSS) + 600
for i, p in enumerate(BASE): print(f"base {i}: {size(p)}")
for i, p in enumerate(GATHER): print(f"gather {i}: {size(p)}")
for k, p in OVERLAY.items(): print(f"overlay {k}: {size(p)}")
print(f"agents (all 6): {sum(size(p) for p in AGENTS)}")
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
