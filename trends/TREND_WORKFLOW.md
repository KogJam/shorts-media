# Daily "Trends Explained" Shorts run – instructions for Claude

Goal: **3 English Shorts per day** (**35–45 s**, vertical – shorter = higher % watched, which is the main Shorts ranking signal; our 65 s Shorts were only watched ~30 % on average) for the second channel (Metricool brand "Storys",
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


**What performs (channel data, Oct 20 – Nov 15 2026):** animal "why does X do that?" Shorts average **~650 views**
(monkeys grooming 1.36k, birds & chili 1.19k, snails' teeth 985, squirrels 840, dogs' head tilt 800); every other topic
(tech, culture, holidays, space, ocean, everyday science) averages **~160**. Average view duration is only 10–25 s.
→ **All 3 daily Shorts are ANIMAL curiosity questions** ("Why do cats…", "How do crows…", "The real reason …"), tied to
what is trending where possible (a viral animal, the season, a news-free animal fact behind a trend). A plant/nature
topic only if it is a clear "why" about a living thing. No space/tech/culture/holiday topics on this channel any more. Title pattern:
"Why <Animal> <surprising behaviour>" / "The <Animal> Isn't Really <assumption>".

## 3. Specs → `trends/specs/<YYYY-MM-DD>-<n>.json`
Same format as the facts channel (see `WORKFLOW.md` step 2 and `trends/specs/2026-11-01-1.json` as example), plus:
- `"voice": "bm_lewis"`, `"speed": 1.08`, `"music": "upbeat"`, `"endcard": "FOLLOW: TRENDS EXPLAINED"`
- hook = the trend's surprising angle, title ≤ 70 chars ending with `#shorts`, description ends with
  "Follow for what's trending, explained!" + 4–5 hashtags incl. #shorts.
- **7–8 scenes, 85–110 spoken words in total** (the renderer prints the duration – it must be 35–45 s; if it is
  shorter add a scene, if longer cut one, then re-render). Each scene a different Pixabay clip (`clip_id`), 2–3 insets,
  numbers via `number`, 3–4 `punch` words.
- **Pep (renderer, automatic):** every scene longer than ~3 s gets a mid-scene cut, the footage gets a camera
  (push-in, snap zoom at cuts, shake on punch words), whoosh/pop/impact/ding sound effects and an upbeat original bed.
  Give every scene a **second clip `clip2_id`** (another fitting clip from the same pick sheet – different angle/animal
  action); without it the renderer does a jump cut into the same clip, which is OK but weaker.
- **Hook (first 1.5 s decides everything):** line 1 is ONE short question or shocking claim, ≤ 10 words, that names the
  animal ("Why do owls never get dizzy?" / "This frog freezes solid, on purpose."). The on-screen `hook` (≤ 6 words) is a
  curiosity gap, not the answer. Scene 1 clip shows the animal itself, close and in motion, from frame 1, plus one emoji
  with `"anim": "pop"` at delay ≤ 0.4. Scene 2 must already give the first surprising fact (no context, no setup).
- **Retention rules:** line 1 (first 2 s) states the surprising claim or question directly – no intro, no "Did you know";
  the hook text on screen and the first spoken line must match. Every scene adds a new fact (no filler). The payoff/twist
  comes in the last 8 s, and the last line should lead back to the first one so the Short loops naturally
  (e.g. ends with "…and that's why the cobra 'dances'." → starts with "The cobra isn't dancing.").
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
**Pinned-comment bait:** add `firstCommentText` with ONE short question that is easy to answer, e.g.
"Which animal should I explain next? 👇" or "Did you know this? Yes or no 👇" (vary it daily). If Metricool rejects
the field for a network, retry that post once without it and mention it in the summary.
**TikTok: NEVER schedule TikTok via Metricool** (auto-posts got 0 views on the new account – the user posts TikTok by hand).
YouTube only. Put the raw download links of the 3 MP4s in the summary so the user can post the best one on TikTok himself
(the `videos-trends` branch keeps them until the next day's run).

**Instagram Reels (connected: @storystotellyt on brand 7782808):** for EVERY Short also create a SEPARATE Metricool post
50 minutes after its YouTube slot (16:37, 20:07, 23:37) with `providers: [{"network":"instagram"}]`,
`instagramData: {"type":"REEL","showReelOnFeed":true,"isAiGenerated":false}`, the same media URL (use the
static.metricool.com URL returned by the YouTube post), and an Instagram caption: the description text + 1 fitting emoji,
"Follow for what's trending, explained!" and 5–6 hashtags ending with #didyouknow #reels (no #shorts, no TikTok tags).
Check getScheduledPosts so no two Instagram posts are < 30 min apart.

Slots (Europe/Berlin): **15:47, 19:17, 22:47** (US late morning → evening; offset from the facts channel).
Call `getScheduledPosts` for brand 7782808 first and skip slots already booked (never double-book);
if a slot is already past, use the next free one ≥ 20 min from now. Confirm PENDING.

## 6. Bookkeeping
Append each Short to `trends/history.json` (`{date, id, title, topic, trend_source, slot}`), commit + push `main`
(never `out/`, clips or keys). Short German summary to the user via SendUserMessage: titles + times + (if TikTok isn't connected) the 3 download links + problems.

## 7. Affiliate links (only if `trends/affiliate.json` has `"enabled": true` and an `amazon_tag`)
Skip this whole step while it is disabled. When enabled:
- Only where it fits naturally (≈1 of 3 Shorts, never forced): pick ONE everyday product type that matches the
  Short's payoff (cat video → wand cat toy, birds → bird feeder, beavers/nature → binoculars). No medical,
  supplements, food for animals with health claims, or anything the Short doesn't talk about. Never claim we tested it.
- Spec: add `"affiliate_cta": "<Product> tip: link in bio"` (≤ 28 chars after "AD · ") – the renderer shows a small
  "AD · …" pill during the last 7 s. Keep the spoken script unchanged (no sales pitch in the voice).
- `python3 trends/links.py add <spec id> "<title without #shorts>" "<Product label>" "<amazon search words>"`
  → updates `docs/index.html` (GitHub Pages link-in-bio page, `page_url` in affiliate.json); commit it with the specs.
- YouTube description: add a line "🔗 <Product> we mention: link in channel bio (affiliate, #ad)".
  Instagram caption: add "🔗 Link in bio (affiliate, #ad)" before the hashtags.
