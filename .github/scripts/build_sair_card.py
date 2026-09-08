# ==============================================================================
# File: build_sair_card.py
# Description: Builds the repository card in the visual language of the SAIR
#   Foundation's own hero art for the ACC Challenge: a flat burgundy ground and
#   white line work, read left to right. A tangled balanced presentation goes
#   in, a search steps through move sequences, and the standard presentation
#   (x, y) comes out verified. This competition's artwork is flat rather than
#   the gradient the three older challenges use, so the card follows it.
#   Every element declares a box and the build refuses to render if any two
#   intersect.
# Usage: python .github/scripts/build_sair_card.py .github/assets
# Tech Stack: Python 3.10+, Pillow
# ==============================================================================

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 675
SS = 3
FRAMES, DURATION = 36, 55

GROUND = (0x3B, 0x0E, 0x27)     # the SAIR burgundy, 20 uses in the site's CSS
INK = (255, 255, 255)
STROKE = 4

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
UIB = "C:/Windows/Fonts/segoeuib.ttf"
MATH, MATH_IDX = "C:/Windows/Fonts/cambria.ttc", 1

# -- layout -----------------------------------------------------------------
# The composition steps downward as it moves right, the way the artwork does:
# the presentation on the left sits high, the trivialised pair on the right
# sits low, and the search descends between them.

LOGO = (56, 40, 296, 92)
LEFT = (84, 122, 274, 312)          # the tangled presentation
RIGHT = (884, 322, 1074, 512)       # the pair (x, y)
LANE = (304, 122, 854, 512)         # where the search runs
TICK_C, TICK_R = (979, 566), 27
CAP_Y = 612                         # the caption under the lane

BOXES = {
    "logo": LOGO,
    "presentation": LEFT,
    "search": LANE,
    "trivialised": RIGHT,
    "verified": (TICK_C[0] - TICK_R, TICK_C[1] - TICK_R,
                 TICK_C[0] + TICK_R, TICK_C[1] + TICK_R),
}


def assert_no_overlap():
    names = list(BOXES)
    bad = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = BOXES[names[i]], BOXES[names[j]]
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > 0 and oy > 0:
                bad.append(f"{names[i]}/{names[j]} by {ox:.0f}x{oy:.0f}")
    if bad:
        raise SystemExit("layout collision: " + "; ".join(bad))


_scratch = ImageDraw.Draw(Image.new("RGB", (8, 8)))
OFFSET = [0.0, 0.0]


def f(path, size, index=0):
    return ImageFont.truetype(path, max(1, int(round(size * SS))), index=index)


def fit_width(path, text, target, index=0):
    lo, hi = 4.0, 300.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _scratch.textlength(text, font=f(path, mid, index)) / SS < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def dim(amount):
    """White faded toward the ground, so a mark can recede without alpha."""
    return tuple(round(GROUND[i] + (INK[i] - GROUND[i]) * amount)
                 for i in range(3))


def ease(t):
    return t * t * (3 - 2 * t)


