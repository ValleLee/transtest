from swepro_trans.validation.revision import _selector_is_emitted, _selector_source_hints


def test_config_selector_does_not_count_as_emitted_test_code(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    selector = "test/units/example.py::TestExample::test_added_by_pr"
    (tests / "config.json").write_text(
        '{"pass_to_pass": ["' + selector + '"]}', encoding="utf-8"
    )
    (tests / "test.sh").write_text(
        "#!/bin/sh\npython3 parser.py --config config.json\n", encoding="utf-8"
    )
    (tests / "parser.py").write_text(
        "import json\njson.load(open('config.json'))\n", encoding="utf-8"
    )

    assert not _selector_is_emitted(selector, tests)


def test_test_source_in_bundle_counts_as_emitted(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_converted.py").write_text(
        "def test_behavior_added_by_conversion():\n    assert product_result() == expected\n",
        encoding="utf-8",
    )

    assert _selector_is_emitted(
        "test_converted.py::test_behavior_added_by_conversion", tests
    )


def test_pipe_selector_matches_hierarchical_suite_and_case_titles(tmp_path):
    tests = tmp_path / "tests"
    (tests / "test").mkdir(parents=True)
    (tests / "test" / "f2p_sorted_topics.js").write_text(
        "describe('Topic\\'s sorted topics', () => {\n"
        "  it('should get topics recent replied last', async () => {});\n"
        "});\n",
        encoding="utf-8",
    )
    selector = (
        "test/f2p_sorted_topics.js | "
        "Topic's sorted topics | should get topics recent replied last"
    )

    assert _selector_is_emitted(selector, tests)
    assert not _selector_is_emitted(
        "test/f2p_sorted_topics.js | Topic's sorted topics | missing case", tests
    )


def test_pipe_selector_resolves_repo_and_container_test_path_prefixes(tmp_path):
    tests = tmp_path / "tests"
    (tests / "f2p_tests").mkdir(parents=True)
    (tests / "f2p_tests" / "CurrentDeviceSectionF2P-test.tsx").write_text(
        "describe('<CurrentDeviceSection />', () => {\n"
        "  it('handles when device is falsy', () => {});\n"
        "});\n",
        encoding="utf-8",
    )

    assert _selector_is_emitted(
        "/tests/f2p_tests/CurrentDeviceSectionF2P-test.tsx | "
        "<CurrentDeviceSection /> | handles when device is falsy",
        tests,
    )


def test_missing_selector_feedback_suggests_actual_bundled_test_source(tmp_path):
    tests = tmp_path / "tests"
    (tests / "verifier_tests").mkdir(parents=True)
    actual = tests / "verifier_tests" / "RoomViewVerifier-test.tsx"
    actual.write_text("describe('room behavior', () => {});\n", encoding="utf-8")

    selector = "test/verifier/RoomViewVerifier-test.tsx | room behavior"
    assert not _selector_is_emitted(selector, tests)
    assert _selector_source_hints(selector, tests) == ["verifier_tests/RoomViewVerifier-test.tsx"]
