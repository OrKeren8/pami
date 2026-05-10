from fastapi import APIRouter, HTTPException, Request

from slack_service.schemas.slack_schemas import CreateChannelRequest, SendMessageRequest
from slack_service.services.slack_api_service import slack_api_service
from slack_service.services.slack_signature_service import slack_signature_service


router = APIRouter(prefix="/slack", tags=["slack"])


@router.post("/test-connection")
def test_slack_connection():
    return slack_api_service.test_connection()


@router.post("/channels")
def create_channel(request: CreateChannelRequest):
    return slack_api_service.create_channel(request.name)


@router.get("/channels")
def list_channels():
    return slack_api_service.list_channels()


@router.post("/messages")
def send_message(request: SendMessageRequest):
    return slack_api_service.send_message(request.channel, request.text)


@router.post("/events")
async def receive_slack_events(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    is_valid = slack_signature_service.is_valid_request(
        timestamp=timestamp,
        signature=signature,
        body=body,
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    payload = await request.json()

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    return {"ok": True, "event_type": payload.get("type")}


@router.post("/commands")
async def receive_slack_command(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    is_valid = slack_signature_service.is_valid_request(
        timestamp=timestamp,
        signature=signature,
        body=body,
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    form = await request.form()

    command = form.get("command", "")
    text = form.get("text", "")
    user_id = form.get("user_id", "")
    channel_id = form.get("channel_id", "")

    return {
        "response_type": "ephemeral",
        "text": f"Command received: {command} | text={text} | user={user_id} | channel={channel_id}",
    }


@router.post("/interactions")
async def receive_slack_interactions(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    is_valid = slack_signature_service.is_valid_request(
        timestamp=timestamp,
        signature=signature,
        body=body,
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    form = await request.form()
    payload = form.get("payload", "")

    return {
        "ok": True,
        "payload_received": payload != "",
    }