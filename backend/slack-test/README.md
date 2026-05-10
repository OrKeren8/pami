# Slack Integration Test

This folder contains a basic Slack integration test for the PAMI project.

## What it does

The script demonstrates a working Slack API integration by:

- testing the Slack connection
- creating a public channel if it does not already exist
- sending a message to the channel
- listing public channels in the workspace

## Files

- `slack_test.py` - the main Slack integration test script
- `requirements.txt` - Python dependencies
- `.env` - contains the Slack bot token (not committed to GitHub)
- `.gitignore` - excludes sensitive and unnecessary files

## Setup

Create and activate a virtual environment, then install dependencies:

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

Create a `.env` file with:

SLACK_BOT_TOKEN=<paste-your-bot-token-here>

## Run

python slack_test.py

## Notes

- The Slack bot token must be a Bot User OAuth Token
- The `.env` file must not be uploaded to GitHub
- This test was converted from Node.js to Python to match the main project language

- Files were resaved in Python during the migration to keep the Slack test aligned with the project stack
