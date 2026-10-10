"""The focused gate must account for each risky assertion and reject counterexamples."""
from swepro_trans.validation.binding_signals import binding_signals
from swepro_trans.validation.counterfactual import review_counterfactuals, validate_review


def _review(kind="message_lexical_gate", *, valid=True, invalid=True, required=False):
    return {
        "verdict": "PASS", "findings": [],
        "assessments": [{
            "file": "tests/test_feature.py", "kind": kind,
            "constraint_required_by_p": required,
            "p_contract_quote": "displaying appropriate error messages" if required else "",
            "valid_alternative": "A meaningful paraphrase with different words",
            "predicted_valid_pass": valid,
            "invalid_alternative": "An incoherent keyword list",
            "predicted_invalid_fail": invalid,
            "reason": "The executable regular expression checks the words only.",
        }],
    }


def test_detects_general_binding_patterns_from_two_unrelated_tasks():
    tests = {
        "tests/test_action.py": {"head": "assert marker_count == 1\nshutil.move('/usr/bin/ruby', backup)"},
        "tests/test_message.py": {"head": "for msg in new_errors:\n    assert msg.text\nfor p in data_dir.iterdir(): pass\nassert re.search(pattern, msg.text)"},
    }
    by_file = {}
    for signal in binding_signals(tests):
        by_file.setdefault(signal["file"], set()).add(signal["kind"])
    assert {"exact_observation_count", "system_path_mutation"} <= by_file["tests/test_action.py"]
    assert {"direct_child_file_scan", "all_observations_required", "message_lexical_gate"} <= by_file["tests/test_message.py"]


def test_tmp_fixture_and_unrelated_regex_do_not_trigger_system_or_message_risks():
    tests = {"tests/test_feature.py": {"head": "shutil.move('/tmp/example', backup)\nassert re.search(pattern, source_code)"}}
    kinds = {signal["kind"] for signal in binding_signals(tests)}
    assert "system_path_mutation" not in kinds
    assert "message_lexical_gate" not in kinds


def test_pytest_output_parser_is_not_a_user_message_gate():
    tests = {"tests/parser.py": {"head": "errors = 0\nmatch = re.search(r'(\\d+) errors?', text)\nassert errors == 0"}}
    assert "message_lexical_gate" not in {signal["kind"] for signal in binding_signals(tests)}


def test_protocol_requires_every_signal_and_actual_contract_quote():
    signals = [{"file": "tests/test_feature.py", "kind": "message_lexical_gate"}]
    assert validate_review(_review(), signals, "The message must be useful.") == []
    assert validate_review(_review(), signals + [{"file": "tests/other.py", "kind": "direct_child_file_scan"}], "P")
    claimed = _review()
    claimed["assessments"][0].update(constraint_required_by_p=True, p_contract_quote="exactly one")
    assert validate_review(claimed, signals, "P says show a message")


def test_counterexample_changes_model_pass_to_fail():
    signals = [{"file": "tests/test_feature.py", "kind": "message_lexical_gate"}]
    result = review_counterfactuals(
        config={}, credentials={}, problem="Show a useful recovery message.", addendum="",
        signals=signals, tests={"tests/test_feature.py": {"head": "assert re.search(pattern, msg.text)"}},
        trace_rows=[], judge_fn=lambda **kwargs: _review(valid=False, invalid=False),
    )
    assert result["verdict"] == "FAIL"
    assert "tests/test_feature.py" in result["findings"][0]


def test_text_findings_are_preserved_when_counterexample_is_added():
    signals = [{"file": "tests/test_feature.py", "kind": "message_lexical_gate"}]
    review = _review(valid=False)
    review["findings"] = "The message predicate binds to a finite token list."
    result = review_counterfactuals(
        config={}, credentials={}, problem="Show a useful recovery message.", addendum="",
        signals=signals, tests={"tests/test_feature.py": {"head": "assert re.search(pattern, msg.text)"}},
        trace_rows=[], judge_fn=lambda **kwargs: review.copy(),
    )
    assert result["verdict"] == "FAIL"
    assert result["findings"][0] == "The message predicate binds to a finite token list."
    assert "tests/test_feature.py" in result["findings"][1]


