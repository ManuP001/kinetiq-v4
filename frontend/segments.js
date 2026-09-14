// segments.js — keeps one user-visible set continuous across several server sessions.
//
// WHY: the detector API holds at most `session_max_frames` frames per session (published by
// /health; ~2 min at 30fps) and re-runs the detector over the whole buffer on every request.
// Past that cap every request is an unrecoverable 413. Before this module, the app re-queued the
// rejected frames and retried into the same full session forever, sending an ever-larger body
// each time — which is how one long set ended as "Can't reach the trainer".
//
// WHAT: before a session fills, the app starts a fresh one ("rolls") and this tracker carries
// the rep count and the per-rep records forward, so the screen and the summary read as one set.
//
// The detector itself is untouched: every segment is scored by the same run_detector on the
// server. A roll only decides WHERE one server session ends and the next begins, and it prefers
// a moment when no rep is in progress so a rep is never split across two sessions.
//
// No DOM, no network — pure state, so it is unit-tested directly (segments.test.mjs).

/**
 * @param {() => (number|null)} getMaxFrames  the server's per-session frame cap, or null if not
 *        yet known (then we can only react to a 413, never roll early)
 * @param {{rollAt: number, forceRollAt: number}} fractions  fractions of the cap, from config.js
 */
export function createSetTracker(getMaxFrames, { rollAt, forceRollAt }) {
  if (!(rollAt > 0 && rollAt < forceRollAt && forceRollAt <= 1)) {
    throw new Error(`bad roll fractions: rollAt=${rollAt} forceRollAt=${forceRollAt}`);
  }

  let serverFrames = 0;     // frames the CURRENT server session has accepted
  let repOffset = 0;        // reps completed in earlier, already-closed segments
  let closedReps = [];      // per-rep records from earlier segments
  let lastResponse = null;  // latest response for the CURRENT segment
  let segments = 1;

  const max = () => {
    const m = getMaxFrames();
    return Number.isFinite(m) && m > 0 ? m : null;
  };

  return {
    /** How many more frames the current session can take (Infinity when the cap is unknown). */
    capacity() {
      const m = max();
      return m === null ? Infinity : Math.max(0, m - serverFrames);
    },

    /**
     * Should we start a fresh server session before sending `pending` more frames?
     *  - at `rollAt` of the cap: roll, but only between reps
     *  - at `forceRollAt`, or if the session is already full: roll regardless — splitting one
     *    rep is better than a 413 that kills the whole set
     */
    shouldRoll(pending) {
      const m = max();
      if (m === null || serverFrames === 0) return false; // nothing to roll away from
      const projected = serverFrames + pending;
      if (serverFrames >= m || projected >= m * forceRollAt) return true;
      const betweenReps = !!lastResponse && lastResponse.rep_in_progress === false;
      return projected >= m * rollAt && betweenReps;
    },

    /** Record a successful POST of `sentCount` frames into the current session. */
    acknowledge(sentCount, response) {
      serverFrames += sentCount;
      lastResponse = response;
    },

    /** Close the current segment, carrying its reps forward. */
    roll() {
      if (lastResponse) {
        repOffset += lastResponse.rep_count || 0;
        closedReps = closedReps.concat(lastResponse.reps || []);
      }
      serverFrames = 0;
      lastResponse = null;
      segments += 1;
    },

    totalReps() {
      return repOffset + ((lastResponse && lastResponse.rep_count) || 0);
    },

    allReps() {
      return closedReps.concat((lastResponse && lastResponse.reps) || []);
    },

    get lastResponse() { return lastResponse; },
    get segments() { return segments; },
    get serverFrames() { return serverFrames; },
  };
}

/**
 * Bound the not-yet-delivered frame queue. During a long outage the camera keeps producing ~30
 * frames/s; left unbounded, every retry sends a larger body than the last until the request
 * itself is too big to survive. Frames older than one whole server session can never be scored
 * in a single request anyway, so the oldest are dropped past `limit`.
 *
 * @returns {{frames: any[], dropped: number}}
 */
export function boundQueue(frames, limit) {
  if (!Number.isFinite(limit) || limit <= 0 || frames.length <= limit) {
    return { frames, dropped: 0 };
  }
  const dropped = frames.length - limit;
  return { frames: frames.slice(dropped), dropped };
}
