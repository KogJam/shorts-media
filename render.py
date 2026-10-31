"""Render a vertical fact Short (1080x1920) from a JSON spec.

Each line = one scene: voice-over + animated 3D emoji images + optional punch text / counter / bars
+ word-by-word pop captions + whoosh/pop sound effects + soft ambient pad.
"""
import json, math, random, subprocess, sys, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import tts
import clips

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.environ.get("SHORTS_ASSETS", os.path.expanduser("~/tts"))
NOTO = os.path.join(ASSETS, "noto-emoji")
EMOJI_DIRS = ["3D/png/512", "2D/png/512"]
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_X = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
_fc = {}
SR = tts.SR


def font(size):
    size = max(8, int(size))
    if size not in _fc: _fc[size] = ImageFont.truetype(FONT, size)
    return _fc[size]


PALETTES = [  # (bg a, bg b, blob colours..., accent)
    {"a": (10, 12, 38), "b": (52, 16, 84), "blobs": [(120, 60, 255), (255, 70, 160), (0, 200, 255)], "acc": (255, 214, 0)},
    {"a": (4, 26, 40), "b": (6, 74, 92), "blobs": [(0, 230, 200), (40, 120, 255), (255, 140, 80)], "acc": (255, 222, 60)},
    {"a": (30, 8, 20), "b": (90, 24, 40), "blobs": [(255, 90, 60), (255, 190, 40), (200, 40, 160)], "acc": (120, 255, 170)},
    {"a": (8, 20, 12), "b": (14, 66, 50), "blobs": [(60, 220, 120), (0, 160, 255), (255, 230, 90)], "acc": (255, 120, 200)},
]


def clamp01(t): return max(0.0, min(1.0, t))
def ease(t): t = clamp01(t); return 1 - (1 - t) ** 3
def spring(t):
    t = clamp01(t)
    return 1 - math.exp(-6 * t) * math.cos(10 * t) if t < 1 else 1.0


# ---------------- emoji loading ----------------
_emoji_cache, _scaled = {}, {}


def emoji_file(e):
    """Path of the 512px Noto emoji image; fetched on demand from a blobless git clone."""
    cps = [f"{ord(c):x}" for c in e if ord(c) != 0xFE0F]
    if not cps: return None
    for d in EMOJI_DIRS:
        for name in ("emoji_u" + "_".join(cps), "emoji_u" + cps[0]):
            rel = f"{d}/{name}.png"
            p = os.path.join(NOTO, rel)
            if not os.path.exists(p) and os.path.isdir(os.path.join(NOTO, ".git")):
                subprocess.run(["git", "-C", NOTO, "checkout", "HEAD", "--", rel], capture_output=True)
            if os.path.exists(p): return p
    return None


def emoji_img(e, px):
    px = max(4, int(px / 8) * 8)  # quantise sizes for caching
    k = (e, px)
    if k in _scaled: return _scaled[k]
    if e not in _emoji_cache:
        p = emoji_file(e)
        _emoji_cache[e] = Image.open(p).convert("RGBA") if p else None
    src = _emoji_cache[e]
    if src is None: return None
    im = src.resize((px, px), Image.LANCZOS)
    if len(_scaled) > 400: _scaled.clear()
    _scaled[k] = im
    return im


def paste_emoji(img, e, cx, cy, size, rot=0, alpha=1.0, shadow=True):
    if size < 6 or alpha <= 0.01: return
    im = emoji_img(e, size)
    if im is None: return
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if shadow:  # soft drop shadow
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.35)))
        img.alpha_composite(sh, (int(cx - im.width / 2 + size * 0.04), int(cy - im.height / 2 + size * 0.07)))
    img.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ---------------- item animation ----------------
