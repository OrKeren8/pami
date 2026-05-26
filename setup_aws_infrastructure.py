#!/usr/bin/env python3
"""
AWS Infrastructure Setup Script for PAMI Project
================================================
This script sets up all required AWS resources for the PAMI project.
It is idempotent - safe to run multiple times.

Requirements:
- boto3: pip install boto3
- AWS credentials configured (use aws configure or environment variables)

Usage:
    python setup_aws_infrastructure.py
"""

import boto3
import json
import sys
from typing import Dict, Optional, List

# Configuration
REGION = "us-east-1"
ACCOUNT_ID = "909189231170"
CLUSTER_NAME = "pami-cluster"

SERVICES = [
    {"name": "projects-service", "port": 8000, "health_check_path": "/health"},
    {"name": "slack-service", "port": 8002, "health_check_path": "/health"},
    {"name": "ai-conversation-service", "port": 8001, "health_check_path": "/health"},
]

# AWS Clients
ecs = boto3.client("ecs", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)
ecr = boto3.client("ecr", region_name=REGION)
elbv2 = boto3.client("elbv2", region_name=REGION)
logs = boto3.client("logs", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def print_header(text: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_success(text: str):
    """Print success message."""
    print(f"✓ {text}")


def print_info(text: str):
    """Print info message."""
    print(f"  {text}")


def print_error(text: str):
    """Print error message."""
    print(f"✗ ERROR: {text}", file=sys.stderr)


def get_default_vpc() -> Optional[str]:
    """Get the default VPC ID."""
    try:
        response = ec2.describe_vpcs(
            Filters=[{"Name": "isDefault", "Values": ["true"]}]
        )
        if response["Vpcs"]:
            vpc_id = response["Vpcs"][0]["VpcId"]
            print_success(f"Found default VPC: {vpc_id}")
            return vpc_id
        else:
            print_error("No default VPC found")
            return None
    except Exception as e:
        print_error(f"Failed to get default VPC: {e}")
        return None


def get_vpc_subnets(vpc_id: str) -> List[str]:
    """Get all subnets for a VPC."""
    try:
        response = ec2.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )
        subnet_ids = [subnet["SubnetId"] for subnet in response["Subnets"]]
        print_success(f"Found {len(subnet_ids)} subnets: {', '.join(subnet_ids)}")
        return subnet_ids
    except Exception as e:
        print_error(f"Failed to get subnets: {e}")
        return []


def create_or_get_security_group(vpc_id: str) -> Optional[str]:
    """Create or get the security group for ECS services."""
    sg_name = "pami-ecs-services-sg"

    try:
        # Check if security group exists
        response = ec2.describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [sg_name]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )

        if response["SecurityGroups"]:
            sg_id = response["SecurityGroups"][0]["GroupId"]
            print_success(f"Security group already exists: {sg_id}")
            return sg_id

        # Create security group
        response = ec2.create_security_group(
            GroupName=sg_name,
            Description="Security group for PAMI ECS services",
            VpcId=vpc_id,
        )
        sg_id = response["GroupId"]

        # Add ingress rules for all service ports
        ports = [8000, 8001, 8002, 80, 443]
        for port in ports:
            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": port,
                        "ToPort": port,
                        "IpRanges": [
                            {"CidrIp": "0.0.0.0/0", "Description": f"Allow port {port}"}
                        ],
                    }
                ],
            )

        print_success(f"Created security group: {sg_id}")
        return sg_id

    except Exception as e:
        print_error(f"Failed to create/get security group: {e}")
        return None


def create_ecs_cluster():
    """Create ECS cluster if it doesn't exist."""
    print_header("Setting up ECS Cluster")

    try:
        # Check if cluster exists
        response = ecs.describe_clusters(clusters=[CLUSTER_NAME])

        if response["clusters"] and response["clusters"][0]["status"] == "ACTIVE":
            print_success(f"ECS cluster '{CLUSTER_NAME}' already exists")
            return True

        # Create cluster
        ecs.create_cluster(clusterName=CLUSTER_NAME)
        print_success(f"Created ECS cluster: {CLUSTER_NAME}")
        return True

    except Exception as e:
        print_error(f"Failed to create ECS cluster: {e}")
        return False