class Pen:
    def __init__(self, draw):
        self.d = draw

    def _p(self, pts):
        ox, oy = OFFSET
        return [((p[0] + ox) * SS, (p[1] + oy) * SS) for p in pts]

    def line(self, pts, colour=INK, width=STROKE, joint="curve"):
        if len(pts) < 2:
            return
        self.d.line(self._p(pts), fill=colour, width=int(round(width * SS)),
                    joint=joint)

    def rrect(self, box, r, colour=INK, width=STROKE):
        ox, oy = OFFSET
        self.d.rounded_rectangle(
            [(box[0] + ox) * SS, (box[1] + oy) * SS,
             (box[2] + ox) * SS, (box[3] + oy) * SS],
            radius=r * SS, outline=colour, width=int(round(width * SS)))

    def circle(self, cx, cy, r, colour=INK, width=STROKE):
        ox, oy = OFFSET
        self.d.ellipse([(cx + ox - r) * SS, (cy + oy - r) * SS,
                        (cx + ox + r) * SS, (cy + oy + r) * SS],
                       outline=colour, width=int(round(width * SS)))

    def disc(self, cx, cy, r, colour=INK):
        ox, oy = OFFSET
        self.d.ellipse([(cx + ox - r) * SS, (cy + oy - r) * SS,
                        (cx + ox + r) * SS, (cy + oy + r) * SS], fill=colour)

    def square(self, cx, cy, half, colour=INK, width=3):
        ox, oy = OFFSET
        self.d.rectangle([(cx + ox - half) * SS, (cy + oy - half) * SS,
                          (cx + ox + half) * SS, (cy + oy + half) * SS],
                         outline=colour, width=int(round(width * SS)))

    def filled_square(self, cx, cy, half, colour=INK):
        ox, oy = OFFSET
        self.d.rectangle([(cx + ox - half) * SS, (cy + oy - half) * SS,
                          (cx + ox + half) * SS, (cy + oy + half) * SS],
                         fill=colour)

    def dashes(self, pts, dash, gap, phase, colour, width=3):
        """A dashed polyline, phase shifted so a route can march."""
        segs = []
        for a, b in zip(pts, pts[1:]):
            length = math.dist(a, b)
            if length < 1e-9:
                continue
            segs.append((a, b, length))
        total = sum(s[2] for s in segs)
        pos = -((phase) % (dash + gap))
        while pos < total:
            self._stroke_between(segs, max(pos, 0.0),
                                 min(pos + dash, total), colour, width)
            pos += dash + gap

    def _stroke_between(self, segs, start, end, colour, width):
        if end <= start:
            return
        walked = 0.0
        for a, b, length in segs:
            s0, s1 = walked, walked + length
            walked = s1
            if s1 <= start or s0 >= end:
                continue
            u0 = max(0.0, (start - s0) / length)
            u1 = min(1.0, (end - s0) / length)
            p = (a[0] + (b[0] - a[0]) * u0, a[1] + (b[1] - a[1]) * u0)
            q = (a[0] + (b[0] - a[0]) * u1, a[1] + (b[1] - a[1]) * u1)
            self.line([p, q], colour, width, None)

    def along(self, pts, progress, colour=INK, width=STROKE):
        """Draw the first `progress` of a polyline by arc length."""
        segs = [(a, b, math.dist(a, b)) for a, b in zip(pts, pts[1:])]
        total = sum(s[2] for s in segs) or 1.0
        self._stroke_between(segs, 0.0, total * progress, colour, width)

    def text(self, pos, s, font, colour=INK, anchor="la"):
        ox, oy = OFFSET
        self.d.text(((pos[0] + ox) * SS, (pos[1] + oy) * SS), s, font=font,
                    fill=colour, anchor=anchor)


# -- the artwork ------------------------------------------------------------

