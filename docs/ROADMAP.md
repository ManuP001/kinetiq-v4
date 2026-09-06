# ROADMAP.md — Kinetiq v3

> The sequenced build, where **every stage is defined by its eval gate**, not by a feature list. A
> stage isn't "done" when the code is written — it's done when the golden set says so (Ch 39).
> This supersedes the v2 vision-track plans (`../kinetiq-v2/SPRINT.md`, `ACTION_PLAN.md`) which
> targeted the old single-rulebook detector.
> Owners: Manu, Gaurav (+ contributors on vision/labeling). Last updated: 2026-09-01

---

## Sequencing principle

Fix the foundation before tuning; prove the technique on the **easy, already-instrumented** exercises
before adding hard ones; let no stage advance until its gate is green. The order follows the root-cause
dependency chain (RC1→RC6) from `../kinetiq-v2/VISION_ERROR_ANALYSIS.md`.

```
 Stage 0  ──►  1  ──►  2  ──►  3  ──►  4  ──►  5  ──►  6
 evals     lock+   pose    robust   learned  expand   coach +
 first     valid   bake    counter  form     A→B→C    drift
 (RC6)     (RC1,2) (RC5)   (RC4)    (RC3,4)  (gated)  (RC6 cont.)
```

---

## Current status — 2026-09-01 (read this first)

Stages 0–3 are **built**, and a **live prototype + effectiveness loop** now sits on top of them
(Detector API → PWA → live feedback → export → validate → score → one-command effectiveness report,
trainer-gated and parity-checked). **But everything green is on synthetic or stubbed data — there are
zero real-world measurements yet.** The machinery to gather evidence is complete and calibrated; the
evidence is not. A fully-green synthetic pipeline is not validation (Ch 39: "I tried it and it works"
is the sentence to distrust).

| Stage / piece | State | Evidence basis |
|---|---|---|
| 0 — Eval harness | built | synthetic fixtures |
| 1 — Subject-lock + rep-validity | built | synthetic fixtures |
| 2 — Pose bake-off tooling | built; **verdict blocked** | needs the ~23 real clips (`GOLDEN_SET_PROTOCOL` §8) |
| 3 — Flag hysteresis + visibility | built | synthetic fixtures |
| Live prototype (Detector API + PWA `kinetiq-demo3`) | built; plumbing-verified | Playwright with **stubbed** MediaPipe |
| Effectiveness report (`effectiveness_report.py`) | built | synthetic + stubbed-camera bundles |
| 4 — Learned form model | **not started — blocked** | needs real labeled golden data |
| 5 — Exercise expansion | not started | gated |
| 6 — Coaching + drift | not started | gated |

**Nothing above Stage 3 proceeds, and no product is built on these results, until GATE G-REAL passes.**
**Exception — preponed, runs in parallel (needs no real data):** authoring the exercise **contracts**
for all 14 exercises (Stage 5a). Detector support and vision-live for the 11 new ones stay gated.

---

## GATE G-REAL — First real effectiveness session *(blocks Stage 4, product build, and threshold tuning)*

**Why:** every result so far is synthetic/stubbed. This gate is the first contact with reality — the
step that turns "the instrument is built" into "we have evidence."
**Do:** run one real gym session through the live prototype — real camera + real MediaPipe, a few clean
and a few deliberately-sloppy sets across squat / push-up / lunge (bench + bystander scenarios if
possible), then a PT labels the reps. Produce the effectiveness report.
**Last mile to run it:** deploy the Detector API + PWA over HTTPS (code built, hosting not); apply the 3
over-cap coaching-cue rewrites; line up the PT.
**Exit gate:** a real (n-small, single-user BlazePose) effectiveness report exists, showing rep-count
accuracy vs human count and per-flag form precision/recall vs the trainer.
**Decision off it:**
- **Holds up on real bodies** → you now have evidence. Proceed: Stage 2 bake-off on the 23 clips → tune
  the placeholder thresholds on real data → Stage 4 → product build.
- **Bad** → caught before building product on a broken detector. Diagnose (the whole reason the harness
  exists); do not paper over with copy or UX.

---

## Stage 0 — Eval foundation & instrumentation *(do this first — it is the product)*
**Why first:** Ch 39 — the eval set is the executable spec; without it every later stage is
un-gradeable. This is also the direct answer to "v1/v2 had no evals."
**Work:** extend `../kinetiq-v2/evals/gate0` to score form precision/recall, subject-lock, and
no-phantom-reps; build the labeling workflow (record → PT/human labels → frozen golden set); stand up
the CI regression gate (fast + full); instrument every pipeline stage to log inputs/outputs.
**Convert now:** the bench→6-reps and hip-sag-false-positive incidents become eval cases #1 and #2.
**Exit gate:** the gate runs in CI and blocks merges; ≥ the two field-bug cases + a starter golden set
per current exercise exist, PT-signed for form labels.

