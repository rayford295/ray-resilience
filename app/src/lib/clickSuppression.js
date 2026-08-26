/**
 * The click-suppression boundary check for the shift-drag box-select gesture
 * (`app/src/components/MapView.jsx`). Pulled out on its own so it can be
 * tested: the surrounding gesture logic runs against a live MapLibre
 * instance and DOM events, which this repository has no browser interaction
 * harness for — this pure comparison is the one piece of that logic cheap
 * enough to cover without one.
 */

/**
 * Is `now` still within the suppression window that ends at `until`?
 *
 * `until` is a deadline in the same clock as `now` (`performance.now()`),
 * not a boolean: it needs no disarm step on any path, since it is simply
 * false again once time passes it. The initial state is `until = 0`, which
 * this correctly treats as "never suppressed" for any real timestamp,
 * without a special case — `now` only equals 0 at the instant navigation
 * started, before any click could occur.
 */
export function isClickSuppressed(now, until) {
  return now <= until;
}
