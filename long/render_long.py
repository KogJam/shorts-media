"""Render a landscape long-form video (1920x1080) from a long-form spec.

Spec: {title, voice, speed, intro:[{say, clip, ss?}], chapters:[{title, scenes:[{say, clip, ss?}]}], outro:[...]}
(clips are filled in by long/pick_long.py). Every chapter starts with a spoken title card ("Number 3. Why ...").
Look: full-screen stock footage with a slow pan, lower-third phrase captions, chapter label top-left,
calm original music bed, mastered voice (render.master_audio).

python3 long/render_long.py spec.json out.mp4
"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import tts, render

W, H, FPS = 1920, 1080, 30
SR = tts.SR
BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
NUMS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-2000:])


def card_png(num, title, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(BOLD, 150); f2 = ImageFont.truetype(BOLD, 86)
    d.text((W / 2, H / 2 - 95), f"#{num}", font=f1, fill=(255, 214, 0), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    words, lines, cur = title.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f2) < W - 300: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    for i, ln in enumerate(lines):
        d.text((W / 2, H / 2 + 60 + i * 100), ln, font=f2, fill="white", anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
    img.save(path)


def chunks(text, maxw=7):
    """Split a line into caption phrases of <= maxw words, breaking at punctuation where possible."""
    words = text.split(); out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxw or (re.search(r"[.,!?:;]$", w) and len(cur) >= 3):
            out.append(" ".join(cur)); cur = []
    if cur:
        if out and len(cur) <= 2: out[-1] += " " + " ".join(cur)
        else: out.append(" ".join(cur))
    return out


def ass_t(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build(spec_path, out):
    spec = json.load(open(spec_path))
    work = out + ".work"; os.makedirs(work, exist_ok=True)
    voice, speed = spec.get("voice", "bm_lewis"), spec.get("speed", 1.0)
    # ---- scene list ----
    scenes = []
    for sc in spec["intro"]: scenes.append(dict(sc, kind="scene", chap=None))
    for ci, ch in enumerate(spec["chapters"]):
        n = ci + 1
        first = ch["scenes"][0]
        scenes.append({"kind": "card", "say": f"Number {NUMS[ci]}. {ch['title'].replace(chr(39), '')}.", "clip": first["clip"],
                       "ss": first.get("ss", 1) + 6, "num": n, "title": ch["title"], "chap": n})
        for sc in ch["scenes"]: scenes.append(dict(sc, kind="scene", chap=n))
    for sc in spec["outro"]: scenes.append(dict(sc, kind="scene", chap=None))
    # ---- voice + timings ----
    parts, t = [np.zeros(int(0.4 * SR), np.float32)], 0.4
    for sc in scenes:
        a = tts.synth(sc["say"], voice=voice, speed=speed)
        pre = 0.5 if sc["kind"] == "card" else 0.0
        post = 0.9 if sc["kind"] == "card" else 0.35
        parts += [np.zeros(int(pre * SR), np.float32), a, np.zeros(int(post * SR), np.float32)]
        sc["start"] = t; sc["vstart"] = t + pre; sc["vend"] = t + pre + len(a) / SR
        t = sc["vend"] + post; sc["end"] = t
    total = t + 1.5
    scenes[-1]["end"] = total
    voice_a = np.concatenate(parts + [np.zeros(int(1.5 * SR), np.float32)])[: int(total * SR)]
    bed = render.ambient(total, sum(map(ord, spec["id"])) % 9999)[: len(voice_a)]
    wav = os.path.join(work, "audio.wav")
    render.master_audio(voice_a, bed, wav)
    # ---- captions (ASS) ----
    ass = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,160,160,80,1
Style: Lbl,Poppins,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,3,10,0,7,50,50,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""]
    for sc in scenes:
        if sc["kind"] == "card": continue
        cs = chunks(sc["say"]); dur = sc["vend"] - sc["vstart"]
        tot = sum(len(c) + 3 for c in cs); tt = sc["vstart"]
        for c in cs:
            d = dur * (len(c) + 3) / tot
            ass.append(f"Dialogue: 0,{ass_t(tt)},{ass_t(tt + d + 0.05)},Cap,,0,0,0,,{{\\fad(60,60)}}{c}")
            tt += d
    chap_spans = {}
    for sc in scenes:
        if sc.get("chap"):
            s, e = chap_spans.get(sc["chap"], (sc["start"], sc["end"])); chap_spans[sc["chap"]] = (min(s, sc["start"]), max(e, sc["end"]))
    for n, (s, e) in chap_spans.items():
        title = spec["chapters"][n - 1]["title"]
        ass.append(f"Dialogue: 1,{ass_t(s + 3.2)},{ass_t(e)},Lbl,,0,0,0,,{{\\fad(300,300)}}#{n}  {title}")
    ass_path = os.path.join(work, "caps.ass"); open(ass_path, "w").write("\n".join(ass) + "\n")
    # ---- video segments ----
    seglist = []
    for i, sc in enumerate(scenes):
        seg = os.path.join(work, f"seg{i:03d}.mp4"); dur = sc["end"] - sc["start"]
        d = 1 if i % 2 else -1
        pan = f"scale={W + 192}:{H + 108}:force_original_aspect_ratio=increase,crop={W + 192}:{H + 108}," \
              f"crop={W}:{H}:x='(iw-{W})*({'t' if d > 0 else f'{dur:.2f}-t'})/{dur:.2f}':y='(ih-{H})/2'"
        if sc["kind"] == "card":
            png = os.path.join(work, f"card{i:03d}.png"); card_png(sc["num"], sc["title"], png)
            vf = f"[0:v]{pan},boxblur=18:2,eq=brightness=-0.18,fps={FPS}[b];[1:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1[t];[b][t]overlay=0:0,format=yuv420p[o]"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", f"{sc.get('ss', 1):.2f}", "-i", sc["clip"],
                   "-loop", "1", "-i", png, "-filter_complex", vf, "-map", "[o]"]
        else:
            vf = f"[0:v]{pan},eq=saturation=1.06:contrast=1.03,fps={FPS},format=yuv420p[o]"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", f"{sc.get('ss', 1):.2f}", "-i", sc["clip"],
                   "-filter_complex", vf, "-map", "[o]"]
        cmd += ["-t", f"{dur:.3f}", "-r", str(FPS), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", seg]
        if not os.path.exists(seg): run(cmd)
        seglist.append(seg)
        print(f"seg {i+1}/{len(scenes)}", flush=True)
    lst = os.path.join(work, "list.txt"); open(lst, "w").write("".join(f"file '{os.path.abspath(s)}'\n" for s in seglist))
    joined = os.path.join(work, "joined.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    # final file must stay under GitHub's 100 MB file limit (publish.py hosts it on a branch): 720p, size-capped bitrate
    max_mb = float(os.environ.get("LONG_MAX_MB", "90"))
    vk = int(max(700, min(4000, max_mb * 8192 / total - 128)))
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", wav, "-vf", f"ass={ass_path},scale=1280:720:flags=lanczos",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-b:v", f"{vk}k", "-maxrate", f"{int(vk * 1.3)}k",
         "-bufsize", f"{vk * 2}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", out])
    # chapters for the YouTube description
    chap = ["0:00 Intro"] + [f"{int(scenes_s // 60)}:{int(scenes_s % 60):02d} {spec['chapters'][n - 1]['title']}"
                             for n, (scenes_s, _) in sorted(chap_spans.items())]
    json.dump({"duration": total, "chapters": chap}, open(out + ".meta.json", "w"), indent=1)
    print("done", out, round(total / 60, 2), "min"); print("\n".join(chap))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
