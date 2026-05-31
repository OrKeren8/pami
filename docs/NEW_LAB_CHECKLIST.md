# 🚨 NEW LAB CHECKLIST

Use this checklist when your AWS Academy lab is recreated.

## ✅ Step-by-Step Checklist

### 1. Get AWS Credentials

- [ ] Login to AWS Academy
- [ ] Start your lab
- [ ] Get AWS CLI credentials (access key, secret key, session token)
- [ ] Set environment variables or run `aws configure`

### 2. Run Infrastructure Setup

- [ ] Install boto3: `pip install -r infrastructure-requirements.txt`
- [ ] Run script: `python setup_aws_infrastructure.py`
- [ ] **Copy the output** - you'll need the subnet IDs, security group ID, and target group ARNs

### 3. Update GitHub Secrets ⚠️ CRITICAL

Go to GitHub repo → Settings → Secrets and variables → Actions

#### Must Update (Changes Every Lab):

- [ ] `AWS_ACCESS_KEY_ID`
- [ ] `AWS_SECRET_ACCESS_KEY`
- [ ] `AWS_SESSION_TOKEN`

#### Verify These Are Set:

- [ ] `MONGODB_URL`
- [ ] `OPENAI_API_KEY` ← **Don't forget this!**
- [ ] `SLACK_BOT_TOKEN`
- [ ] `SLACK_SIGNING_SECRET`

### 4. Update Workflow Files ⚠️ CRITICAL

Your workflows have HARDCODED values that WILL BE WRONG!

#### File: `.github/workflows/deploy-slack-service.yml`

Line ~114, update network-configuration:

- [ ] Replace old subnet IDs with new ones from script output
- [ ] Replace old security group ID with new one from script output

Line ~115, update load-balancers:

- [ ] Replace `REPLACE_WITH_ACTUAL_ARN` with actual target group ARN from script output

**Before:**

```yaml
subnets=[subnet-065ce43c3f6e16d41,subnet-0b0e96bd3e6f30151]
securityGroups=[sg-0479a02a0d7531feb]
targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:669954808028:targetgroup/slack-service-tg/REPLACE_WITH_ACTUAL_ARN
```

**After (use values from script output):**

```yaml
subnets=[YOUR_NEW_SUBNET_1,YOUR_NEW_SUBNET_2]
securityGroups=[YOUR_NEW_SECURITY_GROUP_ID]
targetGroupArn=YOUR_ACTUAL_TARGET_GROUP_ARN
```

#### File: `.github/workflows/deploy-backend.yml`

- [ ] Check if services need network configuration added
- [ ] May need to manually create services first time if workflows only update

### 5. Commit and Deploy

- [ ] Commit workflow changes to git
- [ ] Push to main branch
- [ ] Monitor GitHub Actions for successful deployment

### 6. Verify Deployment

- [ ] Check ECS services are running: `aws ecs list-services --cluster pami-cluster`
- [ ] Check service health in AWS Console
- [ ] Test API endpoints

## 🔍 Common Issues

### "Service not found" on first deployment

The backend workflows only UPDATE services, they don't CREATE them. You may need to manually create the services once or add create-service logic to the workflows.

### "Invalid subnet ID" or "Invalid security group"

You forgot to update the hardcoded values in the workflow files. Go back to Step 4.

### "OpenAI API error" in ai-conversation-service

You forgot to set the `OPENAI_API_KEY` secret. Go back to Step 3.

### "Credentials expired"

Your AWS Academy session expired. Get fresh credentials from Step 1.

## 📞 Need Help?

1. Check the full guide: `AWS_SETUP_GUIDE.md`
2. Review script output carefully - it tells you exactly what to update
3. Check AWS Console to see what resources were created
4. Ask your teacher for help with AWS Academy permissions

## 💡 Pro Tips

- Save the script output to a file for reference: `python setup_aws_infrastructure.py > setup-output.txt`
- Run the script in your IDE terminal so you can copy values easily
- Double-check GitHub Secrets were actually updated (they don't show old values)
- Test with a small change first before full deployment
