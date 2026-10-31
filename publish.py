"""Host rendered MP4s at public URLs for Metricool by force-pushing them to the repo's `videos` branch.

usage: python3 publish.py out/a.mp4 out/b.mp4 ...
Prints one public raw URL per file. The branch is replaced each run (old videos are no longer
needed: Metricool copies the file to its own storage the moment a post is scheduled).
"""
import os, sys, shutil, subprocess, tempfile, time

REPO = os.environ.get("SHORTS_REPO", "KogJam/shorts-media")


def run(*a, cwd=None):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f"{' '.join(a)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def publish(files):
    d = tempfile.mkdtemp(prefix="videos_")
    run("git", "init", "-q", "-b", "videos", cwd=d)
    names = []
    for f in files:
        name = os.path.basename(f)
        shutil.copy(f, os.path.join(d, name)); names.append(name)
    run("git", "add", "-A", cwd=d)
    run("git", "-c", "user.name=shorts-bot", "-c", "user.email=noreply@users.noreply.github.com",
        "commit", "-qm", f"videos {time.strftime('%Y-%m-%d %H:%M')}", cwd=d)
    run("git", "push", "-q", "--force", f"https://github.com/{REPO}.git", "videos:videos", cwd=d)
    shutil.rmtree(d, ignore_errors=True)
    return [f"https://raw.githubusercontent.com/{REPO}/videos/{n}" for n in names]


if __name__ == "__main__":
    for u in publish(sys.argv[1:]):
        print(u)
