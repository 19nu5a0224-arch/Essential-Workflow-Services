# N8N Async Wrapper Usage Documentation

## Overview

The async wrapper provides a flexible interface for making HTTP requests to the n8n API using `*args` and `**kwargs` parameters. This matches the Swagger API documentation structure you're seeing.

## API Endpoints

### Generic Async Wrapper
- **GET** `/features/n8n-workflows/wrapper`
- **POST** `/features/n8n-workflows/wrapper` 
- **PUT** `/features/n8n-workflows/wrapper`
- **PATCH** `/features/n8n-workflows/wrapper`
- **DELETE** `/features/n8n-workflows/wrapper`

### Original Endpoint (Still Functional)
- **GET** `/features/n8n-workflows`

## Usage Examples

### GET Request
```python
import httpx

# Get all workflows
response = await httpx.get("/features/n8n-workflows/wrapper")
# or with query parameters
response = await httpx.get(
    "/features/n8n-workflows/wrapper",
    params={
        "includeData": "false",
        "limit": 10,
        "cursor": "your_cursor"
    }
)
```

### POST Request
```python
# Create a new workflow
response = await httpx.post(
    "/features/n8n-workflows/wrapper",
    json={
        "name": "My Workflow",
        "nodes": [...],
        "connections": {...}
    }
)
```

### PUT Request  
```python
# Update workflow tags
response = await httpx.put(
    "/features/n8n-workflows/wrapper",
    json=[{"id": "tag_id_1"}],
    params={"endpoint": "/workflows/{workflow_id}/tags"}
)
```

### DELETE Request
```python
# Delete a workflow
response = await httpx.delete(
    "/features/n8n-workflows/wrapper",
    params={"endpoint": "/workflows/{workflow_id}"}
)
```

## Parameter Handling

### Method Parameter
- `method`: HTTP method (GET, POST, PUT, PATCH, DELETE)
- Default: "GET"

### Endpoint Parameter  
- `endpoint`: API endpoint path
- Default: "/workflows"

### Authentication
- Uses `get_current_user` dependency for authentication
- Automatically includes API headers

## Response Format

### Success Response
```json
{
    "data": [...],
    "nextCursor": "..."
}
```

### Error Response
```json
{
    "error": "Error message",
    "status_code": 400,
    "response_text": "Detailed error response"
}
```

## Integration with Existing Code

The async wrapper integrates seamlessly with your existing n8n service:

```python
from services.n8n_service import N8NService

n8n_service = N8NService()

# Using the async wrapper
result = await n8n_service.async_wrapper(
    method="POST",
    endpoint="/workflows",
    name="My Workflow",
    nodes=[...],
    connections={...}
)
```

## Key Features

1. **Flexible Parameters**: Accepts any parameters via `*args` and `**kwargs`
2. **Automatic Authentication**: Uses FastAPI dependency injection
3. **Error Handling**: Comprehensive error responses
4. **HTTP Method Support**: All standard HTTP methods
5. **Backward Compatibility**: Original endpoint remains functional

## Common Use Cases

### List Workflows
```python
response = await httpx.get("/features/n8n-workflows/wrapper")
```

### Create Workflow
```python
response = await httpx.post(
    "/features/n8n-workflows/wrapper",
    json=workflow_data
)
```

### Update Workflow
```python
response = await httpx.patch(
    "/features/n8n-workflows/wrapper",
    params={"endpoint": "/workflows/workflow_id"},
    json=updated_data
)
```

### Get Workflow Executions
```python
response = await httpx.get(
    "/features/n8n-workflows/wrapper",
    params={"endpoint": "/executions", "workflowId": "workflow_id"}
)
```

## Migration from Original Implementation

If you were using the original `/features/n8n-workflows` endpoint, you can now use the more flexible wrapper:

**Before:**
```python
response = await httpx.get("/features/n8n-workflows?dashboard_id=123")
```

**After:**
```python
response = await httpx.get(
    "/features/n8n-workflows/wrapper",
    params={"dashboard_id": "123"}
)
```

The wrapper provides the same functionality with enhanced flexibility.