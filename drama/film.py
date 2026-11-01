"""Assemble a drama episode: Ken Burns stills + crossfades + voices + music + burned-in subtitles.

  python3 film.py episodes/ep01.json            -> build/ep01/ep01.mp4  (+ thumb.jpg)
"""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SDIR = None    # series folder: series/<id>/ (holds series.json, refs/, episodes/, build/)
SERIES = None


def load_series(ep_path):
    global SDIR, SERIES
    SDIR = os.path.dirname(os.path.dirname(os.path.abspath(ep_path)))
    SERIES = json.load(open(os.path.join(SDIR, "series.json")))
    return SERIES
W, H, FPS = 1920, 1080, 24
SR = 24000
XF = 0.5           # crossfade seconds
LEAD = float(os.environ.get("DRAMA_LEAD", "0.3"))    # silence before first line of a shot
TAIL = float(os.environ.get("DRAMA_TAIL", "0.2"))    # silence after last line
MIN_SHOT = 2.8
MAX_MIN = float(os.environ.get("DRAMA_MAX_MIN", "9.9"))  # hard cap: speed audio+video up to fit
GAP = float(os.environ.get("DRAMA_GAP", "0.18"))   # pause between lines
FONT_B = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
MAX_MB = float(os.environ.get("DRAMA_MAX_MB", "92"))


def read_wav(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getframerate() != SR:
            n = int(len(a) * SR / w.getframerate())
            a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
    # trim leading/trailing silence
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(0, nz[0] - 600): nz[-1] + 1200]
    return a


