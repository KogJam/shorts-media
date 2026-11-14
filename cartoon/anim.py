#!/usr/bin/env python3
"""Fully animated cartoon POV shorts: AI-painted backgrounds + jointed puppet rigs (cartoon/rig.py) + procedural FX.
Usage: python3 cartoon/anim.py spec.json out.mp4      (spec scenes use act names defined here: c_*)
Reuses stick/stick.py for voice, music bed, captions and the frame loop."""
import math, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location("stick", os.path.join(ROOT, "stick", "stick.py"))
st = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(st)
from PIL import ImageDraw
import poses as P
from rig import Rig

S, W, H, INK, RED, YEL = st.S, st.W, st.H, st.INK, st.RED, st.YEL
ASSET = st.ASSET
_rigs = {}


def rig(c):
    if c not in _rigs: _rigs[c] = Rig(os.path.join(ASSET, "rig_" + c))
    return _rigs[c]


def blink(t, seed=0): return ((t + seed * 1.3) % 3.1) < 0.12


def actor(img, c, x, y, h, track, t, view=None, face=1, expr=None, seed=0):
    """track: list of (t_start, pose_name[, expr]) ; poses cross-blend over 0.3 s."""
    cur, prev, ts = track[0], None, 0
    for k in track:
        if t >= k[0]: prev, cur, ts = cur, k, k[0]
    p = P.get(cur[1], t + seed)
    if prev is not None and prev is not cur and t - ts < 0.3:
        p = P.blend(P.get(prev[1], t + seed), p, (t - ts) / 0.3)
    v = view or ("side" if cur[1] in P.SIDE else "front")
    e = expr or (cur[2] if len(cur) > 2 else "n")
    rig(c).draw(img, x, y, h, p, S, view=v, face=face, expr=e, blink=blink(t, seed) and e == "n")


def water(img, level, t, amp=14, col=(52, 118, 150), foam=True, x0=-40, x1=W + 40, bottom=H + 50, debris=True):
    d = ImageDraw.Draw(img)
    pts = [((x) * S, (level + amp * math.sin(t * 3 + x / 60) + amp * 0.5 * math.sin(t * 5.3 + x / 23)) * S) for x in range(x0, x1 + 1, 20)]
    poly = pts + [(x1 * S, bottom * S), (x0 * S, bottom * S)]
    d.polygon(poly, fill=col)
    d.line(pts, fill=INK, width=8 * S, joint="curve")
    if foam: d.line([(x, y + 10 * S) for x, y in pts], fill=(225, 240, 245), width=6 * S, joint="curve")
    for i in range(6 if debris else 0):   # floating debris
        x = (i * 190 + t * 40 * (1 + i % 3)) % (W + 100) - 50
        yy = level + 60 + i * 35 + 6 * math.sin(t * 3 + i)
        d.rounded_rectangle([(x - 40) * S, (yy - 8) * S, (x + 40) * S, (yy + 8) * S], radius=6 * S, fill=(140, 100, 60), outline=INK, width=4 * S)


def shake(t, a): return a * math.sin(t * 61), a * 0.7 * math.cos(t * 47)


def head_overlays(img, t, d, sc):
    return st.overlays(img, t, d, sc)


# ---------------- scenes ----------------
def c_beach(img, t, d, sc):
    u = t / d; s0 = sc.get("shake", 0.45); on = u >= s0; ts = d * s0
    dx, dy = shake(t, 14 if on else 0)
    st.bg(img, "bg_beach", 1.0 + 0.05 * u, 0.5, 0.6, dx, dy)
    pen = st.Pen(img)
    end = sc.get("ending")
    bgp = [(0, "idle")] + ([] if end else [(ts + 0.2, "panic", "scared")])
    actor(img, "a", 190 + dx, 1330 + dy, 470, bgp, t, seed=1)
    actor(img, "b", 900 + dx, 1350 + dy, 500, [(0, "idle")] + ([] if end else [(ts + 0.35, "panic", "scared")]), t, seed=2)
    if on: st.pebbles(pen, t)
    you = [(0, "idle")] + ([(ts, "look", "scared")] if end else [(ts, "panic", "scared")])
    actor(img, "you", 540 + dx * 1.4, 1790 + dy, 1000, you, t)
    pen = head_overlays(img, t, d, sc)
    if sc.get("countdown") and on:
        left = max(0, sc["countdown"] - (t - ts) * 37)
        st.badge(pen, 880, 860, f"{int(left // 60)}:{int(left % 60):02d}", RED, 76)


