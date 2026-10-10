"""Generic static implementation-binding risks and revision evidence fingerprint."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


_PATTERNS = {
    "historical_patch_dependency": r"(?:test_patch\.patch|historical_tests/test_patch)",
    "exact_mock_call_arguments": r"(?:\.mock\.calls\s*\[|toHaveBeenCalledWith\s*\()",
    "snapshot_shape": r"(?:toMatchSnapshot\s*\(|toMatchInlineSnapshot\s*\()",
    "css_or_dom_shape": r"(?:className|querySelector\s*\(|firstElementChild|parentElement|previousElementSibling)",
    "test_only_locator": r"(?:getByTestId|queryByTestId|data-testid)",
    "global_ui_cardinality": r"(?:screen\.getAllByRole|screen\.getAllByText|document\.querySelectorAll)[\s\S]{0,500}?\.toHaveLength\s*\(\s*\d+\s*\)",
    "oracle_guided_selection": r"if\s+\w+\s+is\s+not\s+None\s+and\s+\w+\s*!=\s*\w+\s*:\s*continue",
    "exact_exception_type": r"(?:instanceof\s+[A-Za-z_$][\w$]*Error\b|isinstance\s*\([^,]+,\s*[A-Za-z_]\w*Error\b|pytest\.raises\s*\(\s*[A-Za-z_]\w*Error\b|\.name\s*(?:===|==)\s*['\"][A-Za-z_]\w*Error\b|toThrow\s*\(\s*[A-Za-z_$][\w$]*Error\b|\b(?:[A-Za-z_$][\w$]*\.)?(?:assert|expect|raise|reject|throw)[A-Za-z_$\w]*\s*\(\s*[A-Za-z_$][\w$]*Error\s*,)",
    # These are advisory signals. A count, directory level, or universal
    # assertion can be correct when P explicitly fixes it; the focused Judge
    # must test a concrete P-conforming counterfactual before accepting it.
    "exact_observation_count": r"(?:\bassert\s+(?:len\s*\([^\n)]{1,120}\)|[A-Za-z_]\w*(?:count|calls|length|size))\s*(?:==|is)\s*\d+\b|\.toHaveLength\s*\(\s*\d+\s*\))",
    "direct_child_file_scan": r"(?:\.iterdir\s*\(|\bos\.listdir\s*\(|\.glob\s*\(\s*['\"]\*['\"]\s*\))",
    "all_observations_required": r"(?:\bassert\s+all\s*\(|\.every\s*\(|\bfor\s+(?P<item>[A-Za-z_]\w*)\s+in\s+[A-Za-z_]\w*\s*:\s*(?:[^\n]*\n){0,5}\s*assert\s+(?P=item)\b|\bfor\s+[A-Za-z_]\w*\s+in\s+[A-Z][A-Z_0-9]+\s*:\s*(?:[^\n]*\n){0,6}\s*assert\s+[A-Za-z_]\w*\s*\()",
    "intermediate_value_exactness": r"\bassert\s+(?:[A-Za-z_]\w*(?:metadata|style|classification|shebang|header)\w*|(?:metadata|style|classification|shebang|header)\w*)\s*==",
    "whole_result_exactness": r"(?:\bassert\s+[A-Za-z_]\w*(?:\[[^\n\]]{1,120}\])?\s*==\s*[{\[]|\.toEqual\s*\(\s*[{\[]|\b(?:assert|return)\s+set\s*\([^\n)]{1,140}\)\s*==\s*\{|\bassert\s+[^\n]{0,200}?\s*==\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\s*\([^\n)]*\)|\bassert\s+[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\s*\([^\n)]*\)\s*==\s*[A-Za-z_]\w*)",
    "default_output_subset": r"\bdef\s+test_[A-Za-z_]*?(?:default|without|no_query|visible_only)[A-Za-z_]*\s*\([^\n]*\)\s*:[\s\S]{0,1500}?\bassert\s+[A-Za-z_]\w*\s+in\s+(?:_lines\s*\([^\n)]*\)|lines\b)",
    "exact_numeric_boundary": r"\bassert\s+[^\n]{0,180}?\b[A-Za-z_]\w*(?:match|compare|score|rank|similarity|threshold)\w*\s*\([^\n]{0,180}?,\s*\d+(?:\.\d+)?\s*\)(?=\s*(?:is\b|==|!=|>=|<=|>|<|$))",
    "self_calibrated_threshold": r"\bwhile\s+(?:not\s+)?[A-Za-z_]\w*(?:match|compare|score|rank)\w*\s*\([^\n]{0,180}?,\s*(?:low|high|threshold)\s*\)",
    "finite_option_vocabulary": r"(?m)^\s*_[A-Z][A-Z_]*(?:SEEDS|PREFIXES)\s*=\s*\(",
    "subcomponent_location_binding": r"\brender_template\s*\(\s*[\x27\x22][^\x27\x22\n]{1,160}/[^\x27\x22\n]{1,160}[\x27\x22]",
    "reflective_entrypoint_scope": r"(?:pkgutil\.walk_packages|inspect\.getmembers)\s*\(",
    "public_type_origin_binding": r"(?:\b[A-Za-z_]\w*\.__module__\b|\b[A-Za-z_]\w*\.__name__\b)",
    # Advisory signal: a private repository helper may have become the test's
    # effective product API. The focused Judge distinguishes it from fixture
    # helpers and documented contracts using the public-behavior counterfactual.
    "private_entrypoint_call": r"(?m)(?:\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\.)_[A-Za-z]\w*\s*\(|^\s*from\s+[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s+import\s+[^\n#]*\b_[A-Za-z_]\w*\b",
    "legacy_alias_representation": r"(?:\b(?:is_builtin_int|is_canonical_member)\b|\btype\s*\([^\n]{1,100}\)\s+is\s+int\b)",
    "permutation_invariant_mapping": r"\b(?:semantic_match|member_match|alias_match)\s*=\s*any\s*\(",
    "decision_branch_binding": r"\bassert\s+(?:unarchived|changed|extracted|updated|needs_update|[A-Za-z_]\w*(?:unarchived|changed|extracted|updated|needs_update)\w*)\s+is\s+(?:True|False)\b",
    "derived_identifier_type_binding": r"\bidentif(?:ier|ication)\b[\s\S]{0,1500}\bisinstance\s*\([^,\n]{1,100},\s*str\s*\)",
    "serialization_shape_assertion": r"\bassert\s+[^\n]{0,160}(?:[\x27\x22][|*,:;][\x27\x22]\s+in\s+|\.split\s*\(\s*[\x27\x22][|,:;][\x27\x22]|\.startswith\s*\(\s*[\x27\x22][*#][\x27\x22]|[\x27\x22]\\n[\x27\x22]\s+not\s+in\s+)",
}


def _sample(text: str, match: re.Match[str]) -> str:
    return text[max(0, match.start() - 120):min(len(text), match.end() + 220)]


def _multiple_null_constructor_calls(text: str) -> list[re.Match[str]]:
    """Find constructor/factory calls supplied with several explicit nulls.

    These calls can make an undocumented dependency-injection shape part of a
    verifier. The signal is advisory: the focused Judge decides whether the
    nulls are ordinary input data or an unauthorized construction constraint.
    """
    callee = re.compile(r"(?:\bnew\s+)?\b[A-Z][A-Za-z0-9_$]*(?:\.[A-Z][A-Za-z0-9_$]*)*\s*\(")
    null_value = re.compile(r"\b(?:None|null|nil|NULL)\b")
    found: list[re.Match[str]] = []
    for match in callee.finditer(text):
        opening = match.end() - 1
        depth = 1
        quote = ""
        escaped = False
        end = opening + 1
        while end < min(len(text), opening + 2000) and depth:
            char = text[end]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char in {"'", '"', "`"}:
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            end += 1
        if depth == 0 and len(null_value.findall(text[opening + 1:end - 1])) >= 3:
            found.append(text[match.start():end])
    return found


def binding_signals(tests: dict[str, dict[str, object]]) -> list[dict[str, str]]:
    """Expose advisory risk sites for an adversarial, P-grounded review."""
    signals: list[dict[str, str]] = []
    for name, data in tests.items():
        text = str(data.get("head", ""))
        for kind, pattern in _PATTERNS.items():
            flags = re.IGNORECASE if kind == "exact_exception_type" else 0
            if kind == "exact_numeric_boundary":
                # The trailing `$` must match an assertion line within a test file.
                flags |= re.MULTILINE
            match = re.search(pattern, text, flags)
            if match:
                signals.append({"file": name, "kind": kind, "sample": _sample(text, match)})
        for call in _multiple_null_constructor_calls(text):
            match = re.search(re.escape(call), text)
            if match:
                signals.append({"file": name, "kind": "multiple_null_constructor_dependencies",
                                "sample": _sample(text, match)})
        # A claimed decision/registration result followed by an observable
        # downstream action can be a false proof when the test double performs
        # that action unconditionally (or defaults to acting on all inputs).
        # This is deliberately advisory: the focused Judge traces control flow
        # and the fake's behavior before deciding whether the assertion binds.
        decision_then_action = re.search(
            r"\bassert\s+(?:not\s+)?(?:[A-Za-z_]\w*(?:unarchived|changed|registered|updated|selected|included|valid|ready)|unarchived|changed|registered|updated|selected|included|valid|ready)"
            r"[A-Za-z_0-9]*\s*(?:is\s+(?:True|False)|==\s*(?:True|False|0|1))"
            r"[\s\S]{0,1800}?\b[A-Za-z_]\w*\.(?:extract|unarchive|apply|commit|persist|publish|save|send|update|write|delete)\s*\(",
            text, re.IGNORECASE,
        )
        if decision_then_action:
            signals.append({"file": name, "kind": "unconditional_downstream_side_effect",
                            "sample": _sample(text, decision_then_action)})
        # Independently authored parse fixtures may freeze one historical wire
        # syntax even when P requires only a stable round trip. Flag the pair
        # of a literal fixture and a parser call for a P-grounded counterfactual.
        parser_call = re.compile(
            r"\b(?:from_(?:markdown|json|yaml|text|csv|xml)|parse(?:_[A-Za-z_]\w*)?|"
            r"deserialize(?:_[A-Za-z_]\w*)?|loads?)\s*\("
        )
        fixture = re.search(
            r"\b(?:line|text|input|fixture|sample)\w*\s*=\s*[rbuf]*['\"][^\n]{1,240}",
            text,
        )
        direct = re.search(
            r"\b(?:from_(?:markdown|json|yaml|text|csv|xml)|parse(?:_[A-Za-z_]\w*)?|"
            r"deserialize(?:_[A-Za-z_]\w*)?|loads?)\s*\(\s*[rbuf]*['\"][^\n]{1,240}",
            text,
        )
        if direct and any(mark in direct.group() for mark in ("|", "{", "<", ":")):
            signals.append({"file": name, "kind": "fixed_serialization_fixture", "sample": _sample(text, direct)})
        elif fixture and any(mark in fixture.group() for mark in ("|", "{", "<", ":")):
            nearby = text[fixture.end():fixture.end() + 500]
            if parser_call.search(nearby):
                signals.append({"file": name, "kind": "fixed_serialization_fixture", "sample": _sample(text, fixture)})
        # A test subclass can add an otherwise nonexistent hook and then
        # require production code to call that hook. Flag the fixture boundary
        # for a P-only review; a subclass by itself is not a defect.
        fixture_subclass = re.search(
            r"\bclass\s+_[A-Za-z_]\w*\s*\(\s*[A-Za-z_][\w.]*\s*\)\s*:",
            text,
        )
        if fixture_subclass:
            nearby = text[fixture_subclass.end():fixture_subclass.end() + 1600]
            added_hook = re.search(r"(?m)^    def\s+(?!__)[A-Za-z_]\w*\s*\(", nearby)
            if added_hook:
                signals.append({"file": name, "kind": "fixture_extension_hook", "sample": _sample(text, fixture_subclass)})
        # An AST walk can find a valid-looking nested record inside an
        # arbitrary wrapper around an otherwise flat representation. The
        # focused review checks the whole public shape, not just descendants.
        representation_walk = re.search(r"\bast\.walk\s*\(", text)
        named_wrapper = re.search(
            r"(?:\bnot\s+in\s+_[A-Z_]*WRAPPER[A-Z_]*\b|"
            r"\b(?:wrapped|container)\s*=\s*True\b)", text
        )
        flat_shape = re.search(r"(?:flat|bare)[_A-Za-z0-9]*(?:sequence|record|wrapper)", text)
        if flat_shape and (representation_walk or named_wrapper):
            match = representation_walk or named_wrapper
            signals.append({"file": name, "kind": "representation_wrapper_acceptance",
                            "sample": _sample(text, match)})
        # A fixture method returning a preloaded constructor value can bypass
        # the product's real acquisition path. Review whether P requires that
        # provider to run as well as the downstream renderer/consumer.
        preloaded_provider = re.search(
            r"\bclass\s+_[A-Za-z]\w*(?:\([^)]*\))?\s*:[\s\S]{0,3000}?"
            r"\bdef\s+__init__\s*\([^)]*\)\s*:\s*\n[ \t]+self\.(?P<field>[A-Za-z_]\w*)\s*=\s*[A-Za-z_]\w*"
            r"[\s\S]{0,2000}?\bdef\s+(?!__)[A-Za-z_]\w*\s*\([^)]*\)\s*:\s*\n[ \t]+return\s+self\.(?P=field)\b",
            text,
        )
        if preloaded_provider:
            signals.append({"file": name, "kind": "fixture_preloaded_provider", "sample": _sample(text, preloaded_provider)})
        # A finite text predicate is a possible false-positive and false-negative
        # source when P asks for an appropriate user-facing message but leaves
        # its wording open. Detect the combination, not arbitrary regex use.
        # Require an executable assertion over user-facing text as well as a
        # finite predicate. Parser helpers may search stdout for pytest counts;
        # those searches do not constrain the product's message wording.
        message_assertion = re.search(
            r"\bassert\s+[^\n]{0,180}(?:\b\w*(?:message|warning|notice)\w*\b|\b\w+\.text\b)",
            text, re.IGNORECASE,
        )
        if message_assertion:
            match = re.search(
                r"(?:\bre\.search\s*\(|\b[A-Za-z_]*PATTERNS\b|\.test\s*\(|"
                r"\bany\s*\(\s*\w+\s+in\s+\w+\s+for\s+\w+\s+in\s+\w+)",
                text,
            )
            if match:
                signals.append({"file": name, "kind": "message_lexical_gate", "sample": _sample(text, match)})
        # A truthy user-message check can accept arbitrary filler text. Flag
        # the executable assertion even when no finite word list is present;
        # the focused review will decide from P whether semantic content matters.
        nonempty_message = re.search(
            r"\bassert\s+(?:[A-Za-z_]\w*(?:messages?|errors?|warnings?)\w*|"
            r"[A-Za-z_]\w*\.text(?:\s+and\s+[A-Za-z_]\w*\.text\.strip\s*\(\s*\))?)\s*(?:,|\n|$)",
            text,
        )
        if nonempty_message and re.search(r"\b(?:message|error|warning|notice)\b|\.text\b", text, re.IGNORECASE):
            signals.append({"file": name, "kind": "message_nonempty_only", "sample": _sample(text, nonempty_message)})
        # A verifier may need an executable wrapper, but moving or replacing a
        # system binary is a harness side effect. The focused review decides
        # whether that mutation is necessary and isolated.
        system_root = re.search(
            r"(?:['\"]/(?:usr/(?:local/)?)?bin(?:/|['\"])|"
            r"os\.path\.join\(\s*os\.sep\s*,\s*['\"](?:usr|etc)['\"]\s*,\s*['\"](?:bin|sbin)['\"])",
            text,
        )
        if system_root:
            match = re.search(r"(?:shutil\.move\s*\(|os\.(?:rename|replace|unlink|remove)\s*\()", text)
            if match and (name.startswith("test") or "test_" in name or "functional" in name):
                signals.append({"file": name, "kind": "system_path_mutation", "sample": _sample(text, match)})
    return signals


def is_verifier_source(path: Path, tests_root: Path) -> bool:
    """Ignore generated Python/test caches when reviewing authored verifier files."""
    if not path.is_file():
        return False
    relative = path.relative_to(tests_root)
    if any(part in {"__pycache__", ".pytest_cache", ".hypothesis"}
           for part in relative.parts[:-1]):
        return False
    return path.suffix not in {".pyc", ".pyo"}


def revision_evidence_fingerprint(tests_root: Path) -> str:
    """Bind a semantic verdict to both verifier bytes and detected risks."""
    tests: dict[str, dict[str, object]] = {}
    file_hashes: dict[str, str] = {}
    for file in sorted(tests_root.rglob("*")):
        if not is_verifier_source(file, tests_root):
            continue
        name = str(file.relative_to(tests_root))
        data = file.read_bytes()
        file_hashes[name] = hashlib.sha256(data).hexdigest()
        tests[name] = {"head": data[:20000].decode("utf-8", errors="replace")}
    evidence = {"files": file_hashes, "signals": binding_signals(tests)}
    encoded = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
