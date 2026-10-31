# AI drama series run – instructions for Claude

Goal of one run: produce **one new episode** (**7.5–10 min**, never shorter than 7 min or longer than 10 min, 16:9, English, every shot AI-animated) of the series whose turn it is,
and schedule it on the drama YouTube channel through the **Metricool** connector (brand / blogId `7782808`,
label "Storys"). Several series rotate so the channel always has variety. Nobody is watching: decide yourself.

## 0. Setup
```bash
git clone https://github.com/KogJam/shorts-media.git ~/shorts-media && cd ~/shorts-media/drama
export GEMINI_API_KEY=...   # from the task prompt – never commit it
```
The shell can reach GitHub and `generativelanguage.googleapis.com`. Fonts/ffmpeg/numpy/Pillow are preinstalled.

## 1. Whose turn?
First do the **Publish date** check from step 5 – if enough episodes are already queued, stop here.
`rotation.json` lists the series in order plus `next` (index). Take `series[next]`.
If that series has `"status": "finished"`, skip to the next. When all are finished, create a new series (step 7).

## 2. Read the series
- `series/<id>/series.json` – characters (look, outfit, voice), style, `arc` (season plan), `extras` (minor voices).
  New recurring characters (e.g. a love interest introduced later in the arc) must be added to `characters` first –
  `gen.py … all` creates their reference portrait automatically.
- `series/<id>/story.md` – what happened in every published part (continuity!). Read it fully.
- The latest `series/<id>/episodes/epNN.json` – tone and format reference.

## 3. Write the next episode → `series/<id>/episodes/epNN.json`
Same format as existing episodes:
- `episode`, `title` (YouTube title ≤ 100 chars, emotional hook, ends with `| Full AI Drama – Part N`),
  `thumb_text` (3 short ALL-CAPS-friendly lines), `thumb_prompt`, `thumb_chars`, `thumb_outfits`,
  `description` (3–4 sentences recap+hook, "Part N+1 drops in X days. Subscribe…", the line
  "This is a fictional AI-generated drama series. All characters are fictional.", 5 hashtags), `tags`.
- `shots`: **45–55 shots of ~9–11 s each** (every shot becomes one ~10 s AI video clip), each `{id, chars, outfit, camera, image, motion, lines}`.
  - `motion`: what moves in the clip (e.g. "she slowly turns towards the window, tears running down", "he slams the folder on the desk").
  - `chars`: ids of series characters visible in the shot (max 4; their reference portraits keep faces consistent).
    Refer to characters inside `image` by their **id** (e.g. "emma walks in"), the generator inserts names.
  - `outfit`: per-character override when not wearing the default outfit; keep outfits consistent within a scene.
  - `camera`: push_in | pull_out | pan_left | pan_right (vary them).
  - `image`: one concrete visual moment (place, action, emotion, light). Never text/signs that must be readable,
    except big logos. Minor characters (manager, butler…) are described fully in `image` and get voices via `extras`.
  - `lines`: `{who, text, how}` – `who` = narrator | character id | extras id; `how` = acting direction.
    1–3 lines per shot, together ~18–28 words (≈ 8–10 s of speech) so speech fills the 10 s clip.
    Total ≈ 1,050–1,400 words → 7.5–10 min. Check: `sum(words)/150` minutes + ~0.5 s per shot.
- Structure: 15–30 s **cold open** hook (flash-forward or strongest moment) → `title_card: true` shot
  ("<Title>. Part N.") → 3–5 scenes with escalating conflict → big reveal → **cliffhanger** → `end_card: true`
  shot (narrator asks the question + "Subscribe…").
- Follow the season plan in `arc`, but make each part satisfying on its own. Keep it PG-13: no graphic violence,
  no sexual content, no real people/brands, no minors in peril.

