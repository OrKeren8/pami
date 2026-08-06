#!/usr/bin/env python3
"""
AWS Infrastructure Shutdown
===========================
Takes the running system offline and removes the resources that cost money by the hour,
leaving only cheap storage behind. Everything it removes is recreated by
setup_aws_infrastructure.py.

What it stops or deletes, in the order that works:
    1. every ECS service is scaled to zero tasks   - Fargate is the largest hourly cost
    2. the Application Load Balancer               - about $0.55/day whether used or not
    3. the target groups                           - free, but a stale one silently breaks
                                                     the next deploy, so they go with it
    4. Elastic IPs the load balancer was using     - free while attached, ~$0.11/day each
                                                     the moment they are not

Optional:
    --prune-untagged   delete untagged ECR images (layers from superseded builds)

Usage:
    python shutdown_aws.py                     # asks first
    python shutdown_aws.py --yes               # no prompt, for automation
    python shutdown_aws.py --yes --prune-untagged
    python shutdown_aws.py --dry-run           # report what would happen
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import boto3
except ImportError:  # pragma: no cover
    sys.exit("boto3 is missing. Install it with: py -m pip install boto3")

REGION = "us-east-1"
CLUSTER_NAME = "pami-cluster"
LOAD_BALANCER_NAME = "pami-alb"

# Every service in the cluster. jira-service was missing from this list, so a shutdown left
# one Fargate task running and still billing - the whole point of the script, undone by an
# omission. Read from the cluster as well, so the next new service cannot repeat it.
SERVICES = [
    "pami-projects-service",
    "pami-slack-service",
    "pami-ai-conversation-service",
    "pami-jira-service",
]

# Named without the pami- prefix, matching setup_aws_infrastructure.py.
TARGET_GROUPS = [
    "projects-service-tg",
    "slack-service-tg",
    "ai-conversation-service-tg",
    "jira-service-tg",
]

ECR_REPOSITORIES = [
    "pami/projects-service",
    "pami/slack-service",
    "pami/ai-conversation-service",
    "pami/jira-service",
]

ecs = elbv2 = ec2 = ecr = None
DRY_RUN = False


def load_env_file(env_path: str | None = None) -> None:
    """Load a .env file into os.environ so credentials need not be set by hand."""
    path = Path(env_path) if env_path else (Path(__file__).resolve().parent / ".env")
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
                value = value[1:-1]
            os.environ[key.strip()] = value
    except Exception:
        # A malformed .env is not worth failing over: boto3 will report what is missing.
        pass


def header(text: str) -> None:
    print(f"\n{'=' * 62}\n  {text}\n{'=' * 62}")


def ok(text: str) -> None:
    print(f"  [done] {text}")


def info(text: str) -> None:
    print(f"         {text}")


def fail(text: str) -> None:
    print(f"  [FAIL] {text}")


def would(text: str) -> None:
    print(f"  [dry ] {text}")


def account_id() -> Optional[str]:
    try:
        return boto3.client("sts").get_caller_identity()["Account"]
    except Exception as error:
        fail(f"could not resolve the AWS account: {error}")
        return None


def all_services() -> list[str]:
    """The services to stop: the known list, plus anything else in the cluster.

    Discovered rather than trusted, because the cost of missing one is a task that keeps
    billing after a shutdown reports success.
    """
    found = set(SERVICES)
    try:
        paginator = ecs.get_paginator("list_services")
        for page in paginator.paginate(cluster=CLUSTER_NAME):
            for arn in page.get("serviceArns", []):
                found.add(arn.rsplit("/", 1)[-1])
    except Exception as error:
        info(f"could not list the cluster's services ({error}); using the known list")
    return sorted(found)


def stop_ecs_services() -> None:
    header("Scaling every ECS service to zero")
    names = all_services()
    if not names:
        info("no services found")
        return

    for name in names:
        try:
            described = ecs.describe_services(cluster=CLUSTER_NAME, services=[name])
            services = described.get("services") or []
            if not services or services[0]["status"] != "ACTIVE":
                info(f"{name}: not active, skipping")
                continue
            if services[0]["desiredCount"] == 0:
                info(f"{name}: already at zero")
                continue
            if DRY_RUN:
                would(f"scale {name} from {services[0]['desiredCount']} to 0")
                continue
            ecs.update_service(cluster=CLUSTER_NAME, service=name, desiredCount=0)
            ok(f"{name}: desired count set to 0")
        except Exception as error:
            fail(f"{name}: {error}")


def wait_for_tasks_to_stop(timeout: int = 300) -> None:
    """Billing stops when the tasks stop, not when the API call returns."""
    if DRY_RUN:
        return
    header("Waiting for the tasks to actually stop")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            running = ecs.list_tasks(cluster=CLUSTER_NAME, desiredStatus="RUNNING")
            count = len(running.get("taskArns", []))
        except Exception as error:
            fail(f"could not list tasks: {error}")
            return
        if count == 0:
            ok("no tasks running - Fargate billing has stopped")
            return
        info(f"{count} task(s) still running...")
        time.sleep(10)
    fail("tasks were still running when the wait timed out; check the console")


def load_balancer_arn() -> Optional[str]:
    try:
        for lb in elbv2.describe_load_balancers().get("LoadBalancers", []):
            if lb["LoadBalancerName"] == LOAD_BALANCER_NAME:
                return lb["LoadBalancerArn"]
    except Exception as error:
        fail(f"could not list load balancers: {error}")
    return None


def load_balancer_eips(lb_arn: str) -> list[dict]:
    """The Elastic IPs attached to the load balancer, recorded BEFORE it is deleted.

    An attached Elastic IP is free; an unattached one is billed. Deleting the load balancer
    is what turns the first into the second, so the addresses have to be identified while
    the interfaces still exist - afterwards there is nothing left to match them against.
    """
    suffix = lb_arn.split("loadbalancer/")[-1]
    try:
        interfaces = ec2.describe_network_interfaces(
            Filters=[{"Name": "description", "Values": [f"ELB {suffix}"]}]
        ).get("NetworkInterfaces", [])
        ids = {interface["NetworkInterfaceId"] for interface in interfaces}
        if not ids:
            return []
        addresses = ec2.describe_addresses().get("Addresses", [])
        return [a for a in addresses if a.get("NetworkInterfaceId") in ids]
    except Exception as error:
        info(f"could not inspect the load balancer's addresses: {error}")
        return []


def delete_load_balancer(eips: list[dict]) -> None:
    header("Deleting the load balancer")
    lb_arn = load_balancer_arn()
    if not lb_arn:
        info("already gone")
        return
    if DRY_RUN:
        would(f"delete {LOAD_BALANCER_NAME}")
        return
    try:
        elbv2.delete_load_balancer(LoadBalancerArn=lb_arn)
        ok(f"deleted {LOAD_BALANCER_NAME}")
    except Exception as error:
        fail(f"could not delete the load balancer: {error}")
        return

    if eips:
        info(f"{len(eips)} Elastic IP(s) will be released once the interfaces detach")


def delete_target_groups() -> None:
    """AWS does not remove target groups with their load balancer.

    Left behind they are recreated on the next setup run under a new ARN, which is what
    silently broke a deploy that had the old ARN written into it. Deleting one needs its
    listener rules gone first, and the listeners go with the load balancer, so this retries.
    """
    header("Deleting the target groups")
    for attempt in range(6):
        remaining = []
        for name in TARGET_GROUPS:
            try:
                described = elbv2.describe_target_groups(Names=[name])
            except elbv2.exceptions.TargetGroupNotFoundException:
                continue
            except Exception as error:
                fail(f"{name}: {error}")
                continue

            for group in described["TargetGroups"]:
                if DRY_RUN:
                    would(f"delete target group {name}")
                    continue
                try:
                    elbv2.delete_target_group(TargetGroupArn=group["TargetGroupArn"])
                    ok(f"deleted {name}")
                except Exception as error:
                    remaining.append(name)
                    if attempt == 5:
                        fail(f"{name} could not be deleted: {error}")
        if not remaining or DRY_RUN:
            return
        if attempt < 5:
            info(f"{len(remaining)} still in use; retrying in 10s")
            time.sleep(10)


def release_elastic_ips(eips: list[dict], timeout: int = 240) -> None:
    """Release the addresses the load balancer was holding, once they are free.

    This is the step whose absence costs real money after a "successful" shutdown: four
    addresses left unattached are about $14 a month for nothing. Each is released only after
    AWS reports it unassociated, so an address still in use is never taken away.
    """
    if not eips:
        return
    header("Releasing the load balancer's Elastic IPs")
    if DRY_RUN:
        for address in eips:
            would(f"release {address['PublicIp']} once detached")
        return

    pending = {a["AllocationId"]: a["PublicIp"] for a in eips if a.get("AllocationId")}
    deadline = time.time() + timeout
    while pending and time.time() < deadline:
        try:
            current = {
                a["AllocationId"]: a
                for a in ec2.describe_addresses(
                    AllocationIds=list(pending)
                ).get("Addresses", [])
            }
        except Exception as error:
            # The same signal in bulk: the addresses have gone with the load balancer.
            if "InvalidAllocationID.NotFound" in str(error):
                for ip in pending.values():
                    ok(f"{ip}: released by AWS with the load balancer")
                return
            fail(f"could not re-check the addresses: {error}")
            return

        for allocation_id in list(pending):
            address = current.get(allocation_id)
            if address is None:
                pending.pop(allocation_id)
                continue
            if address.get("AssociationId"):
                continue
            try:
                ec2.release_address(AllocationId=allocation_id)
                ok(f"released {pending.pop(allocation_id)}")
            except Exception as error:
                # An Application Load Balancer's public addresses belong to the ELB service,
                # not to the account, and AWS releases them itself when the load balancer is
                # deleted. Trying to release one then answers OperationNotPermitted or
                # InvalidAllocationID.NotFound - both mean "already handled, nothing is being
                # billed", which is not a failure and must not read like one.
                text = str(error)
                aws_managed = (
                    "OperationNotPermitted" in text or "InvalidAllocationID.NotFound" in text
                )
                ip = pending.pop(allocation_id, "an address")
                if aws_managed:
                    ok(f"{ip}: released by AWS with the load balancer")
                else:
                    fail(f"{ip}: {error}")

        if pending:
            info(f"{len(pending)} address(es) still attached; waiting...")
            time.sleep(10)

    for ip in pending.values():
        fail(f"{ip} was still attached; release it by hand or it will be billed")


def prune_untagged_images() -> None:
    """Untagged images are layers from superseded builds that nothing can pull."""
    header("Deleting untagged ECR images")
    for repository in ECR_REPOSITORIES:
        try:
            images = ecr.list_images(
                repositoryName=repository, filter={"tagStatus": "UNTAGGED"}
            ).get("imageIds", [])
        except Exception as error:
            info(f"{repository}: {error}")
            continue
        if not images:
            info(f"{repository}: nothing untagged")
            continue
        if DRY_RUN:
            would(f"delete {len(images)} untagged image(s) from {repository}")
            continue
        try:
            # 100 per call is the API's limit.
            for start in range(0, len(images), 100):
                ecr.batch_delete_image(
                    repositoryName=repository, imageIds=images[start : start + 100]
                )
            ok(f"{repository}: deleted {len(images)} untagged image(s)")
        except Exception as error:
            fail(f"{repository}: {error}")


def summary() -> None:
    header("What is left")
    print("""  Stopped or deleted
    - every ECS service scaled to 0 tasks   (Fargate: the main hourly cost)
    - the Application Load Balancer         (about $0.55/day)
    - the target groups
    - the load balancer's Elastic IPs       (about $0.11/day each once detached)

  Still there, and cheap
    - the ECS cluster, empty                free
    - ECR images                            about $0.10/GB/month
    - the S3 transcripts bucket             pennies
    - API Gateway                           per request only
    - Cognito user pool                     free at this size
    - CloudWatch log groups                 pennies
    - the Amplify site                      still serving, but it has no API to call

  Untouched, because it is not AWS
    - MongoDB Atlas: your data is safe and still there

  To bring it all back
    1. py setup_aws_infrastructure.py        recreates the ALB, target groups, wiring
    2. run the "Deploy Backend Services" workflow, or scale the services back to 1
    Expect five to ten minutes, and a NEW API Gateway or ALB address if either was
    recreated - the frontend's REACT_APP_*_API_URL values may need updating.""")