def create_ecr_repositories():
    """Create ECR repositories for all services."""
    print_header("Setting up ECR Repositories")

    repos_created = []

    for service in SERVICES:
        repo_name = f"pami/{service['name']}"

        try:
            # Check if repository exists
            ecr.describe_repositories(repositoryNames=[repo_name])
            print_success(f"ECR repository '{repo_name}' already exists")
            repos_created.append(repo_name)

        except ecr.exceptions.RepositoryNotFoundException:
            # Create repository
            try:
                response = ecr.create_repository(
                    repositoryName=repo_name,
                    imageScanningConfiguration={"scanOnPush": True},
                )
                uri = response["repository"]["repositoryUri"]
                print_success(f"Created ECR repository: {repo_name}")
                print_info(f"URI: {uri}")
                repos_created.append(repo_name)

            except Exception as e:
                print_error(f"Failed to create ECR repository '{repo_name}': {e}")

        except Exception as e:
            print_error(f"Failed to check ECR repository '{repo_name}': {e}")

    return len(repos_created) == len(SERVICES)


def create_cloudwatch_log_groups():
    """Create CloudWatch log groups for all services."""
    print_header("Setting up CloudWatch Log Groups")

    for service in SERVICES:
        log_group_name = f"/ecs/pami-{service['name']}"

        try:
            # Check if log group exists
            logs.describe_log_groups(logGroupNamePrefix=log_group_name)
            print_success(f"Log group '{log_group_name}' already exists")

        except Exception:
            # Create log group
            try:
                logs.create_log_group(logGroupName=log_group_name)
                logs.put_retention_policy(
                    logGroupName=log_group_name, retentionInDays=7
                )
                print_success(f"Created log group: {log_group_name}")

            except logs.exceptions.ResourceAlreadyExistsException:
                print_success(f"Log group '{log_group_name}' already exists")
            except Exception as e:
                print_error(f"Failed to create log group '{log_group_name}': {e}")


def create_s3_bucket():
    """Create S3 bucket for AI conversation service."""
    print_header("Setting up S3 Bucket")

    bucket_name = f"pami-ai-conversations-{REGION}"

    try:
        # Check if bucket exists
        s3.head_bucket(Bucket=bucket_name)
        print_success(f"S3 bucket '{bucket_name}' already exists")
        return bucket_name

    except Exception:
        # Create bucket
        try:
            if REGION == "us-east-1":
                # us-east-1 doesn't need LocationConstraint
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": REGION},
                )

            # Enable versioning for better data protection
            s3.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

            # Set lifecycle policy to clean up old versions
            s3.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": "DeleteOldVersions",
                            "Status": "Enabled",
                            "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
                            "AbortIncompleteMultipartUpload": {
                                "DaysAfterInitiation": 7
                            },
                        }
                    ]
                },
            )

            print_success(f"Created S3 bucket: {bucket_name}")
            return bucket_name

        except Exception as e:
            print_error(f"Failed to create S3 bucket '{bucket_name}': {e}")
            return None


def create_load_balancer(
    vpc_id: str, subnet_ids: List[str], security_group_id: str
) -> Optional[str]:
    """Create Application Load Balancer."""
    print_header("Setting up Application Load Balancer")

    lb_name = "pami-alb"

    try:
        # Check if load balancer exists
        response = elbv2.describe_load_balancers(Names=[lb_name])
        if response["LoadBalancers"]:
            lb_arn = response["LoadBalancers"][0]["LoadBalancerArn"]
            dns_name = response["LoadBalancers"][0]["DNSName"]
            print_success(f"Load balancer already exists: {lb_name}")
            print_info(f"DNS: {dns_name}")
            print_info(f"ARN: {lb_arn}")
            return lb_arn

    except elbv2.exceptions.LoadBalancerNotFoundException:
        pass
    except Exception as e:
        print_error(f"Error checking load balancer: {e}")
        return None

    try:
        # Create load balancer (need at least 2 subnets in different AZs)
        if len(subnet_ids) < 2:
            print_error(
                "Need at least 2 subnets in different availability zones for ALB"
            )
            return None

        response = elbv2.create_load_balancer(
            Name=lb_name,
            Subnets=subnet_ids[:2],  # Use first 2 subnets
            SecurityGroups=[security_group_id],
            Scheme="internet-facing",
            Type="application",
            IpAddressType="ipv4",
        )

        lb_arn = response["LoadBalancers"][0]["LoadBalancerArn"]
        dns_name = response["LoadBalancers"][0]["DNSName"]

        print_success(f"Created load balancer: {lb_name}")
        print_info(f"DNS: {dns_name}")
        print_info(f"ARN: {lb_arn}")

        return lb_arn

    except Exception as e:
        print_error(f"Failed to create load balancer: {e}")
        return None


