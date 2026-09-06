# CODE_SPEC_MAP.md — Kinetiq v3

> **The traceability artifact: every in-scope spec section → the code implementing it → whether it
> conforms.** The docs in this folder are the source of truth; this file is the audit that the
> codebase (across `../kinetiq-v2` and `../kinetiq-demo3`) actually derives from them.
> Read `CLAUDE.md` first — its Code Map says *where* code lives; this says *what implements what*.
> Verified against a green baseline: 301 tests pass, `aggregate.py --mode full` → `Stage 0 gate: PASS`.
> All five surfaced decisions are now closed — see "Decisions surfaced" below.
> Last updated: 2026-09-05

**How to read the status column**

| Status | Meaning |
|---|---|
| **conformant** | Code implements the spec section as written. |
| **conformant (refined)** | Code satisfies the spec's intent with a structure/signature the spec didn't literally prescribe, and the refinement is recorded below (and as an ADR where substantive). |
| **gap — filled** | Spec required it, code lacked it, filled this pass. |
| **open — flagged** | Genuine code↔doc disagreement. **Not silently resolved** — surfaced for a human decision. |
| **gated** | Spec describes it; `ROADMAP.md`/`CLAUDE.md` §6 forbid building it now. Deliberately absent. |

---

## 1. Detector — Stages 1–3 (`VISION_ARCHITECTURE.md` §2)

All in `kinetiq-v2/evals/gate0/detector/`.

| Spec | Implementation | Status |
|---|---|---|
| Stage 1 — person detect + **subject-lock** (RC1): pick one subject, track identity, **pause** rather than silently retarget when lost | `subject_lock.py` (`track_subject`) — selection rule + `SUBJECT_LOST_FRAMES_THRESHOLD` pause, position-based re-id when stream ids are unstable | **conformant** |
| Stage 2 — pose estimation, **model-agnostic feature vector**; "document the COCO-17 ↔ BlazePose-33 mapping so features are model-agnostic" | `keypoint_map.py` (`POSE_MODEL_LANDMARKS`) — named-landmark → per-model index for `blazepose_33` / `movenet_17` / `rtmpose_halpe26`; `pose_capture/` holds the per-model capture adapters | **conformant** — this is the mapping `EVAL_HARNESS_STAGE0_SPEC.md` §11 flagged as missing; it exists and cites that flag in its own docstring |
| Stage 3 — **rep-validity gate** (RC2): human-pose plausibility, visibility, subject check, tempo sanity — "a bench cannot pass" | `plausibility.py` (`is_plausible_human`: visible-landmark fraction + limb-ratio band), tempo band in `rep_counter.py` | **conformant** |
| Stage 4 — rep counter: smoothed FSM, hysteresis, **tempo tolerance**, **graded** (not binary) depth | `rep_counter.py` (`count_reps_with_state`) — median smoothing, hysteresis, min-excursion floor, `MIN/MAX_REP_DURATION_MS`, graded depth scoring | **conformant** |
| RC4 precision-first flagging — a flag attaches only when **sustained**, and is never judged on frames where its landmarks are too low-visibility | `flag_hysteresis.py` (`evaluate_sustained_flag`) + per-predicate `min_visibility` in `faults.py`; `INSUFFICIENT_EVIDENCE` is surfaced, never silently dropped | **conformant** |
| §3/`GOLDEN_SET_PROTOCOL.md` §7 torso lean on squat + lunge | `faults.excess_torso_lean_present` (midline: shoulder-midpoint vs hip-midpoint, requires all four landmarks — one side cannot locate a midline) + `geometry.torso_lean_deg`, transliterated from `kinetiq-demo2`'s shipped `torsoLeanDeg()`. Registered for both exercises in `flag_hysteresis.EXERCISE_SUSTAINED_FLAG_IDS`; thresholds read per-exercise from the library (squat 45°, lunge 20°) | **gap — filled** this pass. Verified end-to-end on the `squat_badform_001` golden fixture: silent when upright (no false positives, existing flags and rep count unchanged), fires on all reps when the torso is tilted, and the cue layer returns "Keep your chest up" within the word cap |
| Deterministic fault rules, transliterated from each exercise's own `keypoint_signature.rule` (Stage 1 does not tune or invent fault logic) | `faults.py`, `exercise_signals.py`, `geometry.py` | **conformant** |
| The adapter interface `run_detector(keypoints_stream, exercise_id, config) -> DetectedClip` (`EVAL_HARNESS_STAGE0_SPEC.md` §5) | `adapter.py::run_detector` — deterministic; never sees ground truth (subject-lock is graded separately by the harness via `score_subject_lock_against_expected`) | **conformant** |
| Stage 5 — **learned form model** | *(absent)* | **gated** — blocked by GATE G-REAL; `ROADMAP.md` Stage 4 says "Do not start" |
| Stage 5b — deterministic safety veto | Structurally upheld: no learned model exists, so nothing can override a rule. Becomes live code when Stage 5 unblocks | **gated** (invariant holds vacuously) |

