"""Official mini-SWE-agent sessions used by the Converter and QA generators.

The outer workflow is controlled by orchestrator.py.  This module owns only the
inner mini-SWE loop: model request, bash execution, observation, next turn and
the explicit submission signal.
"""
from __future__ import annotations

import json
import fcntl
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests

from minisweagent.agents.default import DefaultAgent
from minisweagent.exceptions import Submitted
from minisweagent.models.utils.actions_toolcall import (
    BASH_TOOL,
    format_toolcall_observation_messages,
    parse_toolcall_actions,
)

from .workspace_tools import WorkspaceTools
from ..conversion_schema import (
    REQUIRED_F2P_FIELDS,
    UNRESOLVED_EXACT_VALUES,
    UNRESOLVED_MARKER,
    classification_errors,
    trace_disposition_errors,
    unresolved_trace_errors,
)


def _docker_validation_command(command: str) -> str:
    """Map known container paths for lexical validation, never for execution.

    Docker owns these paths.  In particular, /tmp is container-local scratch
    used by language test runners; treating it as a forbidden host path made
    legitimate Jest/pytest probes fail before reaching Docker.  Parent
    traversal and every other absolute path remain rejected by WorkspaceTools.
    """
    for mount in ("workspace", "app", "testbed", "solution", "tmp"):
        command = re.sub(
            rf"(?<![A-Za-z0-9_/.])/{mount}(?=/|\b)", mount, command,
        )
    return command


SUBMIT_SENTINEL = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

CONVERTER_SKELETON_FILES = (
    "conversion_trace.json",
    "functional_specification.md",
    "self_review.md",
    "manifest.json",
    "tests/test.sh",
    "tests/run_script.sh",
    "tests/parser.py",
    "tests/config.json",
)

OBSERVATION_TEMPLATE = (
    "{% if output.exception_info %}<exception>{{output.exception_info}}</exception>\n{% endif %}"
    "<returncode>{{output.returncode}}</returncode>\n<output>\n{{output.output}}</output>"
)

# Keep enough recent context for the agent to continue its current session while
# preventing large repository listings/test logs from growing a repair request
# past the endpoint's context window.  The official mini-SWE loop still owns
# the conversation; this is only an adapter-side request bound.
MAX_REQUEST_CHARS = 180_000
MAX_MESSAGE_CHARS = 50_000


def _clip_message_content(value: Any, limit: int = MAX_MESSAGE_CHARS) -> Any:
    if not isinstance(value, str) or len(value) <= limit:
        return value
    head = limit // 2
    tail = limit - head
    return (
        value[:head]
        + "\n...[older observation clipped by the model adapter]...\n"
        + value[-tail:]
    )


