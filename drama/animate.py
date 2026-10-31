"""Turn shot stills into short AI-animated clips with Google Veo (image-to-video).

  python3 animate.py series/<id>/episodes/epNN.json            # animate all shots marked "animate": true (or all if --all)
  python3 animate.py <ep.json> --shots s12,s59 --model lite      # specific shots
Clips land in build/epNN/clips/<shot>.mp4 (cached). Needs GEMINI_API_KEY.
Models: lite = veo-3.1-lite-generate-preview (~$0.05/s at 720p), fast = veo-3.1-fast-generate-preview (~$0.10/s).
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

KEY = os.environ.get("GEMINI_API_KEY", "")
BASE = "https://generativelanguage.googleapis.com/v1beta"
MODELS = {"lite": "veo-3.1-lite-generate-preview", "fast": "veo-3.1-fast-generate-preview", "full": "veo-3.1-generate-preview"}


def req(url, body=None, raw=False, tries=4):
    for i in range(tries):
        try:
            r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                       headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=300) as resp:
                data = resp.read()
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:400]
            if e.code in (429, 500, 502, 503) and i < tries - 1: time.sleep(20 * (i + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")


def motion_prompt(shot, series):
    # never put character names in the prompt (Omni blocks anything that sounds like a real person)
    def role(c):
        parts = [p.strip() for p in c["look"].split(",")]
        return "the " + parts[0].split("-year-old ")[-1] + (" with " + parts[1] if len(parts) > 1 else "")
    names = {k: role(v) for k, v in series["characters"].items()}
    desc = shot["image"]
    for k, n in names.items(): desc = desc.replace(k, n)
    speaking = [l for l in shot.get("lines", []) if l["who"] != "narrator"]
    talk = (f"{names.get(speaking[0]['who'], 'the speaking person').capitalize()} talks with natural lip movement and expressive face ({speaking[0].get('how', 'emotional')}). "
            if speaking else "Nobody talks; mouths stay closed. ")
    extra = shot.get("motion", "subtle natural movement: breathing, blinking, small gestures, hair and fabric moving, background people moving")
    cam = {"push_in": "slow dolly-in", "pull_out": "slow dolly-out", "pan_left": "slow pan to the left",
           "pan_right": "slow pan to the right"}.get(shot.get("camera"), "slow camera drift")
    return (f"Animate this exact image as a cinematic live-action drama shot. {desc}. Motion: {extra}. {talk}"
            f"Camera: {cam}. Keep every face, hairstyle, outfit and the setting exactly as in the image, photorealistic, "
            f"film look, consistent lighting. No text, no subtitles, no music.")


def animate_omni(shot, img_path, out, series, resolution="720p"):
    """Gemini Omni Flash image-to-video via the Interactions API (~10 s clip, ~$1 at 720p)."""
    if os.path.exists(out): return out
    body = {"model": os.environ.get("OMNI_MODEL", "gemini-omni-1.1-flash"),
            "input": [{"type": "image", "data": base64.b64encode(open(img_path, "rb").read()).decode(), "mime_type": "image/png"},
                      {"type": "text", "text": motion_prompt(shot, series)}],
            "generation_config": {"video_config": {"task": "image_to_video"}},
            "response_format": {"type": "video", "aspect_ratio": "16:9", "resolution": resolution}}
    d = req(f"{BASE}/interactions", body)
    for st in d.get("steps", []):
        if st.get("type") == "model_output":
            for c in st.get("content", []):
                if c.get("type") == "video":
                    open(out + ".part", "wb").write(base64.b64decode(c["data"])); os.rename(out + ".part", out)
                    return out
    raise RuntimeError("no video in response: " + json.dumps(d)[:300])


def animate(shot, img_path, out, series, model="omni", seconds=6, resolution="720p"):
    if model == "omni": return animate_omni(shot, img_path, out, series, resolution)
    if os.path.exists(out): return out
    body = {"instances": [{"prompt": motion_prompt(shot, series),
                           "image": {"bytesBase64Encoded": base64.b64encode(open(img_path, "rb").read()).decode(),
                                     "mimeType": "image/png"}}],
            "parameters": {"aspectRatio": "16:9", "resolution": resolution, "durationSeconds": seconds,
                           "personGeneration": "allow_adult"}}
    op = req(f"{BASE}/models/{MODELS[model]}:predictLongRunning", body)
    name = op["name"]
    for _ in range(90):
        time.sleep(10)
        st = req(f"{BASE}/{name}")
        if st.get("done"):
            if "error" in st: raise RuntimeError(json.dumps(st["error"])[:300])
            resp = st.get("response", {})
            samples = resp.get("generateVideoResponse", {}).get("generatedSamples", [])
            if not samples: raise RuntimeError("no video (filtered?): " + json.dumps(resp)[:300])
            uri = samples[0]["video"]["uri"]
            data = req(uri, raw=True)
            open(out + ".part", "wb").write(data); os.rename(out + ".part", out)
            return out
    raise RuntimeError("timeout waiting for " + name)


if __name__ == "__main__":
    ep_path = sys.argv[1]
    sdir = os.path.dirname(os.path.dirname(os.path.abspath(ep_path)))
    series = json.load(open(os.path.join(sdir, "series.json")))
    ep = json.load(open(ep_path))
    build = os.environ.get("DRAMA_BUILD") or os.path.join(sdir, "build", f"ep{ep['episode']:02d}")
    os.makedirs(os.path.join(build, "clips"), exist_ok=True)
    args = sys.argv[2:]
    model = args[args.index("--model") + 1] if "--model" in args else "omni"
    suffix = args[args.index("--suffix") + 1] if "--suffix" in args else ""
    if "--shots" in args: want = args[args.index("--shots") + 1].split(",")
    elif "--all" in args: want = [s["id"] for s in ep["shots"]]
    else: want = [s["id"] for s in ep["shots"] if s.get("animate")]
    shots = [s for s in ep["shots"] if s["id"] in want]
    # most important first: shots with characters and dialogue, then the rest
    shots.sort(key=lambda s: (-len(s.get("chars", [])) - 2 * any(l["who"] != "narrator" for l in s["lines"]), ep["shots"].index(s)))

    cdir = os.path.join(build, "clips")
    failp = os.path.join(cdir, "failures.json")
    fails = json.load(open(failp)) if os.path.exists(failp) else {}
    # retry only shots that failed fewer than 2 times (safety filters are usually deterministic)
    shots = [s for s in shots if fails.get(s["id"], 0) < 2]
    stop_flags = ("OUT_OF_CREDIT", "DAILY_LIMIT")
    for f in stop_flags:  # flags are per run
        if os.path.exists(os.path.join(cdir, f)): os.remove(os.path.join(cdir, f))
    limit = int(os.environ.get("MAX_CLIPS", "0")) or None
    made = []

    def one(s):
        out = os.path.join(cdir, f"{s['id']}{suffix}.mp4")
        if any(os.path.exists(os.path.join(cdir, f)) for f in stop_flags): return
        if os.path.exists(out): return
        if limit and len(made) >= limit: return
        try:
            made.append(s["id"])
            animate(s, os.path.join(build, "img", f"{s['id']}.png"), out, series, model, s.get("anim_seconds", 6))
            print("clip", s["id"], flush=True)
        except Exception as e:
            msg = str(e)
            print("CLIP FAIL", s["id"], msg[:200], flush=True)
            if "402" in msg or "depleted" in msg: open(os.path.join(cdir, "OUT_OF_CREDIT"), "w").write(msg)
            elif "429" in msg: open(os.path.join(cdir, "DAILY_LIMIT"), "w").write(msg)
            else: fails[s["id"]] = fails.get(s["id"], 0) + 1
    with ThreadPoolExecutor(int(os.environ.get("VEO_PARALLEL", "3"))) as ex: list(ex.map(one, shots))
    json.dump(fails, open(failp, "w"))
    have = sum(os.path.exists(os.path.join(cdir, f"{s['id']}.mp4")) for s in ep["shots"])
    blocked = [k for k, v in fails.items() if v >= 2]
    flag = next((f for f in stop_flags if os.path.exists(os.path.join(cdir, f))), "")
    print(f"STATUS animated={have}/{len(ep['shots'])} blocked={blocked} stop={flag or 'none'}")
