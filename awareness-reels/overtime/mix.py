"""Build voice + ambience tracks, join scene clips, and mux the final reel.
Usage: python3 mix.py <output.mp4>   (run after render.py has produced clips/)"""
import sys, os, wave, subprocess, numpy as np, scipy.signal as ss
ROOT = os.path.dirname(os.path.abspath(__file__)); os.chdir(ROOT)
SR = 48000
d = [float(x) for x in open('durs.txt').read().split()]; T = sum(d); N = int(T * SR) + SR
vo = np.zeros(N, np.float32); amb = np.zeros(N, np.float32); t0 = 0
for i, dd in enumerate(d):
    w = wave.open(f'tts/out/{i:02d}.wav'); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    a = ss.resample_poly(a, SR, w.getframerate()).astype(np.float32); s = int((t0 + 0.55) * SR); vo[s:s + len(a)] += a
    L = int(0.5 * SR); nz = np.random.randn(L).astype(np.float32); b, aa = ss.butter(2, [400 / (SR / 2), 3000 / (SR / 2)], 'band'); nz = ss.lfilter(b, aa, nz)
    env = np.sin(np.linspace(0, np.pi, L)) ** 2; s = max(0, int((t0 - 0.15) * SR)); n = len(amb[s:s + L]); amb[s:s + L] += 0.10 * nz[:n] * env[:n]
    L = int(1.2 * SR); tt = np.arange(L) / SR; f = [880, 1174.66, 987.77, 1318.5][i % 4]
    ch = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 4) * 0.05; s = int((t0 + 0.25) * SR); amb[s:s + L] += ch[:len(amb[s:s + L])]
    t0 += dd
tt = np.arange(N) / SR; pad = np.zeros(N)
chords = [[146.83, 220, 293.66, 369.99], [123.47, 185, 246.94, 293.66], [164.81, 246.94, 329.63, 392], [146.83, 220, 293.66, 440]]
seg = int(6 * SR)
for k in range(0, N, seg):
    c = chords[(k // seg) % 4]; L = min(seg + SR, N - k); x = np.arange(L) / SR
    env = np.minimum(1, np.minimum(x / 1.5, (L / SR - x) / 1.5)).clip(0)
    for f in c: pad[k:k + L] += env * (np.sin(2 * np.pi * f * x) + 0.25 * np.sin(2 * np.pi * 2.003 * f * x)) / len(c)
b, aa = ss.butter(2, 1500 / (SR / 2)); pad = ss.lfilter(b, aa, pad) * 0.09 * (1 + 0.15 * np.sin(2 * np.pi * 0.2 * tt))
e = int(T * SR); fade = np.ones(N); fade[e - 2 * SR:e] = np.linspace(1, 0, 2 * SR); fade[e:] = 0
amb = (amb + pad) * fade
def wr(n, x):
    x = (np.clip(x, -1, 1) * 32767).astype(np.int16); w = wave.open(n, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes())
wr('vo.wav', vo[:e]); wr('amb.wav', amb[:e])
open('list.txt', 'w').write(''.join(f"file 'clips/{i:02d}.mp4'\n" for i in range(len(d))))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-c', 'copy', 'silent.mp4'], check=True)
fc = ('[1:a]highpass=f=75,equalizer=f=180:t=q:w=1:g=1.5,equalizer=f=3200:t=q:w=1.2:g=2,deesser=i=0.4,'
      'acompressor=threshold=-22dB:ratio=3:attack=4:release=110:makeup=2,aecho=0.85:0.6:18|31:0.10|0.06[v];'
      '[2:a]volume=0.8[c];[v][c]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000[a]')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'silent.mp4', '-i', 'vo.wav', '-i', 'amb.wav', '-filter_complex', fc,
                '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', sys.argv[1]], check=True)
print('wrote', sys.argv[1])
