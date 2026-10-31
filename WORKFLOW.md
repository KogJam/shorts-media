# Daily Shorts run – instructions for Claude

Goal: produce **4 English fact Shorts** (25–40 s, vertical) and schedule them on the YouTube channel
through the **Metricool** connector (brand / blogId `7781434`). No human is watching: make the calls yourself,
note decisions in the final summary.

## 0. Setup (fresh machine)
```bash
git clone https://github.com/KogJam/shorts-media.git ~/shorts-media && cd ~/shorts-media
bash setup.sh                      # voice model, dictionary, emoji (all from GitHub)
export PIXABAY_API_KEY=...         # given in the task prompt – never write it into the repo
```
Network: only GitHub, `pixabay.com` and `cdn.pixabay.com` are reachable from the shell.

## 1. Choose 4 new facts
- Read `history.json` – never repeat a topic that is already in it (check titles *and* topics).
- Mix categories over the day, e.g. animals, space, human body, ocean, history, food, geography, nature, weird science.
- Only well-established, verifiable facts. If you are not sure, verify with WebSearch or pick another fact.
  No medical advice, no politics, no real people, no brands, nothing scary/graphic.
- Each fact needs a strong surprising hook ("Octopuses have THREE hearts").

## 2. Write one spec per fact → `specs/<YYYY-MM-DD>-<n>.json`
```json
{
 "id": "unique-slug",
 "hook": "Short headline shown on top (max ~6 words)",
 "title": "YouTube title, curiosity-driven, <= 70 chars, ends with #shorts",
 "description": "2 sentences + 'Follow for a new fact every day!' + 4-5 hashtags incl. #shorts",
 "tags": ["...", "shorts"],
 "voice": "am_michael",
 "lines": [ { scene }, ... ]          // 5-7 scenes, 6-14 words each
}
```
Scene fields (all optional except `say`):
- `say` – the spoken sentence (simple everyday words; numbers as digits are fine).
- `clip` – Pixabay search query for the full-screen background video, **or** `clip_id` (preferred, after picking).
- `inset` / `inset_id` – small tilted "GIF card" clip (use for a close-up/related object, ~every 2nd-3rd scene).
  `inset_x`, `inset_y` (0-1, default 0.5/0.42), `inset_delay` (s), `inset_tilt` (deg).
- `items` – 3D emoji accents: `{"emoji":"🐙","x":0.5,"y":0.42,"size":0.25,"anim":"pop","delay":0.3,"cross":false}`
  anims: pop, bounce, float, drop, swim, swim_left, spin, shake, pulse, zoom, grow, rise, orbit, fade_out.
  Keep emoji small (size 0.15-0.3) when a clip is behind them; `cross: true` draws a red X.
- `punch` – 1-3 word slam text (`punch_y` ≈ 0.62-0.7, `punch_delay` ≈ when the word is spoken).
- `number` – count-up `{"value": 1000000, "prefix": "", "suffix": "", "label": "...", "y": 0.55}`.
- `bars` – comparison `[{"label":"Crawling","value":25,"show":"easy","emoji":"🐌"}, ...]`, `bars_y`.
Layout: top 0-0.2 = hook, 0.25-0.7 = visuals, 0.75-0.82 = captions (keep free).
Vary scene types: every Short should have at least 4 different background clips, 1-2 insets, emoji accents,
and 2-3 punch words. The first scene must show the hook visually within 1 second.

Check pronunciation: `python3 -c "import tts,json,sys;print(tts.missing_words(' '.join(l['say'] for l in json.load(open(sys.argv[1]))['lines'])))" specs/X.json`
Unknown words get spelled letter by letter → rephrase, or add an IPA entry to `custom_words.json`
(Kokoro/misaki US IPA, e.g. `"octopuses": "ˈɑktəpʊsɪz"`).

## 3. Pick clips (quality matters most!)
```bash
python3 pick.py "octopus" "coral reef" "heart anatomy"   # writes out/pick_*.jpg
```
Look at every sheet with the Read tool. Use only clips that clearly show what is being said.
Avoid: AI-looking monsters, text/watermarks, people's faces as the main subject, logos, unrelated scenes.
If nothing fits, try other queries (simpler nouns work best) or use an emoji-only scene for that line.
Put the chosen ids into the spec as `clip_id` / `inset_id` (P = portrait, L = landscape; portrait preferred).

## 4. Render + check
```bash
python3 render.py specs/X.json out/X.mp4
```
~2 min each. Then grab frames (`ffmpeg -ss <t> -i out/X.mp4 -frames:v 1 -vf scale=270:480 f.png` at 5-6 times),
combine into one contact sheet and look at it: text readable? nothing overlapping captions? clips fitting?
Fix the spec and re-render if needed.

## 5. Publish + schedule
```bash
python3 publish.py out/A.mp4 out/B.mp4 out/C.mp4 out/D.mp4   # prints public URLs
```
For each video call Metricool `createScheduledPost` with blogId `7781434`, network `youtube`, timezone
`Europe/Berlin`, `autoPublish: true`, `media: [url]`, `text` = description, and
`youtubeData: {title, type: "short", privacy: "public", tags, category: "EDUCATION", madeForKids: false, isAiGeneratedContent: false}`.
Default slots (Europe/Berlin): **14:03, 17:33, 21:03, and 00:33 the next night** (= US morning to evening).
If a slot is already in the past, use the next free slot ≥ 20 min from now. Do not double-book: check
`getScheduledPosts` for the day first. Confirm every post comes back with status PENDING.

## 6. Bookkeeping
Append each Short to `history.json` (`{"date","id","title","topic","category","slot"}`), commit and push `main`.
Never commit `out/`, clips or keys. End with a short summary: titles, slots, anything that went wrong.
