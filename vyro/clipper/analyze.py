"""Upload a source video (180p + original audio) to Gemini and ask for the most viral 60-75 s segments.
python3 analyze.py v1   -> writes ana/v1.json
"""
import json, os, sys, time, subprocess, urllib.request

KEY = [l.split("=", 1)[1].strip().strip('"') for l in open(os.path.expanduser("~/.config/shorts/env"))
       if l.startswith("GEMINI_API_KEY") or l.startswith("export GEMINI_API_KEY")][0]
BASE = "https://generativelanguage.googleapis.com"
MODEL = os.environ.get("MODEL", "gemini-3.5-flash")


def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(r, timeout=600) as f:
        return f.headers, f.read()


def upload(path, mime="video/mp4"):
    size = os.path.getsize(path)
    h, _ = req(f"{BASE}/upload/v1beta/files?key={KEY}", json.dumps({"file": {"display_name": os.path.basename(path)}}).encode(),
               {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(size), "X-Goog-Upload-Header-Content-Type": mime,
                "Content-Type": "application/json"}, "POST")
    up = h["X-Goog-Upload-URL"]
    _, body = req(up, open(path, "rb").read(), {"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}, "POST")
    f = json.loads(body)["file"]
    while f.get("state") == "PROCESSING":
        time.sleep(10)
        _, b = req(f"{BASE}/v1beta/{f['name']}?key={KEY}")
        f = json.loads(b)
    print("uploaded", f["name"], f.get("state"))
    return f


CONTEXT = open(os.environ.get("BRIEF", "brief.txt")).read().replace("{", "(").replace("}", ")")
PROMPT = """You are a top short-form video editor (TikTok / YouTube Shorts / Reels). Campaign brief / context:
""" + CONTEXT + """
This file is one of the campaign's raw source videos.
Find the {n} moments with the highest viral potential that work as STANDALONE clips of 60-75 seconds
(ideal ~65 s; or the length the brief asks for): danger, conflict, surprise, funny or emotional moments, strong
one-liners, reveals, useful tricks, anything that makes people stop scrolling, and anything the brief asks for. Each clip must start right at something gripping (no slow intro, no mid-sentence
start) and end at a natural payoff/end of a sentence. Clips must not overlap.

Return ONLY JSON: {{"segments":[{{"start":"MM:SS","end":"MM:SS","score":1-10,"why":"...","hook":"on-screen hook text,
max 8 words, curiosity-driven, may end with one emoji","title":"YouTube title max 70 chars","caption":"TikTok caption 1-2 sentences",
"subject_x":0.0-1.0 (horizontal position of the main subject/person for a vertical 9:16 crop, 0.5=center),
"wide": true if the important action is spread across the whole frame (vertical crop would lose it)}}]}}
Order by score, best first. Timestamps must be precise to the second."""


def analyze(key, n=8):
    src = f"src/{key}_ana.mp4"
    if not os.path.exists(src):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"src/{key}_180.mp4", "-i", f"src/{key}.m4a",
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "48k", "-ac", "1", "-shortest", src], check=True)
    f = upload(src)
    body = {"contents": [{"parts": [{"file_data": {"mime_type": "video/mp4", "file_uri": f["uri"]}},
                                    {"text": PROMPT.format(n=n)}]}],
            "generationConfig": {"responseMimeType": "application/json", "mediaResolution": "MEDIA_RESOLUTION_LOW"}}
    _, b = req(f"{BASE}/v1beta/models/{MODEL}:generateContent?key={KEY}", json.dumps(body).encode(),
               {"Content-Type": "application/json"}, "POST")
    j = json.loads(b)
    txt = j["candidates"][0]["content"]["parts"][0]["text"]
    os.makedirs("ana", exist_ok=True)
    data = json.loads(txt)
    if isinstance(data, list): data = {"segments": data}
    data["usage"] = j.get("usageMetadata")
    json.dump(data, open(f"ana/{key}.json", "w"), indent=1, ensure_ascii=False)
    for s in data["segments"]:
        print(key, s["start"], s["end"], s["score"], s["hook"], "|", s["why"][:90])


if __name__ == "__main__":
    analyze(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8)
