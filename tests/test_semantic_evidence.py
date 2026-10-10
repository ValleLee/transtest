from swepro_trans.validation.semantic import _auditable_revision_tests, _p_authorizes_symbol, _p_names_class, _without_comment_only_lines


def test_auditable_revision_tests_keeps_shell_harness_and_config() -> None:
    tests = {
        "tests/test.sh": {"sha256": "a", "head": "entry"},
        "tests/run_script.sh": {"sha256": "b", "head": "generated test body"},
        "tests/config.json": {"sha256": "c", "head": "x" * 6000 + "tail-selector"},
        "tests/parser.py": {"sha256": "d", "head": "parser"},
        "tests/build_verifier.cjs": {"sha256": "f", "head": "module.exports = build"},
        "tests/helpers/runtime.mjs": {"sha256": "g", "head": "export const run = 1"},
        "tests/notes.md": {"sha256": "e", "head": "notes"},
    }
    result = _auditable_revision_tests(tests)
    assert set(result) == {
        "tests/test.sh",
        "tests/run_script.sh",
        "tests/config.json",
        "tests/parser.py",
        "tests/build_verifier.cjs",
        "tests/helpers/runtime.mjs",
        "tests/notes.md",
    }
    assert result["tests/config.json"]["head"].endswith("tail-selector")
    assert result["tests/build_verifier.cjs"]["head"] == "module.exports = build"
    assert result["tests/helpers/runtime.mjs"]["head"] == "export const run = 1"
    assert "head" not in result["tests/notes.md"]


def test_p_named_new_class_does_not_license_unnamed_method() -> None:
    p = "Switch to a `FontFamilies` class for consistent parsing."
    classes = {"FontFamilies"}
    assert _p_authorizes_symbol("configutils.FontFamilies", p, classes)
    assert not _p_authorizes_symbol("configutils.FontFamilies.from_str", p, classes)
    assert not _p_authorizes_symbol("configutils.GoldHelper", p, {"GoldHelper"})
    assert _p_authorizes_symbol("configutils.FontFamilies.from_str", p + " Use `configutils.FontFamilies.from_str`.", classes)


def test_p_class_recognition_requires_explicit_naming() -> None:
    assert _p_names_class("FontFamilies", "Switch to a `FontFamilies` class.")
    assert _p_names_class("FontFamilies", "Use the FontFamilies class.")
    assert _p_names_class("Options", "Add an `Options` struct for configuration.")
    assert _p_names_class("Options", "Add an Options type for configuration.")
    assert not _p_names_class("FontFamilies", "The font families should parse cleanly.")


def test_symbol_probe_ignores_python_docstrings_but_keeps_code() -> None:
    source = "\n".join([
        chr(34) * 3 + "Historical FontFamilies.from_str is evidence only.",
        "Do not require this exact method." + chr(34) * 3,
        'parser = getattr(cls, "from_str", None)',
    ])
    executable = _without_comment_only_lines(source)
    assert "FontFamilies.from_str" not in executable
    assert 'getattr(cls, "from_str", None)' in executable


def test_protocol_fallback_does_not_reject_false_or_p_named_class() -> None:
    from swepro_trans.validation.semantic import _deterministic_fallback

    evidence = {
        "problem_statement": "Switch to a `WidgetFamilies` class for consistent parsing.",
        "conversion_trace": {"f2p_accounting": [{
            "source_f2p": "test_example", "behavior_intent": "parse names",
            "historical_behavior": "one name", "behavioral_obligations": ["parse"],
            "obligation_accounting": [{"id": "O1", "obligation": "parse"}],
            "preservation_evidence": "public result", "functional_surface": "class",
            "evidence": "base missing", "problem_statement_support": "named class",
            "problem_statement_quotes": ["Switch to a `WidgetFamilies` class for consistent parsing."],
            "behavior_classification": "p_supported_behavior", "binding_detected": False,
            "base_repo_observable": False, "base_behavior_status": "changed_or_missing",
            "gold_only_binding": False, "observable_surface": "parsed output",
            "decision": "rewrite", "emitted_tests": ["test_output"],
            "rationale": "same behavior",
        }]},
        "base_repository_probe": {
            "status": "ok", "gold_only_candidates": ["module.WidgetFamilies"],
            "gold_defined_classes": ["WidgetFamilies"],
        },
    }
    result = _deterministic_fallback(evidence, ["invalid JSON"])
    assert not any("binding_detected" in item for item in result["findings"])
    assert not any("Gold-only symbols remain" in item for item in result["findings"])
    assert result["verdict"] == "FAIL"  # Protocol failure still requires a real Judge verdict.


