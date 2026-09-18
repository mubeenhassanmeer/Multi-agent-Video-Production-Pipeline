# Background music library

Drop royalty-free `.mp3`/`.wav`/`.m4a` tracks here. The render stage picks
one at random per video, loops it to the video's length, and mixes it under
the voiceover at `MUSIC_VOLUME` (default 0.12, i.e. quiet background bed,
not competing with narration).

I'm not downloading/selecting tracks on your behalf here — pick sources
whose license you're comfortable with for monetized content:

- **YouTube Audio Library** (studio.youtube.com → Audio Library) — free,
  built for exactly this use case, some tracks require attribution (shown
  per-track).
- **Incompetech (Kevin MacLeod)** — free under CC-BY, attribution required
  in the video description.
- **Epidemic Sound / Artlist** — paid subscription, cleanest licensing for
  a monetized channel (no attribution needed, explicit commercial license).

Leave this folder empty to disable background music entirely regardless of
the `MUSIC_ENABLED` setting (the pipeline falls back to voiceover-only if no
tracks are found).
