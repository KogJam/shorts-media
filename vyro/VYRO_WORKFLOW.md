# Daily Vyro clipping run – instructions for Claude

The user (CrackBuddy) earns money with **Vyro** clipping campaigns (https://app.vyro.com, pay per views).
Every day: scout new campaigns, turn every campaign the user has **joined** into finished vertical clips, schedule
them on the CrackBuddy accounts via Metricool, and report the post links the user must submit in Vyro.
Nobody is watching: decide yourself, report at the end (German, via SendUserMessage).

## Hard rules (never break)
- **Never** join a campaign, accept terms, submit a form, submit posts in Vyro, type credentials or log in. The user does
  that. You only read Vyro pages.
- Only use footage the campaign itself provides (its asset links). Never download/re-upload other people's videos.
- Follow the brief exactly: mandatory lines/captions, @mentions, FTC hashtag (e.g. #VyroPartner), allowed platforms,
  "do not edit the clip" rules, length limits, banned content. If the brief forbids something we normally do
  (music, cutting, captions, crop), don't do it.
- Keep keys out of the repo (GEMINI_API_KEY / PIXABAY_API_KEY only via env from the task prompt).

## 0. Setup
```bash
git clone https://github.com/KogJam/shorts-media.git ~/shorts-media && cd ~/shorts-media && bash setup.sh
mkdir -p ~/.config/shorts && printf 'GEMINI_API_KEY=%s\n' "$GEMINI_API_KEY" > ~/.config/shorts/env
```
State: `vyro/campaigns.json` (every campaign seen, its status `seen|joined|produced|done|skipped`, slug, clip count,
schedule window, notes). Read it first, update + commit it at the end.

## 1. Read Vyro (built-in browser on the user's PC)
Tools: `mcp__remote-devices__Claude_Browser__*` (load via ToolSearch; read the built-in-browser skill first).
Open https://app.vyro.com/campaigns in a new tab. If it shows the login page → do NOT log in; tell the user
"Bitte einmal im Claude-Browser bei Vyro einloggen" and continue with steps 6–8 only.
If the browser/computer is unreachable → say so in the report, do steps 6–8 only.
- **Discover** list: for every campaign not in campaigns.json, open it and note: brand, title, pay (per 1M views),
  budget left / % used, platforms, end date, locked?, what content is required, source assets. Rate it
  (Ja / Vielleicht / Nein) – good = high rate, lots of budget left, raw footage provided, fits CrackBuddy (English,
  general entertainment), we can produce it with our pipeline. Store as `seen`.
- Campaigns already produced are matched by `vyro_title` in campaigns.json (brand – title).
- Vyro nav: Home (action items, joined campaigns), Discover (/campaigns), Add Posts (/campaigns/add-clips), Earnings.
  On Home also check "Your action items" (e.g. social account not connected, payouts not set) and mention open items.
- **My campaigns / Joined**: every joined campaign not yet `produced` → step 2. The page text + JS
  (`document.querySelectorAll('a')` for asset links) gives the brief and links.

## 2. Get the source footage
- **Frame.io share** (next.frame.io/share/...): open it in the browser, then run JS
  `window.__APOLLO_CLIENT__.cache.extract()` and collect per asset: name, duration, `assets.frame.io/uploads/<id>/original.*`
  URL (full res, supports HTTP range → cut.py streams only the needed seconds) and `encode/<id>/video_h264_180.mp4`
  (tiny proxy, video only). Signed URLs expire – re-extract if you get 403.
  Audio for analysis: `ffmpeg -http_proxy $HTTPS_PROXY -i <original> -vn -c:a copy src/<k>.m4a` (streams the whole file,
  ~5–10 min per 30-min 4K video; run them in parallel, in the background).
  Proxy with audio: `src/<k>_ana.mp4` = 180p video + that audio (analyze.py builds it from `src/<k>_180.mp4` + `src/<k>.m4a`).
- **Short ready clips** (Drive/Dropbox/direct mp4): download them (small) and treat each as a source.
- If a host is blocked by the network allowlist, report the domain to the user ("bitte in den Einstellungen freigeben").

## 3. Find the best moments
Work dir `~/vyro/<slug>/`. Write the brief + campaign facts into `brief.txt`, `sources.json` = {key: original URL or path}.
`BRIEF=brief.txt python3 ~/shorts-media/vyro/clipper/analyze.py <key> 8` per source (Gemini, ~1 call per source).
Pick the best non-overlapping segments over all sources (score ≥ 8, varied topics). Usually 10–20 clips per campaign,
fewer if the campaign is short or the budget is almost used up.
If the brief says clips must stay unedited / provides finished clips: skip analysis and use `vyro/edit.py` (frame +
hook only, original untouched – see `vyro/ketone_plan.json` for that style).

## 4. Produce
`plan.json`: `[{"id":"<slug>01","k":"v1","s":"MM:SS","e":"MM:SS","hook":"short curiosity hook max 8 words + 1 emoji","mood":"tense"}]`
(default **~60–70 s** (≥ 60 s); only when a moment is a complete, very strong beat on its own make it a **short 20–35 s**
clip with `"peak":"MM:SS"` = most dramatic second → 1.6 s cold-open teaser at the start. Start on action, end on a payoff;
`"loud_music": true` for clips with little speech. If the speech is someone SINGING a song, set that clip's
`work/*_cues.json` to `[]` (no lyrics in captions).
Music: 3–4 original instrumental beds with Lyria, in `music/`:
`cd music && python3 ~/shorts-media/vyro/clipper/gen.py tense "Instrumental only, no vocals. 75 seconds. <mood description>, stays understated under speech."`
Then `SOURCES=sources.json TAG="@<brand handle>" python3 ~/shorts-media/vyro/clipper/run.py` → `final/<id>.mp4`
(4:5 window on blurred bg, fixed hook title on top, phrase captions synced to speech with word highlight, profanity
censored in captions, music ducked under speech, ≤ ~100 MB). Run it in the background; ~3–5 min per clip.
QA: contact sheet of 4 frames per clip, LOOK at it (hook matches content, captions present & readable, nothing broken).
Re-render broken ones (delete `out/<id>.mp4` and `final/<id>.mp4`; cached `work/*_cues.json` can be deleted to re-transcribe).

## 5. Host + schedule (Metricool brand **7781434** = CrackBuddy: YouTube + TikTok)
`VIDEOS_BRANCH=videos-<slug> python3 ~/shorts-media/publish.py final/*.mp4` → raw GitHub URLs (Metricool copies them).
First `getScheduledPosts` for 7781434 for the whole window – never double-book, keep ≥ 90 min between any two posts.
Limits across ALL campaigns: **YouTube ≤ 6 posts/day, TikTok ≤ 3/day** (new account). Spread a campaign's clips evenly
until its end date (best clips first; exact end = aria-label of the button under "Ends" on the campaign page, e.g. "November 06, 2026, 15:11:00"; last post ≥ 24 h before the end), slots in **US prime time: 20:00–03:00 Europe/Berlin** (e.g. 22:07 and 02:07; English audience), odd minutes.
Post fields: `providers` youtube (+ tiktok if allowed and under the limit), `autoPublish: true`,
`text` = hook + 1-sentence caption + required @mention/caption + FTC hashtag + 5–7 niche hashtags (+ #fyp on TikTok),
`youtubeData {title ≤ 90 chars incl. FTC hashtag, type "short", privacy "public", madeForKids false, category fitting,
isAiGeneratedContent false}`, `tiktokData {privacyOption "PUBLIC_TO_EVERYONE", commercialContentThirdParty true,
title = hook, autoAddMusic false}`.

## 6. Links to submit
`getScheduledPosts` for 7781434, yesterday 00:00 → today now, extendedRange true. For every published post that carries a
Vyro FTC hashtag (#VyroPartner, #…Partner) collect the YouTube/TikTok public URLs + status. Skip `#KetoneIQPartner`
until 2026-11-06 (it has its own report). Failed network → reschedule once 30 min later with updateScheduledPost.

## 7. Bookkeeping
Update `vyro/campaigns.json`, commit + push main (never videos, keys or work dirs).

## 8. Report (German, SendUserMessage, short)
1. **Neue Kampagnen** – per campaign: name, Rate, Budget-Rest, Ende, Einschätzung Ja/Vielleicht/Nein + 1 Satz Grund
   + Link. „Tritt bei, was du willst – ich mache den Rest beim nächsten Lauf.“
2. **Produziert & eingeplant** – campaign, number of clips, posting window.
3. **Zum Einreichen in Vyro** – the links from step 6 (YouTube + TikTok per clip). Reminder: in YouTube Studio
   „Bezahlte Werbung“ ankreuzen.
4. Problems (login needed, blocked domain, failed render/post).
