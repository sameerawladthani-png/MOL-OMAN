---
videomd: 1
name: 8a0fc128-360p
description: 'AI perfume teaser where the scent''s spray transforms into crystal flower and butterflies and then reassembles as the bottle packshot. Made with (inferred): AI-generated video 100%'
source:
  file: 8a0fc128-360p.mp4
  sha256: ef282454025b89711f8c483a530563d52dd33bed1eb6f6778837e02f916a1d3c
  duration: 10.04
  size: 360x640
  fps: 25.0
  aspect: '9:16'
shots: 1
lang: en
made_mix:
  ai_video: 1.0
confidence: 0.757
readers:
- tools
- agent
open_questions: 2
generator:
  name: rea-video
  version: 0.1.0
---

# 8a0fc128-360p.mp4

**Verdict** (inferred): Mixed production: AI-generated video 100%; overlays: styled text, text labels, subtitles (composited in code / an editor); audio: music 127.6BPM (to confirm, leaning stock library music); packaging: styled text ×3, text labels ×3
**What it says**: AI perfume teaser where the scent's spray transforms into crystal flower and butterflies and then reassembles as the bottle packshot.
**Narrative**: #01 grab attention
**Made with** (inferred, by duration): AI-generated video 100%
**Remake**: 1 AI video shot → 1 generation unit, 1 MiniMax H3 / H3 Max call

## Next steps

- Remake: Capsule Cinema does the generation, assembly and checks. `rea-video remake <this dir>` hands over to it, does what can be done automatically and keeps the original elsewhere; `remake/status.md` says per shot what is left. Add incoming clips to `remake/mine.json` and run it again
- AI shots: prompts are in the generation units of `video/remake.md`; for automatic generation use Capsule Cinema: `scripts/remake_reference.py prepare <this dir>`, then `run <jobs.json> --dry-run` (paid: ask the user first)

## Open questions

- No AI listened to the soundtrack (the review covered the picture only): real voice versus TTS is inferred from the waveform; the effects were found on the separ…
- music source to confirm: most likely stock library music (52%); how to check is under “Sound”

## Map

Read this page first; for detail, open only the file you need. Each line is `path | ~tokens | what is in it · when to read it`; paths are relative to this directory.

```videomd-map
video/timeline.md | 245 | Timeline: one line per shot · what a stretch says, which shots need review, how a shot was made
video/moments.md | 47 | Special moments · reveals, twists, climaxes, goofs: times, key frames, clips
video/content.md | 151 | Content and structure · what it says, the narrative line, structure, the script
video/cast.md | 103 | Cast, scenes and props · reference images for characters, first-frame prompts
video/sound.md | 353 | Sound · voice, music, sound effects, beats and sources
video/rhythm.md | 124 | Rhythm and key frames · when cuts and transitions happen, shot lengths, the change curve, key frames of each shot
video/look.md | 490 | Camera, lighting and editing · for filmed shots: framing, camera, lighting, kit
video/packaging.md | 331 | Packaging · subtitles, styled text, stickers, picture-in-picture: timing and style
video/remake.md | 895 | Remake plan · generation units, shoots, code builds, real material to collect, acting and emotion
video/shots/*.md | 803 | Per-shot detail, tokens per file on average · checking one shot: what is seen, the inference and its basis, prompts, frames
breakdown.json | 9912 | Full raw data · for programs; a model rarely needs it
shots/ | - | contact sheet, first and last frame of each shot · checking by eye
storyboard.jpg | - | storyboard of the whole video · the whole video at a glance
stems/ | - | voice, music and effects stems · listening, remaking the sound
packaging/ | - | subtitle files, packaging timeline, sticker frames · remaking subtitles and packaging
audio.png | - | waveform and beat chart · seeing the rhythm
```

## How to read

- One shot per line: `#<n> start-end (s) | key value | …`. A key ending in `~` is the tools' inference; keys without it are visible on screen or measured directly.
- `story` job in the story and the point · `seen` what is on screen · `act` acting (emotion, strength, face) · `camera` camera move · `overlay` overlays · `made~` how it was made (inferred) · `material~` where the material came from (inferred) · `remake` remake route · `flag` needs a second look
- Full detail for a shot is in `video/shots/<n>.md` (e.g. `video/shots/07.md`).
- What is “seen” can be checked against the frames; what is “inferred” is the tools' and image readers' judgement, with the basis in each shot file. When they disagree, trust the frames.
