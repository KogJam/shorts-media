"""Persist an episode's build folder (stills, voices, clips) between daily runs in a git branch.

  python3 buildstore.py save    series/<id>/episodes/epNN.json   # push build/epNN to branch build/<id>-epNN
  python3 buildstore.py restore series/<id>/episodes/epNN.json   # fetch it back into build/epNN
  python3 buildstore.py drop    series/<id>/episodes/epNN.json   # delete the branch after publishing
Only img/, audio/, clips/, thumb_bg.png are stored (no rendered films).
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.environ.get("SHORTS_REPO", "KogJam/shorts-media")
URL = f"https://github.com/{REPO}.git"
KEEP = ("img", "audio", "clips", "thumb_bg.png")


def run(*a, cwd=None, check=True):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode: raise RuntimeError(f"{' '.join(a)}\n{r.stdout}\n{r.stderr}")
    return r


def paths(ep_path):
    sdir = os.path.dirname(os.path.dirname(os.path.abspath(ep_path)))
    ep = json.load(open(ep_path))
    sid = os.path.basename(sdir)
    return os.path.join(sdir, "build", f"ep{ep['episode']:02d}"), f"build/{sid}-ep{ep['episode']:02d}"


def save(ep_path):
    build, branch = paths(ep_path)
    d = tempfile.mkdtemp(prefix="bs_")
    run("git", "init", "-q", "-b", "main", cwd=d)
    for k in KEEP:
        src = os.path.join(build, k)
        if os.path.isdir(src): shutil.copytree(src, os.path.join(d, k), ignore=shutil.ignore_patterns("*.part", "OUT_OF_CREDIT", "DAILY_LIMIT"))
        elif os.path.isfile(src): shutil.copy(src, d)
    run("git", "add", "-A", cwd=d)
    run("git", "-c", "user.name=drama-bot", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-qm", "build state", cwd=d)
    run("git", "push", "-q", "--force", URL, f"main:{branch}", cwd=d)
    shutil.rmtree(d, ignore_errors=True)
    print("saved", branch)


def restore(ep_path):
    build, branch = paths(ep_path)
    r = run("git", "ls-remote", URL, f"refs/heads/{branch}", check=False)
    if not r.stdout.strip():
        print("no saved state for", branch); return False
    d = tempfile.mkdtemp(prefix="bs_")
    run("git", "clone", "-q", "--depth", "1", "--branch", branch, URL, d)
    os.makedirs(build, exist_ok=True)
    for k in KEEP:
        src = os.path.join(d, k)
        if os.path.isdir(src): shutil.copytree(src, os.path.join(build, k), dirs_exist_ok=True)
        elif os.path.isfile(src): shutil.copy(src, build)
    shutil.rmtree(d, ignore_errors=True)
    print("restored", branch); return True


def drop(ep_path):
    _, branch = paths(ep_path)
    run("git", "push", "-q", URL, "--delete", branch, check=False)
    print("dropped", branch)


if __name__ == "__main__":
    {"save": save, "restore": restore, "drop": drop}[sys.argv[1]](sys.argv[2])