## Stage 1 — Subject-lock + rep-validity gate *(RC1, RC2)*
**Why:** kills the two worst trust failures — phantom reps and skeleton-jumping — that block everything
above the vision layer.
**Work:** person-detect + subject-lock (Stage 1 of `VISION_ARCHITECTURE`), rep-validity gate (Stage 3
there). Pause-on-lost-subject rather than silent retarget.
**Exit gate:** on the golden set — **0 reps** on bench/empty clips; **≥99% subject-lock
(`SUBJECT_LOCK_FLOOR`)** on bystander/multi-person clips (where the user's own reps are still counted);
rep-accuracy on the 3 exercises not regressed vs baseline.

## Stage 2 — Pose-model bake-off *(RC5)*
**Why:** the single-MediaPipe choice was never measured; view/lighting sensitivity partly traces to it.
**Work:** run BlazePose vs MoveNet Thunder vs RTMPose (and multi-person detectors) against the golden
set; read the table across accuracy × latency × device spread; pick by number (Ch 39: "religion into
measurement"). Adopt 3D world-landmarks if they cut the front/side count gap.
**Exit gate:** a chosen pose+tracker stack that wins the golden-set table; view-robustness (front/side/
diagonal spread) improved vs Stage 1.

## Stage 3 — Robust rep counter *(RC4, RC6)*
**Why:** slow reps missed, partial squats not counted, side over-count / front under-count.
**Work:** temporal smoothing + hysteresis + tempo tolerance on the FSM; graded depth (partial reps
count with lower score, not dropped); optional learned rep-boundary model if it beats the smoothed FSM.
**Exit gate:** slow-rep, partial-depth, and cross-view eval cases pass at the rep-accuracy bar.

## Stage 4 — Learned per-exercise form model *(RC3, RC4)*
**Status: BLOCKED by GATE G-REAL** — there is no labeled real data to train on until the first real
session runs. Do not start.
**Why:** false negatives (bad reps unflagged) and false positives (hip-sag on good form) come from the
sparse, uncalibrated, ungraded rule set.
**Work:** train the Stage-5 form model on the labeled golden data; fitness-level grading; deterministic
safety veto retained. Migrate each flag advisory→authoritative **only** when its precision/recall clears
the bar (`EVAL_STRATEGY` §5). Kill the hip-sag false positive **with recall held** — proven on the
before/after table.
**Exit gate:** per-flag precision/recall bar met on squat/pushup/lunge; hip-sag precision fixed without
recall collapse; no single-metric ship.

## Stage 5 — Exercise expansion *(all 14 defined; contracts preponed, detector gated)*
**Why:** the 11 requested additions are part of the plan — but trust one at a time
(`EXERCISE_LIBRARY` §6). "Add an exercise" is three layers with different gates: author the contract →
wire detector support → turn vision-live. Only the last needs real per-exercise data.

**5a — Contracts *(PREPONED — author now, in parallel with GATE G-REAL; needs no real data).***
Author the machine-readable contract JSON for the 11 new exercises (same schema as the 3 core:
rep/hold phases, `form_checks` with **seed** thresholds, severity, contraindications, ≤8-word cues),
matching the tiers/faults already described in `EXERCISE_LIBRARY` §3. `vision_support: false` for all;
seed thresholds flagged placeholder; any biomechanically-uncertain or safety-critical rule marked
`needs_pt_confirmation` rather than guessed. Unblocks fast expansion later without shipping unvalidated
detection.

**5b — Detector support + turn-on *(GATED — after G-REAL and per-exercise eval).***
Order: Tier A (`plank`, `leg_raise`, `pull_up`) → Tier B (`bicep_curl`, `overhead_press`,
`arnold_press`, then `deadlift` w/ PT sign-off) → Tier C (`triceps_pushdown`, `hanging_leg_raise`,
`hamstring_curl`, `bench_press` last, PT-gated). Planks graded on hold-quality, not rep-count. Tier-A
detector code MAY be built in the G-REAL window so it's validation-ready.
**Exit gate (per exercise):** flips `vision_support: true` only on passing its full bar
(`EXERCISE_LIBRARY` §5). Safety-critical lifts need PT sign-off + veto verified before any form flag.

## Stage 6 — Coaching generator + drift monitoring *(RC6 continued)*
**Work:** wire the tiered coaching (v2) on the trusted detector output; stand up scheduled weekly drift
runs on sampled real sessions with alerting.
**Exit gate:** calibrated cue-quality judge passing; drift job live and alerting on downward trends.

---

## What stays parked / explicit non-goals (unchanged from v2 decisions)

- No pixels off device (privacy invariant) — even the learned form model consumes keypoints only.
- No genericising the engine into a reusable library until it's proven on Kinetiq (`CLAUDE.md` §4).
- Diet/nutrition out of scope; exercise breadth gated, not rushed.
- No vision-live exercise before its eval bar — regardless that 14 are defined.

## Relationship to the v2 docs

`../kinetiq-v2` remains the source for the data model, API contracts, and the root-cause analysis this
roadmap answers. v3 changes the **detector and the discipline**; the backend/schema plan from v2 still
stands and is reused.