def _bounded_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bound request size while preserving the task and recent turn groups."""
    prepared = []
    for message in messages:
        item = {key: value for key, value in message.items() if key != "extra"}
        if "content" in item:
            item["content"] = _clip_message_content(item["content"])
        prepared.append(item)

    if len(json.dumps(prepared, ensure_ascii=False)) <= MAX_REQUEST_CHARS:
        return prepared

    # The first two messages are the system prompt and the task.  Keep them,
    # then retain the newest assistant/tool groups so tool-call history remains
    # structurally valid for the OpenAI-compatible endpoint.
    prefix = prepared[:2]
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for message in prepared[2:]:
        if message.get("role") == "assistant" and current:
            groups.append(current)
            current = []
        current.append(message)
    if current:
        groups.append(current)

    kept: list[list[dict[str, Any]]] = []
    size = len(json.dumps(prefix, ensure_ascii=False))
    for group in reversed(groups):
        group_size = len(json.dumps(group, ensure_ascii=False))
        if kept and size + group_size > MAX_REQUEST_CHARS:
            break
        if not kept and size + group_size > MAX_REQUEST_CHARS:
            # The current observation alone is too large; the per-message clip
            # above guarantees this branch still fits in normal operation.
            continue
        kept.append(group)
        size += group_size

    bounded = prefix + [message for group in reversed(kept) for message in group]
    return bounded


class OpenAICompatibleMiniModel:
    """Minimal official-mini Model protocol adapter for OpenAI-compatible APIs."""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: int, max_tokens: int):
        endpoint = base_url.rstrip("/")
        self.endpoint = endpoint if endpoint.endswith("/chat/completions") else endpoint + "/chat/completions"
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.session = requests.Session()
        self.session.trust_env = False

    def query(self, messages: list[dict[str, Any]], **kwargs) -> dict:
        prepared = _bounded_messages(messages)
        request = {
            "model": self.model_name,
            "messages": prepared,
            "tools": [BASH_TOOL],
            "tool_choice": "auto",
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = None
        for attempt in range(6):
            response = self.session.post(
                self.endpoint,
                headers=headers,
                json=request,
                timeout=self.timeout,
            )
            if response.status_code != 429 or attempt == 5:
                break
            retry_after = response.headers.get("Retry-After")
            try:
                delay = max(1.0, min(60.0, float(retry_after))) if retry_after else 2.0 ** attempt
            except ValueError:
                delay = 2.0 ** attempt
            time.sleep(min(60.0, delay))
        if not response.ok:
            raise RuntimeError(f"model API returned HTTP {response.status_code}: {response.text[:2000]}")
        document = response.json()
        message = dict(document["choices"][0]["message"])
        calls = message.get("tool_calls") or []
        call_objects = [
            SimpleNamespace(
                id=call.get("id"),
                function=SimpleNamespace(
                    name=(call.get("function") or {}).get("name"),
                    arguments=(call.get("function") or {}).get("arguments") or "{}",
                ),
            )
            for call in calls
        ]
        actions = parse_toolcall_actions(
            call_objects,
            format_error_template=(
                "Every response must contain a valid bash tool call. "
                f"If complete, execute {SUBMIT_SENTINEL}."
            ),
        )
        message["extra"] = {
            "actions": actions,
            "response": document,
            "cost": 0.0,
            "timestamp": time.time(),
        }
        return message

    def format_message(self, **kwargs) -> dict:
        return dict(kwargs)

    def format_observation_messages(
        self, message: dict, outputs: list[dict], template_vars: dict | None = None,
    ) -> list[dict]:
        return format_toolcall_observation_messages(
            actions=message.get("extra", {}).get("actions", []),
            outputs=outputs,
            observation_template=OBSERVATION_TEMPLATE,
            template_vars=template_vars,
        )

    def get_template_vars(self, **kwargs) -> dict[str, Any]:
        return {"model_name": self.model_name, **kwargs}

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "model": self.model_name,
                    "model_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                }
            }
        }


class MiniSWEEnvironment:
    """Docker-backed bash environment with explicit role mounts."""

    def __init__(
        self,
        sandbox: Path,
        docker_image: str,
        mounts: list[tuple[Path, str, str]],
        timeout: int,
        role: str = "default",
        progress_reminder_step: int | None = None,
        artifact_checkpoint_step: int | None = None,
        artifact_finalization_step: int | None = None,
        formal_output_root: Path | None = None,
        required_f2p_count: int | None = None,
        run_as_root: bool = False,
    ):
        self.sandbox = sandbox.resolve()
        self.docker_image = docker_image
        self.mounts = mounts
        self.tools = WorkspaceTools(self.sandbox, ["."], ["."], timeout=timeout)
        self.container_name = f"mini-swe-{uuid.uuid4().hex[:12]}"
        self.timeout = timeout
        self.cwd = "."
        self.started = False
        self.role = role
        self.run_as_root = run_as_root
        self.action_count = 0
        self.progress_reminder_step = progress_reminder_step
        self.progress_reminder_sent = False
        self.artifact_checkpoint_step = artifact_checkpoint_step
        self.artifact_finalization_step = artifact_finalization_step
        self.formal_output_root = formal_output_root.resolve() if formal_output_root is not None else self.sandbox / "solution"
        self.required_f2p_count = required_f2p_count
        # Repair sessions seed /solution with a complete prior revision.  The
        # controller can arm this checkpoint after construction so repeated
        # repository reading cannot consume the whole repair budget without a
        # single formal edit.
        self.repair_write_checkpoint_step: int | None = None
        self.formal_output_baseline: str | None = None
        self.verifier_write_checkpoint_step: int | None = None
        self.verifier_output_baseline: str | None = None
        self.sync_callback = None

    def _mount_args(self) -> list[str]:
        args: list[str] = []
        for source, target, mode in self.mounts:
            args.extend(["-v", f"{source.resolve()}:{target}:{mode}"])
        return args

    def start(self) -> None:
        if self.started:
            return
        command = ["docker", "run", "-d", "--rm", "--network", "none"]
        if not self.run_as_root:
            command += ["--user", f"{os.getuid()}:{os.getgid()}"]
        command += [
            "--name", self.container_name, "--entrypoint", "/bin/bash",
            *self._mount_args(), "-w", "/workspace", self.docker_image,
            "-c",
            # Keep one canonical bind mount for each writable role output.
            # Relative paths used by the agent resolve through these links,
            # avoiding duplicate bind mounts at /workspace/* whose behavior
            # differs across Docker/NFS combinations.
            "mkdir -p /workspace; "
            "ln -sfn /app /workspace/app; "
            "rm -rf /workspace/solution; "
            "ln -s /solution /workspace/solution; "
            "while true; do sleep 3600; done",
        ]
        try:
            result = subprocess.run(
                command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=self.timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # ``docker run -d`` can time out after the daemon has created the
            # container.  Remove that best-effort orphan immediately; otherwise
            # an interrupted Converter accumulates containers and makes later
            # retries look like model or verifier failures.
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self.container_name],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    timeout=30, check=False,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass
            raise RuntimeError(
                f"failed to start mini-SWE container within {self.timeout}s; "
                "any partially-created container was scheduled for cleanup"
            ) from exc
        if result.returncode != 0:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self.container_name],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    timeout=30, check=False,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass
            raise RuntimeError(f"failed to start mini-SWE container: {result.stdout[-2000:]}")
        self.started = True

    def close(self) -> None:
        if not self.started:
            return
        try:
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=30, check=False,
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # A stuck Docker cleanup must not discard the agent's submitted
            # artifacts.  The container is best-effort cleanup; the caller
            # still owns the mounted sandbox and can sync it safely.
            pass
        except BaseException:
            # Do not let cancellation of a worker strand the workflow in the
            # cleanup path.  The caller still records the interrupted run and
            # the next batch invocation uses a fresh container name.
            pass
        self.started = False

    def execute(self, action: dict, cwd: str = "") -> dict[str, Any]:
        command = str(action.get("command") or "")
        checkpoint_issues = _converter_checkpoint_issues(self.formal_output_root, self.required_f2p_count)
        artifact_reminder = (
            self.role == "converter"
            and self.artifact_checkpoint_step is not None
            and self.action_count >= self.artifact_checkpoint_step
            and checkpoint_issues
            and not _looks_like_formal_mutation(command)
        )
        finalization_issues = _converter_finalization_issues(self.formal_output_root)
        finalization_reminder = (
            self.role == "converter"
            and self.artifact_finalization_step is not None
            and self.action_count >= self.artifact_finalization_step
            and finalization_issues
            and not _looks_like_formal_mutation(command)
        )
        if self.role == "converter" and getattr(self, "partial_missing_baseline", None) is not None:
            missing_now = set(_missing_converter_skeleton(self.formal_output_root))
            if len(missing_now) < len(self.partial_missing_baseline):
                self.partial_missing_baseline = missing_now
                self.partial_progress_action = self.action_count
            if (
                missing_now
                and self.action_count - self.partial_progress_action >= self.partial_write_interval
                and not _looks_like_formal_mutation(command)
            ):
                self.action_count += 1
                if self.sync_callback is not None:
                    self.sync_callback()
                return {
                    "output": (
                        "[CONTROLLER PARTIAL ARTIFACT CHECKPOINT] The number of missing formal files "
                        "has not decreased. Write one of these files under solution/ before more "
                        "repository exploration: " + ", ".join(sorted(missing_now))
                    ),
                    "returncode": 2,
                    "exception_info": "",
                }
        if (
            self.role == "converter"
            and self.repair_write_checkpoint_step is not None
            and self.formal_output_baseline is not None
            and self.action_count >= self.repair_write_checkpoint_step
            and _formal_output_digest(self.formal_output_root) == self.formal_output_baseline
            and not _looks_like_formal_mutation(command)
        ):
            self.action_count += 1
            if self.sync_callback is not None:
                self.sync_callback()
            return {
                "output": (
                    "[CONTROLLER REPAIR CHECKPOINT] The seeded revision has not changed. "
                    "Repository exploration is paused. The next command must edit one or "
                    "more formal files under solution/ to address repair_feedback.json; "
                    "continue focused inspection only after that edit."
                ),
                "returncode": 2,
                "exception_info": "",
            }
        if (
            self.role == "converter"
            and getattr(self, "verifier_write_checkpoint_step", None) is not None
            and getattr(self, "verifier_output_baseline", None) is not None
            and self.action_count >= self.verifier_write_checkpoint_step
            and _verifier_test_digest(self.formal_output_root / "tests") == self.verifier_output_baseline
            and not _looks_like_verifier_mutation(command)
        ):
            self.action_count += 1
            if self.sync_callback is not None:
                self.sync_callback()
            return {
                "output": (
                    "[CONTROLLER VERIFIER CHECKPOINT] The verifier tests are unchanged. "
                    "Editing only self_review.md or conversion_trace.json does not resolve "
                    "an implementation-binding finding. The next command must edit "
                    "solution/tests/; resume focused inspection after that edit."
                ),
                "returncode": 2,
                "exception_info": "",
            }
        try:
            # The sandbox is a Docker container. Permit only its explicit mount
            # points while retaining the path/traversal checks from WorkspaceTools.
            checked_command = _docker_validation_command(command)
            _, _, timeout = self.tools.validate_bash(
                {"command": checked_command, "cwd": self.cwd or cwd},
                reject_hidden=False,
            )
            if not self.started:
                self.start()
            # A timeout on the host-side `docker exec` client does not
            # necessarily terminate the command inside the long-lived agent
            # container.  Wrap the command in the container as well so a
            # stalled package install or test cannot survive into the next QA
            # attempt and consume resources indefinitely.
            bounded_command = (
                f"timeout --signal=TERM --kill-after=5s {max(timeout, 1)}s "
                f"/bin/bash -c {shlex.quote(command)}"
            )
            completed = subprocess.run(
                [
                    "docker", "exec", "-w", "/workspace", self.container_name,
                    "/bin/bash", "-c", bounded_command,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            output = completed.stdout
            returncode = completed.returncode
            error = ""
        except Exception as exc:
            output = ""
            returncode = 1
            error = f"{type(exc).__name__}: {exc}"

        self.action_count += 1
        if self.sync_callback is not None:
            self.sync_callback()
        if artifact_reminder:
            # Do not block evidence inspection before the agent has enough
            # context to account for every historical F2P. Submission and
            # deterministic validation still require complete artifacts.
            output += (
                "\n[CONTROLLER ARTIFACT REMINDER] Write the complete revision "
                "under solution/ soon. Outstanding: " + "; ".join(checkpoint_issues) + "\n"
            )
        if finalization_reminder:
            # A complex task can still need a focused evidence read after the
            # deadline. Blocking that read traps the agent in repeated tool
            # errors; final validation remains the hard gate.
            output += (
                "\n[CONTROLLER FINALIZATION REMINDER] Finish the formal revision "
                "under solution/ promptly. Outstanding: " + "; ".join(finalization_issues) + "\n"
            )
        if (
            self.role == "converter"
            and not self.progress_reminder_sent
            and self.progress_reminder_step is not None
            and self.action_count >= self.progress_reminder_step
            and not _has_initial_verifier_artifact(self.formal_output_root)
        ):
            output += (
                "\n[CONTROLLER REMINDER] No executable verifier artifact has been written yet. "
                "Use the F2P intents and observable surfaces already established to write an "
                "initial verifier and conversion_trace.json now; you may continue revising it.\n"
            )
            self.progress_reminder_sent = True

        if returncode == 0 and output.lstrip().splitlines()[:1] == [SUBMIT_SENTINEL]:
            if self.role == "converter":
                submission_issues = [
                    "missing file " + name for name in _missing_converter_skeleton(self.formal_output_root)
                ] + _converter_finalization_issues(self.formal_output_root)
                if submission_issues:
                    return {
                        "output": (
                            "[CONTROLLER SUBMISSION CHECK] Fix formal artifact errors before submitting: "
                            + "; ".join(submission_issues[:12])
                        ),
                        "returncode": 2,
                        "exception_info": "",
                    }
            submission = "\n".join(output.lstrip().splitlines()[1:])
            raise Submitted({
                "role": "exit",
                "content": submission,
                "extra": {"exit_status": "Submitted", "submission": submission},
            })
        return {
            "output": output,
            "returncode": returncode,
            "exception_info": error,
        }

    def get_template_vars(self, **kwargs) -> dict[str, Any]:
        return {"cwd": str(self.sandbox), **kwargs}

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "environment": str(self.sandbox),
                    "docker_image": self.docker_image,
                    "environment_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                }
            }
        }


def _converter_scratch_name(name: str) -> bool:
    """Return whether *name* is an exploration artifact, not verifier code.

    Converter sessions are allowed to create temporary experiments while
    exploring a repository.  Those files must never be copied into the
    controller's live snapshot or submitted artifact: a model can otherwise
    accidentally copy an entire unpacked dependency (and make monitoring or
    handoff take minutes).
    """
    lowered = name.lower()
    if lowered in {"node_modules", ".deps", "__pycache__", ".cache", ".npm",
                   ".gold_workspace", ".tmp_app_gold"}:
        return True
    if lowered.startswith(("tmp_", "scratch_", "experiment_")):
        return True
    return lowered.endswith((".tgz", ".tar", ".tar.gz", ".zip"))


def _converter_scratch_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if _converter_scratch_name(name)}


def _iter_converter_files(root: Path):
    """Yield artifact files without recursively traversing scratch trees."""
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if not _converter_scratch_name(name)]
        for filename in filenames:
            if not _converter_scratch_name(filename):
                yield Path(directory) / filename


def _missing_converter_skeleton(root: Path) -> list[str]:
    """Return required formal artifacts not yet materialized by Converter."""
    return [
        relative
        for relative in CONVERTER_SKELETON_FILES
        if not (root / relative).is_file() or (root / relative).stat().st_size == 0
    ]


def _converter_checkpoint_issues(root: Path, required_f2p_count: int | None) -> list[str]:
    issues = ["missing file " + value for value in _missing_converter_skeleton(root)]
    if required_f2p_count is None:
        return issues
    trace_path = root / "conversion_trace.json"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if trace_path.is_file():
            issues.append("conversion_trace.json must be valid JSON")
        return issues
    rows = trace.get("f2p_accounting") if isinstance(trace, dict) else None
    actual = len(rows) if isinstance(rows, list) else 0
    if actual != required_f2p_count:
        issues.append(
            f"conversion_trace.json must inventory all {required_f2p_count} historical F2P rows (currently {actual})"
        )
    return issues


def _converter_finalization_issues(root: Path) -> list[str]:
    """Return unresolved scaffold categories after bounded exploration."""
    issues: list[str] = []
    trace_path = root / "conversion_trace.json"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        trace = None
    trace_issues = unresolved_trace_errors(trace if isinstance(trace, dict) else None)
    if trace_issues:
        issues.append(
            f"conversion_trace.json has {len(trace_issues)} unresolved semantic values "
            f"(examples: {trace_issues[:4]})"
        )
    if isinstance(trace, dict):
        if isinstance(trace.get("f2p_accounting"), list):
            for row in trace["f2p_accounting"]:
                if not isinstance(row, dict):
                    issues.append("F2P accounting row must be an object")
                    continue
                source = str(row.get("source_f2p", "<unknown>"))
                obligations = row.get("behavioral_obligations")
                accounting = row.get("obligation_accounting")
                if isinstance(obligations, list) and isinstance(accounting, list) and len(obligations) != len(accounting):
                    issues.append(
                        f"{source}: obligation_accounting has {len(accounting)} entries for "
                        f"{len(obligations)} behavioral_obligations; provide one entry per obligation"
                    )
                missing = sorted(REQUIRED_F2P_FIELDS - set(row))
                if missing:
                    issues.append(f"{source}: missing required F2P fields: {', '.join(missing)}")
                issues.extend(classification_errors(row))
        issues.extend(trace_disposition_errors(trace))
    for relative in ("functional_specification.md", "self_review.md", "tests/test.sh", "tests/run_script.sh", "tests/parser.py"):
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        normalized = text.strip().casefold()
        if UNRESOLVED_MARKER.search(text) or normalized in UNRESOLVED_EXACT_VALUES or re.search(r"\b(?:todo|tbd)\b", text, re.IGNORECASE):
            issues.append(f"{relative} contains TODO/placeholder text")
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = None
    if isinstance(manifest, dict):
        for field in ("revision", "status"):
            value = str(manifest.get(field, "")).strip()
            normalized = re.sub(r"[_-]+", " ", value).casefold()
            if normalized in UNRESOLVED_EXACT_VALUES or UNRESOLVED_MARKER.search(normalized):
                issues.append(f"manifest.json {field} is unresolved")
    return issues


def _formal_output_digest(root: Path) -> str:
    """Return a stable digest of the eight submitted Converter artifacts."""
    digest = hashlib.sha256()
    for relative in CONVERTER_SKELETON_FILES:
        path = root / relative
        digest.update(relative.encode("utf-8"))
        if not path.is_file():
            digest.update(b"\0missing\0")
            continue
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"\0unreadable\0")
    return digest.hexdigest()


def _verifier_test_digest(tests_root: Path) -> str:
    """Fingerprint executable verifier files separately from explanatory records."""
    digest = hashlib.sha256()
    if not tests_root.is_dir():
        return digest.hexdigest()
    for path in sorted(tests_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        digest.update(str(path.relative_to(tests_root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _looks_like_verifier_mutation(command: str) -> bool:
    return bool(re.search(r"(?:^|[\s/])solution/tests(?:/|\b)", command)) and _looks_like_formal_mutation(command)


def _looks_like_formal_mutation(command: str) -> bool:
    """Recognize a command whose stated purpose is editing formal output.

    This is a workflow guard, not a security boundary. It accepts common shell
    and Python editing forms while rejecting more repository exploration after
    the repair deadline.
    """
    if not re.search(r"(?:^|[\s/])solution(?:/|\b)|/solution(?:/|\b)", command):
        return False
    mutation_patterns = (
        r">{1,2}", r"\btee\b", r"\bcp\b", r"\bmv\b", r"\binstall\b",
        r"\btouch\b", r"\bsed\s+-[^\n]*i", r"\bperl\s+-[^\n]*i",
        r"write_text\s*\(", r"write_bytes\s*\(",
        r"open\s*\([^\n]*(?:['\"]w|['\"]a|mode\s*=\s*['\"][wa])",
    )
    return any(re.search(pattern, command) for pattern in mutation_patterns)


def _has_initial_verifier_artifact(root: Path) -> bool:
    """Recognize a first executable test across supported languages."""
    source_suffixes = {
        ".c", ".cc", ".cpp", ".cjs", ".go", ".java", ".js", ".mjs",
        ".py", ".rb", ".rs", ".sh", ".ts", ".tsx",
    }
    return any(path.suffix.lower() in source_suffixes for path in _iter_converter_files(root))


def _copy_tree(source: Path, target: Path, *, ignore_converter_scratch: bool = False) -> None:
    if source.is_dir():
        # SWE-Pro repositories can intentionally contain broken symlinks in
        # fixtures. Preserve the repository tree verbatim instead of making
        # copytree resolve those links and aborting the whole agent session.
        ignore = _converter_scratch_ignore if ignore_converter_scratch else None
        shutil.copytree(
            source,
            target,
            symlinks=True,
            ignore_dangling_symlinks=True,
            ignore=ignore,
            dirs_exist_ok=True,
        )


def _sync_candidate_output(environment: MiniSWEEnvironment, output_dir: Path | None) -> None:
    """Copy a submitted QA payload out before the container is torn down.

    QA output is bind-mounted for normal operation.  The explicit copy also
    makes handoff robust to runtime mount quirks and supports older role
    images that expose only `/solution`.
    """
    if output_dir is None or not environment.started:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in ("/workspace/solution/.", "/solution/."):
        try:
            result = subprocess.run(
                ["docker", "cp", f"{environment.container_name}:{source}", str(output_dir)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=60, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return


def _write_workspace_layout(sandbox: Path, role: str) -> None:
    """Describe the minimal logical mounts visible to a mini-SWE role."""
    text = f"""# Agent sandbox ({role})

