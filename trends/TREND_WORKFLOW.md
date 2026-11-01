# Daily "Trends Explained" Shorts run – instructions for Claude

Goal: **3 English Shorts per day** (25–45 s, vertical) for the second channel (Metricool brand "Storys",
blogId `7782808`). Each Short takes a topic that is **trending on YouTube right now** and explains it with an
original script, the offline voice, Pixabay stock footage and 3D emoji – the same engine as the facts channel.
We never re-upload or copy anyone's video: we only use trends as topic ideas. Nobody is watching: decide yourself.

## 0. Setup
```bash
git clone https://github.com/KogJam/shorts-media.git ~/shorts-media && cd ~/shorts-media
bash setup.sh
export PIXABAY_API_KEY=...   # from the task prompt – never commit it
```

## 1. Find today's trends (one vidIQ call per day – the free plan has 150 credits/month, 5 per call)
vidIQ `vidiq_trending_videos`: `videoFormat: "short"`, `sortBy: "vph"`, `videoTitleLanguage: "en"`, `limit: 50`,
`videoPublishedAfter`: 3 days ago. Save the raw list to `trends/raw/<date>.json` (not committed is fine).
If vidIQ fails or credits are out: use WebSearch ("trending on YouTube today", "Google Trends today", "viral this week")
instead – never skip the day.

## 2. Pick 3 topics
Turn trending videos into **explainable topics** – the curious question behind the trend, e.g.
"Why Dobermans have cropped ears" → *why are dog ears cropped / is it legal*; a soccer-ball factory video →
*one city makes 70 % of all footballs*; Halloween/Diwali/holiday trends → *origin of the custom*;
survival/DIY hacks → *does the hack really work and why*; a viral animal → *the science of that animal*.
- Rules: no politics/elections/wars, no tragedies or crime, no rumours about real people, no celebrities as the
  subject, no brand/franchise characters (games, films, K-pop groups…) as the subject, nothing medical.
  Prefer evergreen-curious angles that viewers of the trend will search for.
- Not already in `trends/history.json` (check topic and title). Mix categories over the day.
- **Verify every fact** with WebSearch (at least one solid source per number). If a fact can't be verified, drop it.

## 3. Specs → `trends/specs/<YYYY-MM-DD>-<n>.json`
Same format as the facts channel (see `WORKFLOW.md` step 2 and `trends/specs/2026-11-01-1.json` as example), plus:
- `"voice": "bm_george"`, `"speed": 1.1`, `"endcard": "FOLLOW: TRENDS EXPLAINED"`
- hook = the trend's surprising angle, title ≤ 70 chars ending with `#shorts`, description ends with
  "Follow for what's trending, explained!" + 4–5 hashtags incl. #shorts.
- 6–8 scenes; each scene a different Pixabay clip (`clip_id`), 1–2 insets, numbers via `number`, 2–3 `punch` words.
- Check pronunciation (`render.check`) – add unknown words to `custom_words.json` (IPA like the existing entries).

## 4. Clips, render, QA
Same as `WORKFLOW.md` steps 3–4: `python3 pick.py "<query>" …` and LOOK at every sheet (Pixabay sometimes returns
429 – wait 60 s and continue one query at a time); avoid green screens, AI-looking or unrelated footage.
`python3 render.py trends/specs/X.json out/X.mp4`, then a 7-frame contact sheet → check with Read.

## 5. Publish + schedule
```bash
VIDEOS_BRANCH=videos-trends python3 publish.py out/A.mp4 out/B.mp4 out/C.mp4
```
Metricool `createScheduledPost`: blogId `7782808`, network `youtube`, timezone `Europe/Berlin`, `autoPublish: true`,
`media: [url]`, `text` = description, `youtubeData: {title, type: "short", privacy: "public", tags,
category: "ENTERTAINMENT", madeForKids: false, isAiGeneratedContent: false}`.
Slots (Europe/Berlin): **15:47, 19:17, 22:47** (US late morning → evening; offset from the facts channel).
Call `getScheduledPosts` for brand 7782808 first and skip slots already booked (never double-book);
if a slot is already past, use the next free one ≥ 20 min from now. Confirm PENDING.

## 6. Bookkeeping
Append each Short to `trends/history.json` (`{date, id, title, topic, trend_source, slot}`), commit + push `main`
(never `out/`, clips or keys). Short German summary to the user via SendUserMessage: titles + times + problems.