**Scope check:** `exercise_signals.py::scoped_exercises()` returns exactly `(squat, pushup, lunge)` —
matching `EXERCISE_LIBRARY.md` §1's statement that detector scope is unchanged by the 11 authored
contracts.

---

## 2. Scorers (`EVAL_HARNESS_STAGE0_SPEC.md` §3, §6)

All in `kinetiq-v2/evals/gate0/scorers/`. §3 requires one unit-testable module per dimension — all five exist, each with tests.

| Spec | Implementation | Status |
|---|---|---|
| §6 rep matching — Needleman–Wunsch-style **monotonic** alignment, cost 0 to align / 1 per gap | `rep_match.py::match_reps` | **conformant** |
| §6 per-flag TP/FP/FN, incl. the two deliberate edge choices (**phantom rep's flags → FP**, **missed rep's faults → FN**) | `form_pr.py::score_clip_form_pr` | **conformant** — both edge cases implemented and documented in-code as the spec requires |
| §6 severity-matched floors (high-sev = strictest precision, *most lenient* recall) | `form_pr.py::gate_flag` / `gate_form_pr` — looks up each fault's severity via `exercise_lib`, applies the matching floor; low-sev advisory, no enforced floor | **conformant** |
| No-phantom-reps, over `phantom_*` clips **only** (bystander is a real-rep clip) | `phantom.py::score_phantom` | **conformant** |
| Subject-lock accuracy over multi-person clips | `subject_lock.py::score_subject_lock` → `SubjectLockResult` (per-clip fractions + mean), so the report can name the offending clip rather than printing a bare aggregate | **conformant** — §7 specifies the typed return as of 2026-09-05 (ADR-301) |
| Per-view rep-accuracy spread | `view.py::score_view_robustness` | **conformant** |

---

## 3. Stage-0 harness (`EVAL_HARNESS_STAGE0_SPEC.md` §4, §5, §7, §8)

