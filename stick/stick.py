#!/usr/bin/env python3
"""Stickman POV Shorts ("You are ... what do you do?").
Procedural flat-colour stick figures drawn with PIL (2x supersampled), voice + lo-fi bed from render.py.
Usage: python3 stick/stick.py spec.json out.mp4
Spec: {id, title, voice, speed, scenes:[{say, act, ...params}]}
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import tts, render

W, H, FPS, S = 1080, 1920, 30, 2
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
INK = (22, 22, 28)
SKY, SKY2 = (178, 222, 255), (232, 245, 255)
SEA, SEA2 = (38, 120, 210), (90, 170, 235)
SAND, SAND2 = (244, 214, 152), (214, 180, 118)
GRASS, HILL = (110, 190, 110), (86, 160, 92)
YEL, RED = (255, 206, 0), (230, 50, 50)
GROUND = 1300
_fc = {}


def F(px):
    if px not in _fc: _fc[px] = ImageFont.truetype(FONT, int(px * S))
    return _fc[px]


class Pen:
    def __init__(s, img, dx=0, dy=0):
        s.d = ImageDraw.Draw(img); s.dx, s.dy = dx, dy

    def p(s, x, y): return ((x + s.dx) * S, (y + s.dy) * S)

    def line(s, pts, fill=INK, w=12):
        q = [s.p(*a) for a in pts]
        s.d.line(q, fill=fill, width=int(w * S), joint="curve")
        r = w * S / 2
        for x, y in (q[0], q[-1]): s.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def circ(s, x, y, r, fill=None, outline=INK, w=10):
        (X, Y) = s.p(x, y); R = r * S
        s.d.ellipse([X - R, Y - R, X + R, Y + R], fill=fill, outline=outline, width=int(w * S) if outline else 0)

    def poly(s, pts, fill, outline=None, w=8):
        s.d.polygon([s.p(*a) for a in pts], fill=fill, outline=outline, width=int(w * S) if outline else 0)

    def rect(s, x0, y0, x1, y1, fill, outline=INK, w=8, r=0):
        a, b = s.p(x0, y0), s.p(x1, y1)
        s.d.rounded_rectangle([a, b], radius=r * S, fill=fill, outline=outline, width=int(w * S) if outline else 0)

    def text(s, x, y, t, px, fill=(255, 255, 255), stroke=6, sfill=INK, anchor="mm"):
        s.d.text(s.p(x, y), t, font=F(px), fill=fill, stroke_width=int(stroke * S), stroke_fill=sfill, anchor=anchor)


# ---------------- stick figure ----------------
def limb(x, y, a1, a2, L=52):
    x1, y1 = x + L * math.sin(a1), y + L * math.cos(a1)
    return [(x, y), (x1, y1), (x1 + L * math.sin(a2), y1 + L * math.cos(a2))]


def stick(pen, x, y, pose="stand", ph=0.0, face=1, col=INK, mood="ok", label=None, sc=1.45):
    """x,y = feet on ground. face = 1 right / -1 left. ph = animation phase (seconds)."""
    k = sc; f = face
    bob = 0; lean = 0
    if pose == "stand":
        bob = 2 * math.sin(ph * 3)
        legs = [(0.18, 0.05), (-0.18, -0.05)]; arms = [(0.35, 0.15), (-0.35, -0.15)]
    elif pose in ("walk", "run"):
        sp, amp = (11, 0.75) if pose == "run" else (6.5, 0.45)
        s_ = math.sin(ph * sp); bob = abs(math.cos(ph * sp)) * (10 if pose == "run" else 4)
        lean = 0.28 if pose == "run" else 0.06
        legs = [(amp * s_, amp * s_ - max(0, -s_) * 0.9), (-amp * s_, -amp * s_ - max(0, s_) * 0.9)]
        arms = [(-amp * s_ * 1.2, -amp * s_ * 1.2 + (1.4 if pose == "run" else 0.3)),
                (amp * s_ * 1.2, amp * s_ * 1.2 + (1.4 if pose == "run" else 0.3))]
    elif pose == "crouch":
        bob = -38 + 3 * math.sin(ph * 40)
        legs = [(1.3, -0.4), (0.9, -0.9)]; arms = [(2.6, 3.9), (2.9, 4.2)]
        lean = 0.35
    elif pose == "panic":
        bob = 3 * math.sin(ph * 18)
        legs = [(0.25, 0.05), (-0.25, -0.05)]
        w_ = 0.35 * math.sin(ph * 14)
        arms = [(2.6 + w_, 2.9 + w_), (-2.6 - w_, -2.9 - w_)]
    elif pose == "look":
        bob = 1.5 * math.sin(ph * 3)
        legs = [(0.18, 0.05), (-0.18, -0.05)]; arms = [(2.2, 4.3), (-0.3, -0.1)]
    elif pose == "point":
        bob = 1.5 * math.sin(ph * 3)
        legs = [(0.18, 0.05), (-0.18, -0.05)]; arms = [(1.57, 1.57 + 0.05 * math.sin(ph * 6)), (-0.3, -0.1)]
    elif pose == "climb":
        s_ = math.sin(ph * 8); bob = 0
        legs = [(0.5 * s_ + 0.3, 0.5 * s_ - 0.6), (-0.5 * s_ + 0.3, -0.5 * s_ - 0.6)]
        arms = [(2.3 + 0.4 * s_, 2.6), (2.3 - 0.4 * s_, 2.6)]
        lean = 0.2
    else:
        legs = [(0.18, 0.05), (-0.18, -0.05)]; arms = [(0.35, 0.15), (-0.35, -0.15)]
    hip = (x, y - 104 * k - bob)
    neck = (hip[0] + f * math.sin(lean) * 110 * k, hip[1] - math.cos(lean) * 110 * k)
    head = (neck[0] + f * math.sin(lean) * 44 * k, neck[1] - math.cos(lean) * 44 * k)
    sh = (hip[0] + (neck[0] - hip[0]) * 0.85, hip[1] + (neck[1] - hip[1]) * 0.85)
    w = 12 * k
    for a1, a2 in legs: pen.line(limb(*hip, f * a1, f * a2, 54 * k), col, w)
    pen.line([hip, neck], col, w)
    for a1, a2 in arms: pen.line(limb(*sh, f * a1, f * a2, 46 * k), col, w)
    pen.circ(*head, 40 * k, fill=(255, 255, 255), outline=col, w=w)
    ex = head[0] + f * 12 * k
    if mood == "scared":
        for o in (-11, 11): pen.circ(ex + o * k, head[1] - 6 * k, 6 * k, fill=(255, 255, 255), outline=col, w=4 * k)
        pen.circ(ex, head[1] + 17 * k, 7 * k, fill=col, outline=None)
    else:
        for o in (-11, 11): pen.circ(ex + o * k, head[1] - 6 * k, 4.5 * k, fill=col, outline=None)
        if mood == "happy":
            pen.d.arc([*pen.p(ex - 14 * k, head[1] + 2 * k), *pen.p(ex + 14 * k, head[1] + 22 * k)], 10, 170, fill=col, width=int(5 * k * S))
        else:
            pen.line([(ex - 9 * k, head[1] + 15 * k), (ex + 9 * k, head[1] + 15 * k)], col, 5 * k)
    if label:
        ty = head[1] - 92 * k
        pen.rect(head[0] - 58, ty - 30, head[0] + 58, ty + 30, YEL, INK, 6, 14)
        pen.text(head[0], ty, label, 34, fill=INK, stroke=0)
        pen.poly([(head[0] - 14, ty + 30), (head[0] + 14, ty + 30), (head[0], ty + 48)], YEL, INK, 5)


# ---------------- scenery ----------------
def sky(img):
    a = np.linspace(0, 1, img.height)[:, None, None]
    g = (np.array(SKY2) * (1 - a) + np.array(SKY) * a).astype(np.uint8)
    img.paste(Image.fromarray(np.repeat(g, img.width, axis=1)))


def sun(pen, t):
    pen.circ(880, 330, 78 + 3 * math.sin(t * 2), fill=(255, 220, 90), outline=None)


def beach(pen, t, shore=430, tide=0.0, wall=0.0):
    """Sea on the left up to x=shore. tide>0 pulls the water out (to the left), exposing wet sand."""
    pen.poly([(-60, GROUND), (W + 60, GROUND - 40), (W + 60, H + 60), (-60, H + 60)], SAND)
    wet_to = shore
    sx = shore - tide * 520
    if tide > 0:
        pen.poly([(sx - 40, GROUND - 10), (wet_to + 30, GROUND - 10), (wet_to + 60, H + 60), (sx - 40, H + 60)], SAND2)
    pts = [(-60, GROUND - 70 - wall * 520)]
    for i in range(0, 41):
        xx = -60 + (sx + 60) * i / 40
        h = wall * 520 * (1 - (i / 40) ** 3)
        pts.append((xx, GROUND - 70 - h + 8 * math.sin(t * 3 + i * 0.7)))
    pts += [(sx + 30, GROUND - 40), (sx + 60, H + 60), (-60, H + 60)]
    pen.poly(pts, SEA)
    for i in range(3):
        y = GROUND - 30 + i * 70
        xs = [(-60 + j * 40, y + 6 * math.sin(t * 4 + j + i)) for j in range(int((sx + 40) / 40))]
        if len(xs) > 1: pen.line(xs, SEA2, 6)


def fish(pen, x, y, t, i):
    j = 14 * abs(math.sin(t * 9 + i * 1.7))
    pen.d.ellipse([*pen.p(x - 26, y - 12 - j), *pen.p(x + 26, y + 12 - j)], fill=(255, 140, 60), outline=INK, width=4 * S)
    pen.poly([(x + 22, y - j), (x + 44, y - 16 - j), (x + 44, y + 16 - j)], (255, 140, 60), INK, 4)


def hill(pen, off=0.0):
    pts = [(-60, GROUND + 40)]
    for i in range(0, 61):
        xx = -60 + i * 22
        pts.append((xx, GROUND + 40 - 260 * (1 / (1 + math.exp(-(xx - 540 + off) / 140))) + 12 * math.sin((xx + off) / 70)))
    pts += [(W + 60, H + 60), (-60, H + 60)]
    pen.poly(pts, HILL)


def hill_y(x, off=0.0):
    return GROUND + 40 - 260 * (1 / (1 + math.exp(-(x - 540 + off) / 140))) + 12 * math.sin((x + off) / 70)


def badge(pen, x, y, txt, col=RED, px=64):
    w = F(px).getlength(txt) / S / 2 + 34
    pen.rect(x - w, y - px * 0.85, x + w, y + px * 0.85, col, INK, 8, 22)
    pen.text(x, y + 2, txt, px, fill=(255, 255, 255), stroke=0)


def clock(pen, x, y, r, frac, col=(255, 255, 255), txt=None):
    pen.circ(x, y, r, fill=col, outline=INK, w=10)
    a = frac * 2 * math.pi
    pen.line([(x, y), (x + r * 0.75 * math.sin(a), y - r * 0.75 * math.cos(a))], INK, 10)
    pen.line([(x, y), (x + r * 0.45 * math.sin(a / 12), y - r * 0.45 * math.cos(a / 12))], INK, 12)
    if txt: pen.text(x, y + r + 60, txt, 58)


def big_x(pen, x, y, r, p):
    if p <= 0: return
    pen.line([(x - r, y - r), (x - r + 2 * r * min(1, p * 2), y - r + 2 * r * min(1, p * 2))], RED, 30)
    if p > 0.5: q = min(1, (p - 0.5) * 2); pen.line([(x + r, y - r), (x + r - 2 * r * q, y - r + 2 * r * q)], RED, 30)


def check(pen, x, y, r, p):
    if p <= 0: return
    pts = [(x - r, y), (x - r * 0.3, y + r * 0.7), (x + r, y - r * 0.8)]
    q = min(1, p * 1.6)
    if q < 0.4: pen.line([pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * q / 0.4, pts[0][1] + (pts[1][1] - pts[0][1]) * q / 0.4)], (40, 170, 80), 30)
    else:
        u = (q - 0.4) / 0.6
        pen.line([pts[0], pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * u, pts[1][1] + (pts[2][1] - pts[1][1]) * u)], (40, 170, 80), 30)


def ease(u): u = max(0.0, min(1.0, u)); return 1 - (1 - u) ** 3


# ---------------- acts ----------------
def act_hook(img, t, d, sc):
    shake = max(0, (t - d * 0.45)) * 9
    pen = Pen(img, shake * math.sin(t * 60), shake * math.cos(t * 47) * 0.6)
    sky(img); sun(pen, t); beach(pen, t)
    pen.poly([(700, GROUND + 10), (900, GROUND + 0), (920, GROUND + 50), (715, GROUND + 62)], (255, 90, 90), INK, 6)   # towel
    stick(pen, 600, GROUND - 26, "panic" if t > d * 0.45 else "stand", t, 1, mood="scared" if t > d * 0.45 else "happy", label="YOU")
    if sc.get("title"):
        p = ease(t / 0.35)
        pen.text(540, 300 - (1 - p) * 120, sc["title"][0], 92, fill=(255, 255, 255), stroke=10)
        pen.text(540, 410 - (1 - p) * 120, sc["title"][1], 92, fill=YEL, stroke=10)
    if t > d * 0.55:
        left = max(0, 600 - (t - d * 0.55) * 37)
        badge(pen, 540, 590, f"{int(left // 60)}:{int(left % 60):02d}", RED, 76)


def act_quake(img, t, d, sc):
    a = 14 * (1 - t / d * 0.5)
    pen = Pen(img, a * math.sin(t * 70), a * math.cos(t * 53))
    sky(img); sun(pen, t); beach(pen, t)
    for i, (x0, y0) in enumerate([(760, GROUND + 60), (900, GROUND + 180)]):
        p = ease(t / 0.8)
        pen.line([(x0, y0), (x0 + 40 * p, y0 + 40 * p), (x0 + 10 * p, y0 + 90 * p), (x0 + 60 * p, y0 + 150 * p)], INK, 8)
    stick(pen, 620, GROUND - 26, "crouch", t, -1, mood="scared", label="YOU")
    badge(pen, 540, 470, sc.get("badge", "DROP • COVER • HOLD"), RED, 56)


def act_timer(img, t, d, sc):
    pen = Pen(img)
    sky(img); sun(pen, t); beach(pen, t)
    secs = min(sc.get("to", 25), t / d * sc.get("to", 25) * 1.25)
    hot = secs >= sc.get("warn", 20)
    clock(pen, 540, 640, 150, secs / 60, (255, 120, 120) if hot else (255, 255, 255))
    pen.text(540, 380, f"{int(secs)} sec", 84, fill=RED if hot else (255, 255, 255), stroke=10)
    stick(pen, 620, GROUND - 26, "look" if not hot else "panic", t, -1, mood="scared" if hot else "ok", label="YOU")
    if hot: pen.text(820, 470, "!", 200, fill=RED, stroke=10)


def act_recede(img, t, d, sc):
    pen = Pen(img)
    sky(img); sun(pen, t)
    tide = ease(t / (d * 0.7))
    beach(pen, t, tide=tide)
    if tide > 0.3:
        for i, (x, y) in enumerate([(250, GROUND + 120), (360, GROUND + 260), (150, GROUND + 330)]):
            if 430 - tide * 520 < x: fish(pen, x, y, t, i)
    stick(pen, 700, GROUND - 30, "look", t, -1, mood="scared", label="YOU")
    if tide > 0.6: badge(pen, 540, 470, sc.get("badge", "WATER GOES OUT"), (40, 110, 200), 60)


def act_dont(img, t, d, sc):
    pen = Pen(img)
    sky(img); sun(pen, t)
    beach(pen, t, tide=1.0, wall=ease((t - d * 0.4) / (d * 0.6)) * 0.45)
    for i in range(3):
        x = 520 - i * 120 - t * 55
        stick(pen, x, GROUND + 40 + i * 50, "walk", t + i, -1, col=(110, 110, 120), mood="happy", sc=1.15)
    stick(pen, 820, GROUND - 40, "point", t, -1, mood="scared", label="YOU")
    big_x(pen, 300, 760, 150, (t - 0.4) / 0.6)


def act_run(img, t, d, sc):
    off = t * 260
    pen = Pen(img)
    sky(img); sun(pen, t)
    hill(pen, off * 0.0)
    for i in range(6):   # passing trees for speed
        x = (W + 200) - ((off * 1.4 + i * 260) % (W + 400))
        y = hill_y(x)
        pen.rect(x - 10, y - 120, x + 10, y, (120, 80, 50), INK, 5)
        pen.circ(x, y - 150, 60, fill=GRASS, outline=INK, w=6)
    x = 520; y = hill_y(x)
    stick(pen, x, y, "run", t, 1, mood="scared", label="YOU")
    h = min(sc.get("m", 30), t / (d * 0.8) * sc.get("m", 30))
    pen.rect(940, 520, 1010, 1120, (255, 255, 255), INK, 8, 18)
    pen.rect(948, 1112 - 584 * h / sc.get("m", 30), 1002, 1112, (40, 170, 80), None, 0, 14)
    pen.text(975, 470, f"{int(h)} m", 52)
    badge(pen, 420, 470, sc.get("badge", "UPHILL / INLAND"), (40, 170, 80), 56)


def act_building(img, t, d, sc):
    pen = Pen(img)
    sky(img); sun(pen, t)
    pen.rect(560, 520, 900, GROUND + 60, (170, 170, 180), INK, 10)
    for r in range(6):
        for c in range(3):
            pen.rect(590 + c * 105, 560 + r * 125, 660 + c * 105, 640 + r * 125, (120, 190, 240), INK, 5, 6)
    water = GROUND + 60 - ease(t / d) * 330
    pts = [(-60, water)] + [(x, water + 10 * math.sin(t * 4 + x / 50)) for x in range(-60, W + 80, 40)] + [(W + 60, H + 60), (-60, H + 60)]
    p = ease(t / (d * 0.75))
    y = GROUND + 30 - p * 760
    stick(pen, 500, y, "climb", t, 1, mood="scared", label="YOU")
    pen.poly(pts, (70, 120, 170))
    badge(pen, 250, 380, sc.get("badge", "GO UP"), (40, 170, 80), 64)


def act_stay(img, t, d, sc):
    pen = Pen(img)
    sky(img); sun(pen, t)
    wave = 0.5 + 0.5 * math.sin(t * 2.2)
    pts = [(-60, GROUND - 20 - wave * 170)] + [(x, GROUND - 20 - wave * 170 * (1 - x / 700) + 12 * math.sin(t * 5 + x / 40)) for x in range(-60, 700, 40)] + [(760, GROUND - 20), (760, H + 60), (-60, H + 60)]
    pen.poly(pts, SEA)
    hill(pen, -220)
    x = 880; y = hill_y(x, -220)
    stick(pen, x, y, "stand", t, -1, mood="ok", label="YOU")
    clock(pen, 300, 620, 130, t / 2.5, (255, 255, 255), sc.get("badge", "HOURS"))


def act_safe(img, t, d, sc):
    pen = Pen(img)
    sky(img); sun(pen, t)
    hill(pen, -220)
    x = 860; y = hill_y(x, -220)
    stick(pen, x, y, "stand", t, -1, mood="happy", label="YOU")
    check(pen, 420, 700, 150, (t - 0.3) / 0.8)


def act_calm(img, t, d, sc):
    a = max(0, (t - d * 0.7)) * 10
    pen = Pen(img, a * math.sin(t * 60), a * math.cos(t * 47) * 0.6)
    sky(img); sun(pen, t); beach(pen, t)
    pen.poly([(700, GROUND + 10), (900, GROUND + 0), (920, GROUND + 50), (715, GROUND + 62)], (255, 90, 90), INK, 6)
    stick(pen, 600, GROUND - 26, "stand", t, 1, mood="happy" if t < d * 0.7 else "ok", label="YOU")


_imgs = {}


def act_img(img, t, d, sc):
    """Illustrated still with camera motion: slow push-in (or pull/pan), optional shake, title, badge."""
    p = sc["img"]
    if p not in _imgs:
        im = Image.open(p).convert("RGB"); r = max(W * S * 1.14 / im.width, H * S * 1.14 / im.height)
        _imgs[p] = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
    src = _imgs[p]; u = t / max(d, 0.01)
    mv = sc.get("move", "in")
    z = {"in": 1.0 + 0.10 * u, "out": 1.10 - 0.10 * u}.get(mv, 1.06)
    cw, ch = W * S * 1.14 / z, H * S * 1.14 / z
    cw, ch = min(cw, src.width), min(ch, src.height)
    cx, cy = src.width / 2, src.height / 2
    if mv == "up": cy = src.height / 2 + (src.height - ch) / 2 * (1 - 2 * u)
    if mv == "right": cx = src.width / 2 + (src.width - cw) / 2 * (2 * u - 1)
    sh = sc.get("shake")
    if sh is not None and u >= sh:
        a = 22 * S * (1 if sc.get("shake_end") is None or u < sc["shake_end"] else 0)
        cx += a * math.sin(t * 61); cy += a * 0.7 * math.cos(t * 47)
    # quick punch-in on scene start
    pz = 1 + 0.06 * max(0, 1 - t / 0.25)
    cw2, ch2 = cw / pz, ch / pz
    cx = min(max(cx, cw2 / 2), src.width - cw2 / 2); cy = min(max(cy, ch2 / 2), src.height - ch2 / 2)
    box = (cx - cw2 / 2, cy - ch2 / 2, cx + cw2 / 2, cy + ch2 / 2)
    img.paste(src.resize((W * S, H * S), Image.BILINEAR, box=box))
    pen = Pen(img)
    if sc.get("title"):
        q = ease(t / 0.35)
        pen.text(540, 150 - (1 - q) * 120, sc["title"][0], 96, fill=(255, 255, 255), stroke=11)
        pen.text(540, 262 - (1 - q) * 120, sc["title"][1], 96, fill=YEL, stroke=11)
    if sc.get("badge") and t > 0.3:
        badge(pen, 540, sc.get("badge_y", 300), sc["badge"], tuple(sc.get("badge_col", RED)), 60)
    if sc.get("countdown") and u > 0.45:
        left = max(0, sc["countdown"] - (t - d * 0.45) * 37)
        badge(pen, 870, 820, f"{int(left // 60)}:{int(left % 60):02d}", RED, 76)


ACTS = {k[4:]: v for k, v in globals().items() if k.startswith("act_")}


# ---------------- build ----------------
def chunks(text, n=4):
    w = text.split(); out = []
    while w: out.append(" ".join(w[:n])); w = w[n:]
    return out


def ass_t(s): return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def build(spec_path, out):
    spec = json.load(open(spec_path))
    work = out + ".work"; os.makedirs(work, exist_ok=True)
    voice, speed = spec.get("voice", "bm_lewis"), spec.get("speed", 1.0)
    SR = render.SR
    parts, t = [np.zeros(int(0.15 * SR), np.float32)], 0.15
    scenes = spec["scenes"]
    for i, sc in enumerate(scenes):
        a = tts.synth(sc["say"], voice=voice, speed=speed)
        post = 0.25
        parts += [a, np.zeros(int(post * SR), np.float32)]
        sc["vstart"] = t; sc["vend"] = t + len(a) / SR
        sc["start"] = 0 if i == 0 else t; t = sc["vend"] + post; sc["end"] = t
    total = t + 0.2; scenes[-1]["end"] = total
    voice_a = np.concatenate(parts + [np.zeros(int(0.3 * SR), np.float32)])[: int(total * SR)]
    bed = render.ambient(total, sum(map(ord, spec["id"])) % 9999)[: len(voice_a)]
    wav = os.path.join(work, "audio.wav"); render.master_audio(voice_a, bed, wav)
    ass = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,2,80,80,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""]
    for sc in scenes:
        cs = chunks(sc["say"]); dur = sc["vend"] - sc["vstart"]; tot = sum(len(c) + 3 for c in cs); tt = sc["vstart"]
        for c in cs:
            dd = dur * (len(c) + 3) / tot
            ass.append(f"Dialogue: 0,{ass_t(tt)},{ass_t(tt + dd)},Cap,,0,0,0,,{{\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}}{c.upper()}")
            tt += dd
    ass_path = os.path.join(work, "caps.ass"); open(ass_path, "w").write("\n".join(ass) + "\n")
    silent = os.path.join(work, "video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    n = int(total * FPS)
    si = 0
    for fi in range(n):
        tt = fi / FPS
        while si < len(scenes) - 1 and tt >= scenes[si]["end"]: si += 1
        sc = scenes[si]
        img = Image.new("RGB", (W * S, H * S))
        ACTS[sc["act"]](img, tt - sc["start"], sc["end"] - sc["start"], sc)
        ff.stdin.write(img.reduce(S).tobytes())
        if fi % 150 == 0: print(f"frame {fi}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-vf", f"ass={ass_path}", "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    print("done", out, round(total, 1), "s")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
