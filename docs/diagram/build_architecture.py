#!/usr/bin/env python3
"""Regenerates docs/architecture.svg + docs/architecture.png using the OFFICIAL AWS Architecture Icons.

The icon pack is not committed (AWS licenses it for diagrams, not redistribution). Download it from
https://aws.amazon.com/architecture/icons/, unzip, then:

    AWS_ICONS_DIR=/path/to/unzipped-icon-package python3 build_architecture.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from awsdiag import Diagram, GREY, INK

ASSUME, RES, RAMC, GOV, RED, OK = "#DD344C", "#7AA116", "#8C4FFF", "#E7157B", "#D13212", "#1D8102"
d = Diagram(1800, 1250)

# title
d.text(40, 40, "Nkosi Payments — cross-account access without shared keys", 19, "bold")
d.text(40, 64, "4 AWS accounts in one Organization  ·  IAM roles + STS  ·  S3 bucket policies  ·  AWS RAM  ·  "
               "permissions boundary  ·  IAM Access Analyzer  ·  us-east-1", 13, "normal", GREY)

d.group("cloud", 20, 90, 1760, 1140, "AWS Cloud  ·  AWS Organizations")

# ---------------------------------------------------------------- Nkosi (data owner)
d.group("account", 45, 135, 1090, 1070, "Nkosi Payments  —  data owner (management account)")

def row_text(x, y, title, lines, color=GREY):
    d.text(x, y, title, 13, "bold")
    for i, t in enumerate(lines):
        d.text(x, y + 17 * (i + 1), t, 11.5, "normal", color)

DX = 900  # "door" column: the policy that lets each outsider in

def door(key, cy, title, lines, size=52):
    d.icon(key, DX, cy - size // 2, size)
    d.text(DX + 26, cy + 44, title, 13, "bold", anchor="middle")
    for i, t in enumerate(lines):
        d.text(DX + 26, cy + 61 + 16 * i, t, 11.5, "normal", GREY, "middle")

# Row A — transactions bucket + vendor role
cyA = 225
d.icon("s3", 110, cyA - 30, 60)
row_text(185, cyA - 12, "S3  nkosi-txn-data", ["transactions/*   → vendor may read", "internal/*          → vendor gets 403"])
door("iam_role", cyA, "IAM role  nkosi-fraud-vendor-access",
     ["trust: Fraudlytics account + sts:ExternalId", "perms: List/Get transactions/* only"])
d.line([(898, cyA), (420, cyA)], ASSUME)
d.label(560, cyA - 12, "temporary credentials · GetObject", ASSUME, 11)

# Row C — drop zone
cyC = 405
d.icon("s3", 110, cyC - 30, 60)
row_text(185, cyC - 12, "S3  nkosi-vendor-dropzone",
         ["Object Ownership: BucketOwnerEnforced", "was ObjectWriter → vendor owned the file, Nkosi 403"])
door("iam_permissions", cyC, "Bucket policy", ["Fraudlytics account: PutObject scores/*", "Allow-only · teardown-safe"])
d.line([(898, cyC), (560, cyC)], RES)

# Row B — audit evidence
cyB = 580
d.icon("s3", 110, cyB - 30, 60)
row_text(185, cyB - 12, "S3  nkosi-audit-evidence", ["evidence/*  → auditor reads as itself"])
door("iam_permissions", cyB, "Bucket policy", ["principal = the auditor's exact role", "(not the whole audit-firm account)"])
d.line([(898, cyB), (430, cyB)], RES)

# Shared VPC + RAM
d.group("vpc", 90, 690, 560, 180, "VPC  nkosi-shared-vpc  10.90.0.0/16")
d.group("private", 115, 735, 510, 115, "Subnet  nkosi-shared-analytics-1a")
d.text(155, 790, "10.90.1.0/24  ·  us-east-1a  ·  AZ ID use1-az1", 12, "normal", GREY)
d.text(155, 810, "owner keeps control: participants launch in,", 12, "normal", GREY)
d.text(155, 827, "they can't modify, delete or re-share it", 12, "normal", GREY)
cyR = 770
door("ram", cyR, "AWS RAM resource share", ["subnet → nkosi-dev only · org-only"])
d.line([(650, cyR), (898, cyR)], RAMC, dashed=True, arrow=False)

# Guardrails
d.box(70, 905, 1040, 280, GOV, fill="#FEF5FA")
d.text(88, 930, "Guardrails that keep it that way", 13.5, "bold", GOV)
d.icon("iam_role", 95, 955, 48)
row_text(155, 972, "nkosi-delegated-admin", ["may create/modify app-* roles", "ONLY with the boundary attached", "can't remove a boundary or edit it"])
d.line([(345, 980), (395, 980)], GOV)
d.icon("iam_role", 400, 955, 48)
d.icon("iam_permissions", 440, 990, 30)
row_text(485, 972, "app-reporting  + AdministratorAccess", ["boundary nkosi-app-boundary caps it at", "s3 · dynamodb · logs · cloudwatch", "iam:CreateUser / ec2:RunInstances → implicitDeny"])
d.icon("access_analyzer", 95, 1085, 52)
row_text(160, 1100, "IAM Access Analyzer  ·  zone of trust = this account",
         ["4 external-access findings: 3 intended (archived), 1 forgotten GitHub OIDC role from an earlier project",
          "the standing detective control for 'no external door nobody meant to open'"])

# ---------------------------------------------------------------- External accounts
# Fraudlytics
d.group("account", 1260, 135, 495, 355, "Fraudlytics  —  fraud-analytics vendor")
cyF = 315
d.icon("ec2_instance", 1300, cyF - 28, 56)
row_text(1368, cyF - 12, "vendor pipeline (their account)", ["serves many customers →", "needs a per-customer external ID"])
d.line([(1298, cyF - 12), (1200, cyF - 12), (1200, cyA), (954, cyA)], ASSUME)
d.icon("sts", 1180, 240, 40)
d.label(975, cyA - 12, "sts:AssumeRole + ExternalId", ASSUME, 11)
d.line([(1298, cyF + 14), (1225, cyF + 14), (1225, cyC), (954, cyC)], RES)
d.label(975, cyC - 12, "PutObject as itself", RES, 11)
d.text(1300, 405, "no external ID → AccessDenied", 11.5, "normal", RED)
d.text(1300, 423, "another customer's ID → AccessDenied", 11.5, "normal", RED)
d.text(1300, 441, "(confused deputy blocked)", 11.5, "normal", RED)

# Audit firm
d.group("account", 1260, 515, 495, 150, "Audit firm  —  external auditor")
d.icon("iam_role", 1300, cyB - 25, 50)
row_text(1362, cyB - 8, "role nkosi-auditor (their account)", ["identity policy: Get/List the audit bucket"])
d.line([(1298, cyB), (954, cyB)], RES)
d.label(975, cyB - 12, "GetObject as itself", RES, 11)
d.text(1362, cyB + 45, "remove this policy → 403 (both sides must allow)", 11.5, "normal", RED)

# Analytics team
d.group("account", 1260, 690, 495, 185, "Analytics team  —  nkosi-dev")
d.icon("users", 1300, cyR - 26, 52)
row_text(1365, cyR - 12, "sees the shared subnet", ["Owner = Nkosi's account", "modify-subnet-attribute →", "UnauthorizedOperation"])
d.line([(954, cyR), (1298, cyR)], RAMC, dashed=True)

# ---------------------------------------------------------------- Measured + legend
d.box(1165, 905, 590, 150, "#D5DBDB", fill="#fff", dashed=False)
d.text(1183, 930, "Measured", 13.5, "bold")
d.icon("long_creds", 1185, 948, 44)
d.icon("long_creds", 1235, 948, 44)
d.block(1233, 970, RED)
d.text(1300, 965, "ext-auditor-keys  ·  ext-fraudlytics-keys", 12, "normal", GREY)
d.text(1300, 990, "long-lived external access keys:  2 → 0", 16, "bold", OK)
d.text(1183, 1030, "every outsider now uses temporary credentials or its own identity", 12, "normal", GREY)

lx, ly = 1165, 1070
d.raw(f'<rect x="{lx}" y="{ly}" width="590" height="115" rx="4" fill="#fff" stroke="#D5DBDB"/>')
d.text(lx + 12, ly + 22, "Legend", 13, "bold")
d.line([(lx + 12, ly + 44), (lx + 62, ly + 44)], ASSUME)
d.text(lx + 72, ly + 48, "Pattern A — assume a role in Nkosi's account (temporary STS credentials)", 12)
d.line([(lx + 12, ly + 68), (lx + 62, ly + 68)], RES)
d.text(lx + 72, ly + 72, "Pattern B — resource policy (caller keeps its own identity)", 12)
d.line([(lx + 12, ly + 92), (lx + 62, ly + 92)], RAMC, dashed=True)
d.text(lx + 72, ly + 96, "AWS RAM subnet share (inside the Organization only)", 12)

here = os.path.dirname(os.path.abspath(__file__))
d.save(os.path.join(here, "..", "architecture.svg"), os.path.join(here, "..", "architecture.png"))
print("wrote docs/architecture.svg and docs/architecture.png")
