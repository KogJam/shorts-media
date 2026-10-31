"""Preview stock clip candidates so a human/Claude can pick relevant ones.

usage: python3 pick.py "query" [more queries...]   -> writes out/pick_<query>.jpg contact sheets with ids
       Then put  "clip_id": <id>  (or "inset_id") into the spec line instead of a query.
"""
import sys, os, subprocess
from PIL import Image, ImageDraw, ImageFont
import clips

FONT = ImageFont.truetype("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", 22)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)


def frame_at(path, t, w=180, h=320):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", path, "-frames:v", "1",
                          "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    return Image.frombytes("RGB", (w, h), raw) if len(raw) == w * h * 3 else Image.new("RGB", (w, h))


def sheet(query, n=6):
    res = clips.search(query)[:n]
    tiles = []
    for c in res:
        p = clips.download(c["url"])
        a, b = frame_at(p, 0.5), frame_at(p, max(0.5, c["duration"] * 0.6))
        tile = Image.new("RGB", (360, 360), (20, 20, 20))
        tile.paste(a, (0, 0)); tile.paste(b, (180, 0))
        d = ImageDraw.Draw(tile)
        d.rectangle([0, 320, 360, 360], fill=(0, 0, 0))
        d.text((8, 326), f"id {c['id']}  {c['duration']}s {'P' if c['h'] > c['w'] else 'L'}", font=FONT, fill=(255, 220, 0))
        tiles.append(tile)
        clips.REGISTRY[str(c["id"])] = c
    clips.save_registry()
    cols = 3
    img = Image.new("RGB", (360 * cols, 360 * max(1, (len(tiles) + cols - 1) // cols)), (0, 0, 0))
    for i, t in enumerate(tiles): img.paste(t, ((i % cols) * 360, (i // cols) * 360))
    path = os.path.join(OUT, "pick_" + "".join(ch if ch.isalnum() else "_" for ch in query) + ".jpg")
    img.save(path, quality=80)
    return path


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print(sheet(q))
