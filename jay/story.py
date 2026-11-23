#!/usr/bin/env python3
"""jay.vs.life narrated story shorts (Bob-style POV narration): one local TTS voice, characters = same voice pitch-shifted
(formant preserved, so it stays clear), AI 3D stills with camera moves, word-by-word captions with a yellow keyword.
Usage: python3 jay/story.py spec.json out.mp4
Spec: {"voice": "am_michael", "speed": 1.0, "music_seed": 5,
       "voices": {"narrator": 0, "theo": 4},            # semitones per speaker
       "lines": [{"say": "...", "who": "narrator", "img": "out/jay/ep1/01.png", "move": "push", "key": "five", "gap": 0.15}]}
"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import tts, render as R
import meme as M

W, H, FPS = M.W, M.H, M.FPS
SR = tts.SR
CAP_Y = 1180
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
_fc = {}


def F(px):
    if px not in _fc: _fc[px] = ImageFont.truetype(FONT, px)
    return _fc[px]


def shift(a, semis):
    if not semis: return a
    tmp = f"/tmp/_v{os.getpid()}"
    R._write_wav(tmp + "a.wav", a / max(1e-6, np.abs(a).max()) * 0.9, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp + "a.wav", "-af",
                    f"rubberband=pitch={2 ** (semis / 12):.5f}:formant=preserved:pitchq=quality", tmp + "b.wav"], check=True)
    with wave.open(tmp + "b.wav") as w: b = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768.0
    return b.astype(np.float32)


def shift_tempo(a, k):
    tmp = f"/tmp/_t{os.getpid()}"
    R._write_wav(tmp + "a.wav", a / max(1e-6, np.abs(a).max()) * 0.9, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp + "a.wav", "-af", f"atempo={k}", tmp + "b.wav"], check=True)
    with wave.open(tmp + "b.wav") as w: return (np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768.0).astype(np.float32)


def squeeze(a, thr=0.012, maxgap=0.22):
    """Shorten pauses inside a line to at most `maxgap` seconds."""
    win = int(0.02 * SR); n = len(a) // win
    if n < 3: return a
    loud = np.abs(a[: n * win]).reshape(n, win).max(1) > thr
    keep, run = [], 0
    for i, l in enumerate(loud):
        run = 0 if l else run + 1
        keep.append(l or run * 0.02 <= maxgap)
    # rebuild from kept runs with 10 ms crossfades at every join (hard joins click)
    out, xf, i = np.zeros(0, np.float32), int(0.01 * SR), 0
    while i < n:
        if not keep[i]: i += 1; continue
        j = i
        while j < n and keep[j]: j += 1
        seg = a[i * win: (j * win if j < n else len(a))].astype(np.float32)
        if len(out) >= xf and len(seg) >= xf:
            r = np.linspace(0, 1, xf, dtype=np.float32)
            out[-xf:] = out[-xf:] * (1 - r) + seg[:xf] * r; seg = seg[xf:]
        out = np.concatenate([out, seg]); i = j
    return out


def level(a, target=0.08):
    """Same loudness for every line (RMS of the voiced part) + 15 ms fade in/out."""
    v = a[np.abs(a) > 0.01]
    if len(v): a = a * (target / max(1e-6, np.sqrt((v ** 2).mean())))
    f = min(len(a) // 2, int(0.015 * SR)); r = np.linspace(0, 1, f, dtype=np.float32)
    a = a.astype(np.float32).copy(); a[:f] *= r; a[len(a) - f:] *= r[::-1]
    return np.clip(a, -0.99, 0.99)


def trim(a, thr=0.01):
    idx = np.where(np.abs(a) > thr)[0]
    return a if not len(idx) else a[max(0, idx[0] - int(0.02 * SR)): idx[-1] + int(0.06 * SR)]


def chunks(words, n=3):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or w.endswith((".", ",", "?", "!", ":")): out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def caption(img, words, key, scale):
    """White heavy caption, black outline, keyword on a yellow tag."""
    if scale <= 0.01: return
    size = int(76 * scale); f = F(size); d = ImageDraw.Draw(img)
    clean = lambda w: w.strip('.,?!:"').lower()
    widths = [d.textlength(w.upper(), font=f) for w in words]; sp = size * 0.28
    x = W / 2 - (sum(widths) + sp * (len(words) - 1)) / 2
    for w, ww in zip(words, widths):
        hit = key and clean(w) in key
        if hit:
            d.rounded_rectangle([x - 12, CAP_Y - size * 0.62, x + ww + 12, CAP_Y + size * 0.62], radius=14, fill=M.YEL)
        d.text((x, CAP_Y), w.upper(), font=f, anchor="lm", fill=M.INK if hit else (255, 255, 255),
               stroke_width=0 if hit else 7, stroke_fill=(0, 0, 0))
        x += ww + sp


def build(spec_path, out):
    sp = json.load(open(spec_path)); voices = sp.get("voices", {"narrator": 0})
    segs, audio, t = [], [], 0.0
    for ln in sp["lines"]:
        who = ln.get("who", "narrator"); vc = voices.get(who, 0)
        if sp.get("engine") == "gemini":
            import gtts
            a = gtts.synth(ln["say"], vc["voice"], ln.get("style", vc.get("style", "")))
            a = squeeze(trim(a)); a = shift(a, vc.get("pitch", 0))
            if vc.get("tempo", 1.0) != 1.0: a = shift_tempo(a, vc["tempo"])
        else:
            a = trim(tts.synth(ln["say"], voice=sp.get("voice", "am_michael"), speed=ln.get("speed", sp.get("speed", 1.0))))
            a = shift(a, vc)
        gap = ln.get("gap", 0.18); dur = len(a) / SR + gap
        words = ln["say"].split(); cs = chunks(words)
        # word timing ~ proportional to letters (+ a little per word), inside the spoken part
        wt = np.array([len(w.strip('.,?!:"')) + 2 for w in words], float); wt = np.cumsum(wt) / wt.sum() * (len(a) / SR)
        starts, i = [], 0
        for c in cs: starts.append(0 if i == 0 else wt[i - 1]); i += len(c)
        segs.append(dict(ln, t0=t, dur=dur, chunks=cs, cstart=starts,
                         key={k.lower() for k in ([ln["key"]] if isinstance(ln.get("key"), str) else ln.get("key", []))}))
        a = level(a)
        audio.append(np.concatenate([a, np.zeros(int(gap * SR), np.float32)])); t += dur
    total = t; voice = np.concatenate(audio)
    srcs = {}
    tmpv = out + ".video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
    img_t0, last_img = {}, None
    for i in range(int(round(total * FPS))):
        tt = i / FPS
        k = max(j for j, s in enumerate(segs) if s["t0"] <= tt + 1e-6); s = segs[k]; lt = tt - s["t0"]
        if s["img"] != last_img: img_t0[s["img"]] = s["t0"]; last_img = s["img"]
        if s["img"] not in srcs: srcs[s["img"]] = M.base_img(s["img"])
        # a held image keeps moving across consecutive lines
        run = [x for x in segs if x["img"] == s["img"] and x["t0"] >= img_t0[s["img"]]]
        it, idur = tt - img_t0[s["img"]], sum(x["dur"] for x in run if x["t0"] < img_t0[s["img"]] + 12)
        frame = M.camera(srcs[s["img"]], s.get("move", "push"), it, max(idur, 0.5)).convert("RGBA")
        if it < 0.07 and img_t0[s["img"]] > 0:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(120 * (1 - it / 0.07)))))
        ci = max(j for j, c0 in enumerate(s["cstart"]) if c0 <= lt + 1e-6)
        cl = lt - s["cstart"][ci]
        caption(frame, s["chunks"][ci], s["key"], min(1.0, 0.82 + cl / 0.08 * 0.18) if cl < 0.08 else 1.0)
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    # sound: voice + quiet original bed + whoosh on image changes / sting on "impact" lines
    bed = R.upbeat(total + 0.5, sp.get("music_seed", 5))[: len(voice)] if len(voice) else np.zeros(1, np.float32)
    bed = np.pad(bed, (0, max(0, len(voice) - len(bed))))[: len(voice)].astype(np.float32)
    fx = np.zeros_like(voice)
    prev = None
    for s in segs:
        if s["img"] != prev and s["t0"] > 0 and sp.get("whoosh"): R.add_at(fx, R.sfx_whoosh() * 0.8, max(0, s["t0"] - 0.12))
        if s.get("sfx") == "impact": R.add_at(fx, R.sfx_impact() * 2.5, s["t0"])
        if s.get("sfx") == "pop": R.add_at(fx, R.sfx_pop() * 2.0, s["t0"])
        if s.get("sfx") == "ding": R.add_at(fx, R.sfx_ding() * 2.0, s["t0"])
        prev = s["img"]
    wav = out + ".wav"
    R.master_audio(voice + fx * 0.8, bed * 0.6, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmpv, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", out], check=True)
    os.remove(tmpv); os.remove(wav)
    print("duration", round(total, 2), out)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
