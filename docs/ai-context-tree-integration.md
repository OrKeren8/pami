# AI Conversation & Context Tree Integration

## Overview
The context tree nodes are now automatically linked to AI conversations. When a new context tree node is created, an AI conversation is automatically created and linked to it.

## Implementation Details

### Database Schema Changes
- Added `conversation_id` field to `ContextTreeNode` model
- Field is optional (nullable) to support existing nodes without conversations

### Service Integration
When a context tree node is created:
1. Node is created in the database
2. HTTP POST request is sent to AI Conversation Service to create a new conversation
3. The returned `conversation_id` is stored in the node
4. If AI service is unavailable, the node is still created (graceful degradation)

### Configuration
**Local Development:**
```bash
AI_SERVICE_URL=http://localhost:8001
```

**AWS Deployment:**
```bash
AI_SERVICE_URL=http://pami-alb-550898099.us-east-1.elb.amazonaws.com/ai
```

The AI service URL is configured in:
- `projects_service/src/projects_service/core/config.py`
- `.github/workflows/deploy-backend.yml` (environment variable in task definition)

### API Response Changes
The `ContextTreeNodeResponse` now includes `conversation_id`:
```json
{
  "id": "uuid-here",
  "parent_id": "parent-uuid",
  "children_ids": [],
  "text": "Node content",
  "summary": null,
  "topics": [],
  "project_id": "project-uuid",
  "node_type": "goal",
  "conversation_id": "conversation-uuid-here",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### Error Handling
- If AI service is unreachable, the node is still created with `conversation_id: null`
- Errors are logged but don't prevent node creation
- This ensures the projects service remains functional even if AI service is down

### Inter-Service Communication
- Uses `httpx.AsyncClient` for HTTP requests
- 10-second timeout to prevent hanging requests
- Calls the AI service endpoint: `POST /ai/ai-conversations/`
- Sends: `context_node_id`, `project_id`, and `title`
- Receives: `conversation_id` in response

## Testing
To test the integration:

1. **Start both services:**
   ```bash
   # Terminal 1 - AI Service
   cd ai_conversation_service
   uvicorn src.ai_conversation_service.main:app --port 8001
   
   # Terminal 2 - Projects Service
   cd projects_service
   uvicorn src.projects_service.main:app --port 8000
   ```

2. **Create a new context tree node:**
   ```bash
   curl -X POST http://localhost:8000/projects/{project_id}/context-tree \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Test node",
       "node_type": "goal"
     }'
   ```

3. **Verify the response includes `conversation_id`**

4. **Check AI service to confirm conversation was created:**
   ```bash
   curl http://localhost:8001/ai/ai-conversations/{conversation_id}
   ```

## Future Enhancements
- Consider using service discovery or internal DNS for service-to-service communication in AWS
- Add retry logic for failed AI conversation creation
- Implement background job to create conversations for existing nodes without them
- Add webhook or event-driven architecture for better decoupling
