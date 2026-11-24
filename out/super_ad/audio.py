"""Original synthesized score + SFX for the SUPER ad (128 BPM, D minor), no third-party audio."""
import os
import wave

import numpy as np

S = float(os.environ.get("SLOW", "1.0"))  # time scale
SR, DUR, BEAT = 44100, 12.0 * S, 60 / 128 * S
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(1)
L = np.zeros(n)
R = np.zeros(n)


def env(t0, a, d, length=None):
    x = t - t0
    e = np.where(x < 0, 0, np.where(x < a, x / a, np.exp(-(x - a) / d)))
    if length:
        e *= np.clip((t0 + length - t) / 0.3, 0, 1)
    return e


def place(sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    sig = sig[: n - i]
    L[i:i + len(sig)] += sig * gain * (1 - max(pan, 0))
    R[i:i + len(sig)] += sig * gain * (1 + min(pan, 0))


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


hz = lambda m: 440 * 2 ** ((m - 69) / 12)

# dark pad: D minor -> Bb -> F -> C  (two beats... changes every 4 beats)
chords = [[50, 57, 62, 65], [46, 53, 58, 62], [41, 53, 57, 60], [48, 55, 60, 64]]
pad = np.zeros(n)
for k in range(7):
    t0 = k * 4 * BEAT
    ch = chords[k % 4]
    e = np.clip((t - t0) / 0.4, 0, 1) * np.clip((t0 + 4 * BEAT + 0.3 - t) / 0.3, 0, 1)
    for m in ch:
        f = hz(m)
        pad += e * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 1.003 * t) + 0.15 * np.sin(4 * np.pi * f * t))
pad = lowpass(pad, 12) * 0.05
pad *= np.clip(t / (1.5 * S), 0, 1)
L += pad
R += np.roll(pad, 300)

# sub kick on every beat from 2.34s (after logo), half-time before
for b in range(26):
    bt = b * BEAT
    if bt < 2.3 * S and b % 2:
        continue
    seg_t = np.arange(int(0.45 * SR)) / SR
    f = 45 + 70 * np.exp(-seg_t * 25)
    k = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-seg_t * 7)
    place(k, bt, 0.55 if bt >= 2.3 * S else 0.35)

# soft ticks on off-beats in the notes section
for b in range(9, 22):
    bt = b * BEAT + BEAT / 2
    nz = rng.standard_normal(int(0.05 * SR))
    nz = (nz - lowpass(nz, 6)) * np.exp(-np.arange(len(nz)) / SR * 80)
    place(nz, bt, 0.08, 0.3 if b % 2 else -0.3)


# shimmer (logo reveal + end card + label glint)
def shimmer(t0, length, gain):
    s = np.zeros(int(length * SR))
    tt = np.arange(len(s)) / SR
    for m in (86, 90, 93, 98, 102):
        s += np.sin(2 * np.pi * hz(m) * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * (6 + m % 5) * tt))
    s *= np.clip(tt / 0.3, 0, 1) * np.exp(-tt / (length * 0.5))
    place(s, t0, gain, 0.2)
    place(np.roll(s, 900), t0, gain, -0.2)


shimmer(0.15 * S, 2.0 * S, 0.035)
shimmer(7.45 * S, 1.2 * S, 0.03)
shimmer(10.95 * S, 1.0 * S, 0.03)


# whooshes at transitions
def whoosh(t0, length=0.6, gain=0.25):
    nz = rng.standard_normal(int(length * SR))
    tt = np.arange(len(nz)) / SR
    e = np.sin(np.pi * tt / length) ** 2
    out = np.zeros_like(nz)
    for k, w in ((40, 0.6), (12, 0.4)):
        out += lowpass(nz, k) * w
    place(out * e * 3, t0 - length / 2, gain)


for tw in (2.3, 4.2, 7.02, 10.45):
    whoosh(tw * S, 0.6 * S)

# atomizer "psst" on the cap shot
nz = rng.standard_normal(int(0.35 * SR))
nz = nz - lowpass(nz, 3)
place(nz * np.exp(-np.arange(len(nz)) / SR * 6) * np.clip(np.arange(len(nz)) / SR / 0.02, 0, 1), 2.55 * S, 0.12)

# riser into the poster reveal + impact
rl = 1.4 * S
tt = np.arange(int(rl * SR)) / SR
rs = rng.standard_normal(len(tt))
rs = lowpass(rs, 4) * (tt / rl) ** 2 + 0.3 * np.sin(2 * np.pi * (200 + 600 * (tt / rl) ** 2) * tt) * (tt / rl) ** 2
place(rs, 8.62 * S - rl, 0.18)
seg_t = np.arange(int(1.6 * S * SR)) / SR
boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-seg_t * 8)) / SR) * np.exp(-seg_t * 2.2 / S)
boom += lowpass(rng.standard_normal(len(seg_t)), 20) * np.exp(-seg_t * 6) * 0.6
place(boom, 8.6 * S, 0.8)

# master: fade out, soft clip, normalise
fade = np.clip((DUR - t) / (0.8 * S), 0, 1)
mix = np.stack([L, R], 1) * fade[:, None]
mix = np.tanh(mix * 1.4)
mix = mix / np.abs(mix).max() * 0.89
pcm = (mix * 32767).astype(np.int16)
with wave.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.environ.get("AOUT", "score.wav")), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("ok")