def test_gold_only_probe_requires_a_gold_declaration() -> None:
    from swepro_trans.validation.semantic import _gold_declaration_matches

    # A method used by Gold on a local variable is not a Gold-defined API.
    assert _gold_declaration_matches("field.partition", ["luqum_replace_field"]) == []
    assert _gold_declaration_matches(
        "query_utils.luqum_replace_field", ["luqum_replace_field"]
    ) == ["luqum_replace_field"]
    assert _gold_declaration_matches(
        "configutils.FontFamilies.from_str", ["FontFamilies", "from_str"]
    ) == ["FontFamilies", "from_str"]


def test_gold_only_probe_extracts_go_receiver_methods() -> None:
    from swepro_trans.validation.semantic import _gold_declaration_matches, _gold_defined_symbols

    added = [
        "type Records map[string]Record",
        "func (r Records) FilterByScore(over float64) Records { return r }",
        "// func (r Records) CommentOnly() Records { return r }",
    ]

    symbols = _gold_defined_symbols(added)

    assert "FilterByScore" in symbols
    assert "CommentOnly" not in symbols
    assert _gold_declaration_matches("records.FilterByScore", symbols) == ["FilterByScore"]


def test_base_probe_flags_gold_only_go_type(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    revision = tmp_path / "rev_001"
    tests = revision / "tests"
    tests.mkdir(parents=True)
    (tests / "run_script.sh").write_text(
        'cache.NewSimpleCache[string](cache.Options{SizeLimit: 2})\n'
    )
    patch = tmp_path / "gold.diff"
    patch.write_text("+type Options struct { SizeLimit int }\n")

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="__TERM__cache.Options\n")

    monkeypatch.setattr(semantic.subprocess, "run", fake_run)
    result = semantic._base_probe("image", revision, patch)

    assert "Options" in result["gold_defined_symbols"]
    assert "Options" in result["gold_defined_types"]
    assert not result["base_present"]["cache.Options"]
    assert result["gold_only_candidates"] == ["cache.Options"]
    assert semantic._p_authorizes_symbol(
        "cache.Options", "The `Options` struct configures eviction.",
        set(result["gold_defined_types"]),
    )
    assert not semantic._p_authorizes_symbol(
        "cache.Options", "The cache supports configuration options.",
        set(result["gold_defined_types"]),
    )
    assert result["gold_only_evidence"]["cache.Options"] == ["Options"]


def test_base_probe_recognizes_module_path_but_not_gold_member(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    revision = tmp_path / "rev_001"
    tests = revision / "tests"
    tests.mkdir(parents=True)
    (tests / "run_script.sh").write_text(
        'module = __import__("example.plugins.autocomplete", fromlist=["handler"])\n'
        'from example.plugins.autocomplete import GoldMember\n'
    )
    patch = tmp_path / "gold.diff"
    patch.write_text("+class autocomplete(Base):\n+    pass\n+class GoldMember(Base):\n+    pass\n")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command[-1])
        return SimpleNamespace(returncode=0, stdout=(
            "__TERM__example.plugins.autocomplete\n"
            "example/plugins/autocomplete.py:1:module source exists\n"
            "__TERM__example.plugins.autocomplete.GoldMember\n"
        ))

    monkeypatch.setattr(semantic.subprocess, "run", fake_run)
    result = semantic._base_probe("image", revision, patch)
    assert "example/plugins/autocomplete.py" in commands[0]
    assert result["base_present"]["example.plugins.autocomplete"]
    assert not result["base_present"]["example.plugins.autocomplete.GoldMember"]
    assert result["gold_only_candidates"] == ["example.plugins.autocomplete.GoldMember"]


def test_base_probe_flags_gold_only_go_receiver_method(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    revision = tmp_path / "rev_001"
    tests = revision / "tests"
    tests.mkdir(parents=True)
    (tests / "run_script.sh").write_text("got = records.FilterByScore(7.0)\n")
    patch = tmp_path / "gold.diff"
    patch.write_text("+func (r Records) FilterByScore(over float64) Records { return r }\n")

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="__TERM__records.FilterByScore\n")

    monkeypatch.setattr(semantic.subprocess, "run", fake_run)
    result = semantic._base_probe("image", revision, patch)

    assert result["gold_only_candidates"] == ["records.FilterByScore"]
    assert result["gold_only_evidence"]["records.FilterByScore"] == ["FilterByScore"]


