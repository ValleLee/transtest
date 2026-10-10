"""Trigger extra semantic scrutiny only for executable exact-error assertions."""
from swepro_trans.validation.semantic import _binding_signals


def test_exact_exception_assertions_trigger_focused_review():
    tests = {
        "tests/functional_test.ts": {
            "head": "if (!(err instanceof DomainCryptoError) || err.name !== 'CryptoError') throw err",
        },
        "tests/other.py": {
            "head": "with pytest.raises(PublicError):\n    invoke()",
        },
    }
    signals = _binding_signals(tests)
    assert {signal["file"] for signal in signals if signal["kind"] == "exact_exception_type"} == set(tests)


def test_generic_error_smoke_does_not_trigger_exact_type_review():
    tests = {"tests/functional_test.ts": {"head": "try { await decrypt() } catch (error) { expect(error).toBeTruthy() }"}}
    assert not [signal for signal in _binding_signals(tests) if signal["kind"] == "exact_exception_type"]


def test_helper_wrapped_exact_exception_assertion_triggers_focused_review():
    tests = {
        "tests/functional_test.ts": {
            "head": "await expectRejects(KeyPermanentlyInvalidatedError, () => decrypt())",
        },
    }
    signals = _binding_signals(tests)
    assert [(signal["file"], signal["kind"]) for signal in signals] == [
        ("tests/functional_test.ts", "exact_exception_type"),
    ]


def test_global_ui_cardinality_is_reviewed_as_a_binding_risk():
    tests = {
        "tests/menu.test.js": {
            "head": "const buttons = screen.getAllByRole('button').filter(button => button.getAttribute('aria-haspopup') === 'true');\nexpect(buttons).toHaveLength(1);",
        },
    }
    assert "global_ui_cardinality" in {signal["kind"] for signal in _binding_signals(tests)}


def test_expected_value_must_not_select_a_different_public_api_per_case():
    tests = {
        "tests/parser.py": {
            "head": "for parser in public_methods:\n    families = list(parser(text))\n    if expected is not None and families != expected:\n        continue\n    return families",
        },
    }
    assert "oracle_guided_selection" in {signal["kind"] for signal in _binding_signals(tests)}


def test_harness_exception_handling_does_not_claim_product_error_contract():
    tests = {
        "tests/test.sh": {
            "head": "try:\n    read_source()\nexcept (OSError, UnicodeError, SyntaxError):\n    continue",
        },
    }
    assert "exact_exception_type" not in {signal["kind"] for signal in _binding_signals(tests)}


def test_unittest_assert_raises_still_triggers_exact_error_review():
    tests = {"tests/test_api.py": {"head": "self.assertRaises(DomainError, invoke)"}}
    assert "exact_exception_type" in {signal["kind"] for signal in _binding_signals(tests)}


def test_legacy_alias_type_constraint_gets_counterfactual_review():
    tests = {
        "tests/test_migration.py": {
            "head": "assert not fact['is_builtin_int']\nassert fact['is_canonical_member']",
        },
    }
    kinds = {signal["kind"] for signal in _binding_signals(tests)}
    assert "legacy_alias_representation" in kinds


def test_change_decision_requires_counterfactual_review():
    tests = {"tests/test_archive.py": {"head": "assert unarchived is False\nassert 'file.txt' in archive.includes"}}
    assert "decision_branch_binding" in {signal["kind"] for signal in _binding_signals(tests)}


def test_name_derived_identifier_string_filter_gets_review():
    tests = {"tests/test_authors.py": {"head": "# name-derived identifier\nreturn {k: v for k, v in author.items() if isinstance(v, str) and v.strip()}"}}
    assert "derived_identifier_type_binding" in {signal["kind"] for signal in _binding_signals(tests)}


def test_numeric_match_threshold_truth_assertion_gets_review():
    tests = {
        "tests/test_match.py": {
            "head": "assert _raw_compare(copy.deepcopy(left), copy.deepcopy(right), 515)\n"
                    "assert _raw_compare(copy.deepcopy(left), copy.deepcopy(right), 516) is False",
        },
    }
    assert "exact_numeric_boundary" in {signal["kind"] for signal in _binding_signals(tests)}


def test_numeric_match_threshold_inside_multiline_file_gets_review():
    tests = {"tests/test_match.py": {"head": (
        "def test_match():\n"
        "    assert _raw_compare(copy.deepcopy(left), copy.deepcopy(right), 875)\n"
        "    assert other_property()\n"
    )}}
    assert "exact_numeric_boundary" in {signal["kind"] for signal in _binding_signals(tests)}


def test_set_equality_on_entire_output_gets_counterfactual_review():
    tests = {"tests/test_config.py": {"head": "return set(lines) == {VISIBLE_LINE, HIDDEN_LINE}\nassert set(lines) == {VISIBLE_LINE, HIDDEN_LINE}"}}
    assert "whole_result_exactness" in {signal["kind"] for signal in _binding_signals(tests)}

def test_default_output_subset_gets_counterfactual_review():
    tests = {"tests/test_config.py": {"head": "def test_default_omits_hidden():\n    lines = _lines(output)\n    assert VISIBLE_LINE in lines\n    assert not hidden_lines(output)"}}
    assert "default_output_subset" in {signal["kind"] for signal in _binding_signals(tests)}


