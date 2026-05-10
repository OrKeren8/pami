# Slack Service

This service provides a dedicated FastAPI-based Slack integration server for the PAMI project.

## Purpose

The service is separated from the main backend and is responsible for communication between PAMI and Slack.

It supports:

- outbound requests from the application to Slack
- inbound requests from Slack to the application
- Slack request signature validation
- Slack URL verification flow

## Available Endpoints

### Health

- `GET /health`

### Outbound Slack Endpoints

- `POST /slack/test-connection`
- `POST /slack/channels`
- `GET /slack/channels`
- `POST /slack/messages`

### Inbound Slack Endpoints

- `POST /slack/events`
- `POST /slack/commands`
- `POST /slack/interactions`

## Environment Variables

Create a local `.env` file with:

```env
SLACK_BOT_TOKEN=<paste-your-bot-token-here>
SLACK_SIGNING_SECRET=<paste-your-signing-secret-here>
```

## Local Run

First enter the service directory, create and activate a virtual environment, and install dependencies:

```bash
cd slack_service
python -m venv venv
venv\Scripts\activate
pip install -e .
```

Run the service:

```bash
uvicorn --app-dir src slack_service.main:app --reload --port 8001
```

## Notes

- `.env` must not be committed to GitHub
- the service is intended to be deployed as a separate server from the main backend
- inbound Slack requests are validated using the Slack signing secret