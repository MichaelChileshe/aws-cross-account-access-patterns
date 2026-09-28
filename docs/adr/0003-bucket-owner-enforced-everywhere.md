# ADR 0003: Bucket owner enforced on every bucket (ACLs disabled)

**Status:** Accepted
**Context:** Fraudlytics writes fraud scores back into a Nkosi drop-zone bucket, using its own identity through a bucket policy. With S3 ACLs enabled (`ObjectWriter`), the writer owns the object.

## What I observed

With `ObjectWriter`, after the vendor uploaded `scores/scores-2026-09-24.csv`:

- Nkosi, the bucket owner, got **`403 Forbidden`** reading its own bucket.
- The object's `Owner.ID` matched **the vendor's** canonical ID.

After switching to `BucketOwnerEnforced`:

- The same object became readable by Nkosi immediately, with no re-upload.
- `Owner.ID` changed to **Nkosi's** canonical ID.

## Decision

- Every Nkosi bucket uses Object Ownership **`BucketOwnerEnforced`**. This has been the default for new buckets since April 2023, and I keep it explicit rather than relying on the default.
- Access is controlled with **policies only**: IAM, bucket policies and, where used, KMS key policies. No ACLs.
- Cross-account writers get `s3:PutObject` in the bucket policy, scoped to their prefix.

## Consequences

- Nkosi owns and governs every object in its buckets, whoever wrote it. Lifecycle, replication, Object Lock, encryption and deletion all behave predictably.
- Any client that still sends ACL headers other than `bucket-owner-full-control` gets an error. That's a feature: it surfaces legacy integrations.
- An SCP or AWS Config rule (`s3-bucket-acl-prohibited`) can enforce this across the Organization, so a new `ObjectWriter` bucket can't quietly reappear.
