"""Vocal (speech) separation with UVR-MDX-NET-Voc_FT (ONNX) – removes background music from a clip's audio.
python3 sep.py in.mp4 out_vocals.wav
"""
import sys, subprocess, numpy as np, onnxruntime as ort

N_FFT, HOP, DIM_F, DIM_T, COMP = 7680, 1024, 3072, 256, 1.021
SR = 44100
MODEL = "/home/claude/models/UVR-MDX-NET-Voc_FT.onnx"
WIN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)  # periodic hann


def load(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"])
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()


def stft(x):  # x: [ch, n] -> [ch, F, T] complex, torch center=True reflect
    pad = N_FFT // 2
    xp = np.pad(x, ((0, 0), (pad, pad)), mode="reflect")
    nfr = 1 + (xp.shape[1] - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(nfr)[:, None]
    fr = xp[:, idx] * WIN  # [ch, T, N]
    return np.fft.rfft(fr, axis=-1).transpose(0, 2, 1)


def istft(S, length):  # S [ch, F, T]
    fr = np.fft.irfft(S.transpose(0, 2, 1), n=N_FFT, axis=-1) * WIN  # [ch,T,N]
    T = fr.shape[1]; n = N_FFT + HOP * (T - 1)
    out = np.zeros((S.shape[0], n), np.float32); wsum = np.zeros(n, np.float32)
    for t in range(T):
        out[:, t * HOP:t * HOP + N_FFT] += fr[:, t]; wsum[t * HOP:t * HOP + N_FFT] += WIN ** 2
    out /= np.maximum(wsum, 1e-8)
    pad = N_FFT // 2
    return out[:, pad:pad + length]


def separate(mix):
    sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    n = mix.shape[1]; chunk = HOP * (DIM_T - 1); trim = N_FFT // 2; gen = chunk - 2 * trim
    pad = gen - n % gen
    mp = np.concatenate([np.zeros((2, trim), np.float32), mix, np.zeros((2, pad + trim), np.float32)], 1)
    outs = []
    for i in range(0, n + pad, gen):
        w = mp[:, i:i + chunk]
        S = stft(w)[:, :DIM_F, :DIM_T]  # [2, F, T]
        x = np.stack([S[0].real, S[0].imag, S[1].real, S[1].imag])[None].astype(np.float32)
        y = sess.run(None, {name: x})[0][0]
        Sv = np.zeros((2, N_FFT // 2 + 1, DIM_T), np.complex64)
        Sv[0, :DIM_F] = y[0] + 1j * y[1]; Sv[1, :DIM_F] = y[2] + 1j * y[3]
        v = istft(Sv, chunk)
        outs.append(v[:, trim:trim + gen])
    return np.concatenate(outs, 1)[:, :n] * COMP


if __name__ == "__main__":
    mix = load(sys.argv[1])
    voc = separate(mix)
    import wave
    pcm = (np.clip(voc.T, -1, 1) * 32767).astype("<i2")
    with wave.open(sys.argv[2], "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print("ok", sys.argv[2], round(voc.shape[1] / SR, 1), "s")
