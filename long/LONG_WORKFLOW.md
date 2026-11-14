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
- One theme for the title: "10 Weird Animal Behaviors Finally Explained", "9 Animal Superpowers Explained by Science",
  "Nature's Strangest Tricks, Explained" … (≤ 70 chars, no #shorts). Never reuse a title from `long/history.json`.

## 2. Write the spec → `long/specs/<YYYY-MM-DD>-<slug>.json`
Format (see `long/specs/2026-11-14-animals.json`): `{id, title, voice: "bm_lewis", speed: 1.0, intro:[…], chapters:[{title, scenes:[…]}], outro:[…]}`,
each scene `{"say": "...", "q": "<pixabay query>"}` (optional `"q2"` alternative query).
- Intro: 3 scenes teasing the 3 most surprising chapters. Outro: 2 scenes (question to the viewer + subscribe).
- Each chapter: 4–6 scenes of 20–40 words, **expanding the Short's spec** (`trends/specs/<date>-<n>.json`) – its facts
  are already verified. Every NEW fact or number needs a WebSearch source; if unsure, leave it out.
- Total 1,100–1,350 spoken words (≈ 8.5–10 min). No politics, tragedies, crime, real people, brands, nothing medical.
- Check pronunciation like in `WORKFLOW.md` (missing words → `custom_words.json`).

## 3. Clips
`python3 long/pick_long.py long/specs/X.json` → writes `clip`/`clip_id` and `long/specs/X_sheet.jpg`.
LOOK at the sheet; for wrong/AI/unrelated clips add a better `q2` and run `--redo i,j`. Landscape only.

## 4. Render (≈ 35 min – run it in the background and poll, tool calls time out after 10 min)
```bash
nohup python3 long/render_long.py long/specs/X.json out/long.mp4 > out/long.log 2>&1 &
# poll: tail -3 out/long.log   (ends with "done … min" + the chapter list; also out/long.mp4.meta.json)
```
The final file is 720p and size-capped to ≈ 90 MB (GitHub limit 100 MB). Check: `ls -la out/long.mp4` < 95 MB,
duration 8–10.5 min, and grab 4 frames (intro, a chapter card, mid chapter, outro) → Read them.

## 5. Publish + schedule
```bash
VIDEOS_BRANCH=videos-long python3 publish.py out/long.mp4
```
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