def test_unstructured_findings_do_not_override_valid_assessments():
    signals = [{"file": "tests/test_feature.py", "kind": "message_lexical_gate"}]
    calls = []
    def invalid(**kwargs):
        calls.append(kwargs)
        return _review() | {"findings": {"unexpected": "object"}}
    result = review_counterfactuals(
        config={}, credentials={}, problem="P", addendum="", signals=signals,
        tests={"tests/test_feature.py": {"head": "assert re.search(pattern, msg.text)"}},
        trace_rows=[], judge_fn=invalid,
    )
    assert len(calls) == 1
    assert result["review_mode"] == "focused_counterfactual"
    assert result["verdict"] == "PASS"


def test_incomplete_review_fails_closed_after_retry():
    signals = [{"file": "tests/test_feature.py", "kind": "message_lexical_gate"}]
    calls = []
    def incomplete(**kwargs):
        calls.append(kwargs)
        return {"verdict": "PASS", "assessments": []}
    result = review_counterfactuals(
        config={}, credentials={}, problem="P", addendum="", signals=signals,
        tests={"tests/test_feature.py": {"head": "assert re.search(pattern, msg.text)"}},
        trace_rows=[], judge_fn=incomplete,
    )
    assert len(calls) == 2
    assert result["verdict"] == "FAIL"
    assert result["review_mode"] == "focused_counterfactual_protocol_failure"


def test_nonempty_user_message_is_a_risk_even_without_keyword_gate():
    tests = {"tests/test_notice.py": {"head": (
        "new_errors = [msg for msg in messages if msg.level == error and msg.text.strip()]\n"
        "assert new_errors, 'expected an error message'\n"
    )}}
    kinds = {signal["kind"] for signal in binding_signals(tests)}
    assert "message_nonempty_only" in kinds
    assert "message_lexical_gate" not in kinds


def test_open_text_message_counterexample_is_recorded_as_residual_limitation():
    signals = [{"file": "tests/test_feature.py", "kind": "message_nonempty_only"}]
    result = review_counterfactuals(
        config={}, credentials={}, problem="Show an appropriate recovery message.", addendum="",
        signals=signals, tests={"tests/test_feature.py": {"head": "assert new_errors"}},
        trace_rows=[], judge_fn=lambda **kwargs: _review(kind="message_nonempty_only", invalid=False),
    )
    assert result["verdict"] == "PASS"
    assert result["residual_limitations"][0]["kind"] == "message_nonempty_only"


def test_open_text_message_requirement_without_content_oracle_is_not_blocking():
    signals = [{"file": "tests/test_feature.py", "kind": "message_nonempty_only"}]
    result = review_counterfactuals(
        config={}, credentials={}, problem="displaying appropriate error messages", addendum="",
        signals=signals, tests={"tests/test_feature.py": {"head": "assert new_errors"}},
        trace_rows=[], judge_fn=lambda **kwargs: _review(
            kind="message_nonempty_only", valid=True, invalid=False, required=True
        ),
    )
    assert result["verdict"] == "PASS"
    assert result["residual_limitations"][0]["kind"] == "message_nonempty_only"


def test_finite_token_family_message_gate_is_detected_without_regex():
    tests = {"tests/test_notice.py": {"head": (
        "def meaningful_message(text):\n"
        "    normalized = text.lower()\n"
        "    return any(term in normalized for term in terms)\n"
        "assert meaningful_message(msg.text)\n"
    )}}
    assert "message_lexical_gate" in {signal["kind"] for signal in binding_signals(tests)}