def lissajous(box, n=220, phase=0.0):
    """A Lissajous figure, which self crosses the way a tangled relator does.

    Not decoration: a closed curve of this shape is the standard planar
    picture of a knotted word, and it is what the challenge's own artwork puts
    in this panel."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    a, b = (x1 - x0) * 0.33, (y1 - y0) * 0.33
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        pts.append((cx + a * math.sin(3 * t + phase),
                    cy + b * math.sin(2 * t + 0.9)))
    return pts


def presentation_panel(pen, t):
    """The hard presentation: two tangled relators in a balanced pair."""
    pen.rrect(LEFT, 26)
    curve = lissajous(LEFT)
    pen.line(curve, dim(0.55), 3, "curve")
    # a bright arc travels the curve, the way a word is read letter by letter
    head = (t * 1.0) % 1.0
    span = 0.22
    n = len(curve)
    lo, hi = int(head * n), int((head + span) * n)
    seg = (curve + curve)[lo:hi + 1]
    pen.line(seg, INK, 4, "curve")
    for k in range(4):
        u = (k / 4 + 0.125) % 1.0
        px, py = curve[int(u * (n - 1))]
        glow = 0.5 + 0.5 * math.sin(2 * math.pi * (t - k * 0.12))
        pen.disc(px, py, 6, dim(0.6 + 0.4 * glow))


STEPS = [(304, 217), (414, 217), (414, 267), (524, 267), (524, 317),
         (634, 317), (634, 367), (744, 367), (744, 417), (854, 417)]
CORNERS = [(414, 217), (524, 267), (634, 317), (744, 367)]
ROUTES = [
    [(320, 178), (470, 178), (470, 140), (700, 140), (700, 198), (836, 198)],
    [(320, 258), (392, 258), (392, 332), (590, 332), (590, 248), (836, 248)],
    [(330, 430), (480, 430), (480, 482), (700, 482), (700, 420), (836, 420)],
    [(340, 300), (340, 382), (560, 382), (560, 444), (820, 444)],
]


def search_lane(pen, t):
    """The routes a search considers, and the one it commits to.

    The dashed lattice is the rest of the tree. The solid staircase is the
    sequence that gets submitted, and it is the only one with an arrow."""
    for k, route in enumerate(ROUTES):
        shimmer = 0.28 + 0.22 * (0.5 + 0.5 * math.sin(2 * math.pi * (t - k * 0.17)))
        pen.dashes(route, 13, 9, t * 44 + k * 7, dim(shimmer), 3)

    progress = span_(t, 0.10, 0.72) - span_(t, 0.93, 1.0)
    pen.line(STEPS, dim(0.30), 3)
    if progress > 0.001:
        pen.along(STEPS, progress, INK, STROKE)

    # how far along the committed path the head has reached
    walked = progress * sum(math.dist(a, b) for a, b in zip(STEPS, STEPS[1:]))
    run = 0.0
    for i, (cx, cy) in enumerate(CORNERS):
        upto = 0.0
        for a, b in zip(STEPS, STEPS[1:]):
            upto += math.dist(a, b)
            if (b[0], b[1]) == (cx, cy) or (a[0], a[1]) == (cx, cy):
                break
        run = upto
        lit = walked >= run - 4
        pen.filled_square(cx, cy, 6, INK) if lit else pen.square(cx, cy, 6, dim(0.45), 3)

    if progress > 0.985:
        tipx, tipy = STEPS[-1]
        pen.line([(tipx - 22, tipy - 13), (tipx + 4, tipy),
                  (tipx - 22, tipy + 13)], INK)


def trivialised_panel(pen, t):
    """The standard presentation: the ordered pair (x, y), one relator each."""
    pen.rrect(RIGHT, 26)
    x0, y0, x1, y1 = RIGHT
    cy = (y0 + y1) / 2
    arrived = span_(t, 0.66, 0.78) - span_(t, 0.93, 1.0)
    for k, yy in enumerate((cy - 30, cy + 30)):
        a, b = x0 + 34, x1 - 34
        pen.line([(a, yy), (b, yy)], dim(0.55 + 0.45 * arrived))
        for px in (a, b):
            pulse = 0.5 + 0.5 * math.sin(2 * math.pi * (t - k * 0.2))
            pen.circle(px, yy, 8, dim(0.6 + 0.4 * (arrived * pulse)), 3)


def verified(pen, t):
    """The verifier's answer. It arrives after the path, never before."""
    p = span_(t, 0.74, 0.88) - span_(t, 0.94, 1.0)
    cx, cy = TICK_C
    pen.circle(cx, cy, TICK_R, dim(0.35 + 0.65 * p))
    if p > 0.02:
        r = TICK_R
        tick = [(cx - 0.42 * r, cy + 0.02 * r), (cx - 0.10 * r, cy + 0.34 * r),
                (cx + 0.46 * r, cy - 0.34 * r)]
        pen.along(tick, p, INK, STROKE)


