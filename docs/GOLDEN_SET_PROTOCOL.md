# GOLDEN_SET_PROTOCOL.md — Kinetiq v3

> How to record and PT-label the **real** golden set — the frozen, human-verified data the eval
> harness scores everything against. Stages 0–1 were built and proven on *synthetic* keypoints; every
> real accuracy number, and the entire Stage-2 pose bake-off, is blocked on this data. This is now the
> critical path.
> Consumes the schema from `EVAL_HARNESS_STAGE0_SPEC.md` §4–§5. Feeds `../kinetiq-v2/evals/gate0/`.
> Owners: Manu, Gaurav + a trainer/PT (form labels). Last updated: 2026-08-30

---

## 0. Why this, and why now

The harness is ready; the data is not. A pose-model bake-off (Stage 2) **cannot** run on synthetic
keypoints — comparing BlazePose vs MoveNet vs RTMPose requires real recorded movement to run each
model over. And "is the detector accurate?" only becomes a real number once clips are labeled by
someone who knows correct form. So the next unblock is recorded, labeled clips — not more code.

**Golden ethos (Ch 39):** don't imagine the finished 500-clip suite and freeze. Start with the small
set that lets you *decide* (§8 "bake-off minimum"), grow it toward the gate-grade set (§9) over time,
and turn every real field failure into a permanent clip.

---

## 1. Privacy & consent (non-negotiable — carries the v3 invariant)

- **Video never enters the repo and never leaves the device it was labeled on.** It exists only to
  (a) let the PT label form and (b) generate keypoints from each candidate pose model. After that it
  is deleted or kept offline. Only **keypoints + labels** are frozen and committed.
- Everyone recorded (including bystanders in multi-person clips) gives explicit consent to be filmed
  for product testing. Don't film strangers who haven't consented — stage the "bystander" with a
  willing second person.
- `golden/` (keypoints + labels) is committed; a `.gitignore` rule keeps any stray video/image files
  out. Never commit a frame.

---

## 2. What a "clip" is, and the files it produces

A **clip** = one recorded set (or one staged negative scenario) of a single exercise. Each clip yields:

```
golden/
  MANIFEST.json                          # index of every clip (EVAL_HARNESS_STAGE0_SPEC §4)
  <clip_id>.labels.json                  # frozen ground truth (PT-verified) (spec §5)
  poses/<pose_model>/<clip_id>.keypoints.jsonl   # frozen input, ONE per pose model (spec §5)
```

- `clip_id` convention: `<exercise>_<scenario>_<view>_<NNN>`, e.g. `squat_clean_side_001`,
  `pushup_badform_diag_003`, `squat_bench_phantom_001`.
- **One keypoints file per pose model per clip** (`poses/blazepose_33/…`, `poses/movenet_17/…`,
  `poses/rtmpose_…/…`). Stage 2 runs the detector over each and reads the comparison table. Each
  `keypoints.jsonl` frame carries its `pose_model`, variable-length `kp`, and `z: null` for 2D models
  (per the Stage-0 schema).
