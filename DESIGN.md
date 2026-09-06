# DESIGN.md

The visual + interaction system for the Kinetiq v4 camera PWA (`frontend/`). Mobile-first; every
screen is designed for a 390px-wide phone held in portrait during a workout.

## Design Principles
- **Glanceable mid-rep.** The person is exercising, often metres from the phone. The rep count is the
  largest thing on screen; the coaching cue is one short line; nothing else competes.
- **Calm, not gamified-loud.** Feedback is a coach's voice, not a slot machine. Positive-first: a cue
  only appears once there's a completed rep to comment on.
- **Honest about the camera.** The privacy promise (pixels stay on device) is stated where the user
  grants camera access, not buried.

## Color Tokens
Defined once as CSS variables in `frontend/styles.css` (`:root`). Do not restate the hex values
elsewhere — reference the token.

- `--bg` `#0f172a` (slate-900) — app background
- `--card` `#1e293b` (slate-800) — cards, cue bubble
- `--good` `#10b981` (emerald-500) — rep count, progress, clean reps, primary buttons
- `--warn` `#f97316` (orange-500) — **medium-severity** form flags
- `--danger` `#ef4444` (red-500) — **high-severity** / safety flags, "end set", "can't see you"
- `--text` `#ffffff`, `--muted` `#94a3b8`

Flag color maps to the exercise contract's `severity` via `frontend/severities.json` (a generated
mirror of `exercises/*.json` — the contract stays the single source; regenerate it if a contract's
severities change).

## Typography
System font stack (no webfont — one less network dependency at gym-wifi speeds). Weights: 800 for the
rep count and wordmark, 700 for buttons/headings, 600 for cues and flags, 400 body.

## Spacing & Layout
8px base rhythm. One screen visible at a time (`.screen.active`); three screens: picker → live →
summary. Content max-width 520px, centered, so it also reads on a tablet/desktop browser during dev.
Safe-area inset respected on the bottom control bar.

## Component Patterns
- **Exercise card** — full-width tappable card, name + view hint; emerald border on hover/focus.
- **Rep HUD** — centered giant number + phase label, drawn over the video, non-interactive.
- **Cue bubble** — card background, emerald left-border, one short line; hidden until the first rep.
- **Flag pill** — rounded chip, colored by severity token; label is the humanized fault id.
- **Primary button** — emerald; the destructive variant ("End set") is danger-red.

## States & Feedback
Every live screen must resolve one of: **loading** (warming up the pose model), **camera prompt**
(before permission), **permission-denied** (explain + Retry), **running** (HUD live), **API-
unreachable** (non-destructive banner + Retry; buffered frames are re-queued, never dropped), and
**empty summary** (no reps detected → guidance to reframe). These are the `#state-overlay` card and
the summary's empty branch.
