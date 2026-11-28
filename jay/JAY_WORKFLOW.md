# jay.vs.life – daily episode run (instructions for Claude)

Channel: **jay.vs.life** – YouTube channel + Instagram @jayvslife2026, both on Metricool brand **blogId 7781434**
(label may still read "CrackBuddy"), timezone Europe/Berlin. One new English episode per day. Nobody is watching:
decide yourself, report at the end in German.

## Format (what works – keep it)
- POV story in the 2nd person ("You…"), told by a dry deadpan narrator, **25–35 s, 10–14 short lines** (changed
  2026-11-28: 50-s videos were watched only 6–18 s on average and 30–65 % swiped away in the first 3 s).
- **Hook first:** line 1 is already the funniest/most embarrassing moment or a tension question (cold open), never slow
  setup. Spec field `"hook"`: ≤ 8 words, e.g. "POV: you said 'you too' to the waiter" – story.py shows it as a white
  banner at the top for the whole video (optional `"hook_secs"` to hide it earlier).
- **Funny and tense the whole time:** a joke, roast or escalation every ~4–5 s, new image or camera move every
  2–3 s, no filler lines. Build it like a mini thriller: things get worse and worse → twist → loop.
- Vary the structure from episode to episode (narrator-led, Theo dialogue-led, countdown, "rules"…) so the channel
  does not look like mass-produced content.
- Best so far: "enjoy your meal – you too" (1.4k IG views, 18 s watch time) – short, awkward social moments win.
- **Topic: an everyday moment almost everyone has lived** ("haha that happened to me" / "relatable"). Not niche,
  not about a specific product, person, game or event. Ideas: forgetting why you entered a room, "enjoy your meal" –
  "you too", "we have food at home", snooze button, winning an argument in the shower, phone at 1 %, "we need to talk",
  replying "you too" to a happy birthday, holding the door for someone who's far away, autocorrect disasters, the
  group chat going silent, saying "what?" three times then just laughing, losing your phone while holding it…
- **Comedy:** jokes, roasts between the friends, insults ("clown", "dumbass", "confused monkey"), 2–4 swear words
  placed on punchlines (never in the first ~4 s), absurd details (the pigeon), one twist in the last 8 s and a last line
  that loops back to the first. Middle finger image allowed. No slurs, nothing about real people, politics, religion,
  ethnicity, sexuality, minors, self-harm or violence against someone.
- Cast: **Jay** (main, mustard hoodie, curly hair, deadpan), **Theo** (best friend, backwards red cap, chaotic,
  always late, roasts Jay). Mia (honest friend) and Rocco (always broke) may be mentioned; create their refs only if
  needed (jay/chars/mia_egg.png is NOT usable – wrong outfit).

## Steps
1. `git clone --single-branch --branch main https://github.com/KogJam/shorts-media.git ~/shorts-media && cd ~/shorts-media && bash setup.sh`
   `export GEMINI_API_KEY=...` (from the task prompt; never commit it).
2. Read `jay/history.json` – never repeat a topic. Pick one relatable topic, write the script.
3. Images: reuse `jay/lib/*.png` (Jay close-up deadpan, sofa, bored; Theo bed, phone at night) wherever they fit,
   generate only the 5–8 new shots the story needs with
   `python3 jay/gen3d.py out/jay/<id>/<shot>.png "<prompt>. One single full-frame image, no panels, absolutely no text,
   letters, signs or logos anywhere." jay/chars/jay_egg.png [jay/chars/theo_egg.png]`
   (run 4 in parallel with `&` + `wait`). Make a contact sheet and LOOK at it: right character (Jay must have his curly
   hair!), no text/misspelled signs, no comic panels, no duplicate characters. Regenerate bad ones. Copy good generic
   shots into `jay/lib/` for later episodes.
4. Spec `jay/specs/ep<N>-<slug>.json` – copy the structure of `jay/specs/ep3-wave.json` (engine gemini, voices
   narrator = Zubenelgenubi tempo 1.1, theo = Zubenelgenubi pitch 3 tempo 1.05, keep the "clear, clean…" style texts).
   Per line: `say`, `img`, `key` (1 word to highlight), optional `who:"theo"`, `move` (push/pull/pan_l/pan_r/snap/shake),
   `sfx` (impact on punchlines, pop), `gap`.
5. Render: `python3 jay/story.py jay/specs/<spec>.json out/jay/<id>.mp4` (Gemini TTS may hit a rate limit – the
   script waits and retries). Duration **25–35 s** (cut lines if longer, do not speed up the voice). Grab 9 frames into a contact sheet and LOOK at it.
6. Publish: `VIDEOS_BRANCH=videos-jay python3 publish.py out/jay/<id>.mp4`.
7. Schedule (Metricool, blogId 7781434): first `getScheduledPosts` for today … +3 days. Slot = **21:13** YouTube,
   **21:43** Instagram on the first day (today, else the next days) where no jay post exists yet; if today's 21:13 is
   past, use the next day. Never more than one episode per day.
   - YouTube: providers [{"network":"youtube"}], youtubeData {title ≤ 70 chars with 💀 and " #shorts", type "short",
     privacy "public", tags [...,"jay vs life","shorts"], category "COMEDY", madeForKids false, isAiGeneratedContent false},
     text = 1–2 lines + "It's not just you." + 4–5 hashtags incl. #relatable #shorts, firstCommentText = an easy question
     or "Tag the friend who…".
   - Instagram: separate post, providers [{"network":"instagram"}], same media URL (use the static.metricool.com URL
     returned by the YouTube post), instagramData {"type":"REEL","showReelOnFeed":true,"isAiGenerated":true}, lowercase
     caption + "it's not just you." + 5–6 hashtags ending with #reels, same firstCommentText.
   - Never TikTok. Confirm both come back PENDING.
8. Append to `jay/history.json` `{date, id, title, topic, yt_slot, ig_slot}`, commit spec + history + new lib images
   (never out/, never keys), push main.
9. German summary via SendUserMessage: title, topic in one line, publish times, any problem.
