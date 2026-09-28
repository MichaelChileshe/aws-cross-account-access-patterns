# ADR 0002: The auditor reads through a bucket policy and keeps its own identity

**Status:** Accepted
**Context:** An external audit firm reads Nkosi's audit evidence for about three weeks a year. Auditors must be **attributable**: Nkosi's records have to show which audit-firm principal read which evidence.

## Options considered

| Option | Verdict |
|---|---|
| Keep the shared IAM user | ❌ Long-lived, and CloudTrail shows only `ext-auditor-keys`, never which auditor |
| Cross-account role in Nkosi's account | ⚠️ Works, but the auditor acts *as Nkosi's role*. It also gives up its own account's permissions for the session |
| **Bucket policy naming the auditor's own role** | ✅ Chosen |

## Decision

- The audit firm creates `nkosi-auditor` in **its own** account and attaches an identity policy allowing `s3:GetObject` and `s3:ListBucket` on Nkosi's evidence bucket.
- Nkosi's bucket policy allows exactly `arn:aws:iam::AUDITOR_ACCOUNT_ID:role/nkosi-auditor`, not the whole audit-firm account.
- The bucket policy is Allow-only.

## Consequences

- CloudTrail in Nkosi's account records the **auditor's own principal**, from the auditor's own account.
- Access requires **both** sides. Trap B proved that removing the audit firm's identity policy blocks access even while Nkosi's bucket policy allows it. Either party can end the engagement unilaterally.
- The auditor's role must exist before Nkosi saves the bucket policy, because S3 rejects unknown principals.
- Limited to services with resource policies. If the auditor later needs, say, read-only access to CloudTrail Lake queries, that's a role-assumption case.
- If the evidence bucket moves to SSE-KMS, the key policy must also allow the auditor's role `kms:Decrypt`, and the auditor's identity policy must allow it too. The both-sides rule applies to KMS as well.
