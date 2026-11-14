#!/usr/bin/env python3
"""gen_img.py out.png "prompt" [ref.png ...] [--ar 9:16] -- Gemini image generation with optional reference images."""
import base64, json, os, sys, time, urllib.request
KEY = os.environ["GEMINI_API_KEY"]; MODEL = os.environ.get("IMG_MODEL", "gemini-3.1-flash-image")
STYLE = ("2D flat cartoon illustration in a clean educational-animation style: characters have simple round cream-colored heads, "
         "small dot eyes with short expressive eyebrows, minimal features, thick dark-brown outlines, real clothing drawn simply, "
         "muted natural colors with soft cel shading, detailed painterly background, no text, no letters, no logos, no watermark.")
def gen(out, prompt, refs=(), ar="9:16"):
    parts = [{"inline_data": {"mime_type": "image/png", "data": base64.b64encode(open(r, "rb").read()).decode()}} for r in refs]
    parts.append({"text": STYLE + " " + prompt + (" Keep the character exactly identical to the reference image (same face, hair, clothes, colors)." if refs else "")})
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ar}}}
    for attempt in range(3):
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}",
                                         json.dumps(body).encode(), {"Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=180))
            for p in d["candidates"][0]["content"]["parts"]:
                if "inlineData" in p or "inline_data" in p:
                    open(out, "wb").write(base64.b64decode((p.get("inlineData") or p["inline_data"])["data"])); return out
            raise RuntimeError(str(d)[:300])
        except Exception as e:
            print("retry", attempt, e, file=sys.stderr); time.sleep(4)
    raise SystemExit("failed " + out)
if __name__ == "__main__":
    a = sys.argv[1:]; ar = "9:16"
    if "--ar" in a: i = a.index("--ar"); ar = a[i + 1]; del a[i:i + 2]
    print(gen(a[0], a[1], a[2:], ar))
