"""Render a vertical fact Short (1080x1920) from a JSON spec.

Each line = one scene: voice-over + animated 3D emoji images + optional punch text / counter / bars
+ word-by-word pop captions + sound design (whoosh, pop, impact, ding) + original music bed ("music": "calm"|"upbeat").
Transitions: new scene = eased push (slide), mid-scene cut = zoom-dissolve (no white flashes).
Pacing: scenes longer than ~3 s get a mid-scene cut ("clip2_id" = second clip, otherwise a jump cut into the same clip),
and the footage gets a camera (push-in, snap zoom at cuts, shake on punch words). "cuts": false / "sfx": false switch off.
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
def _write_wav(path, a, sr=SR):
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def master_audio(voice, bed, out_wav):
    """Broadcast-style chain: voice cleaned (HPF, de-mud, presence, de-ess, compression), bed in stereo with a little
    room, ducked under the voice (sidechain), whole mix loudness-normalised to -14 LUFS / -1.5 dBTP, 48 kHz stereo."""
    vw, bw = out_wav + ".voice.wav", out_wav + ".bed.wav"
    _write_wav(vw, voice / max(1e-6, np.abs(voice).max()) * 0.9)
    _write_wav(bw, bed / max(1e-6, np.abs(bed).max()) * 0.9)
    fc = ("[0:a]aresample=48000,highpass=f=70,lowpass=f=10500,bass=g=3:f=130:w=0.7,"
          "equalizer=f=2800:t=q:w=1.5:g=-3,equalizer=f=7000:t=q:w=1.2:g=-3,deesser=i=0.7:m=0.7:f=0.35,"
          "acompressor=threshold=-18dB:ratio=1.8:attack=15:release=200:makeup=2,"
          "alimiter=limit=0.95,volume=0.84,pan=stereo|c0=c0|c1=c0,asplit=2[v][sc];"
          "[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,aecho=0.8:0.6:60|110:0.22|0.14,"
          "highpass=f=45,lowpass=f=7000,volume=0.40[b0];"
          "[b0][sc]sidechaincompress=threshold=0.03:ratio=5:attack=25:release=350[b];"
          "[v][b]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-2:LRA=9,aresample=48000[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vw, "-i", bw, "-filter_complex", fc, "-map", "[o]",
                    "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out_wav], check=True)
    os.remove(vw); os.remove(bw)


def sfx_whoosh(dur=0.35):
    n = int(dur * SR); t = np.arange(n) / SR
    noise = np.random.default_rng(1).standard_normal(n)
    # sweep a crude band-pass by mixing differences
    env = np.sin(np.pi * t / dur) ** 2
    k = np.exp(-np.arange(24) / 6.0); k /= k.sum()
    lp = np.convolve(noise, k, mode="same")          # soft, airy noise
    sig = lp * env * (0.6 + 0.4 * np.sin(np.pi * t / dur))
    return (sig / np.abs(sig).max() * 0.12).astype(np.float32)


def sfx_pop():
    n = int(0.09 * SR); t = np.arange(n) / SR
    f = 900 * np.exp(-t * 30) + 300
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45)
    return (sig * 0.22).astype(np.float32)


def sfx_ding():
    """Bright two-tone chime for a finished counter."""
    n = int(0.6 * SR); t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * 1318.5 * t) + 0.6 * np.sin(2 * np.pi * 1975.5 * t) * (t > 0.07)) * np.exp(-t * 7)
    return (sig * 0.10).astype(np.float32)


def sfx_impact():
    """Short low thump + click for punch words (felt more than heard)."""
    n = int(0.25 * SR); t = np.arange(n) / SR
    f = 120 * np.exp(-t * 18) + 45
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16)
    click = np.random.default_rng(3).standard_normal(n) * np.exp(-t * 300) * 0.3
    return ((body + click) * 0.28).astype(np.float32)


def _kick():
    n = int(0.22 * SR); t = np.arange(n) / SR
    f = 110 * np.exp(-t * 30) + 48
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)).astype(np.float32)


def _noise_hit(dur, decay, seed, smooth=1):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.random.default_rng(seed).standard_normal(n)
    if smooth > 1: x = np.convolve(x, np.ones(smooth) / smooth, mode="same")
    x = x - np.convolve(x, np.ones(8) / 8, mode="same")     # crude high-pass -> crisp
    return (x * np.exp(-t * decay)).astype(np.float32)


def upbeat(dur, seed):
    """Light, original, energetic bed (no samples, no existing melody): ~100-110 bpm soft kick, off-beat hats,
    claps on 2 & 4, plucky chord stabs and a bouncing bass. Stays under the voice (master_audio ducks it)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(dur * SR) + SR * 4, np.float32)
    root = int(rng.choice([57, 60, 62, 55, 53]))
    prog = [[0, 4, 7, 11], [-3, 0, 4, 7], [-7, -3, 0, 4], [-5, -1, 2, 5]]
    if rng.random() < 0.5: prog = prog[2:] + prog[:2]
    bpm = float(rng.uniform(100, 110)); beat = 60 / bpm; bar = beat * 4
    mtof = lambda m: 440 * 2 ** ((m - 69) / 12)
    kick, hat, clap = _kick(), _noise_hit(0.05, 90, 7), _noise_hit(0.18, 22, 9, 2)
    for b in range(int(dur / bar) + 2):
        ch = [root + iv for iv in prog[b % 4]]; t0 = b * bar
        for q in range(4):
            add_at(out, kick * 0.55, t0 + q * beat)
            add_at(out, hat * 0.10, t0 + q * beat + beat / 2)
            if q in (1, 3): add_at(out, clap * 0.16, t0 + q * beat)
        for q in (0.5, 1.5, 2.75, 3.5):                       # syncopated chord stabs
            for k, m in enumerate(ch):
                add_at(out, _ep_note(mtof(m + 12), 0.35, 0.05), t0 + q * beat + k * 0.008)
        for q, iv in ((0, 0), (1.5, 0), (2, 7), (3, 12)):     # bouncing bass
            add_at(out, _ep_note(mtof(ch[0] - 24 + iv), beat * 0.9, 0.2), t0 + q * beat)
    out = out[: int(dur * SR)]
    t = np.arange(len(out)) / SR
    env = np.minimum(1, t / 0.8) * np.minimum(1, (dur - t) / 1.5)
    return (out * env).astype(np.float32)


