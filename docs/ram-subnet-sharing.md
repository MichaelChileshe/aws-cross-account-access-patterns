# AWS RAM: sharing a subnet with the internal analytics team

The analytics team (`nkosi-dev`) needed to run workloads inside Nkosi's governed network, without owning or changing it. Instead of peering another VPC into the mesh, I shared one subnet through **AWS Resource Access Manager**.

## Why sharing instead of peering

With peering, every team gets its own VPC. Every pair that needs to talk gets a peering connection, a route in both route tables, and a CIDR plan that mustn't overlap. Nobody owns the whole picture. With a shared VPC, the network team owns **one** VPC (routing, NACLs, flow logs, egress), and application accounts consume subnets from it. The reasoning is in [ADR 0004](adr/0004-ram-subnet-sharing-over-peering.md).

## What I built

| | Value |
|---|---|
| VPC | `nkosi-shared-vpc`, `10.90.0.0/16`, owned by Nkosi's account |
| Subnet | `nkosi-shared-analytics-1a`, `10.90.1.0/24`, `us-east-1a` |
| Resource share | `nkosi-shared-analytics-subnet` → the analytics account only |
| External principals | **Not allowed** (`--no-allow-external-principals`) |

No internet gateway, no NAT, nothing that bills by the hour.

```bash
aws ram enable-sharing-with-aws-organization        # once, from the management account
aws ram create-resource-share --name nkosi-shared-analytics-subnet \
  --resource-arns arn:aws:ec2:us-east-1:OWNER_ACCOUNT_ID:subnet/$SSUB \
  --principals ANALYTICS_ACCOUNT_ID \
  --no-allow-external-principals
```

- `enable-sharing-with-aws-organization` returned `"returnValue": true` ([`14`](screenshots/14-step7-ram-org-sharing-enabled.png)). It lets RAM share straight to accounts in the Organization without invitations.
- You share **subnets**, not VPCs. The participant sees the VPC through the subnet.
- `--no-allow-external-principals` means only accounts inside the Organization can ever be added. Subnet sharing requires this anyway.

## The participant's view

From the analytics account:

| Field | Value |
|---|---|
| `Owner` | **Nkosi's account**, not the analytics account |
| `Cidr` | `10.90.1.0/24` |
| `AZ` | `us-east-1a` |
| `AZId` | `use1-az1` |

Evidence: [`15`](screenshots/15-step7-participant-sees-shared-subnet.png).

The subnet is in the participant's view, but it isn't theirs.

## AZ name vs AZ ID

AZ **names** (`us-east-1a`) are mapped to physical zones independently for each account. AZ **IDs** (`use1-az1`) identify the physical zone. In my run, both accounts happened to map `us-east-1a` to the same zone, `use1-az1`. That was luck, not a guarantee. The lesson still stands: shared-network designs, and anything that places resources "in the same AZ" across accounts, should be written in **AZ IDs**.

## The participant tries to change it

```bash
aws ec2 modify-subnet-attribute --subnet-id $SSUB --map-public-ip-on-launch --profile dev-admin
```

Result ([`16`](screenshots/16-step7-participant-modify-denied.png)):

> `UnauthorizedOperation`: *A subnet in this vpc is shared but the provided object is not owned by you.*

Participants can launch resources into a shared subnet. They can't modify, delete or re-share it. Turning on auto-assigned public IPs is exactly the kind of change the network team must keep control of, and here the attempt was refused even though the caller was an administrator in its own account.

## Teardown note

A shared subnet can't be deleted while it's shared, so the resource share goes first. I also disabled RAM's Organization integration afterwards (`aws organizations disable-aws-service-access --service-principal ram.amazonaws.com`). Leaving it on is free and harmless, but I wanted the Organization back to exactly its pre-project state.
