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

# AWS Clients
ecs = boto3.client("ecs", region_name=REGION)
elbv2 = boto3.client("elbv2", region_name=REGION)


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
        print_info("Target groups will be auto-deleted after a short delay")

    except Exception as e:
        print_error(f"Failed to delete load balancer: {e}")


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
        print_header("PAMI AWS Infrastructure Shutdown")
        print()
        print(f"Region: {REGION}")
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
