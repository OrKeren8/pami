# AWS Infrastructure Setup Guide

## When Your Lab Gets Deleted

Follow these steps to recreate your AWS infrastructure from scratch:

### Step 1: Get AWS Academy Credentials

1. Login to AWS Academy
2. Start your lab
3. Click "AWS Details"
4. Click "Show" next to AWS CLI credentials
5. Copy all three values:
   - `aws_access_key_id`
   - `aws_secret_access_key`
   - `aws_session_token`

### Step 2: Configure AWS CLI

Option A - Using environment variables (Windows):

```bash
set AWS_ACCESS_KEY_ID=your_access_key_here
set AWS_SECRET_ACCESS_KEY=your_secret_key_here
set AWS_SESSION_TOKEN=your_session_token_here
set AWS_DEFAULT_REGION=us-east-1
```

Option B - Using aws configure (for persistent credentials):

```bash
aws configure
# Enter access key, secret key, region: us-east-1
# Then manually set session token:
aws configure set aws_session_token your_session_token_here
```

### Step 3: Install boto3

```bash
pip install -r infrastructure-requirements.txt
```

### Step 4: Run the Setup Script

```bash
python setup_aws_infrastructure.py
```

The script will:

- ✓ Create ECS cluster: `pami-cluster`
- ✓ Create ECR repositories for all services
- ✓ Create CloudWatch log groups
- ✓ Create S3 bucket for AI conversation service
- ✓ Create security group with proper ports
- ✓ Create Application Load Balancer
- ✓ Create target groups for each service
- ✓ Set up ALB listeners and routing rules

**The script is idempotent** - you can run it multiple times safely. It checks if resources exist before creating them.

### Step 5: Update GitHub Secrets (CRITICAL!)

Go to your GitHub repository → Settings → Secrets and variables → Actions

**Update these secrets with your NEW AWS Academy credentials:**

- `AWS_ACCESS_KEY_ID` - from Step 1 ⚠️ **MUST UPDATE**
- `AWS_SECRET_ACCESS_KEY` - from Step 1 ⚠️ **MUST UPDATE**
- `AWS_SESSION_TOKEN` - from Step 1 ⚠️ **MUST UPDATE**

**Verify/set these application secrets:**

- `MONGODB_URL` - your MongoDB Atlas connection string
- `OPENAI_API_KEY` - your OpenAI API key (for AI conversation service) ⚠️ **REQUIRED**
- `SLACK_BOT_TOKEN` - your Slack app bot token
- `SLACK_SIGNING_SECRET` - your Slack app signing secret

### Step 6: Update Workflow Files (CRITICAL!)

⚠️ **Your workflow files have HARDCODED subnets and security groups that will be WRONG in your new lab!**

The setup script will output the correct values. You MUST update them in your workflows.

**File: `.github/workflows/deploy-slack-service.yml`**

Find the line with `--network-configuration` (around line 114) and update with values from script output:

```yaml
--network-configuration "awsvpcConfiguration={subnets=[YOUR_NEW_SUBNET_1,YOUR_NEW_SUBNET_2],securityGroups=[YOUR_NEW_SECURITY_GROUP],assignPublicIp=ENABLED}"
```

Also find the line with `--load-balancers` and update the target group ARN:

```yaml
--load-balancers "targetGroupArn=YOUR_NEW_TARGET_GROUP_ARN,containerName=slack-service,containerPort=8002"
```

Replace `REPLACE_WITH_ACTUAL_ARN` with the actual ARN output by the script.

**File: `.github/workflows/deploy-backend.yml`**

⚠️ **WARNING:** Your backend services (projects-service and ai-conversation-service) don't have network configuration in their workflows. The workflows only UPDATE services but don't CREATE them.

After running the setup script, you may need to manually create these services once, OR add network configuration to the workflows if they try to create services.

### Step 7: Deploy

Push to the `main` branch and GitHub Actions will automatically:

1. Build Docker images
2. Push to ECR
3. Deploy to ECS

## Troubleshooting

### "Credentials are expired"

Your AWS Academy session expired. Go back to Step 1 and get fresh credentials.

### "Repository does not exist"

ECR repository wasn't created. Run the setup script again.

### "Cluster not found"

ECS cluster wasn't created. Run the setup script again.

### Script fails with permissions error

Make sure your AWS Academy lab has started and credentials are valid.

## What Gets Deleted vs What Persists

**Deleted when lab ends:**

- All AWS resources (ECS cluster, ECR images, load balancers, S3 buckets, etc.)
- AWS credentials
- **Subnets and security group IDs change** ⚠️

**Persists:**

- Your GitHub repository code
- GitHub secrets (but AWS credentials need updating)
- MongoDB Atlas database (if using Atlas)
- Slack app configuration
- OpenAI API key

## Cost Considerations

AWS Academy labs have budgets. To stay within budget:

- Stop ECS services when not actively developing
- Delete unused Docker images from ECR
- Use spot instances if available (not in current setup)

## Quick Reference

**Check if infrastructure exists:**

```bash
aws ecs describe-clusters --cluster pami-cluster
aws ecr describe-repositories --repository-names pami/projects-service
```

**View running services:**

```bash
aws ecs list-services --cluster pami-cluster
```

**Check service status:**

```bash
aws ecs describe-services --cluster pami-cluster --services pami-projects-service
```
