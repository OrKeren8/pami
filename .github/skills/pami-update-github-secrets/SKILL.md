---
name: pami-update-github-secrets
description: "Use when user asks to update AWS GitHub secrets, refresh expired AWS credentials, or rotate temporary AWS tokens for Actions workflows. Keywords: update github secrets, aws credentials expired, set gh secrets, aws session token, cloud labs credentials."
---

# Update GitHub Secrets Skill

## Goal

Refresh temporary AWS credentials locally and update repository GitHub Actions secrets so deployments and log commands work again.

## Required Inputs

Ask the user for fresh temporary AWS credentials:

- `aws_access_key_id`
- `aws_secret_access_key`
- `aws_session_token`
- region (default `us-east-1`)

## Step 1: Configure local AWS CLI credentials

```bash
mkdir -p ~/.aws
cat > ~/.aws/credentials << 'EOF'
[default]
aws_access_key_id=<ACCESS_KEY>
aws_secret_access_key=<SECRET_KEY>
aws_session_token=<SESSION_TOKEN>
EOF
cat > ~/.aws/config << 'EOF'
[default]
region=us-east-1
output=json
EOF
aws sts get-caller-identity
```

If `sts get-caller-identity` fails, stop and ask for new credentials.

## Step 2: Update GitHub Actions secrets

Run from the repository root where `gh` is authenticated.

```bash
printf '%s' '<ACCESS_KEY>' | gh secret set AWS_ACCESS_KEY_ID
printf '%s' '<SECRET_KEY>' | gh secret set AWS_SECRET_ACCESS_KEY
printf '%s' '<SESSION_TOKEN>' | gh secret set AWS_SESSION_TOKEN
printf '%s' 'us-east-1' | gh secret set AWS_REGION
gh secret list
```

Expected result: the four AWS secrets appear in `gh secret list` with recent update times.

## Step 3: Quick verification command

```bash
aws ecs describe-services --cluster pami-cluster --services pami-projects-service --region us-east-1 --query "services[0].taskDefinition" --output text
```

If this works, credentials are active and AWS CLI access is restored.

## Notes

- Do not commit credentials to git.
- Only set secrets through `gh secret set` (or GitHub UI).
- Temporary Cloud Labs credentials expire; repeat this skill whenever tokens rotate.
