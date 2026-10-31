"""Generate assets for one drama episode with the Gemini API.

  python3 gen.py episodes/ep01.json refs      # character reference portraits (once per series)
  python3 gen.py episodes/ep01.json images    # one still per shot (characters kept consistent via refs)
  python3 gen.py episodes/ep01.json voices    # narrator + dialogue lines (Gemini TTS)
  python3 gen.py episodes/ep01.json thumb     # thumbnail background
  python3 gen.py episodes/ep01.json all

Everything is cached on disk; re-running only fills gaps. Needs GEMINI_API_KEY.
"""
import base64, json, os, sys, time, urllib.request, urllib.error, wave
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SDIR = None    # series folder: series/<id>/ (holds series.json, refs/, episodes/, build/)
SERIES = None


def load_series(ep_path):
    global SDIR, SERIES
    SDIR = os.path.dirname(os.path.dirname(os.path.abspath(ep_path)))
    SERIES = json.load(open(os.path.join(SDIR, "series.json")))
    return SERIES
KEY = os.environ.get("GEMINI_API_KEY", "")
IMAGE_MODEL = os.environ.get("DRAMA_IMAGE_MODEL", "gemini-3.1-flash-image")
TTS_MODEL = os.environ.get("DRAMA_TTS_MODEL", "gemini-3.1-flash-tts-preview")
IMAGE_SIZE = os.environ.get("DRAMA_IMAGE_SIZE", "1K")
EXTRA_VOICES = {  # minor speaking roles without a reference portrait
    "manager": ("Iapetus", "a nervous, fawning middle-aged man's voice"),
    "butler": ("Schedar", "a calm, formal elderly British butler's voice"),
    "chauffeur": ("Rasalgethi", "a polite, deep man's voice"),
}


def api(model, body, tries=5):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:400]
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(8 * (i + 1)); continue
            raise RuntimeError(f"{model} HTTP {e.code}: {msg}")
        except Exception as e:
            if i < tries - 1: time.sleep(5 * (i + 1)); continue
            raise
    raise RuntimeError("unreachable")


def first_inline(resp):
    for c in resp.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            if "inlineData" in p: return p["inlineData"]
    raise RuntimeError("no media in response: " + json.dumps(resp)[:400])


def ep_dir(ep):
    d = os.path.join(SDIR, "build", f"ep{ep['episode']:02d}")
    for sub in ("img", "audio"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def ref_path(cid): return os.path.join(SDIR, "refs", f"{cid}.png")


def describe(cid, outfit=None):
    c = SERIES["characters"][cid]
    return f"{c['name']}: {c['look']}, wearing {outfit or c['default_outfit']}"


def gen_image(prompt, chars, out, aspect="16:9", outfits=None, extra_parts=None):
    if os.path.exists(out): return out
    outfits = outfits or {}
    parts = []
    for cid in chars[:4]:
        if os.path.exists(ref_path(cid)):
            parts.append({"text": f"Reference photo of {SERIES['characters'][cid]['name']} – keep exactly this face, hair and age:"})
            parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(open(ref_path(cid), "rb").read()).decode()}})
    text = prompt
    for cid in SERIES["characters"]:
        text = text.replace(cid, SERIES["characters"][cid]["name"])
    cast = "; ".join(describe(c, outfits.get(c)) for c in chars)
    full = f"{SERIES['style']}. Scene: {text}." + (f" Characters: {cast}. Faces must match the reference photos exactly." if chars else "")
    parts.append({"text": full})
    if extra_parts: parts += extra_parts
    resp = api(IMAGE_MODEL, {"contents": [{"parts": parts}],
                              "generationConfig": {"responseModalities": ["IMAGE"],
                                                   "imageConfig": {"aspectRatio": aspect, "imageSize": IMAGE_SIZE}}})
    data = first_inline(resp)
    open(out, "wb").write(base64.b64decode(data["data"]))
    return out


