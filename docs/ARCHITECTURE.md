# ARCHITECTURE.md — Kinetiq v3 (ADR log)

> Architecture Decision Records for the v3 build. v2 ADRs (100–110) live in
> `../kinetiq-v2/ARCHITECTURE.md`; v3 ADRs are numbered from 300 to avoid collision. Per `CLAUDE.md`
> §6, every decision that departs from the governing docs is recorded here.
> `CODE_SPEC_MAP.md` is the section-by-section audit of code against spec; this log records the
> *decisions* that audit surfaced.
> Last updated: 2026-09-05

Earlier v3 decisions already embodied in the specs (subject-lock, rep-validity gating, field-data-
overrides-the-spreadsheet, the severity taxonomy) should be back-filled as ADRs when convenient; this
log starts with the first one that corrects a live inconsistency found during the build.

---

## ADR-300 — Pose-stage candidates must yield *all* people in frame (subject-lock precondition)

**Status:** Accepted · 2026-09-01
**Relates to:** VISION_ARCHITECTURE.md Stage 1 (subject-lock) & Stage 2 (bake-off); CHANGELOG 0.4.0
(Stage 1), 0.5.0 (Stage 2); `POSE_MODEL_CANDIDATES` in `../kinetiq-v2/backend/app/core/config.py`.

### Context
Stage 1 built **subject-lock** (RC1): pick one user when several people are in frame and track that
identity, so a bystander can't steal the skeleton. Subject-lock is only meaningful if the stage feeding
it presents **multiple candidate people per frame**.

While building the Stage-2 bake-off, we found the candidate registry lists **MoveNet SinglePose
Thunder** (`movenet_17`), which returns exactly **one** pose and cannot see multiple people — so on
that candidate, subject-lock has nothing to choose among and RC1 silently no-ops. The same trap
applies more widely than first noticed: **MediaPipe BlazePose is also single-person by default**, so
`blazepose_33` has the identical limitation unless configured/replaced for multi-person. Only
`rtmpose_halpe26` is inherently multi-person, because it is **top-down** — it already assumes a person
detector produces boxes and runs pose per box.

So "which pose model?" is really "which **detection + pose** stack?" — and comparing a single-person
model against a multi-person one on subject-lock is not like-for-like. VISION_ARCHITECTURE.md Stage 1
already anticipated this ("MoveNet **MultiPose** or YOLO-pose + tracker"); the registry drifted from it.

### Decision
1. The pipeline has an explicit **person-detection stage** ahead of (or fused into) pose. Its job is to
   yield all people per frame as candidate boxes/tracks; subject-lock selects one from them.
2. **Every bake-off candidate must be configured to produce all people in frame**, via one of:
   - a natively multi-person pose model (e.g. **MoveNet MultiPose**, or **MediaPipe Tasks
     PoseLandmarker with `num_poses > 1`**), or
   - a **top-down** pose model run per detected box (e.g. **RTMPose + a person detector** such as
     RTMDet/YOLO).
3. `POSE_MODEL_CANDIDATES` gains explicit fields recording each candidate's strategy, so the harness
   compares like-for-like and no candidate is silently single-person:
   - `multi_person: bool`
   - `person_detector: str | null` (the detector paired with a top-down pose model; `null` for a
     natively multi-person model)
   - `multi_person_config` (e.g. `num_poses` for MediaPipe Tasks; the MoveNet MultiPose variant)
4. Any candidate that cannot yield multiple people is **out of the bake-off** (or must be paired with a
   detector before it re-enters), because it cannot satisfy RC1.

### Consequences
- The registry entries change: `movenet_17` → **MoveNet MultiPose** (or dropped); `blazepose_33` →
  MediaPipe Tasks PoseLandmarker configured for multiple poses; `rtmpose_halpe26` gains its explicit
  `person_detector`. The capture adapters (Stage 2) must emit **all** detected people into
  `keypoints.jsonl` `people[]` (the schema already supports it), not just the top-1.
- Latency/size comparisons must include the **detector's** cost for top-down stacks — a top-down stack
  is detector + pose, not pose alone. The bake-off table should reflect the full stack.
- Slightly more work per candidate, but it's the only way the bake-off answers the real question:
  which stack counts reps accurately **and** locks onto the right person.

### Alternatives considered
- **Keep single-person pose, drop subject-lock.** Rejected — subject-lock is the RC1 fix; the bench /
  bystander failures were half the reason for v3.
- **Only ever use one multi-person model, skip the bake-off.** Rejected — model choice is supposed to
  be measured, not assumed (Ch 39); the bake-off stands, just with like-for-like multi-person configs.

### Follow-ups
- Update `POSE_MODEL_CANDIDATES` and the capture adapters to emit all people (part of the Tier-1
  capture-adapter live-test work, `PARALLEL_PLAN.md`).
