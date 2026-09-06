# CLEANROOM_NOTES.md

What this rebuild was, what the spec determined, what it did not, and how honest the
"clean room" actually is. Read this before comparing anything here to `kinetiq v4`.

---

## The experiment

**Input:** the `kinetiq v4` CLAUDE.md hierarchy, and nothing else —
root `CLAUDE.md` (76 lines) plus `backend/` (22), `evals/` (36), `frontend/` (31),
`skills/` (15). About 180 lines of prose.

**Output:** this repo — detector, harness, golden set, contracts, API, PWA, tests, CI.

**Question:** is a CLAUDE.md hierarchy a sufficient specification to rebuild from?

---

## Honesty about the "clean room"

This was **not hermetic**, and the claim should not be made stronger than it is.

- No v4 source file was read during generation. No implementation was copied.
- **But** the same session had earlier read several v4 files while preparing a deploy:
  `render.yaml`, `frontend/config.js`, `evals/gate0/prototype_api/Dockerfile`,
  `check_local.sh`, `set-api-url.ps1`, the head of `gate0-eval.yml`, `exercise_lib.py`'s
  function signatures, and `aggregate.py`'s printed report format.
- So the **infrastructure** files here are informed by having seen v4's. The **detector,
  scorers, contracts, fixtures, PWA and tests** are not — those were derived from the
  CLAUDE.md text and from working the problem.

Treat convergence on infra as weak evidence. Treat convergence on detector behaviour as
meaningful.

---

## What the spec pinned precisely

The CLAUDE.md hierarchy was far more prescriptive than its length suggests. It fixed:

- The module list, by name: `subject_lock`, `plausibility`, `rep_counter`, `faults`,
  `flag_hysteresis`, `geometry`, `keypoint_map`, `adapter.run_detector`.
- The scorer set: `rep_match`, `form_pr`, `phantom`, `subject_lock`, `view`.
- The wire frame shape, exactly:
  `{t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis]…]}]}`.
- Constant *names*: `GATE0_TARGET_ACCURACY`, `SUBJECT_LOCK_FLOOR`,
  `FORM_PRECISION_FLOOR_*`, `POSE_MODEL_CANDIDATES`, `PROTOTYPE_SESSION_MAX_FRAMES`.
- Load-bearing path arithmetic: `gate_config` reaching `parents[2]/backend`,
  `config.py` reaching `parents[3]/exercises`.
- Architectural invariants: privacy, one-detector-two-consumers, deterministic safety
  veto, config-as-single-source-of-truth, anti-phantom.
- Endpoint names, run commands, the PWA's file list, the cue word cap.

That is a lot of real constraint, and it is why the shape of this repo lands close to v4's.

---

## What the spec left open — the gaps that matter

Each of these had to be decided during the build. Each is a place where this repo and v4
can legitimately differ, and a candidate line to add to v4's CLAUDE.md.

### 1. Every numeric threshold
CLAUDE.md names no angle, ratio or floor — and explicitly says *never invent a threshold*
and *surface uncertain decisions as `needs_pt_confirmation`*. Both were honoured: every
contract here carries `status: needs_pt_confirmation` and a `threshold_provenance` string
saying the values were derived, not validated. **These are not v4's numbers and must not
be compared to them as if they were.**

### 2. Gate floor values
The floor *names* are specified; the values are not. The ones here (90% rep accuracy,
99% subject lock, 90/75/60% precision by severity) are plausible and internally ordered so
that a high-severity false positive costs most — but they are invented.

### 3. The 301-test count
Root CLAUDE.md states "301 backend tests" as a fact. It does not say what they test, so
the number is unreproducible from the spec. This repo has **118**. That gap is not a
shortfall to apologise for — it is the finding: *a count is not a specification.*

### 4. Fault check semantics
CLAUDE.md names no fault checks at all. `shallow_depth`, `hip_sag`, `knee_valgus`,
`elbow_flare`, `trunk_lean` and their geometry were all derived. v4's are near-certainly
different in detail.

### 5. Check scope
Nothing in the spec suggests some checks are per-frame and some per-rep. The build
discovered this the hard way (below). Worth adding to v4's `evals/CLAUDE.md`.

### 6. Whether pose z is used
The frame schema carries `z`, but no document says whether the detector reads it. It
turns out to be decisive (below).

### 7. Golden set contents
"Frozen keypoints + PT labels (currently synthetic fixtures)" — no clip list, no counts,
no fault coverage. The 13 clips here were designed from scratch.

---

## Bugs the build hit, and what they suggest for v4

These were found by the eval harness rejecting fixtures whose labels were authored
independently — which is the harness doing precisely its job.

**1. Depth checks latched on clean reps.**
`min_angle_above` ran per-frame, so during the descent of a *good* rep the running minimum
had not yet reached depth, and the check fired for 8 consecutive frames before the person
got there. `sustain_frames` made it stick. Fix: fault checks carry a **scope**; depth/ROM
checks are evaluated once, at rep close.
→ *Worth checking whether v4's depth checks have the same shape.*

**2. A 2D joint angle cannot count a head-on squat.**
With angles computed from x/y only, a front-view squat shows almost no bend at the knee —
the motion is along the camera axis. Rep counting returns zero. Fix: `joint_angle` and
`angle_from_vertical` use all three axes.
→ *If v4 computes angles in 2D, front-view rep counting is likely weak. Testable.*

**3. Knee valgus read forward knee travel as a cave.**
Comparing the knee against an interpolated hip–ankle line makes normal forward travel look
like lateral deviation. Fix: measure knee-vs-ankle in the frontal plane only, normalised by
hip width, plus a guard that returns *unjudgeable* when the hips project too close together
to see across (a side view).
→ *A valgus check without a view guard will produce side-view false positives.*

**4. The rep gate collided with the depth threshold.**
Both were 100°. A rep is only counted below the gate, so a "too shallow" rep at 118° was
never counted — and the fault existed but could never fire. Fix: the gate sits above the
fault threshold, and a test enforces the ordering for every contract.
→ *This one is cheap to check in v4 and would be invisible until a real shallow set.*

**5. A fixture can be wrong in a way that looks like a detector bug.**
The first fixtures used 840ms reps; `min_rep_ms` correctly rejected them as dither and
every clip scored zero. The fixture was unrealistic, not the detector. Fixed the fixture.

---

## Verified here

| Check | Result |
|---|---|
| `python -m unittest discover -s evals/gate0 -p "test_*.py"` | 118 tests, OK |
| `aggregate.py --mode full` | `Stage 0 gate: PASS`, exit 0 |
| `smoke_assess.py` | 3 reps, `knee_cave_left`, cue returned |

Per the anti-phantom rule: that is the whole of what has been verified. The Docker image
has **not** been built (no Docker on the build machine), nothing has been deployed, and no
human has been in front of a camera. All accuracy evidence is synthetic.

---

## How to use this repo

- **As a spec audit.** The "left open" list above is the actionable output. Each item is a
  candidate line for v4's CLAUDE.md.
- **As a bug checklist.** The five issues above are real and cheap to test for in v4.
- **Not as a detector.** v4's detector is eval-validated; this one is validated only
  against fixtures it was co-developed with. Do not swap it in.