| Spec | Implementation | Status |
|---|---|---|
| §7 CLI: `--data` (unchanged legacy path), `--golden` + `--mode {fast,full}`, non-zero exit on any dimension below floor | `aggregate.py::main` / `run_data` / `run_golden` — verified: `--mode full` exits 0 on PASS | **conformant** |
| §7 `print_stage0_report(clips) -> bool`, legible to a non-engineer | `aggregate.py::print_stage0_report(clips, mode)` — gained a `mode` arg, consistent with §7's own `--mode` flag | **conformant** |
| §7 golden loading + validation in `golden_loader.py`, failing loudly on an unknown flag / missing file; `validate_frame_schema` shared with `prototype_api` | `golden_loader.py::load_golden` / `validate_frame_schema` / `load_golden_poses` / `load_capture_meta` | **conformant** |
| §7 one scorer per dimension in `scorers/*.py`, called directly by `aggregate.py` (no wrapper layer) | `scorers/{rep_match,form_pr,phantom,subject_lock,view}.py` — incl. the `score_clip_form_pr` / `aggregate_form_pr` pair (per-clip vs pooled) | **conformant** — §7 was amended 2026-09-05 to describe this structure rather than the wrapper layer it originally sketched; ADR-301 |
| §8 gate floors are **defined in `config.py` and imported, never restated** | `backend/app/core/config.py` (all 8 constants, exact spec names) → imported via `gate_config.py`, the single import point | **conformant** — verified by search: **zero** restated floor literals anywhere in the harness. This closes §11's last explicitly-open item |
| §5 frozen `keypoints.jsonl` schema: variable-length `kp`, `z: null` for 2D models, multi-person `people[]` | `golden_loader.py::validate_frame_schema` — shared by the loader *and* the capture tool so both enforce identical rules | **conformant** |
| §5 `detected.json` is **recomputed**, never frozen | `golden_loader.py` recomputes via `run_detector` for any Stage-1-scoped exercise | **conformant** |
| §10 cue assertions stubbed in Stage 0 (length ≤ 8 words, no medical terms) | `aggregate.py::check_coaching_cue_assertions`, cap from `LIVE_CUE_MAX_WORDS` | **conformant** |
| §10 calibrated **LLM-as-judge** for cue quality | *(absent)* | **gated** — Stage 6 deliverable |
| §12 offline re-run over frozen keypoints | `golden_loader.py` + `adapter.py` | **conformant** (the deferred item, since delivered) |
| §10 **CI wiring** (fast gate on push, full gate on merge/nightly, report uploaded, non-zero exit blocks the merge) | `kinetiq-v2/.github/workflows/gate0-eval.yml` — `fast-gate` on push/PR runs the unit tests + `--mode fast` across a 3.12/3.13 matrix; `full-gate` on merge-to-main/nightly-cron runs `--mode full` (pipefail'd, so a failing gate actually fails the job) and uploads the report | **conformant** — no longer a draft. One repo-settings step remains before it *blocks*; see Decision 4 |

---

## 4. Exercise-contract schema (`EXERCISE_LIBRARY.md` §3, §4)

| Spec | Implementation | Status |
|---|---|---|
| 14 exercises defined, each a contract JSON | `kinetiq-v2/exercises/*.json` — 14 files, all load via `config.load_exercise_library()` | **conformant** |
| §4 fields incl. `tier` (A/B/C), `movement_type` (`rep`\|`hold`), `vision_support` | All 14 — the 11 newer ones already had them; **`squat`/`pushup`/`lunge` were missing all three despite declaring `schema_version: 2`** | **gap — filled** this pass: `tier: "A"`, `movement_type: "rep"` (both per §3's table), `vision_support: false`. No code reads these fields, so behaviour is unchanged — verified 290 tests + gate still green |
| §4 every fault declares `severity ∈ {high, med, low}`; a missing severity is a schema error | `exercise_lib.py::load_fault_severities` raises `ExerciseLibraryError` on a missing severity | **conformant** |
| §4 canonical taxonomy is `med`, not `medium` | All 30 severity tokens across the 14 contracts normalised to `med`; `exercise_lib.py`'s alias **kept** as a compatibility shim for the `Vision_Contract` sheet (still `medium`) and older exports | **gap — filled** this pass |
| §4 `camera_guidance` (recommended framing per exercise) | All 14 now carry `camera_guidance` (`recommended_views`, `camera_height`, `distance_m`, `framing_note`). squat/pushup/lunge transliterate the strings `kinetiq-demo2`/`kinetiq-demo3` already ship; the other 11 derive from §3's Side-view column + equipment | **gap — filled** this pass |
| §3 squat's **and lunge's** key faults include **torso lean** | `excess_torso_lean` now in both contracts and implemented: `faults.excess_torso_lean_present` + `geometry.torso_lean_deg`, registered in `flag_hysteresis` for both exercises | **gap — filled** this pass — see §1 note below |
| §4 `vision_support: false` until the eval bar passes | All 14 are `false` | **conformant** — the gate is respected in data, not just prose |
| §5 the eval bar itself (gates 1–5 / gate 6) | Enforced by the harness's floors (`aggregate.py` + `config.py`), not by per-exercise code | **conformant** |
| Vision-live for the 11 gated exercises | *(absent)* | **gated** — `EXERCISE_LIBRARY.md` §6, per-exercise eval bar |

---

## 5. `prototype_api` (`CLAUDE.md` Code Map; `prototype_api/README.md` is its own contract)

| Spec | Implementation | Status |
|---|---|---|
| Thin wrapper over the eval-validated `run_detector` — **no** pose runtime on the server | `prototype_api/main.py` — import scan confirms stdlib + fastapi/uvicorn/pydantic only; no mediapipe/tensorflow/rtmlib anywhere | **conformant** |
| `POST /prototype/assess` over keypoints; `GET /health` | `main.py` (both routes present) | **conformant** |
| Keypoints validated against the **same** Stage-0 schema the harness enforces | imports `golden_loader.validate_frame_schema` — literally the same function | **conformant** |
| CORS via `PROTOTYPE_API_CORS_ORIGINS`, default `*` as a deliberate prototype-only choice | `main.py::_CORS_ORIGINS` | **conformant** |
| No server-side persistence beyond an in-memory buffer, bounded by config | `session_buffer.py`, bounded by `PROTOTYPE_SESSION_MAX_FRAMES` | **conformant** |
| Cue layer explicitly interim, ≤ `LIVE_CUE_MAX_WORDS`, over-cap flagged not hidden | `cues.py::cue_for_rep` → `CueResult.over_word_cap` | **conformant** |

---

## 6. `kinetiq-demo3` PWA (`CLAUDE.md` §2 privacy invariant; `VISION_ARCHITECTURE.md`)

| Spec | Implementation | Status |
|---|---|---|
| **Pixels never leave the device** — pose runs on-device, only keypoints cross the network | `index.html` — verified by search: **no** `toDataURL` / `toBlob` / `getImageData` / `FormData` / image upload anywhere. The only request body is `JSON.stringify` of keypoint frames | **conformant** — the invariant is structural, not just documented |
| Client contains **zero detection logic** — rep count, phase, flags, cues all decided server-side | `index.html` streams keypoints and renders the API's response | **conformant** |
| Exported bundle carries keypoints + labels, **never video** | `index.html` export path builds `keypoints.jsonl` + `detected.json` + CSV templates | **conformant** |
| Deploy config: no build step, HTTPS, API URL configurable without a rebuild | `render.yaml` / `netlify.toml` / `config.js` + `set-api-url.ps1` | **conformant** |

---

## 7. The `one-detector-two-consumers` agreement (`CLAUDE.md` Code Map)

`run_detector` is defined **once**, in `detector/adapter.py`, and imported by every consumer — no
reimplementation anywhere:

| Consumer | Import site |
|---|---|
| Live prototype | `prototype_api/main.py:44` |
| Offline harness | `golden_loader.py:29` |
| Post-session report | `effectiveness_report.py:38` |

**conformant.** (Strictly there are three consumers, not two — the effectiveness report joined later.
The agreement's substance, one detector and no duplication, holds; the name is shorthand.)

---

## 8. Pre-recording coverage cross-check (`RECORDING_SHOTLIST.md` ↔ detector)

> **Run 2026-09-05, before the gym session.** ADR-302 caught a fault that four documents said to
> detect and the detector structurally could not see — *seeded* on lunge clips #15/#18, so every
> instance would have scored as a false miss. This section asks whether torso-lean was the only such
> gap, in both directions: every shot-list expectation → is there a real predicate; and every
> labelable fault → is it exercised by a clip.
>
> **"Covered" means a real predicate or state-machine path exists and reads its threshold from the
> exercise contract or `config.py`** — not that a fault is merely named in a JSON contract.
> Audit only: nothing was changed, and no threshold was invented.

### Seeded faults

| Expectation | Source | Detector code | Threshold from contract? | Verdict |
|---|---|---|---|---|
| squat knees cave inward → flagged | shot-list #3, #6 | `faults.knee_cave_left_present` / `knee_cave_right_present`, via `flag_hysteresis.evaluate_sustained_flag` | yes — `thresholds.knee_cave_x` | **covered** ⚠️ see GAP 2 (id naming) |
| push-up hips sag → flagged | shot-list #9, #12 | `faults.hip_sag_present` (sustained) | yes — `thresholds.hip_sag_angle_min` | **covered** |
| lunge torso leans forward → flagged | shot-list #15, #18 | `faults.excess_torso_lean_present` (sustained) | yes — `thresholds.torso_lean_max_deg` (lunge 20°) | **covered** — the ADR-302 fix |

### Non-fault behaviours the clips assert

| Expectation | Source | Detector code | Threshold from contract? | Verdict |
|---|---|---|---|---|
| partial-depth squat **still counts**, at a lower score | shot-list #19 | `rep_counter.count_reps_with_state` (counts on excursion, not depth) + `adapter`'s graded-depth score `floor + (10−floor)·depth_fraction` | yes — depth reference `key_angles.left_knee_angle_at_bottom.max`; floor `GRADED_DEPTH_FORM_SCORE_FLOOR`, counting gated by `REP_MIN_EXCURSION_DEG` | **covered** — verified on `squat_partial_depth_001`: 3 reps, `form_score 4.8` vs `10.0` clean ⚠️ see GAP 1 |
| slow 3-0-1-0 tempo push-up **still counts** | shot-list #20 | `rep_counter` tempo band | n/a — `config.MIN/MAX_REP_DURATION_MS` = 400 / **12000 ms**; a 3-0-1-0 rep is ~4000 ms, comfortably inside | **covered** — verified on `pushup_slow_tempo_001`: counted, `flags=[]`, score 10.0 |
| bench through frame, nobody exercising → **0 reps** | shot-list #21 | `plausibility.is_plausible_human` — a frame failing it contributes no signal regardless of lock status | n/a — `MIN_VISIBLE_KEYPOINT_FRACTION`, `HUMAN_LIMB_RATIO_MIN/MAX`, `MIN_KEYPOINT_VISIBILITY` | **covered** |
| empty frame / passer-by → **0 reps** | shot-list #22 | no `people[]` → no locked subject → no angle signal; `subject_lock.track_subject` pauses rather than retargeting | n/a — `SUBJECT_LOST_FRAMES_THRESHOLD` | **covered** |
| bystander present → skeleton stays on the user | shot-list #23 | `subject_lock.track_subject` (selection + re-id); graded harness-side by `adapter.score_subject_lock_against_expected` | n/a — `SUBJECT_SELECTION_RULE`, `SUBJECT_REID_MAX_CENTROID_DIST`, floor `SUBJECT_LOCK_FLOOR` | **covered** |

### Faults the PT is told to label (`GOLDEN_SET_PROTOCOL.md` §7) beyond the seeded three

| Expectation | Source | Detector code | Threshold from contract? | Verdict |
|---|---|---|---|---|
| squat `shallow_depth` | protocol §7 | `faults.shallow_depth_present` (sustained, bottom-phase-narrowed) | n/a — compares hip.y to knee.y, no configured value | **covered**, and exercised incidentally by #19 ⚠️ **GAP 1** |
| squat `excess_torso_lean` | protocol §7 | `faults.excess_torso_lean_present` | yes — `thresholds.torso_lean_max_deg` (squat 45°) | **covered**, but **no squat clip seeds it** → recall unmeasured (GAP 3) |
| pushup `elbow_flare` | protocol §7 | `faults.elbow_flare_present` (sustained) | yes — `thresholds.elbow_flare_deg` | **covered**, but **no clip seeds it** → recall unmeasured (GAP 3) |
| pushup `shallow_pushup` | protocol §7 | `faults.shallow_pushup_present` (rep-aggregate) | yes — `thresholds.depth_elbow_angle_max` | **covered**, but **no clip seeds it** → recall unmeasured (GAP 3) |
| lunge `shallow_lunge` | protocol §7 | `faults.shallow_lunge_present` (rep-aggregate) | yes — `thresholds.front_knee_angle_bottom_max` | **covered**, but **no clip seeds it** → recall unmeasured (GAP 3) |
| lunge `front_knee_cave`, `front_knee_overextend` | protocol §7 says **do not label** | *(deliberately unimplemented — `status: unresolved_spec_conflict`)* | n/a | **consistent** — doc and code agree; not a gap |

### Reverse direction: every `common_errors` entry → is it exercised?

All 11 labelable fault ids across squat/pushup/lunge have a detector predicate. **No fault is
labelable-but-blind** — the torso-lean class of bug does not recur. Four are detectable but never
positively seeded by the bake-off minimum (GAP 3).

---

### Verdict: **torso-lean was NOT the only gap — 3 findings, 1 of them a real poisoning risk**

> **All three resolved 2026-09-05** (docs only — no code, no threshold, no score). GAP 1 and GAP 2
> fixed as proposed; GAP 3 closed by adding the extra sets rather than accepting the blind spot.
> Resolution notes are inline under each finding below.

**GAP 1 — real, and the mirror image of torso-lean.** Clip #19's partial-depth squats **do** carry
`shallow_depth` (verified empirically: all 3 reps on `squat_partial_depth_001`). The shot-list tells
the lifter only "partial-depth squats (should still count, at lower score)" and never names the
fault — so a PT reading that row would reasonably record these as clean reps, `faults: []`. Every
flag then becomes a **false positive**, directly damaging `shallow_depth` precision. Torso-lean was
*seeded but undetectable* (false misses); this is *detected but unlabelled* (false accusations) —
same poisoning, opposite sign, and it fails silently because a `faults: []` label is perfectly valid.
- **Missing piece:** a labelling instruction, not code. No threshold involved, nothing to invent.
- **RESOLVED 2026-09-05.** Shot-list #19's "do this" is now *"stop clearly above parallel every rep"*
  with the note **"every rep IS `shallow_depth` — PT labels it on all of them"**, plus a callout
  explaining that #19 is a rep-*counting* test (the validity gate accepts a partial rep and scores it
  lower), not a clean-form test. `GOLDEN_SET_PROTOCOL.md` §7 gains a matching paragraph making an
  empty fault list on that clip explicitly wrong, generalised to any deliberately-seeded set.

**GAP 2 — wrong fault id in the shot-list, but it fails loudly.** #3/#6 say seed `` `knee_cave` ``;
that id does not exist. The real ids are `knee_cave_left` / `knee_cave_right`. Verified that
`golden_loader._load_clip` raises `GoldenSetError` on an unknown fault id, so a `knee_cave` label
would be **rejected at load time, not silently absorbed** — friction, not poisoning. But the lifter
also needs to know to cave a *specific* knee and the PT to record *which*, or a left-cave labelled as
right is a simultaneous false positive and false negative.
- **Missing piece:** shot-list wording. No code, no threshold.
- **RESOLVED 2026-09-05.** #3 and #6 now read *"deliberately cave the **LEFT** knee inward (seed
  `knee_cave_left`)"* with **"PT records which knee"** in the notes, plus a callout that no
  `knee_cave` id exists and that a mislabelled side is a false positive and false negative at once.
  `GOLDEN_SET_PROTOCOL.md` §7 gains a "knee cave is per-side" line.

**GAP 3 — four detectable faults are never seeded, so their recall is unmeasured.** `elbow_flare`,
`shallow_pushup`, `shallow_lunge`, and squat's `excess_torso_lean` have working predicates but no
clip that positively exercises them. This is **not poisoning** — the PT labels them absent, the
detector reports absent, and they score as true negatives — and it is largely *by design*: the
shot-list is explicitly the "bake-off minimum", not the gate-grade set (§9), which is what an
exercise needs to go vision-live. Naming them so the first report's silence on those flags is read
correctly, rather than as evidence they work.
- **Missing piece:** clips, i.e. gym time. Nothing to fix in code or docs.
- **RESOLVED 2026-09-05 — the sets were added rather than the blind spot accepted.**
  `RECORDING_SHOTLIST.md` gains **section F, clips #24–#27** (~10 min): `pushup_elbow_flare_side_001`,
  `pushup_shallow_side_001`, `lunge_shallow_side_001`, `squat_torso_lean_side_001` — one seeded fault
  each, with a "which other fault to avoid" note per row so each measures one flag cleanly. Note #27
  seeds `excess_torso_lean` on **squat** specifically: #15/#18 seed it on lunge, and the two carry
  different thresholds (45° vs 20°), so lunge clips never exercise squat's rule. Counts updated
  throughout (~23 → ~27 clips, 60–90 → 70–100 min), including `GOLDEN_SET_PROTOCOL.md` §8's own
  bake-off-minimum arithmetic.

---

## Decisions surfaced — and how they were resolved

These were genuine code↔doc disagreements. Per `CLAUDE.md`'s "surface decisions, don't guess" working
agreement, none was resolved unilaterally — each was put to the user, and the answer is recorded here.

1. **squat's (and lunge's) missing torso-lean fault** — *resolved: implement it fully.*
   `EXERCISE_LIBRARY.md` §3 lists torso lean for both, `GOLDEN_SET_PROTOCOL.md` §7 tells the PT to
   label it, and `RECORDING_SHOTLIST.md` items 15 and 18 deliberately **seed** it on lunge clips — so
   without it every seeded instance would have scored as a detector miss on the very clips being
   recorded for GATE G-REAL. Now implemented for both (§1, §4 above). Two things worth knowing:
   - **No threshold value was invented** — the gate on threshold values holds. `torso_lean_max_deg`
     already existed in both contracts (squat 45°, lunge 20°) and already matched `kinetiq-demo2`'s
     shipped values; the rule was wired to the numbers that were already there.
   - **Severity is `med`, and that is a judgement the PT should confirm.** It matches each exercise's
     other form-quality faults and demo2's coaching-tone treatment, but excessive lean is
     lumbar-loading, so a PT may argue for `high` — which would make it vetoing and raise its
     precision floor. Both contracts carry a `severity_note` saying exactly this.
