"""Render a seamlessly looping "satisfying machine" animation to MP4.

Design rule that makes the loop seamless by construction: every animated
quantity is a pure function of the loop phase, using only integer harmonics of
the base period. There is no state carried between frames, so frame N and frame 0
are the same state by definition. Nothing is eased in or out at the ends.

The machine:
  * a large central gear turns once per loop
  * two counter-rotating gears mesh with it at exact integer ratios
  * a crank pin on the large gear drives a connecting rod and a horizontal piston
  * a cam on the second gear lifts and drops a hammer
  * six balls ride a serpentine ramp, released one per tooth pass
  * the balls land in cups on a conveyor that carries them back to the top

Usage:
    python3 render.py out.mp4 [--frames 360] [--fps 30] [--scale 2]
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080
TAU = math.pi * 2

# Palette: warm brass and enamel, high contrast so it reads at thumbnail size.
BG_TOP = (26, 22, 34)
BG_BOT = (44, 34, 46)
BRASS = (214, 158, 74)
BRASS_D = (150, 102, 40)
BRASS_L = (245, 205, 130)
STEEL = (168, 178, 192)
STEEL_D = (104, 114, 130)
ENAMEL = (232, 240, 246)
ACCENT = (232, 96, 88)
TEAL = (86, 196, 186)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        px[0, y] = mix(top, bottom, y / max(1, h - 1))
    return img.resize((w, h), Image.BILINEAR)


def gear(draw, cx, cy, r_out, teeth, phase, fill, dark, light, tooth_h=None, hole=None):
    """A gear as a ring of trapezoid teeth plus a shaded body."""
    tooth_h = tooth_h if tooth_h is not None else r_out * 0.16
    r_root = r_out - tooth_h
    # body
    draw.ellipse([cx - r_root, cy - r_root, cx + r_root, cy + r_root], fill=fill)
    # teeth
    for i in range(teeth):
        a0 = phase + TAU * i / teeth
        half = TAU / teeth * 0.30
        pts = []
        for a, r in ((a0 - half * 0.55, r_root), (a0 - half, r_out), (a0 + half, r_out), (a0 + half * 0.55, r_root)):
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        draw.polygon(pts, fill=fill)
    # shading: darker rim, lighter inner
    draw.arc([cx - r_root, cy - r_root, cx + r_root, cy + r_root], 200, 340, fill=dark, width=max(2, int(r_root * 0.06)))
    draw.arc([cx - r_root, cy - r_root, cx + r_root, cy + r_root], 20, 160, fill=light, width=max(2, int(r_root * 0.05)))
    if hole:
        draw.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=dark)
        draw.ellipse([cx - hole * 0.55, cy - hole * 0.55, cx + hole * 0.55, cy + hole * 0.55], fill=fill)


def ball(draw, x, y, r, base, hi):
    draw.ellipse([x - r, y - r, x + r, y + r], fill=base)
    draw.ellipse([x - r * 0.42, y - r * 0.55, x + r * 0.18, y - r * 0.02], fill=hi)


def round_rect(draw, box, rad, fill):
    draw.rounded_rectangle(box, radius=rad, fill=fill)


def render_frame(t: float, scale: int, T: float) -> Image.Image:
    """t is the loop phase in seconds, in [0, T). Everything derives from it.

    Layout zones, chosen so no two assemblies can overlap at any phase:
      x < 620    big gear
      x < 1000   meshing gear
      1000-1260  piston rail (rod reaches at most 1000)
      1400-1660  cam, hammer, anvil
      y 700-760  serpentine ramp, x 180-1200
      y 840-920  conveyor with cups
    """
    ph = t / T
    a = TAU * ph
    S = scale
    w, h = W * S, H * S

    img = vertical_gradient((w, h), BG_TOP, BG_BOT)
    d = ImageDraw.Draw(img)

    # ---- machine bed ---------------------------------------------------------
    round_rect(d, [90 * S, 676 * S, 1830 * S, 1020 * S], 26 * S, (34, 28, 40))
    round_rect(d, [90 * S, 676 * S, 1830 * S, 692 * S], 8 * S, (60, 48, 62))

    # ---- big gear ------------------------------------------------------------
    gx, gy, gr = 430 * S, 400 * S, 205 * S
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).ellipse([gx - gr, gy - gr + 22 * S, gx + gr, gy + gr + 22 * S], fill=145)
    sh = sh.filter(ImageFilter.GaussianBlur(20 * S))
    img = Image.composite(Image.new("RGB", (w, h), (12, 10, 16)), img, sh)
    d = ImageDraw.Draw(img)

    gear(d, gx, gy, gr, 24, a, BRASS, BRASS_D, BRASS_L, tooth_h=36 * S, hole=44 * S)
    for i in range(6):
        ang = a + TAU * i / 6
        d.line([gx + math.cos(ang) * 50 * S, gy + math.sin(ang) * 50 * S,
                gx + math.cos(ang) * 162 * S, gy + math.sin(ang) * 162 * S],
               fill=BRASS_D, width=14 * S)

    # ---- crank, rod, piston --------------------------------------------------
    piston_y = 400 * S
    crank_r = 152 * S
    px = gx + math.cos(a) * crank_r
    py = gy + math.sin(a) * crank_r
    rod = 560 * S
    dy = piston_y - py
    head = px + math.sqrt(max(1.0, rod * rod - dy * dy))
    d.line([px, py, head, piston_y], fill=(148, 156, 170), width=20 * S)
    d.line([px, py, head, piston_y], fill=(236, 242, 248), width=7 * S)

    # ---- meshing gear, drawn after the rod so the rod passes behind it ------
    rx, ry, rr = 760 * S, 400 * S, 100 * S
    gear(d, rx, ry, rr, 12, -2 * a + 0.26, STEEL, STEEL_D, ENAMEL, tooth_h=22 * S, hole=21 * S)

    # ---- piston head, in front ----------------------------------------------
    round_rect(d, [head - 16 * S, piston_y - 40 * S, head + 28 * S, piston_y + 40 * S], 9 * S, STEEL)
    round_rect(d, [head + 28 * S, piston_y - 13 * S, head + 62 * S, piston_y + 13 * S], 7 * S, ENAMEL)
    d.ellipse([px - 15 * S, py - 15 * S, px + 15 * S, py + 15 * S], fill=ACCENT)
    d.ellipse([px - 6 * S, py - 6 * S, px + 6 * S, py + 6 * S], fill=(255, 214, 204))

    # ---- cam, hammer, anvil --------------------------------------------------
    cx2, cy2 = 1560 * S, 640 * S
    cam_base = 50 * S
    lobe_off = 30 * S
    ca = -2 * a
    # the lobe is an ellipse offset along ca; its height above the base circle is
    # what the follower rides on, so the hammer uses the same expression
    off_x = math.cos(ca) * lobe_off
    off_y = math.sin(ca) * lobe_off
    d.ellipse([cx2 + off_x - cam_base * 0.94, cy2 + off_y - cam_base * 0.94,
               cx2 + off_x + cam_base * 0.94, cy2 + off_y + cam_base * 0.94], fill=ENAMEL)
    d.ellipse([cx2 - cam_base, cy2 - cam_base, cx2 + cam_base, cy2 + cam_base], fill=STEEL_D)
    d.ellipse([cx2 - cam_base * 0.62, cy2 - cam_base * 0.62,
               cx2 + cam_base * 0.62, cy2 + cam_base * 0.62], fill=STEEL)
    d.ellipse([cx2 - 10 * S, cy2 - 10 * S, cx2 + 10 * S, cy2 + 10 * S], fill=(38, 32, 42))
    # follower height: screen up is -y, so lift is the lobe's upward component
    lift = max(0.0, -off_y)
    hammer_bottom = cy2 - cam_base - 40 * S - lift
    # anvil sits above the hammer so the strike happens in clear space
    round_rect(d, [cx2 - 56 * S, hammer_bottom - 96 * S, cx2 + 56 * S, hammer_bottom - 66 * S], 8 * S, (66, 58, 74))
    round_rect(d, [cx2 - 44 * S, hammer_bottom - 66 * S, cx2 - 20 * S, hammer_bottom - 40 * S], 5 * S, (48, 42, 54))
    round_rect(d, [cx2 + 20 * S, hammer_bottom - 66 * S, cx2 + 44 * S, hammer_bottom - 40 * S], 5 * S, (48, 42, 54))
    d.line([cx2, cy2 - cam_base - 4 * S, cx2, hammer_bottom], fill=(126, 132, 146), width=9 * S)
    round_rect(d, [cx2 - 42 * S, hammer_bottom, cx2 + 42 * S, hammer_bottom + 34 * S], 9 * S, ACCENT)
    round_rect(d, [cx2 - 34 * S, hammer_bottom + 6 * S, cx2 - 8 * S, hammer_bottom + 26 * S], 6 * S, (255, 194, 184))

    # ---- serpentine ramp -----------------------------------------------------
    pts = []
    for i in range(6):
        fx = 180 + i * 200
        fy = 706 - (i % 2) * 34
        pts.append((fx * S, fy * S))
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=(70, 60, 74), width=22 * S)
        d.line([pts[i], pts[i + 1]], fill=(106, 94, 110), width=9 * S)

    def ramp_pos(u: float):
        u = max(0.0, min(0.999999, u))
        seg = u * (len(pts) - 1)
        i = int(seg)
        f = seg - i
        x = lerp(pts[i][0], pts[i + 1][0], f)
        y = lerp(pts[i][1], pts[i + 1][1], f)
        y -= math.sin(f * math.pi) * 10 * S
        return x, y

    # ---- conveyor ------------------------------------------------------------
    belt_y = 848 * S
    round_rect(d, [120 * S, belt_y, 1800 * S, belt_y + 58 * S], 29 * S, (46, 38, 50))
    round_rect(d, [120 * S, belt_y + 6 * S, 1800 * S, belt_y + 18 * S], 6 * S, (62, 52, 66))
    n_cups = 12
    for i in range(n_cups):
        cxp = 120 * S + ((i / n_cups + ph) % 1.0) * 1680 * S
        d.ellipse([cxp - 25 * S, belt_y - 24 * S, cxp + 25 * S, belt_y + 20 * S], fill=(28, 24, 32))
        d.arc([cxp - 25 * S, belt_y - 24 * S, cxp + 25 * S, belt_y + 20 * S], 180, 360,
              fill=(132, 116, 138), width=6 * S)

    # ---- balls: ride the ramp, then fall into a passing cup -------------------
    n_balls = 5
    for k in range(n_balls):
        u = (ph + k / n_balls) % 1.0
        bx, by = ramp_pos(u)
        fade = min(1.0, u * 7) * min(1.0, (1 - u) * 7)
        if u > 0.88:
            f = (u - 0.88) / 0.12
            ex, ey = ramp_pos(0.88)
            bx = ex + f * 150 * S
            by = lerp(ey, belt_y - 20 * S, f * f)
            fade *= max(0.0, 1.0 - max(0.0, (f - 0.7) / 0.3))
        col = mix((66, 56, 66), ACCENT if k % 2 == 0 else TEAL, fade)
        ball(d, bx, by, 19 * S, col, mix(col, (255, 255, 255), 0.7))

    # ---- title plate ---------------------------------------------------------
    round_rect(d, [1330 * S, 116 * S, 1790 * S, 214 * S], 14 * S, (38, 32, 44))
    for i in range(3):
        yy = 150 * S + i * 21 * S
        ww = (300 - i * 64) * S
        round_rect(d, [1360 * S, yy, 1360 * S + ww, yy + 9 * S], 4 * S,
                   mix((92, 82, 98), (156, 142, 162), 0.4 + 0.2 * i))

    return img.resize((W, H), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=360)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--ffmpeg", default=os.path.expanduser("~/.local/ffmpeg/ffmpeg"))
    args = ap.parse_args()

    T = args.frames / args.fps
    tmp = tempfile.mkdtemp(prefix="machine_")
    print(f"rendering {args.frames} frames at {W}x{H}, loop {T:.2f}s -> {tmp}")

    for i in range(args.frames):
        t = i / args.fps
        img = render_frame(t, args.scale, T)
        img.save(os.path.join(tmp, f"f{i:05d}.png"))
        if i % 30 == 0:
            print(f"JCODE_PROGRESS {i}/{args.frames} frame {i}")

    cmd = [
        args.ffmpeg, "-y", "-framerate", str(args.fps), "-i", os.path.join(tmp, "f%05d.png"),
        "-c:v", "libx264", "-preset", "slow", "-crf", "17",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ]
    print("encoding:", " ".join(cmd[:6]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        return 1
    size = os.path.getsize(args.out)
    print(f"wrote {args.out} ({size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
