# EXERCISE_LIBRARY.md — Kinetiq v3

> The exercise library defined **now** (schema + contract), with live vision-support **gated
> per-exercise** behind its own eval bar (`EVAL_STRATEGY.md`). "Defined for all, live for the proven"
> — the same schema-now/behaviour-by-phase pattern from v2, sharpened by Ch 39's rule that nothing
> ships vision until its golden set says so.
> Last updated: 2026-09-03

---

## 1. Scope

**14 exercises: the current 3 + the 11 requested.** All 14 now have a real contract JSON in
`../kinetiq-v2/exercises/` (Stage 5a, `CHANGELOG.md` 0.7.0 — preponed, run in parallel with GATE
G-REAL; spec/data only, no detector change). **Live vision detection turns on for an exercise only
when it passes its eval bar** — so the count of *defined* exercises (14) and *vision-live*
exercises (still 0 until re-proven under the v3 engine) are deliberately different numbers, and
authoring these 11 contracts does not move that second number: `detector/exercise_signals.py`'s
Stage-1 scope and `prototype_api`'s supported-exercise list are both still exactly
squat/pushup/lunge, unchanged.

Requested set, de-duplicated: pull-ups, planks, leg raises, hanging leg raises, military/overhead
press, arnold press, bench press, triceps pushdowns, bicep curls, hamstring curls, deadlifts.

5 faults across these 11 (`deadlift.lumbar_flexion`, `bench_press.excessive_lumbar_arch`,
`bench_press.excessive_elbow_flare`, `overhead_press.lumbar_hyperextension`,
`arnold_press.lumbar_arch`) are marked `status: "needs_pt_confirmation"` with no threshold seeded
— safety-relevant geometry a PT needs to confirm, not a number to guess (`CHANGELOG.md` 0.7.0 has
the full list and reasoning, including why `arnold_press` got the same treatment as
`overhead_press` despite not being named explicitly in the original ask).

---

## 2. The honest warning: the new exercises are HARDER for vision than the first three

This matters more than the count. Squat/push-up/lunge are the *easy* case — bodyweight, no equipment,
one person, whole body visible. Most of the requested additions break at least one of those:

- **Equipment occludes the body** — a barbell across the back/chest, a cable stack, a machine pad
  hides the very joints the form rules need.
- **Lying / seated / hanging positions** — bench press, hamstring curl, hanging leg raise change the
  camera geometry entirely and often hide half the skeleton.
- **The gym is crowded around equipment** — benches, racks, and other lifters are exactly the
  multi-object, multi-person clutter that produced the **bench→6-reps** and **skeleton-jump** bugs.
- **Some are spine-safety-critical** — deadlift and bench press. A wrong form call here isn't just a
  bad UX moment, it's a liability. These get the **highest eval bar + PT sign-off** before any form
  flag ships.

**Conclusion:** the additions make Stage-1 subject-lock and Stage-3 rep-validity (VISION_ARCHITECTURE)
*more* essential, not less, and make per-exercise eval gating non-negotiable. Breadth is cheap to
*define* and expensive to *trust* — so we define all 14 and trust them one eval at a time.

---

## 3. The library (defined now; vision gated)

Tiered by vision difficulty. `Rep/Hold`: whether it counts reps or is a timed isometric hold (planks
need a different eval — time-under-tension + hold-quality, not rep count). `Side-view`: works from the
single-person, camera-on-the-floor side angle testers preferred.

### Tier A — bodyweight / camera-friendly (lowest vision risk)

| ID | Name | Equip | Rep/Hold | Side-view | Key faults to detect | Vision status |
|---|---|---|---|---|---|---|
| `squat` | Bodyweight Squat | none | Rep | ok (needs front for knee-cave) | knee cave, shallow depth, torso lean | **re-prove under v3** |
| `pushup` | Push-Up | none | Rep | good | hip sag, elbow flare, shallow depth | **re-prove under v3** |
| `lunge` | Forward Lunge | none | Rep | good | front-knee track, depth, torso lean | **re-prove under v3** |
| `plank` | Plank | none | **Hold** | good | hip sag / pike, ~~neck alignment~~ (no head/neck landmark — omitted) | contract defined; pending eval |
| `leg_raise` | Lying Leg Raise | mat | Rep | good | lumbar arch, momentum/swing | contract defined; pending eval |
| `pull_up` | Pull-Up | bar | Rep | good | partial ROM (chin over bar), kipping/swing | contract defined; pending eval |