def span_(t, a, b):
    if t <= a:
        return 0.0
    if t >= b:
        return 1.0
    return ease((t - a) / (b - a))


# -- type -------------------------------------------------------------------

CAPTION = "invert  \u00b7  multiply  \u00b7  conjugate"
FS_CAP = fit_width(UIB, CAPTION, 330)
POOL = "10,115 balanced presentations"
FS_POOL = fit_width(UIB, POOL, 300)


def logo(im):
    art = Image.open(os.path.join(ASSETS, "sair-logo.png")).convert("RGBA")
    w = LOGO[2] - LOGO[0]
    h = round(art.height * (w / art.width))
    art = art.resize((round(w * SS), h * SS), Image.LANCZOS)
    ox, oy = OFFSET
    im.paste(art, (round((LOGO[0] + ox) * SS), round((LOGO[1] + oy) * SS)), art)


def frame(i):
    t = i / FRAMES
    im = Image.new("RGB", (W * SS, H * SS), GROUND)
    pen = Pen(ImageDraw.Draw(im))
    logo(im)
    presentation_panel(pen, t)
    search_lane(pen, t)
    trivialised_panel(pen, t)
    verified(pen, t)
    pen.text(((LEFT[0] + RIGHT[2]) / 2, CAP_Y), CAPTION, f(UIB, FS_CAP),
             dim(0.60), "mm")
    return im.resize((W, H), Image.LANCZOS)


def centre_offset():
    import numpy as np
    OFFSET[0] = OFFSET[1] = 0.0
    a = np.asarray(frame(9).convert("RGB")).astype(int)
    ink = (a.min(axis=2) > 120) & ((a.max(axis=2) - a.min(axis=2)) < 60)
    cols = np.where(ink.any(axis=0))[0]
    rows = np.where(ink.any(axis=1))[0]
    dx = ((W - 1 - cols.max()) - cols.min()) / 2.0
    dy = ((H - 1 - rows.max()) - rows.min()) / 2.0
    print(f"  centring by ({dx:+.1f}, {dy:+.1f})")
    return dx, dy


def check_layout(im):
    import numpy as np
    a = np.asarray(im.convert("RGB")).astype(int)
    ink = (a.min(axis=2) > 120) & ((a.max(axis=2) - a.min(axis=2)) < 60)
    cols = np.where(ink.any(axis=0))[0]
    rows = np.where(ink.any(axis=1))[0]
    left, right = int(cols.min()), int(W - 1 - cols.max())
    top, bottom = int(rows.min()), int(H - 1 - rows.max())
    print(f"  margins  left {left}  right {right}  top {top}  bottom {bottom}")
    if abs(left - right) > 6 or abs(top - bottom) > 6:
        raise SystemExit(f"card is not centred: {left}/{right}, {top}/{bottom}")
    if min(left, right, top, bottom) < 20:
        raise SystemExit("ink runs too close to an edge")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else ASSETS
    os.makedirs(out, exist_ok=True)
    assert_no_overlap()
    OFFSET[0], OFFSET[1] = centre_offset()
    frames = [frame(i) for i in range(FRAMES)]
    check_layout(frames[9])
    # The ground is flat, so there is no gradient for an adaptive palette to
    # band and one shared palette is enough.
    pal = frames[0].quantize(colors=96, method=Image.MEDIANCUT)
    q = [fr.quantize(palette=pal, dither=Image.Dither.NONE) for fr in frames]
    path = os.path.join(out, "andrews-curtis-sair.gif")
    q[0].save(path, save_all=True, append_images=q[1:], duration=DURATION,
              loop=0, optimize=True, disposal=1)
    print(f"  {os.path.basename(path)}: {os.path.getsize(path) // 1024} KB, "
          f"{len(frames)} frames, {W}x{H}")