def bed_music(dur, seed, style="calm"):
    return upbeat(dur, seed) if style == "upbeat" else ambient(dur, seed)


def _ep_note(f, dur, vel=0.3):
    """Soft electric-piano-like tone: sine + gentle harmonics, slow decay, light tremolo."""
    n = int(dur * SR); t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) + 0.06 * np.sin(2 * np.pi * 3 * f * t)
    env = np.minimum(1, t / 0.012) * np.exp(-t * 1.6)
    trem = 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    return (tone * env * trem * vel).astype(np.float32)


def ambient(dur, seed):
    """Calm original background music (no samples, no existing melody): slow jazzy chords, soft arpeggios, warm bass."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(dur * SR) + SR * 4, np.float32)
    keys = [57, 60, 62, 55, 53]                       # A3, C4, D4, G3, F3 roots
    root = int(rng.choice(keys))
    # I maj7 – vi7 – IV maj7 – V(sus) in semitones from the key root
    prog = [[0, 4, 7, 11], [-3, 0, 4, 7], [-7, -3, 0, 4], [-5, -1, 2, 5]]
    if rng.random() < 0.5: prog = prog[1:] + prog[:1]
    bpm = float(rng.uniform(68, 78)); beat = 60 / bpm; bar = beat * 4
    mtof = lambda m: 440 * 2 ** ((m - 69) / 12)
    nb = int(dur / bar) + 2
    for b in range(nb):
        ch = [root + iv for iv in prog[b % 4]]
        t0 = b * bar
        for k, m in enumerate(ch):                    # soft rolled chord
            add_at(out, _ep_note(mtof(m), bar + 1.0, 0.11), t0 + k * 0.03)
        add_at(out, _ep_note(mtof(ch[0] - 24), bar, 0.22) * 0.9, t0)          # warm bass
        add_at(out, _ep_note(mtof(ch[0] - 24), beat * 2, 0.12), t0 + beat * 2.5)
        for s in range(4):                             # sparse arpeggio, random chord tones an octave up
            if rng.random() < 0.7:
                m = ch[int(rng.integers(0, 4))] + 12
                add_at(out, _ep_note(mtof(m), 1.2, 0.05), t0 + s * beat + beat * 0.5)
    out = out[: int(dur * SR)]
    t = np.arange(len(out)) / SR
    env = np.minimum(1, t / 1.5) * np.minimum(1, (dur - t) / 1.5)
    return (out * env).astype(np.float32)


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
        # pacing: long scenes get a mid-scene cut (second clip if given, else a jump cut into the same clip)
        vd = s["voice_end"] - s["start"]
        s["cut"] = vd * 0.5 if (spec.get("cuts", True) and vd > 3.2) else None
    total = t0 + 0.9
    voice_a = np.concatenate(vparts + [np.zeros(int(0.9 * SR) + SR, np.float32)])[: int(total * SR)]

    # sound design (mixed into the voice stem so the music ducking doesn't swallow it), scaled to the voice level
    if spec.get("sfx", True):
        sfx = np.zeros_like(voice_a); wh, pop, ding, imp = sfx_whoosh(), sfx_pop(), sfx_ding(), sfx_impact()
        for i, s in enumerate(segs):
            ln = s["line"]
            if i > 0: add_at(sfx, wh, max(0, s["start"] - 0.12))
            if s["cut"]: add_at(sfx, wh * 0.6, s["start"] + s["cut"] - 0.1)
            if ln.get("punch"): add_at(sfx, imp, s["start"] + ln.get("punch_delay", 0.15))
            for it in ln.get("items", []):
                if it.get("anim", "pop") in ("pop", "bounce", "drop", "zoom", "grow", "shake"):
                    add_at(sfx, pop * 0.8, s["start"] + it.get("delay", 0.0))
            if "number" in ln: add_at(sfx, ding, s["start"] + ln["number"].get("delay", 0.2) + 1.3)
        voice_a = voice_a + sfx * float(np.abs(voice_a).max() or 1) * 1.6

    # 2) audio: voice and bed (music) are written separately and mastered in ffmpeg (see master_audio)
    bed = bed_music(total, seed, spec.get("music", "calm"))[: len(voice_a)].copy()
    wav = out_path + ".wav"
    master_audio(voice_a, bed, wav)

    # 3) frames
    base = make_bg_base(pal)
    blobs = [(make_blob(c, rng.randint(260, 380)), rng.random() * 6.28, rng.uniform(0.15, 0.35)) for c in pal["blobs"]]
    stars = [(rng.random() * W, rng.random() * H, rng.uniform(1.5, 4.5), rng.uniform(8, 35)) for _ in range(40)]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out_path], stdin=subprocess.PIPE)
    hook = spec.get("hook", "")
    nframes = int(total * FPS)
    readers, cur_si, cur_phase = {}, -1, 0
    last_bg, trans, TRANS = None, None, 0.3
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
        phase = 1 if (seg.get("cut") and st >= seg["cut"]) else 0
        if si != cur_si:
            for r in readers.values(): r.close()
            readers.clear(); cur_si = si; cur_phase = 0
            if last_bg is not None: trans = {"t": t, "img": last_bg, "kind": "slide"}
            if ln.get("clip_path"):
                readers["bg"] = clips.ClipReader(ln["clip_path"], W, H, FPS, ln.get("clip_start", 0), ln.get("clip_speed", 1.0))
            if ln.get("inset_path"):
                readers["inset"] = clips.ClipReader(ln["inset_path"], INS, INS, FPS, ln.get("inset_start", 0))
        if phase != cur_phase and ln.get("clip_path"):
            cur_phase = phase
            if last_bg is not None: trans = {"t": t, "img": last_bg, "kind": "zoom"}
            if "bg" in readers: readers["bg"].close()
            if ln.get("clip2_path"):
                readers["bg"] = clips.ClipReader(ln["clip2_path"], W, H, FPS, ln.get("clip2_start", 0), ln.get("clip_speed", 1.0))
            else:
                readers["bg"] = clips.ClipReader(ln["clip_path"], W, H, FPS, ln.get("clip_start", 0) + seg["cut"] + 2.5, ln.get("clip_speed", 1.0))
        fr = readers["bg"].frame() if "bg" in readers else None
        if fr:
            img = Image.frombytes("RGBA", (W, H), fr)
            # camera on the footage: slow push-in, snap-zoom at every cut, tighter framing after a jump cut, shake on punch
            p0 = seg["cut"] if phase else 0.0
            p1 = (seg["cut"] if (seg.get("cut") and not phase) else slen)
            pt = st - p0
            z = (1.0 if phase == 0 else 1.12) + 0.07 * ease(pt / max(0.5, p1 - p0)) + 0.09 * max(0, 1 - pt / 0.2)
            dx = dy = 0.0
            if ln.get("punch"):
                k2 = st - ln.get("punch_delay", 0.15)
                if 0 <= k2 < 0.3:
                    amp = 16 * (1 - k2 / 0.3); dx, dy = math.sin(t * 95) * amp, math.cos(t * 83) * amp; z += 0.03
            if z > 1.001 or dx or dy:
                cw, chh = W / z, H / z
                x0 = max(0, min(W - cw, (W - cw) / 2 + dx)); y0 = max(0, min(H - chh, (H - chh) / 2 + dy))
                img = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + chh))).resize((W, H), Image.BILINEAR)
            # smooth shot transitions instead of a white flash:
            #   new scene -> "push" (old shot slides out left, new one slides in from the right, eased)
            #   mid-scene cut -> zoom-dissolve (old shot zooms in while fading into the new one)
            raw = img.copy()
            if trans is not None:
                k = (t - trans["t"]) / TRANS
                if k >= 1: trans = None
                else:
                    k = k * k * (3 - 2 * k)
                    old_im = trans["img"]
                    if trans["kind"] == "slide":
                        comp = Image.new("RGBA", (W, H), (0, 0, 0, 255))
                        off = int(W * k)
                        comp.paste(old_im, (-off, 0)); comp.paste(img, (W - off, 0))
                        img = comp
                    else:
                        zz = 1 + 0.18 * k
                        cw, chh = W / zz, H / zz
                        oz = old_im.crop((int((W - cw) / 2), int((H - chh) / 2), int((W + cw) / 2), int((H + chh) / 2))).resize((W, H), Image.BILINEAR)
                        img = Image.blend(oz, img, k)
            last_bg = raw
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

        # optional affiliate hint (trends channel): small "AD" pill above the endcard during the last ~7 s
        cta = spec.get("affiliate_cta")
        if cta and t > total - 7.0:
            a = ease((t - (total - 7.0)) / 0.4)
            fc = font(46)
            txt = "AD · " + cta
            tw = d.textlength(txt, font=fc)
            y0 = 1650
            d.rounded_rectangle([W / 2 - tw / 2 - 30, y0 - 38, W / 2 + tw / 2 + 30, y0 + 38], radius=38, fill=(0, 0, 0, int(170 * a)))
            text_c(d, (W / 2, y0), txt, fc, (255, 255, 255, int(255 * a)))

        # progress bar + flash at scene change
        d.rounded_rectangle([40, 70, 40 + (W - 80) * t / total, 84], radius=7, fill=acc)
        if t > total - 1.1:
            a = int(255 * ease((t - (total - 1.1)) / 0.35))
            text_c(d, (W / 2, 1760), spec.get("endcard", "FOLLOW FOR DAILY FACTS"), font(56), (*acc, a), stroke=6)
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
        for key in ("clip", "clip2", "inset"):
            if ln.get(key + "_path") and not os.path.exists(ln[key + "_path"]):
                ln.pop(key + "_path")  # stale path from another machine
            q = ln.get(key)
            if ln.get(key + "_id") and not ln.get(key + "_path"):
                path, c = clips.get_by_id(ln[key + "_id"])
                if path:
                    ln[key + "_path"] = path; used.add(c["id"])
                    credits.append(f"{c['user']} (Pixabay): {c['page']}")
                    continue
            if q and not ln.get(key + "_path"):
                path, c = clips.get_clip(q, used, "portrait" if key in ("clip", "clip2") else "square")
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
