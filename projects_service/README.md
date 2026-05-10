# PAMI Projects Service

A FastAPI microservice for managing projects in the PAMI system.

## Overview

This service handles all project-related operations including:

- Project CRUD operations
- Task management
- Context-tree indexing and management
- AI-powered conversations with AWS Bedrock integration
- Conversation storage and retrieval via AWS S3

## Architecture

- **Framework**: FastAPI
- **Database**: MongoDB with Motor (async driver) and Beanie (ODM)
- **AI Services**: AWS Bedrock (Claude) for conversational AI, AWS S3 for conversation storage
- **Models**: Pydantic for data validation

## Collections

- `projects`: Project information (name, goal, status)
- `tasks`: Task details (title, status, due date, assignee, dependencies)
- `context_tree`: Hierarchical project tree nodes

## AWS Services Integration

### AI Conversation Service

The service integrates with AWS services for AI-powered conversations:

- **AWS Bedrock**: Provides access to Anthropic Claude for natural language processing
- **AWS S3**: Stores conversation history and metadata for persistence and scalability
- **AWS IAM**: Manages permissions for secure access to AI and storage services

Conversations are stored in S3 with the following structure:
```
conversations/{context_node_id}/{conversation_id}.json
```

## API Endpoints

### Projects

- `GET /projects` - List all projects
- `POST /projects` - Create a new project
- `GET /projects/{id}` - Get project by ID
- `PUT /projects/{id}` - Update project
- `DELETE /projects/{id}` - Delete project

### Tasks

- `GET /projects/{project_id}/tasks` - List tasks for a project
- `POST /projects/{project_id}/tasks` - Create a new task
- `GET /tasks/{id}` - Get task by ID
- `PUT /tasks/{id}` - Update task
- `DELETE /tasks/{id}` - Delete task

### Context Tree

- `GET /projects/{project_id}/context-tree` - Get context tree for a project
- `POST /projects/{project_id}/context-tree/nodes` - Add a node to the context tree
- `PUT /context-tree/nodes/{id}` - Update a node
- `DELETE /context-tree/nodes/{id}` - Delete a node

### AI Conversations

- `GET /ai-conversations/health` - Health check for AI conversation service
- `POST /ai-conversations/` - Create a new AI conversation for a context node
- `POST /ai-conversations/{conversation_id}/messages` - Send a message and get AI response
- `GET /ai-conversations/{conversation_id}` - Get conversation history
- `GET /ai-conversations/node/{context_node_id}` - List all conversations for a context node
- `DELETE /ai-conversations/{conversation_id}` - Delete a conversation

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

- `MONGODB_URL`: MongoDB connection string
- `DATABASE_NAME`: MongoDB database name
- `AWS_REGION`: AWS region for Bedrock and S3 services
- `S3_BUCKET_NAME`: S3 bucket for conversation storage
- `BEDROCK_MODEL_ID`: Bedrock model ID (default: anthropic.claude-3-sonnet-20240229-v1:0)
- `AWS_ACCESS_KEY_ID`: AWS access key (optional if using IAM roles)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (optional if using IAM roles)

### AWS Permissions Required

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
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
        }
    ]
}
```

## Testing

```bash
pytest
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