def music_bed(dur, seed=7):
    """Slow, dark, emotional synth pad + sparse piano – original, royalty free."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    prog = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66], [164.81, 207.65, 246.94]]  # Am F G E
    seg = 8.0
    out = np.zeros_like(t)
    for k in range(int(dur // seg) + 1):
        chord = prog[k % 4]
        a, b = int(k * seg * SR), min(len(t), int((k + 1) * seg * SR + SR))
        tt = t[a:b] - k * seg
        env = np.clip(tt / 2.0, 0, 1) * np.clip((seg + 1 - tt) / 2.0, 0, 1)
        pad = sum(np.sin(2 * np.pi * f / 2 * tt) + 0.4 * np.sin(2 * np.pi * f * tt + 0.3) for f in chord) / (len(chord) * 1.4)
        out[a:b] += pad * env * 0.5
        for j in range(3):  # piano-ish plucks
            st = j * seg / 3 + rng.uniform(0, 0.4)
            f = chord[rng.integers(0, 3)] * 2
            m = tt >= st
            dt = tt[m] - st
            out[a:b][m] += np.sin(2 * np.pi * f * dt) * np.exp(-dt * 2.2) * 0.35
    drone = np.sin(2 * np.pi * 55 * t) * 0.15
    out = out + drone
    return (out / max(1e-6, np.abs(out).max())).astype(np.float32)


def kb_frames(img, n, mode, rng):
    """Yield n frames (PIL) of a Ken Burns move over img."""
    base = img.convert("RGB")
    bw, bh = base.size
    # cover 16:9
    s = max(W / bw, H / bh) * 1.18
    big = base.resize((int(bw * s), int(bh * s)), Image.LANCZOS)
    BW, BH = big.size
    for i in range(n):
        p = i / max(1, n - 1)
        p = p * p * (3 - 2 * p)  # smoothstep
        if mode == "push_in": z0, z1, x0, x1, y0, y1 = 1.0, 1.14, .5, .5, .45, .42
        elif mode == "pull_out": z0, z1, x0, x1, y0, y1 = 1.14, 1.0, .5, .5, .42, .45
        elif mode == "pan_left": z0, z1, x0, x1, y0, y1 = 1.08, 1.08, .62, .38, .45, .45
        else: z0, z1, x0, x1, y0, y1 = 1.08, 1.08, .38, .62, .45, .45
        z = z0 + (z1 - z0) * p
        cw, ch = W / 1.18 / z * (BW / (W / 1.18 * 1.0)) / (BW / W * 1.18 / 1.18) , 0
        # crop window in big-image pixels
        cw = BW / z; ch = cw * H / W
        if ch > BH: ch = BH; cw = ch * W / H
        cx = (x0 + (x1 - x0) * p) * BW; cy = (y0 + (y1 - y0) * p) * BH
        l = min(max(0, cx - cw / 2), BW - cw); t = min(max(0, cy - ch / 2), BH - ch)
        yield big.resize((W, H), Image.BILINEAR, box=(l, t, l + cw, t + ch))


def clip_frames(path, n):
    """n frames from an AI clip, scaled to the frame; slowed down up to 1.35x if short, then holds the last frame."""
    try:
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())
    except Exception:
        dur = 10.0
    m = max(1, int(dur * FPS) - 2)
    stretch = min(max(n / m, 1.0), 1.35)
    vf = f"setpts={stretch:.4f}*PTS,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=rgb24"
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", path, "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    last = None
    for i in range(n):
        b = p.stdout.read(W * H * 3) if p else b""
        if len(b) == W * H * 3:
            last = Image.frombytes("RGB", (W, H), b)
        elif p:
            p.kill(); p = None
        yield last if last is not None else Image.new("RGB", (W, H))
    if p: p.kill()


def ass_time(s):
    h = int(s // 3600); m = int(s % 3600 // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def wrap_sub(text, maxc=52):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > maxc and cur: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    lines.append(cur)
    return "\\N".join(lines)


def title_overlay(title, sub):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, 120))
    f1 = ImageFont.truetype(FONT_SERIF, 110); f2 = ImageFont.truetype(FONT_B, 54)
    d.text((W / 2, H / 2 - 40), title, font=f1, fill=(244, 214, 140), anchor="mm", stroke_width=4, stroke_fill=(20, 10, 0))
    d.text((W / 2, H / 2 + 90), sub, font=f2, fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    return im


def end_overlay(text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, 90))
    f = ImageFont.truetype(FONT_SERIF, 120)
    d.text((W / 2, H / 2), text, font=f, fill=(244, 214, 140), anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
    return im


def make_thumb(ep, d):
    bg = os.path.join(d, "thumb_bg.png")
    if not os.path.exists(bg): return None
    im = Image.open(bg).convert("RGB")
    s = max(1280 / im.width, 720 / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    l, t = (im.width - 1280) // 2, (im.height - 720) // 2
    im = im.crop((l, t, l + 1280, t + 720))
    from PIL import ImageEnhance
    im = ImageEnhance.Contrast(im).enhance(1.15); im = ImageEnhance.Color(im).enhance(1.2)
    dr = ImageDraw.Draw(im, "RGBA")
    lines = ep.get("thumb_text", [])
    colors = [(255, 255, 255), (255, 214, 0), (255, 214, 0), (255, 255, 255)]
    y = 40
    for i, L in enumerate(lines):
        size = 86 if len(L) < 16 else 70
        f = ImageFont.truetype(FONT_B, size)
        dr.text((36, y), L.upper(), font=f, fill=colors[i % 4], stroke_width=8, stroke_fill=(0, 0, 0))
        y += size + 14
    f = ImageFont.truetype(FONT_B, 40)
    tag = "FULL AI DRAMA – PART %d" % ep["episode"]
    tw = dr.textlength(tag, font=f)
    dr.rounded_rectangle([30, 640, 30 + tw + 40, 700], radius=14, fill=(220, 20, 60))
    dr.text((50, 670), tag, font=f, fill=(255, 255, 255), anchor="lm")
    out = os.path.join(d, "thumb.jpg")
    im.save(out, quality=90)
    return out


def build(ep_path):
    load_series(ep_path)
    ep = json.load(open(ep_path))
    d = os.path.join(SDIR, "build", f"ep{ep['episode']:02d}")
    shots = ep["shots"]
    # ---- audio + timeline ----
    timeline, voice = [], []
    t = 0.0
    subs = []
    for si, s in enumerate(shots):
        start = t
        cur = LEAD if si else 0.8
        clips = []
        for i, l in enumerate(s["lines"]):
            p = os.path.join(d, "audio", f"{s['id']}_{i}.wav")
            a = read_wav(p) if os.path.exists(p) else np.zeros(int(SR * max(1.5, len(l["text"].split()) / 2.6)), np.float32)
            clips.append((start + cur, a))
            subs.append((start + cur, start + cur + len(a) / SR, l))
            cur += len(a) / SR + GAP
        dur = max(cur + TAIL, MIN_SHOT)
        if s.get("title_card") or s.get("end_card"): dur = max(dur, 4.5)
        timeline.append((s, start, dur))
        voice += clips
        t = start + dur - XF  # next shot overlaps by the crossfade
    total = t + XF + 1.0
    vo = np.zeros(int(total * SR) + SR, np.float32)
    for st, a in voice:
        i = int(st * SR); vo[i:i + len(a)] += a[: len(vo) - i]
    mus = music_bed(total + 2)[: len(vo)]
    # duck music under speech
    env = np.convolve((np.abs(vo) > 0.02).astype(np.float32), np.ones(int(SR * 0.3)) / (SR * 0.3), "same")
    gain = 0.16 - 0.10 * np.clip(env * 3, 0, 1)
    fade = np.minimum(1, np.arange(len(vo)) / (SR * 2)) * np.minimum(1, (len(vo) - np.arange(len(vo))) / (SR * 3))
    mix = vo * 0.95 + mus * gain * fade
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
    wav = os.path.join(d, "mix.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # ---- subtitles (ASS) ----
    ass = os.path.join(d, "subs.ass")
    names = {k: v["name"].split()[0] for k, v in SERIES["characters"].items()}
    with open(ass, "w") as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Narr,Poppins,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,1,0,0,100,100,0,0,1,3,1,2,120,120,60,1\n"
                "Style: Dlg,Poppins,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,1,2,120,120,60,1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for st, en, l in subs:
            who = l["who"]
            txt = wrap_sub(l["text"])
            if who == "narrator": f.write(f"Dialogue: 0,{ass_time(st)},{ass_time(en + 0.15)},Narr,,0,0,0,,{txt}\n")
            else:
                nm = names.get(who, who.capitalize())
                f.write(f"Dialogue: 0,{ass_time(st)},{ass_time(en + 0.15)},Dlg,,0,0,0,,{{\\c&H00D7FF&}}{nm}:{{\\c&HFFFFFF&}} {txt}\n")

    # ---- frames ----
    raw = os.path.join(d, "video_noaudio.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", raw], stdin=subprocess.PIPE)
    rng = np.random.default_rng(1)
    prev_tail = None
    used_clips = 0
    for k, (s, start, dur) in enumerate(timeline):
        p = os.path.join(d, "img", f"{s['id']}.png")
        img = Image.open(p) if os.path.exists(p) else Image.new("RGB", (1376, 768), (20, 20, 25))
        overlay = None
        if s.get("title_card"): overlay = title_overlay(SERIES["title"].upper(), f"PART {ep['episode']}")
        if s.get("end_card"): overlay = end_overlay("TO BE CONTINUED…")
        n = int(round((dur if k == len(timeline) - 1 else dur - XF) * FPS))
        nx = int(XF * FPS)
        total_n = n + (nx if k < len(timeline) - 1 else 0)
        clip = os.path.join(d, "clips", f"{s['id']}.mp4")
        frames = clip_frames(clip, total_n) if os.path.exists(clip) else kb_frames(img, total_n, s.get("camera", "push_in"), rng)
        used_clips += os.path.exists(clip)
        for i, fr in enumerate(frames):
            if overlay is not None:
                fr = fr.convert("RGBA"); fr.alpha_composite(overlay); fr = fr.convert("RGB")
            if i < nx and prev_tail is not None:
                a = (i + 1) / (nx + 1)
                fr = Image.blend(prev_tail[i], fr, a)
            if k == 0 and i < FPS: fr = Image.blend(Image.new("RGB", (W, H)), fr, i / FPS)
            if i < n: enc.stdin.write(fr.tobytes())
            if i == n - 1 and k < len(timeline) - 1: prev_tail = []
            if i >= n: prev_tail.append(fr)
        if k == len(timeline) - 1:
            last = fr
            for j in range(FPS):  # fade out
                enc.stdin.write(Image.blend(last, Image.new("RGB", (W, H)), (j + 1) / FPS).tobytes())
        print(f"shot {s['id']} {dur:.1f}s", flush=True)
    enc.stdin.close(); enc.wait()

    # ---- final encode: subtitles + audio, 2-pass to fit size budget ----
    out = os.path.join(d, f"ep{ep['episode']:02d}.mp4")
    speed = max(1.0, (total + 1) / (MAX_MIN * 60))
    if speed > 1.12: print(f"WARNING: episode is {(total+1)/60:.1f} min – script too long, sped up {speed:.2f}x; write shorter next time")
    vdur = (total + 1) / speed
    abr = 96
    vbr = int(MAX_MB * 8 * 1024 / vdur - abr - 20)
    vbr = max(500, min(vbr, 4500))
    fontsdir = os.path.dirname(FONT_B)
    vf = f"subtitles={ass}:fontsdir={fontsdir}" + (f",setpts=PTS/{speed:.4f}" if speed > 1 else "")
    af = ["-af", f"atempo={speed:.4f}"] if speed > 1 else []
    common = ["-i", raw, "-i", wav, "-vf", vf] + af + ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{vbr}k", "-pix_fmt", "yuv420p"]
    plog = os.path.join(d, "pass")
    c1 = [x for x in common if x not in af]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + c1 + ["-pass", "1", "-passlogfile", plog, "-an", "-f", "mp4", "/dev/null"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + common + ["-pass", "2", "-passlogfile", plog, "-c:a", "aac", "-b:a", f"{abr}k",
                                                                   "-shortest", "-movflags", "+faststart", out], check=True)
    thumb = make_thumb(ep, d)
    mb = os.path.getsize(out) / 1e6
    print(f"done {out} {vdur/60:.1f} min (speed {speed:.2f}x), {mb:.1f} MB, video {vbr} kbps; {used_clips}/{len(timeline)} shots animated; thumb {thumb}")
    return out


if __name__ == "__main__":
    build(sys.argv[1])