def create_target_groups(vpc_id: str) -> Dict[str, str]:
    """Create target groups for all services."""
    print_header("Setting up Target Groups")

    target_groups = {}

    for service in SERVICES:
        tg_name = f"{service['name']}-tg"

        try:
            # Check if target group exists
            response = elbv2.describe_target_groups(Names=[tg_name])
            if response["TargetGroups"]:
                tg_arn = response["TargetGroups"][0]["TargetGroupArn"]
                print_success(f"Target group '{tg_name}' already exists")
                target_groups[service["name"]] = tg_arn
                continue

        except elbv2.exceptions.TargetGroupNotFoundException:
            pass
        except Exception as e:
            print_error(f"Error checking target group '{tg_name}': {e}")
            continue

        try:
            # Create target group
            response = elbv2.create_target_group(
                Name=tg_name,
                Protocol="HTTP",
                Port=service["port"],
                VpcId=vpc_id,
                TargetType="ip",
                HealthCheckEnabled=True,
                HealthCheckProtocol="HTTP",
                HealthCheckPath=service["health_check_path"],
                HealthCheckIntervalSeconds=30,
                HealthCheckTimeoutSeconds=5,
                HealthyThresholdCount=2,
                UnhealthyThresholdCount=3,
            )

            tg_arn = response["TargetGroups"][0]["TargetGroupArn"]
            target_groups[service["name"]] = tg_arn

            print_success(f"Created target group: {tg_name}")
            print_info(f"ARN: {tg_arn}")

        except Exception as e:
            print_error(f"Failed to create target group '{tg_name}': {e}")

    return target_groups


def create_alb_listeners(lb_arn: str, target_groups: Dict[str, str]):
    """Create ALB listeners and rules."""
    print_header("Setting up ALB Listeners")

    try:
        # Check if listener exists
        response = elbv2.describe_listeners(LoadBalancerArn=lb_arn)
        if response["Listeners"]:
            print_success("HTTP listener already exists")
            listener_arn = response["Listeners"][0]["ListenerArn"]
        else:
            # Create HTTP listener with default action to projects service
            default_tg = target_groups.get("projects-service")
            if not default_tg:
                print_error(
                    "Cannot create listener: projects-service target group not found"
                )
                return

            response = elbv2.create_listener(
                LoadBalancerArn=lb_arn,
                Protocol="HTTP",
                Port=80,
                DefaultActions=[{"Type": "forward", "TargetGroupArn": default_tg}],
            )
            listener_arn = response["Listeners"][0]["ListenerArn"]
            print_success("Created HTTP listener on port 80")

        # Create rules for path-based routing
        rules = [
            {
                "path": "/slack/*",
                "priority": 10,
                "target_group": target_groups.get("slack-service"),
            },
            {
                "path": "/ai/*",
                "priority": 20,
                "target_group": target_groups.get("ai-conversation-service"),
            },
        ]

        for rule in rules:
            if rule["target_group"]:
                try:
                    elbv2.create_rule(
                        ListenerArn=listener_arn,
                        Conditions=[
                            {"Field": "path-pattern", "Values": [rule["path"]]}
                        ],
                        Priority=rule["priority"],
                        Actions=[
                            {"Type": "forward", "TargetGroupArn": rule["target_group"]}
                        ],
                    )
                    print_success(f"Created routing rule for {rule['path']}")
                except elbv2.exceptions.PriorityInUseException:
                    print_success(f"Routing rule for {rule['path']} already exists")
                except Exception as e:
                    print_error(f"Failed to create rule for {rule['path']}: {e}")

    except Exception as e:
        print_error(f"Failed to setup listeners: {e}")


