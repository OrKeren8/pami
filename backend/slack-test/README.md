# Slack Integration Test

This folder contains a basic Slack integration test for the PAMI project.

## What it does

The script demonstrates a working Slack API integration by:

- testing the Slack connection
- creating a public channel if it does not already exist
- sending a message to the channel
- listing public channels in the workspace

## Files

- `index.js` - the main Slack integration test script
- `.env` - contains the Slack bot token (not committed to GitHub)
- `.gitignore` - excludes sensitive and unnecessary files

## Setup

Install dependencies:

npm install

Create a `.env` file with:

SLACK_BOT_TOKEN=<paste-your-bot-token-here>
## Run

node index.js

## Notes

- The Slack bot token must be a Bot User OAuth Token
- The `.env` file must not be uploaded to GitHub
- This test was created as part of the PAMI Slack integration task