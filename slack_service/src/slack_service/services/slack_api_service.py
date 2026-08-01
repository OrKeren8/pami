import logging
import re

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from slack_service.core.config import settings

logger = logging.getLogger(__name__)


class SlackApiService:
    def __init__(self):
        self.client = WebClient(token=settings.slack_bot_token)
        self._user_name_cache = {}

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
                "error": self._get_slack_error(error),
            }

    def create_channel(self, name: str):
        normalized_name = self._normalize_channel_name(name)

        if normalized_name == "":
            return {
                "ok": False,
                "error": "invalid_channel_name",
                "message": "Channel name is empty after normalization.",
            }

        existing_channel = self._find_channel_by_name(normalized_name)

        if existing_channel is not None:
            return {
                "ok": True,
                "channel_id": existing_channel["id"],
                "channel_name": existing_channel["name"],
                "already_exists": True,
                "created": False,
            }

        try:
            result = self.client.conversations_create(name=normalized_name)

            return {
                "ok": True,
                "channel_id": result["channel"]["id"],
                "channel_name": result["channel"]["name"],
                "already_exists": False,
                "created": True,
            }

        except SlackApiError as error:
            slack_error = self._get_slack_error(error)

            if slack_error == "name_taken":
                existing_channel = self._find_channel_by_name(normalized_name)

                if existing_channel is not None:
                    return {
                        "ok": True,
                        "channel_id": existing_channel["id"],
                        "channel_name": existing_channel["name"],
                        "already_exists": True,
                        "created": False,
                    }

            return {
                "ok": False,
                "error": slack_error,
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
                "error": self._get_slack_error(error),
            }

    def list_channels(self):
        try:
            channels = self._get_all_public_channels()

            return {
                "ok": True,
                "channels": channels,
            }
        except SlackApiError as error:
            return {
                "ok": False,
                "error": self._get_slack_error(error),
            }

    def get_channel_messages(self, channel: str, limit: int = 50):
        try:
            result = self.client.conversations_history(channel=channel, limit=limit)

            messages = [
                self._format_message(raw_message)
                for raw_message in result.get("messages", [])
                if raw_message.get("subtype") is None or raw_message.get("subtype") == "bot_message"
            ]
            messages.reverse()

            return {
                "ok": True,
                "messages": messages,
            }
        except SlackApiError as error:
            return {
                "ok": False,
                "error": self._get_slack_error(error),
                **self._scope_detail(error),
            }

    def _format_message(self, raw_message: dict):
        user_id = raw_message.get("user") or raw_message.get("bot_id")

        return {
            "id": raw_message.get("ts"),
            "user_id": user_id,
            "user_name": self._get_user_name(raw_message.get("user")),
            "text": raw_message.get("text", ""),
            "ts": raw_message.get("ts"),
            "is_bot": raw_message.get("user") is None,
        }

    def _get_user_name(self, user_id: str):
        if not user_id:
            return "Slack Bot"

        if user_id in self._user_name_cache:
            return self._user_name_cache[user_id]

        try:
            result = self.client.users_info(user=user_id)
            profile = result["user"].get("profile", {})
            name = profile.get("display_name") or profile.get("real_name") or result["user"].get("name") or user_id
        except SlackApiError:
            name = user_id

        self._user_name_cache[user_id] = name
        return name

    def _find_channel_by_name(self, name: str):
        channels = self._get_all_public_channels()

        for channel in channels:
            if channel["name"] == name:
                return channel

        return None

    def _get_all_public_channels(self):
        channels = []
        cursor = ""

        while True:
            if cursor == "":
                result = self.client.conversations_list(
                    types="public_channel",
                    exclude_archived=True,
                    limit=200,
                )
            else:
                result = self.client.conversations_list(
                    types="public_channel",
                    exclude_archived=True,
                    limit=200,
                    cursor=cursor,
                )

            for channel in result["channels"]:
                channels.append(
                    {
                        "id": channel["id"],
                        "name": channel["name"],
                    }
                )

            response_metadata = result.get("response_metadata", {})
            cursor = response_metadata.get("next_cursor", "")

            if cursor == "":
                break

        return channels

    def _normalize_channel_name(self, name: str):
        normalized_name = name.strip().lower()
        normalized_name = normalized_name.replace(" ", "-")
        normalized_name = re.sub(r"[^a-z0-9_-]", "-", normalized_name)
        normalized_name = re.sub(r"-+", "-", normalized_name)
        normalized_name = normalized_name.strip("-_")
        normalized_name = normalized_name[:80]

        return normalized_name

    def _get_slack_error(self, error: SlackApiError):
        if error.response is not None and "error" in error.response:
            return error.response["error"]

        return "unknown_slack_error"

    def _scope_detail(self, error: SlackApiError):
        """The scopes Slack says are needed, which its error alone does not reveal.

        Without these, a missing_scope reads as a generic permission problem and the only way
        to learn which scope is missing is to call the Slack API by hand.
        """
        if error.response is None:
            return {}

        detail = {
            key: error.response[key]
            for key in ("needed", "provided")
            if key in error.response
        }

        if detail:
            logger.warning(
                f"Slack rejected the call: needed={detail.get('needed')} "
                f"provided={detail.get('provided')}"
            )

        return detail


slack_api_service = SlackApiService()