- `labels.json` is **model-independent** — one per clip, shared across all pose models (ground truth
  doesn't change with the model under test).

---

## 3. The recording matrix

Vary these axes (values match what the harness already understands):

| Axis | Values | Notes |
|---|---|---|
| Exercise | `squat`, `pushup`, `lunge` | v3 Stage-2 scope = the current three; add Tier A/B/C later |
| View | `front`, `side`, `diagonal` | 23-Aug finding: diagonal > side > front. Capture all three of the same set where possible |
| Lighting | `daylight`, `indoor_evening`, `dim_room` | the 3 the export schema + `aggregate.py` expect |
| Device | ≥5 real mid-range Android phones | record the model string; drives device×lighting coverage |
| Fitness level | `beginner` / `intermediate` / `advanced` | tag per clip; needed for graded-strictness evals |
| Clip type | `normal`, `phantom_bench`, `phantom_empty`, `bystander` | §4 |
| Reps/set | 8–12 (`normal`) | matches the coverage protocol |
| Sets/cell | ≥3 per (device × lighting) cell | matches the coverage protocol |

**Form spread within `normal` clips (this is what makes form P/R real):** record BOTH
- **clean sets** (PT confirms good form → reps labeled `faults: []`) — these test *precision* (a good
  rep must not be accused), and
- **deliberately-faulty sets** (the lifter intentionally caves knees / sags hips / cuts depth → PT
  labels the specific fault per rep) — these test *recall* (a real fault must be caught).
Plus **partial-depth** and **slow-tempo (3-0-1-0)** sets, since those were specific field complaints.

---

## 4. The negative / adversarial clips (the RC1/RC2 gates — record these early)

These prove the Stage-1 gates on real footage. They are the highest-value clips per minute recorded.

| clip_type | How to stage | `actual_reps` | Proves |
|---|---|---|---|
| `phantom_bench` | Point the camera at a bench; slide/move it through frame with **no one exercising** | 0 | bench can't count reps (RC2 / the original bug) |
| `phantom_empty` | Empty frame, or someone walking past not exercising | 0 | no spurious reps from ambient motion |
| `bystander` | The user does the exercise while **1–2 other people** stand/move nearby (ideally one under brighter light) | the user's real count | skeleton stays on the user (RC1) |

For `bystander`, record in `labels.json` which person is the subject (`subject.subject_track_id`) and
`num_people_in_frame`.

---

## 5. Capture procedure (per clip)

1. **Frame it** per the 22-Aug learnings: side/diagonal beats front; camera low (near the floor) for
   side view catches the whole body and lets one person self-record.
2. **Set the metadata** before recording: exercise, view, lighting, device, fitness_level, clip_type.
3. **Count reps out loud** while recording (as in the Gate-0 protocol) — this is the ground-truth rep
   count. For faulty sets, the lifter/PT calls the intended fault per rep too.
4. **Keep it 8–12 reps** for `normal` clips.
5. Save the video locally with the `clip_id` as its filename. **Do not add it to git.**

---

## 6. Generating keypoints (offline, per pose model)

For each recorded video, run **each candidate pose model** over it to emit a `keypoints.jsonl`:

- Models to capture for Stage 2: **BlazePose (33)**, **MoveNet Thunder (17)**, **RTMPose**. (A small
  offline script per model; MediaPipe/MoveNet run in Python or Node, RTMPose via its OSS runtime.)
- Emit the Stage-0 frame schema: `{t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis],…], box}]}`,
  `z: null` for 2D models. Include **all detected people** (needed for `bystander` subject-lock).
- Write to `golden/poses/<pose_model>/<clip_id>.keypoints.jsonl`.
- **Then delete/offline the video.** The committed artifacts are keypoints + labels only.

> This step is a small tool to build in Stage 2 (the "run each pose model over a clip" harness). The
> protocol here defines the output it must produce; the Stage-2 prompt covers building it.

---

## 7. PT labeling workflow (the part only a trainer can do)

The PT watches each video and produces `labels.json` (`EVAL_HARNESS_STAGE0_SPEC.md` §5):

1. **Rep count** — confirm the true number of reps (`ground_truth.actual_reps`).
2. **Per rep** — list the faults present, using **only that exercise's `error_id`s** from
   `../kinetiq-v2/exercises/<exercise>.json` (`common_errors[].error_id`). A clean rep = `faults: []`.
   - squat: `knee_cave_left`, `knee_cave_right`, `shallow_depth` (+ `excess_torso_lean`)
   - pushup: `elbow_flare` (per-side per the Vision_Contract), `hip_sag`, `shallow_pushup`
   - lunge: `shallow_lunge`, `excess_torso_lean` (the two knee checks are an unresolved spec conflict —
     **do not label them** until that's resolved; `CHANGELOG` 0.3.0)

   **Knee cave is per-side.** There is no `knee_cave` id — record `knee_cave_left` or
   `knee_cave_right` for the knee that actually caved. The shot-list seeds the **left** knee
   deliberately so this is unambiguous.

   **A deliberately partial-depth set is not a clean set.** On `squat_partial_side_001` (shot-list
   #19) every rep genuinely is `shallow_depth` and must be labelled as such. That clip exists to
   prove a partial rep still **counts** — the validity gate accepts it and it scores lower — not that
   it is fault-free. Labelling those reps `faults: []` turns every one of the detector's correct
   flags into a false accusation and depresses `shallow_depth` precision for a reason unrelated to
   detection quality. The same logic applies to any deliberately-seeded set: the seeded fault is
   present, so label it.
3. **Subject** — for multi-person clips, mark which person is the user.
4. **Sign-off** — set `labeler` and `pt_verified: true`. A golden case with a wrong "correct" label is
   worse than no case — it trains and tests toward the wrong behaviour — so PT sign-off is the gate.

A simple labeling spreadsheet (one row per rep) that exports to `labels.json` is enough to start; no
tool-building required for round one.

> **Blocked decision to resolve with the PT while they're here:** the lunge knee-safety rule
> (`front_knee_cave` / `front_knee_overextend` / xlsx `knee_past_toe` three-way conflict). Getting the
> PT to confirm the correct physical rule unblocks lunge's high-severity checks.
> Also settle the `medium` → `med` severity-token normalisation flagged in `EXERCISE_LIBRARY.md` §4.

---

## 8. Bake-off minimum (enough to *decide* a pose model)

You do **not** need the full matrix to pick a pose model. Directional minimum:

- 3 exercises × **2 views** (side + diagonal) × **1 lighting** (daylight) × **1 device** ×
  **3 sets** of ~10 reps → ~18 `normal` clips (mix clean + faulty).
- + the **3 negative clips** (`phantom_bench`, `phantom_empty`, `bystander`).
- + 1 partial-depth and 1 slow-tempo clip.
- + **4 recall-coverage sets** — one each seeding `elbow_flare`, `shallow_pushup`, `shallow_lunge`,
  and squat's `excess_torso_lean`. Added 2026-09-05: the 23 above give those four flags a **zero**
  recall denominator, so the report would show them with no positives at all — indistinguishable
  from "working" (`CODE_SPEC_MAP.md` §8, GAP 3).
- Each `normal`/`bystander` clip run through **all 3 pose models**.

That's ~27 clips — a weekend of recording + a labeling session — enough for Stage 2 to print a real
comparison table and choose. **Do this first.** `RECORDING_SHOTLIST.md` is the tick-list version.

## 9. Gate-grade set (enough to declare an exercise vision-live)

To actually pass an exercise's eval bar (`EXERCISE_LIBRARY.md` §5), grow to the coverage the harness
checks: **≥5 devices × 3 lighting**, ≥3 sets of 8–12 reps per cell, all 3 views, both fitness
extremes, and enough labeled faulty reps that per-flag precision/recall are statistically meaningful
(rule of thumb: ≥20–30 labeled instances of each high-severity fault). Build toward this over weeks;
sample real user sessions into it once there are users.

## 10. Checklist (round one)

- [ ] Consent process agreed; `.gitignore` blocks video/image files in `golden/`.
- [ ] Recording matrix for the **bake-off minimum** (§8) planned across the devices you have.
- [ ] Clean + deliberately-faulty + partial + slow `normal` clips recorded, reps counted aloud.
- [ ] The 3 negative clips (`phantom_bench`, `phantom_empty`, `bystander`) staged and recorded.
- [ ] Keypoints generated per pose model into `golden/poses/<model>/…`; **videos deleted/offline**.
- [ ] PT labels each clip → `labels.json`, faults from the exercise's own `error_id`s, `pt_verified: true`.
- [ ] `MANIFEST.json` updated; `python aggregate.py --golden golden/ --mode full` runs on real data.
- [ ] Lunge knee-rule + `medium`→`med` decisions captured while the PT is available.
