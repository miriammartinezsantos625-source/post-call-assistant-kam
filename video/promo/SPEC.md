# SPEC · «Al salir de la consulta» (storyline A)

GOAL:    A pharma hiring manager understands in 25 s that one post-visit dictation becomes an approved,
         compliant CRM record — and that the KAM, not the AI, decides.
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps
TIME:    25.0 s x 30 = 750 frames. Narrated: the voice (Kokoro ef_dora, es) is the clock.
         vo1 0.50–3.55 · vo2 3.85–7.28 · vo3 7.55–11.90 · vo4 12.20–16.89 · vo5 17.15–20.95 · vo6 21.30–23.30
         Anchors: «dictado» 2.46 · «transcribe» 3.95 · «quita» 5.69 · «paciente» 6.65 · «ficha» 10.63 ·
         «efecto adverso» 12.94 · «nada» 15.06 · «aprobación» 16.18 · «recordatorio» 17.51 · «correo» 18.49 ·
         «dos minutos» 20.0 · «Kam» 22.44
LOOK:    The product's own UI, unchanged: ground #F4F6F8, white cards with 1 px #D5DEE8 border, blue accent #1F4E79
         (labels, borders, active step), navy #0B1929 sidebar = the home stage and the end card, soft red #B4483A
         only on the compliance alert. Display: Source Serif 4 500 (italic accent word in #1F4E79); body:
         IBM Plex Sans 400/600; labels: IBM Plex Mono 500, 0.14 em tracking, caps. Rebuilt pieces at 1.6–2x their
         app size (body ≥ 30 px). Shadows only on lifted cards: 0 24 60 -24 rgba(11,25,41,.28). No grain, no vignette.
OBJECTS: the dictation widget (mic, live waveform, 00:00 timer) · the transcript card with the real note ·
         «Ana López» → [PACIENTE] (synthetic name) · the review screen (objective, SMART badges) · the decision panel
         with the red-edged alert card, the checkbox «He notificado a Farmacovigilancia» and «Aprobar y guardar» ·
         a large cursor (64 px) · the outputs screen (KPI «57 s», CSV / ICS cards, email draft) · the logo mark.
MOTION:  enter expo.out 0.5–0.7 s; camera power2.inOut 0.5–0.6 s (scale + x/y on a wrapper, transform-origin 0 0);
         exits power3.in, 40 % shorter; text per word: blur 6 px → 0, 0.13 s, 0.06 s apart; one hero move per shot.
SHOTS:
  S1 0.00–3.85  Recording widget at 2x on the app ground, sidebar edge left; waveform bars live, timer runs to 00:47
                by «dictado». Read: «Graba tu resumen» + reminder line. Hands off: the widget box morphs into the card.
  S2 3.85–7.60  Box morphs (0.55 s) into the transcript card; the note types in per word from «transcribe»;
                on «quita» «Ana López» gets a highlight and swaps to [PACIENTE]; chip «Privacidad · 1 dato sustituido»
                pops by «paciente». Hands off: the card shrinks into the workspace.
  S3 7.60–12.10 Review screen arrives (scale 1.12 → 1, 0.7 s), holds wide 1.0 s, camera pushes to objective + SMART
                (1.55x); badges land one by one on «ficha». Hands off: camera pans right to the decision panel.
  S4 12.10–17.10 Camera on the decision panel (1.7x). Alert card wipes in from its red edge on «efecto adverso».
                Cursor enters 14.6, clicks the checkbox at 15.25 (state swap: checked + Aprobar enabled), moves and
                clicks «Aprobar y guardar» at 16.55. Click sounds 1 frame after each click.
  S5 17.10–21.15 Match cut on the approve click: outputs screen enters at 1.06 and settles (0.5 s). Camera visits the
                CSV card («ficha» 17.2), the ICS card («recordatorio» 17.6), the email draft («correo» 18.5), then
                the KPI «57 s» at 1.9x by «dos minutos» 19.8 and holds.
  S6 21.15–25.00 The navy sidebar widens to fill the frame (0.6 s, power3.inOut). The mark draws, wordmark wipes in,
                then «Dictado → ficha CRM · IA local · decisión de la KAM» and «Miriam Martínez Santos, PhD».
                Holds 2 s. Music fades out over the last 1.5 s.
SOUND:   bgm_001 (HeyGen catalogue, «professional corporate pulse») at 0.12 under the voice, fade in 0.6 s, fade out 1.5 s;
         sfx_001 click at 15.28 and 16.58. No chimes.
BANNED:  dark void with floating UI; glow/particles; gradients on the ground; a title over a dimmed screenshot; three cards
         in a row as a feature list; everything fading up; text moving while read; the logo docked in a corner;
         any number or claim not measured in this project; on-screen text repeating the narration word for word.
QA:      t=0.0 (thumbnail: widget + reminder legible) · 3.2 (timer 00:47) · 6.9 ([PACIENTE] visible, name gone) ·
         10.9 (SMART badges) · 13.6 (alert card full) · 15.4 (checkbox checked) · 16.7 (approve pressed) ·
         20.3 («57 s» large) · 24.5 (end card complete).
