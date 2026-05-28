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
import os
from pathlib import Path
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

# AWS Clients (initialized at runtime after loading .env)
ecs = None
ec2 = None
ecr = None
elbv2 = None
logs = None
s3 = None
amplify = None
apigateway = None


def load_env_file(env_path: str = None):
    """Load environment variables from a .env file into os.environ.
    Minimal loader to allow running the script without manual aws configure.
    """
    path = Path(env_path) if env_path else (Path(__file__).resolve().parent / ".env")
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                os.environ[key] = val
    except Exception:
        pass


def init_aws_clients(region: str = None):
    """Initialize global boto3 clients using environment variables if present."""
    global ecs, ec2, ecr, elbv2, logs, s3, amplify, apigateway
    region = region or os.getenv("AWS_REGION", REGION)
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_token = os.getenv("AWS_SESSION_TOKEN")

    if aws_access_key and aws_secret:
        session_kwargs = {
            "aws_access_key_id": aws_access_key,
            "aws_secret_access_key": aws_secret,
            "aws_session_token": aws_token,
            "region_name": region,
        }
        ecs = boto3.client("ecs", **session_kwargs)
        ec2 = boto3.client("ec2", **session_kwargs)
        ecr = boto3.client("ecr", **session_kwargs)
        elbv2 = boto3.client("elbv2", **session_kwargs)
        logs = boto3.client("logs", **session_kwargs)
        s3 = boto3.client("s3", **session_kwargs)
        amplify = boto3.client("amplify", **session_kwargs)
        apigateway = boto3.client("apigatewayv2", **session_kwargs)
    else:
        ecs = boto3.client("ecs", region_name=region)
        ec2 = boto3.client("ec2", region_name=region)
        ecr = boto3.client("ecr", region_name=region)
        elbv2 = boto3.client("elbv2", region_name=region)
        logs = boto3.client("logs", region_name=region)
        s3 = boto3.client("s3", region_name=region)
        amplify = boto3.client("amplify", region_name=region)
        apigateway = boto3.client("apigatewayv2", region_name=region)


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


def create_api_gateway(lb_dns: str) -> Optional[str]:
    """Create API Gateway HTTP API for HTTPS support."""
    print_header("Setting up API Gateway for HTTPS")

    api_name = "pami-api"

    try:
        # Check if API already exists
        response = apigateway.get_apis()
        for api in response.get("Items", []):
            if api.get("Name") == api_name:
                api_id = api["ApiId"]
                api_endpoint = api["ApiEndpoint"]
                print_success(f"API Gateway already exists: {api_name}")
                print_info(f"HTTPS URL: {api_endpoint}")
                return api_endpoint

        # Create new HTTP API
        response = apigateway.create_api(
            Name=api_name,
            ProtocolType="HTTP",
            Description="PAMI API Gateway with HTTPS for Amplify frontend",
        )
        api_id = response["ApiId"]
        api_endpoint = response["ApiEndpoint"]

        print_success(f"Created API Gateway: {api_name}")
        print_info(f"API ID: {api_id}")

        # Create integration with ALB
        integration_response = apigateway.create_integration(
            ApiId=api_id,
            IntegrationType="HTTP_PROXY",
            IntegrationUri=f"http://{lb_dns}",
            IntegrationMethod="ANY",
            PayloadFormatVersion="1.0",
        )
        integration_id = integration_response["IntegrationId"]
        print_success(f"Created integration with ALB")

        # Create default route that forwards all requests
        apigateway.create_route(
            ApiId=api_id,
            RouteKey="$default",
            Target=f"integrations/{integration_id}",
        )
        print_success(f"Created default route (forwards all paths)")

        # Create $default stage (auto-deploy)
        apigateway.create_stage(
            ApiId=api_id,
            StageName="$default",
            AutoDeploy=True,
        )
        print_success(f"Created auto-deploy stage")

        print_info(f"HTTPS URL: {api_endpoint}")
        print_info("✓ API Gateway is ready immediately (no waiting required)")

        return api_endpoint

    except Exception as e:
        print_error(f"Failed to create API Gateway: {e}")
        print_info("Continuing without HTTPS. You can set up API Gateway manually.")
        return None