def test_fixed_serialization_fixture_triggers_p_grounded_counterfactual():
    # A historical parse input can be stricter than a task that only promises
    # a stable editable round trip; the signal must reach the focused gate.
    source = '''
line = ' | Chapter | | {"authors": [{"name": "A"}]}'
entry = TocEntry.from_markdown(line)
assert entry.authors == [{"name": "A"}]
'''
    tests = {"tests/run_script.sh": {"head": source}}
    signals = binding_signals(tests)
    assert any(s["kind"] == "fixed_serialization_fixture" for s in signals)
    result = review_counterfactuals(
        config={}, credentials={},
        problem="Metadata must survive a stable editable Markdown round trip.",
        addendum="", signals=signals, tests=tests, trace_rows=[],
        judge_fn=lambda **kwargs: _review(
            kind="fixed_serialization_fixture", valid=False, invalid=True
        ) | {"assessments": [{
            **_review(kind="fixed_serialization_fixture", valid=False)["assessments"][0],
            "file": "tests/run_script.sh",
            "valid_alternative": "A serializer and parser use compact canonical metadata JSON; round trips preserve authors, but this spaced historical literal is rejected.",
            "invalid_alternative": "The parser drops authors from its own serialized output.",
        }]},
    )
    assert result["verdict"] == "FAIL"


def test_serialization_shape_assertion_is_a_risk_without_p_format_contract():
    tests = {"tests/run_script.sh": {"head": (
        'rendered = entry.to_markdown()\n'
        'assert "|" in rendered\n'
        'assert rendered.startswith("*" * entry.level)\n'
    )}}
    assert "serialization_shape_assertion" in {s["kind"] for s in binding_signals(tests)}



def test_single_line_serializer_assertion_gets_p_grounded_review():
    tests = {"tests/run_script.sh": {"head": (
        'rendered = entry.to_markdown()\n'
        'assert "\\n" not in rendered\n'
        'assert TocEntry.from_markdown(rendered) == entry\n'
    )}}
    signals = [s for s in binding_signals(tests)
               if s["kind"] == "serialization_shape_assertion"]
    assert len(signals) == 1
    assessment = _review(kind="serialization_shape_assertion", valid=False)["assessments"][0]
    assessment.update(
        file="tests/run_script.sh",
        valid_alternative="A stable multiline Markdown record preserves title and metadata.",
        invalid_alternative="The parser discards metadata from its own output.",
    )
    result = review_counterfactuals(
        config={}, credentials={},
        problem="Preserve metadata in a stable editable Markdown round trip.",
        addendum="", signals=signals, tests=tests, trace_rows=[],
        judge_fn=lambda **kwargs: {"verdict": "PASS", "findings": [],
                                   "assessments": [assessment]},
    )
    assert result["verdict"] == "FAIL"



def test_nested_template_probe_needs_whole_page_counterfactual():
    tests = {"tests/test.sh": {"head": (
        'html = render_template("authors/infobox", page)\n'
        'assert "Google Scholar" in html\n'
    )}}
    signals = [signal for signal in binding_signals(tests)
               if signal["kind"] == "subcomponent_location_binding"]
    assert len(signals) == 1
    assessment = _review(kind="subcomponent_location_binding", valid=False)["assessments"][0]
    assessment.update(
        file="tests/test.sh",
        valid_alternative="The author page renders the profile in its main content.",
        invalid_alternative="No author-page component renders the profile.",
    )
    result = review_counterfactuals(
        config={}, credentials={}, problem="Show external profiles on author pages.",
        addendum="", signals=signals, tests=tests, trace_rows=[],
        judge_fn=lambda **kwargs: {"verdict": "PASS", "findings": [],
                                   "assessments": [assessment]},
    )
    assert result["verdict"] == "FAIL"

def test_reflective_entrypoint_search_needs_public_access_counterfactual():
    tests = {"tests/test_feature.py": {"head": (
        "for module in pkgutil.walk_packages(package.__path__):\n"
        "    if inspect.isclass(value): continue\n"
        "    if _matches_expected_probe(value): return value\n"
    )}}
    signals = [signal for signal in binding_signals(tests)
               if signal["kind"] == "reflective_entrypoint_scope"]
    assert len(signals) == 1
    assessment = _review(kind="reflective_entrypoint_scope", valid=False)["assessments"][0]
    assessment.update(
        valid_alternative="An existing public method exposes an opt-in behavior with the same result.",
        invalid_alternative="No public access path provides the required behavior.",
    )
    result = review_counterfactuals(
        config={}, credentials={}, problem="Expose an opt-in behavior to callers.",
        addendum="", signals=signals, tests=tests, trace_rows=[],
        judge_fn=lambda **kwargs: {"verdict": "PASS", "findings": [],
                                   "assessments": [assessment]},
    )
    assert result["verdict"] == "FAIL"

