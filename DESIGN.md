# DESIGN.md — the PWA's visual system

Mobile-first at **390px**. Dark only. Used in a gym, at arm's length, at a glance.

## Tokens
Defined once in `styles.css` `:root`; never restate a hex in a rule.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0d0f13` | page |
| `--surface` / `--surface-2` | `#161a21` / `#1e2430` | cards, raised rows |
| `--line` | `#272d38` | hairlines, inactive borders |
| `--text` / `--muted` | `#eef1f6` / `#98a2b3` | body / secondary |
| `--accent` | `#4ade80` | primary action, live cue |
| `--high` / `--med` / `--low` | `#f87171` / `#fbbf24` / `#60a5fa` | flag severity |

Severity colour comes from `severities.json`, generated from `exercises/*.json`. Never
hardcode a severity map in JS.

## Type
System stack. Rep count 54px tabular — legible from where the phone is propped. Cue 19px
semibold. Body 16px. Nothing below 13px.

## Layout
Single column, `max-width: 480px`. Camera stage is 3:4, `object-fit: cover`, mirrored.
Tap targets ≥ 48px. Respects `env(safe-area-inset-*)`.

## Every screen handles
1. **Loading** — model warm-up, spinner + what's happening.
2. **Camera prompt** — exercise choice, explains that video never leaves the phone.
3. **Permission denied** — why it's needed, a Retry button, and how to unblock.
4. **Running** — rep count, phase, cue, flag pills.
5. **API unreachable** — a non-destructive amber banner. Counting continues, frames are
   re-queued, never dropped.
6. **Empty summary** — distinguishes "no frames captured" from "no complete reps".

## Honesty rule
A fault the detector could not judge renders as a grey `unknown` pill saying so — never as
absence. "Couldn't tell" and "you were fine" are different messages, and collapsing them
is how a form coach loses trust.

## Motion
Transitions ≤ 150ms. The spinner slows under `prefers-reduced-motion`.