def create_amplify_app(
    api_base_url: str, github_token: Optional[str] = None
) -> Optional[str]:
    """Create or update AWS Amplify app for frontend."""
    print_header("Setting up AWS Amplify for Frontend")

    app_name = "pami-frontend"

    try:
        # Check if app exists
        response = amplify.list_apps()
        existing_app = None
        for app in response.get("apps", []):
            if app["name"] == app_name:
                existing_app = app
                break

        if existing_app:
            app_id = existing_app["appId"]
            default_domain = existing_app["defaultDomain"]
            print_success(f"Amplify app already exists: {app_name}")
            print_info(f"App ID: {app_id}")

            # Update environment variables
            try:
                amplify.update_app(
                    appId=app_id,
                    environmentVariables={
                        "REACT_APP_PROJECTS_API_BASE_URL": api_base_url,
                        "REACT_APP_SLACK_API_BASE_URL": f"{api_base_url}/slack",
                        "_LIVE_UPDATES": '[{"pkg":"@aws-amplify/cli","type":"npm","version":"latest"}]',
                    },
                )
                print_success(f"Updated environment variables with new API URL")
                print_info(f"  REACT_APP_PROJECTS_API_BASE_URL = {api_base_url}")
                print_info(f"  REACT_APP_SLACK_API_BASE_URL = {api_base_url}/slack")

                # Trigger a new build
                try:
                    amplify.start_job(
                        appId=app_id, branchName="main", jobType="RELEASE"
                    )
                    print_success(
                        f"Triggered new deployment with updated configuration"
                    )
                except Exception as deploy_error:
                    print_info(f"Note: Could not trigger auto-deploy: {deploy_error}")
                    print_info(
                        "You can manually redeploy from AWS Console → Amplify → Deployments"
                    )

            except Exception as update_error:
                print_error(f"Failed to update environment variables: {update_error}")

            print_info(f"URL: https://main.{default_domain}")
            return f"https://main.{default_domain}"

        # Create new app
        if not github_token:
            print_error("Cannot create Amplify app: GitHub token required")
            print_info(
                "You can create it manually in AWS Console or provide GitHub token"
            )
            return None

        app_config = {
            "name": app_name,
            "repository": "https://github.com/OrKeren8/pami",
            "platform": "WEB",
            "oauthToken": github_token,
            "environmentVariables": {
                "REACT_APP_PROJECTS_API_BASE_URL": api_base_url,
                "REACT_APP_SLACK_API_BASE_URL": f"{api_base_url}/slack",
                "_LIVE_UPDATES": '[{"pkg":"@aws-amplify/cli","type":"npm","version":"latest"}]',
            },
            "buildSpec": """version: 1
frontend:
  phases:
    preBuild:
      commands:
        - cd frontend
        - npm install
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: frontend/build
    files:
      - '**/*'
  cache:
    paths:
      - frontend/node_modules/**/*
""",
        }

        response = amplify.create_app(**app_config)
        app = response["app"]
        app_id = app["appId"]
        default_domain = app["defaultDomain"]

        # Create branch
        amplify.create_branch(appId=app_id, branchName="main", enableAutoBuild=True)

        print_success(f"Created Amplify app: {app_name}")
        print_info(f"App ID: {app_id}")
        print_info(f"URL: https://main.{default_domain}")
        print_info("Amplify will auto-deploy on every push to main branch")

        return f"https://main.{default_domain}"

    except Exception as e:
        print_error(f"Failed to create Amplify app: {e}")
        print_info("You can set it up manually in AWS Console → Amplify")
        return None


def print_summary(
    vpc_id: str,
    subnet_ids: List[str],
    security_group_id: str,
    lb_arn: Optional[str],
    target_groups: Dict[str, str],
    s3_bucket: Optional[str],
    amplify_url: Optional[str] = None,
    api_gateway_url: Optional[str] = None,
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

    if api_gateway_url:
        print(f"  • API Gateway (HTTPS): {api_gateway_url}")

    if amplify_url:
        print(f"  • Frontend URL (Amplify): {amplify_url}")

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
    print("✓ Backend services now have auto-create logic")
    print()

    if not amplify_url:
        print_header("⚠️  Frontend (Amplify) - Manual Setup Required")
        print()
        print("Amplify app was not created automatically.")
        print("To deploy your frontend, either:")
        print()
        print("Option 1: Manual setup in AWS Console")
        print("  1. Go to AWS Console → Amplify")
        print("  2. Click 'New app' → 'Host web app'")
        print("  3. Connect to GitHub repository: OrKeren8/pami")
        print("  4. Branch: main")
        print("  5. Build settings → Base directory: frontend")
        print("  6. Add environment variables:")
        if lb_arn:
            try:
                response = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])
                lb_dns = response["LoadBalancers"][0]["DNSName"]
                print(f"     REACT_APP_PROJECTS_API_BASE_URL = http://{lb_dns}")
                print(f"     REACT_APP_SLACK_API_BASE_URL = http://{lb_dns}/slack")
            except Exception:
                pass
        print()
        print("Option 2: Re-run this script with GitHub token")
        print("  Set environment variable: GITHUB_TOKEN=<your-token>")
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
    # Load .env (if present) and initialize AWS clients so temporary credentials are used
    load_env_file()
    init_aws_clients()

    print_header("PAMI AWS Infrastructure Setup")
    resolved_region = os.getenv("AWS_REGION", REGION)
    print(f"Region: {resolved_region}")
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

        # Get load balancer DNS
        lb_dns = None
        if lb_arn:
            try:
                response = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])
                lb_dns = response["LoadBalancers"][0]["DNSName"]
            except Exception:
                pass

        # Create API Gateway for HTTPS
        api_gateway_url = None
        if lb_dns:
            api_gateway_url = create_api_gateway(lb_dns)

        # Use API Gateway URL for Amplify if available, otherwise use ALB
        api_base_url = api_gateway_url if api_gateway_url else f"http://{lb_dns}"

        # Setup Amplify for frontend (optional - will skip if no GitHub token)
        amplify_url = None
        if api_base_url:
            amplify_url = create_amplify_app(api_base_url)

        # Print summary
        print_summary(
            vpc_id,
            subnet_ids,
            security_group_id,
            lb_arn,
            target_groups,
            s3_bucket,
            amplify_url,
            api_gateway_url,
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