def test_exact_collection_equality_and_public_type_origin_receive_focused_review():
    tests = {"tests/test_state.py": {"head": (
        "public_module = value_type.__module__.startswith('ansible.')\n"
        "assert public_module\n"
        "assert result['languages'] == ['French']\n"
    )}}
    kinds = {signal["kind"] for signal in binding_signals(tests)}
    assert {"whole_result_exactness", "public_type_origin_binding"} <= kinds


def test_test_defined_subclass_hook_gets_p_only_counterfactual_review():
    source = '''
class _RecordingQueue(FinalQueue):
    def __init__(self, recorder):
        self._recorder = recorder

    def send_display(self, *args, **kwargs):
        self._recorder.put((args, kwargs))

assert marker in recorded
'''
    tests = {"tests/test_fork.py": {"head": source}}
    signals = binding_signals(tests)
    assert any(s["kind"] == "fixture_extension_hook" for s in signals)
    result = review_counterfactuals(
        config={}, credentials={}, problem="Fork output must be reliable.", addendum="",
        signals=signals, tests=tests, trace_rows=[],
        judge_fn=lambda **kwargs: {
            "verdict": "PASS", "findings": [], "assessments": [{
                "file": "tests/test_fork.py", "kind": "fixture_extension_hook",
                "constraint_required_by_p": False, "p_contract_quote": "",
                "valid_alternative": "A reliable IPC pipe transports fork output without calling the test-only send_display hook.",
                "predicted_valid_pass": False,
                "invalid_alternative": "The fork drops messages before parent delivery.",
                "predicted_invalid_fail": True,
                "reason": "The test accepts only the added subclass hook, while P only fixes reliability.",
            }],
        },
    )
    assert result["verdict"] == "FAIL"


def test_fixed_file_list_import_assertion_requires_counterfactual_review():
    source = '''
CHAIN_RELS = ['basic.py', 'collections.py']
for rel in CHAIN_RELS:
    records = imports_from(rel)
    assert not imports_private_shim(records)
    assert imports_supported_abc(records)
'''
    kinds = {signal["kind"] for signal in binding_signals({"tests/test_imports.py": {"head": source}})}
    assert "all_observations_required" in kinds


def test_exact_numeric_boundary_is_reviewed_without_flagging_plain_arithmetic():
    tests = {
        "tests/test_match.sh": {"head": "assert editions_match(e1, e2, 515) is True\nassert editions_match(e1, e2, 516) is False"},
        "tests/test_math.py": {"head": "assert add(1, 2) == 3"},
    }
    by_file = {name: {signal["kind"] for signal in binding_signals(tests) if signal["file"] == name} for name in tests}
    assert "exact_numeric_boundary" in by_file["tests/test_match.sh"]
    assert "exact_numeric_boundary" not in by_file["tests/test_math.py"]


def test_preloaded_provider_review_must_use_broken_provider_counterexample():
    signals = [{"file": "tests/test_feature.py", "kind": "fixture_preloaded_provider"}]
    weak = _review(kind="fixture_preloaded_provider")
    weak["assessments"][0]["invalid_alternative"] = "The renderer emits no profiles."
    errors = validate_review(weak, signals, "Show external profiles from a remote source.")
    assert any("provider counterexample" in error for error in errors)

    concrete = _review(kind="fixture_preloaded_provider", invalid=False)
    concrete["assessments"][0]["invalid_alternative"] = (
        "The real provider returns no data while the fixture still supplies a "
        "preloaded entity and the page renderer works."
    )
    assert validate_review(concrete, signals, "Retrieve remote profiles for the page.") == []

    natural_synonyms = _review(kind="fixture_preloaded_provider", invalid=False)
    natural_synonyms["assessments"][0]["invalid_alternative"] = (
        "The source lookup returns nothing, but the seeded test record remains "
        "available and the result view still displays it."
    )
    assert validate_review(natural_synonyms, signals, "Retrieve remote profiles for the page.") == []

    result = review_counterfactuals(
        config={}, credentials={}, problem="Retrieve remote profiles for the page.",
        addendum="", signals=signals,
        tests={"tests/test_feature.py": {"head": "class _Page:\n    def wikidata(self): return self.entity"}},
        trace_rows=[], judge_fn=lambda **kwargs: concrete.copy(),
    )
    assert result["verdict"] == "FAIL"


