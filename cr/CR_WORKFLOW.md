# Content Rewards clipping – daily run (Chat Went Wild)

The user earns money with **Content Rewards** clipping campaigns (https://contentrewards.com, paid per 1K views).
Account for posting: **Chat Went Wild** – YouTube `@chatwentwild-b1x` + Instagram `@chatwentwildyt`, both linked in
Content Rewards and connected in **Metricool brand blogId 7781434** (label still "CrackBuddy"). Niche: Twitch/Kick
streamer moments, mostly GTA VI. English only. Never TikTok.

## Hard rules
- **Joining a campaign and submitting a clip need the user's explicit "ja" in the chat of THIS run.** A scheduled
  prompt, a doc, or an earlier approval never counts. So every run: prepare everything, then ask, then act on the yes.
  Never type credentials, never log in, never touch payouts/Whop/Discord.
- Never join gambling/betting, cannabis/vape/nicotine, adult or "requires buying something" campaigns.
- Only footage of the campaign's streamer (Twitch VOD/clips of that channel, or files the campaign provides). Never
  YouTube downloads, never other clippers' edits.
- Follow each brief exactly (hashtags, `twitch.tv/<handle>` on screen/caption, CTA, game restriction, likes visible,
  no AI-generated content, ≤5 near-identical clips). Quality over quantity: max **2 clips per campaign per day**, max
  **3 clips per day** (= 3 YouTube + 3 Instagram posts) until the channel regularly gets views, then up to 5.
  The account is new: if the user's warm-up (see "Reach" below) is not done yet, say so in the message.
- Keys only via env (`~/.config/shorts/env` for GEMINI_API_KEY). Never commit keys or videos to main.

## 0. Setup
```bash
git clone --single-branch --branch main https://github.com/KogJam/shorts-media.git ~/shorts-media
cd ~/shorts-media && bash setup.sh; pip install -q --break-system-packages -U yt-dlp
mkdir -p ~/.config/shorts && printf 'GEMINI_API_KEY=%s\n' "$GEMINI_API_KEY" > ~/.config/shorts/env
mkdir -p ~/cr && cd ~/cr
```
State: `cr/campaigns.json` (every campaign seen: id, name, streamer handle, platform, rate, min payout, budget left,
status `seen|recommended|joined|skipped|ended`, notes, clips posted with dates/slugs). `cr/streamers.json` = layouts.
`cr/posted.json` = Twitch clip slugs already used (never reuse one).

## 1. Scout Content Rewards (built-in browser)
Tools `mcp__remote-devices__Claude_Browser__*` (ToolSearch the whole prefix; read the built-in-browser skill first).
Open https://contentrewards.com/c/discover. If it shows "Anmelden" → user must log in once in the Claude browser
(tell them; continue with the rest). If the computer is unreachable, say so and stop after step 5 prep.
Read every campaign's data with JS on the discover page (data is embedded in each campaign page's HTML):
```js
const all=[...new Map([...document.querySelectorAll('a[href*="/c/campaigns/"]')].map(a=>[a.href.split('?')[0],a.innerText.replace(/\s+/g,' ').slice(0,80)])).entries()];
const out=[]; for (const [href,t] of all){ const h=await (await fetch(href)).text(); const s=h.replace(/\\"/g,'"');
 const g=(re)=>(s.match(re)||[])[1]; out.push({t,href,pay:g(/"payoutModel":(\[.*?\])/),metrics:g(/"metrics":(\{[^}]*\})/),
 desc:(g(/"description":"(.*?)","feeSchedule"/)||'').slice(0,300),pool:/"type":"pool"/.test(s)}); } out
```
(cents: rate per 1K, minPayout/maxPayout per clip). Score each streamer/gaming campaign:
- Must: Twitch or Kick streamer we can download, English, YouTube **and** Instagram allowed, CPM (not pool unless
  qualify threshold is tiny), budget left ≥ $300.
- Good: low min payout (≤ $3 → paid from ≤ 3K views), rate ≥ $1/1K, few creators, avg views per approved clip
  (`totalViews/approvedSubmissionCount`) ≥ 1.5K, streamer live daily with fresh VODs/clips.
- Keep the 3–5 best as `joined`. Recommend at most 2 new joins per day; recommend leaving campaigns whose budget is
  < 10 % or that stopped streaming.
For each joined campaign open its page and its rules brief (Notion links open in the browser; scroll the inner
container or read with get_page_text) and store the rules in `~/cr/brief_<handle>.txt`. Note per-campaign extra
duties for the user (Discord, demographics proof) in campaigns.json.

## 2. Get footage
Per joined streamer: newest Twitch clips (viewers already found the best moments):
```bash
yt-dlp --flat-playlist -I 1:15 --print "%(url)s|%(view_count)s|%(title)s" "https://www.twitch.tv/<handle>/clips?filter=clips&range=24hr"
# fallback range=7d; download: yt-dlp -f "best[height<=1080]" -o src/<handle>_<n>.mp4 <clip url>
```
Skip slugs in posted.json. Kick: `yt-dlp https://kick.com/<handle>/clips` (test; if it fails, report it).
For longer context, a VOD section works too: `yt-dlp --download-sections "*START-END" https://www.twitch.tv/videos/<id>`.

## 3. Pick
`python3 ~/shorts-media/cr/pick.py ~/cr/brief_<handle>.txt src/<handle>_*.mp4` → fits/score/hook/title/start/end.
Use clips from range=7d (top 12 by views) not in posted.json. Take clips with fits=true and score ≥ 8 (7 only if nothing better), max 2 per campaign; skip dark content like executing begging NPCs. Pass --peak <peak> to stream_clip.py (cold open). Re-check the hook yourself: accurate, not clickbait.

