import os

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


load_dotenv()

token = os.getenv("SLACK_BOT_TOKEN")

if not token:
    print("Missing SLACK_BOT_TOKEN in .env file")
    raise SystemExit(1)

client = WebClient(token=token)


def test_slack_connection():
    try:
        result = client.auth_test()

        print("Slack connection works")
        print("Bot user ID:", result["user_id"])
        print("Workspace:", result["team"])
        print("URL:", result["url"])
        print()
    except SlackApiError as error:
        print("Slack connection failed")
        print(error.response["error"])
        raise


def create_channel_if_needed(channel_name):
    try:
        result = client.conversations_create(name=channel_name)

        print("Channel created successfully")
        print("Channel ID:", result["channel"]["id"])
        print("Channel name:", result["channel"]["name"])
        print()

        return result["channel"]["id"]

    except SlackApiError as error:
        if error.response["error"] == "name_taken":
            print("Channel already exists:", channel_name)
            print()

            result = client.conversations_list(types="public_channel")

            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]

            print("Channel exists but was not found in the channel list")
            raise

        print("Channel creation failed")
        print(error.response["error"])
        raise


def send_message(channel_id):
    try:
        result = client.chat_postMessage(
            channel=channel_id,
            text="Hello from the PAMI Slack integration test in Python"
        )

        print("Message sent successfully")
        print("Channel:", result["channel"])
        print("Timestamp:", result["ts"])
        print()
    except SlackApiError as error:
        print("Sending message failed")
        print(error.response["error"])
        raise


def list_channels():
    try:
        result = client.conversations_list(types="public_channel")

        print("Channels fetched successfully")

        for channel in result["channels"]:
            print("- " + channel["name"] + " (" + channel["id"] + ")")

        print()
    except SlackApiError as error:
        print("Fetching channels failed")
        print(error.response["error"])
        raise


def main():
    channel_name = "pami-test-channel"

    test_slack_connection()
    channel_id = create_channel_if_needed(channel_name)
    send_message(channel_id)
    list_channels()


if __name__ == "__main__":
    main()
