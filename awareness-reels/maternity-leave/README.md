# ريل توعوي: إجازة الأمومة (الحلقة 1)

مصدر الفيديو `إجازة_الأمومة_قانون_العمل_الحلقة1.mp4` في جذر المستودع: 1080×1920، 30 إطاراً، 48 ثانية.

## الملفات
- `render.py`: يرسم المشاهد التسعة (PIL) ويخرج كل مشهد إلى `clips/NN.mp4`. النصوص والمواد في قائمة `SC`.
- `durs.txt`: مدة كل مشهد = 0.55 + طول جملته الصوتية + 0.75 (والأخير + 3.4 لبطاقة الختام).
- `mix.py`: يولد الأجواء الصوتية، ويضع الجمل في توقيتها، ويدمج كل شيء في الفيديو النهائي.
- `tts/lines.py`: نص التعليق الصوتي مشكّلاً. `tts/out/NN.wav`: الجمل المختارة.
- `tts/arphon.py` و`tts/best.py`: تحويل النص المشكّل إلى رموز نطق، وتوليد عدة نسخ لكل جملة واختيار الأوضح بـ Whisper.

## المواد المستخدمة (قانون العمل 53/2023)
84 (98 يوم أمومة)، 76 (ساعة رضاعة لسنة)، 83 (رعاية طفل حتى سنة بدون أجر)، 12 (الفصل بسبب الحمل تعسفي)، 11 (تعويض 3 إلى 12 شهراً أو الإعادة)، 9 (التسوية).

## إعادة البناء
```bash
# الخطوط (غير مرفوعة)
mkdir -p fonts && cd fonts && npm pack @fontsource/cairo @fontsource/noto-kufi-arabic \
  && for f in *.tgz; do tar xzf $f && mv package ${f%.tgz}; done && cd ..
pip install --break-system-packages pillow numpy scipy
python3 render.py sheet                       # ورقة فحص sheet.png
seq 0 8 | xargs -P 3 -I{} python3 render.py {} # المشاهد
python3 mix.py "../../إجازة_الأمومة_قانون_العمل_الحلقة1.mp4"
```

## تعديل جملة صوتية
عدّل السطر في `tts/lines.py`، ثم شغّل `best.py` (يحتاج `piper-tts sherpa-onnx` وصوت `vits-piper-ar_JO-SA_dii-high` ونموذج Whisper medium كما في سكل arabic-voiceover) بإعداد `length_scale=0.9`:
```bash
cd tts && python3 best.py ~/tts/vits-piper-ar_JO-SA_dii-high out 0.9
```
إذا تغير طول جملة فأعد حساب `durs.txt` وأعد إخراج مشهدها ثم `mix.py`.