Use relative paths only; host absolute paths and `..` traversal are rejected.

- `app/` — repository root (the image may also expose `/testbed`)
- `evidence/` — read-only Problem Statement and construction evidence
- `reference/` — optional read-only verifier design guidance
- `run/` — read-only controller metadata and repair feedback
- `scratch/` — writable temporary exploration; never submitted
- `solution/` — the only writable formal output directory

The final Harbor instruction is `evidence/problem_statement.md`. The converter-authored `evidence/functional_specification.md` is a non-normative proposal record and is not automatically merged into the instruction.
Do not edit the original task, install dependencies, or create output in the
repository.
"""
    (sandbox / "WORKSPACE_LAYOUT.md").write_text(text, encoding="utf-8")


def _prepare_sandbox(
    workspace: Path, sandbox: Path, role: str, output_dir: Path | None,
    parent_solution: Path | None = None,
) -> list[tuple[Path, str, str]]:
    public = workspace / "public"
    repo = public / "repo"
    if not repo.is_dir():
        raise ValueError(f"missing prepared repository: {repo}")
    mounts: list[tuple[Path, str, str]] = []

    if role == "converter":
        # Evidence is mounted directly read-only.  Copying a workspace that
        # contains the NFS -> /tmp repo symlink made repair rounds fragile and
        # allowed a role shell to accidentally mutate the evidence tree.
        if not public.is_dir() or not (workspace / "restricted").is_dir() or not (workspace / "sealed").is_dir():
            raise ValueError("converter evidence directories are incomplete")
        (sandbox / "scratch").mkdir(parents=True, exist_ok=True)
        _copy_tree(workspace / "verifier", sandbox / "output")
        # Keep old prompt/tool references working while making output/ the
        # canonical revision boundary.
        (sandbox / "verifier").symlink_to(sandbox / "output", target_is_directory=True)
        _write_workspace_layout(sandbox, role)
        _copy_tree(repo, sandbox / "app")
        # The classified run layout exposes controller evidence through
        # relative symlinks. A bind mount would preserve those links but not
        # their host-side targets, so materialize a read-only session snapshot.
        # Missing future artifacts are intentionally skipped.
        shutil.copytree(
            workspace / "run",
            sandbox / "run",
            symlinks=False,
            ignore_dangling_symlinks=True,
            dirs_exist_ok=True,
        )
        framework_runner = PROJECT_ROOT / "src" / "swepro_trans" / "deterministic" / "replay" / "p2p_runner.py"
        if not framework_runner.is_file():
            raise ValueError(f"missing framework P2P runner: {framework_runner}")
        mounts.extend([
            (public, "/workspace/public", "ro"),
            (workspace / "restricted", "/workspace/restricted", "ro"),
            (workspace / "sealed", "/workspace/sealed", "ro"),
            *(([(workspace / "reference", "/workspace/reference", "ro")]
               if (workspace / "reference").is_dir() else [])),
            # Repair rounds need construction evidence produced by the outer
            # controller: reviewer findings, replay logs and blind-solver
            # acceptance evidence.  It is read-only and never replaces the
            # sealed reference boundary.
            (sandbox / "run", "/workspace/run", "ro"),
            (sandbox / "scratch", "/workspace/scratch", "rw"),
            (sandbox / "output", "/workspace/output", "rw"),
            (sandbox / "output", "/workspace/verifier", "rw"),
            (sandbox / "output", "/verifier", "rw"),
            (sandbox / "app", "/app", "rw"),
            (framework_runner, "/workspace/framework/p2p_runner.py", "ro"),
            (sandbox / "WORKSPACE_LAYOUT.md", "/workspace/WORKSPACE_LAYOUT.md", "ro"),
        ])
    elif role in {"solver", "mutator"}:
        (sandbox / "public").mkdir(parents=True, exist_ok=True)
        _write_workspace_layout(sandbox, role)
        shutil.copy2(public / "problem_statement.md", sandbox / "public" / "problem_statement.md")
        _copy_tree(repo, sandbox / "app")
        if output_dir is None:
            raise ValueError("solver session requires output_dir")
        output_dir.mkdir(parents=True, exist_ok=True)
        if role == "mutator":
            if not parent_solution or not parent_solution.is_dir():
                raise ValueError("mutator session requires a known-valid parent solution")
            # Seed the working tree with the known-valid candidate.  The
            # mutator still writes a complete replacement payload under
            # /workspace/solution; the parent is only construction context.
            _copy_tree(parent_solution, sandbox / "app")
            mounts.append((workspace / "verifier", "/workspace/verifier", "ro"))
        mounts.extend([
            (sandbox / "public", "/workspace/public", "ro"),
            (sandbox / "app", "/app", "rw"),
            # `/solution` is the single writable bind mount.  The container
            # bootstrap links relative `solution/` to this path.
            (output_dir, "/solution", "rw"),
            (sandbox / "WORKSPACE_LAYOUT.md", "/workspace/WORKSPACE_LAYOUT.md", "ro"),
        ])
        # Positive QA may use Gold as a construction reference, but never sees
        # the verifier. The final scope keeps the candidate focused on the
        # behavior that the converted task will actually ask the solver to do.
        if role == "solver":
            mounts.extend([
                (workspace / "sealed" / "gold.patch", "/workspace/gold.patch", "ro"),
                (workspace / "verifier" / "instruction_scope.md", "/workspace/instruction_scope.md", "ro"),
            ])
    else:
        raise ValueError(f"unknown mini-SWE role: {role}")
    return mounts


def run_miniswe_session(
    *,
    project_root: Path,
    workspace: Path,
    role: str,
    prompt_path: Path,
    credentials: dict[str, str],
    config: dict[str, Any],
    task: str,
    output_dir: Path | None = None,
    converter_output_dir: Path | None = None,
    trajectory_path: Path | None = None,
    step_limit: int | None = None,
    parent_solution: Path | None = None,
) -> str:
    """Run one fresh official mini-SWE-agent session."""
    if credentials.get("backend", config["model"]["backend"]) != "openai_compatible":
        raise ValueError("official mini-SWE runner currently requires an OpenAI-compatible endpoint")
    sandbox = Path(tempfile.mkdtemp(prefix=f"mini_{role}_", dir="/tmp"))
    environment: MiniSWEEnvironment | None = None
    try:
        mounts = _prepare_sandbox(workspace, sandbox, role, output_dir, parent_solution)
        metadata_path = workspace / "run" / "metadata.json"
        if not metadata_path.is_file():
            raise ValueError("prepared workspace is missing run/metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        docker_image = metadata.get("docker_image")
        if not docker_image:
            raise ValueError("run/metadata.json does not contain docker_image")
        prompt = prompt_path.read_text(encoding="utf-8")
        model = OpenAICompatibleMiniModel(
            base_url=credentials["base_url"],
            api_key=credentials["api_key"],
            model=credentials.get("model") or config["model"]["model"],
            timeout=int(credentials.get("request_timeout_seconds") or config["model"].get("request_timeout_seconds", 600)),
            max_tokens=int(credentials.get("max_tokens") or config["model"].get("max_tokens", 8192)),
        )
        progress_step = max(1, int((step_limit or config["agent"].get("max_turns", 100)) * 0.35))
        environment = MiniSWEEnvironment(
            sandbox,
            str(docker_image),
            mounts,
            timeout=int(config["agent"].get("tool_timeout_seconds", 180)),
            role=role,
            progress_reminder_step=progress_step,
            formal_output_root=(sandbox / "output") if role == "converter" else output_dir,
        )

        def sync_live_snapshot() -> None:
            if role != "converter" or environment.action_count % 5:
                return
            try:
                live = workspace / "artifacts" / "live" / "verifier"
                live.parent.mkdir(parents=True, exist_ok=True)
                # Converter exploration may create scratch symlinks (for
                # example an app view under verifier/). Preserve links during
                # monitoring; resolving them can recursively copy the entire
                # repository and stall the live session.
                _copy_tree(sandbox / "output", live, ignore_converter_scratch=True)
                trace = sandbox / "output" / "conversion_trace.json"
                analyzed = None
                if trace.is_file():
                    try:
                        document = json.loads(trace.read_text(encoding="utf-8"))
                        analyzed = len(document.get("f2p_mappings", []))
                    except (OSError, json.JSONDecodeError):
                        analyzed = "partial"
                (workspace / "artifacts" / "live" / "progress.json").write_text(
                    json.dumps({"role": role, "actions": environment.action_count,
                                "f2p_analyzed": analyzed, "verifier_files": sorted(
                                str(path.relative_to(sandbox / "output"))
                                for path in _iter_converter_files(sandbox / "output")
                                )}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            except (OSError, shutil.Error):
                # Live snapshots are monitoring aids and never block the model.
                return

        environment.sync_callback = sync_live_snapshot
        system = (
            prompt
            + "\n\nEvery response must contain exactly one bash tool call. "
            + f"When complete, execute {SUBMIT_SENTINEL} as a standalone command. "
            + "The standalone command is the only successful completion signal."
        )
        agent = DefaultAgent(
            model,
            environment,
            system_template=system,
            instance_template="{{task}}",
            step_limit=int(step_limit or config["agent"].get("max_turns", 100)),
            cost_limit=0.0,
            max_consecutive_format_errors=int(config["agent"].get("max_consecutive_format_errors", 6)),
            output_path=trajectory_path,
        )
        environment.start()
        result = agent.run(task=task)
        if result.get("exit_status") != "Submitted":
            raise RuntimeError(f"mini-SWE {role} did not submit: {result.get('exit_status')!r}")
        # The Docker environment consumes the standalone sentinel while
        # raising ``Submitted``.  Reattach it at this adapter boundary so the
        # Orchestrator and trajectory consumers have one stable completion
        # protocol instead of mistaking a valid submission for a timeout.
        submission = str(result.get("submission") or "")
        return SUBMIT_SENTINEL + ("\n" + submission if submission else "")
    finally:
        # Sync submitted artifacts before cleanup.  Docker teardown can hang
        # on shared hosts, and must never prevent a completed session from
        # returning its verifier or solution payload.
        if role == "converter" and (sandbox / "output").is_dir():
            # Converter output is staged per session.  The controller commits
            # it to the live verifier only after the session submitted
            # successfully.  This prevents a late/stale model session from
            # overwriting the revision currently being validated.
            target = converter_output_dir or (workspace / "verifier")
            target.mkdir(parents=True, exist_ok=True)
            # Preserve converter-created symlinks on handoff. Resolving a
            # scratch app link here can recurse through a full checkout and
            # make an otherwise valid submission impossible to return.
            _copy_tree(sandbox / "output", target, ignore_converter_scratch=True)
        if environment is not None:
            if role in {"solver", "mutator"}:
                _sync_candidate_output(environment, output_dir)
            environment.close()
        shutil.rmtree(sandbox, ignore_errors=True)


def run_builder(**kwargs) -> str:
    """Backward-compatible alias while old callers are being migrated."""
    kwargs["role"] = "converter"
    return run_miniswe_session(**kwargs)
