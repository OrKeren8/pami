# AI-Powered Tree Organization

## Overview

The AI service now automatically analyzes and organizes nodes in the project tree based on conversation context and existing tree structure.

## How It Works

### Flow Diagram

```
1. User creates a new node in projects service
2. Projects service creates the node in database
3. Projects service creates AI conversation for the node
4. Projects service sends entire tree context to AI service
5. AI service:
   - Reads conversation history
   - Analyzes existing tree structure
   - Suggests optimal parent placement
   - Generates summary and extracts topics
6. Projects service updates node with AI suggestions
7. Projects service updates tree relationships (parent-child links)
```

### API Endpoint

**POST** `/ai/tree-analysis/organize-node`

**Request:**

```json
{
  "node_id": "uuid-of-new-node",
  "conversation_id": "conversation-uuid",
  "current_tree": [
    {
      "id": "node-1-id",
      "parent_id": null,
      "text": "Main Project Goal",
      "summary": "Overview of the main goal",
      "topics": ["planning", "strategy"],
      "node_type": "goal"
    },
    {
      "id": "node-2-id",
      "parent_id": "node-1-id",
      "text": "Sub-task A",
      "summary": "Details about sub-task",
      "topics": ["implementation"],
      "node_type": "task"
    }
  ]
}
```

**Response:**

```json
{
  "node_id": "uuid-of-new-node",
  "suggested_parent_id": "node-1-id",
  "summary": "AI-generated summary of the node based on conversation",
  "topics": ["extracted", "relevant", "topics"],
  "reasoning": "This node discusses implementation details related to the main goal, so it should be a child of node-1"
}
```

## AI Analysis Process

The AI analyzes:

1. **Conversation Content**: What was discussed about this node
2. **Tree Structure**: Existing hierarchy and relationships
3. **Node Types**: Whether this should be a goal, task, milestone, etc.
4. **Thematic Similarity**: Which existing nodes are topically related

The AI then suggests:

- **Parent Node**: Best hierarchical placement
- **Summary**: Concise description of the node's purpose
- **Topics**: Relevant tags for categorization
- **Reasoning**: Explanation of the placement decision

## Configuration

### AI Service

No additional configuration needed - uses existing OpenAI setup.

### Projects Service

The AI organization happens automatically after node creation. No configuration required.

## Error Handling

The system is designed with graceful degradation:

- If AI service is unavailable: Node is still created with manual parent/summary
- If AI analysis fails: Node keeps its original values
- If conversation has no messages: AI uses only tree structure for analysis

## Lean Implementation

This is a **single-endpoint, single-call** solution:

1. One HTTP request from projects → AI service
2. AI returns complete organization suggestion
3. Projects service applies the suggestions
4. Tree structure updated in one transaction

No polling, webhooks, or complex state management needed.

## Testing

### Manual Test Flow

1. Create a project
2. Create a root node (e.g., "Build mobile app")
3. Have a conversation about it
4. Create another node (e.g., "Design user interface")
5. Have a conversation about UI design
6. Check that the AI placed it as a child of the main goal
7. Verify summary and topics were auto-generated

### API Test

```bash
# Create a node and let AI organize it
curl -X POST http://localhost:8000/projects/{project_id}/context-tree \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Design login screen",
    "node_type": "task"
  }'

# Check the response includes AI-generated summary and topics
# Check parent_id was set by AI based on tree analysis
```

## Future Enhancements

Possible improvements:

- Allow user to override AI suggestions
- Support for bulk reorganization of existing trees
- AI-powered tree refactoring suggestions
- Confidence scores for placement suggestions
- Learning from user corrections to improve suggestions
