# VISION_ARCHITECTURE.md — Kinetiq v3

> The compound, on-device, open-source vision engine. How it works, which models, and how each stage
> closes a specific root cause from `../kinetiq-v2/VISION_ERROR_ANALYSIS.md`.
> Method backbone: *The Builder's Gita* Ch 30 (Compound AI Systems). Every model choice below is a
> candidate to be **decided by the eval bake-off in `EVAL_STRATEGY.md`**, not by this document's
> opinion (Ch 39: "model selection from religion into measurement").
> Last updated: 2026-08-30

---

## 1. The idea: a rulebook becomes a pipeline of specialists

v1/v2 was one deterministic function: `pose → angle thresholds → rep count + flags`. It failed because
that single function had to be, simultaneously, a person-detector, a subject-tracker, a rep-validator,
and a form-judge — and it was none of them. v3 splits that one overloaded function into a **compound
of small specialists**, each of which does one job well and can be tested and swapped independently.

This is Ch 30's reference architecture (Router → specialists → Generator → **Evaluator loop**) mapped
onto movement. Everything runs **on-device on keypoints** — no pixels leave the phone.

```
 CAMERA FRAME (stays on device)
        │
        ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ 1. PERSON DETECT + SUBJECT-LOCK        (fixes RC1)              │
 │    detect people → pick ONE (largest/most-central at start)    │
 │    → track that identity across frames; ignore everyone else   │
 └───────────────┬────────────────────────────────────────────────┘
                 ▼   (only the locked subject's box)
 ┌────────────────────────────────────────────────────────────────┐
 │ 2. POSE ESTIMATION                     (fixes RC5, part)        │
 │    OSS pose model on the locked crop → keypoints + visibility  │
 └───────────────┬────────────────────────────────────────────────┘
                 ▼   (keypoint time-series + derived features)
 ┌────────────────────────────────────────────────────────────────┐
 │ 3. REP-VALIDITY GATE                   (fixes RC2)              │
 │    is this a plausible human doing a plausible rep?            │
 │    human-pose plausibility · visibility · phase trajectory ·   │
 │    tempo sanity → a bench / bystander / jitter cannot pass     │
 └───────────────┬────────────────────────────────────────────────┘
                 ▼
 ┌───────────────────────────┐   ┌────────────────────────────────┐
 │ 4. REP COUNTER (hybrid)   │   │ 5. FORM MODEL (learned)        │
 │  smoothed FSM + optional  │   │  temporal net over keypoint    │
 │  learned boundary model   │   │  features → per-flag score,    │
 │  tempo-tolerant (RC4/RC6) │   │  fitness-graded (RC3/RC4)      │
 └─────────────┬─────────────┘   └───────────────┬────────────────┘
               │                                 ▼
               │                  ┌────────────────────────────────┐
               │                  │ 5b. DETERMINISTIC SAFETY VETO  │
               │                  │  hard rules can overrule the   │
               │                  │  model; model cannot clear a   │
               │                  │  safety flag or fake a rep     │
               │                  └───────────────┬────────────────┘
               └─────────────┬───────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ 6. COACHING GENERATOR (off hot path)  — cues, set summaries     │
 │    deterministic cue on hot path; cheap/strong model async (v2) │
 └───────────────┬────────────────────────────────────────────────┘
                 ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ 7. EVALUATOR  (Ch 30 comp.6 + Ch 39 loop)                      │
 │    every stage's output is logged + scored against the golden   │
 │    set; gates CI; monitors drift. See EVAL_STRATEGY.md          │
 └────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage by stage

### Stage 1 — Person detect + subject-lock (fixes RC1: skeleton jumps to bystanders)
**Job:** find all people, choose the user once, and keep tracking *that* person.
- At session start, pick the subject deterministically (largest bounding box / most central / closest
  to a "stand here" marker). Persist that identity with a lightweight tracker so a brighter or closer
  bystander cannot steal the skeleton mid-set.
- If the locked subject is lost (occlusion, walks out of frame), **pause** — don't silently retarget.
- OSS candidates: **MoveNet MultiPose** (multi-person, on-device, TF.js) or a **YOLO-pose (v8/11-n)**
  detector, paired with a simple **IoU/OC-SORT/ByteTrack**-style tracker. Choice decided by eval.
- Why this first: it is the precondition for everything. Pose and form on the wrong body are garbage.

### Stage 2 — Pose estimation (fixes RC5, part: view/quality sensitivity)
**Job:** best on-device keypoints for the locked subject.
- Candidates, to be **bake-offed on the golden set** (Ch 39): **MediaPipe BlazePose** (33 kp, world
  landmarks give pseudo-3D, strong on-device), **MoveNet Thunder** (17 kp, accurate, fast),
  **RTMPose** (very accurate, CPU-friendly — the model Good-GYM settled on). Keep 33-kp where possible
  for richer features; document the COCO-17 ↔ BlazePose-33 mapping so features are model-agnostic.
- 3D where available (BlazePose world landmarks) reduces the 2D-projection errors behind RC5 (front
  under-count, side over-count) because depth stops masquerading as foreshortening.
- Output: keypoints + per-landmark visibility, fed forward as a **model-agnostic feature vector**
  (joint angles, symmetry, tempo, ROM) so the pose model can be swapped without touching downstream.

### Stage 3 — Rep-validity gate (fixes RC2: bench counted 6 reps)
**Job:** veto anything that isn't a real human doing a real rep, *before* it can count.
- **Human-pose plausibility:** joint lengths/ratios and angles within human ranges; enough
  high-visibility landmarks. A bench has no plausible 33-point skeleton — it fails here.
- **Subject check:** the motion belongs to the locked identity from Stage 1.
- **Phase-trajectory check:** the movement actually traced the exercise's expected phase path (not a
  random sweep), within a plausible tempo band.
- This is the single most important new component — three of the six root causes trace to its absence.

### Stage 4 — Rep counter, hybrid (fixes RC4/RC6: slow reps missed, deep-only, over/under-count)
**Job:** count real reps robustly across tempo and view.
- **Deterministic FSM baseline** (v2's phase machine) **plus temporal smoothing** — median filter +
  hysteresis + **tempo tolerance** (a slow, smooth rep must still register a clean transition; a
  bench-swing must not double-count).
- **Optional learned boundary model:** a small temporal net that classifies phase / detects rep
  boundaries from the keypoint series — turned on only if it beats the smoothed FSM on the golden set.
- Depth becomes **graded, not binary** (fixes the "only deep squats count" complaint): partial reps
  count with a lower form score rather than not counting at all, graded by fitness level.

### Stage 5 — Learned form model (fixes RC3/RC4: false negatives, false positives, strictness)
**Job:** judge form from data, not from a spreadsheet guess.
- A **small temporal model** (1D-CNN / TCN / GRU) — or, to start, gradient-boosted trees on per-rep
  aggregate features — over the keypoint feature series, producing a per-flag probability and an
  overall form score, **graded by fitness level** (beginner thresholds relaxed).
- Trained on the **same labeled sessions that form the golden eval set** (see §3) — the dataset is one
  asset serving both training and evaluation.
- Catches error modes v2 never hand-coded (rounded back, heels rising, butt wink) and **calibrates**
  thresholds from real distributions, killing the hip-sag false positive.
- **Advisory → authoritative migration is eval-gated** (Ch 39 + v2 ADR-100): it ships as authoritative
  for a flag only once its precision/recall clears the bar for that flag; until then it's advisory and
  the deterministic rule leads.

### Stage 5b — Deterministic safety veto (invariant)
Hard safety rules (knee cave, lumbar flexion, unsafe depth) can **overrule** the learned model; the
model can never **clear** a safety flag nor create a rep the validity gate rejected. Confident model
nonsense must be vetoable.

### Stage 6 — Coaching generator (unchanged from v2 plan)
Deterministic cue on the hot path; set summaries / re-engagement via the tiered cheap/strong models,
off the hot path, health-context- and memory-aware. Positive-before-correction, non-medical, graded.

### Stage 7 — Evaluator (the thing that makes it trustworthy)
Every stage logs its inputs/outputs; the eval harness scores them against the golden set, gates CI,
and monitors drift. This is Ch 30's Evaluator component made permanent by Ch 39's loop. Detailed in
`EVAL_STRATEGY.md`.

---

## 3. The dataset is one asset (labels train AND gate)

The recorded, human/PT-labeled sessions are **simultaneously** the golden eval set (Ch 39) *and* the
training data for the Stage-4/5 learned models. This is the elegant loop and the reusable core:

```
 record sessions ──► human/PT labels (good/fault per rep, per exercise)
        │                        │
        ▼                        ▼
   TRAIN Stage 4/5 models   FREEZE golden eval set
        │                        │
        └──────► every model change is GATED by the frozen set ◄────┘
