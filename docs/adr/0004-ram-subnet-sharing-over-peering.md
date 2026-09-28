# ADR 0004: Share subnets with AWS RAM instead of peering team VPCs

**Status:** Accepted
**Context:** The internal analytics team needs to run workloads inside Nkosi's governed network. The network team must keep control of routing, egress and subnet settings.

## Options considered

| Option | Verdict |
|---|---|
| Give the team its own VPC and peer it | ❌ Adds a routed network, a peering connection and CIDR coordination for every team. The mesh grows quadratically and nobody owns the whole |
| Transit Gateway hub-and-spoke | ⚠️ The right answer when teams genuinely need their own VPCs. Heavier than needed for "run in our network" |
| **Shared VPC via AWS RAM subnet sharing** | ✅ Chosen |

## Decision

- Nkosi's account owns `nkosi-shared-vpc`. The subnet `nkosi-shared-analytics-1a` is shared through AWS RAM to the analytics account only.
- The share uses `--no-allow-external-principals`, so it's limited to the Organization.
- Designs that span accounts refer to **AZ IDs** (`use1-az1`), not AZ names.

## Consequences

- The participant sees the subnet with `Owner` = Nkosi's account and can launch into it.
- The participant **can't** modify, delete or re-share it. `modify-subnet-attribute` returned `UnauthorizedOperation` even for the participant's administrator.
- Each account still owns and pays for its own resources in the shared subnet, and security groups remain per-account.
- The network team becomes a dependency for new subnets. That's intended: it's the control point.
- A shared subnet can't be deleted while shared, so teardown must remove the share first.
