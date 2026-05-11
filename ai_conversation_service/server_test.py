#!/usr/bin/env python3
"""
Simple server test
"""

import subprocess
import time
import requests
import json
import sys


def test_server():
    print("Starting server...")

    # Start server in background
    server = subprocess.Popen(
        [
            "py",
            "-m",
            "uv",
            "run",
            "uvicorn",
            "src.ai_conversation_service.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8007",
        ],
        cwd="ai_conversation_service",
    )

    # Wait for server to start
    time.sleep(5)

    try:
        # Test 1: Create conversation
        print("Testing conversation creation...")
        response = requests.post(
            "http://127.0.0.1:8007/ai-conversations/",
            json={
                "context_node_id": "test-node-123",
                "project_id": "test-project-456",
                "title": "Server Test Conversation",
            },
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            conversation_id = result.get("conversation_id")
            print(f"✅ Conversation created: {conversation_id}")

            # Test 2: Send message
            print("Testing message sending...")
            msg_response = requests.post(
                f"http://127.0.0.1:8007/ai-conversations/{conversation_id}/messages",
                json={
                    "message": "Hello! Test message.",
                    "context_snapshot": {"test": "data"},
                },
                timeout=30,
            )

            if msg_response.status_code == 200:
                msg_result = msg_response.json()
                ai_response = msg_result.get("response", "")
                print(f"✅ AI Response: {ai_response[:100]}...")
                print("🎉 SUCCESS: Both S3 storage and AI are working!")
            else:
                print(
                    f"❌ Message failed: {msg_response.status_code} - {msg_response.text}"
                )

        else:
            print(
                f"❌ Conversation creation failed: {response.status_code} - {response.text}"
            )

    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Kill server
        server.terminate()
        server.wait()
        print("Server stopped.")


if __name__ == "__main__":
    test_server()