def c_quake(img, t, d, sc):
    dx, dy = shake(t, 18 * (1 - 0.5 * t / d))
    st.bg(img, "bg_beach", 1.08, 0.5, 0.75, dx, dy)
    pen = st.Pen(img)
    for i, (x0, y0) in enumerate([(160, 1500), (760, 1560), (420, 1830)]):
        p = st.ease((t - i * 0.3) / 0.9)
        if p > 0:
            pts = [(x0, y0)] + [(x0 + k * 34 * p * (1 if i % 2 else -1) + (18 if k % 2 else -18) * p, y0 + k * 22 * p) for k in range(1, 6)]
            pen.line(pts, (60, 45, 30), 9)
    actor(img, "a", 180 + dx, 1330 + dy, 470, [(0, "cover", "scared")], t, seed=1)
    actor(img, "b", 900 + dx, 1350 + dy, 500, [(0, "cover", "scared")], t, seed=2)
    for i in range(14):
        x = (i * 83 + 40) % 1080; y = ((t * (420 + i * 30)) + i * 260) % 1900
        pen.circ(x + dx, y, 6 + i % 4, fill=(225, 205, 160), outline=None)
    actor(img, "you", 540 + dx * 1.5, 1800 + dy, 1000, [(0, "cover", "scared")], t)
    st.pebbles(pen, t, amp=1.3)
    head_overlays(img, t, d, sc)


def c_timer(img, t, d, sc):
    st.bg(img, "bg_beach", 1.03 + 0.04 * t / d, 0.5, 0.6)
    pen = st.Pen(img)
    to, warn = sc.get("to", 25), sc.get("warn", 20)
    secs = min(to, t / d * to * 1.25); hot = secs >= warn; th = warn / (to * 1.25) * d
    actor(img, "a", 160, 1330, 470, [(0, "idle"), (th, "panic", "scared")], t, seed=1)
    actor(img, "you", 430, 1790, 1000, [(0, "idle"), (d * 0.25, "look"), (th, "panic", "scared")], t)
    st.clock(pen, 870, 600, 115, secs / 60, (255, 120, 120) if hot else (255, 255, 255))
    pen.text(870, 790, f"{int(secs)} SEC", 70, fill=RED if hot else (255, 255, 255), stroke=9)
    head_overlays(img, t, d, sc)


def c_recede(img, t, d, sc):
    u = t / d
    st.bg(img, "bg_seafloor", 1.12 - 0.1 * st.ease(u), 0.5, 0.55)
    # curious tourists wander out toward the sea (side view, walking left/away)
    actor(img, "a", 760 - t * 45, 1240, 380, [(0, "walk_side")], t, face=-1, seed=1)
    actor(img, "b", 930 - t * 40, 1270, 400, [(0, "walk_side")], t, face=-1, seed=2)
    actor(img, "you", 520, 1800, 1000, [(0, "idle", "n"), (d * 0.3, "look", "scared")], t)
    head_overlays(img, t, d, sc)


def c_dont(img, t, d, sc):
    u = t / d
    st.bg(img, "bg_seafloor", 1.02, 0.5, 0.55)
    g = st.ease((u - 0.15) / 0.85)
    if g > 0: st.put(img, "obj/wave", 640, 600, 50 + 200 * g)
    stop = d * 0.55
    ta = min(t, stop)
    actor(img, "a", 820 - ta * 45, 1240, 380, [(0, "walk_side"), (stop, "panic", "scared")], t, face=-1 if t < stop else 1, seed=1, view="side" if t < stop else "front")
    actor(img, "b", 980 - ta * 40, 1270, 400, [(0, "walk_side"), (stop + 0.2, "panic", "scared")], t, face=-1 if t < stop + 0.2 else 1, seed=2, view="side" if t < stop + 0.2 else "front")
    actor(img, "you", 330, 1820, 980, [(0, "panic", "scared")], t)
    st.big_x(st.Pen(img), 800, 1050, 170, (t - 0.4) / 0.6)
    head_overlays(img, t, d, sc)


