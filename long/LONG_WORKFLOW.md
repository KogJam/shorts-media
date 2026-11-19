# Long-form "Trends Explained" videos – twice a week (Wed + Sun)

Goal: one **8–10 min landscape (16:9) compilation** per run for the trends channel (Metricool brand "Storys",
blogId `7782808`, YouTube only). Long videos build **watch hours** (Shorts never count) and give every Short a
"related video" to link to. Zero extra cost: same free stack as the Shorts (Pixabay, local Kokoro voice, Metricool).
Nobody is watching: decide yourself, report at the end.

## 0. Setup
Same as `WORKFLOW.md` step 0 (`bash setup.sh`, `export PIXABAY_API_KEY=...` from the task prompt – never commit it).

## 1. Pick the chapters (8–10)
- Source: Shorts in `trends/history.json` that are **not yet listed in `long/history.json`** (field `chapters` holds
  the Short ids already used). Prefer animal/nature topics (they perform best), newest first.
- If `long/specs/` already contains a spec that is not in `long/history.json` (e.g. the prototype
  `2026-11-14-animals.json`), use that one first: re-check its facts (quick WebSearch for every number), then go on at step 3.
- **Animals only** (channel data: animal Shorts ~650 views, everything else ~160). Use the best-performing animal
  Shorts first – check their views with Metricool `getAnalyticsDataByMetrics` (brand 7782808, metrics YTVP17 title,
  YTVP06 views) and put the strongest topic last as **#1**.
- **Countdown format (default, `"countdown": true`):** chapters are ordered weakest → strongest; the renderer numbers
  them #10 … #1 and says "And number one" for the last. The intro teases #1 without solving it ("…and number one
  breaks every rule of biology – stay for it").
- Title = a curiosity promise, ≤ 60 chars, no #shorts, no "Explained by Science" filler. Good: "10 Animals That Break
  the Rules of Biology", "This Frog Freezes Solid… and Wakes Up (+9 More)", "Animals Doing Impossible Things, Ranked".
  Never reuse a title from `long/history.json`.

## 2. Write the spec → `long/specs/<YYYY-MM-DD>-<slug>.json`
Format (see `long/specs/2026-11-14-animals.json`): `{id, title, voice: "bm_lewis", speed: 1.05, music: "upbeat", countdown: true,
thumb_text, thumb_emoji, intro:[…], chapters:[{title, scenes:[…]}], outro:[…]}`,
each scene `{"say": "...", "q": "<pixabay query>"}` (optional `"q2"` alternative query).
- **Intro (first 15 s decide whether people stay):** scene 1 = the single most shocking fact of the video in ≤ 20 words,
  no greeting ("This frog's heart stops for weeks. Then it starts again."); scene 2–3 tease two more chapters and promise #1.
  Outro: 2 scenes (question to the viewer + subscribe).
- **Open loops:** end every 2nd–3rd chapter with a one-line tease of the next one ("But the next animal does something
  even stranger with its blood…").
- **Thumbnail:** `thumb_text` = 2–4 huge words that create a question (e.g. "FROZEN SOLID… ALIVE?", "NO PEE FOR 7
  MONTHS?"), `thumb_emoji` = the #1 animal, optional `thumb_clip_id` + `thumb_ss` (a close, bright, well-lit frame of
  that animal – default is the first clip of chapter #1).
- Each chapter: 4–6 scenes of 20–40 words, **expanding the Short's spec** (`trends/specs/<date>-<n>.json`) – its facts
  are already verified. Every NEW fact or number needs a WebSearch source; if unsure, leave it out.
- Total 1,100–1,350 spoken words (≈ 8.5–10 min). No politics, tragedies, crime, real people, brands, nothing medical.
- Check pronunciation like in `WORKFLOW.md` (missing words → `custom_words.json`).

## 3. Clips
`python3 long/pick_long.py long/specs/X.json` → writes `clip`/`clip_id` **and a second shot `clip2`/`clip2_id`** per
scene plus `long/specs/X_sheet.jpg` (small yellow-framed thumbnail = clip2). The renderer cuts every ~5 s between the
two shots (with pans and push-ins), so BOTH must fit what is said. LOOK at the sheet; for wrong/AI/unrelated clips add
a better `q2` and run `--redo i,j` (or delete `clip2` from that scene to fall back to one clip). Landscape only.

## 4. Render (≈ 35 min – run it in the background and poll, tool calls time out after 10 min)
```bash
nohup python3 long/render_long.py long/specs/X.json out/long.mp4 > out/long.log 2>&1 &
# poll: tail -3 out/long.log   (ends with "done … min" + the chapter list; also out/long.mp4.meta.json)
```
The final file is 720p and size-capped to ≈ 90 MB (GitHub limit 100 MB). Check: `ls -la out/long.mp4` < 95 MB,
duration 8–10.5 min, and grab 4 frames (intro, a chapter card, mid chapter, outro) → Read them.
Thumbnail: `python3 long/thumb.py long/specs/X.json out/thumb.jpg` → Read it (text readable at small size, animal
clearly visible, nothing cut off); adjust `thumb_text`/`thumb_clip_id`/`thumb_ss` and re-run if not.

## 5. Publish + schedule
```bash
VIDEOS_BRANCH=videos-long python3 publish.py out/long.mp4 out/thumb.jpg
```
Pass the thumbnail as `videoThumbnailUrl` (the raw URL of thumb.jpg). Custom thumbnails need a **verified** YouTube
channel; if Metricool rejects the post because of the thumbnail, schedule it again without `videoThumbnailUrl` and say
so in the summary. Add `firstCommentText` with one question to the viewers ("Which one surprised you most? 👇");
if rejected, retry without it.
Metricool `createScheduledPost`: blogId `7782808`, timezone `Europe/Berlin`, `autoPublish: true`,
`providers: [{"network":"youtube"}]`, `media: [url]`, slot **18:07 the same day** (if past or booked: next free
slot ≥ 30 min away and ≥ 30 min from any Short), `youtubeData: {title, type: "video", privacy: "public", tags,
category: "ENTERTAINMENT", madeForKids: false, isAiGeneratedContent: false}`.
Description (`text`): 2 sentences + the chapter list from `out/long.mp4.meta.json` (one per line, "0:00 Intro" first)
+ "Follow for what's trending, explained!" + 3–4 hashtags (no #shorts). If `trends/affiliate.json` is enabled add
"🔗 Products & tools we mention: <page_url> (affiliate links, #ad)". **Never TikTok, never Instagram** (16:9, too long).
Confirm PENDING.

## 6. Bookkeeping
Append `{date, id, title, spec, chapters: [<short ids>], slot}` to `long/history.json`; `git pull --rebase`, commit spec +
sheet + history (never `out/`), push `main`. German summary to the user via SendUserMessage: title, publish time, length,
problems. Tip for the user (once per summary): in YouTube Studio, set this long video as "Related video" on the Shorts it contains.
