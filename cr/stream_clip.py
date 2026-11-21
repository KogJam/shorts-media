#!/usr/bin/env python3
"""Streamer clip -> 9:16 split layout (facecam on top, gameplay below) + hook + karaoke captions + Twitch CTA.
python3 stream_clip.py <streamer> <src.mp4> <start_s> <end_s> "<hook>" <out.mp4>
Streamer layouts live in streamers.json: {name: {"cam":[x0,y0,x1,y1] in 1920x1080, "game_x":0.5, "handle":"...", "display":"..."}}
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "vyro", "clipper")); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "vyro"))
os.environ.setdefault("SOURCES", os.path.join(HERE, "empty.json"))
if not os.path.exists(os.environ["SOURCES"]): json.dump({}, open(os.environ["SOURCES"], "w"))
from PIL import Image, ImageDraw, ImageFont
import cut as C

W, H = 1080, 1920
BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
CFG = json.load(open(os.path.join(HERE, "streamers.json")))


def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))


def cta_png(st, path, cam_h):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f0 = ImageFont.truetype(BOLD, 44); f1 = ImageFont.truetype(BOLD, 66); f2 = ImageFont.truetype(BOLD, 46)
    t0 = "FOLLOW"; t1 = st['display'].upper() + " ON TWITCH"; t2 = f"twitch.tv/{st['handle']}"
    while d.textlength(t1, font=f1) > W - 200: f1 = ImageFont.truetype(BOLD, f1.size - 4)
    w = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2)) + 100
    y = H // 2 - 150
    d.rounded_rectangle([(W - w) / 2, y, (W + w) / 2, y + 290], radius=34, fill=(145, 70, 255, 245))
    d.text((W / 2, y + 62), t0, font=f0, fill="white", anchor="mm")
    d.text((W / 2, y + 140), t1, font=f1, fill="white", anchor="mm")
    d.text((W / 2, y + 225), t2, font=f2, fill=(255, 235, 120), anchor="mm")
    img.save(path)


def label_png(st, path, cam_h):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(BOLD, 34); t = f"twitch.tv/{st['handle']}"
    w = d.textlength(t, font=f) + 44
    d.rounded_rectangle([W - w - 24, cam_h - 66, W - 24, cam_h - 14], radius=14, fill=(145, 70, 255, 230))
    d.text((W - 24 - w / 2, cam_h - 40), t, font=f, fill="white", anchor="mm")
    img.save(path)


def make(streamer, src, start, end, hook, out, cta_dur=2.6):
    st = CFG[streamer]
    os.makedirs("work", exist_ok=True)
    tag = f"work/{os.path.basename(out)[:-4]}"
    raw = tag + "_raw.mp4"
    C.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", src, "-t", f"{end - start:.2f}",
           "-vf", "scale=1920:1080", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", raw])
    d = dur(raw)
    x0, y0, x1, y1 = st["cam"]
    cam_h = int(round(W * (y1 - y0) / (x1 - x0) / 2)) * 2
    cam_h = min(cam_h, 820)
    game_h = H - cam_h
    gh = st.get("game_h", 940)                                 # skip the streamer's own burned-in captions at the bottom
    gw = int(gh * W / game_h / 2) * 2                         # crop width in the 1080p frame
    gx = int(max(0, min(1920 - gw, st.get("game_x", 0.5) * 1920 - gw / 2)))
    cues = C.phrases(raw, tag + "_cues.json", d)
    C.make_ass(cues, tag + ".ass", cam_h + 260, d)
    C.hook_png(hook, tag + "_hook.png"); cta_png(st, tag + "_cta.png", cam_h); label_png(st, tag + "_lbl.png", cam_h)
    cs = max(0.0, d - cta_dur)
    vf = (f"[0:v]crop={x1 - x0}:{y1 - y0}:{x0}:{y0},scale={W}:{cam_h}[cam];"
          f"[0:v]crop={gw}:{gh}:{gx}:0,scale={W}:{game_h}[game];"
          f"[cam][game]vstack,setsar=1[v0];[v0]ass={tag}.ass[v1];"
          f"[v1][3:v]overlay=0:0[v2];"
          f"[v2][1:v]overlay=0:0:enable='lt(t,3.2)'[v3];"
          f"[v3][2:v]overlay=0:0:enable='gte(t,{cs:.2f})',format=yuv420p[o]")
    C.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-loop", "1", "-i", tag + "_hook.png", "-loop", "1", "-i", tag + "_cta.png",
           "-loop", "1", "-i", tag + "_lbl.png", "-filter_complex", vf, "-map", "[o]", "-map", "0:a", "-t", f"{d:.2f}", "-r", "30",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-maxrate", "11M", "-bufsize", "22M",
           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-movflags", "+faststart", out])
    print("ok", out, f"{d:.1f}s", len(cues), "cues")


if __name__ == "__main__":
    a = sys.argv
    make(a[1], a[2], float(a[3]), float(a[4]), a[5], a[6])
