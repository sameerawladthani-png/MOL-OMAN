---
videomd: 1
part: remake
tokens: 883
---

## Remake plan

### Step by step

This is a short AI clip (pets / spectacle / single scene). Do the steps in this order; the detail for each is in the matching subsection below.

1. **Write the content**: write yours in the same 1 steps as the original (narrative line under “Content and structure”)
2. **Generate**: 1 call (10 s), several shots each. Each shot gets one source frame for composition (subtitles erased, in `remake/refs/`), the swapped-in people, animals and products get reference images, and the prompt lists the shots in order
3. **Adapt the prompts to your model**: each unit's draft is already laid out in MiniMax H3 / H3 Max's shot, tag and audio format; refine it against the model's prompt guide before generating (or run `rea-video plan <folder> --rewrite-prompts`)
4. **Edit**: follow the order and lengths in the shot list; the original is a single 10 s take
5. **Subtitles and styled text**: timing and style under “Packaging layer”
6. **Music**: find a track at the same tempo and mood (source: to confirm, about 128 BPM, C major)
7. **Put it together and compare**: hand the shots you made to the agent; it places them on the original timeline, keeps the original where yours are missing, and renders a side-by-side comparison with the original

**1 AI video shot → 1 generation unit, 1 MiniMax H3 / H3 Max call**

### Generation units

| Part | Shots | Time | Length | Prepare |
|---|---|---|---|---|
| G1 | #1 | 0.0–10.0s | generate 11s, trim to 10.0s | reference images |

**Why it is split this way**

- Grouping: consecutive shots share a call where they fit, ≤10s per call, ≤4 shots; a long stretch is cut at a scene change first
- Inputs: the model also takes reference video, but its default plan is used here: one source frame per shot (subtitles erased) fixes composition, swapped-in things get their own images
- Audio: the model can generate action sound effects and ambience along with the picture
- Packaging: the styled text, text label on the generated shots is post-production packaging: keep it out of the prompts (erased from source references) and lay it back on from the packaging timeline after generation

**G1 · shots #1 · 10.0s**

- reference images: source frames of shots #1 (subtitles erased)

Draft prompt (in MiniMax H3 / H3 Max's layout; check it and put the final into remake/prompts.json before generating):

```text
integrated_multimodal_description: Generate the shots below in order in one go, hard cuts between them; each shot takes composition, size and camera from its source frame image. Vertical 9:16; soft frontal light, cool tones, background slightly soft.
[Shot 1] One 10 s AI take: Arabic title card 'إعلان عطر / AI Perfume Ad' over glowing bottle sketch, macro of crystal flower cap and gold atomizer spraying pink mist, mist swirls into a crystal flower, then crystal butterflies, light ribbons draw a wireframe bottle that solidifies into the Lady Bloom packshot with tagline 'Where Elegance Blooms'. (composition: <Picture 1>)
overall_soundscape: Only the natural sounds of the actions on screen.
non_diegetic_music: N/A
```

**Prompt guides for MiniMax H3 / H3 Max**

- https://huggingface.co/MiniMaxAI/MiniMax-H3/raw/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
- https://huggingface.co/MiniMaxAI/MiniMax-H3/raw/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md
- https://platform.minimax.io/docs/api-reference/video-generation-v2-create
- https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide.md