def main() -> int:
    global ecs, elbv2, ec2, ecr, DRY_RUN

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would happen, change nothing"
    )
    parser.add_argument(
        "--prune-untagged", action="store_true", help="also delete untagged ECR images"
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", REGION))
    args = parser.parse_args()
    DRY_RUN = args.dry_run

    load_env_file()
    session = boto3.session.Session(region_name=args.region)
    ecs = session.client("ecs")
    elbv2 = session.client("elbv2")
    ec2 = session.client("ec2")
    ecr = session.client("ecr")

    header("PAMI infrastructure shutdown" + (" (dry run)" if DRY_RUN else ""))
    print(f"\n  region  : {args.region}")
    print(f"  account : {account_id() or 'unknown'}")

    if not DRY_RUN and not args.yes:
        print("\n  This takes the application completely offline until it is set up again.")
        if input("  Continue? (yes/no): ").strip().lower() not in {"yes", "y"}:
            print("\n  Cancelled.")
            return 0

    # Recorded before anything is deleted: afterwards the interfaces are gone and the
    # addresses cannot be matched to this load balancer any more.
    lb_arn = load_balancer_arn()
    eips = load_balancer_eips(lb_arn) if lb_arn else []
    if eips:
        info(f"load balancer is holding {len(eips)} Elastic IP(s): " +
             ", ".join(a["PublicIp"] for a in eips))

    stop_ecs_services()
    wait_for_tasks_to_stop()
    delete_load_balancer(eips)
    delete_target_groups()
    release_elastic_ips(eips)
    if args.prune_untagged:
        prune_untagged_images()

    summary()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        sys.exit(1)
