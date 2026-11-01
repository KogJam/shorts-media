"""Cut one segment from the 4K original (streamed over HTTP, only the needed range), make it 9:16 with
hook text (first seconds) + word-group captions (Gemini transcript) + small @essentialwilderness tag.
python3 cut.py <key> <start_s> <end_s> "<hook>" <out.mp4> [--x 0.5] [--wide]
"""
import json, os, re, subprocess, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
PROXY = os.environ.get("HTTPS_PROXY", "")
ORIG = json.load(open(os.environ.get("SOURCES", "sources.json")))  # key -> URL or local path of the full-res source


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    return r


def grab(key, start, dur, raw):
    """Stream-copy just the needed part of the original (4K h264) – no full download."""
    if os.path.exists(raw): return
    px = ["-http_proxy", PROXY] if ORIG[key].startswith("http") and PROXY else []
    run(["ffmpeg", "-y", "-loglevel", "error", *px, "-ss", f"{start:.2f}", "-i", ORIG[key],
         "-t", f"{dur + 1:.2f}", "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
         "-vf", "scale=1920:-2", "-c:a", "aac", "-b:a", "192k", raw])


# ---------- captions via Gemini ----------
def gem_key():
    for l in open(os.path.expanduser("~/.config/shorts/env")):
        if "GEMINI_API_KEY" in l: return l.split("=", 1)[1].strip().strip('"')


def transcribe(raw, cache):
    if os.path.exists(cache): return json.load(open(cache))
    wav = raw + ".mp3"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-vn", "-ac", "1", "-b:a", "64k", wav])
    import base64
    b64 = base64.b64encode(open(wav, "rb").read()).decode()
    prompt = ("Transcribe this English speech exactly (verbatim, keep 'um' out). Return ONLY JSON "
              '{"words":[{"w":"word","s":seconds_start,"e":seconds_end}]} with precise word-level timestamps in seconds '
              "from the start of the audio (decimals). No speech -> empty list.")
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "audio/mp3", "data": b64}}, {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    k = gem_key()
    r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={k}",
                               json.dumps(body).encode(), {"Content-Type": "application/json"})
    j = json.loads(urllib.request.urlopen(r, timeout=300).read())
    words = json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
    if isinstance(words, dict): words = words.get("words", [])
    words = [{"w": w.get("w") or w.get("word"), "s": float(w.get("s", w.get("start", 0))), "e": float(w.get("e", w.get("end", 0)))} for w in words]
    json.dump(words, open(cache, "w"))
    os.remove(wav)
    return words


def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


BAD = {"fuck": "f*ck", "fucking": "f*cking", "fucked": "f*cked", "shit": "sh*t", "bullshit": "bullsh*t", "damn": "d*mn",
       "bitch": "b*tch", "ass": "a**", "asshole": "a**hole", "goddamn": "godd*mn", "motherfucker": "m*therf*cker"}


def clean(w):
    m = re.match(r"^(\W*)(.*?)(\W*)$", w)
    a, core, b = m.groups()
    return a + BAD.get(core.lower(), core) + b


def speech_bounds(raw):
    """Speech onsets/offsets from the audio (silencedetect) for snapping caption times."""
    r = subprocess.run(["ffmpeg", "-i", raw, "-af", "highpass=f=120,lowpass=f=4000,silencedetect=n=-32dB:d=0.25", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    on = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r)]
    off = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r)]
    return on, off


