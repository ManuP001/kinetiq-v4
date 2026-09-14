// Unit tests for segments.js.   Run:  node --test frontend/segments.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createSetTracker, boundQueue } from "./segments.js";

const FR = { rollAt: 0.8, forceRollAt: 0.95 };
const resp = (rep_count, rep_in_progress, reps = []) => ({ rep_count, rep_in_progress, reps });

test("rejects nonsensical roll fractions", () => {
  assert.throws(() => createSetTracker(() => 100, { rollAt: 0.9, forceRollAt: 0.8 }));
  assert.throws(() => createSetTracker(() => 100, { rollAt: 0, forceRollAt: 0.9 }));
});

test("does not roll before the roll point", () => {
  const t = createSetTracker(() => 100, FR);
  t.acknowledge(50, resp(2, false));
  assert.equal(t.shouldRoll(10), false);
});

test("rolls at rollAt only BETWEEN reps", () => {
  const t = createSetTracker(() => 100, FR);
  t.acknowledge(78, resp(3, true));          // rep in progress
  assert.equal(t.shouldRoll(5), false, "must not split a rep at the soft roll point");
  t.acknowledge(0, resp(3, false));           // rep finished
  assert.equal(t.shouldRoll(5), true);
});

test("force-rolls near the cap even mid-rep, rather than risk a 413", () => {
  const t = createSetTracker(() => 100, FR);
  t.acknowledge(90, resp(3, true));
  assert.equal(t.shouldRoll(6), true);
});

test("never rolls an empty session", () => {
  const t = createSetTracker(() => 100, FR);
  assert.equal(t.shouldRoll(500), false);
});

test("unknown cap: never rolls early, capacity is unbounded", () => {
  const t = createSetTracker(() => null, FR);
  t.acknowledge(10_000, resp(5, false));
  assert.equal(t.shouldRoll(10_000), false);
  assert.equal(t.capacity(), Infinity);
});

test("rep count and per-rep records carry across segments", () => {
  const t = createSetTracker(() => 100, FR);
  t.acknowledge(80, resp(3, false, [{ flags: [] }, { flags: ["hip_sag"] }, { flags: [] }]));
  t.roll();
  assert.equal(t.totalReps(), 3, "count survives the roll before the new segment answers");
  t.acknowledge(20, resp(2, false, [{ flags: [] }, { flags: [] }]));
  assert.equal(t.totalReps(), 5);
  assert.equal(t.allReps().length, 5);
  assert.equal(t.segments, 2);
  assert.equal(t.serverFrames, 20, "frame count restarts with each server session");
});

test("capacity shrinks as frames are accepted", () => {
  const t = createSetTracker(() => 100, FR);
  t.acknowledge(30, resp(0, false));
  assert.equal(t.capacity(), 70);
  t.roll();
  assert.equal(t.capacity(), 100);
});

test("a long set never needs one session beyond its cap (the original failure)", () => {
  const cap = 3600;
  const t = createSetTracker(() => cap, FR);
  let reps = 0;
  for (let i = 0; i < 1000; i++) {           // ~27 min of 12-frame POSTs
    const batch = 12;
    if (t.shouldRoll(batch)) t.roll();
    assert.ok(t.capacity() >= batch, `batch ${i}: would have hit the cap -> 413`);
    if (i % 25 === 0) reps++;
    t.acknowledge(batch, resp(reps - (t.totalReps() - (t.lastResponse?.rep_count || 0)), i % 25 === 3));
  }
  assert.ok(t.segments > 3, "a 27-minute set spans several server sessions");
});

test("boundQueue keeps the newest frames and reports what it dropped", () => {
  const q = [1, 2, 3, 4, 5, 6];
  assert.deepEqual(boundQueue(q, 4), { frames: [3, 4, 5, 6], dropped: 2 });
  assert.deepEqual(boundQueue(q, 10), { frames: q, dropped: 0 });
  assert.deepEqual(boundQueue(q, Infinity), { frames: q, dropped: 0 });
});
