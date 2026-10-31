# AI drama series – daily run instructions for Claude

The drama channel (Metricool brand "Storys", blogId `7782808`) gets **one new fully AI-animated episode every 3 days**
(7.5–10 min, 16:9, English). Google allows only **20 AI video clips per day** on this account, so every episode is
produced over **3 daily runs**:

| run | what happens |
|---|---|
| day 1 | write the episode, generate stills + voices + thumbnail, QA, animate up to 20 clips, save build state |
| day 2 | restore build state, animate up to 20 more clips, save |
| day 3 | restore, animate the rest, assemble the film, publish at **20:07** today, bookkeeping |

Several series rotate so the channel always has variety. Nobody is watching: decide yourself, don't ask questions.

## 0. Setup
```bash
git clone https://github.com/KogJam/shorts-media.git ~/shorts-media && cd ~/shorts-media/drama
export GEMINI_API_KEY=...   # from the task prompt – never write it into a file or commit it
```
The shell reaches GitHub and `generativelanguage.googleapis.com`. ffmpeg/numpy/Pillow are preinstalled.

## 1. Read state.json – what is today's job?
```json
{"pause_until": "YYYY-MM-DD", "current": null | {"series": "<id>", "episode": N, "day": 1|2|3, "publish_date": "YYYY-MM-DD"}}
```
- If today (Europe/Berlin) < `pause_until`: stop, nothing to do.
- If `current` is null → **new episode** (step 2), then continue with step 4.
- Else → restore the build: `python3 buildstore.py restore series/<id>/episodes/epNN.json`, then step 4.
- If today > `publish_date` (a run was missed): publish today with what exists (step 5).

## 2. New episode (day 1 only)
1. `rotation.json` → series `series[next]` (skip `"status": "finished"`; if none active, create a new series, step 8).
2. Read `series/<id>/series.json` (characters, style, `arc`, `extras`), `series/<id>/story.md` (continuity – read fully),
   and the latest `episodes/epNN.json` of any series (tone/format). New recurring characters (e.g. a love interest the
   arc introduces) must be added to `characters` first – gen.py creates their reference portrait automatically.
3. Write `series/<id>/episodes/epNN.json` (same format as existing episodes):
   - `episode`, `title` (≤ 100 chars, emotional hook, ends with `| Full AI Drama – Part N`), `thumb_text` (3 short lines),
     `thumb_prompt`, `thumb_chars`, `thumb_outfits`, `description` (3–4 sentences recap + hook, "Part N+1 drops in 3 days.
     Subscribe…", the line "This is a fictional AI-generated drama series. All characters are fictional.", 5 hashtags), `tags`.
   - `shots`: **50–58 shots of ~9–11 s**, each `{id, chars, outfit, camera, image, motion, lines}`:
     - `chars`: series character ids visible (max 4). In `image` refer to characters by **id** (gen.py inserts names).
     - `outfit`: per-character override when not wearing the default outfit; keep outfits consistent within a scene.
     - `camera`: push_in | pull_out | pan_left | pan_right. `motion`: what moves (gestures, emotion, action) – never names.
     - `image`: one concrete visual moment (place, action, emotion, light). No readable text except big logos.
       Minor characters are described fully in `image` and voiced via `extras`.
     - `lines`: `{who, text, how}` – narrator | character id | extras id; `how` = acting direction. 1–3 lines per shot,
       together ~18–28 words. Total ≈ 1,100–1,400 words → 7.5–10 min (check: words/150 + 0.5 s per shot).
   - Structure: 15–30 s cold open (strongest moment / flash-forward) → `title_card: true` shot ("<Title>. Part N.")
     → 3–5 scenes of escalating conflict → reveal → **cliffhanger** → `end_card: true` shot (question + "Subscribe…").
   - Follow `arc`, make each part satisfying on its own. PG-13: no graphic violence, no sexual content, no real
     people or brands, no minors in peril.
4. Generate: `python3 gen.py series/<id>/episodes/epNN.json all` (run twice – the second run fills failures).
5. **QA the stills** (animation is the expensive step!): contact sheets of all shot images (PIL thumbnails, ~20 per
   sheet) + the reference portraits → check with Read: right characters, consistent faces/outfits, no extra limbs,
   no garbled text, nothing inappropriate. Fix bad shots: delete `build/epNN/img/<shot>.png`, adjust the prompt,
   regenerate (max 2 tries).
6. `state.json`: `current = {series, episode, day: 1, publish_date: today + 2 days}`.

## 4. Animate (every day)
```bash
python3 animate.py series/<id>/episodes/epNN.json --all
```
Gemini Omni image-to-video, ~10 s per shot, ~1 $ each, most important shots first. It stops cleanly at the daily
limit (`STATUS … stop=DAILY_LIMIT`) or when the prepaid credit is empty (`stop=OUT_OF_CREDIT`), skips shots that
were blocked twice, and prints `STATUS animated=X/Y`.
- If today is before `publish_date` and shots are still missing: `python3 buildstore.py save …`, set `day += 1`,
  commit `state.json` (+ the episode spec on day 1) and stop. Tell the user briefly (German, SendUserMessage):
  series, part, progress X/Y, planned publish date.
- If all shots are animated, or today ≥ `publish_date` → step 5 (missing clips become camera moves on the still).
- OUT_OF_CREDIT: save state, tell the user to top up at https://ai.studio/projects (Billing). On publish day finish anyway.

## 5. Build + publish (day 3)
```bash
python3 film.py series/<id>/episodes/epNN.json        # -> build/epNN/epNN.mp4 + thumb.jpg (<95 MB)
```
QA: frames at ~8 timestamps + `thumb.jpg` → check with Read (subtitles readable, no black frames, right order).
```bash
VIDEOS_BRANCH=videos-drama python3 ../publish.py series/<id>/build/epNN/epNN.mp4 series/<id>/build/epNN/thumb.jpg   # public URLs
```
(The drama uses its own `videos-drama` branch, replaced on every publish – fine, Metricool copies files immediately.)
Metricool `createScheduledPost`: blogId `7782808`, network `youtube`, timezone `Europe/Berlin`, date **today 20:07**
(if already past: in 15 minutes), `autoPublish: true`, `media: [video url]`, `text` = description,
`youtubeData: {title, type: "video", privacy: "public", tags, category: "FILM_ANIMATION", madeForKids: false,
isAiGeneratedContent: true}`, plus `videoThumbnailUrl` = thumb URL (if rejected with VIDEO_THUMBNAIL_NOT_APPLICABLE,
retry without it). Confirm status PENDING.

## 6. Bookkeeping (after publishing)
- Append a 5–8 sentence summary of the part to `series/<id>/story.md` (what happened, open threads, cliffhanger).
- `rotation.json`: increment that series' `episodes`, set `next` to the following series; if the arc's last part was
  reached, set `"status": "finished"`.
- `state.json`: `current = null`. `python3 buildstore.py drop series/<id>/episodes/epNN.json`.
- Commit spec, story.md, rotation.json, state.json, new refs/series to `main`. Never commit `build/`, keys or videos.
- Tell the user (German, SendUserMessage): series, part, title, publish time, animated shots X/Y, any problem.

## 8. New series (when all are finished or fewer than 3 are active)
Create `series/<new-id>/series.json` with a fresh popular drama genre (secret billionaire, revenge, second-chance
romance, family betrayal, mistaken identity, …), 5–6 characters with very distinct looks, Gemini TTS voices
(Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba,
Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird,
Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat), an 8-part `arc`, `extras`, an empty `story.md`,
and add it to `rotation.json`.