def gen_refs():
    os.makedirs(os.path.join(SDIR, "refs"), exist_ok=True)
    def one(cid):
        if os.path.exists(ref_path(cid)): return
        c = SERIES["characters"][cid]
        gen_image(f"Character reference portrait of {cid}, upper body, facing the camera, neutral soft studio light, plain dark grey background",
                  [], ref_path(cid), aspect="3:4",
                  extra_parts=[{"text": f"The person: {describe(cid)}."}])
        print("ref", cid, flush=True)
    with ThreadPoolExecutor(3) as ex: list(ex.map(one, SERIES["characters"]))


def gen_images(ep):
    d = ep_dir(ep)
    def one(s):
        out = os.path.join(d, "img", f"{s['id']}.png")
        if os.path.exists(out): return
        try:
            gen_image(s["image"], s.get("chars", []), out, outfits=s.get("outfit"))
            print("img", s["id"], flush=True)
        except Exception as e:
            print("IMG FAIL", s["id"], e, flush=True)
    with ThreadPoolExecutor(4) as ex: list(ex.map(one, ep["shots"]))


def voice_for(who):
    if who == "narrator": return SERIES["narrator_voice"], SERIES["narrator_style"]
    if who in SERIES["characters"]:
        c = SERIES["characters"][who]; return c["voice"], f"Speak as {c['voice_style']}"
    extras = dict(EXTRA_VOICES); extras.update({k: tuple(v) for k, v in SERIES.get("extras", {}).items()})
    v, st = extras.get(who, ("Charon", "a neutral voice")); return v, f"Speak as {st}"


def gen_voice(line, out):
    if os.path.exists(out): return out
    voice, style = voice_for(line["who"])
    how = line.get("how")
    prompt = f"{style}{', ' + how if how else ''}. Say only this, naturally like an actor in a TV drama: {line['text']}"
    resp = api(TTS_MODEL, {"contents": [{"parts": [{"text": prompt}]}],
                           "generationConfig": {"responseModalities": ["AUDIO"],
                                                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
    data = first_inline(resp)
    pcm = base64.b64decode(data["data"])
    rate = 24000
    if "rate=" in data.get("mimeType", ""):
        rate = int(data["mimeType"].split("rate=")[1].split(";")[0])
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return out


def gen_voices(ep):
    d = ep_dir(ep)
    jobs = [(l, os.path.join(d, "audio", f"{s['id']}_{i}.wav")) for s in ep["shots"] for i, l in enumerate(s["lines"])]
    def one(j):
        try:
            if not os.path.exists(j[1]): gen_voice(*j); print("voice", os.path.basename(j[1]), flush=True)
        except Exception as e:
            print("VOICE FAIL", j[1], e, flush=True)
    with ThreadPoolExecutor(4) as ex: list(ex.map(one, jobs))


def gen_thumb(ep):
    d = ep_dir(ep)
    gen_image(ep["thumb_prompt"] + ". Leave the left third and bottom area slightly darker for big title text. Extremely dramatic, high contrast, YouTube thumbnail style but no text.",
              ep.get("thumb_chars", []), os.path.join(d, "thumb_bg.png"), outfits=ep.get("thumb_outfits"))
    print("thumb ok")


def missing(ep):
    d = ep_dir(ep)
    m = [s["id"] for s in ep["shots"] if not os.path.exists(os.path.join(d, "img", f"{s['id']}.png"))]
    a = [f"{s['id']}_{i}" for s in ep["shots"] for i, _ in enumerate(s["lines"]) if not os.path.exists(os.path.join(d, "audio", f"{s['id']}_{i}.wav"))]
    return m, a


if __name__ == "__main__":
    load_series(sys.argv[1])
    ep = json.load(open(sys.argv[1]))
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    if what in ("refs", "all"): gen_refs()
    if what in ("images", "all"): gen_images(ep)
    if what in ("voices", "all"): gen_voices(ep)
    if what in ("thumb", "all"): gen_thumb(ep)
    m, a = missing(ep)
    print("missing images:", m, "missing voices:", a)
