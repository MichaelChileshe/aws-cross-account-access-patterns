# IAM Access Analyzer: finding every external door

Steps 3 to 7 of this build opened doors on purpose. In real accounts, doors also get opened by accident: a trust policy from a proof of concept, a bucket policy from a migration, a CI role nobody remembers. IAM Access Analyzer reads the policies themselves, and reports every resource that a principal outside the **zone of trust** can reach.

## Setup

```bash
aws accessanalyzer create-analyzer --analyzer-name nkosi-external-access --type ACCOUNT
```

- `--type ACCOUNT`: the zone of trust is **this account**. Anything reachable from any other account, including accounts in my own Organization, is a finding. That's what I wanted here, because the vendor and the auditor are modelled as member accounts.
- An `ORGANIZATION` analyzer would treat every member account as trusted and stay quiet about them. In production you'd run one at Organization level for real external exposure, plus account-level analyzers where accounts must be isolated from each other.
- External-access analysis is **free**. (Unused-access analysis is a separate, paid analyzer type.)

## The findings

```bash
aws accessanalyzer list-findings --analyzer-arn $ANALYZER \
  --filter '{"status":{"eq":["ACTIVE"]}}' \
  --query 'findings[].{Type:resourceType,Resource:resource,Principal:principal.AWS,Condition:condition}'
```

| # | Resource | External principal | Expected? |
|---|---|---|---|
| 1 | `role/ubuntu-retail-github-actions-terraform` | `null` in my query (web-identity federation, not an AWS account) | **No, forgotten** |
| 2 | `role/nkosi-fraud-vendor-access` | the vendor's account | Yes, Pattern A |
| 3 | `nkosi-audit-evidence-<acct>` bucket | `role/nkosi-auditor` in the audit firm's account | Yes, Pattern B |
| 4 | `nkosi-vendor-dropzone-<acct>` bucket | the vendor's account | Yes, drop zone |

Evidence: [`22`](screenshots/22-step9-access-analyzer-findings.png).

The three intended findings map one-to-one onto the doors I opened. The audit bucket's finding names the **exact role**, not the whole account, which confirms the bucket policy is as narrow as I meant it to be.

## Triage

Intended findings are reviewed and archived. Whatever stays `ACTIVE` is external access nobody has justified.

```bash
for F in $(aws accessanalyzer list-findings --analyzer-arn $ANALYZER \
    --filter '{"status":{"eq":["ACTIVE"]}}' \
    --query "findings[?contains(resource, 'nkosi-')].id" --output text); do
  aws accessanalyzer update-findings --analyzer-arn $ANALYZER --status ARCHIVED --ids $F
done
```

After triage, exactly one finding was still `ACTIVE` ([`23`](screenshots/23-step9-after-triage-oidc-role-still-active.png)):

```
arn:aws:iam::OWNER_ACCOUNT_ID:role/ubuntu-retail-github-actions-terraform
```

## The one I didn't plant

That role is the GitHub Actions deploy role from `aws-terraform-iac-pipeline`. Its trust policy federates GitHub's OIDC provider, so GitHub workflows can assume it with no stored AWS keys. That's the right pattern for CI/CD, but the role outlived its project, and I'd forgotten it.

The `principal.AWS` field is `null` because the trusted principal is a **federated** identity provider rather than an AWS account. The finding is still correct: something outside the account can assume this role.

In a real company this is the whole value of the tool. The three doors I opened on purpose are documented in ADRs. The one that causes an incident is the one nobody remembers. The follow-up for this role is:

1. Confirm its trust policy's `sub` condition is pinned to one repository and branch (`repo:<org>/<repo>:ref:refs/heads/main`), not a wildcard.
2. If the pipeline is retired, delete the role and the OIDC provider.
3. Otherwise, archive the finding with a recorded reason, so the next reviewer doesn't have to rediscover it.

## A caveat I'm keeping honest

In my query output, the `condition` field came back `{}` for every finding, including the vendor role that requires `sts:ExternalId`. So I don't use the finding as evidence that the external ID is enforced. [Trap A](trap-drills.md#trap-a-assume-the-vendor-role-without-the-external-id) is that evidence. Access Analyzer's job is to tell me *which* doors exist. The drills tell me each door locks.

## Running it as a standing control

- One analyzer per Region in use. Access Analyzer is regional, and the CIS AWS Foundations Benchmark expects it enabled across Regions.
- Findings go to EventBridge → SNS or a ticketing queue, so a new external door creates a ticket the day it appears.
- Archive rules for known-good patterns (for example, "the vendor's account on `nkosi-fraud-vendor-access`"), so only new doors reach a human.
- Use **policy validation** and **custom policy checks** in CI to catch a new external door before it's deployed, rather than after.
