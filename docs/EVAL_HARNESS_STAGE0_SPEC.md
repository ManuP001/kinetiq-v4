# EVAL_HARNESS_STAGE0_SPEC.md — Kinetiq v3

> The first buildable piece of Stage 0 (`ROADMAP.md`). A concrete spec for the labels schema and the
> extension of the existing `../kinetiq-v2/evals/gate0/aggregate.py`, so the eval harness can score not
> just rep-count accuracy (what it does today) but **form precision/recall, subject-lock, and
> no-phantom-reps** — the dimensions v1/v2 never measured and that failed in the gym.
> Implements `EVAL_STRATEGY.md` steps 1–4. Code lives in `kinetiq-v2/evals/gate0/`; this doc is the spec.
> Last updated: 2026-08-30

---

## 1. Goal & what already exists

**Today** (`kinetiq-v2/evals/gate0/aggregate.py`): ingests per-set device exports
`{exercise, actual, detected, device, lighting}`, computes weighted rep accuracy
(`1 − Σ|detected−actual| / Σactual`) per exercise vs the 90% bar, and prints device×lighting coverage.
Rep-count only.

**Stage 0 adds** the *golden set* — frozen, PT-verified, per-rep labels — and the scorers that turn it
into the five missing numbers: **no-phantom-reps, subject-lock, form precision, form recall, view
robustness**. The existing rep-count path is kept and unchanged (backward compatible).

Design rule (from the v2 threshold-drift lesson): flag lists and severities are **read from the
exercise library at runtime** via the existing `config.load_exercise_library()`, never re-hardcoded in
the harness. One source of truth.

---

## 2. Two data tiers (keep them separate)

