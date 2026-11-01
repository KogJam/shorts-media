"""Render every clip in plan.json, then mix its music bed.
plan.json: [{"id","k","s":"MM:SS","e":"MM:SS","hook","mood"}]  (mood = name of music/<mood>.mp3)
  python3 run.py            -> out/<id>.mp4 (captions) -> final/<id>.mp4 (with music)
Env: SOURCES=sources.json, TAG="@brandhandle" (shown at the bottom, optional)
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cut

def ts(x):
    p = [float(v) for v in str(x).split(":")]
    return p[0] * 60 + p[1] if len(p) == 2 else p[0]

def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))

def mix(cid, mood, loud):
    src = f"out/{cid}.mp4"; d = dur(src); vol = 0.30 if loud else 0.20
    fc = (f"[0:a]asplit[v][sc];[1:a]atrim=0:{d:.2f},volume={vol},afade=t=in:d=1.0,afade=t=out:st={d-2.5:.2f}:d=2.5[m];"
          f"[m][sc]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=500[md];"
          f"[v][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-stream_loop", "-1", "-i", f"music/{mood}.mp3", "-filter_complex", fc,
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
                    f"final/{cid}.mp4"], check=True)

def job(p):
    out = f"out/{p['id']}.mp4"
    try:
        if not os.path.exists(out):
            tz = (ts(p["peak"]) - ts(p["s"])) if p.get("peak") else None
            cut.cut(p["k"], ts(p["s"]), ts(p["e"]) + 0.5, p["hook"], out, 0.5, True, teaser=tz)
        if not os.path.exists(f"final/{p['id']}.mp4"):
            mix(p["id"], p.get("mood", "epic"), p.get("loud_music", False))
        print("ok", p["id"], flush=True)
    except Exception as e:
        print("FAIL", p["id"], e, flush=True)

os.makedirs("out", exist_ok=True); os.makedirs("final", exist_ok=True)
with ThreadPoolExecutor(3) as ex: list(ex.map(job, json.load(open("plan.json"))))
print("DONE")