```

Every field bug becomes a labeled case, which both **trains the model away from the error** and
**gates its return forever**. This is the mechanism that answers "why will v3 be more accurate than
v1/v2?": not a bigger model — a measured, ever-growing labeled distribution the models are fit to and
tested against.

---

## 4. Why compound-of-small beats one-big-model here (Ch 30)

- **Testability:** each specialist has its own eval; a regression is localised to a stage, not a
  monolith.
- **Swappability:** the pose model can be replaced (MediaPipe → RTMPose) without touching the form
  model, because features are model-agnostic.
- **On-device + privacy:** small specialists run in the browser/phone; no pixels leave. A big hosted
  VLM would break the invariant and the latency budget.
- **Cost/latency:** the hot path stays cheap and deterministic; learned models run where they earn it.
- **Auditability:** a deterministic safety layer can always veto a learned layer.

---

## 5. Open questions for the bake-off (decided by eval, not here)

- Which pose model wins on *our* golden set across accuracy × latency × device spread? (BlazePose vs
  MoveNet Thunder vs RTMPose.)
- Multi-person detector+tracker choice for subject-lock (MoveNet MultiPose vs YOLO-pose+ByteTrack).
- Does the learned rep-boundary model (Stage 4) beat the smoothed FSM enough to justify its weight?
- Minimum labeled-rep count per exercise before the Stage-5 form model clears advisory→authoritative.
- 2D-only vs BlazePose world-landmark 3D for the view-dependence (RC5) fix.

Each is a table to fill in, per Ch 39 — not an argument to have.
