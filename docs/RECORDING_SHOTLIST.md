# RECORDING_SHOTLIST.md — Kinetiq v3 (bake-off minimum)

> Tick-as-you-go list of the ~27 clips that unblock the real pose bake-off and the first real accuracy
> numbers. Derived from `GOLDEN_SET_PROTOCOL.md` §8 (23 clips), plus section F's 4 recall-coverage sets
> added 2026-09-05 after the pre-recording cross-check (`CODE_SPEC_MAP.md` §8). One device, daylight —
> that's deliberate; device and lighting spread come later (gate-grade, protocol §9).
> Print this, take it to the gym, fill the blanks.

---

## Before you start
- **Device:** ________________  **Lighting:** daylight  **Date:** __________  **Camera height:** low / on the floor
- One person films while the other lifts (or self-record for side view with the phone on the floor).
- **Count every rep out loud while recording** — that spoken number is the ground truth.
- Save each video with its `clip_id` as the filename. **Do not put video in the repo** (protocol §1).
- After the session, each recorded video gets run through all 3 pose models to make keypoints, then the
  video is deleted/kept offline. Only keypoints + PT labels are committed.

## Fitness level of the lifter(s): ________________  (tag per clip if it varies)

---

## A. Normal sets — squat (6)   ~10 reps each (8–12)

| # | clip_id | view | do this | ✔ rec | reps counted | notes |
|---|---|---|---|---|---|---|
| 1 | `squat_clean_side_001` | side | clean form | ☐ | ____ | |
| 2 | `squat_clean_side_002` | side | clean form | ☐ | ____ | |
| 3 | `squat_faulty_side_001` | side | **deliberately cave the LEFT knee inward** (seed `knee_cave_left`) | ☐ | ____ | PT records **which knee** |
| 4 | `squat_clean_diag_001` | diagonal | clean form | ☐ | ____ | |
| 5 | `squat_clean_diag_002` | diagonal | clean form | ☐ | ____ | |
| 6 | `squat_faulty_diag_001` | diagonal | **deliberately cave the LEFT knee inward** (seed `knee_cave_left`) | ☐ | ____ | PT records **which knee** |

