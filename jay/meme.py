#!/usr/bin/env python3
"""jay.vs.life meme shorts: AI-rendered 3D stills (jay/gen3d.py) + camera moves, caption boxes, SFX, original music bed.
Usage: python3 jay/meme.py spec.json out.mp4
Spec: {"hook": "When your friend says he's 5 min away",
       "scenes": [{"img": "out/jay/s1.png", "dur": 2.0, "label": "1 hour later...", "move": "push|pull|pan_l|pan_r|shake|snap",
                   "sfx": "whoosh|pop|impact|ding|none"}], "music_seed": 3}
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import render as R

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
YEL, INK, WHITE = (255, 214, 64), (28, 24, 32), (255, 255, 255)
_f = {}


def font(px):
    if px not in _f: _f[px] = ImageFont.truetype(FONT, px)
    return _f[px]


def ease(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3


def wrap(text, f, maxw, d):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def box(img, text, cy, size, fill, fg, scale=1.0, tilt=0, maxw=900):
    """Rounded caption box with drop shadow, centered at cy, popped in by `scale`."""
    if scale <= 0.01: return
    f = font(size); d0 = ImageDraw.Draw(img)
    lines = wrap(text, f, maxw, d0); lh = int(size * 1.18)
    tw = max(d0.textlength(l, font=f) for l in lines)
    bw, bh = int(tw + size * 1.2), int(lh * len(lines) + size * 0.7)
    layer = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    d.rounded_rectangle([24, 28, bw + 24, bh + 28], radius=int(size * 0.45), fill=(0, 0, 0, 90))
    d.rounded_rectangle([16, 16, bw + 16, bh + 16], radius=int(size * 0.45), fill=fill + (255,), outline=INK, width=6)
    for i, l in enumerate(lines):
        d.text((16 + bw / 2, 16 + size * 0.35 + lh * i + lh / 2), l, font=f, fill=fg, anchor="mm")
    if tilt: layer = layer.rotate(tilt, resample=Image.BICUBIC, expand=True)
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.LANCZOS)
    img.alpha_composite(layer, (int(W / 2 - layer.width / 2), int(cy - layer.height / 2)))


def pop(t, d=0.25):
    if t <= 0: return 0
    if t >= d: return 1
    x = t / d; return 1 + 0.18 * math.sin(math.pi * x) * (1 - x) * 3 if x > 0.5 else ease(x * 2) * 1.12


def base_img(path):
    im = Image.open(os.path.join(ROOT, path) if not os.path.isabs(path) else path).convert("RGB")
    s = max(W * 1.15 / im.width, H * 1.15 / im.height)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def camera(src, move, t, dur):
    p = ease(t / dur) if move != "snap" else ease(min(1, t / 0.18))
    z, dx, dy = 1.0, 0.0, 0.0
    if move == "push": z = 1.0 + 0.08 * p
    elif move == "pull": z = 1.08 - 0.08 * p
    elif move == "pan_l": dx = -0.05 * (p - 0.5); z = 1.04
    elif move == "pan_r": dx = 0.05 * (p - 0.5); z = 1.04
    elif move == "snap": z = 1.18 - 0.12 * p + 0.03 * ease(t / dur)
    elif move == "shake":
        z = 1.05; a = 0.012 * max(0, 1 - t / 0.6)
        dx, dy = a * math.sin(t * 70), a * math.cos(t * 53)
    k = min(src.width / W, src.height / H) / 1.08 / z
    cw, ch = W * k, H * k
    cx, cy = src.width / 2 + dx * src.width, src.height / 2 + dy * src.height
    crop = src.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
    return crop.resize((W, H), Image.BILINEAR)


def build(spec_path, out):
    sp = json.load(open(spec_path))
    scenes = sp["scenes"]; total = sum(s["dur"] for s in scenes)
    srcs = [base_img(s["img"]) for s in scenes]
    tmp = out + ".video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    n = int(round(total * FPS)); starts = np.cumsum([0] + [s["dur"] for s in scenes])
    for i in range(n):
        t = i / FPS; k = min(len(scenes) - 1, int(np.searchsorted(starts, t, side="right") - 1))
        sc, lt = scenes[k], t - starts[k]
        frame = camera(srcs[k], sc.get("move", "push"), lt, sc["dur"]).convert("RGBA")
        if lt < 0.08 and k > 0:                                     # white flash on cut
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - lt / 0.08)))))
        box(frame, sp["hook"], 250, 64, WHITE, INK, scale=pop(t if k == 0 else 1), maxw=860)
        if sc.get("label"):
            box(frame, sc["label"], 1540, 70, YEL, INK, scale=pop(lt - 0.12), tilt=sc.get("tilt", -2), maxw=880)
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    # audio: original upbeat bed + sfx at each cut
    SR = R.SR; bed = R.upbeat(total + 0.5, sp.get("music_seed", 3))[: int(total * SR)] * 0.55
    fx = {"whoosh": R.sfx_whoosh, "pop": R.sfx_pop, "impact": R.sfx_impact, "ding": R.sfx_ding}
    for k, s in enumerate(scenes):
        nm = s.get("sfx", "whoosh" if k else "pop")
        if nm in fx: R.add_at(bed, fx[nm]() * 3.0, starts[k] + (0.12 if nm == "pop" else 0))
        if s.get("label") and nm != "pop": R.add_at(bed, R.sfx_pop() * 2.5, starts[k] + 0.12)
    wav = out + ".wav"; R._write_wav(wav, bed / max(1e-6, np.abs(bed).max()) * 0.9)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", out], check=True)
    os.remove(tmp); os.remove(wav)
    print("duration", round(total, 2), out)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
