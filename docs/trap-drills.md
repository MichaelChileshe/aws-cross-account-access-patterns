# Trap drills: proving the guardrails fail closed

A working happy path proves access *works*. It doesn't prove access is *controlled*. For each pattern I deliberately did the thing a careless integration, or an attacker, would do, and confirmed AWS refused.

Account IDs are shown as placeholders here. The screenshots show the real run.

---

## Trap A: assume the vendor role without the external ID

**The real-world risk:** the confused deputy. Fraudlytics' system assumes roles in many customers' accounts. If Nkosi's trust policy only checked "is this Fraudlytics' account?", another Fraudlytics customer could register *Nkosi's* role ARN in their own Fraudlytics settings, and Fraudlytics' pipeline would read Nkosi's data and hand it to them.

**The drill** (run from the vendor's account, as an administrator there):

```bash
aws sts assume-role --profile fraud-admin --role-arn $FRAUD_ROLE \
  --role-session-name no-external-id ; echo "exit=$?"

aws sts assume-role --profile fraud-admin --role-arn $FRAUD_ROLE \
  --role-session-name wrong-external-id --external-id some-other-customer ; echo "exit=$?"
```

**Result:** both calls returned **`AccessDenied`** for `sts:AssumeRole`, with `exit=254` ([`06`](screenshots/06-trapA-external-id-missing-and-wrong-denied.png)). The caller was in the right account and had admin rights there. The only thing missing was the agreed external ID. The second call is the confused-deputy attack in miniature: another customer's ID can't open Nkosi's door.

**What the external ID is and isn't:** it isn't a password, and it doesn't need to be secret from the vendor. It's a per-customer value that stops the vendor's own system being used against its customers. It isn't needed for roles between your own accounts.

---

## Trap B: the bucket policy alone isn't enough

**The real-world risk:** teams assume that a bucket policy naming a partner is all it takes, then lose hours when the partner reports `AccessDenied`. The reverse also matters. If the partner's own administrators remove their identity policy, access stops, whatever the owner's policy says.

**The drill:** delete the auditor's identity policy in the **audit firm's** account, and leave Nkosi's bucket policy untouched.

```bash
aws iam delete-role-policy --profile auditor-admin --role-name nkosi-auditor \
  --policy-name read-nkosi-evidence
sleep 10
aws s3 cp s3://$AUDIT/evidence/q3-access-review.txt - --profile auditor ; echo "exit=$?"
```

**Result:** **`403`**, even though Nkosi's bucket policy still explicitly allowed `role/nkosi-auditor`. After I restored the identity policy, the same read worked again ([`09`](screenshots/09-trapB-identity-policy-removed-denied-then-restored.png)).

**Why:** cross-account access is evaluated on both sides. Nkosi's resource policy opened Nkosi's door. The audit firm's account didn't authorise its own role to walk through it. Inside a single account, the bucket policy alone *would* have been enough, and that's the difference that makes this worth drilling.

---

## Trap C: the vendor owns a file in Nkosi's bucket

**The real-world risk:** before AWS changed the default for new buckets in April 2023, this caught many companies. A vendor wrote files into the customer's bucket, and the customer couldn't read them, couldn't audit them, and couldn't even see who else could.

**The setup:** a drop-zone bucket created with **ACLs enabled** on purpose.

```bash
aws s3api create-bucket --bucket $DROP --region us-east-1 --object-ownership ObjectWriter
```

The bucket policy ([`dropzone-policy.json`](../policies/dropzone-policy.json)) lets the vendor's account `PutObject` under `scores/` and read the ACL of what it wrote. The vendor then uploaded **as itself**, not through Nkosi's role:

```bash
aws s3 cp /tmp/scores.csv s3://$DROP/scores/scores-2026-09-24.csv --profile fraud-admin
```

**The broken state:**

| Check | Result |
|---|---|
| Object Ownership | `ObjectWriter` ([`10`](screenshots/10-trapC-dropzone-objectwriter.png)) |
| Nkosi reads its own bucket | **`403 Forbidden`** ([`11`](screenshots/11-trapC-vendor-write-owner-gets-403.png)) |
| Object `Owner.ID` | Matches **the vendor's** canonical ID, not Nkosi's ([`12`](screenshots/12-trapC-object-owned-by-vendor.png)) |

Nkosi owned the bucket, but not the object. The object's ACL granted access only to its owner, the vendor.

**The fix:** one setting.

```bash
aws s3api put-bucket-ownership-controls --bucket $DROP \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'
```

| Check | Result |
|---|---|
| Object Ownership | `BucketOwnerEnforced` |
| Nkosi reads the same object | ✅ Works |
| Object `Owner.ID` | Now **Nkosi's** canonical ID ([`13`](screenshots/13-trapC-bucket-owner-enforced-fixed.png)) |

`BucketOwnerEnforced` disables ACLs entirely, and with ACLs disabled the bucket owner owns every object, **including ones that already existed**. No re-upload was needed.

**The rule I took from it:** keep every bucket on `BucketOwnerEnforced` and control access with policies only. The decision is recorded in [ADR 0003](adr/0003-bucket-owner-enforced-everywhere.md).