def test_self_calibrated_matcher_threshold_gets_causal_review():
    tests = {"tests/test_match.py": {"head": (
        "while not editions_match(e1, e2, low):\n"
        "    low = low * 2 - 1\n"
        "while editions_match(e1, e2, high):\n"
        "    high = high * 2 + 1\n"
        "assert editions_match(e1, e2, boundary) is True\n"
    )}}
    assert "self_calibrated_threshold" in {signal["kind"] for signal in _binding_signals(tests)}


def test_preloaded_fixture_provider_gets_retrieval_review():
    tests = {"tests/test_page.py": {"head": (
        "class _Page:\n"
        "    def __init__(self, entity):\n"
        "        self.entity = entity\n"
        "    def wikidata(self):\n"
        "        return self.entity\n"
        "def test_render():\n"
        "    assert 'Profile' in render(_Page(preloaded))\n"
    )}}
    assert "fixture_preloaded_provider" in {signal["kind"] for signal in _binding_signals(tests)}


def test_finite_option_vocabulary_gets_interface_review():
    tests = {"tests/test_config.py": {"head": (
        "_INCLUDE_OPTION_SEEDS = ('hidden', 'all')\n"
        "for name in _candidate_spellings():\n"
        "    result = request('/config?' + name + '=true')\n"
    )}}
    assert "finite_option_vocabulary" in {signal["kind"] for signal in _binding_signals(tests)}


def test_member_set_compatibility_requires_permutation_counterfactual():
    tests = {"tests/test_migration.py": {"head": (
        "semantic_match = any(value == member for member in state_member_values)\n"
        "assert semantic_match is True\n"
        "assert len(set(value_reprs)) == len(names)\n"
    )}}
    assert "permutation_invariant_mapping" in {s["kind"] for s in _binding_signals(tests)}


def test_nested_record_walk_with_flat_sequence_check_gets_wrapper_review():
    tests = {"tests/test_repr.py": {"head": (
        "def _is_flat_sequence_expr(expr): return False\n"
        "for child in ast.walk(tree):\n"
        "    if has_value_and_scope(child): return True\n"
    )}}
    assert "representation_wrapper_acceptance" in {s["kind"] for s in _binding_signals(tests)}


def test_stringification_fixture_is_not_a_preloaded_provider():
    tests = {"tests/test_display.py": {"head": (
        "class _FakeHost:\n"
        "    def __init__(self, token):\n"
        "        self.name = token\n"
        "    def __str__(self):\n"
        "        return self.name\n"
    )}}
    assert "fixture_preloaded_provider" not in {s["kind"] for s in _binding_signals(tests)}


def test_generated_pycache_is_excluded_from_verifier_evidence(tmp_path):
    from swepro_trans.validation.binding_signals import is_verifier_source, revision_evidence_fingerprint
    source = tmp_path / "test_feature.py"
    source.write_text("assert meaningful_result()\n")
    before = revision_evidence_fingerprint(tmp_path)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    bytecode = cache / "test_feature.cpython-38.pyc"
    bytecode.write_bytes(b"pkgutil.walk_packages fake old verifier")
    assert not is_verifier_source(bytecode, tmp_path)
    assert revision_evidence_fingerprint(tmp_path) == before


def test_named_wrapper_around_flat_repr_gets_review_without_ast_walk():
    tests = {"tests/test_repr.sh": {"head": (
        "_FLAT_WRAPPER_NAMES = {'tuple', 'list'}\n"
        "def _bare_flat_record_sequence(text):\n"
        "    if match.group(1) not in _FLAT_WRAPPER_NAMES:\n"
        "        wrapped = True\n"
        "    return not wrapped\n"
    )}}
    assert "representation_wrapper_acceptance" in {s["kind"] for s in _binding_signals(tests)}


def test_unconditional_downstream_side_effect_gets_counterfactual_review():
    tests = {"tests/test_archive.py": {"head": (
        "assert unarchived is False\n"
        "extract = archive.unarchive()\n"
        "assert extract['rc'] == 0\n"
        "assert extracted_path.read_bytes() == archived_content"
    )}}
    assert "unconditional_downstream_side_effect" in {
        signal["kind"] for signal in _binding_signals(tests)
    }


def test_whole_mapping_equality_against_product_result_gets_counterfactual_review():
    tests = {"tests/test_facts.py": {"head": (
        "assert scenario['expected_result'] == inst.get_cpu_facts()"
    )}}
    assert "whole_result_exactness" in {
        signal["kind"] for signal in _binding_signals(tests)
    }


def test_direct_private_repository_entrypoint_triggers_focused_review():
    tests = {
        "tests/test_parser.py": {
            "head": "from qutebrowser.misc import elf\nresult = elf._parse_from_file(io.BytesIO(data))\n",
        },
    }
    assert "private_entrypoint_call" in {s["kind"] for s in _binding_signals(tests)}


def test_multiple_explicit_null_constructor_dependencies_trigger_review():
    tests = {"tests/public_http_test.go": {"head": (
        "router := api.New(nil, nil, nil, nil, nil)\n"
        "response := httptest.NewRecorder()"
    )}}
    signals = _binding_signals(tests)
    assert "multiple_null_constructor_dependencies" in {signal["kind"] for signal in signals}