def print_summary(
    vpc_id: str,
    subnet_ids: List[str],
    security_group_id: str,
    lb_arn: Optional[str],
    target_groups: Dict[str, str],
    s3_bucket: Optional[str],
):
    """Print setup summary and next steps."""
    print_header("Setup Summary")

    print_success("Infrastructure setup completed!")
    print()

    print("Resources Created:")
    print(f"  • ECS Cluster: {CLUSTER_NAME}")
    print(f"  • VPC: {vpc_id}")
    print(f"  • Subnets: {', '.join(subnet_ids)}")
    print(f"  • Security Group: {security_group_id}")

    if s3_bucket:
        print(f"  • S3 Bucket: {s3_bucket}")

    if lb_arn:
        try:
            response = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])
            dns_name = response["LoadBalancers"][0]["DNSName"]
            print(f"  • Load Balancer DNS: {dns_name}")
        except Exception:
            pass

    print()
    print("ECR Repositories:")
    for service in SERVICES:
        repo_uri = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/pami/{service['name']}"
        print(f"  • {service['name']}: {repo_uri}")

    print()
    print("Target Groups:")
    for name, arn in target_groups.items():
        print(f"  • {name}: {arn}")

    print()
    print_header("⚠️  CRITICAL: Update GitHub Secrets")
    print()
    print("These secrets MUST be updated with your NEW lab credentials:")
    print("   • AWS_ACCESS_KEY_ID")
    print("   • AWS_SECRET_ACCESS_KEY")
    print("   • AWS_SESSION_TOKEN")
    print()
    print("These secrets should also be verified/set:")
    print("   • MONGODB_URL (your MongoDB Atlas connection string)")
    print("   • OPENAI_API_KEY (for AI conversation service)")
    print("   • SLACK_BOT_TOKEN (your Slack app bot token)")
    print("   • SLACK_SIGNING_SECRET (your Slack app signing secret)")
    print()
    print_header("⚠️  CRITICAL: Update Workflow Files")
    print()
    print("Your workflows have HARDCODED values that MUST be updated!")
    print()
    print("File: .github/workflows/deploy-slack-service.yml")
    print("Find line with --network-configuration and update:")
    print(f"   subnets=[{','.join(subnet_ids[:2])}]")
    print(f"   securityGroups=[{security_group_id}]")
    print()

    if target_groups.get("slack-service"):
        print("Also update the load balancer target group ARN:")
        print(f"   targetGroupArn={target_groups['slack-service']}")
        print()

    print("File: .github/workflows/deploy-backend.yml")
    print("⚠️  WARNING: Your backend services workflows don't include network")
    print("configuration or service creation. After first deployment, you may need")
    print("to manually create the ECS services or add network-configuration to the")
    print("create-service commands similar to the slack-service workflow.")
    print()
    print("Network configuration to add (if needed):")
    print(
        f"   --network-configuration \"awsvpcConfiguration={{subnets=[{','.join(subnet_ids[:2])}],securityGroups=[{security_group_id}],assignPublicIp=ENABLED}}\""
    )
    print()
    print_header("Next Steps")
    print("1. Update GitHub Secrets (see above)")
    print("2. Update workflow files with new subnets and security groups")
    print("3. Commit and push the workflow changes")
    print("4. Push to main branch to trigger deployment")
    print()
    print("To verify infrastructure:")
    print(f"   aws ecs describe-clusters --cluster {CLUSTER_NAME}")
    print(f"   aws ecr describe-repositories")
    print()


def main():
    """Main setup function."""
    print_header("PAMI AWS Infrastructure Setup")
    print(f"Region: {REGION}")
    print(f"Account: {ACCOUNT_ID}")
    print()

    try:
        # Get VPC and network resources
        vpc_id = get_default_vpc()
        if not vpc_id:
            print_error("Cannot proceed without VPC")
            sys.exit(1)

        subnet_ids = get_vpc_subnets(vpc_id)
        if not subnet_ids:
            print_error("Cannot proceed without subnets")
            sys.exit(1)

        security_group_id = create_or_get_security_group(vpc_id)
        if not security_group_id:
            print_error("Cannot proceed without security group")
            sys.exit(1)

        # Create ECS resources
        if not create_ecs_cluster():
            print_error("Failed to create ECS cluster")
            sys.exit(1)

        if not create_ecr_repositories():
            print_error("Failed to create all ECR repositories")
            sys.exit(1)

        create_cloudwatch_log_groups()

        # Create S3 bucket for AI conversation service
        s3_bucket = create_s3_bucket()

        # Create load balancer and target groups
        target_groups = create_target_groups(vpc_id)

        lb_arn = create_load_balancer(vpc_id, subnet_ids, security_group_id)
        if lb_arn and target_groups:
            create_alb_listeners(lb_arn, target_groups)

        # Print summary
        print_summary(
            vpc_id, subnet_ids, security_group_id, lb_arn, target_groups, s3_bucket
        )

        print_success("Setup completed successfully!")

    except KeyboardInterrupt:
        print()
        print_error("Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
