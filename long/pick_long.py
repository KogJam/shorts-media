"""Pick landscape Pixabay clips for every scene of a long-form spec and make a QA contact sheet.
python3 long/pick_long.py spec.json [--redo i,j]   -> writes spec with 'clip' + 'clip_id', sheet next to it
"""
import json, os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import clips
from PIL import Image, ImageDraw, ImageFont

def scenes(spec):
    out = [("intro", i, sc) for i, sc in enumerate(spec["intro"])]
    for ci, c in enumerate(spec["chapters"]):
        out += [(f"c{ci+1}", i, sc) for i, sc in enumerate(c["scenes"])]
    out += [("outro", i, sc) for i, sc in enumerate(spec["outro"])]
    return out

def main():
    p = sys.argv[1]; spec = json.load(open(p))
    redo = set()
    if "--redo" in sys.argv: redo = {int(x) for x in sys.argv[sys.argv.index("--redo") + 1].split(",")}
    used = {sc.get("clip_id") for _, _, sc in scenes(spec) if sc.get("clip_id")}
    for n, (tag, i, sc) in enumerate(scenes(spec)):
        if sc.get("clip") and os.path.exists(sc["clip"]) and n not in redo: continue
        q = sc.get("q2") if n in redo and sc.get("q2") else sc["q"]
        try:
            res = clips.pixabay_search(q, orientation="landscape", per_page=20)
        except Exception as e:
            print("search fail", q, e); continue
        res = [r for r in res if not r["portrait"]] or res
        if n in redo and sc.get("clip_id"): used.add(sc["clip_id"])
        got = 0
        for r in res:
            if r["id"] in used: continue
            try:
                path = clips.download(r["url"])
            except Exception as e:
                print("dl fail", e); continue
            if got == 0: sc["clip"] = path; sc["clip_id"] = r["id"]
            else: sc["clip2"] = path; sc["clip2_id"] = r["id"]      # second shot for the ~5 s cuts
            used.add(r["id"]); got += 1
            if got == 2: break
        print(n, tag, q, sc.get("clip_id"), flush=True)
    json.dump(spec, open(p, "w"), indent=1, ensure_ascii=False)
    # contact sheet
    th = []
    for n, (tag, i, sc) in enumerate(scenes(spec)):
        f = f"/tmp/ls_{n}.jpg"
        if sc.get("clip"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", sc["clip"], "-frames:v", "1", "-vf", "scale=320:180:force_original_aspect_ratio=increase,crop=320:180", f])
        im = Image.open(f) if os.path.exists(f) else Image.new("RGB", (320, 180), "gray")
        d = ImageDraw.Draw(im); d.rectangle([0, 0, 320, 22], fill=(0, 0, 0))
        d.text((4, 4), f"{n} {tag} {sc['q'][:30]}", fill=(255, 255, 0))
        if sc.get("clip2"):
            f2 = f"/tmp/ls_{n}_b.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", sc["clip2"], "-frames:v", "1", "-vf", "scale=120:68:force_original_aspect_ratio=increase,crop=120:68", f2])
            if os.path.exists(f2): im.paste(Image.open(f2), (196, 108)); d.rectangle([196, 108, 319, 179], outline=(255, 255, 0))
        th.append(im)
    cols = 8; rows = (len(th) + cols - 1) // cols
    sheet = Image.new("RGB", (320 * cols, 180 * rows))
    for k, im in enumerate(th): sheet.paste(im, ((k % cols) * 320, (k // cols) * 180))
    sheet.save(p.replace(".json", "_sheet.jpg"))

main()
