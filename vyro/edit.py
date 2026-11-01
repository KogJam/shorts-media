"""Vyro campaign edit: keep the provided clip 100 % intact (no trim/crop, original audio), place it inside a
9:16 frame with a hook text on top and a thin accent border – both explicitly allowed by the brief.

  python3 vyro/edit.py <in.mp4> <out.mp4> "<HOOK TEXT>" [--style 0..3]
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
STYLES = [  # (bg top, bg bottom, accent, hook text colour)
    ((12, 12, 16), (12, 12, 16), (255, 214, 0), (255, 255, 255)),
    ((8, 18, 40), (30, 8, 50), (0, 220, 255), (255, 255, 255)),
    ((20, 6, 6), (8, 8, 8), (255, 70, 70), (255, 255, 255)),
    ((6, 24, 14), (6, 10, 8), (120, 255, 140), (255, 255, 255)),
]


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:format=duration", "-of", "json", path])
    j = json.loads(out)
    s = j["streams"][0]
    return s["width"], s["height"], float(j["format"]["duration"])


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def split_emoji(text):
    """Return (text without emoji, list of emoji strings) – emoji are drawn as Noto 3D images."""
    import re
    ems = re.findall(r"[\U0001F000-\U0001FAFF\u2600-\u27BF][\uFE0F\u200D\U0001F000-\U0001FAFF]*", text)
    clean = text
    for e in ems: clean = clean.replace(e, "")
    return " ".join(clean.split()), ems


def emoji_png(e, size):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import render
    p = render.emoji_file(e)
    return Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS) if p else None


def overlay_png(hook, style, vid_box, path):
    hook, ems = split_emoji(hook)
    top, bot, acc, col = STYLES[style % len(STYLES)]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = vid_box
    # border around the (untouched) video
    d.rounded_rectangle([x0 - 8, y0 - 8, x1 + 8, y1 + 8], radius=26, outline=acc, width=8)
    # hook text in the free space above the video (or over the top of a full-height clip, on a dark pill)
    size = 78
    while size > 44:
        f = ImageFont.truetype(FONT, size)
        lines = wrap(d, hook, f, W - 120)
        if len(lines) <= 3: break
        size -= 6
    lh = int(size * 1.18)
    block = lh * len(lines)
    free = y0 - 16
    cy = max(60, (free - block) // 2) if free > block + 40 else 120
    if free <= block + 40:  # no room above: put a translucent pill behind the text
        d.rounded_rectangle([40, cy - 24, W - 40, cy + block + 24], radius=30, fill=(0, 0, 0, 170))
    for i, ln in enumerate(lines):
        d.text((W / 2, cy + i * lh + lh / 2), ln, font=f, fill=col, anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    if ems:  # emoji after the last line
        last_w = d.textlength(lines[-1], font=f)
        ex = int(W / 2 + last_w / 2 + 14)
        for e in ems[:2]:
            im = emoji_png(e, int(size * 1.05))
            if im is None: continue
            if ex + im.width > W - 20:  # no space: centre under the text
                ex = (W - im.width) // 2; cy += lh
            img.alpha_composite(im, (ex, int(cy + (len(lines) - 1) * lh + lh / 2 - im.height / 2)))
            ex += im.width + 6
    # accent underline
    d.rounded_rectangle([W / 2 - 90, cy + block + 14, W / 2 + 90, cy + block + 22], radius=4, fill=acc)
    img.save(path)
    bg = Image.new("RGB", (W, H))
    g = Image.linear_gradient("L").resize((W, H))
    bg = Image.composite(Image.new("RGB", (W, H), bot), Image.new("RGB", (W, H), top), g)
    bg.save(path.replace(".png", "_bg.png"))


def edit(src, out, hook, style=0):
    w, h, dur = probe(src)
    # scale the WHOLE clip to fit (no crop): max 1000 wide, leave >= 300 px on top for the hook
    scale = min(1000 / w, (H - 420) / h)
    vw, vh = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    x0 = (W - vw) // 2
    y0 = max(330, (H - vh) // 2 + 120) if vh < H - 450 else 360
    y0 = min(y0, H - vh - 40)
    ov = out + ".ov.png"
    overlay_png(hook, style, (x0, y0, x0 + vw, y0 + vh), ov)
    fc = (f"[1:v]scale={vw}:{vh}:flags=lanczos,setsar=1[v];[0:v][v]overlay={x0}:{y0}[b];[b][2:v]overlay=0:0,format=yuv420p[o]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", ov.replace(".png", "_bg.png"), "-i", src,
           "-loop", "1", "-i", ov, "-filter_complex", fc, "-map", "[o]", "-map", "1:a?", "-t", f"{dur:.3f}",
           "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "copy", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:  # audio codec not mp4-compatible -> re-encode audio losslessly-ish
        cmd[cmd.index("copy")] = "aac"; cmd.insert(cmd.index("aac") + 1, "-b:a"); cmd.insert(cmd.index("-b:a") + 1, "256k")
        subprocess.run(cmd, check=True)
    for p in (ov, ov.replace(".png", "_bg.png")):
        os.remove(p)
    w2, h2, d2 = probe(out)
    print(f"{out}: {w2}x{h2}, {d2:.2f}s (source {dur:.2f}s, video {vw}x{vh} at y={y0})")


if __name__ == "__main__":
    style = int(sys.argv[sys.argv.index("--style") + 1]) if "--style" in sys.argv else 0
    edit(sys.argv[1], sys.argv[2], sys.argv[3], style)
