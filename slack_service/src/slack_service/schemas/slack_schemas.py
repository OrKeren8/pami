from pydantic import BaseModel


class CreateChannelRequest(BaseModel):
    name: str


class SendMessageRequest(BaseModel):
    channel: str
    text: str


class SlackEventRequest(BaseModel):
    type: str
    message: str