def phrases(raw, cache, dur):
    if os.path.exists(cache): return json.load(open(cache))
    mp3 = raw + ".mp3"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-vn", "-ac", "1", "-b:a", "64k", mp3])
    import base64
    b64 = base64.b64encode(open(mp3, "rb").read()).decode()
    prompt = (f"This audio is {dur:.1f} seconds long. Transcribe the English speech verbatim (drop 'um/uh') as subtitle cues of "
              "2-7 words that follow natural pauses and phrasing. For every cue give the exact time the FIRST word starts and the "
              "LAST word ends, in seconds from the start of the audio (2 decimals). Listen carefully: times must match the audio, "
              'never compress them. Return ONLY JSON {"cues":[{"t":"text","s":0.00,"e":0.00}]}. No speech -> empty list.')
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "audio/mp3", "data": b64}}, {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gem_key()}",
                               json.dumps(body).encode(), {"Content-Type": "application/json"})
    c = []
    for attempt in range(3):
        j = json.loads(urllib.request.urlopen(r, timeout=300).read())
        raw_c = json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
        if isinstance(raw_c, dict): raw_c = raw_c.get("cues") or next((v for v in raw_c.values() if isinstance(v, list)), [])
        for x in raw_c:
            t = x.get("t") or x.get("text") or x.get("cue") or ""
            st = x.get("s", x.get("start")); en = x.get("e", x.get("end"))
            if t and st is not None and en is not None: c.append({"t": t, "s": float(st), "e": float(en)})
        if c: break
        print("empty cues, retry", raw[:40], str(raw_c)[:200], flush=True)
    os.remove(mp3)
    # snap to real speech onsets/offsets
    on, off = speech_bounds(raw)
    for x in c:
        near = [o for o in on if abs(o - x["s"]) < 0.8]
        if near: x["s"] = min(near, key=lambda o: abs(o - x["s"]))
        neare = [o for o in off if abs(o - x["e"]) < 0.8 and o > x["s"] + 0.3]
        if neare: x["e"] = min(neare, key=lambda o: abs(o - x["e"]))
        x["e"] = max(x["e"], x["s"] + 0.25 * len(x["t"].split()))
    c = [x for x in c if x["s"] < dur]
    json.dump(c, open(cache, "w"), indent=0)
    return c


def make_ass(cues, path, cap_y, dur):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,84,&H0000D7FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,70,70,{H - cap_y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    out = []
    for i, c in enumerate(cues):
        s = c["s"]; nxt = cues[i + 1]["s"] if i + 1 < len(cues) else dur
        e = min(nxt, max(c["e"] + 0.5, s + 1.3))  # stay readable, hold through short pauses
        if nxt - c["e"] < 1.0: e = nxt
        words = [clean(w) for w in c["t"].split()]
        # word highlight: spread the spoken span over the words by length (karaoke \\kf in centiseconds)
        span = max(0.3, min(c["e"], nxt) - s); tot = sum(len(w) + 2 for w in words)
        parts = [f"{{\\kf{max(1, int(span * (len(w) + 2) / tot * 100))}}}{w.upper()}" for w in words]
        out.append(f"Dialogue: 0,{ass_time(s)},{ass_time(min(e, dur))},Cap,,0,0,0,,{{\\fad(80,60)}}" + " ".join(parts))
    open(path, "w").write(head + "\n".join(out) + "\n")


# ---------- hook + tag overlay ----------
def hook_png(hook, path):
    from edit import split_emoji, emoji_png, wrap
    hook, ems = split_emoji(hook)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    size = 76
    while True:
        f = ImageFont.truetype(BOLD, size); lines = wrap(d, hook, f, W - 160)
        if len(lines) <= 3 or size < 48: break
        size -= 6
    lh = int(size * 1.2); y = max(48, 150 - lh * len(lines) // 2)
    widths = [d.textlength(l, font=f) for l in lines]
    bw = max(widths) + 70 + (size + 10 if ems else 0)
    d.rounded_rectangle([(W - bw) / 2, y - 26, (W + bw) / 2, y + lh * len(lines) + 22], radius=28, fill=(255, 255, 255, 240))
    for i, l in enumerate(lines):
        d.text((W / 2 - (size / 2 + 5 if ems and i == len(lines) - 1 else 0), y + i * lh + lh / 2), l, font=f,
               fill=(15, 15, 15), anchor="mm")
    if ems:
        im = emoji_png(ems[0], size)
        if im: img.alpha_composite(im, (int(W / 2 + widths[-1] / 2 - size / 2 + 10), int(y + (len(lines) - 1) * lh + lh / 2 - size / 2)))
    img.save(path)


def tag_png(path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(BOLD, 34)
    d.text((W / 2, 1850), os.environ.get("TAG", ""), font=f, fill=(255, 255, 255, 215), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, 160))
    img.save(path)


def track(raw, cmdfile, cw=608):
    """Face-tracking crop: detect faces at 5 fps, smooth, write an ffmpeg sendcmd file for crop x."""
    import cv2, numpy as np
    fr = cv2.CascadeClassifier(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "haarcascade_frontalface_default.xml"))
    pr = cv2.CascadeClassifier(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "haarcascade_profileface.xml"))
    cap = cv2.VideoCapture(raw); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps / 5))); i = 0; xs = []
    while True:
        ok = cap.grab()
        if not ok: break
        if i % step == 0:
            _, f = cap.retrieve(); g = cv2.cvtColor(cv2.resize(f, (960, 540)), cv2.COLOR_BGR2GRAY)
            faces = list(fr.detectMultiScale(g, 1.15, 6, minSize=(50, 50))) or list(pr.detectMultiScale(g, 1.15, 6, minSize=(50, 50)))
            if faces:
                x, y, w, h = max(faces, key=lambda b: b[2] * b[3]); xs.append((i / fps, (x + w / 2) * 2))
            else: xs.append((i / fps, None))
        i += 1
    W0 = 1920
    found = [c for _, c in xs if c is not None]
    if len(found) < len(xs) * 0.15:  # hardly any faces -> keep centre
        open(cmdfile, "w").write(f"0.0 crop@c x {(W0 - cw) / 2:.0f};\n"); return
    # fill gaps with last known, median filter, then slow EMA (no jitter)
    last = found[0]; seq = []
    for t, c in xs:
        last = c if c is not None else last; seq.append(last)
    med = [float(np.median(seq[max(0, k - 5):k + 6])) for k in range(len(seq))]
    out = []; cur = med[0]
    for (t, _), m in zip(xs, med):
        if abs(m - cur) > 260: cur = m  # big jump = new shot -> cut directly
        else: cur += (m - cur) * 0.15
        left = min(max(cur - cw / 2, 0), W0 - cw); out.append(f"{t:.2f} crop@c x {left:.0f};")
    open(cmdfile, "w").write("\n".join(out) + "\n")


