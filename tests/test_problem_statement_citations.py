from swepro_trans.validation.revision import problem_statement_citation_errors


def test_exact_p_excerpt_is_accepted_with_whitespace_normalization():
    trace = {"f2p_accounting": [{
        "source_f2p": "historical::public_behavior",
        "behavior_classification": "p_supported_behavior",
        "problem_statement_quotes": ["The service returns a useful result. "],
    }]}
    assert problem_statement_citation_errors(
        trace, "The service returns\n a useful result."
    ) == []


def test_paraphrase_or_unrelated_quote_is_rejected():
    trace = {"f2p_accounting": [{
        "source_f2p": "historical::public_behavior",
        "behavior_classification": "p_supported_behavior",
        "problem_statement_quotes": ["The service returns a useful report."],
    }]}
    errors = problem_statement_citation_errors(trace, "The service returns a useful result.")
    assert len(errors) == 1
    assert "not present verbatim" in errors[0]


def test_quote_may_come_from_current_approved_addendum():
    trace = {"f2p_accounting": [{
        "source_f2p": "historical::specified_behavior",
        "behavior_classification": "base_regression_behavior",
        "problem_statement_quotes": ["The user can recover from the failure."],
    }]}
    assert problem_statement_citation_errors(
        trace, "The user can make a request.", "The user can recover from the failure."
    ) == []


def test_normative_behavior_requires_quote():
    trace = {"f2p_accounting": [{
        "source_f2p": "historical::behavior",
        "behavior_classification": "p_supported_behavior",
        "problem_statement_quotes": [],
    }]}
    errors = problem_statement_citation_errors(trace, "Any P text")
    assert len(errors) == 1
    assert "missing exact" in errors[0]


def test_non_normative_classifications_do_not_require_p_quote():
    trace = {"f2p_accounting": [{
        "source_f2p": "historical::detail",
        "behavior_classification": "implementation_detail",
        "problem_statement_quotes": [],
    }]}
    assert problem_statement_citation_errors(trace, "Any P text") == []
