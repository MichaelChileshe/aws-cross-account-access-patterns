# Teardown: four accounts back to their starting state

Almost everything here is free, but teardown still matters. Leftover trust policies and bucket policies are *exactly* the forgotten external doors this project is about.

**Teardown-safety check:** every bucket policy in this build is **Allow-only**, so an administrator can always delete them. The only `Deny` statements are inside `nkosi-delegated-admin`'s own permissions, so they limit that role and no one else. That's why step 2 below works for the account administrator even though the delegated admin is forbidden from removing a boundary.

Run from the management account (Nkosi) unless a `--profile` says otherwise.

```bash
# 1. Access Analyzer
aws accessanalyzer delete-analyzer --analyzer-name nkosi-external-access

# 2. App role, delegated admin and boundary
#    The admin can remove the boundary; the Deny binds only the delegated-admin role.
aws iam detach-role-policy --role-name app-reporting --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam delete-role-permissions-boundary --role-name app-reporting
aws iam delete-role --role-name app-reporting
aws iam delete-role-policy --role-name nkosi-delegated-admin --policy-name delegated-role-admin
aws iam delete-role --role-name nkosi-delegated-admin
aws iam delete-policy --policy-arn $BOUNDARY

# 3. RAM share first (a shared subnet can't be deleted), then the network
aws ram delete-resource-share --resource-share-arn $SHARE_ARN
sleep 15
aws ec2 delete-subnet --subnet-id $SSUB
aws ec2 delete-vpc --vpc-id $SVPC

# 4. Vendor role
aws iam delete-role-policy --role-name nkosi-fraud-vendor-access --policy-name read-transactions
aws iam delete-role --role-name nkosi-fraud-vendor-access

# 5. Auditor role, in the audit firm's account
aws iam delete-role-policy --profile auditor-admin --role-name nkosi-auditor --policy-name read-nkosi-evidence
aws iam delete-role --profile auditor-admin --role-name nkosi-auditor

# 6. Buckets: policy off, empty, delete
for B in $TXN $AUDIT $DROP; do
  aws s3api delete-bucket-policy --bucket $B 2>/dev/null
  aws s3 rm s3://$B --recursive
  aws s3api delete-bucket --bucket $B
done

# 7. Optional: return RAM's Organization integration to its original state
aws organizations disable-aws-service-access --service-principal ram.amazonaws.com
```

**Why this order:**

- The app role's managed policy and boundary come off before the role can be deleted.
- The resource share goes before the subnet.
- Inline policies come off before their roles.
- Bucket policies are removed before emptying. With Allow-only policies that's belt and braces, but it's the habit that saves you when a bucket *does* carry a Deny.

The two `ext-` users and their access keys were already deleted in step 10 of the build. That deletion *is* the migration.

## Confirm clean

```bash
aws iam list-roles --query "Roles[?starts_with(RoleName,'nkosi-') || starts_with(RoleName,'app-')].RoleName" --output text
aws iam list-roles --profile auditor-admin --query "Roles[?RoleName=='nkosi-auditor'].RoleName" --output text
aws s3 ls | grep nkosi- || echo "no nkosi buckets"
aws ram get-resource-shares --resource-owner SELF --query "resourceShares[?status=='ACTIVE'].name" --output text
```

My result ([`25`](screenshots/25-step11-teardown-clean-check.png)):

| Check | Result |
|---|---|
| This build's roles in Nkosi's account | Gone. One unrelated leftover surfaced: `nkosi-flowlogs-role` from an earlier project (see [`debugging-journey.md`](debugging-journey.md#5--the-clean-check-wasnt-empty)) |
| `nkosi-auditor` in the audit firm's account | Gone |
| `nkosi-` buckets | `no nkosi buckets` |
| Active resource shares | None |
| Cost Explorer | **`-US$0.00`** ([`26`](screenshots/26-step11-cost-explorer-zero.png)) |

## Local clean-up

- Remove the `auditor-admin`, `fraud-admin`, `dev-admin`, `auditor` and `delegated-admin` blocks from `~/.aws/config` with the `configparser` approach in [`debugging-journey.md`](debugging-journey.md#1--i-erased-my-own-default-profile). Back up first.
- Delete the local `/tmp` seed files and the working JSON files.