- Add a golden clip with 2+ people to the bake-off set so subject-lock is actually exercised per
  candidate (the shot-list's `pushup_bystander_diag_001` covers this once recorded).

---

## ADR-301 — The Stage-0 scorers live in `scorers/`, not as wrappers in `aggregate.py`

**Status:** Accepted · 2026-09-05 · **Resolved 2026-09-05 — spec amended to match the code**
**Relates to:** `EVAL_HARNESS_STAGE0_SPEC.md` §3 (directory layout) vs §7 (functions to add);
`CODE_SPEC_MAP.md` §2–§3, decision #5 (now closed).

### Context
The Stage-0 spec describes the scoring layer twice, and the two descriptions don't quite agree:

- **§3** defines `scorers/` as "one scorer per dimension, each unit-testable" — `rep_match.py`,
  `form_pr.py`, `phantom.py`, `subject_lock.py`, `view.py`.
- **§7** says to add `score_form_pr` / `score_phantom` / `score_subject_lock` /
  `score_view_robustness` **to `aggregate.py`**, as "thin wrappers over `scorers/*.py`", plus
  `load_golden` there too.

Read literally, §7 asks for a second layer of pass-through functions whose only job is to re-export
what `scorers/*.py` already provides.

### Decision
Implement each scorer **once**, in its own `scorers/` module (satisfying §3), and have `aggregate.py`
call those directly. Do not build §7's wrapper layer. Two consequences worth naming explicitly:

1. `load_golden` lives in `golden_loader.py` rather than `aggregate.py` — loading and validating the
   frozen set is a distinct concern from reporting on it, and `prototype_api` reuses
   `validate_frame_schema` from that same module (one schema validator, two consumers).
2. One name differs from §7: `form_pr.py` exposes **`aggregate_form_pr`**, not `score_form_pr` —
   `score_clip_form_pr` scores a single clip and `aggregate_form_pr` pools across clips, so the pair
   reads correctly together where a single `score_form_pr` would be ambiguous.

Two spec'd return types are also **refined rather than narrowed**: §7 types `score_subject_lock` as
`-> float`; the code returns a `SubjectLockResult` (mean *plus* per-clip detail) so the report can
name the clip that failed, which §7's own "legible to a non-engineer" requirement needs. Same for
`score_view_robustness` returning typed `ViewResult`s instead of bare dicts.

### Consequences
- No behavioural difference; this is structure and naming only. 290 tests and
  `aggregate.py --mode full` are green either way.
- `EVAL_HARNESS_STAGE0_SPEC.md` §7's function list is now **descriptive of an intent** the code meets
  differently, not a literal contract. Anyone diffing §7 against the code will find the wrapper layer
  missing — hence this ADR, and the entry in `CODE_SPEC_MAP.md`.
- **Not unilaterally "fixed" in either direction.** Renaming `aggregate_form_pr` → `score_form_pr` and
  adding wrappers is a mechanical change with real regression surface and no behavioural gain;
  amending §7 edits the spec to match code, which the docs-are-truth rule reserves for a human. The
  disagreement was listed as open decision #5 in `CODE_SPEC_MAP.md`.

### Resolution — 2026-09-05

**The user authorised amending the spec; no code was renamed.** `EVAL_HARNESS_STAGE0_SPEC.md` §7 is
rewritten from "what to add to `aggregate.py`" into "how the scoring layer is structured", and now
describes what exists: scorers implemented once each in `scorers/*.py` and called directly, golden
loading and validation in `golden_loader.py`, `aggregate_form_pr`/`score_clip_form_pr` named as they
are, and the typed `SubjectLockResult`/`ViewResult` returns with the reason they're typed (the report
can name the failing clip, which a bare mean cannot). §7 carries a dated amendment note saying the
wrapper layer was specified, never built, and is not wanted.

This keeps docs-are-truth intact rather than hollowing it out: the spec was changed **deliberately, by
the person who owns it**, not retro-fitted by the agent to whatever the code happened to do. Decision
#5 in `CODE_SPEC_MAP.md` is closed. No code, test, or eval score changed — 301 tests and both gate
modes are untouched by this edit.

### Alternatives considered
- **Build §7 literally.** Rejected for now: a pass-through layer that exists only to satisfy a doc
  sentence is the kind of indirection `CLAUDE.md` §1's "no machinery that's never met reality" spirit
  argues against — but it remains the user's call.
- **Silently amend §7.** Rejected — the docs are the source of truth; editing the spec to match
  whatever the code happens to do would hollow out that rule.

---

## ADR-302 — `excess_torso_lean` implemented for squat and lunge, at `severity: med`