def test_mapping_review_must_swap_named_meanings():
    signals = [{"file": "tests/test_feature.py", "kind": "permutation_invariant_mapping"}]
    weak = _review(kind="permutation_invariant_mapping")
    weak["assessments"][0]["invalid_alternative"] = "The old alias emits no deprecation warning."
    assert any("mapping counterexample" in e for e in validate_review(weak, signals, "Preserve named legacy state meanings."))

    concrete = _review(kind="permutation_invariant_mapping", invalid=False)
    concrete["assessments"][0]["invalid_alternative"] = (
        "Swap two named legacy aliases while preserving distinct public member "
        "values and every deprecation warning."
    )
    assert validate_review(concrete, signals, "Preserve named legacy state meanings.") == []
    result = review_counterfactuals(
        config={}, credentials={}, problem="Preserve named legacy state meanings.",
        addendum="", signals=signals,
        tests={"tests/test_feature.py": {"head": "semantic_match = any(value == member for member in members)"}},
        trace_rows=[], judge_fn=lambda **kwargs: concrete.copy(),
    )
    assert result["verdict"] == "FAIL"


def test_counterfactual_audit_batches_signals_and_combines_assessments():
    signals = [
        {"file": f"tests/test_{index}.py", "kind": "message_lexical_gate"}
        for index in range(5)
    ]
    calls = []

    def judge(**kwargs):
        batch = kwargs["evidence"]["risk_signals"]
        calls.append(batch)
        return {
            "verdict": "PASS", "findings": [],
            "assessments": [{
                "file": signal["file"], "kind": signal["kind"],
                "constraint_required_by_p": False, "p_contract_quote": "",
                "valid_alternative": "A valid meaningful paraphrase with different wording.",
                "predicted_valid_pass": True,
                "invalid_alternative": "An incoherent keyword heap.",
                "predicted_invalid_fail": True,
                "reason": "The relevant predicate accepts meaning, not just lexical hits.",
            } for signal in batch],
        }

    result = review_counterfactuals(
        config={}, credentials={}, problem="P", addendum="", signals=signals,
        tests={signal["file"]: {"head": "assert meaningful(message)"} for signal in signals},
        trace_rows=[], judge_fn=judge,
    )

    assert [len(batch) for batch in calls] == [2, 2, 1]
    assert result["verdict"] == "PASS"
    assert result["risk_batch_count"] == 3
    assert len(result["assessments"]) == len(signals)
    assert {row["file"] for row in result["assessments"]} == {row["file"] for row in signals}


def test_private_entrypoint_counterfactual_requires_public_alternative():
    signals = [{"file": "tests/test_feature.py", "kind": "private_entrypoint_call"}]
    review = _review(kind="private_entrypoint_call")
    review["assessments"][0]["valid_alternative"] = (
        "A different implementation removes the private helper but preserves the same public parser outcome."
    )
    assert validate_review(review, signals, "Parse the input and report its result.") == []

    review["assessments"][0]["valid_alternative"] = "The helper has another internal name."
    assert any("public observable boundary" in error for error in validate_review(
        review, signals, "Parse the input and report its result."
    ))


def test_null_constructor_dependency_signal_requires_valid_and_invalid_counterfactuals():
    signals = [{"file": "tests/public_http_test.go", "kind": "multiple_null_constructor_dependencies"}]
    review = _review(kind="multiple_null_constructor_dependencies")
    review["assessments"][0]["file"] = "tests/public_http_test.go"
    assert validate_review(review, signals, "Serve the public endpoint.") == []

    review["assessments"][0]["invalid_alternative"] = ""
    assert any("missing P-violating alternative" in error for error in validate_review(
        review, signals, "Serve the public endpoint."
    ))
