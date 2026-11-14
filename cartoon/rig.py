#!/usr/bin/env python3
"""Cut-out puppet rig: AI-drawn head expressions + torso, procedural jointed arms/legs (tube limbs, same outline style),
AI-drawn hands/shoes attached at the joints.  Front view and side view (facing right; flip for left).

extract(char_dir): needs body_front.png + heads.png in char_dir (green screen), writes parts + rig.json.
Rig(char_dir).draw(img, x, feet_y, height, pose, S)   pose = dict from poses.py
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sprites import key, main as split_sheet

# reference layout of an A-pose front body (measured on the generated 768x1376 sheet; all chars use the same prompt)
REF = dict(top=84, bottom=1303, neck=(385, 415), head_w=300,
           torso_box=(228, 398, 542, 862), torso_cols_low=(256, 512), torso_split_y=468,
           sh_l=(286, 500), sh_r=(484, 500), up_arm=165, fore_arm=118, arm_w=60, sleeve_w=80, sleeve_len=62,
           hip_l=(318, 820), hip_r=(452, 820), thigh=180, shin=190, thigh_w=104, shin_w=68,
           hand_l_box=(50, 728, 156, 848), wrist_l=(128, 742), hand_tip_l=(88, 832),
           hand_r_box=(612, 728, 718, 848), wrist_r=(640, 742), hand_tip_r=(680, 832),
           shoe_l_box=(185, 1178, 355, 1306), ankle_l=(312, 1190), shoe_r_box=(415, 1178, 585, 1306), ankle_r=(455, 1190))


def _col(px): return tuple(int(v) for v in np.median(px, axis=0)[:3])


def extract(cdir):
    a = key(np.array(Image.open(os.path.join(cdir, "body_front.png")).convert("RGB")))
    R = REF
    # normalise: scale/shift so the figure's bbox matches the reference layout
    ys, xs = np.where(a[..., 3] > 128); t0, b0 = ys.min(), ys.max()
    rows = a[int(t0 + (b0 - t0) * 0.62):int(t0 + (b0 - t0) * 0.8), :, 3] > 128
    cx = np.where(rows.any(0))[0].mean()
    sc = (R["bottom"] - R["top"]) / (b0 - t0)
    big = Image.fromarray(a).resize((int(a.shape[1] * sc), int(a.shape[0] * sc)), Image.LANCZOS)
    can = Image.new("RGBA", (768, 1376)); can.paste(big, (int(385 - cx * sc), int(R["top"] - t0 * sc)))
    a = np.array(can); im = can
    # torso: shoulders full width above split_y, body columns only below (sleeves removed)
    x0, y0, x1, y1 = R["torso_box"]
    t = a[y0:y1, x0:x1].copy()
    c0, c1 = R["torso_cols_low"]; sy = R["torso_split_y"] - y0
    t[sy:, : c0 - x0, 3] = 0; t[sy:, c1 - x0:, 3] = 0
    # cut the sleeve triangles at the shoulder corners too
    for yy in range(0, sy):
        f = yy / max(sy, 1)
        lcut = int((c0 - x0) * f); t[yy, :lcut, 3] = 0; t[yy, t.shape[1] - lcut:, 3] = 0
    Image.fromarray(t).save(os.path.join(cdir, "torso.png"))
    for side in "lr":
        bx = R[f"hand_{side}_box"]; im.crop(bx).save(os.path.join(cdir, f"hand_{side}.png"))
        bx = R[f"shoe_{side}_box"]; im.crop(bx).save(os.path.join(cdir, f"shoe_{side}.png"))
    op = a[..., 3] > 200; rgb = a[..., :3].astype(int)
    def region(x0, y0, x1, y1):
        m = op[y0:y1, x0:x1]; return rgb[y0:y1, x0:x1][m]
    cols = dict(shirt=_col(region(330, 600, 440, 700)), shorts=_col(region(290, 880, 350, 960)),
                skin=_col(region(290, 1040, 330, 1140)))
    px = rgb[op]; s = px.sum(1); cols["ink"] = _col(px[s < np.percentile(s, 3)])
    split_sheet(os.path.join(cdir, "heads.png"), cdir, ["f_n", "f_blink", "f_scared", "f_happy", "s_n", "s_scared"])
    json.dump(cols, open(os.path.join(cdir, "rig.json"), "w"))
    print("extracted", cdir, cols)


def chaikin(pts, n=3):
    for _ in range(n):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        pts = out
    return pts


def shade(c, f): return tuple(max(0, min(255, int(v * f))) for v in c)


class Rig:
    def __init__(s, cdir):
        s.dir = cdir; s.cols = json.load(open(os.path.join(cdir, "rig.json")))
        s.img = {}
        for n in ["torso", "hand_l", "hand_r", "shoe_l", "shoe_r", "f_n", "f_blink", "f_scared", "f_happy", "s_n", "s_scared"]:
            s.img[n] = Image.open(os.path.join(cdir, n + ".png")).convert("RGBA")
        s.cache = {}
        R = REF
        s.hand_ang = {sd: math.atan2(R[f"hand_tip_{sd}"][0] - R[f"wrist_{sd}"][0], R[f"hand_tip_{sd}"][1] - R[f"wrist_{sd}"][1]) for sd in "lr"}

    # -- sprite helpers: scaled + rotated around a pivot, cached
    def _rot(s, name, scale, ang_deg, pivot, flip=False):
        k = (name, round(scale, 3), int(round(ang_deg)) % 360, flip)
        if k in s.cache: return s.cache[k]
        im = s.img[name]
        if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT); pivot = (im.width - pivot[0], pivot[1])
        w, h = max(1, int(im.width * scale)), max(1, int(im.height * scale))
        im = im.resize((w, h), Image.LANCZOS); px, py = pivot[0] * scale, pivot[1] * scale
        r = int(math.hypot(max(px, w - px), max(py, h - py))) + 2
        can = Image.new("RGBA", (2 * r, 2 * r)); can.paste(im, (int(r - px), int(r - py)))
        if int(round(ang_deg)) % 360: can = can.rotate(ang_deg, resample=Image.BICUBIC, center=(r, r))
        s.cache[k] = (can, r)
        if len(s.cache) > 4000: s.cache.clear()
        return can, r

    def _paste(s, img, name, scale, ang, pivot, at, flip=False):
        can, r = s._rot(name, scale, math.degrees(ang), pivot, flip)
        img.paste(can, (int(at[0] - r), int(at[1] - r)), can)

    @staticmethod
    def _tube(d, pts, w, fill, ink, ol):
        d.line(pts, fill=ink, width=int(w + 2 * ol), joint="curve")
        for (x, y) in pts:
            rr = (w + 2 * ol) / 2; d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=ink)
        d.line(pts, fill=fill, width=int(w), joint="curve")
        for (x, y) in pts:
            rr = w / 2; d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)

    @staticmethod
    def _seg(p, a, L): return (p[0] + L * math.sin(a), p[1] + L * math.cos(a))

    def draw(s, img, x, feet_y, height, pose, S=2, view="front", face=1, expr="n", blink=False):
        """x, feet_y in logical px; height = full figure height in logical px. pose keys:
        la/ra = (shoulder, elbow) abs angles, ll/rl = (hip, knee) abs angles, lean, bob, head (tilt rad), hand/shoe flags."""
        R = REF; k = height * S / (R["bottom"] - R["top"]); d = ImageDraw.Draw(img)
        ink = tuple(s.cols["ink"]); ol = 7 * k
        flip = face < 0 and view == "side"
        f = -1 if flip else 1
        bob = pose.get("bob", 0) * S * height / 780; lean = pose.get("lean", 0) * f
        X = x * S; Y = feet_y * S + bob
        def P(px, py):  # reference px -> screen, relative to feet centre, before lean
            return (X + (px - 385) * k * (f if view == "front" else 1), Y + (py - R["bottom"]) * k)
        pelvis = P(385, 820)
        def L(pt):     # apply torso lean around pelvis
            dx, dy = pt[0] - pelvis[0], pt[1] - pelvis[1]; c, sn = math.cos(lean), math.sin(lean)
            return (pelvis[0] + dx * c - dy * sn * -1 * 0 + dy * sn, pelvis[1] - dx * sn * 0 + dy * c) if False else \
                   (pelvis[0] + dx * c - dy * sn, pelvis[1] + dx * sn + dy * c)
        lean_a = -lean   # for limbs: rotating torso by lean moves "down" direction
        sh_w = (R["sh_r"][0] - R["sh_l"][0])
        if view == "side":
            sh = {"l": L(P(385, 505)), "r": L(P(385, 505))}
            hip = {"l": P(385, 830), "r": P(385, 830)}
        else:
            sh = {"l": L(P(*R["sh_l"])), "r": L(P(*R["sh_r"]))}
            hip = {"l": P(*R["hip_l"]), "r": P(*R["hip_r"])}
        if flip: sh = {"l": sh["l"], "r": sh["r"]}
        cols = s.cols

        def leg(sd):
            a1, a2 = pose[sd + "l"]; a1 *= f; a2 *= f
            h0 = hip[sd]; kn = s._seg(h0, a1, R["thigh"] * k); an = s._seg(kn, a2, R["shin"] * k)
            s._tube(d, [kn, an], R["shin_w"] * k, tuple(cols["skin"]), ink, ol)
            s._tube(d, [h0, s._seg(h0, a1, R["thigh"] * k * 1.02)], R["thigh_w"] * k, tuple(cols["shorts"]), ink, ol)
            shoe = ("shoe_r" if view == "side" else f"shoe_{sd}")
            piv = (R[f"ankle_{'r' if view == 'side' else sd}"][0] - R[f"shoe_{'r' if view == 'side' else sd}_box"][0],
                   R[f"ankle_{'r' if view == 'side' else sd}"][1] - R[f"shoe_{'r' if view == 'side' else sd}_box"][1])
            sa = pose.get("foot", 0) * f + (a2 * 0.35 if view == "side" else 0)
            s._paste(img, shoe, k * 1.0, sa, piv, an, flip=flip)
            d2 = ImageDraw.Draw(img); return d2

        def arm(sd):
            a1, a2 = pose[sd + "a"]; a1 = a1 * f + lean_a * 0; a2 = a2 * f
            s0 = sh[sd]; el = s._seg(s0, a1, R["up_arm"] * k); wr = s._seg(el, a2, R["fore_arm"] * k)
            s._tube(d, [s0, el], R["arm_w"] * k, tuple(cols["skin"]), ink, ol)
            s._tube(d, [el, wr], R["arm_w"] * k * 0.95, tuple(cols["skin"]), ink, ol)
            hn = "hand_r" if (view == "side") else f"hand_{sd}"
            hs = "r" if view == "side" else sd
            piv = (R[f"wrist_{hs}"][0] - R[f"hand_{hs}_box"][0], R[f"wrist_{hs}"][1] - R[f"hand_{hs}_box"][1])
            ha = s.hand_ang[hs] * (f if view == "side" else 1)
            s._paste(img, hn, k * 0.95, a2 - ha, piv, wr, flip=flip)
            dd = ImageDraw.Draw(img)
            sl = s._seg(s0, a1, R["sleeve_len"] * k)
            s._tube(dd, [s0, sl], R["sleeve_w"] * k, tuple(cols["shirt"]), ink, ol)
            return dd

        order_far = ("l",) if view == "side" else ()
        # far limbs first (side view), then legs, torso, arms, head
        if view == "side":
            d = arm("l"); d = leg("l"); d = leg("r")
        else:
            d = leg("l"); d = leg("r")
        # torso
        if view == "front":
            x0, y0, x1, y1 = R["torso_box"]
            piv = (385 - x0, 820 - y0)
            s._paste(img, "torso", k, lean, piv, pelvis)
        else:
            d = ImageDraw.Draw(img)
            shorts = chaikin([P(300, 760), P(470, 760), P(466, 880), P(302, 880)], 2)
            d.polygon(shorts, fill=tuple(cols["shorts"]), outline=ink, width=int(ol * 2))
            body = [L(P(*q)) for q in [(345, 418), (425, 418), (468, 455), (482, 520), (484, 790), (296, 790), (292, 520), (305, 455)]]
            body = chaikin(body)
            d.polygon(body, fill=tuple(cols["shirt"]), outline=ink, width=int(ol * 2))
        d = ImageDraw.Draw(img)
        if view == "side":
            d = arm("r")
        else:
            d = arm("l"); d = arm("r")
        # head
        neck = L(P(385, 418))
        hn = ("s_" if view == "side" else "f_") + ("blink" if (blink and view == "front") else expr if (expr in ("n", "scared") or view == "front") else "n")
        if view == "side" and expr == "scared": hn = "s_scared"
        hi = s.img[hn]; hs = (R["head_w"] * k) / (hi.width if view == "front" else hi.width * 1.0)
        hs *= 1.0 if view == "front" else 0.86
        piv = (hi.width * (0.5 if view == "front" else 0.62), hi.height * 0.97)
        s._paste(img, hn, hs, lean + pose.get("head", 0) * f, piv, neck, flip=flip)


if __name__ == "__main__":
    extract(sys.argv[1])
