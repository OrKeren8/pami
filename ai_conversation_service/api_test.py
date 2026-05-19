#!/usr/bin/env python3
"""
Direct API test for AI Conversation Service
"""

import asyncio
import httpx
import json
import time

BASE_URL = "http://127.0.0.1:8005"


async def test_api():
    """Test the AI conversation API directly."""

    print("🚀 Testing AI Conversation API")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test 1: Create conversation
            print("📝 Test 1: Creating conversation...")
            create_payload = {
                "context_node_id": "test-node-123",
                "project_id": "test-project-456",
                "title": "API Test Conversation",
            }

            response = await client.post(
                f"{BASE_URL}/ai-conversations/",
                json=create_payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                conversation_id = result.get("conversation_id")
                print(f"✅ Conversation created: {conversation_id}")
            else:
                print(
                    f"❌ Failed to create conversation: {response.status_code} - {response.text}"
                )
                return

            # Wait a moment
            await asyncio.sleep(1)

            # Test 2: Send message
            print("\n💬 Test 2: Sending message...")
            message_payload = {
                "message": "Hello! Can you explain what machine learning is?",
                "context_snapshot": {"project": "test", "context": "learning"},
            }

            response = await client.post(
                f"{BASE_URL}/ai-conversations/{conversation_id}/messages",
                json=message_payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result.get("response", "")
                print(f"✅ AI Response: {ai_response[:100]}...")
            else:
                print(
                    f"❌ Failed to send message: {response.status_code} - {response.text}"
                )

        except httpx.RequestError as e:
            print(f"❌ Request error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    print("\n" + "=" * 50)
    print("🎉 API test completed!")


if __name__ == "__main__":
    asyncio.run(test_api())
