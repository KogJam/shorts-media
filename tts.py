"""Offline English TTS: CMUdict G2P -> Kokoro ONNX (no network needed after setup)."""
import json, re, os
import numpy as np
import onnxruntime as ort

BASE = os.environ.get("SHORTS_ASSETS", os.path.expanduser("~/tts"))
_VOCAB = json.load(open(f"{BASE}/kokoro-onnx/src/kokoro_onnx/config.json"))["vocab"]
_SESS = None
_VOICES = None
_DICT = None
SR = 24000

VOWELS = {"AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "W", "AY": "I", "EH": "ɛ",
          "ER": "ɜɹ", "EY": "A", "IH": "ɪ", "IY": "i", "OW": "O", "OY": "Y", "UH": "ʊ", "UW": "u"}
CONS = {"B": "b", "CH": "ʧ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "ʤ",
        "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s",
        "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num2words(n: int) -> str:
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000: return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + num2words(n % 100))
    for div, name in ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand")):
        if n >= div:
            r = n % div
            return num2words(n // div) + " " + name + ("" if r == 0 else " " + num2words(r))
    return str(n)


def _load():
    global _SESS, _VOICES, _DICT
    if _SESS is None:
        _SESS = ort.InferenceSession(f"{BASE}/kokoro.onnx", providers=["CPUExecutionProvider"])
        _VOICES = np.load(f"{BASE}/voices.bin")
        _DICT = {}
        for line in open(f"{BASE}/cmudict/cmudict.dict", encoding="utf8"):
            w, *ph = line.split("#")[0].split()
            if "(" in w: continue  # keep first pronunciation
            _DICT[w] = ph


def normalize(text: str) -> str:
    text = text.replace("%", " percent").replace("&", " and ").replace("°C", " degrees Celsius")
    text = text.replace("°F", " degrees Fahrenheit").replace("°", " degrees").replace("—", ", ").replace("–", " to ")
    text = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    text = re.sub(r"(\d+)\.(\d+)", lambda m: num2words(int(m[1])) + " point " + " ".join(ONES[int(d)] for d in m[2]), text)
    text = re.sub(r"\d+", lambda m: num2words(int(m[0])), text)
    return text


FUNCTION = {"the": "ðə", "a": "ə", "an": "ən", "of": "əv", "to": "tə", "and": "ænd", "in": "ɪn",
            "is": "ɪz", "it": "ɪt", "its": "ɪts", "that": "ðæt", "for": "fɔɹ", "on": "ɑn", "are": "ɑɹ",
            "as": "æz", "at": "æt", "be": "bi", "by": "baɪ", "or": "ɔɹ", "from": "fɹʌm", "was": "wʌz",
            "with": "wɪð", "can": "kæn", "your": "jɔɹ", "you": "ju", "than": "ðæn", "their": "ðɛɹ",
            "they": "ðA", "them": "ðɛm", "this": "ðɪs", "into": "ɪntu", "but": "bʌt", "has": "hæz",
            "have": "hæv", "were": "wɜɹ", "do": "du", "does": "dʌz", "we": "wi", "he": "hi", "his": "hɪz"}
CUSTOM = {}  # word -> IPA overrides, filled from custom_words.json if present
if os.path.exists(os.path.join(os.path.dirname(__file__), "custom_words.json")):
    CUSTOM = json.load(open(os.path.join(os.path.dirname(__file__), "custom_words.json")))


def _lookup(w):
    if w in _DICT: return _DICT[w]
    for suf, add in (("'s", ["Z"]), ("es", ["IH0", "Z"]), ("s", ["Z"]), ("ed", ["D"]), ("d", ["D"]), ("ing", ["IH0", "NG"]), ("ly", ["L", "IY0"])):
        if w.endswith(suf) and w[: -len(suf)] in _DICT:
            return _DICT[w[: -len(suf)]] + add
    return None


def word_ipa(word: str):
    w = word.lower().strip("'")
    if w in CUSTOM: return CUSTOM[w]
    if w in FUNCTION: return FUNCTION[w]
    ph = _lookup(w)
    if ph is None:
        return None
    out = []
    for p in ph:
        m = re.match(r"([A-Z]+)([012]?)", p)
        base, st = m[1], m[2]
        if base in VOWELS:
            v = VOWELS[base]
            if st == "0":
                v = {"ʌ": "ə", "ɜɹ": "əɹ", "ɪ": "ɪ"}.get(v, v)
            out.append(("ˈ" if st == "1" else "ˌ" if st == "2" else "") + v)
        else:
            out.append(CONS[base])
    return "".join(out)


def missing_words(text: str):
    _load()
    words = re.findall(r"[A-Za-z']+", normalize(text))
    return sorted({w for w in words if word_ipa(w) is None})


def phonemize(text: str) -> str:
    _load()
    parts = []
    for tok in re.findall(r"[A-Za-z']+|[.,!?;:]", normalize(text)):
        if tok in ".,!?;:":
            if parts: parts[-1] += tok
            continue
        ipa = word_ipa(tok)
        if ipa is None:  # spell it out letter by letter as a last resort
            ipa = " ".join(word_ipa(c) or "" for c in tok.lower())
        parts.append(ipa)
    return " ".join(parts)


def synth(text: str, voice="am_michael", speed=1.05) -> np.ndarray:
    _load()
    ph = phonemize(text)
    toks = [_VOCAB[c] for c in ph if c in _VOCAB][:510]
    style = _VOICES[voice][len(toks)]
    audio = _SESS.run(None, {"tokens": np.array([[0, *toks, 0]], dtype=np.int64),
                             "style": style.astype(np.float32),
                             "speed": np.array([speed], dtype=np.float32)})[0]
    return audio.reshape(-1).astype(np.float32)


if __name__ == "__main__":
    import sys, wave
    t = sys.argv[1] if len(sys.argv) > 1 else "Did you know that octopuses have three hearts? Two of them stop beating when they swim."
    print(phonemize(t))
    a = synth(t)
    with wave.open("/tmp/claude-0/test.wav", "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    print(len(a) / SR, "s")
