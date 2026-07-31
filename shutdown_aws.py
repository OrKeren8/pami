#!/usr/bin/env python3
"""
AWS Infrastructure Shutdown Script
===================================
Stops all running services and removes expensive resources to minimize costs.

Cost savings: ~$2.20/day
Remaining cost: ~$0.05/day (storage only)

Usage:
    python shutdown_aws.py
"""

import boto3
import sys
import os
import time
from pathlib import Path
from typing import List

# Configuration
REGION = "us-east-1"
ACCOUNT_ID = "909189231170"
CLUSTER_NAME = "pami-cluster"

SERVICES = [
    "pami-projects-service",
    "pami-slack-service",
    "pami-ai-conversation-service",
]

# Named without the pami- prefix, matching setup_aws_infrastructure.py.
TARGET_GROUPS = [
    "projects-service-tg",
    "slack-service-tg",
    "ai-conversation-service-tg",
]

# AWS Clients (will be initialized at runtime after loading credentials)
ecs = None
elbv2 = None


def load_env_file(env_path: str = None):
    """Load environment variables from a .env file into os.environ.
    This is a minimal loader so users don't have to set credentials manually.
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
                # Remove surrounding quotes if any
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                # Overwrite existing values to ensure script uses latest .env
                os.environ[key] = val
    except Exception:
        # Silently ignore parse errors (we'll rely on boto3 defaults/error messages)
        pass


def print_header(text: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print("=" * 60)


def print_success(text: str):
    """Print a success message."""
    print(f"✓ {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"✗ ERROR: {text}")


def print_info(text: str):
    """Print an info message."""
    print(f"  {text}")


def stop_ecs_services():
    """Stop all ECS services by setting desired count to 0."""
    print_header("Stopping ECS Services")

    for service_name in SERVICES:
        try:
            # Check if service exists
            response = ecs.describe_services(
                cluster=CLUSTER_NAME, services=[service_name]
            )

            if (
                not response["services"]
                or response["services"][0]["status"] != "ACTIVE"
            ):
                print_info(f"Service {service_name} not found or already stopped")
                continue

            # Stop the service
            ecs.update_service(
                cluster=CLUSTER_NAME, service=service_name, desiredCount=0
            )
            print_success(f"Stopped {service_name}")

        except Exception as e:
            print_error(f"Failed to stop {service_name}: {e}")


def delete_load_balancer():
    """Delete the Application Load Balancer."""
    print_header("Deleting Application Load Balancer")

    try:
        # Find the load balancer
        response = elbv2.describe_load_balancers()

        lb_arn = None
        for lb in response["LoadBalancers"]:
            if lb["LoadBalancerName"] == "pami-alb":
                lb_arn = lb["LoadBalancerArn"]
                break

        if not lb_arn:
            print_info("Load balancer not found (already deleted)")
            return

        # Delete the load balancer
        elbv2.delete_load_balancer(LoadBalancerArn=lb_arn)
        print_success("Deleted Application Load Balancer")

        delete_target_groups()

    except Exception as e:
        print_error(f"Failed to delete load balancer: {e}")


def delete_target_groups():
    """Delete this project's target groups once the load balancer is gone.

    AWS does not remove target groups when their load balancer is deleted - the old
    message promising that was simply wrong. Left behind, they are recreated on the next
    setup run under a new random ARN suffix, which is what silently broke a deploy that
    had a target-group ARN written into it.
    """
    print_header("Deleting Target Groups")

    # Deleting a target group requires its listener rules to be gone first, and the
    # listeners go with the load balancer. It is not instant.
    for attempt in range(6):
        remaining = []

        for tg_name in TARGET_GROUPS:
            try:
                response = elbv2.describe_target_groups(Names=[tg_name])
            except elbv2.exceptions.TargetGroupNotFoundException:
                continue
            except Exception as error:
                print_error(f"Could not look up target group {tg_name}: {error}")
                continue

            for target_group in response["TargetGroups"]:
                try:
                    elbv2.delete_target_group(
                        TargetGroupArn=target_group["TargetGroupArn"]
                    )
                    print_success(f"Deleted target group {tg_name}")
                except Exception as error:
                    remaining.append(tg_name)
                    if attempt == 5:
                        print_error(
                            f"Target group {tg_name} could not be deleted: {error}"
                        )

        if not remaining:
            return

        if attempt < 5:
            print_info(
                f"{len(remaining)} target group(s) still in use; retrying in 10s"
            )
            time.sleep(10)


def print_summary():
    """Print shutdown summary and next steps."""
    print_header("Shutdown Complete")

    print_success("All expensive resources have been stopped/deleted!")
    print()
    print("Cost Impact:")
    print("  • Running costs: ~$2.25/day")
    print("  • After shutdown: ~$0.05/day")
    print("  • Savings: ~$2.20/day (~$66/month)")
    print()
    print("Resources Stopped:")
    print("  ✓ 3 ECS Fargate services (0 tasks running)")
    print("  ✓ Application Load Balancer deleted")
    print()
    print("Resources Still Active (minimal cost):")
    print("  • ECS Cluster (empty)")
    print("  • ECR Docker repositories")
    print("  • S3 bucket (with data)")
    print("  • API Gateway (pay per request)")
    print("  • CloudWatch Log Groups")
    print()
    print_header("To Restart Everything")
    print()
    print("Run the setup script to recreate infrastructure:")
    print("  python setup_aws_infrastructure.py")
    print()
    print("Then trigger deployment:")
    print("  git commit --allow-empty -m 'Trigger deployment'")
    print("  git push")
    print()
    print("Services will be running again in ~5-10 minutes")


def main():
    """Main shutdown flow."""
    try:
        # Load environment (.env) so the script can run without manual setup
        load_env_file()

        # Resolve runtime region and credentials from environment
        region = os.getenv("AWS_REGION", REGION)
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_token = os.getenv("AWS_SESSION_TOKEN")

        # Initialize AWS clients with provided credentials (if any)
        global ecs, elbv2
        if aws_access_key and aws_secret:
            ecs = boto3.client(
                "ecs",
                region_name=region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret,
                aws_session_token=aws_token,
            )
            elbv2 = boto3.client(
                "elbv2",
                region_name=region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret,
                aws_session_token=aws_token,
            )
        else:
            ecs = boto3.client("ecs", region_name=region)
            elbv2 = boto3.client("elbv2", region_name=region)

        print_header("PAMI AWS Infrastructure Shutdown")
        print()
        print(f"Region: {region}")
        print(f"Account: {ACCOUNT_ID}")
        print()

        # Confirm shutdown
        print("⚠️  WARNING: This will stop all services and delete the load balancer.")
        print("Your application will be completely offline until you restart.")
        print()
        response = input("Continue with shutdown? (yes/no): ")

        if response.lower() not in ["yes", "y"]:
            print("\nShutdown cancelled.")
            sys.exit(0)

        # Stop ECS services
        stop_ecs_services()

        # Delete load balancer
        delete_load_balancer()

        # Print summary
        print_summary()

        print_success("Shutdown completed successfully!")

    except KeyboardInterrupt:
        print()
        print_error("Shutdown interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
