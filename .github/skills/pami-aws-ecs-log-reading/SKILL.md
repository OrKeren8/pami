---
name: pami-aws-ecs-log-reading
description: "Use when user asks to read ECS logs, check CloudWatch logs, debug deployed AWS service issues, or verify runtime errors in pami-cluster. Keywords: ecs logs, cloudwatch logs, read logs, pami-projects-service, ai_service_url, task definition, deployment issues."
---

# AWS ECS Log Reading Skill

## Goal

Quickly diagnose runtime backend issues in AWS by reading current ECS/CloudWatch logs and validating active task configuration.

## Credential Prerequisite

This skill assumes AWS CLI credentials are already configured and valid.
If AWS auth fails (`ExpiredToken`, `InvalidClientTokenId`, `UnrecognizedClientException`), use the `pami-update-github-secrets` skill first to refresh local credentials and GitHub secrets.

## Standard Diagnostic Flow

Run these in order.

### 1) Identify active service revision

```bash
aws ecs describe-services \
  --cluster pami-cluster \
  --services pami-projects-service \
  --region us-east-1 \
  --query "services[0].{taskDef:taskDefinition,running:runningCount,desired:desiredCount,deployments:deployments[].{status:status,taskDef:taskDefinition}}" \
  --output json
```

### 2) Inspect runtime env vars (especially AI_SERVICE_URL)

```bash
TD_ARN=$(aws ecs describe-services \
  --cluster pami-cluster \
  --services pami-projects-service \
  --region us-east-1 \
  --query 'services[0].taskDefinition' \
  --output text)

aws ecs describe-task-definition \
  --task-definition "$TD_ARN" \
  --region us-east-1 \
  --query "taskDefinition.containerDefinitions[?name=='pami-projects-service'].environment" \
  --output json
```

### 3) Resolve current ALB DNS for comparison

```bash
aws elbv2 describe-load-balancers \
  --region us-east-1 \
  --query "LoadBalancers[?LoadBalancerName=='pami-alb'].DNSName | [0]" \
  --output text
```

### 4) Read latest CloudWatch logs

In Git Bash, disable path conversion for log group names starting with `/`.

```bash
MSYS2_ARG_CONV_EXCL='*' aws logs tail /ecs/pami-projects-service --region us-east-1 --since 20m
```

Optional targeted filtering:

```bash
MSYS2_ARG_CONV_EXCL='*' aws logs tail /ecs/pami-projects-service --region us-east-1 --since 20m | grep -Ei "ai_organize_node|tree-analysis|ai-conversations|ERROR|Cannot connect|Name or service"
```

## Fast Interpretation Rules

- If logs show `Cannot connect to host ... Name or service not known`:
  - `AI_SERVICE_URL` points to stale/invalid host.
- If `AI_SERVICE_URL` lacks `/ai` while service expects `/ai/...` routes:
  - routing mismatch likely.
- If logs show `Calling AI tree-analysis ...` then `status=200` and `Updated node ... with AI suggestions`:
  - connectivity and AI path are currently healthy.

## Report Template

When done, summarize in 4 bullets:

1. Active task definition revision.
2. Current `AI_SERVICE_URL` value.
3. Current ALB DNS value.
4. Most recent AI call outcome from logs (error/success).

## If Fix Is Needed

If `AI_SERVICE_URL` is stale, recommend updating deployment workflow and forcing new deployment. Do not hardcode old ALB DNS in task definitions.