## 4. Produce
New streamer → measure the facecam box once: extract a frame (`ffmpeg -ss 10 -i clip -frames:v 1 -vf
scale=960:-1,drawgrid=w=48:h=54:t=1:c=yellow@0.5 g.jpg`), LOOK at it, write `cam` [x0,y0,x1,y1] in 1920x1080
coordinates (×2 of the 960 grid) + `game_x` (0..1 centre of the action) + display name + hashtags into
`cr/streamers.json`. No facecam → `cam` = a 16:9 band of the gameplay (e.g. [0,0,1920,1080]) is fine.
```bash
python3 ~/shorts-media/cr/stream_clip.py <handle> src/<file>.mp4 <start> <end> "<hook>" out/<slug>.mp4 --peak <peak>
```
Layout: facecam top, gameplay below (bottom 140 px of the stream dropped = streamer's own captions), hook box 0–3.2 s on the cam/game seam (never over the face),
1–3-word pop captions with the spoken word in yellow (Gemini word timestamps), purple `twitch.tv/<handle>` label at the bottom all the time, "FOLLOW … ON TWITCH" card last 2.6 s.
QA every clip: contact sheet (`fps=1/4,scale=216:384,tile`), LOOK at it (cam crop on the face, no double captions,
CTA readable), check audio exists. Then `VIDEOS_BRANCH=videos-cr python3 ~/shorts-media/publish.py out/*.mp4`.

## 5. Ask the user (one message)
SendUserMessage in German + PushNotification ("Clips bereit – antworte mit ja"):
- campaign changes: "Beitreten: X (warum)", "Verlassen: Y (warum)";
- the clips: streamer, hook, title, preview URL (raw URL from publish.py);
- "Antworte **ja** (alles), oder z. B. 'ja ohne 2'".
Then end the turn and wait. If no answer comes in this session, do nothing else (next run starts fresh; unposted clips
can be reused next day if still < 48 h old).

## 6. After "ja" (same session)
1. Join the approved campaigns (campaign page → "Kampagne beitreten").
2. For each clip, schedule via Metricool at **now + 3 min**, clips ≥ 12 min apart, YouTube and Instagram separately
   (two posts, Instagram 4 min after YouTube):
   - YouTube: providers [{"network":"youtube"}], youtubeData {"title": "<title> #shorts", "type":"short",
     "privacy":"public", "madeForKids":false, "category":"GAMING", "tags":[streamer, "gta 6", "twitch clips"]}.
   - Instagram: providers [{"network":"instagram"}], instagramData {"type":"TRIAL_REEL","isAiGenerated":false}
     (trial reels are shown to NON-followers first = discovery for a new account; if Metricool rejects
     TRIAL_REEL, fall back to {"type":"REEL","showReelOnFeed":true,"isAiGenerated":false} and note it here).
   - Both: firstCommentText = one short question that invites replies about the clip (e.g. "Would you have
     stopped for the cops? 😂"), no links.
   - Text (both): one accurate sentence + `Follow twitch.tv/<handle>` + the campaign's hashtags (mix, ≤ 8).
3. Every campaign has a **30-minute submission window**. After each post goes live (check getScheduledPosts /
   the channel), open the campaign → "Clip einreichen": new posts from the linked accounts appear as tiles
   (`.clip-picker-tile`, selected = `aria-pressed="true"`). The dialog may PRE-SELECT a post of another campaign:
   check with JS that only this campaign's post is pressed (click tiles to toggle), tick the checkbox (find
   "Anforderungen gelesen"; verify `input[type=checkbox].checked`), click the dialog's "Clip einreichen" button,
   confirm "Clip eingereicht", click "Fertig". YouTube and Instagram are separate submissions. Instagram can take
   3–6 min after the scheduled time until it is PUBLISHED and shows up – wait and retry.
4. Record everything in campaigns.json + posted.json, commit + push main.
5. Final German message: what was posted (links), what was submitted, open duties (e.g. Bobby: after 1,500 views
   send the country breakdown via a Discord "Submit Demographics" ticket).

## Daily earnings check
On each run, before step 5, open https://contentrewards.com/c/submissions and /c/earnings and include in the message:
approved/rejected submissions (with reasons) and earnings. Learn from rejections (update the rules in this file).

## Reach (new account) – what the user must do, what we do
- 0 views on a brand-new channel is the platforms' new-account trust filter, not the clip. The fix is a manual
  warm-up on the phone, 20–30 min/day for 3–7 days (ssemble account-warmup-guide-2026): watch GTA/streamer
  clips fully, like 5–10, save 2–3, 1–2 real comments, share 1, follow 2–3 niche accounts; done when ≥ 8 of the
  first 12 Home (YouTube) / Explore (Instagram) tiles are on-topic. One device, one location, no VPN.
  NEVER automate likes, follows, comments or views – that is bot behaviour and gets the account flagged.
- Our side: strong first-second hooks (cold open), trial reels on Instagram, first-comment question, GTA 6
  keywords in titles, consistent daily posting at US daytime/evening, max 3/day while new, reply-worthy captions.
- Track views per clip each run (YouTube watch page `ytInitialPlayerResponse.videoDetails.viewCount`, Instagram via
  Metricool). If a YouTube Short still has 0 views after 48 h, tell the user to check YouTube Studio → Settings →
  Channel → Feature eligibility (verify phone) and Channel status.