def animate_item(it, t, idx, scene_len):
    """Return (x, y, size, rot, alpha) in pixels for an emoji item at scene time t."""
    x, y = it.get("x", 0.5) * W, it.get("y", 0.42) * H
    size = it.get("size", 0.45) * W
    d = it.get("delay", idx * 0.25)
    lt = t - d
    if lt < 0: return None
    anim = it.get("anim", "pop")
    rot, alpha = 0.0, 1.0
    s = spring(lt / 0.55)
    if anim == "pop":
        size *= s; y += math.sin(lt * 2.2 + idx) * 14
    elif anim == "float":
        size *= ease(lt / 0.5); y += math.sin(lt * 1.8 + idx) * 28; rot = math.sin(lt * 1.3 + idx) * 6
    elif anim == "bounce":
        hop = abs(math.sin(lt * 4.5)) * 70 * math.exp(-lt * 0.3)
        size *= s; y -= hop
    elif anim == "drop":
        k = ease(lt / 0.45); y = -size + (y + size) * k
        if lt > 0.45: y -= abs(math.sin((lt - 0.45) * 9)) * 40 * math.exp(-(lt - 0.45) * 4)
    elif anim in ("swim", "swim_left"):
        dirn = -1 if anim == "swim_left" else 1
        span = W + size
        x = (-size / 2 if dirn > 0 else W + size / 2) + dirn * span * clamp01(lt / max(1.5, scene_len))
        y += math.sin(lt * 5) * 30; rot = math.sin(lt * 5) * 8 * dirn
    elif anim == "spin":
        size *= s; rot = -lt * 90
    elif anim == "shake":
        size *= s; x += math.sin(lt * 55) * 14 * (1 if lt < 1.2 else 0.2); rot = math.sin(lt * 40) * 5
    elif anim == "pulse":
        size *= s * (1 + 0.09 * math.sin(lt * 7))
    elif anim == "zoom":
        size *= 0.6 + 0.6 * ease(lt / max(1.0, scene_len))
    elif anim == "grow":
        size *= ease(lt / max(1.0, scene_len * 0.8))
    elif anim == "rise":
        k = ease(lt / 0.6); y = H + size / 2 - (H + size / 2 - y) * k; y += math.sin(lt * 2) * 12
    elif anim == "orbit":
        r = it.get("radius", 0.3) * W
        a = lt * it.get("speed", 1.6) + idx
        x = W / 2 + r * math.cos(a); y = it.get("cy", 0.42) * H + r * 0.4 * math.sin(a)
        size *= (0.85 + 0.15 * math.sin(a)) * ease(lt / 0.4)
    elif anim == "fade_out":
        alpha = 1 - ease(lt / 0.8); size *= 1 + 0.2 * ease(lt / 0.8)
    if it.get("cross"):  # crossed out / dimmed (e.g. "not this")
        alpha *= 0.45
    return x, y, size, rot, alpha


# ---------------- background ----------------
def make_bg_base(pal):
    a, b = np.array(pal["a"], float), np.array(pal["b"], float)
    g = np.linspace(0, 1, H)[:, None, None]
    return Image.fromarray((a * (1 - g) + b * g).repeat(W, axis=1).astype(np.uint8), "RGB").convert("RGBA")


def make_blob(color, r):
    pad = r
    im = Image.new("RGBA", (r * 2 + pad * 2, r * 2 + pad * 2), (*color, 0))
    ImageDraw.Draw(im).ellipse([pad, pad, pad + r * 2, pad + r * 2], fill=(*color, 110))
    return im.filter(ImageFilter.GaussianBlur(r // 2))


# ---------------- text helpers ----------------
def text_c(d, xy, s, f, fill, anchor="mm", stroke=0, sfill=(0, 0, 0)):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sfill)


def wrap(s, f, maxw, d):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def fmt_num(v, dec=0): return f"{v:,.{dec}f}"


# ---------------- sound ----------------
def sfx_whoosh(dur=0.35):
    n = int(dur * SR); t = np.arange(n) / SR
    noise = np.random.default_rng(1).standard_normal(n)
    # sweep a crude band-pass by mixing differences
    env = np.sin(np.pi * t / dur) ** 2
    hp = np.diff(noise, prepend=0)
    sig = (noise * 0.3 + hp * 0.7) * env
    return (sig / np.abs(sig).max() * 0.18).astype(np.float32)


def sfx_pop():
    n = int(0.09 * SR); t = np.arange(n) / SR
    f = 900 * np.exp(-t * 30) + 300
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45)
    return (sig * 0.22).astype(np.float32)


