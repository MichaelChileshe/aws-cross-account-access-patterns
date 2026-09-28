#!/usr/bin/env bash
# Counts ACTIVE access keys on every IAM user whose name starts with "ext-".
# That prefix is how Nkosi tagged "outsider" users that exist only to hold a key.
# Baseline before this project: 2. After: 0.
set -euo pipefail
export AWS_PAGER=""

count=0
for user in $(aws iam list-users --query 'Users[?starts_with(UserName, `ext-`)].UserName' --output text); do
  keys=$(aws iam list-access-keys --user-name "$user" \
    --query 'AccessKeyMetadata[?Status==`Active`].AccessKeyId' --output text)
  n=$(echo "$keys" | wc -w)
  printf '%-28s %s active key(s)\n' "$user" "$n"
  count=$((count + n))
done
echo "long-lived external access keys: $count"
