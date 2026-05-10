from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from slack_service.core.config import settings


class SlackApiService:
    def __init__(self):
        self.client = WebClient(token=settings.slack_bot_token)

    def test_connection(self):
        try:
            result = self.client.auth_test()

            return {
                "ok": True,
                "user_id": result["user_id"],
                "team": result["team"],
                "url": result["url"],
            }
        except SlackApiError as error:
            return {
                "ok": False,
                "error": error.response["error"],
            }

    def create_channel(self, name: str):
        try:
            result = self.client.conversations_create(name=name)

            return {
                "ok": True,
                "channel_id": result["channel"]["id"],
                "channel_name": result["channel"]["name"],
            }
        except SlackApiError as error:
            return {
                "ok": False,
                "error": error.response["error"],
            }

    def send_message(self, channel: str, text: str):
        try:
            result = self.client.chat_postMessage(
                channel=channel,
                text=text,
            )

            return {
                "ok": True,
                "channel": result["channel"],
                "timestamp": result["ts"],
            }
        except SlackApiError as error:
            return {
                "ok": False,
                "error": error.response["error"],
            }

    def list_channels(self):
        try:
            result = self.client.conversations_list(types="public_channel")

            channels = []

            for channel in result["channels"]:
                channels.append(
                    {
                        "id": channel["id"],
                        "name": channel["name"],
                    }
                )

            return {
                "ok": True,
                "channels": channels,
            }
        except SlackApiError as error:
            return {
                "ok": False,
                "error": error.response["error"],
            }


slack_api_service = SlackApiService()