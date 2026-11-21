#!/usr/bin/env python3
"""Rate downloaded streamer clips against a campaign brief with Gemini (video in, JSON out).
python3 pick.py <brief.txt> <clip1.mp4> [clip2.mp4 ...]  -> prints JSON list, also writes picks.json
Per clip: fits (bool), score 1-10, reason, hook (<=8 words + 1 emoji), title (YouTube, <=70 chars), start/end (trim, s)."""
import base64, json, os, subprocess, sys, urllib.request

MODEL = os.environ.get("MODEL", "gemini-3.5-flash")


def key():
    for l in open(os.path.expanduser("~/.config/shorts/env")):
        if l.startswith("GEMINI_API_KEY"): return l.split("=", 1)[1].strip().strip('"')


def proxy(p):
    out = p[:-4] + "_360.mp4"
    if not os.path.exists(out):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", p, "-vf", "scale=-2:360", "-r", "15", "-c:v", "libx264",
                        "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "48k", "-ac", "1", out], check=True)
    return out


def rate(brief, clip):
    b64 = base64.b64encode(open(proxy(clip), "rb").read()).decode()
    prompt = ("You pick clips for a paid clipping campaign. Campaign brief:\n" + brief + "\n\n"
              "Watch this stream clip (landscape, streamer facecam + gameplay). Decide if it qualifies under the brief "
              "(right streamer, right game, allowed content, not negative about the streamer/sponsor) and how viral it can be "
              "as a YouTube Short / Reel (a clear funny, crazy or surprising moment understandable without context). "
              "Return ONLY JSON {\"fits\":true/false,\"score\":1-10,\"reason\":\"...\",\"hook\":\"max 8 words, curiosity, "
              "1 emoji at the end, NOT misleading\",\"title\":\"YouTube Shorts title max 70 chars, accurate\",\"start\":s,\"end\":s} "
              "where start/end trim dead air (keep 15-45 s, cut right after the payoff).")
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": b64}}, {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}}
    r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key()}",
                               json.dumps(body).encode(), {"Content-Type": "application/json"})
    j = json.loads(urllib.request.urlopen(r, timeout=300).read())
    d = json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
    if isinstance(d, list): d = d[0]
    d["clip"] = clip
    return d


if __name__ == "__main__":
    brief = open(sys.argv[1]).read()
    res = []
    for c in sys.argv[2:]:
        try: res.append(rate(brief, c))
        except Exception as e: res.append({"clip": c, "error": str(e)[:300]})
    res.sort(key=lambda d: -(d.get("score", 0) if d.get("fits") else -1))
    json.dump(res, open("picks.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