| Tier | What | Committed? | Scores |
|---|---|---|---|
| **`data/`** (exists) | Raw device exports, rep-count-only, `navigator.userAgent` inside | **No** (gitignored — contains device strings) | rep-count accuracy, device×lighting coverage |
| **`golden/`** (new) | Frozen, PT-labeled clips: **keypoints + labels only, no video** | **Yes** (it's the yardstick; keypoints are privacy-safe derived data) | everything: rep-count, phantom, subject-lock, form P/R, view |

**Privacy invariant holds:** the golden set stores **keypoint time-series, never pixels.** Video is
used by the PT to label, then discarded/kept off-repo; only keypoints + labels are frozen and committed.

---

## 3. Directory layout (extends `kinetiq-v2/evals/gate0/`)

```
kinetiq-v2/evals/gate0/
  aggregate.py                 # extended (see §7)
  scorers/                     # NEW — one scorer per dimension, each unit-testable
    rep_match.py               # align detected reps ↔ ground-truth reps (§6)
    form_pr.py                 # per-flag precision/recall
    phantom.py                 # no-phantom-reps
    subject_lock.py            # subject-lock accuracy
    view.py                    # per-view rep-accuracy spread
  golden/                      # NEW frozen golden set (committed, PT-verified)
    MANIFEST.json              # index of every clip (§4)
    <clip_id>.keypoints.jsonl  # frozen INPUT: one JSON pose frame per line
    <clip_id>.labels.json      # frozen TRUTH: per-rep faults, subject, view (§5)
  data/                        # raw device exports (gitignored) — unchanged
  README.md                    # updated with the golden-set workflow
```

---

## 4. `golden/MANIFEST.json` — the index

One row per clip. Lets the harness enumerate the frozen set and slice by exercise/clip_type/view.

```json
{
  "schema_version": 1,
  "golden_version": "v3.0",
  "clips": [
    { "clip_id": "pushup_good_side_001", "exercise": "pushup", "clip_type": "normal",
      "view": "side", "lighting": "indoor_evening", "fitness_level": "intermediate",
      "num_people_in_frame": 1, "labeler": "PT-AR", "pt_verified": true },
    { "clip_id": "squat_bench_phantom_001", "exercise": "squat", "clip_type": "phantom_bench",
      "view": "diagonal", "lighting": "daylight", "num_people_in_frame": 0,
      "labeler": "PT-AR", "pt_verified": true }
  ]
}
```

`clip_type ∈ { normal, phantom_bench, phantom_empty, bystander }`
`view ∈ { front, side, diagonal }`, `lighting ∈ { daylight, indoor_evening, dim_room }` (matches the
existing `aggregate.py` `LIGHTING_CONDITIONS`).

---

## 5. `<clip_id>.labels.json` — the frozen ground truth

```json
{
  "schema_version": 1,
  "clip_id": "pushup_good_side_001",
  "exercise": "pushup",
  "clip_type": "normal",
  "view": "side",
  "lighting": "indoor_evening",
  "fitness_level": "intermediate",
  "subject": { "expected": "user", "num_people_in_frame": 1,
               "subject_track_id": 0 },
  "ground_truth": {
    "actual_reps": 10,
    "reps": [
      { "idx": 1, "faults": [] },
      { "idx": 2, "faults": ["hip_sag"] },
      { "idx": 3, "faults": [] }
    ]
  }
}
```

Rules:
- `faults` values MUST be `error_id`s that exist in that exercise's library entry (validated at load).
- **Phantom clips** (`phantom_bench`, `phantom_empty`): `ground_truth.actual_reps = 0`, `reps = []` —
  they prove the detector produces **zero** reps.
- **Bystander clips are NOT zero-rep.** The user *is* exercising: `actual_reps` = the user's real
  count and `reps[]` are labeled normally (with faults). A bystander clip proves the skeleton **stays
  on the user** (subject-lock) *while still counting the user's reps*, despite other people in frame.
  Only `phantom_*` clips are zero-rep.
- `subject_track_id` is the ground-truth "which person is the user" for subject-lock scoring.

### `<clip_id>.keypoints.jsonl` — the frozen input (one line per frame)

```
{"t_ms":0,  "pose_model":"blazepose_33", "people":[{"track_id":0,"kp":[[x,y,z,vis], ...],"box":[x,y,w,h]}]}
{"t_ms":33, "pose_model":"blazepose_33", "people":[{"track_id":0,"kp":[...]},{"track_id":1,"kp":[...]}]}
```

- `pose_model` names the model that produced the frame (e.g. `blazepose_33`, `movenet_17`). `kp` is a
  **variable-length** array of `[x, y, z, vis]` landmarks whose length is set by `pose_model` (33 for
  BlazePose, 17 for MoveNet) — **not fixed at 33**. The harness maps whichever model to a common
  feature set via the keypoint mapping (`VISION_ARCHITECTURE.md` §2). `vis` = visibility.
- **`z` is `null`** for 2D-only pose models (e.g. MoveNet → `[x, y, null, vis]`); only 3D models (e.g.
  BlazePose world landmarks) populate it. Scorers and features must treat `z` as optional.
- `people` may hold multiple detections (bystander/multi-person clips) — this is what subject-lock is
  scored against.
- Freezing keypoints (not video) is what makes evals **reproducible**: any candidate detector/model
  can be re-run over the identical input (Stage-2 bake-offs, Ch 39 before/after).

### `<clip_id>.detected.json` — produced by the harness, NOT frozen

The harness runs the detector-under-test over `keypoints.jsonl` to produce this; it is regenerated
every run, never committed. Interim bootstrap: until the detector can run offline, capture the demo's
live per-rep output during recording into this shape.

```json
{ "clip_id": "pushup_good_side_001", "detector_version": "demo2@<sha>",
  "detected_reps": 11,
  "reps": [ { "idx": 1, "flags": [], "form_score": 8.4 },
            { "idx": 2, "flags": ["hip_sag"], "form_score": 6.1 } ],
  "subject_lock": { "frames_total": 900, "frames_on_expected_subject": 882 },
  "coaching_cues": [ { "rep_idx": 2, "text": "Good depth — lift the hips a touch" } ] }
```

Detector adapter interface (what Stage 1+ implements):
`run_detector(keypoints_stream, exercise_id, config) -> DetectedClip`

---

## 6. The rep-matching algorithm (the crux of form P/R)

To compute per-flag precision/recall you must decide **which detected rep corresponds to which true
rep**, because counts can differ (phantom or missed reps). Reps are an ordered sequence, so align them
monotonically and minimise index displacement.

```
match_reps(gt_reps, det_reps) -> list[(gt|None, det|None)]
  # Needleman–Wunsch-style monotonic alignment on rep order.
  # cost(pair)      = 0        (align a true rep to a detected rep)
  # cost(gap in det)= 1        (a true rep with no detected rep  -> MISSED)
  # cost(gap in gt) = 1        (a detected rep with no true rep  -> PHANTOM)
  # Return the min-cost alignment as (gt_rep|None, det_rep|None) pairs, in order.
```

Then, per exercise, per flag `f`, over all matched pairs:

```
matched pair (gt, det):
  TP(f) += (f in gt.faults) and (f in det.flags)          # correctly flagged a real fault
  FP(f) += (f not in gt.faults) and (f in det.flags)      # FALSE ACCUSATION on a good rep
  FN(f) += (f in gt.faults) and (f not in det.flags)      # MISSED a real fault
phantom det rep (gt=None): every flag it carries -> FP(f)  # accusing a rep that didn't happen
missed gt rep (det=None):  every fault it had   -> FN(f)   # never got the chance to catch it

precision(f) = TP / (TP + FP)      # "when we flag, are we right?"  -> guards false accusations
recall(f)    = TP / (TP + FN)      # "of real faults, how many caught?" -> guards missed faults
```

Aggregate per-flag, then gate each flag against **its severity's floors** (§8): the high/med **precision**
floors (`FORM_PRECISION_FLOOR_HIGH_SEV` / `FORM_PRECISION_FLOOR_MED_SEV`) and the high/med **recall**
floors (`FORM_RECALL_FLOOR_HIGH_SEV` / `FORM_RECALL_FLOOR_MED_SEV`). High-severity carries the strictest
precision floor but the *most lenient* recall floor — precision-first: never accuse a good rep, tolerate
some misses. Low-severity is advisory/logged with no enforced floor. `score_form_pr` (and
`scorers/form_pr.py`) must look up each fault's severity from the exercise library and apply the
**matching** floor, not one flat recall bar. Document the two edge choices above (phantom-flag→FP,
missed-fault→FN) in the code — they are deliberate.

---

## 7. How the scoring layer is structured

> **Amended 2026-09-05** to describe the structure as built. This section previously specified a
> layer of thin wrapper functions inside `aggregate.py` re-exporting `scorers/*.py`. That layer was
> never built and is not wanted: it duplicates §3's directory contract for no behavioural gain. The
> code is the reference; ADR-301 records the decision and the reasoning.

`aggregate.py` keeps every existing function (`load_sessions`, `weighted_accuracy`,
`print_accuracy_verdict`, `print_matrix_coverage`, `parse_device_label`) and calls the scorers
**directly** — each scorer is implemented exactly once, in its own module, and nothing re-exports it.

### Golden loading — `golden_loader.py`

Loading and validating the frozen set is a separate concern from reporting on it, so it lives in its
own module rather than in `aggregate.py`:

```python
def load_golden(golden_dir: Path) -> List[GoldenClip]
    # reads MANIFEST.json, each clip's labels.json, recomputes detected.json via run_detector
    # for any Stage-1-scoped exercise; validates fault ids against the exercise library;
    # raises GoldenSetError loudly on an unknown flag / missing file.

def validate_frame_schema(frame: Dict[str, Any], context: str) -> None
def load_golden_poses(golden_dir: Path, pose_model: str) -> List[GoldenClip]   # Stage-2 bake-off
def load_capture_meta(golden_dir: Path, pose_model: str, clip_id: str) -> Optional[Dict[str, Any]]
```

`validate_frame_schema` is deliberately public: **`prototype_api` imports the same function**, so the
live API and the offline harness enforce byte-identical frame rules rather than two drifting copies
(the same one-definition-many-consumers rule as `run_detector`).

### Scorers — one module per dimension, in `scorers/`

Per §3. Each is independently unit-testable and imported directly by `aggregate.py`:

```python
# scorers/rep_match.py
def match_reps(gt_reps, det_reps) -> list[MatchPair]        # §6's monotonic alignment

# scorers/form_pr.py
def score_clip_form_pr(gt_reps, det_reps) -> dict[str, PR]  # ONE clip -> flag -> PR(tp, fp, fn)
def aggregate_form_pr(clips) -> dict[str, dict[str, PR]]    # pooled: exercise -> flag -> PR
def insufficient_evidence_counts(clips) -> Dict[str, int]
def gate_flag(pr: PR, severity: str) -> FlagGateResult      # applies the severity-matched floors
def gate_form_pr(...)

# scorers/phantom.py
def score_phantom(clips) -> PhantomResult                   # {phantom_bench, phantom_empty} ONLY -- never bystander

# scorers/subject_lock.py
def score_subject_lock(clips) -> SubjectLockResult          # per_clip: clip_id -> fraction locked, + mean

# scorers/view.py
def score_view_robustness(clips) -> Dict[str, ViewResult]   # exercise -> accuracy_by_view + gap
```

Two naming/typing notes, so a reader diffing this section against the code finds no surprises:

- **`aggregate_form_pr`, not `score_form_pr`.** The pair reads correctly together:
  `score_clip_form_pr` scores a single clip, `aggregate_form_pr` pools across clips. A single
  `score_form_pr` would be ambiguous about which it did.
- **Typed results, not bare `float`/`dict`.** `score_subject_lock` returns a `SubjectLockResult`
  (per-clip fractions plus the mean) rather than a lone mean, and `score_view_robustness` returns
  typed `ViewResult`s. This is what lets the report **name the failing clip** instead of printing
  only an aggregate — which §4's "legible to a non-engineer" requirement needs, since "subject-lock
  0.97" is not actionable but "`pushup_bystander_001` 0.97" is.

### Report + gate — `aggregate.py`

```python
def check_coaching_cue_assertions(clips) -> CueAssertionResult   # §10's Stage-0 cue stub
def print_stage0_report(clips, mode: str) -> bool                # legible table; returns all_pass
```

`print_stage0_report` takes `mode` so one function serves both depths, matching the `--mode` flag
below.

Wire into `main()` with a mode flag:

```
python aggregate.py --data data/                    # existing rep-count path (unchanged)
python aggregate.py --golden golden/ --mode fast    # assertions + rep-acc on golden subset (CI push)
python aggregate.py --golden golden/ --mode full    # + form P/R + subject-lock + view (CI merge/nightly)
```

`main()` exits non-zero if **any** gate dimension is below its floor. The printed report is a table a
non-engineer can read (accuracy by exercise, per-flag precision/recall, worst offenders, phantom/lock
pass-fail) — Ch 39's "legible to a human."

---

## 8. Gate thresholds (defined in `kinetiq-v2/backend/app/core/config.py`)

Single source of truth, imported by the harness (as `GATE0_TARGET_ACCURACY` already is). These now
exist in `config.py`:

```python
# --- Stage 0 eval gate floors (single source of truth: config.py) ---
GATE0_TARGET_ACCURACY            = 0.90   # exists
PHANTOM_REPS_MUST_BE_ZERO        = True   # any rep on a phantom/empty clip -> hard fail
SUBJECT_LOCK_FLOOR               = 0.99   # fraction of frames tracking the right person
FORM_PRECISION_FLOOR_HIGH_SEV    = 0.90   # high-severity flags: never accuse a good rep
FORM_PRECISION_FLOOR_MED_SEV     = 0.75
FORM_RECALL_FLOOR_HIGH_SEV       = 0.60   # precision-first: high-sev tolerates MORE misses
FORM_RECALL_FLOOR_MED_SEV        = 0.70
VIEW_ACC_MAX_GAP                 = 0.10   # max rep-acc spread across front/side/diagonal
# low-severity flags: advisory / logged only — no enforced precision or recall floor.
```

Recall is split by severity so the harness applies the **matching** floor per fault (via §6's
`score_form_pr`), never one flat bar. Values are chosen "like an adult" (Ch 39): a live gate that
catches real drops beats a perfect gate everyone disables. Tune as the golden set stabilises.

---

## 9. Seed the golden set now (the two field bugs become cases #1 and #2)

Minimum viable golden set to stand the gate up — record + PT-label these first:

| clip_id | clip_type | Proves | Gate |
|---|---|---|---|
| `squat_bench_phantom_001` | phantom_bench | bench → **0 reps** | phantom |
| `pushup_good_side_00x` (×5) | normal, all clean | hip_sag **precision** (no false accusation) | form P |
| `squat_badform_00x` (×5) | normal, seeded faults | fault **recall** (no misses) | form R |
| `pushup_bystander_001` | bystander (2 people) | skeleton stays on user | subject-lock |
| `squat_partial_00x` | normal, partial depth | partial reps **counted** (graded) | rep-count |
| `pushup_slow_00x` | normal, 3-0-1-0 tempo | slow reps counted | rep-count |
| `squat_{front,side,diag}_001` | normal, same set 3 views | view robustness | view |

Cases #1 (bench) and #2 (hip-sag) are the exact gym failures — now permanent tests that can never
silently return.

---

## 10. CI wiring (Step 4 of the eval-driven loop)

```
on: pull_request
  - lint
  - unit tests  (incl. scorers/*.py unit tests over tiny synthetic clips)
  - FAST eval:  python aggregate.py --golden golden/ --mode fast   # seconds
on: merge to main / nightly
  - FULL eval:  python aggregate.py --golden golden/ --mode full   # + form P/R + judge
  - upload the report as a build artifact
Block the merge if the harness exits non-zero.
```

The coaching-cue **LLM judge** (`EVAL_STRATEGY.md` §2) is stubbed in Stage 0 — schema field + cheap
assertions (cue length ≤ 8 words, no medical terms). The calibrated LLM judge lands with Stage 6.

---

## 11. Build checklist (definition of done for this piece)

> Status audited 2026-09-05 against the code — see `CODE_SPEC_MAP.md` §3 for the file-by-file
> evidence. Ticks below are verified, not assumed.

- [x] `scorers/rep_match.py` + unit tests (equal counts, phantom, missed, empty).
- [x] `scorers/form_pr.py`, `phantom.py`, `subject_lock.py`, `view.py` + unit tests on synthetic clips.
      *(Implemented in `scorers/` and called directly from `aggregate.py` — §7 describes this
      structure as of 2026-09-05; ADR-301.)*
- [x] `golden/` schema validator (fault ids checked against the exercise library; **every fault has a
      `severity ∈ {high,med,low}`** — `EXERCISE_LIBRARY.md` §4). *(`golden_loader.py` +
      `exercise_lib.py::load_fault_severities`, which raises on a missing severity.)*
- [x] `aggregate.py` extended with `--golden/--mode`, backward compatible with `--data`.
- [x] Gate floors **defined** in `config.py` (incl. the severity-split `FORM_RECALL_FLOOR_HIGH_SEV` /
      `_MED_SEV`) **and imported, never restated** — verified by search: zero duplicated floor literals
      anywhere in the harness. All reads go through `gate_config.py`, the single import point.
- [x] Write and commit the **COCO-17 ↔ BlazePose-33 keypoint mapping** referenced in
      `VISION_ARCHITECTURE.md` §2. *(`detector/keypoint_map.py`'s `POSE_MODEL_LANDMARKS`; Stage 2
      extended it to every bake-off candidate.)*
- [ ] Seed golden set (§9) recorded, PT-verified, committed (keypoints + labels only).
      **Still open — synthetic fixtures only.** This is the GATE G-REAL critical path
      (`GOLDEN_SET_PROTOCOL.md`).
- [~] CI runs fast gate on push, full gate on merge; report is human-readable.
      **Pushed 2026-09-05, not yet blocking.** `.github/workflows/gate0-eval.yml` implements this
      section's shape (fast gate on push/PR, full gate on merge/nightly, report uploaded) and the
      report is human-readable. It had never run — the repo was 68 commits ahead of `origin/main` —
      until `main` was pushed, which triggers its first run. Two things remain: **branch protection
      with these jobs as required status checks** (a dashboard setting) is what actually makes the
      gate *block* a merge, and the workflow is still self-described as a DRAFT (it pins Python 3.11
      against local 3.13). See `CODE_SPEC_MAP.md` decision #4.
- [x] `README.md` updated with the record→label→freeze→score workflow. *(`evals/gate0/README.md`.)*

## 12. Deliberately deferred (not Stage 0)

- Re-running detection offline over frozen keypoints (needs the Stage-1 detector adapter) — Stage 0 may
  bootstrap with live-captured `detected.json`.
- The calibrated LLM-as-judge for cue quality — Stage 6.
- Drift scheduling — Stage 6 (the schema and scorers here are what the drift job will reuse).