2. **`medium` → `med` normalisation** — *resolved: normalise the JSON, keep the alias.* All 30 tokens
   normalised; `exercise_lib.py`'s alias retained so the `Vision_Contract` sheet (still `medium`) and
   older exports keep loading. The alias is now a compatibility shim, not the primary mechanism.
3. **`camera_guidance`** — *resolved: add it for all 14.* squat/pushup/lunge transliterate the
   framing strings `kinetiq-demo2`/`kinetiq-demo3` already ship; the other 11 derive from §3's
   Side-view column and equipment (e.g. `bench_press` records that the bar and bench occlude a pure
   side view; `hamstring_curl` that the machine pad hides the hips the check needs).
4. **The CI regression gate — RESOLVED as a workflow; one repo setting left.** `EVAL_STRATEGY.md` §4
   calls this "the part v1/v2 never had". It had **never run** (the repo was 68 commits ahead of
   `origin/main`), and the workflow self-described as a DRAFT. Both are now fixed:
   - **Pushed** (2026-09-05) after a clean scan for secrets, tracked `.env`/credentials, and any
     video or image under `golden/` — so the privacy invariant holds in what is now public.
   - **Made real** — DRAFT language removed; Python reconciled from **3.11** (below `CLAUDE.md` §4's
     mandated 3.12+) to a **3.12/3.13 matrix** on `fast-gate` and a **3.12** pin on `full-gate`.
   - **A gate-defeating bug found and fixed in the process:** the full-gate step piped into `tee`,
     and GitHub's default shell (`bash -e`, no `pipefail`) reports the *pipeline's last* exit status
     — `tee`'s, always 0. `aggregate.py` exits non-zero correctly, but that was being discarded, so
     **a failing Stage-0 gate would have been reported as a passing job.** Now `shell: bash` +
     `set -o pipefail`, demonstrated against a deliberately failing gate (exit 2 with, exit 0
     without). Worth noting because the gate would have *looked* green while not gating at all.
   - **Still open, and only the repo owner can do it:** required status checks in branch protection.
     Require **`fast-gate (3.12)` and `fast-gate (3.13)`** — *not* `full-gate`, which by design does
     not run on `pull_request` (§10's fast/full split), so requiring it would hang every PR on a
     check that never starts.
   - **Not verified locally: Python 3.12** — only 3.13.5 is installed on the dev machine, so the
     matrix's 3.12 leg is first exercised by CI itself.
5. **§7 wrapper layer / one function name** — *resolved 2026-09-05: **spec amended to match the code**,
   no code renamed.* §7 was rewritten from "what to add to `aggregate.py`" into "how the scoring layer
   is structured" and now describes reality — scorers implemented once each in `scorers/*.py` and
   called directly, loading in `golden_loader.py` (with `validate_frame_schema` shared with
   `prototype_api`), the real names `aggregate_form_pr`/`score_clip_form_pr`, and the typed
   `SubjectLockResult`/`ViewResult` returns plus why they're typed. §7 carries a dated amendment note;
   ADR-301 carries the resolution. Renaming working, tested code to satisfy a doc sentence would have
   been churn with regression surface and no behavioural gain.

---

## What was deliberately NOT built (gate compliance)

Per `ROADMAP.md` and `CLAUDE.md` §6, none of the following was generated, despite the docs describing
them: the **Stage-4/5 learned form model**; any **real threshold value** (every placeholder stays a
placeholder); **vision-live** for the 11 gated exercises; the **Tier-3 product app**
(`PARALLEL_PLAN.md` T3); the **Stage-6 calibrated cue judge**; the **pose-model verdict**
(`PARALLEL_PLAN.md` — the tooling exists, the answer needs real clips).