### Tier B — free weights, standing (medium risk: weight occlusion)

| ID | Name | Equip | Rep/Hold | Side-view | Key faults | Vision status |
|---|---|---|---|---|---|---|
| `overhead_press` | Military / Overhead Press | barbell/DB | Rep | ok | lockout ROM, **lumbar hyperextension (needs PT confirmation)**, uneven press | contract defined; pending eval |
| `arnold_press` | Arnold Press | dumbbell | Rep | ok | ~~rotation path~~ (no wrist-orientation data — omitted), lockout, **lumbar arch (needs PT confirmation)** | contract defined; pending eval |
| `bicep_curl` | Bicep Curl | DB/barbell | Rep | good | elbow drift, torso swing (momentum), partial ROM | contract defined; pending eval |
| `deadlift` | Deadlift | barbell | Rep | good | **spinal flexion (needs PT confirmation)**, bar path, lockout | contract defined; pending eval — **PT sign-off required** |

### Tier C — bench / cable / machine (highest risk: heavy occlusion, lying/seated)

| ID | Name | Equip | Rep/Hold | Side-view | Key faults | Vision status |
|---|---|---|---|---|---|---|
| `bench_press` | Bench Press | barbell/bench | Rep | partial (bar + bench occlude) | **spinal + elbow-flare/shoulder safety (both need PT confirmation)**, depth, bar path, uneven | contract defined; pending eval — **PT sign-off required** |
| `triceps_pushdown` | Triceps Rope Pushdown | cable | Rep | ok | elbow drift, torso lean/momentum, partial ROM | contract defined; pending eval |
| `hamstring_curl` | Hamstring Curl | machine | Rep | partial (machine occludes) | hip lift off pad, partial ROM | contract defined; pending eval |
| `hanging_leg_raise` | Hanging Leg Raise | bar | Rep | good | swing/momentum, ROM, lumbar control | contract defined; pending eval |

---

## 4. Per-exercise contract (what "defined" means)

Each exercise gets a JSON record in the same shape as v2's `exercises/*.json`, extended for v3:

- `id`, `name`, `equipment`, `movement_type` (`rep` | `hold`), `difficulty`, `tier` (A/B/C).
- `rep_counting` — phase machine (or hold criterion for planks).
- `form_checks` — per-fault: rule (for the deterministic baseline/veto) **and** the learned-model
  feature set (Stage 5). **Every fault declares a `severity` (see taxonomy below); safety-critical
  faults are `severity: high` with `veto: true`.**
- `thresholds` — per-exercise named values, **seeded** from a spec but **owned by field-measured data**
  (the xlsx/spec is a seed, not truth — the standing rule from the v2 threshold-drift lesson).
- `graded_thresholds` — beginner/intermediate/advanced multipliers (strictness by fitness level).
- `vision_support` — `false` until the eval bar passes; flipped per-exercise by a gated merge.
- `contraindications` — carried from v2 (health-context modifiers).
- `camera_guidance` — recommended framing (view + camera height) for this exercise.

### Severity taxonomy (canonical)

Every fault carries a `severity ∈ { high, med, low }`, which sets its eval floors. **The floor values
live in `../kinetiq-v2/backend/app/core/config.py` (single source of truth) — this table names the
constants, it does not restate the numbers as independent truth.**

| severity | veto | precision floor | recall floor | meaning |
|---|---|---|---|---|
| `high` | `veto: true` | `FORM_PRECISION_FLOOR_HIGH_SEV` | `FORM_RECALL_FLOOR_HIGH_SEV` | safety-relevant; never accuse a good rep; may overrule the learned model |
| `med` | no | `FORM_PRECISION_FLOOR_MED_SEV` | `FORM_RECALL_FLOOR_MED_SEV` | form-quality; enforced but non-vetoing |
| `low` | no | — (advisory / logged only) | — | nuance; surfaced/logged, no enforced floor |

Precision-first: `high` carries the strictest precision floor but the *most lenient* recall floor — we
would rather miss a real fault than falsely accuse a good rep on a safety flag. **Every fault in the
library must declare one of these three values; a fault with no `severity` is a schema error and fails
the golden-set validator (`EVAL_HARNESS_STAGE0_SPEC.md` §11).**

