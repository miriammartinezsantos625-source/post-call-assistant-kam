# REVIEW · Post-Call Assistant KAM — promo 40 s

Delivered: `../out/post-call-assistant-kam-demo-40s.mp4` (1920×1080, 30 fps, H.264 + AAC, 40.0 s, 9.9 MB) — copy on the Desktop;
uploaded to YouTube as **unlisted** (Oculto): https://youtu.be/6jJMFs4iWzM (QR on the Desktop). The 25 s cut is `../out/post-call-assistant-kam-demo.mp4`.

40 s version adds: the sidebar click into «Historial por cuenta» and the next-visit brief (22.2–28.4 s), then a zoom through the
«Alertas gestionadas» card into the measured results — 3/3 possible adverse events detected, 0 patient identifiers sent to the
model, on 20 synthetic notes (28.4–36.8 s). Music bed: the catalogue track crossfaded with itself to 40 s. Loudness −13.4 LUFS,
true peak −1.0 dBTP; rendered audio re-transcribed: one voice, eight lines in order.

## Creative calls
- Storyline A «Al salir de la consulta» (B «Un minuto, una ficha» and C «Lo que no puede esperar» not built; both in STORYLINES.md).
- Every product screen is the real app, captured from one synthetic demo visit (account 4, invented patient «Ana López»).
  Rebuilt on top of it, in the app's own styles: the live dictation widget (waveform + timer), the transcription card,
  the cursor, and covers that are wiped away to show the record filling in and the alert landing.
- Numbers on screen are from that run: proposal 52 s, note → approved record 57 s. No other claims.
- Voice: Kokoro `ef_dora` (local, free). HeyGen voices required a paid HyperFrames plan, so they were not used.
  «email» → «correo» and «KAM» spelled «Kam» so the voice pronounces them correctly.
- Music: HeyGen catalogue track (free with the account), 0.12 under the voice; two real click sounds on the two clicks.

## Measured
- `check`: 0 errors. Kept warnings: camera/cursor extending past the canvas (intentional moves); svg dash warning on the
  logo strokes (they start at opacity 0, so no stray dot).
- Rendered audio: −13.3 LUFS integrated, true peak −1.0 dBTP, no clipping. Voice lines loudness-normalised (−16 LUFS each).
- Re-transcribed the rendered audio with Whisper: one voice, all six lines in order, no overlap. Music checked alone: no speech.
- Sound was measured and transcribed, not listened to by a person.

## Weakest shot / with more time
- 7.6–8.4 s: the review screen arrives with its fields still empty — reads as «before», but is the plainest frame.
- The «Privacidad · 1 datos sustituidos» label in the captured screens has the old plural bug (fixed in the app since).
  Re-capturing needs another local LLM run; do it once the disk has room.
- Product UI text is small at phone width (360 px); the voice, the «57 s» close-up and the end card carry the message there.