def ambient(dur, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    root = rng.choice([110, 123.47, 130.81, 146.83, 98])
    chord = [root, root * 1.25, root * 1.5, root * 2, root * 3]
    pad = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) * (0.5 + 0.5 * np.sin(2 * np.pi * (0.06 + 0.025 * i) * t)) for i, f in enumerate(chord)) / len(chord)
    beat = (np.sin(2 * np.pi * 2.0 * t) > 0.95).astype(float) * np.sin(2 * np.pi * 55 * t) * 0.6  # soft pulse
    env = np.minimum(1, t / 1.0) * np.minimum(1, (dur - t) / 1.2)
    return ((pad + beat * 0.5) * env * 0.07).astype(np.float32)


def add_at(buf, clip, t):
    i = int(t * SR)
    if i >= len(buf): return
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[: j - i]


# ---------------- main render ----------------
def render(spec_path, out_path, voice=None):
    spec = json.load(open(spec_path))
    seed = sum(map(ord, spec.get("id", spec_path))) % 10_000
    rng = random.Random(seed)
    pal = PALETTES[seed % len(PALETTES)]
    voice = voice or spec.get("voice", "am_michael")
    acc = pal["acc"]

    # 1) voice + timings
    segs, t0 = [], 0.25
    vparts = [np.zeros(int(0.25 * SR), np.float32)]
    for ln in spec["lines"]:
        a = tts.synth(ln["say"], voice=voice, speed=spec.get("speed", 1.12))
        dur = len(a) / SR
        words = ln.get("caption", ln["say"]).split()
        wts = np.array([len(w.strip(".,!?")) + 2.5 for w in words], float)
        cum = np.concatenate([[0], np.cumsum(wts)]) / wts.sum() * dur
        segs.append({"start": t0, "voice_end": t0 + dur, "line": ln,
                     "words": [(w, t0 + cum[i], t0 + cum[i + 1]) for i, w in enumerate(words)]})
        gap = 0.18
        vparts += [a, np.zeros(int(gap * SR), np.float32)]
        t0 += dur + gap
    for i, s in enumerate(segs):
        s["end"] = segs[i + 1]["start"] if i + 1 < len(segs) else t0 + 0.9
    total = t0 + 0.9
    voice_a = np.concatenate(vparts + [np.zeros(int(0.9 * SR) + SR, np.float32)])[: int(total * SR)]

    # 2) audio mix: voice + pad + sfx
    mix = voice_a.copy()
    mix += ambient(total, seed)[: len(mix)]
    wh, pp = sfx_whoosh(), sfx_pop()
    for i, s in enumerate(segs):
        if i: add_at(mix, wh, s["start"] - 0.12)
        for k, it in enumerate(s["line"].get("items", [])):
            if it.get("anim", "pop") in ("pop", "bounce", "spin", "shake", "pulse", "drop"):
                add_at(mix, pp, s["start"] + it.get("delay", k * 0.25) + (0.4 if it.get("anim") == "drop" else 0.02))
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
    wav = out_path + ".wav"
    with wave.open(wav, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((mix * 32767).astype(np.int16).tobytes())

    # 3) frames
    base = make_bg_base(pal)
    blobs = [(make_blob(c, rng.randint(260, 380)), rng.random() * 6.28, rng.uniform(0.15, 0.35)) for c in pal["blobs"]]
    stars = [(rng.random() * W, rng.random() * H, rng.uniform(1.5, 4.5), rng.uniform(8, 35)) for _ in range(40)]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path], stdin=subprocess.PIPE)
    hook = spec.get("hook", "")
    nframes = int(total * FPS)
    readers, cur_si = {}, -1
    # dark gradient over stock footage so text stays readable
    g = np.concatenate([np.linspace(0.75, 0.25, int(H * 0.3)), np.full(int(H * 0.35), 0.25), np.linspace(0.25, 0.85, H - int(H * 0.3) - int(H * 0.35))])
    shade = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), np.repeat((g * 255).astype(np.uint8)[:, None], W, 1)]), "RGBA")
    INS, BORDER = 560, 14
    ins_mask = Image.new("L", (INS, INS), 0); ImageDraw.Draw(ins_mask).rounded_rectangle([0, 0, INS - 1, INS - 1], radius=48, fill=255)
    ins_border = Image.new("RGBA", (INS + 2 * BORDER, INS + 2 * BORDER), (0, 0, 0, 0))
    ImageDraw.Draw(ins_border).rounded_rectangle([0, 0, INS + 2 * BORDER - 1, INS + 2 * BORDER - 1], radius=58, fill=(255, 255, 255, 255))
    for fi in range(nframes):
        t = fi / FPS
        si = max(0, sum(1 for s in segs if s["start"] <= t) - 1)
        seg = segs[si]
        st = t - seg["start"]
        slen = seg["end"] - seg["start"]
        ln = seg["line"]

        # --- background: stock clip if available, else animated gradient ---
        if si != cur_si:
            for r in readers.values(): r.close()
            readers.clear(); cur_si = si
            if ln.get("clip_path"):
                readers["bg"] = clips.ClipReader(ln["clip_path"], W, H, FPS, ln.get("clip_start", 0), ln.get("clip_speed", 1.0))
            if ln.get("inset_path"):
                readers["inset"] = clips.ClipReader(ln["inset_path"], INS, INS, FPS, ln.get("inset_start", 0))
        fr = readers["bg"].frame() if "bg" in readers else None
        if fr:
            img = Image.frombytes("RGBA", (W, H), fr)
            img.alpha_composite(shade)
            d = ImageDraw.Draw(img, "RGBA")
        else:
            img = base.copy()
            for k, (bl, ph, sp) in enumerate(blobs):  # drifting colour blobs
                bx = W / 2 + math.cos(t * sp + ph) * 380 - bl.width / 2
                by = H * (0.25 + 0.25 * k) + math.sin(t * sp * 1.3 + ph) * 260 - bl.height / 2
                img.alpha_composite(bl, (int(bx), int(by)))
            d = ImageDraw.Draw(img, "RGBA")
            for (px, py, r, sp) in stars:
                y = (py - t * sp) % H
                d.ellipse([px - r, y - r, px + r, y + r], fill=(255, 255, 255, 50))

        # --- inset clip card (like a little GIF / reaction window) ---
        fr2 = readers["inset"].frame() if "inset" in readers else None
        if fr2:
            k = spring((st - ln.get("inset_delay", 0.3)) / 0.5)
            if k > 0.05:
                card = Image.frombytes("RGBA", (INS, INS), fr2)
                card.putalpha(ins_mask)
                framed = ins_border.copy(); framed.alpha_composite(card, (BORDER, BORDER))
                sz = int((INS + 2 * BORDER) * k)
                framed = framed.resize((sz, sz), Image.BILINEAR).rotate(ln.get("inset_tilt", -5) + math.sin(t * 2) * 1.5, resample=Image.BILINEAR, expand=True)
                cx, cy = ln.get("inset_x", 0.5) * W, ln.get("inset_y", 0.42) * H + math.sin(t * 1.7) * 10
                img.alpha_composite(framed, (int(cx - framed.width / 2), int(cy - framed.height / 2)))
                d = ImageDraw.Draw(img, "RGBA")

        # camera: gentle push-in during each scene + punch at scene start
        cam = 1.0 + 0.05 * ease(st / slen) + 0.06 * max(0, 1 - st / 0.25)

        # scene items (3D images)
        for k, it in enumerate(ln.get("items", [])):
            r = animate_item(it, st, k, slen)
            if not r: continue
            x, y, size, rot, alpha = r
            x = W / 2 + (x - W / 2) * cam; y = H * 0.45 + (y - H * 0.45) * cam
            paste_emoji(img, it["emoji"], x, y, size * cam, rot, alpha)
            if it.get("cross") and alpha > 0.1:
                s2 = size * cam * 0.5
                d.line([x - s2, y - s2, x + s2, y + s2], fill=(255, 60, 60), width=22)
                d.line([x - s2, y + s2, x + s2, y - s2], fill=(255, 60, 60), width=22)

        # counter
        if "number" in ln:
            nb = ln["number"]
            v = nb["value"] * ease((st - nb.get("delay", 0.2)) / 1.3)
            s = nb.get("prefix", "") + fmt_num(v, nb.get("decimals", 0)) + nb.get("suffix", "")
            sz = (200 if len(s) <= 6 else 150 if len(s) <= 9 else 110) * spring(st / 0.5) * cam
            text_c(d, (W / 2, nb.get("y", 0.6) * H), s, font(sz), acc, stroke=8)
            if nb.get("label"):
                text_c(d, (W / 2, nb.get("y", 0.6) * H + 130), nb["label"], font(56), (255, 255, 255), stroke=5)

        # comparison bars
        if "bars" in ln:
            items = ln["bars"][:4]
            mx = max(b["value"] for b in items) or 1
            bw, gap = 800, 170
            top = ln.get("bars_y", 0.56) * H - (len(items) - 1) * gap / 2
            for i, b in enumerate(items):
                y = top + i * gap
                k = ease((st - 0.2 - 0.25 * i) / 1.0)
                x0 = (W - bw) / 2 + 70
                if b.get("emoji"): paste_emoji(img, b["emoji"], x0 - 90, y + 35, 120 * spring((st - 0.25 * i) / 0.5), shadow=False)
                d.rounded_rectangle([x0, y + 10, x0 + bw - 70, y + 64], radius=27, fill=(255, 255, 255, 45))
                d.rounded_rectangle([x0, y + 10, x0 + max(54, (bw - 70) * b["value"] / mx * k), y + 64], radius=27, fill=acc if i == 0 else pal["blobs"][2])
                text_c(d, (x0, y - 24), b["label"], font(46), (255, 255, 255), anchor="lm", stroke=3)
                text_c(d, (x0 + bw - 70, y - 24), b.get("show", fmt_num(b["value"] * k)), font(46), (255, 255, 255), anchor="rm", stroke=3)

        # punch text
        if ln.get("punch"):
            ptxt = ln["punch"]
            pd = ln.get("punch_delay", 0.15)
            sc = spring((st - pd) / 0.4)
            if sc > 0.02:
                lines = wrap(ptxt, font(120), 960, d)
                py = ln.get("punch_y", 0.66) * H
                for i, L in enumerate(lines):
                    rot_jit = math.sin(t * 30) * 4 * max(0, 1 - (st - pd) / 0.3)
                    text_c(d, (W / 2 + rot_jit, py + (i - (len(lines) - 1) / 2) * 135), L, font(120 * sc), acc, stroke=9)

        # hook banner (top) – big slam for first scene, small afterwards
        if hook:
            if si == 0 and st < seg["voice_end"] - seg["start"]:
                sc = spring(st / 0.35)
                for i, L in enumerate(wrap(hook, font(92), 960, d)):
                    text_c(d, (W / 2 + math.sin(t * 40) * 6 * max(0, 1 - st / 0.4), 300 + i * 110), L, font(92 * sc), (255, 255, 255), stroke=8)
            else:
                for i, L in enumerate(wrap(hook, font(54), 940, d)):
                    d.text((W / 2, 190 + i * 66), L, font=font(54), fill=(255, 255, 255, 230), anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))

        # captions: chunks of up to 3 words, active word highlighted & popped
        words = seg["words"]
        act = max(0, sum(1 for w in words if w[1] <= t) - 1)
        if t <= seg["voice_end"] + 0.15:
            chunks, cur = [], []
            for w in words:
                cur.append(w)
                if len(cur) == 3 or w[0][-1] in ".,!?": chunks.append(cur); cur = []
            if cur: chunks.append(cur)
            ch = next(c for c in chunks if words[act] in c)
            fsz = 88
            f = font(fsz)
            widths = [d.textlength(w[0].upper(), font=f) for w in ch]
            totw = sum(widths) + 26 * (len(ch) - 1)
            scale = min(1.0, 980 / totw)
            x = (W - totw * scale) / 2
            cy = 1500
            for w, wd in zip(ch, widths):
                on = w is words[act]
                pop = 1 + 0.15 * max(0, 1 - (t - w[1]) / 0.15) if on else 1
                fw = font(fsz * scale * pop)
                d.text((x + wd * scale / 2, cy), w[0].upper(), font=fw, anchor="mm", fill=acc if on else (255, 255, 255),
                       stroke_width=9, stroke_fill=(0, 0, 0))
                x += (wd + 26) * scale

        # progress bar + flash at scene change
        d.rounded_rectangle([40, 70, 40 + (W - 80) * t / total, 84], radius=7, fill=acc)
        if si > 0 and st < 0.08:
            d.rectangle([0, 0, W, H], fill=(255, 255, 255, int(110 * (1 - st / 0.08))))
        if t > total - 1.1:
            a = int(255 * ease((t - (total - 1.1)) / 0.35))
            text_c(d, (W / 2, 1760), "FOLLOW FOR DAILY FACTS", font(56), (*acc, a), stroke=6)
        ff.stdin.write(img.tobytes())
    for r in readers.values(): r.close()
    ff.stdin.close(); ff.wait()
    os.remove(wav)
    return total


