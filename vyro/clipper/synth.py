"""Original, algorithmically generated background beds (no samples, no existing melodies) -> music2/<mood>.wav"""
import numpy as np, wave, os, subprocess
SR = 44100
os.makedirs("music2", exist_ok=True)
rng = np.random.default_rng(11)


def note(f, d, a=0.3, dec=3.0, harm=(1, .5, .25)):
    t = np.arange(int(d * SR)) / SR
    s = sum(h * np.sin(2 * np.pi * f * (i + 1) * t) for i, h in enumerate(harm))
    return s * np.exp(-t * dec) * a


def pad(freqs, d, a=0.12):
    t = np.arange(int(d * SR)) / SR
    env = np.clip(t / 1.5, 0, 1) * np.clip((d - t) / 1.5, 0, 1)
    s = sum(np.sin(2 * np.pi * f * t + i) + .3 * np.sin(2 * np.pi * f * 2.003 * t) for i, f in enumerate(freqs))
    return s / len(freqs) * env * a


def kick(a=.5):
    t = np.arange(int(.35 * SR)) / SR
    return np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 9) * a


def hat(a=.05):
    n = int(.06 * SR)
    return rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 60) * a


def place(buf, x, at):
    i = int(at * SR)
    if i >= len(buf): return
    j = min(len(buf), i + len(x)); buf[i:j] += x[:j - i]


def mtof(m): return 440 * 2 ** ((m - 69) / 12)


def build(name, dur, bpm, chords, kick_pat, hats, arp, drone):
    L = np.zeros(int(dur * SR)); R = np.zeros(int(dur * SR))
    beat = 60 / bpm; bar = beat * 4
    nb = int(dur / bar) + 1
    for b in range(nb):
        ch = chords[b % len(chords)]
        p = pad([mtof(m) for m in ch], bar + 1.5)
        place(L, p, b * bar); place(R, p * .9, b * bar + .01)
        for k in kick_pat:
            place(L, kick(), b * bar + k * beat); place(R, kick(), b * bar + k * beat)
        if hats:
            for h in range(8):
                hh = hat(.04 if h % 2 else .025)
                place(L if h % 2 else R, hh, b * bar + h * beat / 2)
        if arp:
            for s in range(8):
                m = ch[rng.integers(0, len(ch))] + 12 * rng.integers(1, 3)
                n = note(mtof(m), .6, .07, 5)
                place(L if s % 2 else R, n, b * bar + s * beat / 2)
    if drone:
        t = np.arange(len(L)) / SR
        d = np.sin(2 * np.pi * mtof(drone) * t) * .08 * (0.7 + .3 * np.sin(2 * np.pi * .1 * t))
        L += d; R += d
    x = np.stack([L, R], 1); x /= np.abs(x).max() + 1e-9; x *= .9
    tmp = f"music2/{name}_dry.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", "aecho=0.8:0.6:60|180:0.25|0.15,loudnorm=I=-16",
                    f"music2/{name}.wav"], check=True)
    os.remove(tmp)
    print(name)


# minor, slow, heartbeat (tense) – Am F C E
build("tense", 80, 72, [[57, 60, 64], [53, 57, 60], [48, 52, 55], [52, 56, 59]], [0, 0.75, 2, 2.75], False, False, 45)
# driving adventure – Dm Bb F C
build("epic", 80, 100, [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]], [0, 1.5, 2, 3], True, False, 38)
# light / playful – C G Am F (no melody, random arpeggio)
build("quirky", 80, 112, [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]], [0, 2], True, True, None)
