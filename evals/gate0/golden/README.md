# golden/ — the frozen eval set

13 clips. **All synthetic.** Each is a geometric construction: a skeleton placed
analytically so a named joint angle hits a chosen value, sampled over a 2-second rep.

## These prove one thing, and not another

They prove the detector behaves as specified — that hysteresis rejects dither, that a
depth fault fires when depth is missed, that a bystander cannot steal the subject lock.

They prove **nothing** about accuracy on a human being. Real bodies are noisier, partially
occluded, and lit badly. Real accuracy is unmeasured until a real session
(`effectiveness_report.py`).

## Ground truth is authored, never read back

Each clip's labels come from the parameters it was built with — "constructed with a 42°
torso lean, therefore labelled `torso_lean`". Labels are **never** produced by running the
detector and recording the output. That would make the gate agree with itself forever and
detect no regression at all.

## Regenerating

```bash
cd evals/gate0/golden && python _generate_fixtures.py
```

Deterministic — same output every run. CI regenerates and diffs, so a drift between the
generator and the committed JSON fails the build.

## Coverage

| Clip | Exercise | View | Type | Reps | Labelled fault |
|---|---|---|---|---|---|
| `squat_clean_side_001` | squat | side | normal | 3 | — |
| `squat_shallow_side_002` | squat | side | normal | 3 | `shallow_depth` |
| `squat_clean_front_003` | squat | front | normal | 3 | — |
| `squat_kneecave_front_004` | squat | front | normal | 3 | `knee_cave_left` |
| `squat_lean_side_005` | squat | side | normal | 3 | `excessive_forward_lean` |
| `pushup_clean_side_006` | pushup | side | normal | 4 | — |
| `pushup_hipsag_side_007` | pushup | side | normal | 4 | `hip_sag` |
| `pushup_flare_side_008` | pushup | side | normal | 4 | `elbow_flare` |
| `lunge_clean_side_009` | lunge | side | normal | 2 | — |
| `lunge_lean_side_010` | lunge | side | normal | 2 | `torso_lean` |
| `phantom_empty_011` | squat | side | phantom_empty | 0 | — |
| `phantom_bench_012` | squat | side | phantom_bench | 0 | — |
| `pushup_bystander_013` | pushup | side | bystander | 4 | — |

## Why side-view clips report knee cave as "unjudgeable"

Valgus is a frontal-plane measurement. From the side the hips project onto nearly the same
point, so the check refuses to answer rather than reading normal forward knee travel as a
cave. That shows up in the report as *insufficient evidence*, which is correct — and is
excluded from precision/recall rather than counted as a clean rep.

## Never commit video

Keypoints and labels only. A test asserts no media files are present here.