> **Cross-repo flag — RESOLVED 2026-09-05.** Both halves of this are now closed:
> - **`medium` → `med`**: all 30 occurrences across the 14 contract JSONs are normalised to `med`.
>   `exercise_lib.py`'s read-time alias is **kept** so the `Vision_Contract` sheet (which still says
>   `medium`) and any older exported data continue to load — the alias is now a compatibility shim
>   rather than the primary mechanism.
> - **squat's `excess_torso_lean`**: the entry now exists in `squat.json`, and — since
>   `EXERCISE_LIBRARY.md` §3 lists torso lean for **lunge** too, and `RECORDING_SHOTLIST.md` items 15
>   and 18 deliberately *seed* it on lunge clips — in `lunge.json` as well. It is implemented in the
>   detector (`faults.excess_torso_lean_present`), transliterated from `kinetiq-demo2`'s shipped rule,
>   using each exercise's existing `torso_lean_max_deg` (squat 45°, lunge 20°). Both are
>   `severity: med` with a `severity_note` asking the PT to confirm that level at GATE G-REAL.

## 5. The eval bar an exercise must clear to go vision-live

Two tiers of "live", so an exercise can start helping (advisory) long before the full coaching stack —
and the calibrated judge, which only exists at Stage 6 — is built.

**(a) `vision_support: true` (advisory) — requires gates 1–5**, on its frozen golden set
(`EVAL_STRATEGY.md`):

1. **Rep-count accuracy ≥ 90%** across front/side/diagonal and the device×lighting matrix.
2. **No phantom reps** on bench/empty clips (bystander is a real-rep clip — its subject-lock is gate 3).
3. **Subject-lock ≥ 99% (`SUBJECT_LOCK_FLOOR`)** on its multi-person clips — the floor lives in
   `../kinetiq-v2/backend/app/core/config.py`, not restated here.
4. **Form precision ≥ its severity floor** on every fault (`FORM_PRECISION_FLOOR_HIGH_SEV` /
   `FORM_PRECISION_FLOOR_MED_SEV`) **and recall ≥ its severity floor** (`FORM_RECALL_FLOOR_HIGH_SEV` /
   `FORM_RECALL_FLOOR_MED_SEV`), per the §4 severity taxonomy — never accusing a good rep on a
   high-severity fault.
5. **Safety-critical exercises** (`deadlift`, `bench_press`): PT sign-off on the labeled faults +
   deterministic safety veto verified, before *any* form flag is shown.

**(b) Authoritative / public coaching-cue delivery — additionally requires:**

6. **Coaching cues pass the calibrated LLM judge** (positive-first, non-medical, grounded) — the
   **Stage-6** deliverable in `EVAL_HARNESS_STAGE0_SPEC.md` (§10, §12). Until Stage 6 exists, cues are
   gated only by the cheap Stage-0 assertions (length ≤ 8 words, no medical terms), and an exercise may
   be advisory-live under (a) in the meantime.

Planks are graded on **hold-quality over time** (posture maintained ≥ X% of the hold) instead of
rep-count accuracy.

## 6. Recommended build order (feeds `ROADMAP.md`)

Prove the engine on the **easy, known** cases first, then climb the tiers:

1. Re-prove `squat`, `pushup`, `lunge` under the v3 engine (they already have field data + bugs).
2. Tier A additions (`plank`, `leg_raise`, `pull_up`) — bodyweight, camera-friendly.
3. Tier B (`bicep_curl`, `overhead_press`, `arnold_press`), then `deadlift` with PT sign-off.
4. Tier C (`triceps_pushdown`, `hanging_leg_raise`, `hamstring_curl`, `bench_press`) — occlusion-heavy,
   `bench_press` last and PT-gated.

Each step is one or more gated merges; none ships on vibes.

**"Vision-live" here means tier (a) advisory** (§5 gates 1–5). `squat`/`pushup`/`lunge` can and should
go advisory-live as soon as they pass gates 1–5 — **well before** the Stage-6 calibrated judge exists.
Authoritative/public coaching-cue delivery (tier b, gate 6) follows once Stage 6 lands; it does not
block the advisory rollout.
