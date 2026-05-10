# PAMI Projects Service

A FastAPI microservice for managing projects in the PAMI system.

## Overview

This service handles all project-related operations including:

- Project CRUD operations
- Task management
- Context-tree indexing and management
- Integration with MongoDB

## Architecture

- **Framework**: FastAPI
- **Database**: MongoDB with Motor (async driver) and Beanie (ODM)
- **Models**: Pydantic for data validation

## Collections

- `projects`: Project information (name, goal, status)
- `tasks`: Task details (title, status, due date, assignee, dependencies)
- `context_tree`: Hierarchical project tree nodes

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

## Running the Service

1. Install dependencies:

   ```bash
   pip install -e .
   ```

2. Set environment variables (see .env.example)

3. Run the service:
   ```bash
   uvicorn src.projects_service.main:app --reload
   ```

## Testing

```bash
pytest
```
# CI/CD Test - Fri, May  8, 2026  1:01:15 PM
