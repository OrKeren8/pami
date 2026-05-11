# PAMI AI Conversation Service

A FastAPI microservice for AI-powered conversations with OpenAI integration.

## Overview

This service provides AI conversation capabilities for the PAMI system:

- AI-powered conversations using OpenAI GPT models
- REST API for conversation management
- Context-aware responses linked to project context nodes

## Architecture

- **Framework**: FastAPI
- **AI Services**: OpenAI GPT models for conversational AI
- **Models**: Pydantic for data validation

## AWS Services Integration

### AI Conversation Service

The service integrates with AWS services for AI-powered conversations:

- **AWS Bedrock**: Provides access to Anthropic Claude for natural language processing
- **AWS S3**: Stores conversation history and metadata for persistence and scalability

Conversations are stored in S3 with the following structure:

```
conversations/{conversation_id}.json
```

## API Endpoints

### AI Conversations

- `GET /health` - Health check for AI conversation service
- `POST /ai-conversations/` - Create a new AI conversation for a context node
- `POST /ai-conversations/{conversation_id}/messages` - Send a message and get AI response
- `GET /ai-conversations/{conversation_id}` - Get conversation history
- `GET /ai-conversations/node/{context_node_id}` - List all conversations for a context node
- `DELETE /ai-conversations/{conversation_id}` - Delete a conversation

## Configuration

### Environment Variables

Create a `.env` file and configure the following variables:

- `SERVICE_NAME`: Service name (default: ai-conversation-service)
- `DEBUG`: Debug mode (default: true)
- `LOG_LEVEL`: Logging level (default: INFO)
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-4o-mini)

### OpenAI API Key Setup

The service requires the following AWS permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
    }
  ]
}
```

## Running the Service

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Set environment variables (create .env file)

3. Run the service:
   ```bash
   uv run src/ai_conversation_service/main.py
   ```

## Testing

```bash
uv run pytest tests/ -v
```

### AI Conversation Service Testing

The AI conversation service includes comprehensive unit tests and integration tests:

- Unit tests for service logic, S3 operations, and Bedrock integration
- Integration tests for API endpoints
- Mocked AWS services for reliable testing

Note: AI conversation tests require AWS credentials to be configured for full functionality. Tests will skip AWS-dependent features if credentials are not available.

## Development

### Adding New AI Features

1. Extend the `AIConversationService` class for new functionality
2. Add corresponding API endpoints in `ai_conversations.py`
3. Write comprehensive tests
4. Update this README with new endpoints and configuration

### Conversation Storage

Conversations are stored in S3 as JSON files with the following structure:

```json
{
    "conversation_id": "uuid",
    "context_node_id": "node_id",
    "project_id": "project_id",
    "title": "Conversation Title",
    "messages": [
        {
            "role": "user|assistant",
            "content": "message content",
            "timestamp": "ISO datetime",
            "context_snapshot": {...},
            "model": "model_id",
            "tokens_used": 150
        }
    ],
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime",
    "status": "active|archived"
}
```

## Deployment

The service is containerized with Docker and can be deployed to:

- AWS ECS Fargate
- Kubernetes
- Any container orchestration platform

Default port: 8001
