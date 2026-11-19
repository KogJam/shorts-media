"""Make a YouTube thumbnail (1280x720 JPG) for a long-form spec.

python3 long/thumb.py long/specs/X.json out/thumb.jpg
Uses spec["thumb_text"] (2-4 punchy words, e.g. "FROZEN SOLID... ALIVE?"), spec["thumb_emoji"] (optional) and the
first clip of the #1 chapter (the LAST chapter in countdown order) or spec["thumb_clip"] + spec["thumb_ss"].
Look: bright, high-contrast frame on the right, huge outlined text on the left, a yellow count badge ("10").
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import render

W, H = 1280, 720
BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"


def grab(clip, ss, path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(ss), "-i", clip, "-frames:v", "1",
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", path], check=True)


def main(spec_path, out):
    spec = json.load(open(spec_path))
    chs = spec["chapters"]
    top = chs[-1] if spec.get("countdown", True) else chs[0]
    clip = spec.get("thumb_clip") or top["scenes"][0].get("clip")
    if not clip or not os.path.exists(clip):            # spec from another machine: fetch the clip again by id
        import clips
        clip, _ = clips.get_by_id(spec.get("thumb_clip_id") or top["scenes"][0]["clip_id"])
    tmp = out + ".frame.png"
    grab(clip, spec.get("thumb_ss", 2), tmp)
    img = Image.open(tmp).convert("RGB")
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.35)).enhance(1.15)
    img = ImageEnhance.Brightness(img).enhance(1.08).convert("RGBA")
    # dark gradient on the left for the text
    grad = Image.new("L", (W, 1))
    for x in range(W): grad.putpixel((x, 0), int(max(0, 215 * (1 - x / (W * 0.62)))))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 255)); shade.putalpha(grad.resize((W, H)))
    img.alpha_composite(shade)
    d = ImageDraw.Draw(img)
    text = spec.get("thumb_text") or spec["title"].split(",")[0]
    words = text.upper().split()
    # 2 lines max, as big as fits into the left 58 %
    lines = [" ".join(words[: (len(words) + 1) // 2]), " ".join(words[(len(words) + 1) // 2:])] if len(words) > 1 else words
    size = 150
    while size > 60 and max(d.textlength(L, font=ImageFont.truetype(BOLD, size)) for L in lines) > W * 0.58: size -= 4
    f = ImageFont.truetype(BOLD, size)
    y0 = H / 2 - (len(lines) - 1) * size * 0.55
    for i, L in enumerate(lines):
        d.text((48, y0 + i * size * 1.1), L, font=f, anchor="lm", fill=(255, 222, 0) if i == len(lines) - 1 else (255, 255, 255),
               stroke_width=max(6, size // 14), stroke_fill=(0, 0, 0))
    # count badge
    n = str(len(chs))
    d.ellipse([W - 190, 30, W - 30, 190], fill=(255, 222, 0), outline=(0, 0, 0), width=8)
    d.text((W - 110, 112), n, font=ImageFont.truetype(BOLD, 96), anchor="mm", fill=(0, 0, 0))
    if spec.get("thumb_emoji"):
        render.paste_emoji(img, spec["thumb_emoji"], W - 200, H - 170, 230, rot=-8)
    img.convert("RGB").save(out, quality=90)
    os.remove(tmp)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
