"""Pose library: functions (t) -> pose dict (angles in rad, 0 = straight down, + = toward screen right)."""
import math
def _p(la, ra, ll, rl, **kw): d = dict(la=la, ra=ra, ll=ll, rl=rl); d.update(kw); return d
def idle(t):
    b = math.sin(t * 2.2)
    return _p((-0.22 - 0.03 * b, -0.12), (0.22 + 0.03 * b, 0.12), (-0.04, -0.02), (0.04, 0.02), bob=-2 * b, head=0.03 * math.sin(t * 0.9))
def talk(t):
    p = idle(t); g = math.sin(t * 3.1)
    p["ra"] = (0.5 + 0.25 * g, -0.6 + 0.3 * g); return p
def panic(t):
    w = math.sin(t * 13)
    return _p((-2.5 - 0.25 * w, -2.9 - 0.35 * w), (2.5 + 0.25 * w, 2.9 + 0.35 * w), (-0.12, -0.05), (0.12, 0.05), bob=3 * math.sin(t * 26), head=0.08 * w)
def cover(t):  # crouch, hands on head (front)
    j = math.sin(t * 40) * 0.03
    return _p((-2.3 + j, 2.0), (2.3 - j, -2.0), (-1.25, 0.15), (1.25, -0.15), bob=-150, head=j)
def point(t):
    return _p((-0.2, -0.1), (1.45 + 0.04 * math.sin(t * 5), 1.5), (-0.04, -0.02), (0.04, 0.02), bob=-1.5 * math.sin(t * 2.2))
def look(t):   # hand shading eyes
    return _p((-0.2, -0.1), (2.6, -2.2 + 0.05 * math.sin(t * 2)), (-0.04, -0.02), (0.04, 0.02), head=0.05 * math.sin(t * 0.8))
def cheer(t):
    w = math.sin(t * 9)
    return _p((-2.6, -2.8 - 0.2 * w), (2.6, 2.8 + 0.2 * w), (-0.06, -0.03), (0.06, 0.03), bob=-abs(math.sin(t * 6)) * 30)
# ---- side view (facing right) ----
def walk_side(t, sp=5.5):
    s = math.sin(t * sp); c = math.cos(t * sp)
    return _p((-0.45 * s, -0.45 * s + 0.35), (0.45 * s, 0.45 * s + 0.35), (0.45 * s, 0.45 * s - max(0, -c) * 0.7),
              (-0.45 * s, -0.45 * s - max(0, c) * 0.7), bob=-abs(c) * 8, lean=0.04)
def run_side(t, sp=9.5):
    s = math.sin(t * sp); c = math.cos(t * sp)
    return _p((-0.95 * s, -0.95 * s + 1.5), (0.95 * s, 0.95 * s + 1.5), (0.8 * s + 0.15, 0.8 * s - 0.3 - max(0, -c) * 1.4),
              (-0.8 * s + 0.15, -0.8 * s - 0.3 - max(0, c) * 1.4), bob=-abs(c) * 26 + 10, lean=0.22)
def climb_side(t, sp=6):
    s = math.sin(t * sp)
    return _p((2.4 + 0.3 * s, 2.0), (2.4 - 0.3 * s, 2.0), (0.9 + 0.5 * s, -0.2), (0.9 - 0.5 * s, -0.2), bob=-6 * abs(s), lean=0.15)
def sit_side(t):
    b = math.sin(t * 2)
    return _p((0.5, 1.2), (0.6, 1.3), (1.5, 0.1), (1.45, 0.05), bob=-150 - 2 * b, lean=-0.05, head=0.04 * b)
def stand_side(t):
    b = math.sin(t * 2.2)
    return _p((-0.05, 0.05), (0.05, 0.12), (0.0, 0.0), (0.02, 0.0), bob=-2 * b)
SIDE = {"walk_side", "run_side", "climb_side", "sit_side", "stand_side"}
def get(name, t): return globals()[name](t)
def blend(p, q, u):
    u = max(0.0, min(1.0, u)); u = u * u * (3 - 2 * u)
    out = {}
    for k_ in set(p) | set(q):
        a, b = p.get(k_, q.get(k_)), q.get(k_, p.get(k_))
        out[k_] = tuple(x + (y - x) * u for x, y in zip(a, b)) if isinstance(a, tuple) else a + (b - a) * u
    return out
