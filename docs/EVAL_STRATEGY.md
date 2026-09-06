# EVAL_STRATEGY.md — Kinetiq v3

> Eval-Driven Development for a movement detector. *The Builder's Gita* Ch 39 applied, almost
> line-for-line, to Kinetiq — because the hypothesis is exactly right: v1/v2 shipped with no evals, so
> "I tried it and it works" was the only evidence, and it was wrong in the gym.
> This doc wins on any "is it good enough to ship?" question (`CLAUDE.md` §6).
> Builds on the existing `../kinetiq-v2/evals/gate0/aggregate.py`.
> Last updated: 2026-08-30

---

## 0. The mental shift (Ch 39, translated)

Ordinary software is a light bulb — one test tells you everything. An AI detector is a drug — the same
input helps most reps, does nothing for some, harms a few, and you cannot tell from three tries. v1/v2
shipped the drug on a sample size of three (Gaurav's gym session *was* the trial, run in production).
Eval-driven development is refusing to do that: a defined set, measured outcomes, before-and-after,
decisions made on the distribution.

Kinetiq's twist on the book: our outputs aren't only text. So we run **three kinds of eval**, cheapest
first (the 70/30 rule):

| Kind | For | Example | Cost |
|---|---|---|---|
| **Assertion** | deterministic, syntactic | "empty frame → 0 reps"; "output schema valid"; "latency < budget" | free |
| **Label-based** (our "golden set") | rep-count accuracy + form precision/recall vs human/PT labels | "on 50 labeled squat reps, hip_sag precision ≥ X" | medium |
| **Judge** (LLM-as-judge) | semantic *text* only — coaching cues | "is the cue positive-before-correction, non-medical, grounded?" | model call |

The judge is for the **coaching text**, where the book's LLM-as-judge mechanics apply directly. The
detector itself is graded by **labels**, not a judge — you don't need a model to tell you the human
counted 12 reps and the app said 15.

---

## 1. Step 1 — Write the first eval set today (the day-one move)

Don't imagine the finished suite. Start with the cases we already have, for free, because the gym
already generated them. **Every field bug becomes eval case #1, #2, … the day it's found** — this is
the single most important habit in Ch 39, and it's how the known failures die permanently.

Seed cases (record these clips + label them):

| # | Case | Type | Must hold |
|---|---|---|---|
| 1 | **Bench moved, no human** | assertion | detected reps = 0 (validity gate rejects) |
| 2 | **Good-form push-ups** (PT-confirmed clean) | label | hip_sag flagged on ≤ 5% of good reps (precision) |
| 3 | **Two people in frame**, user is subject | assertion | skeleton stays on the locked user ≥99% of frames (`SUBJECT_LOCK_FLOOR`) |
| 4 | **Deliberately bad squats** (PT-confirmed faults) | label | each seeded fault flagged (recall ≥ bar) |
| 5 | **Partial-depth squats** | label | reps counted (graded), not dropped |
| 6 | **Slow reps** (3-0-1-0 tempo) | label | rep count matches human count |
| 7 | **Front / side / diagonal** of same set | label | rep count within tolerance across all three views |
| 8 | **Coaching cue on a flagged rep** | judge | positive-before-correction, non-medical, ≤ 8 words |

Cases 1 and 2 are the bench and hip-sag incidents. They are now tests. They cannot silently return.

Store as recorded sessions + a labels file, versioned in git next to the code (the eval set is
*source*). Extend `../kinetiq-v2/evals/gate0` — it already computes weighted rep accuracy and
device×lighting coverage; v3 adds **form precision/recall**, **subject-lock**, and **no-phantom-rep**
scoring.

---

## 2. Step 2 — The judge (coaching cues only) and how to keep it honest

Reach for the LLM judge only for the semantic *text* property — cue quality — never for the detector.
Ch 39's traps apply:
- **Calibrate first.** Hand-grade 20 cues, run the judge on the same 20, check agreement before
  trusting it at scale. A judge you haven't calibrated is a thermometer you never dipped in ice water.
- **Avoid the circular judge.** Don't judge cues with the same model family that wrote them; anchor to
  a human-written reference cue or use a different family. Self-preference bias grades generously.
- **Rubric, not vibes:** positive signal present? correction ≤ 8 words? medical language absent?
  grounded in the exercise library? Each a scored line.

---

## 3. Step 3 — Freeze a golden dataset (PT-verified)

Once the labeled set passes a couple dozen trustworthy cases per exercise, **freeze** it: a curated,
versioned, slow-changing set of recorded sessions with **PT/trainer-verified** labels. The trainer is
our domain expert — the book's "someone who actually knows the right answer." A golden case with a
wrong "correct" label is worse than no case (it trains and tests toward the wrong behaviour), so form
labels get PT sign-off.

Rules (Ch 39):
- **Cover the distribution** — include the awkward, the adversarial (bench, bystander, terrible
  lighting, equipment occlusion), and the should-not-count, not just clean reps.
- **The yardstick holds still.** Never "improve" the golden set in the same commit that changes a
  model — you'd no longer know if the score moved because the system improved or the goalposts did.
- **Version in git**, with each case linked to the bug or session that motivated it.
- Re-freeze the yardstick only at deliberate milestones (v3.0 golden set → v3.1 after adding a wave of
  exercises), and re-baseline everything against the new frozen set.

This golden set doubles as the **training set** for the Stage-4/5 learned models
(`VISION_ARCHITECTURE.md` §3) — one asset, both jobs.

---

## 4. Step 4 — The regression gate in CI (this is what v1/v2 never had)

Wire the golden set into CI next to unit tests. A change to the pose model, tracker, thresholds, form
model, or a new exercise runs the golden set; **if a tracked metric drops below its threshold, the
build fails and the merge is blocked** — with a legible report naming the regressed cases and showing
old vs new.

```
 PR opened
   └─► CI: 1.lint  2.unit tests  3.FAST EVAL (assertions + small labeled subset)
         └─ on merge-to-main / nightly: FULL EVAL (all labels + judge + drift)
              └─ metric < threshold → BLOCK, report: "squat rep-acc 94%→88%, 6 cases regressed…"
```

Ch 39's three gate rules:
- **Pick the threshold like an adult.** Detector evals have run-to-run + labeling variance; a too-
  strict "zero regressions" gate cries wolf and gets disabled. A live gate at a sane bar beats a
  perfect gate everyone bypasses.
- **Fast gate vs full gate.** Cheap assertions + a small labeled subset on every push (instant);
  full labeled precision/recall + judge on merge/nightly.
- **Legible to a non-engineer.** The report is a table Manu or Gaurav can read — accuracy by
  exercise, worst offenders, before/after — not raw JSON.

---

## 5. Step 5 — Before/after, every change, multi-dimensional

The deepest lesson in Ch 39: **a single climbing number can ship a disaster.** For Kinetiq the
dimensions that must move together:

```
 CHANGE: "turn on learned hip_sag model for push-up"
                    rep-acc  hip_sag   hip_sag   subject  latency
                             PRECISION  RECALL    lock             
 BEFORE (rules)      95%       62% ✗    90%       100%     40ms
 AFTER  (model)      95%       94% ✓    71% ✗     100%     55ms
 verdict: precision fixed (false accusations gone) BUT recall dropped —
          we now MISS real sags. Net: ship only if the miss is acceptable
          for this severity, else keep tuning. Decide on the TABLE, not a vibe.
```

For a **high-severity** flag we bias to precision (never accuse a good rep) and accept some recall
loss — but that is a *decision read off the table*, not a surprise found in the gym. Model selection
(BlazePose vs MoveNet vs RTMPose) is the same: point the golden suite at each, read the table, pick.
"Should we upgrade the pose model?" becomes an afternoon, not a religion.

---

## 6. Step 6 — Catch silent drift

Kinetiq drifts even with frozen code: a **pose library update**, a **browser/WebGL change**, a new
**device/OS**, or a shift in **who's testing and how they film** all move keypoints under us. Defense
(Ch 39): run the golden set on a **schedule** (weekly) plus a sample of recent real sessions, and
alert on a downward trend.

```
 golden-set rep-accuracy, weekly, CODE UNCHANGED:
   wk1 ████████████████ 94   wk2 ███████████████ 93   wk3 ██████████ 84  ← ALERT
   nobody deployed. MediaPipe Tasks Web auto-updated. Only the weekly run saw it.
```

A 5%/month slide = investigate; a 10%/day drop = incident. The graph is cheap; the churn report is not.

---

## 7. What to measure (the Kinetiq scorecard)

Per exercise, per change, the gate reports:

- **Rep-count accuracy** — `1 − Σ|detected−actual| / Σactual` (existing `aggregate.py` formula).
- **No-phantom-reps** — bench / empty clips must yield 0 reps. (Bystander is a *real-rep* clip: the
  user's reps are counted; it's scored under subject-lock + rep-accuracy, not here.)
- **Subject-lock accuracy** — % frames the locked user is the one tracked, in multi-person clips.
- **Form precision & recall, per flag** — the pair v1/v2 never measured; precision guards against
  false accusations, recall against missed faults. Weighted by severity.
- **View robustness** — rep-accuracy spread across front/side/diagonal.
- **Coaching-cue quality** — judge score (calibrated), + hard assertions (length, no medical terms).
- **Latency & cost** — hot-path budget held; on-device inference within device spread.

Device × lighting matrix coverage (already in `aggregate.py`) continues to gate breadth of evidence —
accuracy without coverage isn't a pass.

---

## 8. The one-week rhythm (Ch 39, Kinetiq edition)

- **Mon:** PT labels a new batch of recorded reps → new golden cases *before* any model change.
- **Tue:** train/tune a stage → run golden set locally → open PR with the before/after table attached.
- **Wed:** CI gate runs; a reviewer reads the table; merge only if no dimension regressed.
- **Thu:** a new field failure (from a real session) → add the exact clip as a labeled case, then fix,
  then confirm green.
- **Fri:** someone wants to swap the pose model to save size → point the golden suite at it → the
  table settles it in minutes, not a debate. Uneventful Friday.

The reward is invisible: the gym sessions that *don't* produce a bench-counts-6-reps story.