def prepare(spec_path):
    """Resolve "clip"/"inset" search queries into downloaded stock clips (Pexels). Writes credits into the spec."""
    spec = json.load(open(spec_path))
    used, credits = set(), []
    for ln in spec["lines"]:
        for key in ("clip", "inset"):
            q = ln.get(key)
            if ln.get(key + "_id") and not ln.get(key + "_path"):
                path, c = clips.get_by_id(ln[key + "_id"])
                if path:
                    ln[key + "_path"] = path; used.add(c["id"])
                    credits.append(f"{c['user']} (Pixabay): {c['page']}")
                    continue
            if q and not ln.get(key + "_path"):
                path, c = clips.get_clip(q, used, "portrait" if key == "clip" else "square")
                if not path and key == "inset":
                    path, c = clips.get_clip(q, used, "portrait")
                if path:
                    ln[key + "_path"] = path
                    credits.append(f"{c['user']} (Pixabay): {c['page']}")
                else:
                    print(f"no clip found for {key}: {q!r}")
    spec["credits"] = credits
    json.dump(spec, open(spec_path, "w"), indent=1, ensure_ascii=False)
    return spec


def check(spec_path):
    spec = json.load(open(spec_path))
    problems = []
    miss = tts.missing_words(" ".join(l["say"] for l in spec["lines"]))
    if miss: problems.append(f"words not in pronunciation dictionary: {miss}")
    for l in spec["lines"]:
        for it in l.get("items", []) + l.get("bars", []):
            if it.get("emoji") and not emoji_file(it["emoji"]): problems.append(f"no image for emoji {it['emoji']!r}")
    return problems


if __name__ == "__main__":
    spec, out = sys.argv[1], sys.argv[2]
    if os.environ.get("PIXABAY_API_KEY") or os.environ.get("PEXELS_API_KEY"): prepare(spec)
    for p in check(spec): print("WARNING:", p)
    print("duration", round(render(spec, out), 2))
