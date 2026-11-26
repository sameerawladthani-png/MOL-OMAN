import sys, os, re, wave, difflib, numpy as np, scipy.signal as ss, sherpa_onnx
from piper import PiperVoice, SynthesisConfig
from lines import L
from arphon import phonemize
d, out, ls = sys.argv[1], sys.argv[2], float(sys.argv[3])
onnx = [f for f in os.listdir(d) if f.endswith('.onnx')][0]
v = PiperVoice.load(f'{d}/{onnx}', config_path=f'{d}/{onnx}.json'); SR = v.config.sample_rate
w = 'sherpa-onnx-whisper-medium'
r = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=f'{w}/medium-encoder.int8.onnx', decoder=f'{w}/medium-decoder.int8.onnx', tokens=f'{w}/medium-tokens.txt', language='ar', task='transcribe', num_threads=2)
def norm(s):
    s = re.sub('[ً-ْـ]', '', s); s = re.sub('[^ء-ي ]', '', s)
    for a, b in (('أ','ا'),('إ','ا'),('آ','ا'),('ة','ه'),('ى','ي')): s = s.replace(a, b)
    return ' '.join(s.split())
os.makedirs(out, exist_ok=True)
for i in ([int(x) for x in os.environ["IDX"].split(",")] if os.environ.get("IDX") else range(len(L))):
    ref = norm(L[i]); best = None
    for ns, nw in [(0.45,0.7),(0.55,0.8),(0.35,0.6),(0.5,0.75),(0.4,0.9)]:
        a = np.asarray(v.phoneme_ids_to_audio(v.phonemes_to_ids(list(phonemize(L[i]))), SynthesisConfig(length_scale=ls, noise_scale=ns, noise_w_scale=nw)), dtype=np.float32)
        x = ss.resample_poly(a, 16000, SR).astype('float32'); x = np.concatenate([np.zeros(8000,'float32'), x, np.zeros(16000,'float32')])  # الحشو يمنع Whisper من قطع آخر كلمة
        st = r.create_stream(); st.accept_waveform(16000, x); r.decode_stream(st)
        sc = difflib.SequenceMatcher(None, ref, norm(st.result.text)).ratio()
        if best is None or sc > best[0]: best = (sc, a, st.result.text)
        if sc > 0.97: break
    pcm = (np.clip(best[1], -1, 1) * 32767).astype(np.int16)
    with wave.open(f'{out}/{i:02d}.wav', 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
    print(i, round(best[0],3), round(len(pcm)/SR,2), best[2], flush=True)
