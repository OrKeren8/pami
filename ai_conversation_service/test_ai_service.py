#!/usr/bin/env python3
"""
Test script for AI Conversation Service S3 and OpenAI functionality
"""

import asyncio
import json
import os
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
)


async def test_ai_conversation_service():
    """Test the AI conversation service with S3 storage and OpenAI integration."""

    print("Testing AI Conversation Service")
    print("=" * 50)

    # Initialize the service
    print("Initializing AI Conversation Service...")
    service = AIConversationService()

    if not service.openai_client:
        print("OpenAI client not initialized")
        return

    if not service.s3_client:
        print("S3 client not initialized")
        return

    print("Service initialized successfully")
    print()

    # Test 1: Create a conversation
    print("Test 1: Creating a conversation...")
    try:
        conversation = await service.create_conversation(
            context_node_id="test-node-123",
            project_id="test-project-456",
            title="Test AI Conversation",
        )
        conversation_id = conversation.conversation_id
        print(f"Conversation created: {conversation_id}")
        print(f"   Title: {conversation.title}")
        print(f"   Context Node: {conversation.context_node_id}")

        # Debug: Check if we can retrieve it immediately
        print("   Checking if conversation can be retrieved...")
        retrieved = await service.get_conversation(conversation_id)
        if retrieved:
            print("   SUCCESS: Conversation can be retrieved")
        else:
            print("   ERROR: Conversation cannot be retrieved")

    except Exception as e:
        print(f"Failed to create conversation: {e}")
        return

    print()

    # Test 2: Send a message and get AI response
    print("Test 2: Sending message and getting AI response...")
    try:
        user_message = "Hello! Can you help me understand how machine learning works?"
        ai_response = await service.send_message(
            conversation_id=conversation_id,
            user_message=user_message,
            context_snapshot={"project": "test", "context": "learning"},
        )
        print(f"AI Response received: {ai_response[:100]}...")
    except Exception as e:
        print(f"Failed to send message: {e}")
        return

    print()

    # Test 3: Get conversation history
    print("Test 3: Retrieving conversation history...")
    try:
        history = await service.get_conversation_history(conversation_id)
        if history:
            print(f"Conversation history retrieved")
            print(f"   Total messages: {len(history['messages'])}")
            print(f"   Title: {history['title']}")
            for i, msg in enumerate(history["messages"][-2:]):  # Show last 2 messages
                role = msg["role"]
                content = (
                    msg["content"][:50] + "..."
                    if len(msg["content"]) > 50
                    else msg["content"]
                )
                print(f"   Message {i+1}: {role} - {content}")
        else:
            print("No conversation history found")
    except Exception as e:
        print(f"Error retrieving conversation history: {e}")

    print()

    # Test 4: List conversations for node
    print("Test 4: Listing conversations for context node...")
    try:
        conversations = await service.list_conversations_for_node("test-node-123")
        print(f"Found {len(conversations)} conversations for node")
        if conversations:
            for conv in conversations:
                print(
                    f"   - {conv['conversation_id']}: {conv['title']} ({conv['message_count']} messages)"
                )
    except Exception as e:
        print(f"Error listing conversations: {e}")

    print()

    # Test 5: Get conversation by ID
    print("Test 5: Retrieving conversation by ID...")
    try:
        retrieved_conversation = await service.get_conversation(conversation_id)
        if retrieved_conversation:
            print(f"Conversation retrieved: {retrieved_conversation.conversation_id}")
            print(f"   Messages: {len(retrieved_conversation.messages)}")
        else:
            print("Conversation not found")
    except Exception as e:
        print(f"Error retrieving conversation: {e}")

    print()
    print("All tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_ai_conversation_service())
