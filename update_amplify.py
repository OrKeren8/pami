#!/usr/bin/env python3
"""
Quick script to update Amplify environment variables
"""

import boto3

REGION = "us-east-1"
API_GATEWAY_URL = "https://6ogy7m6whd.execute-api.us-east-1.amazonaws.com"

amplify = boto3.client("amplify", region_name=REGION)

print("Finding Amplify apps...")
response = amplify.list_apps()

apps = response.get("apps", [])
if not apps:
    print("No Amplify apps found!")
    exit(1)

print(f"\nFound {len(apps)} app(s):")
for i, app in enumerate(apps, 1):
    print(f"{i}. {app['name']} (ID: {app['appId']})")
    print(f"   URL: https://main.{app['defaultDomain']}")

if len(apps) == 1:
    selected_app = apps[0]
    print(f"\nUsing app: {selected_app['name']}")
else:
    selection = input("\nSelect app number: ")
    selected_app = apps[int(selection) - 1]

app_id = selected_app["appId"]

print(f"\nUpdating environment variables for {selected_app['name']}...")
amplify.update_app(
    appId=app_id,
    environmentVariables={
        "REACT_APP_PROJECTS_API_BASE_URL": API_GATEWAY_URL,
        "REACT_APP_SLACK_API_BASE_URL": f"{API_GATEWAY_URL}/slack",
        "_LIVE_UPDATES": '[{"pkg":"@aws-amplify/cli","type":"npm","version":"latest"}]',
    },
)

print(f"✓ Updated environment variables")
print(f"  REACT_APP_PROJECTS_API_BASE_URL = {API_GATEWAY_URL}")
print(f"  REACT_APP_SLACK_API_BASE_URL = {API_GATEWAY_URL}/slack")

print(f"\nTriggering new deployment...")
try:
    amplify.start_job(appId=app_id, branchName="main", jobType="RELEASE")
    print(f"✓ Deployment started!")
    print(
        f"\nWait 2-3 minutes, then check: https://main.{selected_app['defaultDomain']}"
    )
except Exception as e:
    print(f"Could not trigger deployment: {e}")
    print("Please manually redeploy from AWS Console → Amplify → Deployments")
