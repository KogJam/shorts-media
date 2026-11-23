#!/usr/bin/env python3
"""Gemini TTS: synth(text, voice, style) -> float32 mono at 24 kHz. Key from GEMINI_API_KEY or ~/.config/shorts/env."""
import base64, json, os, sys, time, urllib.request
import numpy as np
if "GEMINI_API_KEY" not in os.environ:
    for l in open(os.path.expanduser("~/.config/shorts/env")):
        if "=" in l and not l.startswith("#"): k, v = l.strip().split("=", 1); os.environ.setdefault(k.replace("export ", ""), v.strip('"\''))
KEY = os.environ["GEMINI_API_KEY"]; MODEL = os.environ.get("TTS_MODEL", "gemini-3.8-flash-tts"); SR = 24000
CACHE = os.path.expanduser("~/.cache/jay_tts"); os.makedirs(CACHE, exist_ok=True)


def pcm(raw):
    """Gemini returns a full WAV file (44-byte header + PCM + a trailing metadata chunk, e.g. the
    'trainedAlgorithmicMedia' AI label). Decoding all bytes as PCM gives a click at the start and a loud scratch
    at the end, so read only the real 'data' chunk."""
    import io, wave
    if raw[:4] == b"RIFF":
        with wave.open(io.BytesIO(raw)) as w:
            assert w.getframerate() == SR and w.getsampwidth() == 2, (w.getframerate(), w.getsampwidth())
            raw = w.readframes(w.getnframes())
    return (np.frombuffer(raw[: len(raw) // 2 * 2], np.int16) / 32768.0).astype(np.float32)


def clean(a):
    """Old cache entries hold the whole WAV file decoded as PCM: rebuild the bytes and parse them properly."""
    raw = np.round(a * 32768.0).astype(np.int16).tobytes()
    return pcm(raw) if raw[:4] == b"RIFF" else a


def synth(text, voice="Charon", style=""):
    import hashlib
    h = hashlib.sha1(f"v2|{MODEL}|{voice}|{style}|{text}".encode()).hexdigest()[:16]; p = os.path.join(CACHE, h + ".npy")
    if os.path.exists(p): return clean(np.load(p))
    # style must go in a "director's notes" block, otherwise the model reads the instruction aloud
    prompt = (f"# Director's notes\nStyle: {style.strip()}\n\n# Transcript\n" if style else "") + text
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}",
                                         json.dumps(body).encode(), {"Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=120))
            b64 = d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
            raw = base64.b64decode(b64); a = pcm(raw)
            if len(a) / SR > 2.0 + 0.6 * len(text.split()):      # model rambled / read the notes: try again
                print("tts too long, retry", round(len(a) / SR, 1), text, file=sys.stderr); continue
            np.save(p, a); return a
        except Exception as e:
            msg = e.read().decode()[:300] if hasattr(e, "read") else str(e)
            print("tts retry", attempt, msg, file=sys.stderr); time.sleep(5 * (attempt + 1))
    raise SystemExit("tts failed: " + text)
