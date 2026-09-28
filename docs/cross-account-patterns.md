# Cross-account patterns: role assumption vs resource-based policy

Both of Nkosi's outsiders needed to read an S3 bucket in Nkosi's account. I deliberately gave them **different** patterns so I could compare them on real accounts instead of on paper.

## How AWS decides a cross-account request

For a request from account B to a resource in account A, AWS evaluates two separate questions:

1. **Does account A allow it?** This is the resource's policy (a bucket policy), or for role assumption, the role's **trust policy**.
2. **Does account B allow it?** This is the caller's own **identity policy**, attached by account B's administrators.

Both have to say yes. Inside a single account, either one is enough, which is why this catches people out when they move from single-account to multi-account work. Trap B in [`trap-drills.md`](trap-drills.md#trap-b-the-bucket-policy-alone-isnt-enough) proves it.

For role assumption the rule applies twice. The vendor's own IAM must allow `sts:AssumeRole` on Nkosi's role, and Nkosi's trust policy must name the vendor. Once assumed, the vendor is acting *inside* Nkosi's account, so only Nkosi's permissions policy on the role matters from then on.

## Pattern A: the vendor assumes a role

```
Fraudlytics pipeline ──sts:AssumeRole + ExternalId──► role nkosi-fraud-vendor-access (Nkosi's account)
                                                            │ temporary credentials (1 hour)
                                                            ▼
                                                 s3://nkosi-txn-data/transactions/*
```

- **Trust policy** ([`fraud-vendor-trust.json`](../policies/fraud-vendor-trust.json)): principal `arn:aws:iam::VENDOR_ACCOUNT_ID:root`, with `sts:ExternalId` required. In a principal, `:root` means *the account*, not its root user: any principal in that account whose own IAM allows the call can assume the role.
- **Permissions policy** ([`fraud-vendor-perms.json`](../policies/fraud-vendor-perms.json)): `s3:ListBucket` with an `s3:prefix` condition of `transactions/*`, and `s3:GetObject` on `transactions/*` only.
- **What I saw:** `get-caller-identity` returned `assumed-role/nkosi-fraud-vendor-access/fraudlytics-pipeline`. The session name records *which* vendor process acted. The transactions CSV printed, and `internal/contracts.txt` returned `403` ([`05`](screenshots/05-step3-vendor-assumed-role-prefix-scoped.png)).

**Why this fits the vendor:** it's an automated system acting *for* Nkosi. Nkosi wants full control of what it can do, in Nkosi's own policy language, with credentials that expire on their own. Revoking the vendor means editing one trust policy in Nkosi's account. There's no key to hunt down in someone else's config.

## Pattern B: the auditor keeps its own identity

```
role nkosi-auditor (audit firm's account) ──s3:GetObject──► s3://nkosi-audit-evidence (Nkosi's account)
  identity policy: allows Get/List on Nkosi's bucket          bucket policy: allows role/nkosi-auditor
```

- **Caller side** ([`auditor-identity.json`](../policies/auditor-identity.json)): attached by the audit firm to its own role.
- **Resource side** ([`audit-bucket-policy.json`](../policies/audit-bucket-policy.json)): Nkosi's bucket policy names **the exact role**, `role/nkosi-auditor`, not the whole audit-firm account.
- **What I saw:** the identity was `assumed-role/nkosi-auditor/...` in the **audit firm's** account ([`07`](screenshots/07-step4-auditor-own-identity.png)). The auditor never touched STS in Nkosi's account.

**Why this fits the auditor:** an audit trail has to show *who* at the audit firm read the evidence. With a resource policy, Nkosi's CloudTrail records the auditor's own principal. The auditor also keeps its own account's permissions while working. With role assumption it would have given those up for the duration of the session.

**Ordering gotcha:** S3 validates principals when a bucket policy is saved. The auditor's role must exist *before* Nkosi saves the policy, otherwise S3 rejects it as `Invalid principal`.

## Side by side

| | Role assumption | Resource-based policy |
|---|---|---|
| Whose identity acts | The role in the **owner's** account | The caller's **own** identity |
| Caller keeps its own permissions? | No, only the role's | Yes |
| Credentials | Temporary STS credentials | The caller's own |
| Where access is defined | Owner's trust policy + owner's permissions policy (plus the caller's `sts:AssumeRole` permission) | Owner's resource policy + the caller's identity policy |
| Revoke by | Editing the trust policy | Editing the resource policy |
| Services | Anything IAM can grant | Only services with resource policies (S3, KMS, SQS, SNS, Lambda, Secrets Manager, ECR, …) |
| Confused-deputy defence | External ID | Name the exact principal ARN |
| Best for | A third-party system acting on your behalf | A party that must stay attributable as itself |

## The side effect that decides object ownership

The pattern also changes who *writes* objects. If the vendor writes while holding Nkosi's role, the writer is Nkosi, and Nkosi owns the object. If the vendor writes **as itself** through a bucket policy, as it does in the drop zone, the writer is the vendor. With ACLs enabled, the vendor then *owns* the object. That's exactly the trap I reproduced in [Trap C](trap-drills.md#trap-c-the-vendor-owns-a-file-in-nkosis-bucket) and closed with `BucketOwnerEnforced` ([ADR 0003](adr/0003-bucket-owner-enforced-everywhere.md)).
