require("dotenv").config();

const { WebClient } = require("@slack/web-api");

const token = process.env.SLACK_BOT_TOKEN;

if (!token) {
  console.error("Missing SLACK_BOT_TOKEN in .env file");
  process.exit(1);
}

const client = new WebClient(token, {
  headers: {
    "User-Agent": "pami-slack-test/1.0"
  }
});

async function testSlackConnection() {
  const result = await client.auth.test();

  console.log("Slack connection works");
  console.log("Bot user ID:", result.user_id);
  console.log("Workspace:", result.team);
  console.log("URL:", result.url);
  console.log("");
}

async function createChannelIfNeeded(channelName) {
  try {
    const result = await client.conversations.create({
      name: channelName
    });

    console.log("Channel created successfully");
    console.log("Channel ID:", result.channel.id);
    console.log("Channel name:", result.channel.name);
    console.log("");

    return result.channel.id;
  } catch (error) {
    if (error.data && error.data.error === "name_taken") {
      console.log("Channel already exists:", channelName);
      console.log("");

      const listResult = await client.conversations.list({
        types: "public_channel"
      });

      const existingChannel = listResult.channels.find(function (channel) {
        return channel.name === channelName;
      });

      if (!existingChannel) {
        throw new Error("Channel exists but could not be found in channel list");
      }

      return existingChannel.id;
    }

    throw error;
  }
}

async function sendMessage(channelId) {
  const result = await client.chat.postMessage({
    channel: channelId,
    text: "Hello from the PAMI Slack integration test"
  });

  console.log("Message sent successfully");
  console.log("Channel:", result.channel);
  console.log("Timestamp:", result.ts);
  console.log("");
}

async function listChannels() {
  const result = await client.conversations.list({
    types: "public_channel"
  });

  console.log("Channels fetched successfully");

  for (const channel of result.channels) {
    console.log("- " + channel.name + " (" + channel.id + ")");
  }

  console.log("");
}

async function main() {
  try {
    const channelName = "pami-test-channel";

    await testSlackConnection();
    const channelId = await createChannelIfNeeded(channelName);
    await sendMessage(channelId);
    await listChannels();
  } catch (error) {
    console.error("Slack integration flow failed");

    if (error.data) {
      console.error(error.data);
    } else {
      console.error(error.message);
    }
  }
}

main();