## 4. Generate + build
```bash
python3 gen.py series/<id>/episodes/epNN.json all     # refs (first time only), images, voices, thumbnail
python3 gen.py series/<id>/episodes/epNN.json all     # run again: fills anything that failed
# QA the stills first (see below) – animation is the expensive step, fix bad stills before it
python3 animate.py series/<id>/episodes/epNN.json --all   # Gemini Omni image-to-video, ~10 s per shot, ~1 $ each
python3 animate.py series/<id>/episodes/epNN.json --all   # again: retries failed shots (cached clips are skipped)
python3 film.py series/<id>/episodes/epNN.json        # -> series/<id>/build/epNN/epNN.mp4 + thumb.jpg (<95 MB)
```
gen ~10–15 min, animate ~20–30 min, film ~10 min. Cost ≈ 50–60 $ per episode. Never regenerate a whole episode;
re-do single shots by deleting just that `build/epNN/img/<shot>.png` / `clips/<shot>.mp4`.
Omni blocks prompts that look like real people: animate.py already replaces names with descriptions – never put
character names into `motion`. If a clip is blocked twice, leave it: film.py uses a camera move on the still instead.
If `clips/OUT_OF_CREDIT` appears, the Google prepaid credit is empty: finish the episode with the clips you have
and tell the user to top up at https://ai.studio/projects (Billing).

**QA (mandatory):** look at the reference portraits once, then make a contact sheet of ~20 shot images
(PIL, small thumbnails) and check them with Read: right characters, consistent faces/outfits, no extra limbs,
no garbled text, nothing inappropriate. Fix bad shots (delete + regenerate, max 2 tries, else adjust the prompt).
Also look at `thumb.jpg`.

## 5. Publish + schedule
```bash
python3 ../publish.py series/<id>/build/epNN/epNN.mp4 series/<id>/build/epNN/thumb.jpg   # public URLs
```
(publish.py replaces the `videos` branch – fine, Metricool copies the file immediately. Do NOT run it while a
Shorts run might be scheduling, i.e. avoid 09:30–10:30 Europe/Berlin.)
Metricool `createScheduledPost`: blogId `7782808`, network `youtube`, timezone `Europe/Berlin`, `autoPublish: true`,
`media: [video url]`, `text` = description,
`youtubeData: {title, type: "video", privacy: "public", tags, category: "FILM_ANIMATION", madeForKids: false,
isAiGeneratedContent: true}`. Publish time: see **Publish date** below.
**Publish date:** call `getScheduledPosts` for brand `7782808` (range: last 7 days to 10 days ahead, extendedRange true)
and find the latest drama post (scheduled or published). New date = that date + 2 days, at 20:07 Europe/Berlin
(if none, or that is in the past: today 20:07, or tomorrow 20:07 if today's is less than 1 h away).
If the new date is more than 4 days ahead, there are enough episodes queued: stop the run without generating anything
(tell the user briefly). Do this check FIRST, before step 3, so no money is spent unnecessarily.
Add `videoThumbnailUrl` with the thumb URL; if the request is rejected with VIDEO_THUMBNAIL_NOT_APPLICABLE,
retry without it. Confirm status PENDING.

## 6. Bookkeeping
- Append a 5–8 sentence summary of the new part to `series/<id>/story.md` (what happened, open threads, cliffhanger).
- `rotation.json`: increment the series' `episodes`, set `next` to the following series; if the series reached
  its planned last part, set `"status": "finished"`.
- Commit spec + story + rotation (+ new refs) to `main`. Never commit `build/`, keys or videos.
- Summary to the user in German via SendUserMessage: series, part, title, publish time, any problem.

## 7. New series (only when all are finished or rotation has < 3 active series)
Create `series/<new-id>/series.json` with a fresh popular drama genre (e.g. secret billionaire, revenge, second
chance romance, family betrayal, mistaken identity), 5–6 characters with very distinct looks, voices from the
Gemini TTS list (Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus,
Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux,
Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat), an 8-part `arc`, empty story.md,
and add it to rotation.json.
