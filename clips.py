"""Stock footage: Pexels search + download cache, and a frame reader that streams clips via ffmpeg."""
import json, os, subprocess, urllib.request, urllib.parse, hashlib
import numpy as np

CACHE = os.path.expanduser("~/.cache/shorts_clips")
os.makedirs(CACHE, exist_ok=True)
_REG = os.path.join(CACHE, "registry.json")
REGISTRY = json.load(open(_REG)) if os.path.exists(_REG) else {}


def save_registry():
    json.dump(REGISTRY, open(_REG, "w"))


def get_by_id(cid):
    """Download a clip previously seen in a search (pick.py) by its id."""
    c = REGISTRY.get(str(cid))
    if not c: return None, None
    return download(c["url"]), c


def pexels_search(query, orientation="portrait", min_dur=4, per_page=8):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not set")
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": orientation, "per_page": per_page, "size": "medium"})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "shorts-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    out = []
    for v in data.get("videos", []):
        if v.get("duration", 0) < min_dur: continue
        files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
        # prefer ~1080 wide portrait files, else the largest under 1440
        files.sort(key=lambda f: (abs(f["width"] - 1080), -f["height"]))
        if files:
            out.append({"id": v["id"], "url": files[0]["link"], "page": v["url"], "user": v["user"]["name"],
                        "duration": v["duration"], "w": files[0]["width"], "h": files[0]["height"]})
    return out


def pixabay_search(query, orientation="portrait", min_dur=4, per_page=12):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("PIXABAY_API_KEY not set")
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {"key": key, "q": query[:100], "per_page": per_page, "safesearch": "true", "order": "popular"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "shorts-bot"}), timeout=30) as r:
        data = json.load(r)
    out = []
    for v in data.get("hits", []):
        if v.get("duration", 0) < min_dur: continue
        files = [f for f in v["videos"].values() if f.get("url") and f.get("width")]
        files.sort(key=lambda f: (abs(min(f["width"], f["height"]) - 1080), -f["height"]))
        f = files[0]
        portrait = f["height"] > f["width"]
        out.append({"id": v["id"], "url": f["url"], "page": v["pageURL"], "user": v.get("user", ""),
                    "duration": v["duration"], "w": f["width"], "h": f["height"], "portrait": portrait})
    # prefer the requested orientation, keep relevance order otherwise
    if orientation == "portrait":
        out.sort(key=lambda c: not c["portrait"])
    return out


def search(query, orientation="portrait"):
    if os.environ.get("PIXABAY_API_KEY"):
        return pixabay_search(query, orientation)
    return pexels_search(query, orientation)


def download(url):
    name = hashlib.md5(url.encode()).hexdigest()[:16] + ".mp4"
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": "shorts-bot"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
            while chunk := r.read(1 << 20): f.write(chunk)
        os.rename(path + ".part", path)
    return path


def get_clip(query, used_ids=None, orientation="portrait"):
    """Return (local_path, credit dict) for the best unused clip matching query, or (None, None)."""
    used_ids = used_ids if used_ids is not None else set()
    try:
        res = search(query, orientation)
        if not res and " " in query:  # retry with a shorter query
            res = search(" ".join(query.split()[:2]), orientation)
    except Exception as e:
        print("clip search failed:", query, e)
        return None, None
    for c in res:
        if c["id"] in used_ids: continue
        try:
            p = download(c["url"])
            used_ids.add(c["id"])
            return p, c
        except Exception as e:
            print("download failed:", e)
    return None, None


def probe_duration(path):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())
    except Exception:
        return 0.0


class ClipReader:
    """Streams RGBA frames of `path`, scaled+cropped to (w,h), at fps, looping forever."""

    def __init__(self, path, w, h, fps=30, start=0.0, speed=1.0):
        self.w, self.h = w, h
        dur = probe_duration(path)
        if dur and start >= dur - 1: start = 0
        vf = f"setpts=PTS/{speed},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=rgba"
        self.p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-ss", str(start), "-i", path,
                                   "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                                  stdout=subprocess.PIPE, bufsize=w * h * 4 * 2)
        self.n = w * h * 4

    def frame(self):
        b = self.p.stdout.read(self.n)
        if len(b) < self.n: return None
        return b

    def close(self):
        try:
            self.p.kill(); self.p.wait(timeout=2)
        except Exception:
            pass