def c_run(img, t, d, sc):
    u = t / d
    st.bg(img, "bg_road", 1.0, 0.1 + 0.8 * u, 1.0)
    pen = st.Pen(img)
    for i in range(4):
        q = ((t * 3 + i * 0.25) % 1.0)
        pen.circ(400 - q * 260, 1830 - q * 40, 14 + q * 34, fill=(205, 195, 175), outline=None)
    actor(img, "b", 120, 1700, 640, [(0, "run_side", "scared")], t, seed=0.5)
    actor(img, "a", 300, 1760, 700, [(0, "run_side", "scared")], t, seed=0.2)
    actor(img, "you", 640, 1860, 900, [(0, "run_side", "scared")], t)
    head_overlays(img, t, d, sc)
    m = sc.get("m", 30); h = min(m, u / 0.85 * m)
    pen.rect(960, 560, 1030, 1160, (255, 255, 255), INK, 8, 18)
    pen.rect(968, 1152 - 584 * h / m, 1022, 1152, (40, 170, 80), None, 0, 14)
    pen.text(990, 505, f"{int(h)} m", 52)


STAIR0, STAIR1 = (110, 1880), (930, 820)


def stairs(img):
    d = ImageDraw.Draw(img); n = 11
    (x0, y0), (x1, y1) = STAIR0, STAIR1
    sw, shh = (x1 - x0) / n, (y0 - y1) / n
    pts = [(x0, y0 + 40)]
    for i in range(n):
        pts += [(x0 + i * sw, y0 - (i + 1) * shh), (x0 + (i + 1) * sw, y0 - (i + 1) * shh)]
    pts += [(x1 + 60, y1), (x1 + 60, y1 + 90), (x0 + 120, y0 + 140), (x0, y0 + 140)]
    d.polygon([(x * S, y * S) for x, y in pts], fill=(178, 176, 170), outline=INK, width=7 * S)
    rail = [(x0 + 10, y0 - 230), (x1 + 40, y1 - 230)]
    d.line([(x * S, y * S) for x, y in rail], fill=INK, width=12 * S)
    for i in range(0, n + 1, 2):
        x = x0 + 10 + i * sw; y = y0 - i * shh
        d.line([(x * S, (y - 230) * S), (x * S, (y - 10) * S)], fill=INK, width=8 * S)


def c_building(img, t, d, sc):
    u = t / d
    st.bg(img, "bg_building", 1.0, 0.5, 0.75)
    stairs(img)
    def on_stair(f):
        f = max(0, min(1, f)); (x0, y0), (x1, y1) = STAIR0, STAIR1
        return x0 + 60 + (x1 - x0 - 60) * f, y0 - (y0 - y1) * f - 20
    pa = on_stair(u * 0.85 - 0.12); actor(img, "a", pa[0], pa[1], 520, [(0, "walk_side", "scared")], t, seed=0.3)
    py = on_stair(u * 0.9); actor(img, "you", py[0], py[1], 600, [(0, "walk_side", "scared")], t)
    water(img, 1930 - st.ease(u) * 470, t)
    head_overlays(img, t, d, sc)


def c_stay(img, t, d, sc):
    u = t / d
    st.bg(img, "bg_hilltop", 1.06 - 0.05 * u, 0.5, 0.6)
    # sea surges into the town again and again
    for i in range(2):
        q = ((t / 3.2) + i * 0.5) % 1.0
        st.put(img, "obj/wave", -150 + q * 1400, 1000, 150 + 40 * math.sin(q * math.pi))
    water(img, 1010 - 30 * math.sin(t * 2.0), t, amp=8, foam=True, bottom=1240, debris=False)
    actor(img, "b", 900, 1760, 560, [(0, "idle")], t, seed=2)
    actor(img, "a", 190, 1780, 600, [(0, "idle")], t, seed=1)
    actor(img, "you", 560, 1880, 900, [(0, "idle", "n"), (d * 0.5, "talk", "n")], t)
    pen = head_overlays(img, t, d, sc)
    st.clock(pen, 870, 560, 100, t / 2.0, (255, 255, 255), sc.get("clock", "HOURS"))


for _k, _v in list(globals().items()):
    if _k.startswith("c_"): st.ACTS[_k] = _v

if __name__ == "__main__":
    st.build(sys.argv[1], sys.argv[2])