def test_focused_counterfactual_protocol_failure_is_not_a_verifier_defect() -> None:
    from swepro_trans.validation.semantic import _merge_focused_counterfactual_audit

    result = {"verdict": "PASS", "findings": [], "binding_risks": []}
    focused = {
        "verdict": "FAIL",
        "review_mode": "focused_counterfactual_protocol_failure",
        "findings": ["Focused risk review could not account for every flagged assertion"],
        "protocol_errors": ["batch_3: attempt_1: focused review omitted assessments"],
    }

    merged = _merge_focused_counterfactual_audit(result, focused)

    assert merged["verdict"] == "FAIL"
    assert merged["review_mode"] == "protocol_failure"
    assert merged["failure_classification"] == "judge_transport"
    assert merged["focused_counterfactual_audit"] is focused
    assert merged["binding_risks"] == []


def test_focused_counterfactual_finding_still_routes_to_converter_repair() -> None:
    from swepro_trans.validation.semantic import _merge_focused_counterfactual_audit

    result = {"verdict": "PASS", "findings": [], "binding_risks": []}
    focused = {
        "verdict": "FAIL", "review_mode": "focused_counterfactual",
        "findings": ["A plausible implementation is rejected"],
    }

    merged = _merge_focused_counterfactual_audit(result, focused)

    assert merged["verdict"] == "FAIL"
    assert "failure_classification" not in merged
    assert merged["binding_risks"] == [
        "Focused counterfactual audit found an implementation-bound verifier assertion"
    ]



def test_historical_selector_terms_include_suite_root_and_node_id_parts() -> None:
    from swepro_trans.validation.semantic import _historical_selector_terms

    terms = _historical_selector_terms([
        "TestLoad",
        "TestLoad/grpc_level_provided",
        "tests/test_config.py::test_load[advanced]",
    ])
    assert "TestLoad" in terms
    assert "TestLoad/grpc_level_provided" in terms
    assert "tests/test_config.py" in terms
    assert "test_load[advanced]" in terms


def test_parse_historical_test_sources_extracts_paths_and_bodies() -> None:
    from swepro_trans.validation.semantic import _parse_historical_test_sources

    sources = _parse_historical_test_sources(
        "probe output\n"
        "__HIST_SOURCE_BEGIN__config/config_test.go\n"
        "func TestLoad(t *testing.T) { t.Run(\"cache - redis\", run) }\n"
        "__HIST_SOURCE_END__\n"
    )
    assert sources == [{
        "path": "config/config_test.go",
        "source": "func TestLoad(t *testing.T) { t.Run(\"cache - redis\", run) }",
    }]


def test_historical_test_source_probe_searches_and_returns_suite_source(monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command[-1])
        return SimpleNamespace(returncode=0, stdout=(
            "__HIST_SOURCE_BEGIN__config/config_test.go\n"
            "func TestLoad(t *testing.T) {\n"
            "  tests := []struct{name string}{ {name: \\\"cache - redis\\\"} }\n"
            "}\n"
            "__HIST_SOURCE_END__\n"
        ))

    monkeypatch.setattr(semantic.subprocess, "run", fake_run)
    result = semantic._historical_test_source_probe(
        "image", ["TestLoad", "TestLoad/grpc_level_provided"]
    )

    assert result["status"] == "ok"
    assert result["source_file_count"] == 1
    assert "cache - redis" in result["sources"][0]["source"]
    assert "TestLoad/grpc_level_provided" in commands[0]
    assert "head -c 14000" in commands[0]


def test_semantic_selector_list_parses_stage1_stringified_arrays() -> None:
    from swepro_trans.validation.semantic import _parse_selector_list

    assert _parse_selector_list(["TestOne", "TestTwo/case"]) == ["TestOne", "TestTwo/case"]
    assert _parse_selector_list('["TestOne", "TestTwo/case"]') == ["TestOne", "TestTwo/case"]
    assert _parse_selector_list("['TestOne', 'TestTwo/case']") == ["TestOne", "TestTwo/case"]
    assert _parse_selector_list("not a selector array") == []


