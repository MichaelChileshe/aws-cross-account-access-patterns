# Delegated role creation under a permissions boundary

## The problem

App teams constantly need new IAM roles: a Lambda here, a batch job there. If every request waits for the central security team, delivery stalls. If app teams get `iam:*`, one of them eventually creates a role with `AdministratorAccess` and uses it. That's privilege escalation through the front door.

A **permissions boundary** makes delegation safe. It's a managed policy that sets the **maximum** permissions a role can have. The effective permissions of any request are the identity policy **intersected** with the boundary (and any SCP and session policy on top). A boundary grants nothing by itself.

## The two policies

**The ceiling**, [`app-boundary.json`](../policies/app-boundary.json): `s3:*`, `dynamodb:*`, `logs:*`, `cloudwatch:*`. No app role can ever exceed that.

**The delegated admin**, [`delegated-admin-perms.json`](../policies/delegated-admin-perms.json):

| Statement | Effect | What it does |
|---|---|---|
| `ManageAppRolesOnlyWithBoundary` | Allow | `CreateRole`, `Attach/DetachRolePolicy`, `Put/DeleteRolePolicy` and `PutRolePermissionsBoundary`, **only** on `role/app-*` and **only** when `iam:PermissionsBoundary` equals `nkosi-app-boundary` |
| `DeleteAndReadAppRoles` | Allow | Housekeeping on `app-*` roles |
| `ReadIamGenerally` | Allow | List and read, for visibility |
| `NeverRemoveABoundary` | **Deny** | `iam:DeleteRolePermissionsBoundary` on any role |
| `NeverEditTheBoundaryPolicy` | **Deny** | Creating, deleting or switching versions of the boundary policy, or deleting it |

Allowing `PutRolePermissionsBoundary` under the same condition means the delegated admin can only ever set *this exact* boundary, never a weaker one. Without the two Deny statements it could raise its own ceiling, either by removing the boundary from a role or by publishing a new version of the boundary policy with `"Action": "*"`.

**Teardown-safety:** both Deny statements sit in the **delegated admin's own** permissions. They limit that role and nobody else, so an account administrator can always remove the boundary and delete everything.

## The five tests

| # | Attempt (as the delegated admin) | Result | Evidence |
|---|---|---|---|
| 1 | Create `app-reporting` **without** a boundary | ❌ `AccessDenied`: no identity-based policy allows it, because the condition fails | [`17`](screenshots/17-step8-test1-no-boundary-denied.png) |
| 2 | Create `app-reporting` **with** the boundary | ✅ Created. `get-role` shows `PermissionsBoundaryArn` = `nkosi-app-boundary` | [`18`](screenshots/18-step8-test2-created-with-boundary.png) |
| 3 | Attach **`AdministratorAccess`** to it | ✅ Allowed (`exit=0`). The role carries the boundary, so the condition matches | [`19`](screenshots/19-step8-test3-administratoraccess-attached.png) |
| 4 | What can that role actually do? (simulated as the account admin) | S3 and DynamoDB **allowed**. `iam:CreateUser` and `ec2:RunInstances` **implicitDeny** | [`20`](screenshots/20-step8-test4-simulation-capped-by-boundary.png) |
| 5a | Remove the boundary from `app-reporting` | ❌ **Explicit deny** in an identity-based policy (`NeverRemoveABoundary`) | [`21`](screenshots/21-step8-test5-boundary-escape-denied.png) |
| 5b | Create a role called `escape-hatch` (not `app-*`), even with the boundary | ❌ `AccessDenied`: outside the resource scope | [`21`](screenshots/21-step8-test5-boundary-escape-denied.png) |

## Why Test 3 is the point

Test 3 looks like a failure: the delegated admin attached `AdministratorAccess` and AWS said yes. Test 4 shows why that's fine:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::OWNER_ACCOUNT_ID:role/app-reporting \
  --action-names s3:ListAllMyBuckets dynamodb:ListTables iam:CreateUser ec2:RunInstances
```

```
s3:ListAllMyBuckets   allowed
dynamodb:ListTables   allowed
iam:CreateUser        implicitDeny
ec2:RunInstances      implicitDeny
```

`simulate-principal-policy` evaluates the role's real attached policies **including its permissions boundary**. `AdministratorAccess` ∩ boundary = S3, DynamoDB, Logs and CloudWatch. Whatever an app team attaches, the ceiling holds. That's what lets a security team say yes to delegation.

## What I'd add in production

- Put the boundary condition into an **SCP** as well, so it holds even if someone edits the delegated admin's policy.
- Add `iam:PassRole` scoped to `app-*`, so app teams can actually hand these roles to Lambda or ECS.
- Require a naming-plus-tag convention (`aws:RequestTag/team`) so every delegated role is attributable to a team.