**Status:** Accepted · 2026-09-05 · *severity pending PT confirmation at GATE G-REAL*
**Relates to:** `EXERCISE_LIBRARY.md` §3 and its §4 cross-repo flag; `GOLDEN_SET_PROTOCOL.md` §7;
`RECORDING_SHOTLIST.md` items 15 & 18; `CODE_SPEC_MAP.md` decision 1.

### Context
Four documents said the detector should flag torso lean, and it could not:

- `EXERCISE_LIBRARY.md` §3 lists "torso lean" among the key faults for **squat** *and* **lunge**.
- `GOLDEN_SET_PROTOCOL.md` §7 instructs the PT to label `excess_torso_lean` on both.
- `RECORDING_SHOTLIST.md` items 15 and 18 tell the lifter to **deliberately seed** it on lunge clips.
- The `Vision_Contract` sheet carries it, and `kinetiq-demo2` has shipped the rule and a cue for both
  exercises since v2.

But neither `squat.json` nor `lunge.json` had a `common_errors` entry for it, so `run_detector` had no
rule to run. Left alone, the ~23 bake-off clips would have been recorded with a seeded fault the
detector structurally cannot see: every seeded instance scores as a **miss**, depressing recall for a
reason that has nothing to do with detection quality, and the PT's labelling time on those reps is
wasted. That is the specific failure this was worth fixing *before* the recording session, not after.

### Decision
Implement it for **both** exercises:

- `geometry.torso_lean_deg(shoulder_mid, hip_mid)` — transliterated from `kinetiq-demo2`'s shipped
  `torsoLeanDeg()`, so the offline detector measures the same quantity the product already does
  rather than introducing a second, subtly different definition of "torso lean".
- `faults.excess_torso_lean_present(...)` — a per-frame predicate, therefore subject to the existing
  sustained-flag hysteresis and visibility gating like every other per-frame fault.
- Registered for `squat` and `lunge` in `flag_hysteresis.EXERCISE_SUSTAINED_FLAG_IDS`. No change to
  `adapter.py` was needed: it already reads that table, the severity, and `phase_detected_in` from the
  library generically.

Two sub-decisions worth recording:

1. **It requires all four landmarks (both shoulders, both hips), not either side.** Unlike
   `elbow_flare` / `hip_sag`, which are per-side rules where one visible side is a valid reading,
   torso lean is a **midline** measurement — one shoulder tells you nothing about where the torso's
   centre line is. Missing any of the four returns `None` (insufficient evidence), which the harness
   already surfaces rather than scoring as either a hit or a miss.
2. **`severity: med`, explicitly provisional.** It matches each exercise's other form-quality faults
   and demo2's coaching-tone treatment. But excessive lean is lumbar-loading, and a PT may well argue
   for `high` — which under the §4 taxonomy would make it **vetoing** and raise its precision floor.
   Both contracts therefore carry a `severity_note` putting that question to the PT at the GATE G-REAL
   labelling session. Guessing `high` would have asserted a safety claim we have no evidence for;
   guessing `med` and *saying so* is the honest version.

**No threshold value was invented** — the gate on threshold values (`ROADMAP.md`) holds.
`torso_lean_max_deg` already existed in both contracts (squat 45°, lunge 20°) and already matched
demo2's shipped values; this ADR only wires a rule to numbers that were already there.

### Consequences
- squat gains a 4th sustained flag and lunge its **first** — lunge previously had only the
  rep-aggregate `shallow_lunge` and never entered `flag_hysteresis` at all.
- Verified no regression: on `squat_badform_001` the upright fixture produces the identical rep count
  and identical existing flags, with no `excess_torso_lean`; tilting the torso makes it fire on every
  rep. 301 tests pass (up from 290 — 9 new predicate tests plus 2 new coverage tests, no test
  weakened), `--mode full` still `Stage 0 gate: PASS`, and the prototype smoke is green.
- One existing test legitimately changed: `test_covers_exactly_the_five_per_frame_flags` pinned the
  flag inventory at five. It now pins six and is renamed. Two coverage tests were added so a future
  flag can't be registered without a matching library entry and predicate.
- **A real accuracy consequence to expect at GATE G-REAL:** squat and lunge will now flag reps they
  previously ignored. On real clips this is untested — it may surface false positives that the
  synthetic fixtures cannot. That is the point of the gate; note it when reading the first report.

### Alternatives considered
- **Squat only** (as literally asked). Rejected: lunge has the identical gap, and the shot-list seeds
  the fault *on lunge*, so fixing only squat would have left the more urgent half broken.
- **Contract entry only, no rule** (`status: needs_pt_confirmation`, as the 5 gated faults do).
  Reasonable, and it was offered — but it leaves the shot-list's seeded lunge clips unmeasurable,
  which is the problem worth solving before recording.