> **One specific side, deliberately.** There is no `knee_cave` fault — the library defines
> `knee_cave_left` and `knee_cave_right` as separate ids, and the detector flags them separately. A
> left-side cave recorded as `knee_cave_right` is a false positive *and* a false negative at once, so
> cave one named knee and have the PT label that exact id. (A label of plain `knee_cave` won't
> silently corrupt anything — `golden_loader` rejects an unknown fault id outright — but it will stop
> the whole set loading until it's fixed.)

## B. Normal sets — push-up (6)   ~10 reps each

| # | clip_id | view | do this | ✔ rec | reps counted | notes |
|---|---|---|---|---|---|---|
| 7 | `pushup_clean_side_001` | side | clean form | ☐ | ____ | |
| 8 | `pushup_clean_side_002` | side | clean form | ☐ | ____ | |
| 9 | `pushup_faulty_side_001` | side | **deliberately sag the hips** (seed `hip_sag` — the exact gym bug) | ☐ | ____ | |
| 10 | `pushup_clean_diag_001` | diagonal | clean form | ☐ | ____ | |
| 11 | `pushup_clean_diag_002` | diagonal | clean form | ☐ | ____ | |
| 12 | `pushup_faulty_diag_001` | diagonal | **deliberately sag the hips** | ☐ | ____ | |

## C. Normal sets — lunge (6)   ~10 reps each (alternating legs)

| # | clip_id | view | do this | ✔ rec | reps counted | notes |
|---|---|---|---|---|---|---|
| 13 | `lunge_clean_side_001` | side | clean form | ☐ | ____ | |
| 14 | `lunge_clean_side_002` | side | clean form | ☐ | ____ | |
| 15 | `lunge_faulty_side_001` | side | **deliberately lean torso forward** (seed `excess_torso_lean`) | ☐ | ____ | |
| 16 | `lunge_clean_diag_001` | diagonal | clean form | ☐ | ____ | |
| 17 | `lunge_clean_diag_002` | diagonal | clean form | ☐ | ____ | |
| 18 | `lunge_faulty_diag_001` | diagonal | **deliberately lean torso forward** | ☐ | ____ | |

## D. Special cases (2)

| # | clip_id | view | do this | ✔ rec | reps counted | notes |
|---|---|---|---|---|---|---|
| 19 | `squat_partial_side_001` | side | **partial-depth** squats — stop clearly above parallel every rep | ☐ | ____ | **every rep IS `shallow_depth` — PT labels it on all of them** |
| 20 | `pushup_slow_side_001` | side | **slow 3-0-1-0 tempo** push-ups (must still count) | ☐ | ____ | clean form otherwise — expect `faults: []` |

> **#19 is a rep-counting test, not a clean-form test.** What it proves is that a partial rep still
> **counts** (the validity gate accepts it) and scores lower — *not* that it's fault-free. Every rep in
> this clip genuinely is `shallow_depth`, and the detector flags it (verified: all reps flagged,
> form score 4.8 vs 10.0 for a full-depth rep). If the PT labels these reps `faults: []`, every one of
> those flags becomes a **false accusation** and `shallow_depth` precision drops for a reason that has
> nothing to do with detection quality. Label `shallow_depth` on every rep here.

## E. Negative / adversarial (3) — highest value, don't skip

| # | clip_id | view | do this | ✔ rec | reps (truth) | notes |
|---|---|---|---|---|---|---|
| 21 | `squat_bench_phantom_001` | side/diag | **slide a bench through frame, nobody exercising** (~20–30s) | ☐ | **0** | must detect 0 reps |
| 22 | `pushup_phantom_empty_001` | side | **empty frame / someone walks past**, nobody exercising | ☐ | **0** | must detect 0 reps |
| 23 | `pushup_bystander_diag_001` | diagonal | **user does ~10 push-ups while 1–2 others stand nearby** (put one under a brighter light) | ☐ | ____ | skeleton must stay on the user |

For #23, note **which person is the user** (position in frame) — the PT records it as the subject.

## F. Recall-coverage sets (4)   ~10 reps each — ~10 minutes total

Four faults have a working detector rule but nothing in A–E seeds them, so without these clips their
**recall denominator is zero** — the first report would show them with no positives at all, which
reads as "working" but is really "never tested". One set each fixes that.

| # | clip_id | view | do this | ✔ rec | reps counted | notes |
|---|---|---|---|---|---|---|
| 24 | `pushup_elbow_flare_side_001` | side | **deliberately flare the elbows out wide** (seed `elbow_flare`) | ☐ | ____ | keep hips level — isolate the one fault |
| 25 | `pushup_shallow_side_001` | side | **deliberately cut the depth** — bend the elbows only part-way (seed `shallow_pushup`) | ☐ | ____ | full lockout at the top, so only depth is wrong |
| 26 | `lunge_shallow_side_001` | side | **deliberately cut the depth** — shallow front knee, back knee high (seed `shallow_lunge`) | ☐ | ____ | stay upright — don't also lean the torso |
| 27 | `squat_torso_lean_side_001` | side | **deliberately lean the torso forward** (seed `excess_torso_lean`) | ☐ | ____ | reach full depth — don't also cut it short |

> **Seed one fault at a time.** Each of these exists to give one flag a clean recall measurement, so a
> set that accidentally carries two faults measures neither well. The "notes" column above says which
> *other* fault to actively avoid in each. Squat's `excess_torso_lean` is seeded here on **squat**
> specifically — clips #15/#18 seed it on lunge, and the two exercises carry different thresholds
> (45° vs 20°), so lunge clips do not exercise squat's rule.

---

## After recording (hand off)
- [ ] All 27 videos saved with `clip_id` filenames, reps-counted written above.
- [ ] Videos → keypoints per pose model (`golden/poses/<model>/`), then videos deleted/offline.
- [ ] PT labels each clip per `GOLDEN_SET_PROTOCOL.md` §7 (per-rep faults from the exercise's own
      `error_id`s; clean reps = `faults: []`), signs off (`pt_verified: true`).
- [ ] `MANIFEST.json` updated; run `python aggregate.py --golden golden/ --mode full` and
      `--compare-pose-models` — the first real numbers.

## Roughly how long
~27 sets is one focused gym session (70–100 min) plus a separate PT labeling sitting. Clean and faulty
sets can be back-to-back; the 3 negatives take five minutes total and matter most, and section F's
4 recall-coverage sets add roughly 10 minutes.

> This is the *bake-off minimum* — enough to pick a pose model and get a first real read. It is **not**
> enough to declare an exercise vision-live (that needs the gate-grade set, protocol §9: ≥5 devices ×
> 3 lighting, and ≥20–30 labeled instances of each high-severity fault).