def cut(key, start, end, hook, out, x=0.5, wide=False, hook_dur=3.5):
    os.makedirs("work", exist_ok=True)
    dur = end - start
    tag = f"work/{key}_{int(start)}_{int(end)}"
    raw = tag + "_raw.mp4"
    grab(key, start, dur, raw)
    words = phrases(raw, tag + "_cues.json", dur)
    hook_png(hook, tag + "_hook.png"); tag_png(tag + "_tag.png")
    if wide:  # 4:5 window on blurred full-frame background
        cap_y = 1640
        vf = (f"[0:v]split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=30:3,eq=brightness=-0.15[bg];"
              f"[b]crop=ih*4/5:ih:(iw-ih*4/5)*{x}:0,scale={W}:{int(W * 5 / 4)}[fg];[bg][fg]overlay=0:{(H - int(W * 5 / 4)) // 2}[v0]")
    else:  # full-screen 9:16 crop around the subject
        cap_y = 1500
        track(raw, tag + ".cmd")
        vf = f"[0:v]sendcmd=f={tag}.cmd,crop@c=608:1080:{(1920 - 608) // 2}:0,scale={W}:{H}:flags=lanczos[v0]"
    make_ass(words, tag + ".ass", cap_y, dur)
    vf += (f";[v0]ass={tag}.ass[v1];[v1][2:v]overlay=0:0[v2];"
           f"[v2][1:v]overlay=0:0,format=yuv420p[o]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-loop", "1", "-i", tag + "_hook.png", "-loop", "1", "-i", tag + "_tag.png",
         "-filter_complex", vf, "-map", "[o]", "-map", "0:a", "-t", f"{dur:.2f}", "-r", "30",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", "11M", "-bufsize", "22M", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-movflags", "+faststart", out])
    print("ok", out, f"{dur:.1f}s", len(words), "words")


if __name__ == "__main__":
    a = sys.argv
    x = float(a[a.index("--x") + 1]) if "--x" in a else 0.5
    cut(a[1], float(a[2]), float(a[3]), a[4], a[5], x, "--wide" in a)
