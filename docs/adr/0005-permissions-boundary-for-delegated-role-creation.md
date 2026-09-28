# ADR 0005: Permissions boundaries for delegated IAM role creation

**Status:** Accepted
**Context:** App teams need to create IAM roles for their workloads without waiting on the security team, and without being able to escalate their own privileges.

## Options considered

| Option | Verdict |
|---|---|
| Security team creates every role | ❌ A bottleneck, and teams route around bottlenecks |
| Give app teams `iam:*` | ❌ One `AdministratorAccess` attachment away from full escalation |
| **Delegated admin role + mandatory permissions boundary** | ✅ Chosen |

## Decision

- `nkosi-app-boundary` defines the ceiling for app roles: S3, DynamoDB, CloudWatch Logs and CloudWatch.
- `nkosi-delegated-admin` may create and change only `role/app-*`, and only when `iam:PermissionsBoundary` equals `nkosi-app-boundary`.
- Explicit Deny statements stop the delegated admin from removing a boundary from any role, or from editing or deleting the boundary policy.
- These Deny statements sit in the delegated admin's own policy, so they never constrain the account administrator (teardown-safe).

## Consequences

- The five tests confirmed the design: no boundary → denied; with boundary → created; `AdministratorAccess` attached → allowed but capped; the simulator showed `iam:CreateUser` and `ec2:RunInstances` as `implicitDeny`; removing the boundary → explicit deny; a non-`app-*` role → denied.
- App teams can attach whatever managed policies they like, and the boundary still decides the maximum.
- Changing the ceiling is a deliberate, central act: a new version of `nkosi-app-boundary`.
- To be production-complete, add `iam:PassRole` scoped to `app-*`, and back the boundary requirement with an SCP.