def test_historical_source_probe_receives_stringified_selector_values(monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command[-1])
        return SimpleNamespace(returncode=0, stdout=(
            "__HIST_SOURCE_BEGIN__scanner_test.go\n"
            "func TestParse(t *testing.T) {}\n"
            "__HIST_SOURCE_END__\n"
        ))

    monkeypatch.setattr(semantic.subprocess, "run", fake_run)
    config = {"fail_to_pass": "['TestParse', 'TestParse/invalid']"}
    selectors = semantic._parse_selector_list(config["fail_to_pass"])
    result = semantic._historical_test_source_probe("image", selectors)

    assert result["status"] == "ok"
    assert result["selectors"] == ["TestParse", "TestParse/invalid"]
    assert result["sources"][0]["path"] == "scanner_test.go"
    assert "TestParse" in commands[0]


def test_historical_test_patch_paths_include_changed_test_file() -> None:
    from swepro_trans.validation.semantic import _historical_test_patch_paths

    patch = (
        "diff --git a/models/scanresults_test.go b/models/scanresults_test.go\n"
        "index abc..def 100644\n"
        "--- a/models/scanresults_test.go\n"
        "+++ b/models/scanresults_test.go\n"
    )
    assert _historical_test_patch_paths(patch) == ["models/scanresults_test.go"]


def test_historical_source_probe_includes_patch_test_files(monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command[-1])
        return SimpleNamespace(returncode=0, stdout=(
            "__HIST_SOURCE_BEGIN__models/scanresults_test.go\n"
            "func TestFilterIgnorePkgs(t *testing.T) {}\n"
            "__HIST_SOURCE_END__\n"
        ))

    monkeypatch.setattr(semantic.subprocess, "run", fake_run)
    patch = "diff --git a/models/scanresults_test.go b/models/scanresults_test.go\n"
    result = semantic._historical_test_source_probe("image", ["TestVulnInfos_FilterIgnorePkgs"], patch)

    assert result["status"] == "ok"
    assert result["patch_paths"] == ["models/scanresults_test.go"]
    assert result["sources"][0]["path"] == "models/scanresults_test.go"
    assert "git show" in commands[0]
    assert "models/scanresults_test.go" in commands[0]
    assert "exit 0" in commands[0]


def test_historical_source_probe_reports_no_matches_without_probe_error(monkeypatch) -> None:
    from types import SimpleNamespace
    from swepro_trans.validation import semantic

    monkeypatch.setattr(
        semantic.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""),
    )
    result = semantic._historical_test_source_probe("image", ["TestNotPresent"])
    assert result["status"] == "no_matches"
    assert result["source_file_count"] == 0


def test_compacted_semantic_evidence_preserves_per_obligation_status_and_evidence() -> None:
    from swepro_trans.validation.semantic import _compact_semantic_f2p_rows

    trace = {"f2p_accounting": [{
        "source_f2p": "historical::mixed",
        "behavior_classification": "p_supported_behavior",
        "obligation_accounting": [{
            "id": "O1", "obligation": "public result", "scope": "product_behavior",
            "disposition": "preserved", "base_behavior_status": "already_satisfies",
            "emitted_tests": ["converted::result"], "evidence": "Base behavior evidence",
            "rationale": "This is a regression obligation.",
        }],
    }]}

    rows = _compact_semantic_f2p_rows(trace, lambda value, _limit: value)

    assert rows[0]["obligation_accounting"] == [{
        "id": "O1", "obligation": "public result", "scope": "product_behavior",
        "disposition": "preserved", "base_behavior_status": "already_satisfies",
        "emitted_tests": ["converted::result"], "evidence": "Base behavior evidence",
        "rationale": "This is a regression obligation.",
    }]


def test_focused_counterfactual_runs_after_closed_broad_fail_to_collect_all_defects():
    from swepro_trans.validation.semantic import _should_run_focused_counterfactual

    assert _should_run_focused_counterfactual({"verdict": "PASS"}, deterministic_only=False)
    assert _should_run_focused_counterfactual({"verdict": "FAIL"}, deterministic_only=False)
    assert not _should_run_focused_counterfactual({"verdict": "ERROR"}, deterministic_only=False)
    assert not _should_run_focused_counterfactual(
        {"verdict": "FAIL", "failure_classification": "judge_transport"},
        deterministic_only=False,
    )
    assert not _should_run_focused_counterfactual({"verdict": "FAIL"}, deterministic_only=True)
