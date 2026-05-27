# AWS Cost Management Scripts

## Shutdown Script

**Purpose:** Stop all expensive AWS resources at the end of your session to minimize costs.

**Cost Savings:**

- Running: ~$2.25/day
- After shutdown: ~$0.05/day
- **Savings: ~$2.20/day (~$66/month)**

### Usage

```bash
# Set your AWS credentials first
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_SESSION_TOKEN="your-token"

# Run shutdown
python shutdown_aws.py
```

**What it does:**

1. ✅ Stops all 3 ECS Fargate services (sets desired count to 0)
2. ✅ Deletes the Application Load Balancer
3. ✅ Keeps ECR, S3, API Gateway (minimal/no cost when idle)

## Restart Everything

When you're ready to work again:

```bash
# 1. Set AWS credentials (get fresh ones from AWS Academy)
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_SESSION_TOKEN="your-token"

# 2. Recreate infrastructure
python setup_aws_infrastructure.py

# 3. Trigger deployment to start services
git commit --allow-empty -m "Restart services"
git push
```

**Time to be fully operational:** ~10 minutes

## Quick Status Check

```bash
# Check if services are running
aws ecs describe-services \
  --cluster pami-cluster \
  --services pami-projects-service pami-slack-service pami-ai-conversation-service \
  --region us-east-1 \
  --query 'services[*].[serviceName,runningCount,desiredCount]' \
  --output table
```

## What Stays, What Goes

### Deleted (Costs Saved):

- ❌ **ECS Tasks** - $1.70/day saved
- ❌ **Application Load Balancer** - $0.55/day saved
- ❌ **Target Groups** - Auto-deleted with ALB

### Kept (Minimal Cost):

- ✅ **ECS Cluster** (empty) - Free
- ✅ **ECR Repositories** - ~$0.01/day (small images)
- ✅ **S3 Bucket** - ~$0.02/day (conversation data)
- ✅ **API Gateway** - Pay per request ($0 when idle)
- ✅ **CloudWatch Logs** - ~$0.02/day
- ✅ **Amplify** - Pay per build ($0 when not building)

## Best Practices

1. **End of day:** Run `python shutdown_aws.py`
2. **Start of day:** Run `python setup_aws_infrastructure.py` then trigger deployment
3. **Check costs:** AWS Console → Billing Dashboard
4. **AWS Academy:** Labs reset every 4 hours, credentials expire

## Important Notes

- Amplify frontend will show errors when backend is down (expected)
- All your data is safe in MongoDB and S3
- Docker images stay in ECR (no need to rebuild)
- Target groups auto-delete ~2 minutes after ALB deletion
- Setup script is idempotent (safe to run multiple times)

## Emergency: Force Stop Everything

If you need to stop immediately without the script:

```bash
# Stop all services
aws ecs update-service --cluster pami-cluster --service pami-projects-service --desired-count 0 --region us-east-1
aws ecs update-service --cluster pami-cluster --service pami-ai-conversation-service --desired-count 0 --region us-east-1
aws ecs update-service --cluster pami-cluster --service pami-slack-service --desired-count 0 --region us-east-1

# Delete load balancer
aws elbv2 delete-load-balancer \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:909189231170:loadbalancer/app/pami-alb/d378f0bd4f903c82 \
  --region us-east-1
```
